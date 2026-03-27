"""Web Presence sub-agent: gathers company signals from website and JD text."""

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


class WebPresenceAgent:
    """Scrapes company website for tech stack signals and business context.

    Current implementation is a stub that extracts basic signals from the JD text.
    """

    agent_type = SubAgentType.WEB_PRESENCE

    async def run(
        self,
        company_name: str,
        company_url: str | None,
        jd_text: str | None,
    ) -> SubAgentResult:
        """Research the company's web presence."""
        log = logger.bind(agent="web_presence", company=company_name)
        start = time.monotonic()

        try:
            log.info("started")
            data: dict[str, object] = {}
            data_sources: list[DataSource] = []

            # Stub: extract signals from JD text if available
            if jd_text:
                data["tech_stack_signals"] = _extract_tech_signals(jd_text)
                data_sources.append(
                    DataSource(
                        name=f"{company_name} Job Description",
                        source_type="jd_text",
                        reliability_score=60.0,
                    )
                )

            if company_url:
                data_sources.append(
                    DataSource(
                        name=f"{company_name} Website",
                        url=company_url,
                        source_type="website",
                        reliability_score=80.0,
                    )
                )

            elapsed = time.monotonic() - start
            log.info("completed", elapsed=round(elapsed, 3))

            return SubAgentResult(
                agent_type=SubAgentType.WEB_PRESENCE,
                success=True,
                data=data,
                data_sources=data_sources,
                execution_time_seconds=round(elapsed, 3),
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            log.error("failed", error=str(exc))
            return SubAgentResult(
                agent_type=SubAgentType.WEB_PRESENCE,
                success=False,
                error=StructuredError(
                    error_category=ErrorCategory.TRANSIENT,
                    is_retryable=True,
                    message=f"Web presence research failed: {exc}",
                    attempted_query=f"research web presence for {company_name}",
                ),
                execution_time_seconds=round(elapsed, 3),
            )


def _extract_tech_signals(jd_text: str) -> list[str]:
    """Extract technology keywords from JD text (simple keyword matching stub)."""
    known_tech = [
        "python",
        "javascript",
        "typescript",
        "react",
        "next.js",
        "fastapi",
        "django",
        "flask",
        "node.js",
        "go",
        "rust",
        "java",
        "kotlin",
        "swift",
        "postgresql",
        "mysql",
        "mongodb",
        "redis",
        "docker",
        "kubernetes",
        "aws",
        "gcp",
        "azure",
        "terraform",
        "graphql",
        "rest",
        "grpc",
        "kafka",
        "rabbitmq",
        "elasticsearch",
        "pytorch",
        "tensorflow",
        "pandas",
        "spark",
    ]
    lower_text = jd_text.lower()
    return [tech for tech in known_tech if tech in lower_text]
