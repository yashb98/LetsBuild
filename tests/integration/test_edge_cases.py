"""Edge case integration tests for the LetsBuild pipeline.

Tests verify:
- Empty JD text handled gracefully
- JD with no skills detected still produces output
- JD with unknown role category uses OTHER fallback
- Extremely long JD (>10000 chars) is processed without crash
- Special characters in company name are handled
- Pipeline with zero budget rejects all layers with cost
- Unicode and multilingual JD text
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from letsbuild.harness.middleware import MiddlewareChain
from letsbuild.harness.middlewares.budget_guard import BudgetGuardMiddleware
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
from letsbuild.pipeline.state import PipelineState

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_minimal_jd_analysis(
    *,
    role_title: str = "Software Engineer",
    role_category: RoleCategory = RoleCategory.FULL_STACK,
    required_skills: list[Skill] | None = None,
    raw_text: str = "Software Engineer role",
) -> JDAnalysis:
    """Build a minimal JDAnalysis with optional skill override."""
    return JDAnalysis(
        role_title=role_title,
        role_category=role_category,
        seniority=SeniorityLevel.MID,
        required_skills=required_skills or [],
        tech_stack=TechStack(languages=[], frameworks=[]),
        domain_keywords=[],
        key_responsibilities=[],
        raw_text=raw_text,
    )


def make_empty_company_research() -> ResearchResult:
    """Build a ResearchResult with minimal data."""
    return ResearchResult(
        company_profile=CompanyProfile(
            company_name="Unknown Company",
            industry="unknown",
            tech_stack_signals=[],
            confidence_score=10.0,
            data_sources=[],
            sub_agent_results=[
                SubAgentResult(
                    agent_type=SubAgentType.WEB_PRESENCE,
                    success=False,
                    execution_time_seconds=0.1,
                )
            ],
        ),
        total_execution_time_seconds=0.1,
        agents_succeeded=0,
        agents_failed=6,
        partial=True,
    )


def make_controller_with_mocks(
    jd_override: JDAnalysis | None = None,
    research_override: ResearchResult | None = None,
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> PipelineController:
    """Create a PipelineController with L1/L2 mocked."""
    if monkeypatch is not None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_OWNER", raising=False)

    controller = PipelineController()
    controller.intake_engine.parse_jd = AsyncMock(  # type: ignore[assignment]
        return_value=jd_override or make_minimal_jd_analysis()
    )
    controller.intelligence_coordinator.research_company = AsyncMock(  # type: ignore[assignment]
        return_value=research_override or make_empty_company_research()
    )
    return controller


# ---------------------------------------------------------------------------
# Test 1: Empty JD text — ValueError raised (no jd_text or jd_url)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edge_case_no_jd_input_raises_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling run() with no jd_text and no jd_url must raise ValueError."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_OWNER", raising=False)

    controller = PipelineController()
    with pytest.raises(ValueError, match="Either jd_text or jd_url must be provided"):
        await controller.run()


# ---------------------------------------------------------------------------
# Test 2: JD with no skills detected — pipeline still completes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edge_case_jd_no_skills_pipeline_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline must complete without crashing when JD has zero required_skills."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_OWNER", raising=False)

    jd = make_minimal_jd_analysis(required_skills=[], raw_text="A vague job description.")
    controller = make_controller_with_mocks(jd_override=jd, monkeypatch=monkeypatch)

    state = await controller.run(jd_text="A vague job description.")

    # Pipeline ran and completed
    assert state.completed_at is not None
    # L1 output is set
    assert state.jd_analysis is not None
    assert state.jd_analysis.required_skills == []
    # L4 still designed a project (architect uses defaults when skills are empty)
    assert state.project_spec is not None


# ---------------------------------------------------------------------------
# Test 3: JD with unknown role category — uses OTHER fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edge_case_unknown_role_category_uses_other(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline must handle RoleCategory.OTHER without crashing."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_OWNER", raising=False)

    # RoleCategory.OTHER requires role_category_detail per model validation rules
    jd = JDAnalysis(
        role_title="Quantum Computing Architect",
        role_category=RoleCategory.OTHER,
        role_category_detail="Quantum software engineer combining physics and CS",
        seniority=SeniorityLevel.SENIOR,
        required_skills=[],
        tech_stack=TechStack(languages=["python"], frameworks=[]),
        domain_keywords=["quantum", "research"],
        key_responsibilities=["Design quantum circuits", "Build simulators"],
        raw_text="Quantum computing role at startup.",
    )
    controller = make_controller_with_mocks(jd_override=jd, monkeypatch=monkeypatch)

    state = await controller.run(jd_text="Quantum computing role at startup.")

    assert state.completed_at is not None
    assert state.jd_analysis is not None
    assert state.jd_analysis.role_category == RoleCategory.OTHER
    assert state.project_spec is not None


# ---------------------------------------------------------------------------
# Test 4: Extremely long JD (>10000 chars) — pipeline handles without crash
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edge_case_extremely_long_jd_no_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline must not crash when given a JD text exceeding 10000 characters."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_OWNER", raising=False)

    long_jd_text = "Senior Software Engineer. " * 500  # ~12500 chars
    assert len(long_jd_text) > 10000

    jd = make_minimal_jd_analysis(raw_text=long_jd_text[:500])
    controller = make_controller_with_mocks(jd_override=jd, monkeypatch=monkeypatch)

    state = await controller.run(jd_text=long_jd_text)

    assert state.completed_at is not None
    assert state.jd_analysis is not None


# ---------------------------------------------------------------------------
# Test 5: Special characters in company name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edge_case_special_characters_in_company_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline must handle company names with special characters (apostrophes, hyphens, etc)."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_OWNER", raising=False)

    jd = make_minimal_jd_analysis(raw_text="Engineer at O'Brien & Co. — New York")
    research = ResearchResult(
        company_profile=CompanyProfile(
            company_name="O'Brien & Co.",
            industry="consulting",
            tech_stack_signals=["python"],
            confidence_score=60.0,
            data_sources=[],
            sub_agent_results=[],
        ),
        total_execution_time_seconds=0.2,
        agents_succeeded=2,
        agents_failed=4,
        partial=True,
    )
    controller = make_controller_with_mocks(
        jd_override=jd,
        research_override=research,
        monkeypatch=monkeypatch,
    )

    state = await controller.run(jd_text="Engineer at O'Brien & Co. — New York")

    assert state.completed_at is not None
    assert state.company_profile is not None
    assert "O'Brien" in state.company_profile.company_name


# ---------------------------------------------------------------------------
# Test 6: Pipeline with zero budget rejects all expensive layers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edge_case_zero_budget_blocks_all_layers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pipeline with £0.00 budget must be blocked immediately by BudgetGuard."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_OWNER", raising=False)

    controller = PipelineController()
    controller.intake_engine.parse_jd = AsyncMock(  # type: ignore[assignment]
        return_value=make_minimal_jd_analysis()
    )
    controller.intelligence_coordinator.research_company = AsyncMock(  # type: ignore[assignment]
        return_value=make_empty_company_research()
    )

    # £0.00 budget — no layer with a cost > 0 should run
    budget_guard = BudgetGuardMiddleware(max_budget_gbp=0.0)
    chain = MiddlewareChain(middlewares=[budget_guard])
    controller.set_middleware_chain(chain)

    state = await controller.run(jd_text="Software Engineer at Startup")

    # At least one BudgetGate error should have accumulated
    assert len(state.errors) >= 1
    budget_errors = [
        e for e in state.errors if "budget" in e.message.lower() or "BudgetGate" in e.message
    ]
    assert len(budget_errors) >= 1


# ---------------------------------------------------------------------------
# Test 7: Unicode and multilingual JD text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edge_case_unicode_jd_text_no_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline must not crash when given JD text containing Unicode characters."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_OWNER", raising=False)

    unicode_jd = (
        "シニアエンジニア — Python/FastAPI専門家。"
        " Looking for developers with 5+ years experience. "
        "Привет мир. こんにちは世界. 안녕하세요."
        " Salary: €150,000. Location: München."
    )

    jd = make_minimal_jd_analysis(raw_text=unicode_jd[:200])
    controller = make_controller_with_mocks(jd_override=jd, monkeypatch=monkeypatch)

    state = await controller.run(jd_text=unicode_jd)

    assert state.completed_at is not None
    assert state.jd_analysis is not None


# ---------------------------------------------------------------------------
# Test 8: Pipeline with jd_url (URL-based input)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edge_case_jd_url_based_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline must call parse_from_url when jd_url is given without jd_text."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_OWNER", raising=False)

    jd = make_minimal_jd_analysis()

    controller = PipelineController()
    # Mock parse_from_url (used when only URL is provided)
    controller.intake_engine.parse_from_url = AsyncMock(  # type: ignore[assignment]
        return_value=jd
    )
    controller.intelligence_coordinator.research_company = AsyncMock(  # type: ignore[assignment]
        return_value=make_empty_company_research()
    )

    state = await controller.run(jd_url="https://example.com/job/12345")

    assert state.jd_analysis is not None
    assert state.completed_at is not None


# ---------------------------------------------------------------------------
# Test 9: PipelineState is_failed returns True at >= 3 errors
# ---------------------------------------------------------------------------


def test_edge_case_pipeline_state_is_failed_threshold() -> None:
    """PipelineState.is_failed() must return True when errors >= 3, False otherwise."""
    from letsbuild.models.shared import ErrorCategory, StructuredError

    state = PipelineState(jd_text="test")

    assert state.is_failed() is False

    for i in range(2):
        state.add_error(
            StructuredError(
                error_category=ErrorCategory.TRANSIENT,
                is_retryable=True,
                message=f"Error {i}",
                attempted_query=f"layer_{i}",
            )
        )
    assert state.is_failed() is False  # 2 errors — not yet failed

    state.add_error(
        StructuredError(
            error_category=ErrorCategory.TRANSIENT,
            is_retryable=True,
            message="Error 3",
            attempted_query="layer_3",
        )
    )
    assert state.is_failed() is True  # 3 errors — failed


# ---------------------------------------------------------------------------
# Test 10: Pipeline accumulates completed_at timestamp
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edge_case_completed_at_is_set_after_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """state.completed_at must be set to a datetime after any run completes."""
    from datetime import UTC, datetime

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_OWNER", raising=False)

    controller = make_controller_with_mocks(monkeypatch=monkeypatch)

    before_run = datetime.now(UTC)
    state = await controller.run(jd_text="Quick pipeline run test")
    after_run = datetime.now(UTC)

    assert state.completed_at is not None
    assert before_run <= state.completed_at <= after_run
