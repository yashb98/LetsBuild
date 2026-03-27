"""End-to-end tests for the pipeline controller running layers 1-4.

All LLM calls are mocked -- these tests verify that the PipelineController
correctly orchestrates IntakeEngine, IntelligenceCoordinator, MatchEngine,
and ProjectArchitect, accumulating results into PipelineState.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from letsbuild.models.intake_models import (  # noqa: TC001
    JDAnalysis,
    RoleCategory,
    SeniorityLevel,
    Skill,
    TechStack,
)
from letsbuild.models.intelligence_models import (  # noqa: TC001
    CompanyProfile,
    ResearchResult,
    SubAgentResult,
    SubAgentType,
)
from letsbuild.pipeline.controller import PipelineController


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_RAW_JD_TEXT = "Senior Full-Stack Engineer at Fintech Co"


def _make_jd_analysis() -> JDAnalysis:
    """Build a valid JDAnalysis for a senior full-stack engineer role."""
    return JDAnalysis(
        role_title="Senior Full-Stack Engineer",
        role_category=RoleCategory.FULL_STACK,
        seniority=SeniorityLevel.SENIOR,
        required_skills=[
            Skill(name="python", category="languages", confidence=90.0),
            Skill(name="react", category="frameworks", confidence=85.0),
        ],
        tech_stack=TechStack(
            languages=["python", "typescript"],
            frameworks=["react", "fastapi"],
        ),
        domain_keywords=["fintech"],
        key_responsibilities=["Build REST APIs", "Design React components"],
        raw_text=_RAW_JD_TEXT,
    )


def _make_company_profile() -> CompanyProfile:
    """Build a minimal CompanyProfile for tests."""
    return CompanyProfile(
        company_name="Unknown Company",
        industry="fintech",
        tech_stack_signals=["python", "react", "fastapi"],
        confidence_score=60.0,
        data_sources=[],
        sub_agent_results=[
            SubAgentResult(
                agent_type=SubAgentType.WEB_PRESENCE,
                success=True,
                execution_time_seconds=0.1,
            ),
        ],
    )


def _make_research_result() -> ResearchResult:
    """Build a ResearchResult wrapping the fake company profile."""
    return ResearchResult(
        company_profile=_make_company_profile(),
        total_execution_time_seconds=0.3,
        agents_succeeded=4,
        agents_failed=2,
        partial=True,
    )


def _make_controller() -> PipelineController:
    """Create a PipelineController with L1 and L2 mocked (no LLM calls).

    L3 (MatchEngine) and L4 (ProjectArchitect) are pure-Python / heuristic
    engines that do not call the LLM, so they run for real.
    """
    controller = PipelineController()

    controller.intake_engine.parse_jd = AsyncMock(  # type: ignore[assignment]
        return_value=_make_jd_analysis(),
    )
    controller.intelligence_coordinator.research_company = AsyncMock(  # type: ignore[assignment]
        return_value=_make_research_result(),
    )

    return controller


# ------------------------------------------------------------------
# Test 1: full pipeline produces a ProjectSpec
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_pipeline_produces_project_spec() -> None:
    """Run L1-L4 and verify a complete ProjectSpec is produced."""
    controller = _make_controller()

    state = await controller.run(jd_text=_RAW_JD_TEXT)

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
# Test 2: state accumulates progressively across layers
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_pipeline_state_accumulates() -> None:
    """Verify that each layer sets its corresponding field on PipelineState."""
    controller = _make_controller()

    state = await controller.run(jd_text=_RAW_JD_TEXT)

    # L1 output
    assert state.jd_analysis is not None
    assert state.jd_analysis.role_title == "Senior Full-Stack Engineer"
    assert state.jd_analysis.role_category == RoleCategory.FULL_STACK
    assert state.jd_analysis.seniority == SeniorityLevel.SENIOR

    # L2 output
    assert state.company_profile is not None
    assert state.company_profile.company_name == "Unknown Company"

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
# Test 3: metrics are tracked for each layer
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_pipeline_metrics_tracked() -> None:
    """Verify that layer_durations are populated for all 4 layers."""
    controller = _make_controller()

    state = await controller.run(jd_text=_RAW_JD_TEXT)

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
# Test 4: pipeline handles layer failure gracefully
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_pipeline_handles_layer_failure() -> None:
    """Mock L2 to raise an exception; pipeline should continue with partial state."""
    controller = PipelineController()

    # Mock L1 to succeed
    controller.intake_engine.parse_jd = AsyncMock(  # type: ignore[assignment]
        return_value=_make_jd_analysis(),
    )

    # Mock L2 to fail
    controller.intelligence_coordinator.research_company = AsyncMock(  # type: ignore[assignment]
        side_effect=RuntimeError("Network timeout during company research"),
    )

    state = await controller.run(jd_text=_RAW_JD_TEXT)

    # L1 should have succeeded
    assert state.jd_analysis is not None

    # L2 should have failed -- company_profile remains None
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
