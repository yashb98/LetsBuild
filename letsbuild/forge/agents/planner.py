"""Planner agent — decomposes a ProjectSpec into a TaskGraph."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

from letsbuild.forge.base_agent import BaseAgent
from letsbuild.forge.tools import LIST_DIRECTORY_TOOL, READ_FILE_TOOL
from letsbuild.models.forge_models import (
    AgentOutput,
    AgentRole,
    SwarmTopology,
    Task,
    TaskGraph,
)

if TYPE_CHECKING:
    from letsbuild.harness.llm_client import LLMClient
    from letsbuild.models.architect_models import ProjectSpec

logger = structlog.get_logger()


class PlannerAgent(BaseAgent):
    """Decomposes a ProjectSpec into a TaskGraph with ordered tasks and dependencies.

    The Planner operates in read-only sandbox mode with only ``read_file``
    and ``list_directory`` tools.  When no LLM client is available it falls
    back to :meth:`_plan_heuristic`.
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        super().__init__(
            role=AgentRole.PLANNER,
            llm_client=llm_client,
            model=None,
        )

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def system_prompt(self) -> str:
        """Return the system prompt for the Planner agent."""
        return (
            "You are the Planner agent in the LetsBuild Code Forge.\n\n"
            "Your job is to decompose a ProjectSpec into a TaskGraph — an ordered "
            "list of implementation tasks with explicit dependencies.\n\n"
            "Rules:\n"
            "1. Create one Task per feature in the ProjectSpec.\n"
            "2. Each Task must have a unique task_id, module_name, description, "
            "estimated_complexity (1-10), and a list of dependency task_ids.\n"
            "3. Respect feature dependency order: if feature B depends on feature A, "
            "task B must list task A's ID in its dependencies.\n"
            "4. Use HIERARCHICAL topology unless the project requires tight coupling "
            "(MESH) or strict sequential ordering (SEQUENTIAL).\n"
            "5. Return the complete TaskGraph using the produce_task_graph tool.\n"
            "6. You may use read_file and list_directory to inspect the sandbox "
            "workspace for existing files before planning."
        )

    def tools(self) -> list[dict[str, object]]:
        """Return read-only sandbox tools for the Planner."""
        return [READ_FILE_TOOL, LIST_DIRECTORY_TOOL]

    async def process_result(self, response: object) -> AgentOutput:
        """Extract a TaskGraph from the LLM response.

        The base ``run`` method wraps the return value, so we return a
        minimal successful AgentOutput here.
        """
        return AgentOutput(
            agent_role=AgentRole.PLANNER,
            task_id="",
            success=True,
            output_modules=[],
            tokens_used=0,
            execution_time_seconds=0.0,
            retry_count=0,
        )

    # ------------------------------------------------------------------
    # Public convenience API
    # ------------------------------------------------------------------

    async def plan(self, project_spec: ProjectSpec) -> TaskGraph:
        """Decompose *project_spec* into a :class:`TaskGraph`.

        If no LLM client is configured the heuristic fallback is used.
        """
        if self.llm_client is None:
            logger.info("planner.heuristic_fallback")
            return self._plan_heuristic(project_spec)

        context = (
            f"Project: {project_spec.project_name}\n"
            f"One-liner: {project_spec.one_liner}\n"
            f"Tech stack: {', '.join(project_spec.tech_stack)}\n\n"
            "Features:\n"
        )
        for idx, feat in enumerate(project_spec.feature_specs, 1):
            context += (
                f"  {idx}. {feat.feature_name} — {feat.description} "
                f"(complexity {feat.estimated_complexity}, "
                f"module: {feat.module_path}, "
                f"depends on: {feat.dependencies})\n"
            )
        context += "\nDecompose this into a TaskGraph."

        await self.run(context)
        # In a full implementation the LLM would return a structured TaskGraph
        # via tool_use.  For now, fall back to heuristic as a safe default.
        return self._plan_heuristic(project_spec)

    # ------------------------------------------------------------------
    # Heuristic fallback
    # ------------------------------------------------------------------

    def _plan_heuristic(self, spec: ProjectSpec) -> TaskGraph:
        """Create a TaskGraph from *spec* without an LLM call.

        Creates one :class:`Task` per ``FeatureSpec``, wiring dependencies
        based on the feature's declared dependency list.
        """
        # Map feature_name → task_id so we can wire deps.
        feature_to_task_id: dict[str, str] = {}
        tasks: list[Task] = []

        for feat in spec.feature_specs:
            task_id = str(uuid.uuid4())
            feature_to_task_id[feat.feature_name] = task_id

        total_complexity = 0
        for feat in spec.feature_specs:
            task_id = feature_to_task_id[feat.feature_name]
            dep_ids = [
                feature_to_task_id[dep] for dep in feat.dependencies if dep in feature_to_task_id
            ]
            task = Task(
                task_id=task_id,
                module_name=feat.module_path,
                description=feat.description,
                dependencies=dep_ids,
                assigned_agent=AgentRole.CODER,
                estimated_complexity=feat.estimated_complexity,
            )
            tasks.append(task)
            total_complexity += feat.estimated_complexity

        return TaskGraph(
            tasks=tasks,
            topology=SwarmTopology.HIERARCHICAL,
            total_estimated_complexity=total_complexity,
        )
