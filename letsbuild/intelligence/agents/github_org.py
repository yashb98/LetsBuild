"""GitHub Org sub-agent: gathers signals from the company's GitHub organisation."""

from __future__ import annotations

import time

import structlog

from letsbuild.models.intelligence_models import (
    DataSource,
    SubAgentResult,
    SubAgentType,
)
from letsbuild.models.shared import ErrorCategory, StructuredError

logger = structlog.get_logger()


class GitHubOrgAgent:
    """Queries GitHub API for company repos, languages, and activity.

    Current implementation is a stub returning basic signals from the company name.
    """

    agent_type = SubAgentType.GITHUB_ORG

    async def run(
        self,
        company_name: str,
        company_url: str | None,
        jd_text: str | None,
    ) -> SubAgentResult:
        """Research the company's GitHub organisation."""
        log = logger.bind(agent="github_org", company=company_name)
        start = time.monotonic()

        try:
            log.info("started")

            # Stub: construct a plausible GitHub org URL
            org_slug = company_name.lower().replace(" ", "-").replace(".", "")
            github_org_url = f"https://github.com/{org_slug}"

            data: dict[str, object] = {
                "github_org_url": github_org_url,
                "public_repos_count": None,
                "top_languages": [],
            }

            data_sources: list[DataSource] = [
                DataSource(
                    name=f"{company_name} GitHub (stub)",
                    url=github_org_url,
                    source_type="github",
                    reliability_score=30.0,
                )
            ]

            elapsed = time.monotonic() - start
            log.info("completed", elapsed=round(elapsed, 3))

            return SubAgentResult(
                agent_type=SubAgentType.GITHUB_ORG,
                success=True,
                data=data,
                data_sources=data_sources,
                execution_time_seconds=round(elapsed, 3),
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            log.error("failed", error=str(exc))
            return SubAgentResult(
                agent_type=SubAgentType.GITHUB_ORG,
                success=False,
                error=StructuredError(
                    error_category=ErrorCategory.TRANSIENT,
                    is_retryable=True,
                    message=f"GitHub org research failed: {exc}",
                    attempted_query=f"research GitHub org for {company_name}",
                ),
                execution_time_seconds=round(elapsed, 3),
            )
