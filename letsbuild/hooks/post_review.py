"""PostReview hook — routes review verdicts to retry or proceed."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import structlog

from letsbuild.models.forge_models import AgentOutput, ReviewVerdict

logger = structlog.get_logger()


class PostReviewAction(StrEnum):
    """Possible actions after a review verdict."""

    RETRY = "retry"
    PROCEED = "proceed"
    ABORT = "abort"


@dataclass
class PostReviewResult:
    """Result returned by the PostReview hook."""

    action: PostReviewAction
    reason: str
    retry_context: str | None = None


class PostReviewHook:
    """Routes the Reviewer verdict to the appropriate next step.

    Corresponds to the ``PostReview`` hook in the Layer 9 hooks table
    (ARCHITECTURE.md).  Must complete within 5 seconds per security rules.
    """

    def __init__(self) -> None:
        self.log = structlog.get_logger(hook="PostReview")

    async def run(
        self,
        review_verdict: ReviewVerdict,
        agent_output: AgentOutput | None = None,
    ) -> PostReviewResult:
        """Decide next action based on *review_verdict*.

        * ``FAIL``  -> ``RETRY`` (include error context for the Coder)
        * ``PASS``  -> ``PROCEED``
        * ``PASS_WITH_SUGGESTIONS`` -> ``PROCEED`` (log suggestions)
        """
        if review_verdict == ReviewVerdict.FAIL:
            retry_context = self._build_retry_context(agent_output)
            self.log.warning("review_failed", action="retry")
            return PostReviewResult(
                action=PostReviewAction.RETRY,
                reason="Reviewer verdict is FAIL — routing back to Coder for retry.",
                retry_context=retry_context,
            )

        if review_verdict == ReviewVerdict.PASS_WITH_SUGGESTIONS:
            self.log.info("review_pass_with_suggestions", action="proceed")
            return PostReviewResult(
                action=PostReviewAction.PROCEED,
                reason="Reviewer verdict is PASS_WITH_SUGGESTIONS — proceeding with logged suggestions.",
            )

        # ReviewVerdict.PASS
        self.log.info("review_passed", action="proceed")
        return PostReviewResult(
            action=PostReviewAction.PROCEED,
            reason="Reviewer verdict is PASS — proceeding to next stage.",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_retry_context(agent_output: AgentOutput | None) -> str:
        """Extract actionable context from the agent output for the retry loop."""
        if agent_output is None:
            return "No agent output available for retry context."

        parts: list[str] = [f"Agent role: {agent_output.agent_role}"]
        if agent_output.error is not None:
            parts.append(f"Error category: {agent_output.error.error_category}")
            parts.append(f"Error message: {agent_output.error.message}")
        return " | ".join(parts)
