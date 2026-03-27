"""End-to-end tests for the pipeline controller running layers 1-5.

All LLM calls are mocked -- these tests verify that the PipelineController
correctly orchestrates L1 Intake through L5 Code Forge, accumulating results
into PipelineState including ForgeOutput with code_modules and review_verdict.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from letsbuild.models.forge_models import ReviewVerdict
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

    L3 (MatchEngine), L4 (ProjectArchitect), and L5 (Code Forge) are
    pure-Python / heuristic engines that do not call the LLM, so they run
    for real.
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
# Test 1: L1-L5 produces a ForgeOutput
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l5_produces_forge_output() -> None:
    """Run L1-L5 and verify a complete ForgeOutput is produced."""
    controller = _make_controller()

    state = await controller.run(jd_text=_RAW_JD_TEXT)

    # L1-L4 outputs should be present
    assert state.jd_analysis is not None
    assert state.company_profile is not None
    assert state.gap_analysis is not None
    assert state.project_spec is not None

    # L5 output: ForgeOutput with code_modules and review_verdict
    assert state.forge_output is not None
    assert len(state.forge_output.code_modules) > 0
    assert state.forge_output.review_verdict in (
        ReviewVerdict.PASS,
        ReviewVerdict.PASS_WITH_SUGGESTIONS,
    )

    # No errors should have accumulated
    assert len(state.errors) == 0


# ------------------------------------------------------------------
# Test 2: ForgeOutput has a positive quality score
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l5_forge_output_has_quality_score() -> None:
    """Verify that the forge output quality_score is greater than zero."""
    controller = _make_controller()

    state = await controller.run(jd_text=_RAW_JD_TEXT)

    assert state.forge_output is not None
    assert state.forge_output.quality_score > 0.0

    # Metrics should include the forge layer duration
    assert "forge" in state.metrics.layer_durations
    assert state.metrics.layer_durations["forge"] >= 0.0

    # Pipeline should have completed successfully
    assert state.completed_at is not None
