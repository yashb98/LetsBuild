"""Tests for Layer 2: IntelligenceCoordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from letsbuild.intelligence.coordinator import IntelligenceCoordinator
from letsbuild.models.intelligence_models import (
    DataSource,
    ResearchResult,
    SubAgentResult,
    SubAgentType,
)


def _make_success_result(
    agent_type: SubAgentType,
    *,
    data: dict[str, object] | None = None,
) -> SubAgentResult:
    """Create a successful SubAgentResult for testing."""
    return SubAgentResult(
        agent_type=agent_type,
        success=True,
        data=data or {},
        data_sources=[
            DataSource(
                name=f"{agent_type.value} source",
                source_type="test",
                reliability_score=80.0,
            )
        ],
        execution_time_seconds=0.1,
    )


def _make_all_success_results() -> list[SubAgentResult]:
    """Build 6 success results, one per sub-agent type."""
    return [
        _make_success_result(SubAgentType.WEB_PRESENCE),
        _make_success_result(SubAgentType.TECH_BLOG),
        _make_success_result(SubAgentType.GITHUB_ORG),
        _make_success_result(SubAgentType.BUSINESS_INTEL),
        _make_success_result(SubAgentType.NEWS_MONITOR),
        _make_success_result(SubAgentType.CULTURE_PROBE),
    ]


@pytest.mark.asyncio
async def test_research_company_all_agents_succeed() -> None:
    """When all 6 sub-agents succeed, confidence should be 100 and partial=False."""
    results = _make_all_success_results()

    with patch("letsbuild.intelligence.coordinator.asyncio.gather", new_callable=AsyncMock) as m:
        m.return_value = results
        coordinator = IntelligenceCoordinator()
        res = await coordinator.research_company("Acme Corp")

    assert isinstance(res, ResearchResult)
    assert res.agents_succeeded == 6
    assert res.agents_failed == 0
    assert res.partial is False
    assert res.company_profile.confidence_score == 100.0
    assert res.company_profile.company_name == "Acme Corp"


@pytest.mark.asyncio
async def test_research_company_partial_failure() -> None:
    """When 2 of 6 agents raise exceptions, confidence ~66.7 and partial=True."""
    results: list[SubAgentResult | BaseException] = [
        _make_success_result(SubAgentType.WEB_PRESENCE),
        _make_success_result(SubAgentType.TECH_BLOG),
        _make_success_result(SubAgentType.GITHUB_ORG),
        _make_success_result(SubAgentType.BUSINESS_INTEL),
        RuntimeError("news timeout"),
        RuntimeError("culture timeout"),
    ]

    with patch("letsbuild.intelligence.coordinator.asyncio.gather", new_callable=AsyncMock) as m:
        m.return_value = results
        coordinator = IntelligenceCoordinator()
        res = await coordinator.research_company("Acme Corp")

    assert res.agents_succeeded == 4
    assert res.agents_failed == 2
    assert res.partial is True
    # confidence = 100 * 4/6 = 66.7
    assert abs(res.company_profile.confidence_score - 66.7) < 0.1


@pytest.mark.asyncio
async def test_research_company_all_fail() -> None:
    """When all 6 agents raise exceptions, confidence=0 and partial=True."""
    results: list[BaseException] = [RuntimeError(f"fail {i}") for i in range(6)]

    with patch("letsbuild.intelligence.coordinator.asyncio.gather", new_callable=AsyncMock) as m:
        m.return_value = results
        coordinator = IntelligenceCoordinator()
        res = await coordinator.research_company("FailCorp")

    assert res.agents_succeeded == 0
    assert res.agents_failed == 6
    assert res.partial is True
    assert res.company_profile.confidence_score == 0.0
    assert res.company_profile.company_name == "FailCorp"


@pytest.mark.asyncio
async def test_research_company_returns_research_result() -> None:
    """Verify ResearchResult wrapper fields are populated correctly."""
    results = _make_all_success_results()

    with patch("letsbuild.intelligence.coordinator.asyncio.gather", new_callable=AsyncMock) as m:
        m.return_value = results
        coordinator = IntelligenceCoordinator()
        res = await coordinator.research_company("TestCo", company_url="https://testco.com")

    assert isinstance(res, ResearchResult)
    assert res.total_execution_time_seconds >= 0.0
    assert res.company_profile.company_url == "https://testco.com"
    assert len(res.company_profile.sub_agent_results) == 6
    assert len(res.company_profile.data_sources) == 6


@pytest.mark.asyncio
async def test_research_company_merges_tech_signals() -> None:
    """Tech stack signals from multiple agents should be merged and deduplicated."""
    results = [
        _make_success_result(
            SubAgentType.WEB_PRESENCE,
            data={"tech_stack_signals": ["python", "react"]},
        ),
        _make_success_result(
            SubAgentType.TECH_BLOG,
            data={"tech_stack_signals": ["react", "kubernetes"]},
        ),
        _make_success_result(SubAgentType.GITHUB_ORG),
        _make_success_result(SubAgentType.BUSINESS_INTEL),
        _make_success_result(SubAgentType.NEWS_MONITOR),
        _make_success_result(SubAgentType.CULTURE_PROBE),
    ]

    with patch("letsbuild.intelligence.coordinator.asyncio.gather", new_callable=AsyncMock) as m:
        m.return_value = results
        coordinator = IntelligenceCoordinator()
        res = await coordinator.research_company("TechCo")

    signals = res.company_profile.tech_stack_signals
    # Deduplicated: python, react, kubernetes
    assert signals == ["python", "react", "kubernetes"]
