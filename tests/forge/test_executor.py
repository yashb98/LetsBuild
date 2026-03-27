"""Tests for letsbuild.forge.executor — ForgeExecutor."""

from __future__ import annotations

import pytest

from letsbuild.forge.executor import ForgeExecutor
from letsbuild.models.forge_models import Task, TaskGraph, TaskStatus


def _make_task(
    task_id: str,
    module_name: str,
    *,
    dependencies: list[str] | None = None,
    complexity: int = 3,
) -> Task:
    return Task(
        task_id=task_id,
        module_name=module_name,
        description=f"Build {module_name}",
        dependencies=dependencies or [],
        estimated_complexity=complexity,
    )


def _make_graph(tasks: list[Task]) -> TaskGraph:
    total = sum(t.estimated_complexity for t in tasks)
    return TaskGraph(tasks=tasks, total_estimated_complexity=total)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_tasks_sequential() -> None:
    """Two dependent tasks must run in order: A then B."""
    task_a = _make_task("a", "module_a")
    task_b = _make_task("b", "module_b", dependencies=["a"])
    graph = _make_graph([task_a, task_b])

    executor = ForgeExecutor()
    results = await executor.execute_tasks(graph, project_context="test project")

    assert len(results) == 2
    # First result should be task A, second task B
    assert results[0].task_id == "a"
    assert results[1].task_id == "b"
    assert all(r.success for r in results)


@pytest.mark.asyncio
async def test_execute_tasks_parallel() -> None:
    """Two independent tasks should run concurrently via asyncio.gather."""
    task_a = _make_task("a", "module_a")
    task_b = _make_task("b", "module_b")
    graph = _make_graph([task_a, task_b])

    executor = ForgeExecutor()
    results = await executor.execute_tasks(graph, project_context="test project")

    assert len(results) == 2
    task_ids = {r.task_id for r in results}
    assert task_ids == {"a", "b"}
    assert all(r.success for r in results)


def test_get_ready_tasks() -> None:
    """_get_ready_tasks returns only tasks whose deps are fully met."""
    task_a = _make_task("a", "module_a")
    task_b = _make_task("b", "module_b", dependencies=["a"])
    task_c = _make_task("c", "module_c")
    graph = _make_graph([task_a, task_b, task_c])

    # Nothing completed yet — only A and C are ready (no deps).
    ready = ForgeExecutor._get_ready_tasks(graph, completed=set())
    ready_ids = {t.task_id for t in ready}
    assert ready_ids == {"a", "c"}

    # After A completes — B becomes ready.
    task_a.status = TaskStatus.COMPLETED
    ready = ForgeExecutor._get_ready_tasks(graph, completed={"a"})
    ready_ids = {t.task_id for t in ready}
    assert ready_ids == {"b", "c"}


@pytest.mark.asyncio
async def test_task_status_updated() -> None:
    """Task status transitions from PENDING to COMPLETED after execution."""
    task_a = _make_task("a", "module_a")
    graph = _make_graph([task_a])

    assert task_a.status == TaskStatus.PENDING

    executor = ForgeExecutor()
    results = await executor.execute_tasks(graph, project_context="ctx")

    assert task_a.status == TaskStatus.COMPLETED
    assert len(results) == 1
    assert results[0].success is True
