"""Layer 2 coordinator: spawns 6 parallel sub-agents and merges results."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import structlog

from letsbuild.intelligence.agents.business_intel import BusinessIntelAgent
from letsbuild.intelligence.agents.culture_probe import CultureProbeAgent
from letsbuild.intelligence.agents.github_org import GitHubOrgAgent
from letsbuild.intelligence.agents.news_monitor import NewsMonitorAgent
from letsbuild.intelligence.agents.tech_blog import TechBlogAgent
from letsbuild.intelligence.agents.web_presence import WebPresenceAgent
from letsbuild.models.intelligence_models import (
    CompanyProfile,
    EngineeringCulture,
    ResearchResult,
    SubAgentResult,
)

if TYPE_CHECKING:
    from letsbuild.harness.llm_client import LLMClient

logger = structlog.get_logger()


class IntelligenceCoordinator:
    """Orchestrates 6 parallel research sub-agents and merges their results."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client
        self._log = logger.bind(component="intelligence_coordinator")

    async def research_company(
        self,
        company_name: str,
        company_url: str | None = None,
        jd_text: str | None = None,
    ) -> ResearchResult:
        """Run all 6 sub-agents in parallel and merge into a CompanyProfile."""
        self._log.info("research_started", company=company_name)
        start = time.monotonic()

        agents = [
            WebPresenceAgent(),
            TechBlogAgent(),
            GitHubOrgAgent(),
            BusinessIntelAgent(),
            NewsMonitorAgent(),
            CultureProbeAgent(),
        ]

        tasks = [agent.run(company_name, company_url, jd_text) for agent in agents]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions into failed SubAgentResults
        results: list[SubAgentResult] = []
        for i, raw in enumerate(raw_results):
            if isinstance(raw, BaseException):
                self._log.warning(
                    "sub_agent_exception",
                    agent=type(agents[i]).__name__,
                    error=str(raw),
                )
                results.append(
                    SubAgentResult(
                        agent_type=agents[i].agent_type,
                        success=False,
                        error=None,
                        execution_time_seconds=0.0,
                    )
                )
            else:
                results.append(raw)

        elapsed = time.monotonic() - start
        succeeded = sum(1 for r in results if r.success)
        failed = len(results) - succeeded

        profile = self._merge_results(results, company_name, company_url)

        self._log.info(
            "research_complete",
            company=company_name,
            succeeded=succeeded,
            failed=failed,
            elapsed=round(elapsed, 2),
        )

        return ResearchResult(
            company_profile=profile,
            total_execution_time_seconds=round(elapsed, 3),
            agents_succeeded=succeeded,
            agents_failed=failed,
            partial=failed > 0,
        )

    def _merge_results(
        self,
        results: list[SubAgentResult],
        company_name: str,
        company_url: str | None = None,
    ) -> CompanyProfile:
        """Combine successful sub-agent results into a single CompanyProfile."""
        tech_stack_signals: list[str] = []
        recent_news: list[str] = []
        top_languages: list[str] = []
        all_data_sources = []
        industry: str | None = None
        company_size: str | None = None
        business_context: str | None = None
        github_org_url: str | None = None
        public_repos_count: int | None = None
        funding_stage: str | None = None
        engineering_culture: EngineeringCulture | None = None

        succeeded = sum(1 for r in results if r.success)

        for result in results:
            if not result.success:
                continue

            data = result.data
            all_data_sources.extend(result.data_sources)

            # Merge tech stack signals from any agent
            if "tech_stack_signals" in data:
                raw = data["tech_stack_signals"]
                if isinstance(raw, list):
                    tech_stack_signals.extend(str(s) for s in raw)

            if "recent_news" in data:
                raw = data["recent_news"]
                if isinstance(raw, list):
                    recent_news.extend(str(n) for n in raw)

            if "top_languages" in data:
                raw = data["top_languages"]
                if isinstance(raw, list):
                    top_languages.extend(str(lang) for lang in raw)

            if "industry" in data and data["industry"] is not None:
                industry = str(data["industry"])

            if "company_size" in data and data["company_size"] is not None:
                company_size = str(data["company_size"])

            if "business_context" in data and data["business_context"] is not None:
                business_context = str(data["business_context"])

            if "github_org_url" in data and data["github_org_url"] is not None:
                github_org_url = str(data["github_org_url"])

            if "public_repos_count" in data and data["public_repos_count"] is not None:
                public_repos_count = int(data["public_repos_count"])  # type: ignore[arg-type]

            if "funding_stage" in data and data["funding_stage"] is not None:
                funding_stage = str(data["funding_stage"])

            if "engineering_culture" in data and isinstance(data["engineering_culture"], dict):
                engineering_culture = EngineeringCulture(**data["engineering_culture"])  # type: ignore[arg-type]

        # Deduplicate while preserving order
        tech_stack_signals = list(dict.fromkeys(tech_stack_signals))
        top_languages = list(dict.fromkeys(top_languages))

        confidence_score = round(100.0 * succeeded / 6, 1) if succeeded > 0 else 0.0

        return CompanyProfile(
            company_name=company_name,
            company_url=company_url,
            industry=industry,
            company_size=company_size,
            tech_stack_signals=tech_stack_signals,
            engineering_culture=engineering_culture,
            business_context=business_context,
            recent_news=recent_news,
            github_org_url=github_org_url,
            public_repos_count=public_repos_count,
            top_languages=top_languages,
            funding_stage=funding_stage,
            confidence_score=confidence_score,
            data_sources=all_data_sources,
            sub_agent_results=results,
        )
