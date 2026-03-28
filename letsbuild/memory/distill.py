"""DISTILL: Extract learnable patterns from accumulated JUDGE verdicts.

Every 10 runs, PatternDistiller analyses the most recent JudgeVerdict records,
groups them by inferred tech-stack context, and produces DistilledPattern
objects that the ReasoningBank can use to bias future Project Architect runs.

This is a purely heuristic/statistical distiller — no LLM calls are made.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from letsbuild.models.memory_models import DistilledPattern, JudgeVerdict, VerdictOutcome

if TYPE_CHECKING:
    from letsbuild.memory.hnsw_index import HNSWIndex
    from letsbuild.memory.storage import MemoryStorage

__all__ = ["PatternDistiller"]

logger = structlog.get_logger(__name__)

# Minimum sample size before we emit a pattern.
_MIN_SAMPLE_COUNT: int = 2

# Rate thresholds for pattern text selection.
_HIGH_SUCCESS_THRESHOLD: float = 0.75
_HIGH_FAILURE_THRESHOLD: float = 0.60

# High-retry heuristic: average retries per verdict above this signals friction.
_HIGH_RETRY_MEAN: float = 2.0

# Confidence formula weight for sample count saturation (logistic-style).
_SAMPLE_SATURATION: int = 20


def _confidence_from_rate_and_samples(success_rate: float, sample_count: int) -> float:
    """Calculate a [0, 100] confidence score.

    Confidence scales with success_rate but is capped by sample size:
    fewer than ``_MIN_SAMPLE_COUNT`` samples → 0, saturates at 100 by
    ``_SAMPLE_SATURATION``.
    """
    if sample_count < _MIN_SAMPLE_COUNT:
        return 0.0
    sample_weight = min(sample_count / _SAMPLE_SATURATION, 1.0)
    return round(success_rate * 100.0 * sample_weight, 2)


class PatternDistiller:
    """Extract learnable patterns from JUDGE verdicts.

    Parameters
    ----------
    storage:
        Initialised MemoryStorage instance.
    hnsw_index:
        Optional HNSWIndex. When provided, pattern embeddings are added
        for similarity-based retrieval.
    """

    def __init__(
        self,
        storage: MemoryStorage,
        hnsw_index: HNSWIndex | None = None,
    ) -> None:
        self._storage = storage
        self._hnsw = hnsw_index

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def distill(
        self,
        verdicts: list[JudgeVerdict] | None = None,
    ) -> list[DistilledPattern]:
        """Analyse *verdicts* and emit DistilledPattern objects.

        Parameters
        ----------
        verdicts:
            Explicit list of verdicts to analyse. When ``None``, the last 10
            verdicts from storage are loaded automatically.

        Returns
        -------
        list[DistilledPattern]
            Newly created patterns (may be empty if data is insufficient).
        """
        if verdicts is None:
            verdicts = await self._storage.list_verdicts(limit=10)

        if not verdicts:
            logger.info("distill.no_verdicts_available")
            return []

        logger.info("distill.starting", verdict_count=len(verdicts))

        groups = self._group_by_tech_stack(verdicts)
        patterns: list[DistilledPattern] = []

        for tech_tags, group_verdicts in groups.items():
            new_patterns = self._analyse_group(
                tech_tags=list(tech_tags),
                verdicts=group_verdicts,
            )
            patterns.extend(new_patterns)

        # Persist and optionally index each new pattern.
        for pattern in patterns:
            await self._storage.save_pattern(pattern)
            if self._hnsw is not None:
                self._index_pattern(pattern)

        logger.info(
            "distill.complete",
            new_pattern_count=len(patterns),
            verdict_count=len(verdicts),
        )
        return patterns

    # ------------------------------------------------------------------
    # Private helpers — grouping
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_tech_tags(verdict: JudgeVerdict) -> frozenset[str]:
        """Infer tech stack tags from a verdict.

        JudgeVerdict does not directly carry tech stack information (that lives
        in the ProjectSpec which is not persisted in the verdict). We use the
        failure_reasons text as a heuristic signal for now, and fall back to a
        sentinel tag so all verdicts are still grouped.

        When the pipeline wires richer metadata into verdicts (e.g. tech_tags
        field), this method can be updated without changing the rest of the
        distiller.
        """
        if not verdict.failure_reasons:
            return frozenset(["general"])

        # Scan failure reason strings for common tech keywords.
        keywords = {
            "fastapi",
            "sqlalchemy",
            "django",
            "flask",
            "react",
            "next.js",
            "nextjs",
            "postgres",
            "postgresql",
            "redis",
            "docker",
            "pytest",
            "typescript",
            "node",
            "express",
            "mongodb",
            "sqlite",
            "celery",
        }
        found: set[str] = set()
        for reason in verdict.failure_reasons:
            lower = reason.lower()
            for kw in keywords:
                if kw in lower:
                    found.add(kw)

        return frozenset(found) if found else frozenset(["general"])

    def _group_by_tech_stack(
        self,
        verdicts: list[JudgeVerdict],
    ) -> dict[frozenset[str], list[JudgeVerdict]]:
        """Group verdicts by their inferred tech stack tag set."""
        groups: dict[frozenset[str], list[JudgeVerdict]] = defaultdict(list)
        for v in verdicts:
            tags = self._infer_tech_tags(v)
            groups[tags].append(v)
        return dict(groups)

    # ------------------------------------------------------------------
    # Private helpers — analysis
    # ------------------------------------------------------------------

    def _analyse_group(
        self,
        tech_tags: list[str],
        verdicts: list[JudgeVerdict],
    ) -> list[DistilledPattern]:
        """Produce patterns from a group of verdicts sharing the same tech tags."""
        n = len(verdicts)
        if n < _MIN_SAMPLE_COUNT:
            logger.debug(
                "distill.group_skipped_insufficient_samples",
                tech_tags=tech_tags,
                sample_count=n,
            )
            return []

        pass_verdicts = [v for v in verdicts if v.outcome == VerdictOutcome.PASS]
        fail_verdicts = [v for v in verdicts if v.outcome == VerdictOutcome.FAIL]
        success_rate = len(pass_verdicts) / n
        verdict_ids = [v.verdict_id for v in verdicts]
        now = datetime.now(UTC)

        patterns: list[DistilledPattern] = []

        # --- High success rate pattern ---
        if success_rate >= _HIGH_SUCCESS_THRESHOLD:
            tag_str = " + ".join(sorted(tech_tags))
            pattern_text = (
                f"{tag_str} projects succeed at {success_rate:.0%} "
                f"over {n} runs — use as a reliable baseline approach."
            )
            confidence = _confidence_from_rate_and_samples(success_rate, n)
            patterns.append(
                DistilledPattern(
                    pattern_text=pattern_text,
                    source_verdicts=verdict_ids,
                    confidence=confidence,
                    tech_stack_tags=tech_tags,
                    success_rate=round(success_rate * 100.0, 2),
                    sample_count=n,
                    distilled_at=now,
                )
            )

        # --- High failure rate pattern ---
        fail_rate = len(fail_verdicts) / n
        if fail_rate >= _HIGH_FAILURE_THRESHOLD:
            tag_str = " + ".join(sorted(tech_tags))
            pattern_text = (
                f"{tag_str} projects fail at {fail_rate:.0%} "
                f"over {n} runs — review scaffold and validation steps before generation."
            )
            confidence = _confidence_from_rate_and_samples(fail_rate, n)
            patterns.append(
                DistilledPattern(
                    pattern_text=pattern_text,
                    source_verdicts=verdict_ids,
                    confidence=confidence,
                    tech_stack_tags=tech_tags,
                    success_rate=round(success_rate * 100.0, 2),
                    sample_count=n,
                    distilled_at=now,
                )
            )

        # --- High retry count pattern ---
        mean_retries = sum(v.retry_count_total for v in verdicts) / n
        if mean_retries >= _HIGH_RETRY_MEAN:
            tag_str = " + ".join(sorted(tech_tags))
            pattern_text = (
                f"{tag_str} projects average {mean_retries:.1f} retries — "
                f"increase initial planning depth and schema generation order."
            )
            confidence = _confidence_from_rate_and_samples(
                min(mean_retries / (_HIGH_RETRY_MEAN * 2), 1.0), n
            )
            patterns.append(
                DistilledPattern(
                    pattern_text=pattern_text,
                    source_verdicts=verdict_ids,
                    confidence=confidence,
                    tech_stack_tags=tech_tags,
                    success_rate=round(success_rate * 100.0, 2),
                    sample_count=n,
                    distilled_at=now,
                )
            )

        # --- Quality score pattern ---
        mean_quality = sum(v.quality_score for v in verdicts) / n
        if mean_quality >= 80.0 and success_rate >= _HIGH_SUCCESS_THRESHOLD:
            tag_str = " + ".join(sorted(tech_tags))
            pattern_text = (
                f"{tag_str} projects achieve mean quality {mean_quality:.1f}/100 "
                f"— a high-quality template candidate for future runs."
            )
            confidence = _confidence_from_rate_and_samples(success_rate, n)
            patterns.append(
                DistilledPattern(
                    pattern_text=pattern_text,
                    source_verdicts=verdict_ids,
                    confidence=confidence,
                    tech_stack_tags=tech_tags,
                    success_rate=round(success_rate * 100.0, 2),
                    sample_count=n,
                    distilled_at=now,
                )
            )

        logger.debug(
            "distill.group_analysed",
            tech_tags=tech_tags,
            sample_count=n,
            success_rate=success_rate,
            mean_retries=mean_retries,
            patterns_emitted=len(patterns),
        )
        return patterns

    # ------------------------------------------------------------------
    # Private helpers — HNSW indexing
    # ------------------------------------------------------------------

    def _index_pattern(self, pattern: DistilledPattern) -> None:
        """Add *pattern* embedding to the HNSW index."""
        from letsbuild.memory.hnsw_index import simple_text_embedding  # local import avoids cycle

        if self._hnsw is None:
            return

        try:
            vector = simple_text_embedding(pattern.pattern_text)
            self._hnsw.add([pattern.pattern_id], [vector])
            logger.debug("distill.pattern_indexed", pattern_id=pattern.pattern_id)
        except Exception:
            logger.exception("distill.pattern_index_failed", pattern_id=pattern.pattern_id)
