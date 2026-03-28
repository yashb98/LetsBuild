"""Integration tests for Memory layer (L8) interactions with the pipeline.

Tests verify:
- JUDGE records verdict after forge completes
- DISTILL triggers after 10 verdicts
- MemoryRetrieval injects cached CompanyProfile
- MemoryPersistence saves metrics after pipeline completion
- Cache TTL is respected (stale records are not injected)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from letsbuild.harness.middlewares.memory_persistence import MemoryPersistenceMiddleware
from letsbuild.harness.middlewares.memory_retrieval import MemoryRetrievalMiddleware
from letsbuild.memory.judge import JudgeRecorder

if TYPE_CHECKING:
    from letsbuild.memory.storage import MemoryStorage
from letsbuild.models.forge_models import ForgeOutput, ReviewVerdict, SwarmTopology
from letsbuild.models.memory_models import MemoryRecord, VerdictOutcome
from letsbuild.models.shared import PipelineMetrics
from letsbuild.pipeline.state import PipelineState
from tests.integration.conftest import (
    _RAW_JD_TEXT,
    make_company_profile,
    make_full_pipeline_state,
    make_jd_analysis,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_forge_output_passing() -> ForgeOutput:
    """Return a passing ForgeOutput for JUDGE tests."""
    return ForgeOutput(
        code_modules=[],
        test_results={"test_a": True, "test_b": True},
        review_verdict=ReviewVerdict.PASS,
        review_comments=[],
        quality_score=85.0,
        total_tokens_used=10000,
        total_retries=0,
        topology_used=SwarmTopology.HIERARCHICAL,
    )


def make_forge_output_failing() -> ForgeOutput:
    """Return a failing ForgeOutput for JUDGE tests."""
    return ForgeOutput(
        code_modules=[],
        test_results={"test_a": False},
        review_verdict=ReviewVerdict.FAIL,
        review_comments=["Critical issues found"],
        quality_score=25.0,
        total_tokens_used=5000,
        total_retries=3,
        topology_used=SwarmTopology.HIERARCHICAL,
    )


def make_pipeline_state_for_judge(
    *,
    forge: ForgeOutput | None = None,
    api_cost_gbp: float = 5.0,
) -> PipelineState:
    """Build a minimal PipelineState for JUDGE testing."""
    metrics = PipelineMetrics(
        total_api_cost_gbp=api_cost_gbp,
        retries_by_layer={},
        layer_durations={"forge": 120.0},
        quality_score=forge.quality_score if forge else 0.0,
    )
    state = PipelineState(metrics=metrics, jd_text=_RAW_JD_TEXT)
    state.forge_output = forge
    return state


# ---------------------------------------------------------------------------
# Test 1: JUDGE records verdict after forge completes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_judge_records_verdict_after_forge_pass(
    memory_storage: MemoryStorage,
) -> None:
    """JudgeRecorder must persist a PASS verdict for a high-quality forge run."""
    forge = make_forge_output_passing()
    state = make_pipeline_state_for_judge(forge=forge)

    recorder = JudgeRecorder(storage=memory_storage)
    verdict = await recorder.record_verdict(state)

    assert verdict.outcome == VerdictOutcome.PASS
    assert verdict.sandbox_passed is True
    assert verdict.quality_score >= 70.0

    # Verify it was persisted
    retrieved = await memory_storage.get_verdict(verdict.verdict_id)
    assert retrieved is not None
    assert retrieved.outcome == VerdictOutcome.PASS


@pytest.mark.asyncio
async def test_judge_records_verdict_after_forge_fail(
    memory_storage: MemoryStorage,
) -> None:
    """JudgeRecorder must persist a FAIL verdict for a low-quality forge run."""
    forge = make_forge_output_failing()
    state = make_pipeline_state_for_judge(forge=forge)

    recorder = JudgeRecorder(storage=memory_storage)
    verdict = await recorder.record_verdict(state)

    assert verdict.outcome == VerdictOutcome.FAIL
    assert verdict.sandbox_passed is False

    retrieved = await memory_storage.get_verdict(verdict.verdict_id)
    assert retrieved is not None
    assert retrieved.outcome == VerdictOutcome.FAIL


# ---------------------------------------------------------------------------
# Test 2: DISTILL triggers after 10 verdicts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_distill_triggers_on_10th_verdict(
    memory_storage: MemoryStorage,
) -> None:
    """PatternDistiller.distill() must be called exactly when verdict count hits 10."""
    mock_distiller = MagicMock()
    mock_distiller.distill = AsyncMock(return_value=[])

    recorder = JudgeRecorder(storage=memory_storage, distiller=mock_distiller)
    state = make_pipeline_state_for_judge(forge=make_forge_output_passing())

    # Record 9 verdicts — distill must NOT fire
    for _ in range(9):
        await recorder.record_verdict(state)

    mock_distiller.distill.assert_not_called()

    # 10th verdict triggers distill
    await recorder.record_verdict(state)
    mock_distiller.distill.assert_called_once()


@pytest.mark.asyncio
async def test_distill_does_not_trigger_before_10_verdicts(
    memory_storage: MemoryStorage,
) -> None:
    """DISTILL must not fire before the 10-verdict threshold."""
    mock_distiller = MagicMock()
    mock_distiller.distill = AsyncMock(return_value=[])

    recorder = JudgeRecorder(storage=memory_storage, distiller=mock_distiller)
    state = make_pipeline_state_for_judge(forge=make_forge_output_passing())

    for _ in range(7):
        await recorder.record_verdict(state)

    mock_distiller.distill.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: MemoryRetrieval injects cached CompanyProfile
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_retrieval_injects_fresh_company_profile(
    memory_storage: MemoryStorage,
) -> None:
    """MemoryRetrievalMiddleware must inject a fresh cached CompanyProfile into state."""
    company = make_company_profile()

    # Save a fresh (< 30 days old) company profile record
    record = MemoryRecord(
        record_type="company_profile",
        data=company.model_dump(mode="json"),
        created_at=datetime.now(UTC) - timedelta(days=5),
    )
    await memory_storage.save_record(record)

    middleware = MemoryRetrievalMiddleware(storage=memory_storage)
    state = PipelineState(jd_text=_RAW_JD_TEXT)
    # MemoryRetrievalMiddleware only queries cache when company_name is set
    jd = make_jd_analysis()
    jd.company_name = company.company_name  # type: ignore[assignment]
    state.jd_analysis = jd

    state = await middleware.before(state)

    assert state.company_profile is not None
    assert state.company_profile.company_name == company.company_name


@pytest.mark.asyncio
async def test_memory_retrieval_skips_stale_company_profile(
    memory_storage: MemoryStorage,
) -> None:
    """MemoryRetrievalMiddleware must NOT inject a stale (> 30 days old) company profile."""
    company = make_company_profile()

    # Save a stale (40 days old) company profile record
    record = MemoryRecord(
        record_type="company_profile",
        data=company.model_dump(mode="json"),
        created_at=datetime.now(UTC) - timedelta(days=40),
    )
    await memory_storage.save_record(record)

    middleware = MemoryRetrievalMiddleware(storage=memory_storage)
    state = PipelineState(jd_text=_RAW_JD_TEXT)
    jd = make_jd_analysis()
    jd.company_name = company.company_name  # type: ignore[assignment]
    state.jd_analysis = jd

    state = await middleware.before(state)

    # Stale profile must not be injected
    assert state.company_profile is None


@pytest.mark.asyncio
async def test_memory_retrieval_does_not_overwrite_existing_profile(
    memory_storage: MemoryStorage,
) -> None:
    """MemoryRetrievalMiddleware must not overwrite an already-populated company_profile."""
    company = make_company_profile()

    record = MemoryRecord(
        record_type="company_profile",
        data=company.model_dump(mode="json"),
        created_at=datetime.now(UTC) - timedelta(days=2),
    )
    await memory_storage.save_record(record)

    middleware = MemoryRetrievalMiddleware(storage=memory_storage)
    state = PipelineState(jd_text=_RAW_JD_TEXT)
    jd = make_jd_analysis()
    jd.company_name = company.company_name  # type: ignore[assignment]
    state.jd_analysis = jd

    # Pre-populate with a different profile
    from letsbuild.models.intelligence_models import CompanyProfile

    existing_profile = CompanyProfile(
        company_name="Pre-existing Corp",
        industry="edtech",
        tech_stack_signals=["java"],
        confidence_score=50.0,
        data_sources=[],
        sub_agent_results=[],
    )
    state.company_profile = existing_profile

    state = await middleware.before(state)

    # Should NOT be overwritten
    assert state.company_profile.company_name == "Pre-existing Corp"


# ---------------------------------------------------------------------------
# Test 4: MemoryPersistence saves metrics after pipeline completion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_persistence_saves_pipeline_metrics(
    memory_storage: MemoryStorage,
) -> None:
    """MemoryPersistenceMiddleware must save PipelineMetrics to storage after a layer."""
    middleware = MemoryPersistenceMiddleware(storage=memory_storage)
    state = make_full_pipeline_state()

    state = await middleware.after(state)

    # Verify metrics were saved
    metrics = await memory_storage.get_metrics(state.thread_id)
    assert metrics is not None
    assert metrics.total_api_cost_gbp == state.metrics.total_api_cost_gbp


@pytest.mark.asyncio
async def test_memory_persistence_saves_company_profile(
    memory_storage: MemoryStorage,
) -> None:
    """MemoryPersistenceMiddleware must persist CompanyProfile for future cache hits."""
    middleware = MemoryPersistenceMiddleware(storage=memory_storage)
    state = make_full_pipeline_state()

    state = await middleware.after(state)

    # Find the saved company profile record
    records = await memory_storage.find_records("company_profile", limit=10)
    assert len(records) >= 1

    saved_names = [r.data.get("company_name") for r in records]
    assert state.company_profile is not None
    assert state.company_profile.company_name in saved_names


# ---------------------------------------------------------------------------
# Test 5: Cache TTL is respected (delete_expired removes stale records)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_cache_ttl_expired_records_deleted(
    memory_storage: MemoryStorage,
) -> None:
    """delete_expired must remove records with expires_at in the past."""
    past = datetime.now(UTC) - timedelta(hours=1)
    future = datetime.now(UTC) + timedelta(days=30)

    expired_record = MemoryRecord(
        record_type="company_profile",
        data={"company_name": "OldCorp"},
        created_at=datetime.now(UTC) - timedelta(days=100),
        expires_at=past,
    )
    fresh_record = MemoryRecord(
        record_type="company_profile",
        data={"company_name": "FreshCorp"},
        created_at=datetime.now(UTC),
        expires_at=future,
    )

    await memory_storage.save_record(expired_record)
    await memory_storage.save_record(fresh_record)

    deleted_count = await memory_storage.delete_expired()

    assert deleted_count == 1

    # OldCorp should be gone
    remaining = await memory_storage.find_records("company_profile", limit=10)
    remaining_names = [r.data.get("company_name") for r in remaining]
    assert "OldCorp" not in remaining_names
    assert "FreshCorp" in remaining_names


# ---------------------------------------------------------------------------
# Test 6: Multiple verdicts persisted and retrievable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_multiple_verdicts_persisted(
    memory_storage: MemoryStorage,
) -> None:
    """Multiple JUDGE verdicts from different runs should all be persisted and retrievable."""
    recorder = JudgeRecorder(storage=memory_storage)

    verdicts = []
    for i in range(5):
        state = make_pipeline_state_for_judge(
            forge=make_forge_output_passing(),
            api_cost_gbp=float(i + 1),
        )
        verdict = await recorder.record_verdict(state)
        verdicts.append(verdict)

    all_stored = await memory_storage.list_verdicts(limit=50)
    assert len(all_stored) == 5

    stored_ids = {v.verdict_id for v in all_stored}
    for v in verdicts:
        assert v.verdict_id in stored_ids


# ---------------------------------------------------------------------------
# Test 7: JUDGE extracts correct generation time from forge layer duration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_judge_generation_time_from_layer_durations(
    memory_storage: MemoryStorage,
) -> None:
    """JUDGE must use the forge layer duration as generation_time_seconds."""
    # JUDGE uses "layer_5" key to look up forge duration
    metrics = PipelineMetrics(
        total_api_cost_gbp=3.0,
        retries_by_layer={},
        layer_durations={"layer_5": 180.0, "layer_1": 5.0},
        quality_score=80.0,
    )
    state = PipelineState(metrics=metrics, jd_text=_RAW_JD_TEXT)
    state.forge_output = make_forge_output_passing()

    recorder = JudgeRecorder(storage=memory_storage)
    verdict = await recorder.record_verdict(state)

    assert abs(verdict.generation_time_seconds - 180.0) < 0.001
