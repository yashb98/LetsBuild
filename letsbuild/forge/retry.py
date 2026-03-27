"""Retry-with-feedback loop for Code Forge task recovery."""

from __future__ import annotations

from collections.abc import Callable  # noqa: TC003
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from letsbuild.models.forge_models import AgentOutput, Task

logger = structlog.get_logger()


class RetryHandler:
    """Manages retry-with-feedback for failed Code Forge tasks.

    When a test or build fails, the handler captures the exact error output,
    feeds structured context back to the coder function, and requests a
    targeted fix rather than a full regeneration.
    """

    def __init__(self, max_retries: int = 3) -> None:
        self.max_retries = max_retries
        self._log = logger.bind(component="retry_handler")

    async def retry_with_feedback(
        self,
        task: Task,
        error_context: str,
        coder_fn: Callable[..., AgentOutput],
        max_retries: int | None = None,
    ) -> AgentOutput:
        """Retry a failed task with structured error feedback.

        Parameters
        ----------
        task:
            The task that failed and needs a fix.
        error_context:
            The initial error output from the failed test or build.
        coder_fn:
            An async or sync callable that accepts ``(task, retry_context)``
            and returns an :class:`AgentOutput`.
        max_retries:
            Override the instance default for this call.

        Returns
        -------
        AgentOutput
            A successful output, or the last failed output after exhausting
            all retries.
        """
        limit = max_retries if max_retries is not None else self.max_retries
        current_error = error_context

        for attempt in range(1, limit + 1):
            self._log.info(
                "retry_attempt",
                task_id=task.task_id,
                attempt=attempt,
                max_retries=limit,
            )

            retry_ctx = self.build_retry_context(
                original_task=task.description,
                error_output=current_error,
                retry_number=attempt,
            )

            result = await coder_fn(task, retry_ctx)

            if result.success:
                self._log.info(
                    "retry_succeeded",
                    task_id=task.task_id,
                    attempt=attempt,
                )
                return result

            # Extract error for next attempt.
            current_error = (
                result.error.message
                if result.error is not None
                else "Unknown error — no structured error returned."
            )
            self._log.warning(
                "retry_failed",
                task_id=task.task_id,
                attempt=attempt,
                error=current_error,
            )

        # Exhausted all retries — return last failed result.
        self._log.error(
            "retries_exhausted",
            task_id=task.task_id,
            total_attempts=limit,
        )
        return result  # type: ignore[possibly-undefined]  # limit >= 1

    def build_retry_context(
        self,
        original_task: str,
        error_output: str,
        retry_number: int,
    ) -> str:
        """Build structured retry context for the coder.

        The context instructs the coder to produce a targeted fix rather than
        regenerating the full implementation from scratch.
        """
        return (
            f"## RETRY ATTEMPT {retry_number}\n\n"
            f"### Original Task\n{original_task}\n\n"
            f"### Error Output\n```\n{error_output}\n```\n\n"
            "### Instructions\n"
            "Fix the SPECIFIC error shown above. Do NOT regenerate the entire "
            "implementation from scratch. Make the minimal targeted change "
            "needed to resolve this failure."
        )
