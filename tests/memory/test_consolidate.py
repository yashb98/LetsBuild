"""Tests for PatternConsolidator — CONSOLIDATE (EWC++) phase of Memory layer."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from letsbuild.memory.consolidate import (
    PatternConsolidator,
    _merge_patterns,
    _pattern_polarity,
    _tags_overlap_fraction,
)
from letsbuild.memory.storage import MemoryStorage
from letsbuild.models.memory_models import DistilledPattern

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


@pytest.fixture
async def storage(tmp_path: pytest.TempPathFactory) -> MemoryStorage:  # type: ignore[type-arg]
    """Initialised MemoryStorage backed by a temp file."""
    db_path = str(tmp_path / "consolidate_test.db")
    store = MemoryStorage(db_path=db_path)
    async with store:
        yield store


def make_pattern(
    *,
    pattern_text: str = "fastapi projects succeed at 80% — use as a reliable baseline.",
    tech_stack_tags: list[str] | None = None,
    confidence: float = 60.0,
    success_rate: float = 80.0,
    sample_count: int = 5,
    source_verdicts: list[str] | None = None,
) -> DistilledPattern:
    """Create a DistilledPattern with sensible defaults."""
    return DistilledPattern(
        pattern_text=pattern_text,
        source_verdicts=source_verdicts or ["v1", "v2"],
        confidence=confidence,
        tech_stack_tags=tech_stack_tags or ["fastapi"],
        success_rate=success_rate,
        sample_count=sample_count,
        distilled_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------


def test_pattern_polarity_positive() -> None:
    """Patterns with positive signals should be classified as 'positive'."""
    text = "fastapi projects succeed at 80% — use as a reliable baseline approach."
    assert _pattern_polarity(text) == "positive"


def test_pattern_polarity_negative() -> None:
    """Patterns with negative signals should be classified as 'negative'."""
    text = "fastapi projects fail at 70% — review scaffold before generation."
    assert _pattern_polarity(text) == "negative"


def test_pattern_polarity_neutral() -> None:
    """A pattern with no clear signals should be 'neutral'."""
    text = "fastapi project generated with standard structure."
    assert _pattern_polarity(text) == "neutral"


def test_tags_overlap_fraction_identical() -> None:
    """Identical tag lists should have overlap = 1.0."""
    assert _tags_overlap_fraction(["fastapi", "postgres"], ["fastapi", "postgres"]) == 1.0


def test_tags_overlap_fraction_disjoint() -> None:
    """Completely different tag lists should have overlap = 0.0."""
    assert _tags_overlap_fraction(["react"], ["django"]) == 0.0


def test_tags_overlap_fraction_partial() -> None:
    """Partially overlapping tag lists should have overlap between 0 and 1."""
    overlap = _tags_overlap_fraction(["fastapi", "postgres"], ["fastapi", "redis"])
    assert 0.0 < overlap < 1.0


def test_tags_overlap_fraction_both_empty() -> None:
    """Two empty tag lists should have overlap = 1.0 (both represent 'general')."""
    assert _tags_overlap_fraction([], []) == 1.0


def test_merge_patterns_blends_confidence_and_sample_count() -> None:
    """_merge_patterns should blend confidence and accumulate sample counts."""
    existing = make_pattern(confidence=60.0, sample_count=4, success_rate=80.0)
    new = make_pattern(confidence=80.0, sample_count=6, success_rate=90.0)

    merged = _merge_patterns(existing, new)

    # Sample count should be sum
    assert merged.sample_count == 10
    # Blended confidence: (60*4 + 80*6) / 10 = 720/10 = 72
    assert abs(merged.confidence - 72.0) < 0.01
    # Pattern ID preserved from existing
    assert merged.pattern_id == existing.pattern_id


def test_merge_patterns_deduplicates_source_verdicts() -> None:
    """_merge_patterns should deduplicate source verdict IDs."""
    existing = make_pattern(source_verdicts=["v1", "v2"])
    new = make_pattern(source_verdicts=["v2", "v3"])

    merged = _merge_patterns(existing, new)

    # v2 appears in both — should appear once
    assert merged.source_verdicts.count("v2") == 1
    assert set(merged.source_verdicts) == {"v1", "v2", "v3"}


# ---------------------------------------------------------------------------
# consolidate — non-conflicting patterns
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_conflicting_patterns_are_all_kept(storage: MemoryStorage) -> None:
    """Patterns about different tech stacks should all be accepted without conflict."""
    fastapi_pattern = make_pattern(
        pattern_text="fastapi projects succeed — reliable baseline.",
        tech_stack_tags=["fastapi"],
        confidence=60.0,
    )
    react_pattern = make_pattern(
        pattern_text="react projects succeed — reliable baseline.",
        tech_stack_tags=["react"],
        confidence=60.0,
    )

    consolidator = PatternConsolidator(storage=storage)
    result = await consolidator.consolidate([fastapi_pattern, react_pattern])

    accepted_ids = {p.pattern_id for p in result}
    assert fastapi_pattern.pattern_id in accepted_ids
    assert react_pattern.pattern_id in accepted_ids


@pytest.mark.asyncio
async def test_consolidate_empty_new_patterns_returns_existing(storage: MemoryStorage) -> None:
    """Consolidating an empty list should return the existing stored patterns unchanged."""
    existing = make_pattern(confidence=70.0)
    await storage.save_pattern(existing)

    consolidator = PatternConsolidator(storage=storage)
    result = await consolidator.consolidate([])

    assert len(result) == 1
    assert result[0].pattern_id == existing.pattern_id


# ---------------------------------------------------------------------------
# consolidate — conflict resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_conflicting_higher_confidence_new_pattern_replaces_existing(
    storage: MemoryStorage,
) -> None:
    """When new pattern has strictly higher confidence, it should replace the existing one."""
    existing = make_pattern(
        pattern_text="fastapi projects succeed — reliable baseline.",
        tech_stack_tags=["fastapi"],
        confidence=30.0,
        sample_count=3,
    )
    await storage.save_pattern(existing)

    new = make_pattern(
        pattern_text="fastapi projects fail at 70% — review scaffold.",
        tech_stack_tags=["fastapi"],
        confidence=75.0,
        sample_count=10,
    )

    consolidator = PatternConsolidator(storage=storage)
    result = await consolidator.consolidate([new])

    result_ids = {p.pattern_id for p in result}
    # New pattern should be in the bank; old one replaced
    assert new.pattern_id in result_ids


@pytest.mark.asyncio
async def test_conflicting_similar_confidence_patterns_are_merged(
    storage: MemoryStorage,
) -> None:
    """When confidence delta <= 10, conflicting patterns should be merged."""
    existing = make_pattern(
        pattern_text="fastapi projects succeed — reliable baseline.",
        tech_stack_tags=["fastapi"],
        confidence=60.0,
        sample_count=4,
    )
    await storage.save_pattern(existing)

    new = make_pattern(
        pattern_text="fastapi projects fail at 70% — review scaffold.",
        tech_stack_tags=["fastapi"],
        confidence=65.0,  # within 10-point delta of 60
        sample_count=6,
    )

    consolidator = PatternConsolidator(storage=storage)
    result = await consolidator.consolidate([new])

    # Existing pattern_id should persist (merge keeps existing.pattern_id)
    result_ids = {p.pattern_id for p in result}
    assert existing.pattern_id in result_ids

    merged = next(p for p in result if p.pattern_id == existing.pattern_id)
    # Merged sample count = 4 + 6 = 10
    assert merged.sample_count == 10


# ---------------------------------------------------------------------------
# consolidate — protected patterns (EWC++)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_protected_pattern_survives_low_confidence_challenge(
    storage: MemoryStorage,
) -> None:
    """A high-confidence (protected) pattern should not be overwritten by a lower-confidence one."""
    protected = make_pattern(
        pattern_text="fastapi projects succeed — reliable baseline.",
        tech_stack_tags=["fastapi"],
        confidence=85.0,  # above default protection_threshold of 80
        sample_count=20,
    )
    await storage.save_pattern(protected)

    challenger = make_pattern(
        pattern_text="fastapi projects fail at 70% — review scaffold.",
        tech_stack_tags=["fastapi"],
        confidence=40.0,  # lower than protected.confidence
        sample_count=3,
    )

    consolidator = PatternConsolidator(storage=storage, protection_threshold=80.0)
    result = await consolidator.consolidate([challenger])

    result_ids = {p.pattern_id for p in result}
    # Protected pattern should still be in the bank
    assert protected.pattern_id in result_ids
    # Challenger should NOT have been added (it was blocked)
    assert challenger.pattern_id not in result_ids


@pytest.mark.asyncio
async def test_protected_pattern_can_be_replaced_by_higher_confidence(
    storage: MemoryStorage,
) -> None:
    """A protected pattern SHOULD be replaced if the new pattern has strictly higher confidence."""
    protected = make_pattern(
        pattern_text="fastapi projects succeed — reliable baseline.",
        tech_stack_tags=["fastapi"],
        confidence=82.0,
        sample_count=10,
    )
    await storage.save_pattern(protected)

    stronger = make_pattern(
        pattern_text="fastapi projects fail at 80% — review scaffold.",
        tech_stack_tags=["fastapi"],
        confidence=95.0,  # strictly higher
        sample_count=30,
    )

    consolidator = PatternConsolidator(storage=storage, protection_threshold=80.0)
    result = await consolidator.consolidate([stronger])

    result_ids = {p.pattern_id for p in result}
    assert stronger.pattern_id in result_ids


# ---------------------------------------------------------------------------
# consolidate — sample count merging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sample_count_merging_on_similar_confidence(storage: MemoryStorage) -> None:
    """Merging patterns should add their sample counts together."""
    existing = make_pattern(
        pattern_text="fastapi projects succeed — reliable baseline.",
        tech_stack_tags=["fastapi"],
        confidence=55.0,
        sample_count=7,
    )
    await storage.save_pattern(existing)

    new = make_pattern(
        pattern_text="fastapi projects fail at 70% — review scaffold.",
        tech_stack_tags=["fastapi"],
        confidence=60.0,  # within 10-point delta
        sample_count=8,
    )

    consolidator = PatternConsolidator(storage=storage)
    result = await consolidator.consolidate([new])

    merged = next((p for p in result if p.pattern_id == existing.pattern_id), None)
    assert merged is not None
    assert merged.sample_count == 15  # 7 + 8
