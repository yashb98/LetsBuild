"""News Monitor sub-agent: searches for recent company news."""

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


class NewsMonitorAgent:
    """Searches news APIs for recent company mentions and announcements.

    Current implementation is a stub returning an empty news list.
    """

    agent_type = SubAgentType.NEWS_MONITOR

    async def run(
        self,
        company_name: str,
        company_url: str | None,
        jd_text: str | None,
    ) -> SubAgentResult:
        """Search for recent news about the company."""
        log = logger.bind(agent="news_monitor", company=company_name)
        start = time.monotonic()

        try:
            log.info("started")

            data: dict[str, object] = {
                "recent_news": [],
            }

            data_sources: list[DataSource] = [
                DataSource(
                    name=f"{company_name} News (stub)",
                    source_type="news",
                    reliability_score=20.0,
                )
            ]

            elapsed = time.monotonic() - start
            log.info("completed", elapsed=round(elapsed, 3))

            return SubAgentResult(
                agent_type=SubAgentType.NEWS_MONITOR,
                success=True,
                data=data,
                data_sources=data_sources,
                execution_time_seconds=round(elapsed, 3),
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            log.error("failed", error=str(exc))
            return SubAgentResult(
                agent_type=SubAgentType.NEWS_MONITOR,
                success=False,
                error=StructuredError(
                    error_category=ErrorCategory.TRANSIENT,
                    is_retryable=True,
                    message=f"News monitor research failed: {exc}",
                    attempted_query=f"search news for {company_name}",
                ),
                execution_time_seconds=round(elapsed, 3),
            )
