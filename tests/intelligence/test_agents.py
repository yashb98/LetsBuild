"""Tests for Layer 2: individual sub-agents."""

from __future__ import annotations

import pytest

from letsbuild.intelligence.agents.business_intel import BusinessIntelAgent
from letsbuild.intelligence.agents.culture_probe import CultureProbeAgent
from letsbuild.intelligence.agents.github_org import GitHubOrgAgent
from letsbuild.intelligence.agents.news_monitor import NewsMonitorAgent
from letsbuild.intelligence.agents.tech_blog import TechBlogAgent
from letsbuild.intelligence.agents.web_presence import WebPresenceAgent
from letsbuild.models.intelligence_models import SubAgentResult, SubAgentType


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("agent_cls", "expected_type"),
    [
        (WebPresenceAgent, SubAgentType.WEB_PRESENCE),
        (TechBlogAgent, SubAgentType.TECH_BLOG),
        (GitHubOrgAgent, SubAgentType.GITHUB_ORG),
        (BusinessIntelAgent, SubAgentType.BUSINESS_INTEL),
        (NewsMonitorAgent, SubAgentType.NEWS_MONITOR),
        (CultureProbeAgent, SubAgentType.CULTURE_PROBE),
    ],
    ids=[
        "web_presence",
        "tech_blog",
        "github_org",
        "business_intel",
        "news_monitor",
        "culture_probe",
    ],
)
async def test_agent_run_returns_sub_agent_result(
    agent_cls: type[
        WebPresenceAgent
        | TechBlogAgent
        | GitHubOrgAgent
        | BusinessIntelAgent
        | NewsMonitorAgent
        | CultureProbeAgent
    ],
    expected_type: SubAgentType,
) -> None:
    """Each sub-agent's run() returns a SubAgentResult with correct agent_type."""
    agent = agent_cls()
    result = await agent.run("TestCo", "https://testco.com", "We use Python and React")

    assert isinstance(result, SubAgentResult)
    assert result.agent_type == expected_type
    assert result.success is True
    assert result.execution_time_seconds >= 0.0
    assert result.error is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("agent_cls", "expected_type"),
    [
        (WebPresenceAgent, SubAgentType.WEB_PRESENCE),
        (TechBlogAgent, SubAgentType.TECH_BLOG),
        (GitHubOrgAgent, SubAgentType.GITHUB_ORG),
        (BusinessIntelAgent, SubAgentType.BUSINESS_INTEL),
        (NewsMonitorAgent, SubAgentType.NEWS_MONITOR),
        (CultureProbeAgent, SubAgentType.CULTURE_PROBE),
    ],
    ids=[
        "web_presence",
        "tech_blog",
        "github_org",
        "business_intel",
        "news_monitor",
        "culture_probe",
    ],
)
async def test_agent_has_correct_agent_type_attribute(
    agent_cls: type[
        WebPresenceAgent
        | TechBlogAgent
        | GitHubOrgAgent
        | BusinessIntelAgent
        | NewsMonitorAgent
        | CultureProbeAgent
    ],
    expected_type: SubAgentType,
) -> None:
    """Each agent class has the correct agent_type class attribute."""
    agent = agent_cls()
    assert agent.agent_type == expected_type


@pytest.mark.asyncio
async def test_web_presence_extracts_tech_signals() -> None:
    """WebPresenceAgent extracts known tech keywords from JD text."""
    agent = WebPresenceAgent()
    result = await agent.run(
        "TestCo",
        None,
        "We need a Python developer experienced with React and Docker",
    )

    assert result.success is True
    signals = result.data.get("tech_stack_signals", [])
    assert isinstance(signals, list)
    assert "python" in signals
    assert "react" in signals
    assert "docker" in signals


@pytest.mark.asyncio
async def test_github_org_builds_org_url() -> None:
    """GitHubOrgAgent constructs a plausible GitHub org URL from company name."""
    agent = GitHubOrgAgent()
    result = await agent.run("Acme Corp", None, None)

    assert result.success is True
    assert result.data.get("github_org_url") == "https://github.com/acme-corp"
