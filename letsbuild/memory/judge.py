"""JUDGE: Record structured verdicts after every Code Forge run.

After each Code Forge run completes, JudgeRecorder analyses the PipelineState
and writes a JudgeVerdict to persistent storage. It also triggers the DISTILL
phase whenever the cumulative verdict count reaches a multiple of 10.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from letsbuild.models.memory_models import JudgeVerdict, VerdictOutcome

if TYPE_CHECKING:
    from letsbuild.memory.distill import PatternDistiller
    from letsbuild.memory.storage import MemoryStorage
    from letsbuild.pipeline.state import PipelineState

__all__ = ["JudgeRecorder"]

logger = structlog.get_logger(__name__)

# Thresholds matching architecture spec and QualityGate default.
_PASS_QUALITY_THRESHOLD: float = 70.0
_PARTIAL_QUALITY_THRESHOLD: float = 40.0
_DISTILL_INTERVAL: int = 10


class JudgeRecorder:
    """Records structured verdicts after every Code Forge run.

    Parameters
    ----------
    storage:
        Initialised MemoryStorage instance used to persist verdicts.
    distiller:
        Optional PatternDistiller. When provided, DISTILL is triggered
        automatically every ``_DISTILL_INTERVAL`` verdicts.
    """

    def __init__(
        self,
        storage: MemoryStorage,
        distiller: PatternDistiller | None = None,
    ) -> None:
        self._storage = storage
        self._distiller = distiller

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def record_verdict(self, state: PipelineState) -> JudgeVerdict:
        """Analyse *state* and persist a JudgeVerdict.

        Extracts quality_score, sandbox_passed, retry counts, API cost, and
        generation time from the accumulated PipelineState, determines the
        overall outcome, saves the verdict, and conditionally triggers DISTILL.

        Parameters
        ----------
        state:
            The completed PipelineState from a pipeline run.

        Returns
        -------
        JudgeVerdict
            The persisted verdict.
        """
        quality_score, sandbox_passed, failure_reasons = self._extract_forge_signals(state)
        retry_count_total = self._extract_retry_count(state)
        api_cost_gbp = state.metrics.total_api_cost_gbp
        generation_time_seconds = self._extract_generation_time(state)

        outcome = self._determine_outcome(quality_score, sandbox_passed)

        verdict = JudgeVerdict(
            run_id=state.thread_id,
            outcome=outcome,
            sandbox_passed=sandbox_passed,
            quality_score=quality_score,
            retry_count_total=retry_count_total,
            api_cost_gbp=api_cost_gbp,
            generation_time_seconds=generation_time_seconds,
            failure_reasons=failure_reasons,
        )

        await self._storage.save_verdict(verdict)

        logger.info(
            "judge.verdict_recorded",
            verdict_id=verdict.verdict_id,
            run_id=verdict.run_id,
            outcome=verdict.outcome,
            quality_score=verdict.quality_score,
            sandbox_passed=verdict.sandbox_passed,
        )

        await self._maybe_trigger_distill()

        return verdict

    # ------------------------------------------------------------------
    # Private helpers — signal extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_forge_signals(
        state: PipelineState,
    ) -> tuple[float, bool, list[str]]:
        """Return (quality_score, sandbox_passed, failure_reasons) from *state*."""
        forge = state.forge_output
        if forge is None:
            # No forge output means the layer did not run or failed entirely.
            early_reasons: list[str] = ["forge_output missing — layer 5 did not complete"]
            return 0.0, False, early_reasons

        # sandbox_passed is True when every test result passed.
        sandbox_passed = bool(forge.test_results) and all(
            passed for passed in forge.test_results.values()
        )

        failure_reasons: list[str] = []
        if not sandbox_passed:
            failed_tests = [name for name, passed in forge.test_results.items() if not passed]
            if failed_tests:
                failure_reasons.append(f"failed_tests: {', '.join(failed_tests)}")
            elif not forge.test_results:
                failure_reasons.append("no test results recorded")

        if forge.review_verdict.value == "fail":
            failure_reasons.append("review_verdict: fail")
            failure_reasons.extend(forge.review_comments[:5])  # cap verbose output

        return forge.quality_score, sandbox_passed, failure_reasons

    @staticmethod
    def _extract_retry_count(state: PipelineState) -> int:
        """Sum retries across all layers from PipelineMetrics."""
        return sum(state.metrics.retries_by_layer.values())

    @staticmethod
    def _extract_generation_time(state: PipelineState) -> float:
        """Return the L5 forge generation time from layer_durations, or total if absent."""
        layer_durations = state.metrics.layer_durations
        forge_key = "layer_5"
        if forge_key in layer_durations:
            return layer_durations[forge_key]

        # Fall back to completed_at - started_at wall time.
        end = state.completed_at or datetime.now(UTC)
        delta = end - state.started_at
        return max(delta.total_seconds(), 0.0)

    # ------------------------------------------------------------------
    # Private helpers — outcome determination
    # ------------------------------------------------------------------

    @staticmethod
    def _determine_outcome(quality_score: float, sandbox_passed: bool) -> VerdictOutcome:
        """Determine VerdictOutcome from quality score and sandbox result."""
        if quality_score >= _PASS_QUALITY_THRESHOLD and sandbox_passed:
            return VerdictOutcome.PASS
        if quality_score >= _PARTIAL_QUALITY_THRESHOLD:
            return VerdictOutcome.PARTIAL
        return VerdictOutcome.FAIL

    # ------------------------------------------------------------------
    # Private helpers — DISTILL trigger
    # ------------------------------------------------------------------

    async def _maybe_trigger_distill(self) -> None:
        """Trigger PatternDistiller every _DISTILL_INTERVAL verdicts."""
        if self._distiller is None:
            return

        count = await self._storage.count_verdicts()
        if count > 0 and count % _DISTILL_INTERVAL == 0:
            logger.info(
                "judge.triggering_distill",
                verdict_count=count,
                interval=_DISTILL_INTERVAL,
            )
            try:
                await self._distiller.distill()
            except Exception:
                logger.exception("judge.distill_trigger_failed", verdict_count=count)
