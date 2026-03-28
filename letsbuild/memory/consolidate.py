"""CONSOLIDATE: Elastic Weight Consolidation for ReasoningBank patterns.

When new patterns arrive from DISTILL, PatternConsolidator prevents well-established
high-confidence patterns from being overwritten by conflicting low-sample patterns.
This is a simplified EWC++ analogue operating on pattern confidence values rather
than neural network weights.

Protection rules
----------------
* A pattern is *protected* if its confidence >= ``protection_threshold``.
* A new pattern *conflicts* with an existing one when:
  - Their tech_stack_tags overlap by more than 50%, AND
  - The pattern_texts are directionally contradictory (detected via keyword
    analysis — "succeed/works well" vs "fail/avoid").
* Conflict resolution:
  - If the existing pattern is protected and the new one has lower confidence,
    keep the existing pattern unchanged.
  - If both have similar confidence, merge their sample counts and
    recalculate a blended confidence.
  - If the new pattern has strictly higher confidence, replace the existing one.
* Non-conflicting new patterns are always accepted.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from letsbuild.models.memory_models import DistilledPattern

if TYPE_CHECKING:
    from letsbuild.memory.hnsw_index import HNSWIndex
    from letsbuild.memory.storage import MemoryStorage

__all__ = ["PatternConsolidator"]

logger = structlog.get_logger(__name__)

# Keyword sets used to determine pattern polarity.
_POSITIVE_SIGNALS: frozenset[str] = frozenset(
    {
        "succeed",
        "success",
        "works",
        "reliable",
        "high-quality",
        "baseline",
        "recommended",
        "good",
        "best",
        "template",
    }
)
_NEGATIVE_SIGNALS: frozenset[str] = frozenset(
    {
        "fail",
        "avoid",
        "poor",
        "review",
        "caution",
        "error",
        "problematic",
        "retries",
        "retry",
        "friction",
    }
)

# Tag overlap fraction above which two patterns are considered "about the same stack".
_TAG_OVERLAP_THRESHOLD: float = 0.5

# Confidence delta below which we consider two patterns to have "similar" confidence
# (triggering a merge rather than a replacement).
_SIMILAR_CONFIDENCE_DELTA: float = 10.0


def _pattern_polarity(pattern_text: str) -> str:
    """Return 'positive', 'negative', or 'neutral' based on keyword presence."""
    lower = pattern_text.lower()
    pos_hits = sum(1 for kw in _POSITIVE_SIGNALS if kw in lower)
    neg_hits = sum(1 for kw in _NEGATIVE_SIGNALS if kw in lower)
    if pos_hits > neg_hits:
        return "positive"
    if neg_hits > pos_hits:
        return "negative"
    return "neutral"


def _tags_overlap_fraction(tags_a: list[str], tags_b: list[str]) -> float:
    """Return the Jaccard overlap between two tag lists."""
    set_a = {t.lower() for t in tags_a}
    set_b = {t.lower() for t in tags_b}
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union


def _are_contradictory(existing: DistilledPattern, new: DistilledPattern) -> bool:
    """Return True if existing and new patterns carry opposite polarities."""
    existing_polarity = _pattern_polarity(existing.pattern_text)
    new_polarity = _pattern_polarity(new.pattern_text)

    # Both neutral or same polarity → not contradictory.
    if existing_polarity == "neutral" or new_polarity == "neutral":
        return False
    return existing_polarity != new_polarity


def _merge_patterns(
    existing: DistilledPattern,
    new: DistilledPattern,
) -> DistilledPattern:
    """Merge two similar-confidence patterns into a blended pattern.

    The winner keeps its pattern_id (existing) but absorbs the new pattern's
    sample count and recalculates a weighted-average confidence and success_rate.
    """
    total_samples = existing.sample_count + new.sample_count
    # Weighted average for both confidence and success_rate.
    blended_confidence = (
        existing.confidence * existing.sample_count + new.confidence * new.sample_count
    ) / total_samples
    blended_success_rate = (
        existing.success_rate * existing.sample_count + new.success_rate * new.sample_count
    ) / total_samples

    merged_verdict_ids = list(dict.fromkeys(existing.source_verdicts + new.source_verdicts))

    return DistilledPattern(
        pattern_id=existing.pattern_id,
        pattern_text=existing.pattern_text,
        source_verdicts=merged_verdict_ids,
        confidence=round(blended_confidence, 2),
        tech_stack_tags=existing.tech_stack_tags,
        success_rate=round(blended_success_rate, 2),
        sample_count=total_samples,
        distilled_at=datetime.now(UTC),
    )


class PatternConsolidator:
    """Prevent catastrophic forgetting in the ReasoningBank.

    Parameters
    ----------
    storage:
        Initialised MemoryStorage instance.
    hnsw_index:
        Optional HNSWIndex. When provided, updated patterns are re-indexed.
    protection_threshold:
        Minimum confidence for a pattern to be considered "protected".
        Defaults to 80.0.
    """

    def __init__(
        self,
        storage: MemoryStorage,
        hnsw_index: HNSWIndex | None = None,
        protection_threshold: float = 80.0,
    ) -> None:
        self._storage = storage
        self._hnsw = hnsw_index
        self._protection_threshold = protection_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def consolidate(
        self,
        new_patterns: list[DistilledPattern],
    ) -> list[DistilledPattern]:
        """Integrate *new_patterns* while protecting high-confidence existing ones.

        Parameters
        ----------
        new_patterns:
            Freshly distilled patterns to integrate into the ReasoningBank.

        Returns
        -------
        list[DistilledPattern]
            The final accepted pattern list after conflict resolution.
        """
        if not new_patterns:
            logger.info("consolidate.no_new_patterns")
            existing = await self._storage.list_patterns()
            return existing

        existing_patterns = await self._storage.list_patterns()
        existing_by_id: dict[str, DistilledPattern] = {p.pattern_id: p for p in existing_patterns}

        accepted: list[DistilledPattern] = []
        protected_overrides: int = 0
        merges: int = 0
        replacements: int = 0

        for new_pat in new_patterns:
            conflict = self._find_conflict(new_pat, list(existing_by_id.values()))

            if conflict is None:
                # No conflict — accept the new pattern.
                await self._storage.save_pattern(new_pat)
                self._maybe_index(new_pat)
                existing_by_id[new_pat.pattern_id] = new_pat
                accepted.append(new_pat)
                logger.debug(
                    "consolidate.pattern_accepted",
                    pattern_id=new_pat.pattern_id,
                    confidence=new_pat.confidence,
                )
                continue

            # --- Conflict detected ---
            existing_pat = conflict
            is_protected = existing_pat.confidence >= self._protection_threshold

            if is_protected and new_pat.confidence < existing_pat.confidence:
                # EWC++ rule: protected pattern wins when new has lower confidence.
                protected_overrides += 1
                logger.info(
                    "consolidate.protected_pattern_retained",
                    existing_pattern_id=existing_pat.pattern_id,
                    existing_confidence=existing_pat.confidence,
                    new_confidence=new_pat.confidence,
                )
                # Do not accept the new pattern; existing remains unchanged.
                continue

            confidence_delta = abs(new_pat.confidence - existing_pat.confidence)
            if confidence_delta <= _SIMILAR_CONFIDENCE_DELTA:
                # Similar confidence → merge sample counts for a richer pattern.
                merged = _merge_patterns(existing_pat, new_pat)
                await self._storage.save_pattern(merged)
                self._maybe_index(merged)
                existing_by_id[merged.pattern_id] = merged
                accepted.append(merged)
                merges += 1
                logger.info(
                    "consolidate.patterns_merged",
                    pattern_id=merged.pattern_id,
                    blended_confidence=merged.confidence,
                    total_samples=merged.sample_count,
                )
            else:
                # New pattern has strictly higher confidence — replace existing.
                await self._storage.save_pattern(new_pat)
                self._maybe_index(new_pat)
                existing_by_id.pop(existing_pat.pattern_id, None)
                existing_by_id[new_pat.pattern_id] = new_pat
                accepted.append(new_pat)
                replacements += 1
                logger.info(
                    "consolidate.pattern_replaced",
                    old_pattern_id=existing_pat.pattern_id,
                    new_pattern_id=new_pat.pattern_id,
                    old_confidence=existing_pat.confidence,
                    new_confidence=new_pat.confidence,
                )

        final_patterns = list(existing_by_id.values())

        logger.info(
            "consolidate.complete",
            new_patterns_received=len(new_patterns),
            accepted=len(accepted),
            protected_overrides=protected_overrides,
            merges=merges,
            replacements=replacements,
            total_patterns_in_bank=len(final_patterns),
        )

        return final_patterns

    # ------------------------------------------------------------------
    # Private helpers — conflict detection
    # ------------------------------------------------------------------

    def _find_conflict(
        self,
        new_pat: DistilledPattern,
        existing_patterns: list[DistilledPattern],
    ) -> DistilledPattern | None:
        """Return the first existing pattern that conflicts with *new_pat*, or None."""
        for existing in existing_patterns:
            overlap = _tags_overlap_fraction(existing.tech_stack_tags, new_pat.tech_stack_tags)
            if overlap < _TAG_OVERLAP_THRESHOLD:
                continue  # Different stacks — no conflict.
            if _are_contradictory(existing, new_pat):
                return existing
        return None

    # ------------------------------------------------------------------
    # Private helpers — HNSW indexing
    # ------------------------------------------------------------------

    def _maybe_index(self, pattern: DistilledPattern) -> None:
        """Add or update *pattern* in the HNSW index if available."""
        if self._hnsw is None:
            return

        from letsbuild.memory.hnsw_index import simple_text_embedding  # local import avoids cycle

        try:
            vector = simple_text_embedding(pattern.pattern_text)
            if self._hnsw.contains(pattern.pattern_id):
                self._hnsw.update(pattern.pattern_id, vector)
            else:
                self._hnsw.add([pattern.pattern_id], [vector])
            logger.debug("consolidate.pattern_indexed", pattern_id=pattern.pattern_id)
        except Exception:
            logger.exception("consolidate.pattern_index_failed", pattern_id=pattern.pattern_id)
