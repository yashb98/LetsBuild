"""Shared fixtures for publisher layer tests."""

from __future__ import annotations

import pytest

from letsbuild.models.architect_models import (
    ADR,
    ADRStatus,
    FeatureSpec,
    FileTreeNode,
    ProjectSpec,
    SandboxValidationCommand,
    SandboxValidationPlan,
)
from letsbuild.models.forge_models import CodeModule, ForgeOutput, ReviewVerdict, SwarmTopology

# ---------------------------------------------------------------------------
# ProjectSpec fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_validation_plan() -> SandboxValidationPlan:
    """Minimal but valid SandboxValidationPlan (min 3 commands required)."""
    return SandboxValidationPlan(
        commands=[
            SandboxValidationCommand(
                command="pip install -e .",
                description="Install package",
            ),
            SandboxValidationCommand(
                command="pytest tests/ -v",
                description="Run tests",
            ),
            SandboxValidationCommand(
                command="ruff check .",
                description="Lint code",
            ),
        ],
        base_image="letsbuild/sandbox:latest",
    )


@pytest.fixture
def sample_adr() -> ADR:
    """A minimal ADR for testing."""
    return ADR(
        title="Use FastAPI for REST API",
        status=ADRStatus.ACCEPTED,
        context="Need a high-performance async Python framework.",
        decision="We will use FastAPI with Pydantic v2 for input validation.",
        consequences="Team must learn FastAPI conventions; gains async support.",
    )


@pytest.fixture
def sample_project_spec(
    sample_validation_plan: SandboxValidationPlan,
    sample_adr: ADR,
) -> ProjectSpec:
    """Minimal but fully valid ProjectSpec."""
    return ProjectSpec(
        project_name="MyFastAPI Project",
        one_liner="A high-performance REST API built with FastAPI and Pydantic.",
        tech_stack=["python", "fastapi", "pydantic"],
        file_tree=[
            FileTreeNode(
                path="src",
                is_directory=True,
                description="Source code",
                children=[
                    FileTreeNode(path="src/main.py", is_directory=False, description="Entry point"),
                    FileTreeNode(path="src/api.py", is_directory=False),
                ],
            ),
            FileTreeNode(path="tests", is_directory=True),
            FileTreeNode(path="pyproject.toml", is_directory=False),
        ],
        feature_specs=[
            FeatureSpec(
                feature_name="REST API",
                description="Core REST API endpoints.",
                module_path="src/api.py",
                estimated_complexity=5,
                acceptance_criteria=["GET /health returns 200", "POST /items creates item"],
            ),
        ],
        sandbox_validation_plan=sample_validation_plan,
        adr_list=[sample_adr],
        skill_name="fullstack",
        complexity_score=5.0,
        estimated_loc=500,
        seniority_target="mid",
    )


# ---------------------------------------------------------------------------
# ForgeOutput fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_code_modules() -> list[CodeModule]:
    """A small set of code modules across different phases."""
    return [
        CodeModule(
            module_path="src/main.py",
            content='"""Main entry point."""\nfrom fastapi import FastAPI\napp = FastAPI()\n',
            language="python",
            loc=3,
        ),
        CodeModule(
            module_path="src/api.py",
            content='"""API routes."""\nfrom fastapi import APIRouter\nrouter = APIRouter()\n',
            language="python",
            loc=3,
        ),
        CodeModule(
            module_path="tests/test_api.py",
            content='"""Tests for API."""\nimport pytest\n\ndef test_health():\n    pass\n',
            language="python",
            loc=5,
        ),
        CodeModule(
            module_path=".github/workflows/ci.yml",
            content="name: CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n",
            language="yaml",
            loc=5,
        ),
        CodeModule(
            module_path="pyproject.toml",
            content='[project]\nname = "my-fastapi-project"\nversion = "0.1.0"\n',
            language="toml",
            loc=3,
        ),
    ]


@pytest.fixture
def sample_forge_output(sample_code_modules: list[CodeModule]) -> ForgeOutput:
    """A ForgeOutput with passing tests and review verdict."""
    return ForgeOutput(
        code_modules=sample_code_modules,
        test_results={
            "pip install -e .": True,
            "pytest tests/ -v": True,
            "ruff check .": True,
        },
        review_verdict=ReviewVerdict.PASS,
        review_comments=["Code is clean and well-structured."],
        quality_score=85.0,
        total_tokens_used=10000,
        total_retries=0,
        topology_used=SwarmTopology.HIERARCHICAL,
    )
