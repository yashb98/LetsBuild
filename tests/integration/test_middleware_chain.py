"""Integration tests for the middleware chain (L0 harness).

Tests verify:
- Middleware chain runs in correct order (before: 1→N, after: N→1)
- BudgetGuard blocks when estimated cost exceeds remaining budget
- NotificationDispatch fires without blocking pipeline
- Middleware errors in after() do not crash the pipeline
- Middleware chain wraps layer execution correctly
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from letsbuild.harness.middleware import Middleware, MiddlewareChain
from letsbuild.harness.middlewares.budget_guard import BudgetGuardMiddleware
from letsbuild.harness.middlewares.notification import NotificationDispatchMiddleware
from letsbuild.harness.middlewares.request_validation import RequestValidationMiddleware
from letsbuild.harness.middlewares.thread_data import ThreadDataMiddleware
from letsbuild.models.shared import ErrorCategory
from letsbuild.pipeline.state import PipelineState
from tests.integration.conftest import _RAW_JD_TEXT, make_jd_analysis

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helper: order-tracking middleware
# ---------------------------------------------------------------------------


class OrderTracker:
    """Records the order in which middleware hooks execute."""

    def __init__(self) -> None:
        self.calls: list[str] = []


class _TrackingMiddleware(Middleware):
    """Middleware that records before/after execution order."""

    def __init__(self, label: str, tracker: OrderTracker) -> None:
        self._label = label
        self._tracker = tracker

    async def before(self, state: PipelineState) -> PipelineState:
        self._tracker.calls.append(f"before:{self._label}")
        return state

    async def after(self, state: PipelineState) -> PipelineState:
        self._tracker.calls.append(f"after:{self._label}")
        return state


class _FailingAfterMiddleware(Middleware):
    """Middleware that raises in after() to test non-fatal after errors."""

    async def before(self, state: PipelineState) -> PipelineState:
        return state

    async def after(self, state: PipelineState) -> PipelineState:
        raise RuntimeError("Simulated after() failure")


# ---------------------------------------------------------------------------
# Test 1: Middleware chain runs in correct order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_middleware_chain_correct_execution_order() -> None:
    """before() hooks run in insertion order; after() hooks run in reverse order."""
    tracker = OrderTracker()

    m1 = _TrackingMiddleware("m1", tracker)
    m2 = _TrackingMiddleware("m2", tracker)
    m3 = _TrackingMiddleware("m3", tracker)

    chain = MiddlewareChain(middlewares=[m1, m2, m3])
    state = PipelineState(jd_text=_RAW_JD_TEXT)
    state.current_layer = 1

    async def no_op_layer(s: PipelineState) -> PipelineState:
        return s

    await chain.execute(state, no_op_layer)

    # before() must run in insertion order: m1, m2, m3
    # after() must run in reverse: m3, m2, m1
    assert tracker.calls == [
        "before:m1",
        "before:m2",
        "before:m3",
        "after:m3",
        "after:m2",
        "after:m1",
    ]


# ---------------------------------------------------------------------------
# Test 2: Middleware chain with empty list — layer executes directly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_middleware_chain_empty_executes_layer_directly() -> None:
    """An empty middleware chain should execute the layer function without error."""
    chain = MiddlewareChain(middlewares=[])
    state = PipelineState(jd_text=_RAW_JD_TEXT)

    executed = []

    async def layer_fn(s: PipelineState) -> PipelineState:
        executed.append(True)
        return s

    result = await chain.execute(state, layer_fn)

    assert executed == [True]
    assert result is not None


# ---------------------------------------------------------------------------
# Test 3: BudgetGuard blocks when over budget
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_budget_guard_blocks_expensive_layer() -> None:
    """BudgetGuard must raise ValueError and add error when budget is insufficient.

    The BudgetGuard determines remaining budget from state.budget_remaining.
    Setting budget_remaining=0.0 with max_budget=0.10 ensures estimated_cost
    (£3.00 for intelligence) exceeds the remaining budget (£0.10 - £0.10 = £0.00).
    """
    guard = BudgetGuardMiddleware(max_budget_gbp=0.10)
    state = PipelineState(jd_text=_RAW_JD_TEXT)
    state.current_layer = 2  # intelligence layer
    # Simulate that budget is fully depleted
    state.budget_remaining = 0.0

    with pytest.raises(ValueError, match="BudgetGate blocked"):
        await guard.before(state)

    # A StructuredError should have been added
    assert len(state.errors) == 1
    assert state.errors[0].error_category == ErrorCategory.BUSINESS
    assert state.errors[0].is_retryable is False


@pytest.mark.asyncio
async def test_budget_guard_allows_affordable_layer() -> None:
    """BudgetGuard must not block a layer whose estimated cost fits within budget."""
    # Intake is estimated at £0.50 — well within £50 budget
    guard = BudgetGuardMiddleware(max_budget_gbp=50.0)
    state = PipelineState(jd_text=_RAW_JD_TEXT)
    state.current_layer = 1  # intake layer

    result = await guard.before(state)

    # Should not raise, no errors added
    assert len(result.errors) == 0


@pytest.mark.asyncio
async def test_budget_guard_reconciles_after_execution() -> None:
    """BudgetGuard.after() must sync budget_remaining from state.metrics.total_api_cost_gbp."""
    guard = BudgetGuardMiddleware(max_budget_gbp=50.0)
    state = PipelineState(jd_text=_RAW_JD_TEXT)
    state.current_layer = 1

    # Simulate that a layer spent some money
    state.metrics.total_api_cost_gbp = 5.0

    result = await guard.after(state)

    assert result.budget_remaining == pytest.approx(45.0, abs=0.01)


# ---------------------------------------------------------------------------
# Test 4: NotificationDispatch fires without blocking pipeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notification_middleware_does_not_block_pipeline() -> None:
    """NotificationMiddleware must not raise and must return state unchanged."""
    notification = NotificationDispatchMiddleware()
    state = PipelineState(jd_text=_RAW_JD_TEXT)
    state.current_layer = 3

    # before() should be a no-op or fire async (non-blocking)
    result_before = await notification.before(state)
    assert result_before is not None

    # after() should complete without error
    result_after = await notification.after(state)
    assert result_after is not None


# ---------------------------------------------------------------------------
# Test 5: Middleware after() failure does not crash pipeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_middleware_after_failure_does_not_crash_pipeline() -> None:
    """An exception in a middleware after() hook must be swallowed, not re-raised."""
    failing_mw = _FailingAfterMiddleware()
    chain = MiddlewareChain(middlewares=[failing_mw])
    state = PipelineState(jd_text=_RAW_JD_TEXT)
    state.current_layer = 1

    async def layer_fn(s: PipelineState) -> PipelineState:
        return s

    # Should not raise — after() failures are non-fatal per architecture
    result = await chain.execute(state, layer_fn)
    assert result is not None


# ---------------------------------------------------------------------------
# Test 6: Middleware before() failure is fatal and re-raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_middleware_before_failure_is_fatal() -> None:
    """An exception in a middleware before() hook must be re-raised (fatal)."""

    class _FailingBeforeMiddleware(Middleware):
        async def before(self, state: PipelineState) -> PipelineState:
            raise ValueError("Fatal before() failure")

        async def after(self, state: PipelineState) -> PipelineState:
            return state

    chain = MiddlewareChain(middlewares=[_FailingBeforeMiddleware()])
    state = PipelineState(jd_text=_RAW_JD_TEXT)

    async def layer_fn(s: PipelineState) -> PipelineState:
        return s

    with pytest.raises(ValueError, match=r"Fatal before\(\) failure"):
        await chain.execute(state, layer_fn)


# ---------------------------------------------------------------------------
# Test 7: RequestValidation middleware accepts valid state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_validation_accepts_valid_state() -> None:
    """RequestValidationMiddleware must pass through a state with jd_text."""
    middleware = RequestValidationMiddleware()
    state = PipelineState(jd_text=_RAW_JD_TEXT)
    state.current_layer = 1

    result = await middleware.before(state)
    assert result is not None


# ---------------------------------------------------------------------------
# Test 8: ThreadData middleware assigns workspace metadata
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thread_data_middleware_before_passes() -> None:
    """ThreadDataMiddleware.before() must complete without error."""
    middleware = ThreadDataMiddleware()
    state = PipelineState(jd_text=_RAW_JD_TEXT)
    state.current_layer = 1

    result = await middleware.before(state)
    assert result is not None


# ---------------------------------------------------------------------------
# Test 9: Pipeline controller correctly uses middleware chain via set_middleware_chain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_controller_uses_injected_middleware_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PipelineController.set_middleware_chain must use the injected chain for layer wrapping."""
    from letsbuild.pipeline.controller import PipelineController

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_OWNER", raising=False)

    tracker = OrderTracker()
    m1 = _TrackingMiddleware("middleware_1", tracker)

    controller = PipelineController()
    controller.intake_engine.parse_jd = AsyncMock(  # type: ignore[assignment]
        return_value=make_jd_analysis()
    )
    controller.intelligence_coordinator.research_company = AsyncMock(  # type: ignore[assignment]
        side_effect=RuntimeError("Skip L2 for speed")
    )

    chain = MiddlewareChain(middlewares=[m1])
    controller.set_middleware_chain(chain)

    await controller.run(jd_text=_RAW_JD_TEXT)

    # The tracking middleware must have fired for at least layer 1 (intake)
    before_calls = [c for c in tracker.calls if c.startswith("before:")]
    after_calls = [c for c in tracker.calls if c.startswith("after:")]
    assert len(before_calls) >= 1
    assert len(after_calls) >= 1
