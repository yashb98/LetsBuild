"""End-to-end tests for the pipeline controller running layers 1-4.

All LLM calls are mocked — these tests verify that the PipelineController
correctly orchestrates IntakeEngine, IntelligenceCoordinator, MatchEngine,
and ProjectArchitect, accumulating results into PipelineState.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from letsbuild.models.intake_models import (
    JDAnalysis,
    RoleCategory,
    SeniorityLevel,
    Skill,
    TechStack,
)
from letsbuild.models.intelligence_models import (
    CompanyProfile,
    ResearchResult,
    SubAgentResult,
    SubAgentType,
)
from letsbuild.pipeline.controller import PipelineController

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "sample_jds"


@pytest.fixture()
def sample_jd_text() -> str:
    """Load the senior fullstack fintech sample JD from fixtures."""
    jd_path = _FIXTURES_DIR / "senior_fullstack_fintech.txt"
    return jd_path.read_text()


@pytest.fixture()
def fake_jd_analysis(sample_jd_text: str) -> JDAnalysis:
    """Pre-built JDAnalysis matching the senior fullstack fintech JD."""
    return JDAnalysis(
        role_title="Senior Full-Stack Engineer",
        role_category=RoleCategory.FULL_STACK,
        seniority=SeniorityLevel.SENIOR,
        company_name="Acme Financial Technologies",
        company_url=None,
        required_skills=[
            Skill(name="TypeScript", category="language", is_primary=True),
            Skill(name="React", category="framework", is_primary=True),
            Skill(name="Node.js", category="framework", is_primary=True),
            Skill(name="PostgreSQL", category="database"),
            Skill(name="AWS", category="cloud"),
            Skill(name="RESTful API", category="methodology"),
        ],
        preferred_skills=[
            Skill(name="GraphQL", category="framework"),
            Skill(name="Docker", category="tool"),
            Skill(name="Kubernetes", category="tool"),
        ],
        tech_stack=TechStack(
            languages=["typescript"],
            frameworks=["react", "node.js"],
            databases=["postgresql"],
            cloud_providers=["aws"],
            tools=["docker", "git"],
        ),
        domain_keywords=["fintech", "payments", "real-time"],
        key_responsibilities=[
            "Design and implement new features across the full stack",
            "Build and maintain RESTful APIs and GraphQL endpoints",
            "Collaborate with DevOps to improve CI/CD pipelines",
            "Mentor junior engineers through code reviews",
            "Contribute to architectural decisions",
        ],
        years_experience_min=3,
        salary_min_gbp=75000.0,
        salary_max_gbp=95000.0,
        location="London, UK",
        remote_policy="hybrid",
        raw_text=sample_jd_text,
    )


@pytest.fixture()
def fake_company_profile() -> CompanyProfile:
    """Pre-built CompanyProfile for Acme Financial Technologies."""
    return CompanyProfile(
        company_name="Acme Financial Technologies",
        industry="fintech",
        company_size="51-200",
        tech_stack_signals=["react", "node.js", "postgresql", "aws", "kubernetes"],
        business_context="Payment infrastructure for European businesses.",
        confidence_score=66.7,
        data_sources=[],
        sub_agent_results=[
            SubAgentResult(
                agent_type=SubAgentType.WEB_PRESENCE,
                success=True,
                execution_time_seconds=0.1,
            ),
        ],
    )


@pytest.fixture()
def fake_research_result(fake_company_profile: CompanyProfile) -> ResearchResult:
    """Pre-built ResearchResult wrapping the fake company profile."""
    return ResearchResult(
        company_profile=fake_company_profile,
        total_execution_time_seconds=0.5,
        agents_succeeded=4,
        agents_failed=2,
        partial=True,
    )


def _make_controller(
    fake_jd_analysis: JDAnalysis,
    fake_research_result: ResearchResult,
) -> PipelineController:
    """Create a PipelineController with mocked layer engines."""
    controller = PipelineController()

    # Mock L1: IntakeEngine.parse_jd
    controller.intake_engine.parse_jd = AsyncMock(return_value=fake_jd_analysis)

    # Mock L2: IntelligenceCoordinator.research_company
    controller.intelligence_coordinator.research_company = AsyncMock(
        return_value=fake_research_result,
    )

    # L3 (MatchEngine) and L4 (ProjectArchitect) are pure Python / heuristic
    # — no LLM calls needed — so they run for real.

    return controller


# ------------------------------------------------------------------
# Test: full pipeline produces a ProjectSpec
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_pipeline_produces_project_spec(
    sample_jd_text: str,
    fake_jd_analysis: JDAnalysis,
    fake_research_result: ResearchResult,
) -> None:
    """Run L1-L4 and verify a complete ProjectSpec is produced."""
    controller = _make_controller(fake_jd_analysis, fake_research_result)

    state = await controller.run(jd_text=sample_jd_text)

    # All layer outputs must be populated
    assert state.jd_analysis is not None
    assert state.company_profile is not None
    assert state.gap_analysis is not None
    assert state.project_spec is not None

    # ProjectSpec must contain essential artefacts
    assert len(state.project_spec.file_tree) > 0
    assert len(state.project_spec.feature_specs) > 0
    assert len(state.project_spec.adr_list) > 0

    # No errors should have accumulated
    assert len(state.errors) == 0


# ------------------------------------------------------------------
# Test: state accumulates progressively across layers
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_pipeline_state_accumulates(
    sample_jd_text: str,
    fake_jd_analysis: JDAnalysis,
    fake_research_result: ResearchResult,
) -> None:
    """Verify that each layer sets its corresponding field on PipelineState."""
    controller = _make_controller(fake_jd_analysis, fake_research_result)

    state = await controller.run(jd_text=sample_jd_text)

    # L1 output
    assert state.jd_analysis is not None
    assert state.jd_analysis.role_title == "Senior Full-Stack Engineer"
    assert state.jd_analysis.role_category == RoleCategory.FULL_STACK

    # L2 output
    assert state.company_profile is not None
    assert state.company_profile.company_name == "Acme Financial Technologies"

    # L3 output
    assert state.gap_analysis is not None
    assert state.gap_analysis.match_score is not None
    assert state.gap_analysis.match_score.overall_score >= 0.0

    # L4 output
    assert state.project_spec is not None
    assert state.project_spec.project_name  # non-empty string
    assert state.project_spec.seniority_target == "senior"

    # Pipeline completed (not aborted)
    assert state.completed_at is not None


# ------------------------------------------------------------------
# Test: metrics are tracked for each layer
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_pipeline_metrics_tracked(
    sample_jd_text: str,
    fake_jd_analysis: JDAnalysis,
    fake_research_result: ResearchResult,
) -> None:
    """Verify that layer_durations are populated for all 4 layers."""
    controller = _make_controller(fake_jd_analysis, fake_research_result)

    state = await controller.run(jd_text=sample_jd_text)

    # Each successfully completed layer should have a duration recorded
    assert "intake" in state.metrics.layer_durations
    assert "intelligence" in state.metrics.layer_durations
    assert "matcher" in state.metrics.layer_durations
    assert "architect" in state.metrics.layer_durations

    # All durations must be non-negative floats
    for _layer_name, duration in state.metrics.layer_durations.items():
        assert duration >= 0.0

    # Total duration must also be set
    assert state.metrics.total_duration_seconds > 0.0


# ------------------------------------------------------------------
# Test: pipeline handles layer failure gracefully
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_pipeline_handles_layer_failure(
    sample_jd_text: str,
    fake_jd_analysis: JDAnalysis,
) -> None:
    """Mock L2 to raise an exception; pipeline should continue with partial state."""
    controller = PipelineController()

    # Mock L1 to succeed
    controller.intake_engine.parse_jd = AsyncMock(return_value=fake_jd_analysis)

    # Mock L2 to fail
    controller.intelligence_coordinator.research_company = AsyncMock(
        side_effect=RuntimeError("Network timeout during company research"),
    )

    state = await controller.run(jd_text=sample_jd_text)

    # L1 should have succeeded
    assert state.jd_analysis is not None

    # L2 should have failed — company_profile remains None
    assert state.company_profile is None

    # Error should have been recorded
    assert len(state.errors) >= 1
    l2_errors = [e for e in state.errors if "intelligence" in e.message.lower()]
    assert len(l2_errors) == 1
    assert l2_errors[0].is_retryable is True

    # L3 and L4 should still have run (they tolerate missing company_profile)
    assert state.gap_analysis is not None
    assert state.project_spec is not None

    # Pipeline should have completed (only 1 failure, threshold is 3)
    assert state.completed_at is not None
