"""Parallel task executor for Code Forge agent swarm."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from letsbuild.models.forge_models import AgentOutput, AgentRole, TaskStatus

if TYPE_CHECKING:
    from letsbuild.harness.llm_client import LLMClient
    from letsbuild.models.forge_models import Task, TaskGraph

logger = structlog.get_logger()


class _CoderAgent:
    """Lightweight wrapper that produces an AgentOutput for a single task.

    When an ``LLMClient`` is provided the full agentic loop would run; without
    one a deterministic heuristic is used instead (useful for tests and dry-runs).
    """

    def __init__(
        self, llm_client: LLMClient | None = None, workspace_path: str | None = None
    ) -> None:
        self._llm_client = llm_client
        self._workspace_path = workspace_path
        self._log = logger.bind(agent_role=AgentRole.CODER)

    async def code(self, task: Task, project_context: str) -> AgentOutput:
        """Generate code for *task* using an LLM or heuristic fallback."""
        if self._llm_client is None:
            return self._code_heuristic(task)

        # Full LLM path would delegate to BaseAgent.run here.
        # Placeholder until the full CoderAgent(BaseAgent) is wired up.
        return self._code_heuristic(task)

    @staticmethod
    def _code_heuristic(task: Task) -> AgentOutput:
        from letsbuild.models.forge_models import CodeModule

        module = CodeModule(
            module_path=f"{task.module_name}.py",
            content=f"# Auto-generated module for {task.module_name}\n",
            language="python",
            loc=1,
        )
        return AgentOutput(
            agent_role=AgentRole.CODER,
            task_id=task.task_id,
            success=True,
            output_modules=[module],
            tokens_used=0,
            execution_time_seconds=0.0,
        )


class ForgeExecutor:
    """Execute a ``TaskGraph`` respecting dependency order.

    Independent tasks (no unmet dependencies) are dispatched in parallel via
    ``asyncio.gather``.  Dependent tasks wait for their prerequisites to
    complete before starting.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        workspace_path: str | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._workspace_path = workspace_path
        self._log = logger.bind(component="forge_executor")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_tasks(
        self,
        task_graph: TaskGraph,
        project_context: str,
    ) -> list[AgentOutput]:
        """Run every task in *task_graph* and return all ``AgentOutput`` s."""
        completed: set[str] = set()
        results: list[AgentOutput] = []

        while True:
            ready = self._get_ready_tasks(task_graph, completed)
            if not ready:
                break

            # Mark ready tasks as in-progress.
            for task in ready:
                task.status = TaskStatus.IN_PROGRESS

            # Fire all independent tasks in parallel.
            coros = [self._execute_task(t, project_context) for t in ready]
            batch_results = await asyncio.gather(*coros, return_exceptions=True)

            for task, result in zip(ready, batch_results, strict=True):
                if isinstance(result, BaseException):
                    task.status = TaskStatus.FAILED
                    self._log.error(
                        "task_failed",
                        task_id=task.task_id,
                        error=str(result),
                    )
                    results.append(
                        AgentOutput(
                            agent_role=AgentRole.CODER,
                            task_id=task.task_id,
                            success=False,
                            output_modules=[],
                            tokens_used=0,
                            execution_time_seconds=0.0,
                            error=None,
                        )
                    )
                else:
                    task.status = TaskStatus.COMPLETED
                    results.append(result)

                completed.add(task.task_id)

        return results

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _execute_task(self, task: Task, project_context: str) -> AgentOutput:
        """Create a coder agent and execute a single *task*."""
        self._log.info("task_start", task_id=task.task_id, module=task.module_name)
        coder = _CoderAgent(
            llm_client=self._llm_client,
            workspace_path=self._workspace_path,
        )
        output = await coder.code(task, project_context)
        self._log.info(
            "task_complete",
            task_id=task.task_id,
            success=output.success,
        )
        return output

    @staticmethod
    def _get_ready_tasks(graph: TaskGraph, completed: set[str]) -> list[Task]:
        """Return tasks whose dependencies are all satisfied and status is PENDING."""
        return [
            t
            for t in graph.tasks
            if t.status == TaskStatus.PENDING and all(d in completed for d in t.dependencies)
        ]
