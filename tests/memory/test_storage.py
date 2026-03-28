"""Tests for MemoryStorage — SQLite CRUD operations for all Layer 8 memory types."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from letsbuild.memory.storage import MemoryStorage
from letsbuild.models.memory_models import (
    DistilledPattern,
    JudgeVerdict,
    MemoryRecord,
    VerdictOutcome,
)
from letsbuild.models.shared import PipelineMetrics

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def storage(tmp_path: pytest.TempPathFactory) -> MemoryStorage:  # type: ignore[type-arg]
    """Provide an initialised MemoryStorage backed by a temporary SQLite file."""
    db_path = str(tmp_path / "test_memory.db")
    store = MemoryStorage(db_path=db_path)
    async with store:
        yield store


def make_verdict(
    *,
    outcome: VerdictOutcome = VerdictOutcome.PASS,
    quality_score: float = 85.0,
    sandbox_passed: bool = True,
    judged_at: datetime | None = None,
) -> JudgeVerdict:
    """Create a JudgeVerdict with sensible defaults."""
    return JudgeVerdict(
        run_id="run-test-001",
        outcome=outcome,
        sandbox_passed=sandbox_passed,
        quality_score=quality_score,
        retry_count_total=0,
        api_cost_gbp=1.50,
        generation_time_seconds=120.0,
        failure_reasons=[],
        judged_at=judged_at or datetime.now(UTC),
    )


def make_pattern(
    *,
    confidence: float = 75.0,
    tech_stack_tags: list[str] | None = None,
    success_rate: float = 80.0,
    sample_count: int = 5,
) -> DistilledPattern:
    """Create a DistilledPattern with sensible defaults."""
    return DistilledPattern(
        pattern_text="fastapi projects succeed at 80% over 5 runs.",
        source_verdicts=["v1", "v2"],
        confidence=confidence,
        tech_stack_tags=tech_stack_tags or ["fastapi"],
        success_rate=success_rate,
        sample_count=sample_count,
        distilled_at=datetime.now(UTC),
    )


def make_record(
    *,
    record_type: str = "company_profile",
    expires_at: datetime | None = None,
) -> MemoryRecord:
    """Create a MemoryRecord with sensible defaults."""
    return MemoryRecord(
        record_type=record_type,
        data={"company_name": "Acme Corp", "confidence_score": 90.0},
        created_at=datetime.now(UTC),
        expires_at=expires_at,
    )


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_init_db_creates_tables(tmp_path: pytest.TempPathFactory) -> None:  # type: ignore[type-arg]
    """init_db should create all four required tables without error."""
    db_path = str(tmp_path / "init_test.db")
    store = MemoryStorage(db_path=db_path)
    await store.init_db()

    # Verify tables exist by querying sqlite_master
    assert store._conn is not None
    async with store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ) as cursor:
        rows = await cursor.fetchall()
    table_names = {row[0] for row in rows}

    await store.close()

    assert "judge_verdicts" in table_names
    assert "distilled_patterns" in table_names
    assert "memory_records" in table_names
    assert "pipeline_metrics" in table_names


# ---------------------------------------------------------------------------
# judge_verdicts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_and_get_verdict_round_trip(storage: MemoryStorage) -> None:
    """save_verdict then get_verdict should return the same verdict."""
    verdict = make_verdict()
    await storage.save_verdict(verdict)

    retrieved = await storage.get_verdict(verdict.verdict_id)

    assert retrieved is not None
    assert retrieved.verdict_id == verdict.verdict_id
    assert retrieved.run_id == verdict.run_id
    assert retrieved.outcome == verdict.outcome
    assert retrieved.sandbox_passed == verdict.sandbox_passed
    assert abs(retrieved.quality_score - verdict.quality_score) < 0.001
    assert retrieved.retry_count_total == verdict.retry_count_total
    assert abs(retrieved.api_cost_gbp - verdict.api_cost_gbp) < 0.001
    assert retrieved.failure_reasons == verdict.failure_reasons


@pytest.mark.asyncio
async def test_get_verdict_returns_none_for_missing_id(storage: MemoryStorage) -> None:
    """get_verdict should return None for a non-existent verdict_id."""
    result = await storage.get_verdict("no-such-id")
    assert result is None


@pytest.mark.asyncio
async def test_list_verdicts_with_limit(storage: MemoryStorage) -> None:
    """list_verdicts should respect the limit parameter."""
    for _ in range(5):
        await storage.save_verdict(make_verdict())

    results = await storage.list_verdicts(limit=3)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_list_verdicts_ordered_newest_first(storage: MemoryStorage) -> None:
    """list_verdicts should return verdicts ordered by judged_at DESC."""
    old = make_verdict(judged_at=datetime(2024, 1, 1, tzinfo=UTC))
    new = make_verdict(judged_at=datetime(2025, 1, 1, tzinfo=UTC))
    await storage.save_verdict(old)
    await storage.save_verdict(new)

    results = await storage.list_verdicts(limit=10)
    assert len(results) == 2
    assert results[0].judged_at >= results[1].judged_at


@pytest.mark.asyncio
async def test_get_verdicts_since_filters_by_date(storage: MemoryStorage) -> None:
    """get_verdicts_since should only return verdicts at or after the cutoff."""
    past = make_verdict(judged_at=datetime(2024, 6, 1, tzinfo=UTC))
    recent = make_verdict(judged_at=datetime(2025, 6, 1, tzinfo=UTC))
    await storage.save_verdict(past)
    await storage.save_verdict(recent)

    cutoff = datetime(2025, 1, 1, tzinfo=UTC)
    results = await storage.get_verdicts_since(cutoff)

    verdict_ids = {v.verdict_id for v in results}
    assert recent.verdict_id in verdict_ids
    assert past.verdict_id not in verdict_ids


@pytest.mark.asyncio
async def test_count_verdicts_returns_correct_count(storage: MemoryStorage) -> None:
    """count_verdicts should return the total number of stored verdicts."""
    assert await storage.count_verdicts() == 0

    for _ in range(3):
        await storage.save_verdict(make_verdict())

    assert await storage.count_verdicts() == 3


@pytest.mark.asyncio
async def test_save_verdict_replace_on_duplicate_id(storage: MemoryStorage) -> None:
    """Saving a verdict with the same ID should replace it (INSERT OR REPLACE)."""
    verdict = make_verdict(quality_score=75.0)
    await storage.save_verdict(verdict)

    updated = JudgeVerdict(
        verdict_id=verdict.verdict_id,
        run_id=verdict.run_id,
        outcome=VerdictOutcome.FAIL,
        sandbox_passed=False,
        quality_score=30.0,
        retry_count_total=2,
        api_cost_gbp=2.0,
        generation_time_seconds=200.0,
        failure_reasons=["test failed"],
        judged_at=datetime.now(UTC),
    )
    await storage.save_verdict(updated)

    retrieved = await storage.get_verdict(verdict.verdict_id)
    assert retrieved is not None
    assert retrieved.outcome == VerdictOutcome.FAIL
    assert abs(retrieved.quality_score - 30.0) < 0.001


# ---------------------------------------------------------------------------
# distilled_patterns
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_and_get_pattern_round_trip(storage: MemoryStorage) -> None:
    """save_pattern then get_pattern should return the same pattern."""
    pattern = make_pattern()
    await storage.save_pattern(pattern)

    retrieved = await storage.get_pattern(pattern.pattern_id)

    assert retrieved is not None
    assert retrieved.pattern_id == pattern.pattern_id
    assert retrieved.pattern_text == pattern.pattern_text
    assert retrieved.source_verdicts == pattern.source_verdicts
    assert abs(retrieved.confidence - pattern.confidence) < 0.001
    assert retrieved.tech_stack_tags == pattern.tech_stack_tags
    assert retrieved.sample_count == pattern.sample_count


@pytest.mark.asyncio
async def test_get_pattern_returns_none_for_missing_id(storage: MemoryStorage) -> None:
    """get_pattern should return None for a non-existent pattern_id."""
    result = await storage.get_pattern("ghost-id")
    assert result is None


@pytest.mark.asyncio
async def test_list_patterns_with_min_confidence_filter(storage: MemoryStorage) -> None:
    """list_patterns should respect min_confidence filter."""
    low = make_pattern(confidence=30.0)
    high = make_pattern(confidence=85.0)
    await storage.save_pattern(low)
    await storage.save_pattern(high)

    results = await storage.list_patterns(min_confidence=60.0)
    ids = {p.pattern_id for p in results}

    assert high.pattern_id in ids
    assert low.pattern_id not in ids


@pytest.mark.asyncio
async def test_list_patterns_with_tech_stack_filter(storage: MemoryStorage) -> None:
    """list_patterns with tech_stack_filter should return only matching patterns."""
    fastapi_pattern = make_pattern(tech_stack_tags=["fastapi", "postgresql"])
    react_pattern = make_pattern(tech_stack_tags=["react", "typescript"])
    await storage.save_pattern(fastapi_pattern)
    await storage.save_pattern(react_pattern)

    results = await storage.list_patterns(tech_stack_filter=["fastapi"])
    ids = {p.pattern_id for p in results}

    assert fastapi_pattern.pattern_id in ids
    assert react_pattern.pattern_id not in ids


@pytest.mark.asyncio
async def test_list_patterns_ordered_by_confidence_desc(storage: MemoryStorage) -> None:
    """list_patterns should return patterns ordered by confidence descending."""
    p1 = make_pattern(confidence=40.0)
    p2 = make_pattern(confidence=90.0)
    p3 = make_pattern(confidence=60.0)
    for p in [p1, p2, p3]:
        await storage.save_pattern(p)

    results = await storage.list_patterns()
    confidences = [p.confidence for p in results]
    assert confidences == sorted(confidences, reverse=True)


# ---------------------------------------------------------------------------
# memory_records
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_and_get_record_round_trip(storage: MemoryStorage) -> None:
    """save_record then get_record should return the same record."""
    record = make_record()
    await storage.save_record(record)

    retrieved = await storage.get_record(record.record_id)

    assert retrieved is not None
    assert retrieved.record_id == record.record_id
    assert retrieved.record_type == record.record_type
    assert retrieved.data == record.data
    assert retrieved.embedding == record.embedding
    assert retrieved.expires_at == record.expires_at


@pytest.mark.asyncio
async def test_get_record_returns_none_for_missing_id(storage: MemoryStorage) -> None:
    """get_record should return None for a non-existent record_id."""
    result = await storage.get_record("missing-record-id")
    assert result is None


@pytest.mark.asyncio
async def test_save_record_with_embedding(storage: MemoryStorage) -> None:
    """save_record should persist the embedding vector correctly."""
    embedding = [0.1, 0.2, 0.3, 0.4]
    record = MemoryRecord(
        record_type="reasoning_pattern",
        data={"pattern": "test"},
        embedding=embedding,
        created_at=datetime.now(UTC),
    )
    await storage.save_record(record)

    retrieved = await storage.get_record(record.record_id)
    assert retrieved is not None
    assert retrieved.embedding is not None
    assert len(retrieved.embedding) == len(embedding)
    for a, b in zip(retrieved.embedding, embedding, strict=True):
        assert abs(a - b) < 0.0001


@pytest.mark.asyncio
async def test_find_records_by_type(storage: MemoryStorage) -> None:
    """find_records should return only records of the specified type."""
    company_record = make_record(record_type="company_profile")
    portfolio_record = make_record(record_type="portfolio_entry")
    await storage.save_record(company_record)
    await storage.save_record(portfolio_record)

    results = await storage.find_records("company_profile")
    ids = {r.record_id for r in results}

    assert company_record.record_id in ids
    assert portfolio_record.record_id not in ids


@pytest.mark.asyncio
async def test_delete_expired_removes_old_records(storage: MemoryStorage) -> None:
    """delete_expired should remove records whose expires_at is in the past."""
    expired = make_record(expires_at=datetime.now(UTC) - timedelta(days=1))
    permanent = make_record(expires_at=None)
    future = make_record(expires_at=datetime.now(UTC) + timedelta(days=90))
    for r in [expired, permanent, future]:
        await storage.save_record(r)

    deleted_count = await storage.delete_expired()

    assert deleted_count == 1
    assert await storage.get_record(expired.record_id) is None
    assert await storage.get_record(permanent.record_id) is not None
    assert await storage.get_record(future.record_id) is not None


@pytest.mark.asyncio
async def test_delete_expired_returns_zero_when_nothing_expired(storage: MemoryStorage) -> None:
    """delete_expired should return 0 when no records have expired."""
    record = make_record(expires_at=datetime.now(UTC) + timedelta(days=30))
    await storage.save_record(record)

    count = await storage.delete_expired()
    assert count == 0


# ---------------------------------------------------------------------------
# pipeline_metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_and_get_metrics_round_trip(storage: MemoryStorage) -> None:
    """save_metrics then get_metrics should return the same metrics."""
    metrics = PipelineMetrics(
        total_duration_seconds=300.0,
        layer_durations={"layer_1": 10.0, "layer_5": 200.0},
        total_tokens_used=50000,
        total_api_cost_gbp=3.75,
        retries_by_layer={"layer_5": 1},
        quality_score=82.5,
    )
    run_id = "run-metrics-001"
    await storage.save_metrics(run_id, metrics)

    retrieved = await storage.get_metrics(run_id)

    assert retrieved is not None
    assert abs(retrieved.total_duration_seconds - metrics.total_duration_seconds) < 0.001
    assert retrieved.layer_durations == metrics.layer_durations
    assert retrieved.total_tokens_used == metrics.total_tokens_used
    assert abs(retrieved.total_api_cost_gbp - metrics.total_api_cost_gbp) < 0.001
    assert retrieved.retries_by_layer == metrics.retries_by_layer
    assert abs(retrieved.quality_score - metrics.quality_score) < 0.001


@pytest.mark.asyncio
async def test_get_metrics_returns_none_for_missing_run_id(storage: MemoryStorage) -> None:
    """get_metrics should return None for a non-existent run_id."""
    result = await storage.get_metrics("no-such-run")
    assert result is None


@pytest.mark.asyncio
async def test_save_metrics_replaces_existing(storage: MemoryStorage) -> None:
    """Saving metrics with the same run_id should replace the previous entry."""
    run_id = "run-replace-metrics"
    initial = PipelineMetrics(quality_score=50.0)
    updated = PipelineMetrics(quality_score=90.0)

    await storage.save_metrics(run_id, initial)
    await storage.save_metrics(run_id, updated)

    retrieved = await storage.get_metrics(run_id)
    assert retrieved is not None
    assert abs(retrieved.quality_score - 90.0) < 0.001
