"""Culture Probe sub-agent: gathers engineering culture signals."""

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


class CultureProbeAgent:
    """Probes Glassdoor, LinkedIn, and other sources for engineering culture signals.

    Current implementation is a stub returning default culture data.
    """

    agent_type = SubAgentType.CULTURE_PROBE

    async def run(
        self,
        company_name: str,
        company_url: str | None,
        jd_text: str | None,
    ) -> SubAgentResult:
        """Research the company's engineering culture."""
        log = logger.bind(agent="culture_probe", company=company_name)
        start = time.monotonic()

        try:
            log.info("started")

            data: dict[str, object] = {
                "engineering_culture": {
                    "open_source_active": False,
                    "tech_blog_active": False,
                    "key_values": [],
                },
            }

            data_sources: list[DataSource] = [
                DataSource(
                    name=f"{company_name} Culture (stub)",
                    source_type="culture",
                    reliability_score=20.0,
                )
            ]

            elapsed = time.monotonic() - start
            log.info("completed", elapsed=round(elapsed, 3))

            return SubAgentResult(
                agent_type=SubAgentType.CULTURE_PROBE,
                success=True,
                data=data,
                data_sources=data_sources,
                execution_time_seconds=round(elapsed, 3),
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            log.error("failed", error=str(exc))
            return SubAgentResult(
                agent_type=SubAgentType.CULTURE_PROBE,
                success=False,
                error=StructuredError(
                    error_category=ErrorCategory.TRANSIENT,
                    is_retryable=True,
                    message=f"Culture probe research failed: {exc}",
                    attempted_query=f"research culture for {company_name}",
                ),
                execution_time_seconds=round(elapsed, 3),
            )
