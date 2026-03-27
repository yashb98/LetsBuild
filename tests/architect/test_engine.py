"""Tests for the Project Architect engine (Layer 4)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from letsbuild.architect.engine import ProjectArchitect
from letsbuild.models.architect_models import (
    ADR,
    ADRStatus,
    FeatureSpec,
    ProjectSpec,
    SandboxValidationCommand,
    SandboxValidationPlan,
)
from letsbuild.models.config_models import SkillConfig
from letsbuild.models.intake_models import (
    JDAnalysis,
    RoleCategory,
    SeniorityLevel,
    Skill,
    TechStack,
)


@pytest.fixture()
def sample_jd() -> JDAnalysis:
    """Minimal JDAnalysis for testing."""
    return JDAnalysis(
        role_title="Senior Backend Engineer",
        role_category=RoleCategory.BACKEND,
        seniority=SeniorityLevel.SENIOR,
        company_name="Acme Corp",
        required_skills=[
            Skill(name="Python", category="language", is_primary=True),
            Skill(name="FastAPI", category="framework", is_primary=True),
        ],
        tech_stack=TechStack(
            languages=["python"],
            frameworks=["fastapi"],
            databases=["postgresql"],
        ),
        domain_keywords=["fintech", "real-time"],
        key_responsibilities=[
            "Design and build REST APIs",
            "Implement authentication and authorisation",
            "Optimise database queries for performance",
            "Write comprehensive test suites",
        ],
        raw_text="Senior Backend Engineer at Acme Corp...",
    )


@pytest.fixture()
def sample_skill() -> SkillConfig:
    """Minimal SkillConfig for testing."""
    return SkillConfig(
        name="backend-api",
        display_name="Backend API Service",
        category="project",
        role_categories=["backend_engineer"],
        seniority_range=["junior", "mid", "senior"],
        tech_stacks_primary=["Python", "FastAPI"],
        complexity_range=[3, 8],
        estimated_loc=[800, 2500],
        topology="hierarchical",
    )


def test_design_heuristic_returns_project_spec(sample_jd: JDAnalysis) -> None:
    """Heuristic design returns a valid ProjectSpec instance."""
    architect = ProjectArchitect(llm_client=None)
    spec = architect._design_heuristic(sample_jd, None, None, None)
    assert isinstance(spec, ProjectSpec)
    assert spec.project_name
    assert spec.one_liner
    assert spec.seniority_target == "senior"


def test_design_heuristic_has_file_tree(sample_jd: JDAnalysis) -> None:
    """Heuristic design produces a non-empty file tree."""
    architect = ProjectArchitect(llm_client=None)
    spec = architect._design_heuristic(sample_jd, None, None, None)
    assert len(spec.file_tree) > 0
    paths = [node.path for node in spec.file_tree]
    assert any("src" in p for p in paths)


def test_design_heuristic_has_features(sample_jd: JDAnalysis) -> None:
    """Heuristic design produces non-empty feature_specs from key responsibilities."""
    architect = ProjectArchitect(llm_client=None)
    spec = architect._design_heuristic(sample_jd, None, None, None)
    assert len(spec.feature_specs) > 0
    assert len(spec.feature_specs) <= 5
    for feat in spec.feature_specs:
        assert isinstance(feat, FeatureSpec)
        assert feat.feature_name
        assert feat.description


def test_design_heuristic_has_validation_plan(sample_jd: JDAnalysis) -> None:
    """Heuristic design produces a validation plan with at least 3 commands."""
    architect = ProjectArchitect(llm_client=None)
    spec = architect._design_heuristic(sample_jd, None, None, None)
    assert isinstance(spec.sandbox_validation_plan, SandboxValidationPlan)
    assert len(spec.sandbox_validation_plan.commands) >= 3
    for cmd in spec.sandbox_validation_plan.commands:
        assert isinstance(cmd, SandboxValidationCommand)
        assert cmd.command


def test_design_heuristic_has_adrs(sample_jd: JDAnalysis) -> None:
    """Heuristic design produces non-empty ADR list."""
    architect = ProjectArchitect(llm_client=None)
    spec = architect._design_heuristic(sample_jd, None, None, None)
    assert len(spec.adr_list) > 0
    for adr in spec.adr_list:
        assert isinstance(adr, ADR)
        assert adr.title
        assert adr.status in ADRStatus


def test_build_file_tree_python(sample_jd: JDAnalysis) -> None:
    """Python tech stack produces src/, tests/, pyproject.toml."""
    architect = ProjectArchitect(llm_client=None)
    tree = architect._build_file_tree(["python", "fastapi"], "my-api")
    paths = [node.path for node in tree]
    assert "src/" in paths
    assert "tests/" in paths
    assert "pyproject.toml" in paths
    assert "README.md" in paths
    assert "docs/" in paths


def test_build_tool_schema() -> None:
    """Tool schema has required name, description, and input_schema keys."""
    architect = ProjectArchitect(llm_client=None)
    schema = architect._build_tool_schema()
    assert schema["name"] == "design_project"
    assert "description" in schema
    assert isinstance(schema["description"], str)
    assert "input_schema" in schema
    assert isinstance(schema["input_schema"], dict)


@pytest.mark.asyncio()
async def test_design_with_mocked_llm(sample_jd: JDAnalysis) -> None:
    """Design with a mocked LLM client returns a valid ProjectSpec."""
    # Build a valid raw dict that ProjectSpec.model_validate can parse.
    raw_output: dict[str, Any] = {
        "project_name": "fintech-backend-api",
        "one_liner": "A senior-level backend API for fintech.",
        "tech_stack": ["python", "fastapi"],
        "file_tree": [
            {"path": "src/", "is_directory": True},
            {"path": "tests/", "is_directory": True},
        ],
        "feature_specs": [
            {
                "feature_name": "rest_api",
                "description": "REST API endpoints",
                "module_path": "src/api.py",
                "estimated_complexity": 5,
            },
        ],
        "sandbox_validation_plan": {
            "commands": [
                {"command": "pip install -e .", "description": "Install deps."},
                {"command": "pytest tests/ -v", "description": "Run tests."},
                {"command": "ruff check .", "description": "Lint."},
            ],
        },
        "adr_list": [
            {
                "title": "Use FastAPI",
                "status": "accepted",
                "context": "Need async API framework.",
                "decision": "Use FastAPI.",
                "consequences": "Good async support.",
            },
        ],
        "skill_name": "backend-api",
        "complexity_score": 7.0,
        "estimated_loc": 2500,
        "seniority_target": "senior",
    }

    mock_client = AsyncMock()
    mock_client.extract_structured = AsyncMock(return_value=raw_output)

    architect = ProjectArchitect(llm_client=mock_client)
    spec = await architect.design(sample_jd)

    assert isinstance(spec, ProjectSpec)
    assert spec.project_name == "fintech-backend-api"
    mock_client.extract_structured.assert_awaited_once()
