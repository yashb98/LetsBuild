"""Shared fixtures for integration tests.

Provides:
- Full PipelineState factory with all fields populated
- Mocked Anthropic client
- Temporary SQLite-backed MemoryStorage
- HNSWIndex setup
- Full pipeline controller factory (L1/L2 mocked)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from letsbuild.memory.hnsw_index import HNSWIndex
from letsbuild.memory.storage import MemoryStorage
from letsbuild.models.architect_models import (
    FeatureSpec,
    FileTreeNode,
    ProjectSpec,
    SandboxValidationCommand,
    SandboxValidationPlan,
)
from letsbuild.models.content_models import ContentFormat, ContentOutput
from letsbuild.models.forge_models import (
    AgentOutput,
    AgentRole,
    CodeModule,
    ForgeOutput,
    ReviewVerdict,
    SwarmTopology,
)
from letsbuild.models.intake_models import (
    JDAnalysis,
    RoleCategory,
    SeniorityLevel,
    Skill,
    TechStack,
)
from letsbuild.models.intelligence_models import (
    CompanyProfile,
    DataSource,
    ResearchResult,
    SubAgentResult,
    SubAgentType,
)
from letsbuild.models.matcher_models import (
    DimensionScore,
    GapAnalysis,
    GapCategory,
    GapItem,
    MatchDimension,
    MatchScore,
)
from letsbuild.models.publisher_models import (
    CommitEntry,
    CommitPhase,
    CommitPlan,
    PublishResult,
    RepoConfig,
)
from letsbuild.models.shared import GateResult, PipelineMetrics
from letsbuild.pipeline.controller import PipelineController
from letsbuild.pipeline.state import PipelineState
from letsbuild.publisher.engine import PublisherEngine

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RAW_JD_TEXT = "Senior Full-Stack Engineer at Acme Corp — Python, React, FastAPI, PostgreSQL"
_FAKE_TOKEN = "ghp_fake_integration_token"
_FAKE_OWNER = "testuser"
_FAKE_REPO_URL = "https://github.com/testuser/senior-full-stack-engineer-acme"


# ---------------------------------------------------------------------------
# Model factories
# ---------------------------------------------------------------------------


def make_jd_analysis(
    *,
    role_title: str = "Senior Full-Stack Engineer",
    role_category: RoleCategory = RoleCategory.FULL_STACK,
    seniority: SeniorityLevel = SeniorityLevel.SENIOR,
    raw_text: str = _RAW_JD_TEXT,
) -> JDAnalysis:
    """Build a valid JDAnalysis."""
    return JDAnalysis(
        role_title=role_title,
        role_category=role_category,
        seniority=seniority,
        required_skills=[
            Skill(name="python", category="languages", confidence=90.0),
            Skill(name="react", category="frameworks", confidence=85.0),
            Skill(name="fastapi", category="frameworks", confidence=80.0),
        ],
        tech_stack=TechStack(
            languages=["python", "typescript"],
            frameworks=["react", "fastapi"],
            databases=["postgresql"],
        ),
        domain_keywords=["fintech", "saas"],
        key_responsibilities=[
            "Build REST APIs with FastAPI",
            "Design React components",
            "Manage PostgreSQL schemas",
        ],
        raw_text=raw_text,
    )


def make_company_profile() -> CompanyProfile:
    """Build a minimal CompanyProfile."""
    return CompanyProfile(
        company_name="Acme Corp",
        industry="fintech",
        tech_stack_signals=["python", "react", "fastapi", "postgresql"],
        confidence_score=75.0,
        data_sources=[
            DataSource(
                name="Acme Corp GitHub",
                url="https://github.com/acmecorp",
                source_type="github",
                reliability_score=90.0,
            ),
            DataSource(
                name="Acme Corp Website",
                url="https://acmecorp.com",
                source_type="website",
                reliability_score=85.0,
            ),
        ],
        sub_agent_results=[
            SubAgentResult(
                agent_type=SubAgentType.WEB_PRESENCE,
                success=True,
                execution_time_seconds=0.2,
            ),
        ],
    )


def make_research_result() -> ResearchResult:
    """Build a ResearchResult wrapping the fake company profile."""
    return ResearchResult(
        company_profile=make_company_profile(),
        total_execution_time_seconds=0.5,
        agents_succeeded=5,
        agents_failed=1,
        partial=True,
    )


def make_gap_analysis() -> GapAnalysis:
    """Build a minimal GapAnalysis."""
    return GapAnalysis(
        match_score=MatchScore(
            overall_score=82.0,
            ats_predicted_score=84.0,
            dimension_scores=[
                DimensionScore(
                    dimension=MatchDimension.HARD_SKILLS,
                    score=85.0,
                    weight=0.30,
                    weighted_score=25.5,
                    details="Strong Python and React skills.",
                ),
                DimensionScore(
                    dimension=MatchDimension.TECH_STACK,
                    score=80.0,
                    weight=0.20,
                    weighted_score=16.0,
                    details="FastAPI and PostgreSQL match.",
                ),
                DimensionScore(
                    dimension=MatchDimension.DOMAIN,
                    score=75.0,
                    weight=0.15,
                    weighted_score=11.25,
                    details="Fintech domain experience.",
                ),
                DimensionScore(
                    dimension=MatchDimension.PORTFOLIO,
                    score=70.0,
                    weight=0.15,
                    weighted_score=10.5,
                    details="Several relevant projects.",
                ),
                DimensionScore(
                    dimension=MatchDimension.SENIORITY,
                    score=90.0,
                    weight=0.10,
                    weighted_score=9.0,
                    details="5+ years experience matches senior level.",
                ),
                DimensionScore(
                    dimension=MatchDimension.SOFT_SKILLS,
                    score=70.0,
                    weight=0.10,
                    weighted_score=7.0,
                    details="Good communication signals.",
                ),
            ],
        ),
        strong_matches=[
            GapItem(
                skill_name="python",
                category=GapCategory.STRONG_MATCH,
                confidence=90.0,
                evidence="5 years experience with Python across multiple projects.",
            ),
        ],
        demonstrable_gaps=[],
        learnable_gaps=[],
        hard_gaps=[],
        portfolio_redundancy=[],
        recommended_project_focus=["Build a FastAPI service with async patterns"],
        analysis_summary=(
            "Strong match for this role. Python and React skills align well with requirements."
        ),
    )


def make_project_spec() -> ProjectSpec:
    """Build a minimal ProjectSpec."""
    return ProjectSpec(
        project_name="acme-fintech-api",
        one_liner="A production-grade FastAPI service with React dashboard for Acme Corp",
        tech_stack=["python", "fastapi", "react", "postgresql"],
        feature_specs=[
            FeatureSpec(
                feature_name="REST API",
                description="Core REST API endpoints with FastAPI.",
                module_path="src/api.py",
                estimated_complexity=5,
                acceptance_criteria=["GET /health returns 200", "POST /items creates item"],
            ),
        ],
        file_tree=[
            FileTreeNode(path="src", is_directory=True, description="Source code"),
            FileTreeNode(path="src/main.py", is_directory=False, description="Entry point"),
            FileTreeNode(path="tests", is_directory=True),
            FileTreeNode(path="README.md", is_directory=False),
        ],
        sandbox_validation_plan=SandboxValidationPlan(
            commands=[
                SandboxValidationCommand(
                    command="pip install -e .",
                    description="Install project dependencies",
                ),
                SandboxValidationCommand(
                    command="pytest tests/ -v",
                    description="Run the test suite",
                ),
                SandboxValidationCommand(
                    command="ruff check .",
                    description="Check code style",
                ),
            ],
        ),
        adr_list=[],
        skill_name="fullstack",
        complexity_score=6.0,
        estimated_loc=800,
        seniority_target="senior",
    )


def make_forge_output() -> ForgeOutput:
    """Build a passing ForgeOutput."""
    return ForgeOutput(
        code_modules=[
            CodeModule(
                module_path="src/main.py",
                content='"""Main FastAPI application."""\nfrom fastapi import FastAPI\napp = FastAPI()\n',
                language="python",
                loc=3,
            ),
        ],
        test_results={"test_main": True, "test_api": True},
        review_verdict=ReviewVerdict.PASS,
        review_comments=["Code quality is excellent."],
        quality_score=88.0,
        total_tokens_used=15000,
        total_retries=0,
        topology_used=SwarmTopology.HIERARCHICAL,
        agent_outputs=[
            AgentOutput(
                agent_role=AgentRole.CODER,
                task_id="task-001",
                success=True,
                output_modules=[],
                tokens_used=5000,
                retry_count=0,
                execution_time_seconds=10.0,
            ),
        ],
    )


def make_publish_result() -> PublishResult:
    """Build a minimal PublishResult."""
    return PublishResult(
        repo_url=_FAKE_REPO_URL,
        commit_shas=["abc123", "def456"],
        readme_url=f"{_FAKE_REPO_URL}/blob/main/README.md",
        repo_config=RepoConfig(
            repo_name="acme-fintech-api",
            description="A production-grade FastAPI service",
            topics=["python", "fastapi", "react"],
        ),
        commit_plan=CommitPlan(
            commits=[
                CommitEntry(
                    message="feat: initial scaffold",
                    files=["src/main.py"],
                    phase=CommitPhase.SCAFFOLDING,
                    timestamp_offset_hours=0.0,
                ),
            ],
            total_commits=1,
            spread_days=3,
        ),
    )


def make_full_pipeline_state() -> PipelineState:
    """Build a fully-populated PipelineState with all layer outputs set."""
    state = PipelineState(jd_text=_RAW_JD_TEXT)
    state.jd_analysis = make_jd_analysis()
    state.company_profile = make_company_profile()
    state.gap_analysis = make_gap_analysis()
    state.project_spec = make_project_spec()
    state.forge_output = make_forge_output()
    state.publish_result = make_publish_result()
    state.content_outputs = [
        ContentOutput(
            format=fmt,
            title=f"Test title for {fmt.value}",
            content=f"Test content body for {fmt.value} — acme-fintech-api on GitHub",
            word_count=50,
            target_platform=fmt.value,
            seo_keywords=["python", "fastapi", "acme-fintech-api"],
        )
        for fmt in ContentFormat
    ]
    state.metrics = PipelineMetrics(
        total_duration_seconds=45.0,
        layer_durations={
            "intake": 2.0,
            "intelligence": 8.0,
            "matcher": 1.5,
            "architect": 5.0,
            "forge": 20.0,
            "publisher": 4.0,
            "content": 4.5,
        },
        total_tokens_used=50000,
        total_api_cost_gbp=18.0,
        retries_by_layer={},
        quality_score=88.0,
    )
    return state


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def memory_storage(tmp_path: Any) -> MemoryStorage:  # type: ignore[type-arg]
    """Provide an initialised MemoryStorage backed by a temporary file."""
    db_path = str(tmp_path / "integration_test.db")
    store = MemoryStorage(db_path=db_path)
    async with store:
        yield store


@pytest.fixture
def hnsw_index() -> HNSWIndex:
    """Provide a fresh HNSWIndex instance."""
    return HNSWIndex(dim=128, max_elements=1000)


@pytest.fixture
def full_state() -> PipelineState:
    """Provide a fully-populated PipelineState."""
    return make_full_pipeline_state()


@pytest.fixture
def base_controller() -> PipelineController:
    """Provide a PipelineController with L1/L2 mocked (no publisher)."""
    controller = PipelineController()
    controller.intake_engine.parse_jd = AsyncMock(  # type: ignore[assignment]
        return_value=make_jd_analysis()
    )
    controller.intelligence_coordinator.research_company = AsyncMock(  # type: ignore[assignment]
        return_value=make_research_result()
    )
    return controller


@pytest.fixture
def publisher_engine() -> PublisherEngine:
    """Provide a PublisherEngine with fake credentials."""
    return PublisherEngine(
        github_token=_FAKE_TOKEN,
        owner=_FAKE_OWNER,
        quality_threshold=50.0,
        spread_days=3,
        commit_seed=42,
    )


@pytest.fixture
def controller_with_publisher(publisher_engine: PublisherEngine) -> PipelineController:
    """Provide a PipelineController with publisher engine and L1/L2 mocked."""
    controller = PipelineController(publisher_engine=publisher_engine)
    controller.intake_engine.parse_jd = AsyncMock(  # type: ignore[assignment]
        return_value=make_jd_analysis()
    )
    controller.intelligence_coordinator.research_company = AsyncMock(  # type: ignore[assignment]
        return_value=make_research_result()
    )
    return controller


def make_github_mock_responses() -> dict[str, Any]:
    """Return mock payloads for all GitHubClient methods."""
    return {
        "create_repo": {"html_url": _FAKE_REPO_URL, "name": "acme-fintech-api"},
        "create_or_update_file": {"commit": {"sha": "init_sha_integration_abc123"}},
        "create_tree": {"sha": "tree_sha_integration_abc123"},
        "create_commit": {"sha": "commit_sha_integration_abc123"},
        "update_ref": {"ref": "refs/heads/main"},
        "set_topics": {"names": ["python", "fastapi", "letsbuild"]},
    }


def patch_github_client(mock_responses: dict[str, Any]) -> Any:
    """Build a mock GitHubClient instance."""

    async def mock_request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if "/git/commits/" in path and method == "GET":
            return {"tree": {"sha": "base_tree_sha_integration"}}
        return {}

    mock_client = AsyncMock()
    mock_client.create_repo = AsyncMock(return_value=mock_responses["create_repo"])
    mock_client.create_or_update_file = AsyncMock(
        return_value=mock_responses["create_or_update_file"]
    )
    mock_client.create_tree = AsyncMock(return_value=mock_responses["create_tree"])
    mock_client.create_commit = AsyncMock(return_value=mock_responses["create_commit"])
    mock_client.update_ref = AsyncMock(return_value=mock_responses["update_ref"])
    mock_client.set_topics = AsyncMock(return_value=mock_responses["set_topics"])
    mock_client._request = AsyncMock(side_effect=mock_request)
    return mock_client


_ALL_GATES_PASS = [
    GateResult(gate_name="QualityGate", passed=True, reason="test gate", blocking=True),
    GateResult(gate_name="ReviewGate", passed=True, reason="test gate", blocking=True),
    GateResult(gate_name="SandboxGate", passed=True, reason="test gate", blocking=True),
    GateResult(gate_name="SecurityGate", passed=True, reason="test gate", blocking=True),
    GateResult(gate_name="ReadmeGate", passed=True, reason="test gate", blocking=False),
]
