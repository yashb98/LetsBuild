"""Intake Engine (Layer 1) — parses job descriptions into structured JDAnalysis.

Uses forced tool_choice on ``extract_jd_analysis`` to guarantee structured
output from the LLM.  Supports both raw text and URL-based JD ingestion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from letsbuild.intake.fetcher import JDFetcher
from letsbuild.models.intake_models import JDAnalysis

if TYPE_CHECKING:
    from letsbuild.harness.llm_client import LLMClient

logger = structlog.get_logger()

_SYSTEM_PROMPT = """\
You are a job description analysis expert.  Given the raw text of a job \
description, extract all structured information using the \
extract_jd_analysis tool.

Guidelines:
- Identify the exact role title as written in the JD.
- Categorise the role into one of the predefined categories. Use OTHER only \
when no category fits and provide role_category_detail in that case.
- Determine seniority from explicit mentions (e.g. "Senior", "Staff") or \
infer from years of experience and responsibilities.
- Extract every required and preferred skill with its category \
(language, framework, tool, methodology, etc.).
- Build the tech_stack from all technologies mentioned. All items must be \
lowercase.
- Pull out domain keywords (e.g. "fintech", "real-time", "healthcare").
- List key responsibilities verbatim or lightly paraphrased.
- Extract salary, experience range, location, and remote policy when present.
- Set raw_text to the full original JD text provided.
- Set source_url if one was provided in the user message.
"""

_TOOL_NAME = "extract_jd_analysis"


class IntakeEngine:
    """Layer 1 — Intake Engine.

    Parses job description text (or fetches from a URL) and returns a
    validated ``JDAnalysis`` Pydantic model using forced ``tool_use``.
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client
        self._log = logger.bind(component="intake_engine")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def parse_jd(self, text: str, source_url: str | None = None) -> JDAnalysis:
        """Parse raw JD *text* and return a validated ``JDAnalysis``.

        Uses forced ``tool_choice`` (``extract_jd_analysis``) to guarantee
        structured output from the LLM.
        """
        client = self._resolve_client()

        user_content = text
        if source_url:
            user_content = f"Source URL: {source_url}\n\n{text}"

        self._log.info("parse_jd_start", text_len=len(text), has_url=source_url is not None)

        raw_data: dict[str, Any] = await client.extract_structured(
            messages=[{"role": "user", "content": user_content}],
            system=_SYSTEM_PROMPT,
            tool_schema=self._build_tool_schema(),
            tool_name=_TOOL_NAME,
            model="claude-haiku-4-5",
        )

        # Ensure raw_text is always present (the LLM may omit it).
        raw_data.setdefault("raw_text", text)
        if source_url:
            raw_data.setdefault("source_url", source_url)

        analysis = JDAnalysis.model_validate(raw_data)

        self._log.info(
            "parse_jd_complete",
            role_title=analysis.role_title,
            role_category=analysis.role_category.value,
            seniority=analysis.seniority.value,
            required_skills=len(analysis.required_skills),
            preferred_skills=len(analysis.preferred_skills),
        )

        return analysis

    async def parse_from_url(self, url: str) -> JDAnalysis:
        """Fetch JD text from *url* and parse it into a ``JDAnalysis``."""
        self._log.info("parse_from_url", url=url)
        fetcher = JDFetcher()
        text = await fetcher.fetch(url)
        return await self.parse_jd(text, source_url=url)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_tool_schema(self) -> dict[str, object]:
        """Build the Claude tool definition for ``extract_jd_analysis``."""
        return {
            "name": _TOOL_NAME,
            "description": (
                "Extract structured data from a job description. "
                "Return all fields that can be determined from the text."
            ),
            "input_schema": JDAnalysis.model_json_schema(),
        }

    def _resolve_client(self) -> LLMClient:
        """Return the stored LLM client or create a default one."""
        if self._llm_client is not None:
            return self._llm_client

        # Late import to avoid circular dependency at module level.
        from letsbuild.harness.llm_client import LLMClient

        self._llm_client = LLMClient()
        self._log.info("llm_client_created", note="default LLMClient instantiated")
        return self._llm_client
