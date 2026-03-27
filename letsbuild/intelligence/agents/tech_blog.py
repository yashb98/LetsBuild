"""Tech Blog sub-agent: discovers and analyses the company's engineering blog."""

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


class TechBlogAgent:
    """Searches for and analyses a company's engineering/tech blog.

    Current implementation is a stub returning default signals.
    """

    agent_type = SubAgentType.TECH_BLOG

    async def run(
        self,
        company_name: str,
        company_url: str | None,
        jd_text: str | None,
    ) -> SubAgentResult:
        """Research the company's tech blog."""
        log = logger.bind(agent="tech_blog", company=company_name)
        start = time.monotonic()

        try:
            log.info("started")

            data: dict[str, object] = {
                "tech_stack_signals": [],
                "engineering_culture": {
                    "open_source_active": False,
                    "tech_blog_active": False,
                    "key_values": [],
                },
            }

            data_sources: list[DataSource] = [
                DataSource(
                    name=f"{company_name} Tech Blog (stub)",
                    source_type="blog",
                    reliability_score=20.0,
                )
            ]

            elapsed = time.monotonic() - start
            log.info("completed", elapsed=round(elapsed, 3))

            return SubAgentResult(
                agent_type=SubAgentType.TECH_BLOG,
                success=True,
                data=data,
                data_sources=data_sources,
                execution_time_seconds=round(elapsed, 3),
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            log.error("failed", error=str(exc))
            return SubAgentResult(
                agent_type=SubAgentType.TECH_BLOG,
                success=False,
                error=StructuredError(
                    error_category=ErrorCategory.TRANSIENT,
                    is_retryable=True,
                    message=f"Tech blog research failed: {exc}",
                    attempted_query=f"research tech blog for {company_name}",
                ),
                execution_time_seconds=round(elapsed, 3),
            )
