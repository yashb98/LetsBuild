"""Business Intelligence sub-agent: gathers company business data."""

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


class BusinessIntelAgent:
    """Queries business data APIs for company size, funding, and industry.

    Current implementation is a stub returning basic structure.
    """

    agent_type = SubAgentType.BUSINESS_INTEL

    async def run(
        self,
        company_name: str,
        company_url: str | None,
        jd_text: str | None,
    ) -> SubAgentResult:
        """Research the company's business intelligence."""
        log = logger.bind(agent="business_intel", company=company_name)
        start = time.monotonic()

        try:
            log.info("started")

            data: dict[str, object] = {
                "industry": None,
                "company_size": None,
                "funding_stage": None,
                "business_context": None,
            }

            data_sources: list[DataSource] = [
                DataSource(
                    name=f"{company_name} Business Intel (stub)",
                    source_type="business_api",
                    reliability_score=20.0,
                )
            ]

            elapsed = time.monotonic() - start
            log.info("completed", elapsed=round(elapsed, 3))

            return SubAgentResult(
                agent_type=SubAgentType.BUSINESS_INTEL,
                success=True,
                data=data,
                data_sources=data_sources,
                execution_time_seconds=round(elapsed, 3),
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            log.error("failed", error=str(exc))
            return SubAgentResult(
                agent_type=SubAgentType.BUSINESS_INTEL,
                success=False,
                error=StructuredError(
                    error_category=ErrorCategory.TRANSIENT,
                    is_retryable=True,
                    message=f"Business intel research failed: {exc}",
                    attempted_query=f"research business intel for {company_name}",
                ),
                execution_time_seconds=round(elapsed, 3),
            )
