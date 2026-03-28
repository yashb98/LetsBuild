"""Tests for JudgeRecorder — JUDGE phase of Memory layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from letsbuild.memory.judge import JudgeRecorder
from letsbuild.memory.storage import MemoryStorage
from letsbuild.models.forge_models import ForgeOutput, ReviewVerdict, SwarmTopology
from letsbuild.models.memory_models import VerdictOutcome
from letsbuild.models.shared import PipelineMetrics
from letsbuild.pipeline.state import PipelineState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_forge_output(
    *,
    quality_score: float = 85.0,
    test_results: dict[str, bool] | None = None,
    review_verdict: ReviewVerdict = ReviewVerdict.PASS,
    review_comments: list[str] | None = None,
    total_retries: int = 0,
) -> ForgeOutput:
    """Create a minimal ForgeOutput."""
    return ForgeOutput(
        code_modules=[],
        test_results=test_results if test_results is not None else {"test_main": True},
        review_verdict=review_verdict,
        review_comments=review_comments or [],
        quality_score=quality_score,
        total_tokens_used=10000,
        total_retries=total_retries,
        topology_used=SwarmTopology.HIERARCHICAL,
    )


def make_state(
    *,
    forge_output: ForgeOutput | None = None,
    retries_by_layer: dict[str, int] | None = None,
    layer_durations: dict[str, float] | None = None,
    api_cost_gbp: float = 2.0,
    quality_score: float = 0.0,
) -> PipelineState:
    """Create a minimal PipelineState for testing JUDGE."""
    metrics = PipelineMetrics(
        total_api_cost_gbp=api_cost_gbp,
        retries_by_layer=retries_by_layer or {},
        layer_durations=layer_durations or {"layer_5": 120.0},
        quality_score=quality_score,
    )
    state = PipelineState(metrics=metrics)
    state.forge_output = forge_output
    return state


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def storage(tmp_path: pytest.TempPathFactory) -> MemoryStorage:  # type: ignore[type-arg]
    """Initialised MemoryStorage backed by a temp file."""
    db_path = str(tmp_path / "judge_test.db")
    store = MemoryStorage(db_path=db_path)
    async with store:
        yield store


# ---------------------------------------------------------------------------
# record_verdict — outcome determination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_verdict_passing_run(storage: MemoryStorage) -> None:
    """A run with quality >= 70 and all tests passing should produce PASS verdict."""
    forge = make_forge_output(quality_score=85.0, test_results={"test_a": True, "test_b": True})
    state = make_state(forge_output=forge)

    recorder = JudgeRecorder(storage=storage)
    verdict = await recorder.record_verdict(state)

    assert verdict.outcome == VerdictOutcome.PASS
    assert verdict.sandbox_passed is True
    assert abs(verdict.quality_score - 85.0) < 0.001


@pytest.mark.asyncio
async def test_record_verdict_failing_run(storage: MemoryStorage) -> None:
    """A run with quality < 40 and failed tests should produce FAIL verdict."""
    forge = make_forge_output(
        quality_score=30.0,
        test_results={"test_a": False, "test_b": False},
        review_verdict=ReviewVerdict.FAIL,
        review_comments=["Critical bugs found."],
    )
    state = make_state(forge_output=forge)

    recorder = JudgeRecorder(storage=storage)
    verdict = await recorder.record_verdict(state)

    assert verdict.outcome == VerdictOutcome.FAIL
    assert verdict.sandbox_passed is False
    assert "review_verdict: fail" in verdict.failure_reasons


@pytest.mark.asyncio
async def test_record_verdict_partial_run(storage: MemoryStorage) -> None:
    """A run with quality between 40 and 70 should produce PARTIAL verdict."""
    forge = make_forge_output(
        quality_score=55.0,
        test_results={"test_a": False},
        review_verdict=ReviewVerdict.PASS_WITH_SUGGESTIONS,
    )
    state = make_state(forge_output=forge)

    recorder = JudgeRecorder(storage=storage)
    verdict = await recorder.record_verdict(state)

    assert verdict.outcome == VerdictOutcome.PARTIAL


@pytest.mark.asyncio
async def test_record_verdict_missing_forge_output(storage: MemoryStorage) -> None:
    """When forge_output is None, outcome should be FAIL with appropriate failure reason."""
    state = make_state(forge_output=None)

    recorder = JudgeRecorder(storage=storage)
    verdict = await recorder.record_verdict(state)

    assert verdict.outcome == VerdictOutcome.FAIL
    assert verdict.sandbox_passed is False
    assert any("forge_output missing" in r for r in verdict.failure_reasons)


# ---------------------------------------------------------------------------
# record_verdict — persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verdict_is_saved_to_storage(storage: MemoryStorage) -> None:
    """record_verdict should persist the verdict so it can be retrieved by ID."""
    forge = make_forge_output(quality_score=75.0)
    state = make_state(forge_output=forge)

    recorder = JudgeRecorder(storage=storage)
    verdict = await recorder.record_verdict(state)

    retrieved = await storage.get_verdict(verdict.verdict_id)
    assert retrieved is not None
    assert retrieved.verdict_id == verdict.verdict_id
    assert retrieved.outcome == VerdictOutcome.PASS


@pytest.mark.asyncio
async def test_verdict_uses_state_thread_id_as_run_id(storage: MemoryStorage) -> None:
    """The verdict's run_id should match state.thread_id."""
    state = make_state()
    recorder = JudgeRecorder(storage=storage)
    verdict = await recorder.record_verdict(state)

    assert verdict.run_id == state.thread_id


@pytest.mark.asyncio
async def test_verdict_captures_api_cost(storage: MemoryStorage) -> None:
    """The verdict should capture the API cost from state metrics."""
    state = make_state(api_cost_gbp=4.50)
    recorder = JudgeRecorder(storage=storage)
    verdict = await recorder.record_verdict(state)

    assert abs(verdict.api_cost_gbp - 4.50) < 0.001


@pytest.mark.asyncio
async def test_verdict_captures_retry_count(storage: MemoryStorage) -> None:
    """The verdict should sum retries across all layers."""
    state = make_state(retries_by_layer={"layer_1": 1, "layer_5": 3})
    recorder = JudgeRecorder(storage=storage)
    verdict = await recorder.record_verdict(state)

    assert verdict.retry_count_total == 4


@pytest.mark.asyncio
async def test_verdict_captures_generation_time_from_layer_durations(
    storage: MemoryStorage,
) -> None:
    """The verdict should use layer_5 duration as generation_time_seconds."""
    state = make_state(layer_durations={"layer_5": 250.0, "layer_1": 10.0})
    recorder = JudgeRecorder(storage=storage)
    verdict = await recorder.record_verdict(state)

    assert abs(verdict.generation_time_seconds - 250.0) < 0.001


# ---------------------------------------------------------------------------
# auto-distill trigger
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_distill_triggered_after_10_verdicts(storage: MemoryStorage) -> None:
    """JudgeRecorder should trigger distill() exactly when count reaches a multiple of 10."""
    mock_distiller = MagicMock()
    mock_distiller.distill = AsyncMock(return_value=[])

    recorder = JudgeRecorder(storage=storage, distiller=mock_distiller)

    # Record 9 verdicts — distill should NOT be triggered yet
    for _ in range(9):
        await recorder.record_verdict(make_state())

    mock_distiller.distill.assert_not_called()

    # The 10th verdict should trigger distill
    await recorder.record_verdict(make_state())

    mock_distiller.distill.assert_called_once()


@pytest.mark.asyncio
async def test_auto_distill_not_triggered_without_distiller(storage: MemoryStorage) -> None:
    """When no distiller is provided, recording verdicts should not raise errors."""
    recorder = JudgeRecorder(storage=storage, distiller=None)

    for _ in range(10):
        await recorder.record_verdict(make_state())

    # No assertion needed beyond "no exception raised"


@pytest.mark.asyncio
async def test_distill_failure_does_not_crash_recording(storage: MemoryStorage) -> None:
    """If distill() raises, record_verdict should still complete successfully."""
    mock_distiller = MagicMock()
    mock_distiller.distill = AsyncMock(side_effect=RuntimeError("Distill exploded"))

    recorder = JudgeRecorder(storage=storage, distiller=mock_distiller)

    # Record 10 verdicts to trigger distill
    for _ in range(9):
        await recorder.record_verdict(make_state())

    # The 10th should trigger (and swallow) the distill error
    verdict = await recorder.record_verdict(make_state())

    # Verdict was still saved
    assert await storage.get_verdict(verdict.verdict_id) is not None
