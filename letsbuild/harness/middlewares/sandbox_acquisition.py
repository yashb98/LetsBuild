"""SandboxAcquisition middleware — provisions and cleans up Docker sandboxes.

Third middleware in the 10-stage chain. Acquires a Docker sandbox container
from the SandboxManager before layer execution and releases it afterwards.
Handles environments where Docker is unavailable by logging a warning and
continuing without a sandbox.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from letsbuild.harness.middleware import Middleware
from letsbuild.harness.sandbox import SandboxManager

if TYPE_CHECKING:
    from letsbuild.pipeline.state import PipelineState

logger = structlog.get_logger()


class SandboxAcquisitionMiddleware(Middleware):
    """Provision a Docker sandbox before layer execution and clean it up after.

    before(): Creates a ``SandboxManager`` (if not provided) and provisions a
    sandbox container. Stores the container ID in ``state.sandbox_id``.  If
    Docker is unavailable, logs a warning and continues without a sandbox.

    after(): Cleans up the provisioned sandbox and resets ``state.sandbox_id``
    to ``None``.  Errors during cleanup are logged but never raised, ensuring
    the rest of the after-hook chain can still run.
    """

    def __init__(self, sandbox_manager: SandboxManager | None = None) -> None:
        self._sandbox_manager = sandbox_manager

    async def before(self, state: PipelineState) -> PipelineState:
        """Provision a Docker sandbox for this pipeline run.

        If no ``SandboxManager`` was provided at construction time, a new one
        is created with default configuration.  The sandbox container ID is
        written to ``state.sandbox_id``.

        If Docker is not available (e.g. in CI or local dev without Docker),
        the error is caught, a warning is logged, and the pipeline continues
        without a sandbox.

        Args:
            state: The current pipeline state.

        Returns:
            The pipeline state with ``sandbox_id`` populated (or ``None``
            if Docker was unavailable).
        """
        if self._sandbox_manager is None:
            self._sandbox_manager = SandboxManager()

        try:
            container_id = await self._sandbox_manager.provision()
            state.sandbox_id = container_id
            await logger.ainfo(
                "sandbox_acquisition_provisioned",
                thread_id=state.thread_id,
                sandbox_id=container_id,
            )
        except Exception as exc:
            await logger.awarning(
                "sandbox_acquisition_docker_unavailable",
                thread_id=state.thread_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            state.sandbox_id = None

        return state

    async def after(self, state: PipelineState) -> PipelineState:
        """Clean up the provisioned Docker sandbox.

        If a sandbox was provisioned, asks the ``SandboxManager`` to stop and
        remove the container.  Errors during cleanup are logged but never
        re-raised so that subsequent after-hooks can still execute.

        Args:
            state: The current pipeline state.

        Returns:
            The pipeline state with ``sandbox_id`` set to ``None``.
        """
        if self._sandbox_manager is not None and state.sandbox_id is not None:
            try:
                await self._sandbox_manager.cleanup()
                await logger.ainfo(
                    "sandbox_acquisition_cleaned_up",
                    thread_id=state.thread_id,
                    sandbox_id=state.sandbox_id,
                )
            except Exception as exc:
                await logger.awarning(
                    "sandbox_acquisition_cleanup_failed",
                    thread_id=state.thread_id,
                    sandbox_id=state.sandbox_id,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        state.sandbox_id = None
        return state
