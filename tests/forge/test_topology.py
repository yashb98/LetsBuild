"""Tests for the TopologySelector in the Code Forge."""

from __future__ import annotations

from letsbuild.forge.topology import TopologySelector
from letsbuild.models.architect_models import (
    FeatureSpec,
    ProjectSpec,
    SandboxValidationCommand,
    SandboxValidationPlan,
)
from letsbuild.models.forge_models import AgentRole, SwarmTopology, Task

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALIDATION_PLAN = SandboxValidationPlan(
    commands=[
        SandboxValidationCommand(command="echo ok", description="smoke"),
        SandboxValidationCommand(command="echo ok2", description="smoke2"),
        SandboxValidationCommand(command="echo ok3", description="smoke3"),
    ],
)


def _make_project_spec(
    num_features: int = 5,
    *,
    with_deps: bool = False,
) -> ProjectSpec:
    """Create a ProjectSpec with *num_features* features."""
    features = []
    for i in range(num_features):
        deps = [f"feature_{i - 1}"] if (with_deps and i > 0) else []
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
        one_liner="A test project.",
        tech_stack=["python"],
        file_tree=[],
        feature_specs=features,
        sandbox_validation_plan=_VALIDATION_PLAN,
        skill_name="test-skill",
        complexity_score=5.0,
        estimated_loc=500,
        seniority_target="mid",
    )


def _make_task(
    name: str = "task_0",
    role: AgentRole = AgentRole.CODER,
) -> Task:
    """Create a minimal Task for testing."""
    return Task(
        module_name=name,
        description=f"Implement {name}",
        assigned_agent=role,
        estimated_complexity=3,
    )


# ---------------------------------------------------------------------------
# Tests — select()
# ---------------------------------------------------------------------------


def test_select_sequential_few_features() -> None:
    """Projects with <= 3 features should use SEQUENTIAL topology."""
    selector = TopologySelector()
    spec = _make_project_spec(num_features=2)
    assert selector.select(spec) == SwarmTopology.SEQUENTIAL

    spec3 = _make_project_spec(num_features=3)
    assert selector.select(spec3) == SwarmTopology.SEQUENTIAL


def test_select_hierarchical_default() -> None:
    """Projects with 4-10 independent features should use HIERARCHICAL."""
    selector = TopologySelector()
    spec = _make_project_spec(num_features=5, with_deps=False)
    assert selector.select(spec) == SwarmTopology.HIERARCHICAL


def test_select_mesh_topology_from_spec() -> None:
    """Projects with cross-dependencies should use MESH."""
    selector = TopologySelector()
    spec = _make_project_spec(num_features=5, with_deps=True)
    assert selector.select(spec) == SwarmTopology.MESH


def test_select_ring_many_features() -> None:
    """Projects with > 10 features should use RING."""
    selector = TopologySelector()
    spec = _make_project_spec(num_features=12)
    assert selector.select(spec) == SwarmTopology.RING


# ---------------------------------------------------------------------------
# Tests — get_execution_order()
# ---------------------------------------------------------------------------


def test_get_execution_order_sequential() -> None:
    """SEQUENTIAL topology puts each task in its own batch."""
    selector = TopologySelector()
    tasks = [_make_task("t0"), _make_task("t1"), _make_task("t2")]
    batches = selector.get_execution_order(SwarmTopology.SEQUENTIAL, tasks)

    assert len(batches) == 3
    for batch in batches:
        assert len(batch) == 1


def test_get_execution_order_mesh() -> None:
    """MESH topology puts all tasks in a single batch."""
    selector = TopologySelector()
    tasks = [_make_task("t0"), _make_task("t1"), _make_task("t2")]
    batches = selector.get_execution_order(SwarmTopology.MESH, tasks)

    assert len(batches) == 1
    assert len(batches[0]) == 3


def test_get_execution_order_hierarchical() -> None:
    """HIERARCHICAL topology groups tasks by agent role in pipeline order."""
    selector = TopologySelector()
    tasks = [
        _make_task("plan", role=AgentRole.PLANNER),
        _make_task("code_a", role=AgentRole.CODER),
        _make_task("code_b", role=AgentRole.CODER),
        _make_task("test", role=AgentRole.TESTER),
        _make_task("integrate", role=AgentRole.INTEGRATOR),
    ]
    batches = selector.get_execution_order(SwarmTopology.HIERARCHICAL, tasks)

    # Should have 4 non-empty batches (planner, coder, tester, integrator).
    assert len(batches) == 4
    assert batches[0][0].module_name == "plan"
    assert len(batches[1]) == 2  # two coder tasks
    assert batches[2][0].module_name == "test"
    assert batches[3][0].module_name == "integrate"


def test_get_execution_order_empty_tasks() -> None:
    """Empty task list returns empty batches."""
    selector = TopologySelector()
    batches = selector.get_execution_order(SwarmTopology.MESH, [])
    assert batches == []
