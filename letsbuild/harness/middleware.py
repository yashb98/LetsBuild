"""Abstract Middleware base class and MiddlewareChain orchestrator.

The middleware chain wraps every pipeline layer execution, running pre-processing
steps in order and post-processing steps in reverse order. This follows the
10-stage middleware pattern defined in the architecture specification.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable  # noqa: TC003
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from letsbuild.pipeline.state import PipelineState

logger = structlog.get_logger()


class Middleware(ABC):
    """Abstract base class for all pipeline middleware.

    Every middleware implements before() and after() hooks that wrap
    layer execution. The chain runs before() in order (1-10) and
    after() in reverse order (10-1).
    """

    @abstractmethod
    async def before(self, state: PipelineState) -> PipelineState:
        """Pre-processing hook run before a pipeline layer executes.

        Args:
            state: The current pipeline state.

        Returns:
            The (potentially modified) pipeline state.

        Raises:
            Exception: To abort the pipeline if a fatal condition is detected.
        """
        ...

    @abstractmethod
    async def after(self, state: PipelineState) -> PipelineState:
        """Post-processing hook run after a pipeline layer executes.

        Args:
            state: The current pipeline state (with layer results).

        Returns:
            The (potentially modified) pipeline state.
        """
        ...

    @property
    def name(self) -> str:
        """Human-readable middleware name."""
        return self.__class__.__name__


class MiddlewareChain:
    """Ordered chain of middleware that wraps pipeline layer execution.

    Middleware before() hooks run in insertion order (index 0 first).
    Middleware after() hooks run in reverse order (last middleware first).
    This creates a symmetric wrapping pattern around the layer function.
    """

    def __init__(self, middlewares: list[Middleware]) -> None:
        self._middlewares = list(middlewares)
        self._log = structlog.get_logger(component="MiddlewareChain")

    @property
    def middlewares(self) -> list[Middleware]:
        """Return a copy of the middleware list."""
        return list(self._middlewares)

    async def run_before(self, state: PipelineState) -> PipelineState:
        """Run all middleware before() hooks in order.

        Args:
            state: The current pipeline state.

        Returns:
            The pipeline state after all before() hooks have run.

        Raises:
            Exception: Re-raised from any middleware whose failure is fatal.
        """
        for mw in self._middlewares:
            await self._log.adebug(
                "middleware_before_start",
                middleware=mw.name,
                layer=state.current_layer,
            )
            start = time.monotonic()
            state = await mw.before(state)
            elapsed = time.monotonic() - start
            await self._log.adebug(
                "middleware_before_complete",
                middleware=mw.name,
                elapsed_seconds=round(elapsed, 4),
            )
        return state

    async def run_after(self, state: PipelineState) -> PipelineState:
        """Run all middleware after() hooks in reverse order.

        Args:
            state: The current pipeline state.

        Returns:
            The pipeline state after all after() hooks have run.
        """
        for mw in reversed(self._middlewares):
            await self._log.adebug(
                "middleware_after_start",
                middleware=mw.name,
                layer=state.current_layer,
            )
            start = time.monotonic()
            state = await mw.after(state)
            elapsed = time.monotonic() - start
            await self._log.adebug(
                "middleware_after_complete",
                middleware=mw.name,
                elapsed_seconds=round(elapsed, 4),
            )
        return state

    async def execute(
        self,
        state: PipelineState,
        layer_fn: Callable[[PipelineState], Awaitable[PipelineState]],
    ) -> PipelineState:
        """Execute a layer function wrapped by the full middleware chain.

        Runs before() hooks in order, then the layer function, then after()
        hooks in reverse order. Exceptions in before() are fatal and re-raised.
        Exceptions in the layer function are fatal and re-raised (after hooks
        still run). Exceptions in after() are logged but do not halt execution.

        Args:
            state: The current pipeline state.
            layer_fn: The async layer function to execute.

        Returns:
            The pipeline state after the complete middleware + layer cycle.

        Raises:
            Exception: From before() hooks or the layer function.
        """
        # Run before hooks — failures here are fatal
        state = await self.run_before(state)

        # Execute the layer function
        layer_error: BaseException | None = None
        try:
            await self._log.ainfo(
                "layer_execution_start",
                layer=state.current_layer,
            )
            start = time.monotonic()
            state = await layer_fn(state)
            elapsed = time.monotonic() - start
            await self._log.ainfo(
                "layer_execution_complete",
                layer=state.current_layer,
                elapsed_seconds=round(elapsed, 4),
            )
        except Exception as exc:
            layer_error = exc
            await self._log.aerror(
                "layer_execution_failed",
                layer=state.current_layer,
                error=str(exc),
                error_type=type(exc).__name__,
            )

        # Run after hooks — failures here are logged but non-fatal
        for mw in reversed(self._middlewares):
            try:
                await self._log.adebug(
                    "middleware_after_start",
                    middleware=mw.name,
                    layer=state.current_layer,
                )
                start = time.monotonic()
                state = await mw.after(state)
                elapsed = time.monotonic() - start
                await self._log.adebug(
                    "middleware_after_complete",
                    middleware=mw.name,
                    elapsed_seconds=round(elapsed, 4),
                )
            except Exception as exc:
                await self._log.awarning(
                    "middleware_after_failed",
                    middleware=mw.name,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        # Re-raise the layer error after all after hooks have run
        if layer_error is not None:
            raise layer_error

        return state
