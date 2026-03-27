"""Tests for the retry-with-feedback handler."""

from __future__ import annotations

import pytest

from letsbuild.forge.retry import RetryHandler
from letsbuild.models.forge_models import AgentOutput, AgentRole, Task
from letsbuild.models.shared import ErrorCategory, StructuredError


def _make_task() -> Task:
    return Task(
        task_id="task-001",
        module_name="src/app.py",
        description="Implement the main application module.",
        estimated_complexity=5,
    )


def _make_output(*, success: bool, error_msg: str | None = None) -> AgentOutput:
    return AgentOutput(
        agent_role=AgentRole.CODER,
        task_id="task-001",
        success=success,
        output_modules=[],
        error=(
            StructuredError(
                error_category=ErrorCategory.TRANSIENT,
                is_retryable=True,
                message=error_msg or "test failure",
            )
            if not success
            else None
        ),
        tokens_used=100,
        execution_time_seconds=1.0,
        retry_count=0,
    )


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt() -> None:
    """Coder fails once, then succeeds on the second attempt."""
    handler = RetryHandler(max_retries=3)
    task = _make_task()
    call_count = 0

    async def coder_fn(_task: Task, _ctx: str) -> AgentOutput:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_output(success=False, error_msg="ImportError: no module named foo")
        return _make_output(success=True)

    result = await handler.retry_with_feedback(
        task=task,
        error_context="ImportError: no module named foo",
        coder_fn=coder_fn,
    )

    assert result.success is True
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_exhausts_max_retries() -> None:
    """Coder fails on every attempt; handler returns last failure."""
    handler = RetryHandler(max_retries=2)
    task = _make_task()
    call_count = 0

    async def coder_fn(_task: Task, _ctx: str) -> AgentOutput:
        nonlocal call_count
        call_count += 1
        return _make_output(success=False, error_msg=f"error on attempt {call_count}")

    result = await handler.retry_with_feedback(
        task=task,
        error_context="initial failure",
        coder_fn=coder_fn,
    )

    assert result.success is False
    assert call_count == 2


def test_build_retry_context_includes_error() -> None:
    """Retry context must contain the error output and attempt number."""
    handler = RetryHandler()
    ctx = handler.build_retry_context(
        original_task="Implement auth module",
        error_output="TypeError: expected str, got int",
        retry_number=2,
    )

    assert "RETRY ATTEMPT 2" in ctx
    assert "TypeError: expected str, got int" in ctx
    assert "Implement auth module" in ctx
    assert "targeted" in ctx.lower() or "SPECIFIC" in ctx
