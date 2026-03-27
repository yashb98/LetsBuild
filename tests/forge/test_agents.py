"""Tests for Planner and Coder agents in the Code Forge."""

from __future__ import annotations

import pytest

from letsbuild.forge.agents.coder import CoderAgent
from letsbuild.forge.agents.planner import PlannerAgent
from letsbuild.models.architect_models import (
    FeatureSpec,
    ProjectSpec,
    SandboxValidationCommand,
    SandboxValidationPlan,
)
from letsbuild.models.forge_models import (
    AgentRole,
    SwarmTopology,
    Task,
    TaskGraph,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project_spec(num_features: int = 3) -> ProjectSpec:
    """Create a minimal ProjectSpec for testing."""
    features = []
    for i in range(num_features):
        deps = [f"feature_{i - 1}"] if i > 0 else []
        features.append(
            FeatureSpec(
                feature_name=f"feature_{i}",
                description=f"Implement feature {i}",
                module_path=f"src/feature_{i}.py",
                dependencies=deps,
                estimated_complexity=3,
            )
        )
    return ProjectSpec(
        project_name="test-project",
        one_liner="A test project for unit tests.",
        tech_stack=["python", "fastapi"],
        file_tree=[],
        feature_specs=features,
        sandbox_validation_plan=SandboxValidationPlan(
            commands=[
                SandboxValidationCommand(command="echo ok", description="smoke"),
                SandboxValidationCommand(command="echo ok2", description="smoke2"),
                SandboxValidationCommand(command="echo ok3", description="smoke3"),
            ],
        ),
        skill_name="test-skill",
        complexity_score=5.0,
        estimated_loc=500,
        seniority_target="mid",
    )


def _make_task() -> Task:
    """Create a minimal Task for testing."""
    return Task(
        module_name="src/utils.py",
        description="Implement utility functions for data processing.",
        estimated_complexity=4,
        assigned_agent=AgentRole.CODER,
    )


# ---------------------------------------------------------------------------
# Planner tests
# ---------------------------------------------------------------------------


class TestPlannerAgent:
    """Tests for the PlannerAgent."""

    def test_planner_has_correct_tools(self) -> None:
        """Planner should only have read_file and list_directory."""
        planner = PlannerAgent()
        tool_names = [str(t["name"]) for t in planner.tools()]
        assert tool_names == ["read_file", "list_directory"]

    def test_planner_heuristic_returns_task_graph(self) -> None:
        """Heuristic fallback should return a valid TaskGraph."""
        planner = PlannerAgent()
        spec = _make_project_spec(num_features=2)
        result = planner._plan_heuristic(spec)

        assert isinstance(result, TaskGraph)
        assert result.topology == SwarmTopology.HIERARCHICAL
        assert result.total_estimated_complexity == 6  # 2 features * complexity 3

    def test_planner_tasks_match_features(self) -> None:
        """Heuristic should produce one task per feature with correct deps."""
        planner = PlannerAgent()
        spec = _make_project_spec(num_features=3)
        result = planner._plan_heuristic(spec)

        assert len(result.tasks) == 3
        # First task has no deps; second depends on first; third depends on second.
        assert result.tasks[0].dependencies == []
        assert result.tasks[1].dependencies == [result.tasks[0].task_id]
        assert result.tasks[2].dependencies == [result.tasks[1].task_id]

        # Module names match feature module paths.
        for task, feat in zip(result.tasks, spec.feature_specs, strict=True):
            assert task.module_name == feat.module_path

    @pytest.mark.asyncio
    async def test_planner_plan_uses_heuristic_without_client(self) -> None:
        """plan() should use heuristic when no LLM client is set."""
        planner = PlannerAgent()
        spec = _make_project_spec(num_features=2)
        result = await planner.plan(spec)

        assert isinstance(result, TaskGraph)
        assert len(result.tasks) == 2


# ---------------------------------------------------------------------------
# Coder tests
# ---------------------------------------------------------------------------


class TestCoderAgent:
    """Tests for the CoderAgent."""

    def test_coder_has_correct_tools(self) -> None:
        """Coder should have exactly 4 tools: write_file, bash_execute, install_package, read_file."""
        coder = CoderAgent()
        tool_names = [str(t["name"]) for t in coder.tools()]
        assert tool_names == ["write_file", "bash_execute", "install_package", "read_file"]
        assert len(tool_names) == 4

    def test_coder_heuristic_returns_agent_output(self) -> None:
        """Heuristic fallback should return a valid AgentOutput."""
        coder = CoderAgent()
        task = _make_task()
        result = coder._code_heuristic(task)

        assert result.agent_role == AgentRole.CODER
        assert result.success is True
        assert result.task_id == task.task_id

    def test_coder_output_has_code_module(self) -> None:
        """Heuristic output should contain at least one CodeModule."""
        coder = CoderAgent()
        task = _make_task()
        result = coder._code_heuristic(task)

        assert len(result.output_modules) == 1
        module = result.output_modules[0]
        assert module.module_path == "src/utils.py"
        assert module.language == "python"
        assert module.loc > 0
        assert "utils" in module.content

    @pytest.mark.asyncio
    async def test_coder_code_uses_heuristic_without_client(self) -> None:
        """code() should use heuristic when no LLM client is set."""
        coder = CoderAgent()
        task = _make_task()
        result = await coder.code(task, "Test project context")

        assert result.success is True
        assert len(result.output_modules) == 1

    def test_coder_workspace_path_default(self) -> None:
        """Default workspace path should be /mnt/workspace."""
        coder = CoderAgent()
        assert coder.workspace_path == "/mnt/workspace"

    def test_coder_workspace_path_custom(self) -> None:
        """Custom workspace path should be preserved."""
        coder = CoderAgent(workspace_path="/tmp/test")
        assert coder.workspace_path == "/tmp/test"
