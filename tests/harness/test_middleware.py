"""Tests for letsbuild.harness.middleware and letsbuild.pipeline.state."""

from __future__ import annotations

import uuid

import pytest

from letsbuild.harness.middleware import Middleware, MiddlewareChain
from letsbuild.models.shared import ErrorCategory, StructuredError
from letsbuild.pipeline.state import PipelineState

# ---------------------------------------------------------------------------
# DummyMiddleware for testing
# ---------------------------------------------------------------------------


class DummyMiddleware(Middleware):
    """Concrete middleware that records call order for testing."""

    def __init__(self, tag: str, call_log: list[str]) -> None:
        self._tag = tag
        self._call_log = call_log

    async def before(self, state: PipelineState) -> PipelineState:
        self._call_log.append(f"before:{self._tag}")
        return state

    async def after(self, state: PipelineState) -> PipelineState:
        self._call_log.append(f"after:{self._tag}")
        return state


class FailingBeforeMiddleware(Middleware):
    """Middleware whose before() raises an exception."""

    async def before(self, state: PipelineState) -> PipelineState:
        raise RuntimeError("before failed")

    async def after(self, state: PipelineState) -> PipelineState:
        return state


class FailingAfterMiddleware(Middleware):
    """Middleware whose after() raises an exception."""

    def __init__(self, call_log: list[str]) -> None:
        self._call_log = call_log

    async def before(self, state: PipelineState) -> PipelineState:
        self._call_log.append("before:failing_after")
        return state

    async def after(self, state: PipelineState) -> PipelineState:
        self._call_log.append("after:failing_after")
        raise RuntimeError("after failed")


# ---------------------------------------------------------------------------
# Middleware ABC
# ---------------------------------------------------------------------------


class TestMiddlewareABC:
    """Tests for the abstract Middleware base class."""

    def test_cannot_instantiate_directly(self) -> None:
        """Middleware cannot be instantiated because it is abstract."""
        with pytest.raises(TypeError, match=r"abstract method"):
            Middleware()  # type: ignore[abstract]

    def test_subclass_must_implement_before_and_after(self) -> None:
        """A subclass missing before() or after() cannot be instantiated."""

        class PartialMiddleware(Middleware):
            async def before(self, state: PipelineState) -> PipelineState:
                return state

        with pytest.raises(TypeError, match=r"abstract method"):
            PartialMiddleware()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# MiddlewareChain
# ---------------------------------------------------------------------------


class TestMiddlewareChain:
    """Tests for the MiddlewareChain orchestrator."""

    @pytest.mark.asyncio
    async def test_empty_chain_passes_state_through(self) -> None:
        """An empty middleware chain returns the state unchanged."""
        chain = MiddlewareChain([])
        state = PipelineState()

        result = await chain.run_before(state)

        assert result is state

    @pytest.mark.asyncio
    async def test_before_runs_in_order(self) -> None:
        """before() hooks execute in insertion order."""
        call_log: list[str] = []
        chain = MiddlewareChain(
            [
                DummyMiddleware("A", call_log),
                DummyMiddleware("B", call_log),
                DummyMiddleware("C", call_log),
            ]
        )

        await chain.run_before(PipelineState())

        assert call_log == ["before:A", "before:B", "before:C"]

    @pytest.mark.asyncio
    async def test_after_runs_in_reverse_order(self) -> None:
        """after() hooks execute in reverse order."""
        call_log: list[str] = []
        chain = MiddlewareChain(
            [
                DummyMiddleware("A", call_log),
                DummyMiddleware("B", call_log),
                DummyMiddleware("C", call_log),
            ]
        )

        await chain.run_after(PipelineState())

        assert call_log == ["after:C", "after:B", "after:A"]

    @pytest.mark.asyncio
    async def test_execute_runs_before_layer_after(self) -> None:
        """execute() runs before -> layer_fn -> after in correct order."""
        call_log: list[str] = []
        chain = MiddlewareChain(
            [
                DummyMiddleware("M1", call_log),
            ]
        )

        async def layer_fn(state: PipelineState) -> PipelineState:
            call_log.append("layer")
            return state

        await chain.execute(PipelineState(), layer_fn)

        assert call_log == ["before:M1", "layer", "after:M1"]

    @pytest.mark.asyncio
    async def test_exception_in_before_propagates(self) -> None:
        """An exception in before() is re-raised and halts execution."""
        chain = MiddlewareChain([FailingBeforeMiddleware()])

        async def layer_fn(state: PipelineState) -> PipelineState:
            return state

        with pytest.raises(RuntimeError, match=r"before failed"):
            await chain.execute(PipelineState(), layer_fn)

    @pytest.mark.asyncio
    async def test_exception_in_after_does_not_crash(self) -> None:
        """An exception in after() is logged but does not crash the pipeline."""
        call_log: list[str] = []
        chain = MiddlewareChain([FailingAfterMiddleware(call_log)])

        async def layer_fn(state: PipelineState) -> PipelineState:
            call_log.append("layer")
            return state

        # Should not raise even though after() throws
        result = await chain.execute(PipelineState(), layer_fn)

        assert isinstance(result, PipelineState)
        assert "before:failing_after" in call_log
        assert "layer" in call_log
        assert "after:failing_after" in call_log

    @pytest.mark.asyncio
    async def test_execute_after_hooks_run_even_when_layer_fails(self) -> None:
        """after() hooks still run when the layer function raises."""
        call_log: list[str] = []
        chain = MiddlewareChain([DummyMiddleware("M1", call_log)])

        async def failing_layer(state: PipelineState) -> PipelineState:
            call_log.append("layer_fail")
            raise ValueError("layer exploded")

        with pytest.raises(ValueError, match=r"layer exploded"):
            await chain.execute(PipelineState(), failing_layer)

        assert "before:M1" in call_log
        assert "layer_fail" in call_log
        assert "after:M1" in call_log


# ---------------------------------------------------------------------------
# PipelineState
# ---------------------------------------------------------------------------


class TestPipelineState:
    """Tests for the PipelineState model."""

    def test_default_thread_id_is_uuid(self) -> None:
        """Default thread_id is a valid UUID4 string."""
        state = PipelineState()
        parsed = uuid.UUID(state.thread_id)
        assert parsed.version == 4

    def test_default_current_layer_is_zero(self) -> None:
        """Default current_layer is 0."""
        state = PipelineState()
        assert state.current_layer == 0

    def test_default_budget_remaining(self) -> None:
        """Default budget_remaining is 50.0."""
        state = PipelineState()
        assert state.budget_remaining == 50.0

    def test_add_error_appends_to_list(self) -> None:
        """add_error() appends a StructuredError to the errors list."""
        state = PipelineState()
        error = StructuredError(
            error_category=ErrorCategory.TRANSIENT,
            is_retryable=True,
            message="test error",
        )

        state.add_error(error)

        assert len(state.errors) == 1
        assert state.errors[0].message == "test error"

    def test_is_failed_true_with_three_or_more_errors(self) -> None:
        """is_failed() returns True when 3 or more errors have accumulated."""
        state = PipelineState()
        for i in range(3):
            state.add_error(
                StructuredError(
                    error_category=ErrorCategory.VALIDATION,
                    is_retryable=False,
                    message=f"error {i}",
                )
            )

        assert state.is_failed() is True

    def test_is_failed_false_with_fewer_than_three_errors(self) -> None:
        """is_failed() returns False when fewer than 3 errors."""
        state = PipelineState()
        state.add_error(
            StructuredError(
                error_category=ErrorCategory.TRANSIENT,
                is_retryable=True,
                message="one error",
            )
        )

        assert state.is_failed() is False

    def test_is_failed_false_with_zero_errors(self) -> None:
        """is_failed() returns False with no errors."""
        state = PipelineState()
        assert state.is_failed() is False

    def test_advance_layer_increments(self) -> None:
        """advance_layer() increments current_layer by 1."""
        state = PipelineState()
        assert state.current_layer == 0

        state.advance_layer()
        assert state.current_layer == 1

        state.advance_layer()
        assert state.current_layer == 2

    def test_layer_result_fields_default_to_none(self) -> None:
        """All layer output fields default to None."""
        state = PipelineState()

        assert state.jd_analysis is None
        assert state.company_profile is None
        assert state.gap_analysis is None
        assert state.project_spec is None
        assert state.forge_output is None
        assert state.publish_result is None
        assert state.content_outputs == []

    def test_json_schema_generation(self) -> None:
        """PipelineState can produce a valid JSON schema."""
        schema = PipelineState.model_json_schema()

        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "thread_id" in schema["properties"]
        assert "current_layer" in schema["properties"]
        assert "errors" in schema["properties"]
        assert "budget_remaining" in schema["properties"]
