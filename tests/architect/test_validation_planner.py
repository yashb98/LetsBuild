"""Tests for ValidationPlanner — sandbox validation plan generation."""

from __future__ import annotations

from letsbuild.architect.validation_planner import ValidationPlanner
from letsbuild.models.config_models import SkillConfig


def _make_planner() -> ValidationPlanner:
    return ValidationPlanner()


# ------------------------------------------------------------------
# Stack-specific generation
# ------------------------------------------------------------------


def test_generate_python_stack() -> None:
    """Python tech stack produces pip/pytest/ruff/mypy commands."""
    planner = _make_planner()
    plan = planner.generate(["Python", "FastAPI", "PostgreSQL"])

    cmds = [c.command for c in plan.commands]
    assert any("pip install" in c for c in cmds)
    assert any("pytest" in c for c in cmds)
    assert any("ruff check" in c for c in cmds)
    assert any("mypy" in c for c in cmds)


def test_generate_node_stack() -> None:
    """Node tech stack produces npm install/test/lint/build commands."""
    planner = _make_planner()
    plan = planner.generate(["React", "Next.js", "TypeScript"])

    cmds = [c.command for c in plan.commands]
    assert any("npm install" in c for c in cmds)
    assert any("npm test" in c for c in cmds)
    assert any("npm run lint" in c for c in cmds)
    assert any("npm run build" in c for c in cmds)


def test_generate_go_stack() -> None:
    """Go tech stack produces go build/test/vet commands."""
    planner = _make_planner()
    plan = planner.generate(["Go", "Gin", "gRPC"])

    cmds = [c.command for c in plan.commands]
    assert any("go build" in c for c in cmds)
    assert any("go test" in c for c in cmds)
    assert any("go vet" in c for c in cmds)


def test_generate_minimum_three_commands() -> None:
    """Every plan has at least 3 commands, even for unknown stacks."""
    planner = _make_planner()
    plan = planner.generate(["SomeObscureTech"])

    assert len(plan.commands) >= 3


def test_generate_with_skill_config() -> None:
    """Skill config provides extra_packages from primary tech stacks."""
    planner = _make_planner()
    skill = SkillConfig(
        name="fullstack",
        display_name="Full-Stack Web Application",
        category="project",
        role_categories=["full_stack_engineer"],
        seniority_range=["junior", "mid", "senior"],
        tech_stacks_primary=["React", "FastAPI", "PostgreSQL"],
        tech_stacks_alternatives=["Vue", "Django"],
        complexity_range=[3, 8],
        estimated_loc=[800, 3000],
    )
    plan = planner.generate(["Python", "FastAPI"], skill_config=skill)

    assert plan.extra_packages == ["React", "FastAPI", "PostgreSQL"]


def test_detect_stack_type_python() -> None:
    """Detection correctly identifies Python stacks."""
    planner = _make_planner()
    assert planner._detect_stack_type(["Python", "Django"]) == "python"
    assert planner._detect_stack_type(["FastAPI"]) == "python"
    assert planner._detect_stack_type(["flask", "redis"]) == "python"


def test_detect_stack_type_node() -> None:
    """Detection correctly identifies Node.js stacks."""
    planner = _make_planner()
    assert planner._detect_stack_type(["React", "TypeScript"]) == "node"
    assert planner._detect_stack_type(["Next.js"]) == "node"
    assert planner._detect_stack_type(["express", "mongodb"]) == "node"


def test_default_base_image() -> None:
    """Default base image is letsbuild/sandbox:latest."""
    planner = _make_planner()
    plan = planner.generate(["Python"])

    assert plan.base_image == "letsbuild/sandbox:latest"
