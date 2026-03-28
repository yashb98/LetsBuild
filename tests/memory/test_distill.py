"""Tests for PatternDistiller — DISTILL phase of Memory layer."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from letsbuild.memory.distill import PatternDistiller, _confidence_from_rate_and_samples
from letsbuild.memory.storage import MemoryStorage
from letsbuild.models.memory_models import JudgeVerdict, VerdictOutcome

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


@pytest.fixture
async def storage(tmp_path: pytest.TempPathFactory) -> MemoryStorage:  # type: ignore[type-arg]
    """Initialised MemoryStorage backed by a temp file."""
    db_path = str(tmp_path / "distill_test.db")
    store = MemoryStorage(db_path=db_path)
    async with store:
        yield store


def make_verdict(
    outcome: VerdictOutcome = VerdictOutcome.PASS,
    quality_score: float = 85.0,
    sandbox_passed: bool = True,
    retry_count_total: int = 0,
    failure_reasons: list[str] | None = None,
) -> JudgeVerdict:
    """Build a JudgeVerdict with sensible defaults."""
    return JudgeVerdict(
        run_id="run-test",
        outcome=outcome,
        sandbox_passed=sandbox_passed,
        quality_score=quality_score,
        retry_count_total=retry_count_total,
        api_cost_gbp=1.0,
        generation_time_seconds=100.0,
        failure_reasons=failure_reasons or [],
        judged_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# _confidence_from_rate_and_samples helper
# ---------------------------------------------------------------------------


def test_confidence_zero_for_below_min_sample_count() -> None:
    """Confidence should be 0 when sample_count < MIN_SAMPLE_COUNT (2)."""
    assert _confidence_from_rate_and_samples(1.0, 1) == 0.0


def test_confidence_scales_with_sample_count() -> None:
    """More samples should yield higher confidence (up to saturation)."""
    c_small = _confidence_from_rate_and_samples(1.0, 2)
    c_large = _confidence_from_rate_and_samples(1.0, 10)
    assert c_large > c_small


def test_confidence_saturates_at_100_with_many_samples() -> None:
    """With sample_count >= SAMPLE_SATURATION (20) and success_rate 1.0, confidence == 100."""
    confidence = _confidence_from_rate_and_samples(1.0, 20)
    assert abs(confidence - 100.0) < 0.01


def test_confidence_scales_with_success_rate() -> None:
    """Higher success rate should yield higher confidence (same sample count)."""
    c_low = _confidence_from_rate_and_samples(0.5, 10)
    c_high = _confidence_from_rate_and_samples(1.0, 10)
    assert c_high > c_low


# ---------------------------------------------------------------------------
# distill — basic behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_distill_with_empty_verdicts_returns_empty(storage: MemoryStorage) -> None:
    """distill() with an explicit empty list should return an empty pattern list."""
    distiller = PatternDistiller(storage=storage)
    patterns = await distiller.distill(verdicts=[])
    assert patterns == []


@pytest.mark.asyncio
async def test_distill_loads_from_storage_when_no_verdicts_provided(
    storage: MemoryStorage,
) -> None:
    """When verdicts=None, distill() should load the last 10 verdicts from storage."""
    # No verdicts in storage → should return []
    distiller = PatternDistiller(storage=storage)
    patterns = await distiller.distill(verdicts=None)
    assert patterns == []


@pytest.mark.asyncio
async def test_distill_with_single_verdict_below_min_sample_count(
    storage: MemoryStorage,
) -> None:
    """Groups with fewer than MIN_SAMPLE_COUNT (2) verdicts should produce no patterns."""
    distiller = PatternDistiller(storage=storage)
    single_verdict = [make_verdict(outcome=VerdictOutcome.PASS)]
    patterns = await distiller.distill(verdicts=single_verdict)
    # All verdicts share the same "general" tag → one group of 1 → skipped
    assert patterns == []


@pytest.mark.asyncio
async def test_distill_mixed_verdicts_produces_patterns(storage: MemoryStorage) -> None:
    """A group of mixed pass/fail verdicts with >= 2 samples should produce at least one pattern."""
    verdicts = [
        make_verdict(outcome=VerdictOutcome.PASS),
        make_verdict(outcome=VerdictOutcome.PASS),
        make_verdict(outcome=VerdictOutcome.PASS),
        make_verdict(outcome=VerdictOutcome.FAIL),
    ]
    distiller = PatternDistiller(storage=storage)
    patterns = await distiller.distill(verdicts=verdicts)
    # 3/4 pass → 75% success → HIGH_SUCCESS_THRESHOLD (0.75) met → at least one pattern
    assert len(patterns) >= 1


# ---------------------------------------------------------------------------
# distill — high-success pattern
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_distill_extracts_high_success_pattern(storage: MemoryStorage) -> None:
    """When >= 75% verdicts are PASS, a high-success pattern should be produced."""
    verdicts = [make_verdict(outcome=VerdictOutcome.PASS) for _ in range(4)]
    distiller = PatternDistiller(storage=storage)
    patterns = await distiller.distill(verdicts=verdicts)

    pattern_texts = [p.pattern_text for p in patterns]
    assert any("succeed" in t or "reliable" in t for t in pattern_texts)


@pytest.mark.asyncio
async def test_distill_high_success_pattern_has_positive_confidence(
    storage: MemoryStorage,
) -> None:
    """High-success patterns should have a confidence > 0."""
    verdicts = [make_verdict(outcome=VerdictOutcome.PASS) for _ in range(4)]
    distiller = PatternDistiller(storage=storage)
    patterns = await distiller.distill(verdicts=verdicts)

    assert all(p.confidence > 0.0 for p in patterns)


# ---------------------------------------------------------------------------
# distill — high-failure pattern
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_distill_extracts_failure_pattern(storage: MemoryStorage) -> None:
    """When >= 60% verdicts are FAIL, a failure pattern should be produced."""
    verdicts = [make_verdict(outcome=VerdictOutcome.FAIL) for _ in range(4)]
    distiller = PatternDistiller(storage=storage)
    patterns = await distiller.distill(verdicts=verdicts)

    pattern_texts = [p.pattern_text for p in patterns]
    assert any("fail" in t for t in pattern_texts)


# ---------------------------------------------------------------------------
# distill — confidence calculation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_distill_pattern_confidence_increases_with_more_samples(
    storage: MemoryStorage,
) -> None:
    """More verdicts in the same group should yield a higher confidence pattern."""
    small_group = [make_verdict(outcome=VerdictOutcome.PASS) for _ in range(2)]
    large_group = [make_verdict(outcome=VerdictOutcome.PASS) for _ in range(10)]

    distiller = PatternDistiller(storage=storage)
    small_patterns = await distiller.distill(verdicts=small_group)
    large_patterns = await distiller.distill(verdicts=large_group)

    small_max = max((p.confidence for p in small_patterns), default=0.0)
    large_max = max((p.confidence for p in large_patterns), default=0.0)
    assert large_max >= small_max


# ---------------------------------------------------------------------------
# distill — persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_distill_saves_patterns_to_storage(storage: MemoryStorage) -> None:
    """Patterns produced by distill() should be persisted in storage."""
    verdicts = [make_verdict(outcome=VerdictOutcome.PASS) for _ in range(4)]
    distiller = PatternDistiller(storage=storage)
    patterns = await distiller.distill(verdicts=verdicts)

    if patterns:
        retrieved = await storage.get_pattern(patterns[0].pattern_id)
        assert retrieved is not None
        assert retrieved.pattern_id == patterns[0].pattern_id


# ---------------------------------------------------------------------------
# distill — high retry pattern
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_distill_produces_retry_pattern_for_high_retry_runs(
    storage: MemoryStorage,
) -> None:
    """When mean retries >= 2.0, a retry-warning pattern should be produced."""
    verdicts = [make_verdict(outcome=VerdictOutcome.PARTIAL, retry_count_total=3) for _ in range(2)]
    distiller = PatternDistiller(storage=storage)
    patterns = await distiller.distill(verdicts=verdicts)

    pattern_texts = [p.pattern_text for p in patterns]
    assert any("retr" in t.lower() for t in pattern_texts)


# ---------------------------------------------------------------------------
# distill — HNSW indexing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_distill_indexes_patterns_in_hnsw_when_provided(
    storage: MemoryStorage,
) -> None:
    """When an HNSWIndex is passed, patterns should be added to it."""
    from letsbuild.memory.hnsw_index import HNSWIndex

    hnsw = HNSWIndex(dim=384, max_elements=100)
    hnsw.init_index()

    verdicts = [make_verdict(outcome=VerdictOutcome.PASS) for _ in range(4)]
    distiller = PatternDistiller(storage=storage, hnsw_index=hnsw)
    patterns = await distiller.distill(verdicts=verdicts)

    if patterns:
        assert len(hnsw) == len(patterns)
