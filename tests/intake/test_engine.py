"""Tests for the Intake Engine (Layer 1)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from letsbuild.intake.engine import IntakeEngine
from letsbuild.models.intake_models import JDAnalysis, RoleCategory, SeniorityLevel


def _make_jd_dict(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid JDAnalysis dict with optional overrides.

    Uses enum member values (strings) since JDAnalysis has strict=True and
    model_validate is called on the raw dict returned by the LLM client.
    We pass through model_validate with strict=False via model_construct
    workaround — but the engine itself calls model_validate, so we need
    to provide actual enum instances for strict mode.
    """
    base: dict[str, Any] = {
        "role_title": "Software Engineer",
        "role_category": RoleCategory.FULL_STACK,
        "seniority": SeniorityLevel.MID,
        "raw_text": "Sample JD text",
        "required_skills": [],
        "preferred_skills": [],
        "tech_stack": {},
        "domain_keywords": [],
        "key_responsibilities": [],
    }
    base.update(overrides)
    return base


class TestBuildToolSchema:
    """Tests for IntakeEngine._build_tool_schema."""

    def test_build_tool_schema_has_required_fields(self) -> None:
        """The tool schema must contain name, description, and input_schema keys."""
        engine = IntakeEngine(llm_client=MagicMock())
        schema = engine._build_tool_schema()

        assert "name" in schema
        assert "description" in schema
        assert "input_schema" in schema

    def test_build_tool_schema_name_is_extract_jd_analysis(self) -> None:
        """The tool name must be 'extract_jd_analysis'."""
        engine = IntakeEngine(llm_client=MagicMock())
        schema = engine._build_tool_schema()
        assert schema["name"] == "extract_jd_analysis"

    def test_build_tool_schema_input_schema_has_properties(self) -> None:
        """The input_schema must include a 'properties' key from the Pydantic model."""
        engine = IntakeEngine(llm_client=MagicMock())
        schema = engine._build_tool_schema()
        input_schema = schema["input_schema"]
        assert isinstance(input_schema, dict)
        assert "properties" in input_schema


class TestParseJD:
    """Tests for IntakeEngine.parse_jd with mocked LLM."""

    @pytest.mark.asyncio
    async def test_parse_jd_with_mocked_llm(self) -> None:
        """parse_jd should return a JDAnalysis instance when LLM returns valid data."""
        mock_client = MagicMock()
        mock_client.extract_structured = AsyncMock(return_value=_make_jd_dict())

        engine = IntakeEngine(llm_client=mock_client)
        result = await engine.parse_jd("Some job description text")

        assert isinstance(result, JDAnalysis)

    @pytest.mark.asyncio
    async def test_parse_jd_extracts_role_title(self) -> None:
        """parse_jd should set role_title from the LLM response."""
        mock_client = MagicMock()
        mock_client.extract_structured = AsyncMock(
            return_value=_make_jd_dict(role_title="Senior Backend Engineer"),
        )

        engine = IntakeEngine(llm_client=mock_client)
        result = await engine.parse_jd("Senior Backend Engineer needed")

        assert result.role_title == "Senior Backend Engineer"

    @pytest.mark.asyncio
    async def test_parse_jd_sets_raw_text_from_input(self) -> None:
        """parse_jd should default raw_text to the original input text."""
        jd_text = "A unique JD about widgets"
        mock_client = MagicMock()
        # Return dict WITHOUT raw_text so the engine fills it in via setdefault.
        data = _make_jd_dict()
        data.pop("raw_text")
        mock_client.extract_structured = AsyncMock(return_value=data)

        engine = IntakeEngine(llm_client=mock_client)
        result = await engine.parse_jd(jd_text)

        assert result.raw_text == jd_text

    @pytest.mark.asyncio
    async def test_parse_jd_preserves_source_url(self) -> None:
        """parse_jd should set source_url when provided."""
        mock_client = MagicMock()
        data = _make_jd_dict()
        data.pop("raw_text")
        mock_client.extract_structured = AsyncMock(return_value=data)

        engine = IntakeEngine(llm_client=mock_client)
        result = await engine.parse_jd("Some JD", source_url="https://example.com/job")

        assert result.source_url == "https://example.com/job"

    @pytest.mark.asyncio
    async def test_parse_jd_passes_model_haiku(self) -> None:
        """parse_jd should call extract_structured with claude-haiku-4-5."""
        mock_client = MagicMock()
        mock_client.extract_structured = AsyncMock(return_value=_make_jd_dict())

        engine = IntakeEngine(llm_client=mock_client)
        await engine.parse_jd("Some JD")

        call_kwargs = mock_client.extract_structured.call_args
        assert call_kwargs.kwargs["model"] == "claude-haiku-4-5"


class TestParseFromURL:
    """Tests for IntakeEngine.parse_from_url."""

    @pytest.mark.asyncio
    async def test_parse_from_url_calls_fetcher_then_parse(self) -> None:
        """parse_from_url should fetch text via JDFetcher then call parse_jd."""
        mock_client = MagicMock()
        mock_client.extract_structured = AsyncMock(return_value=_make_jd_dict())

        engine = IntakeEngine(llm_client=mock_client)

        with patch(
            "letsbuild.intake.engine.JDFetcher.fetch",
            new_callable=AsyncMock,
            return_value="Fetched JD text from URL",
        ) as mock_fetch:
            result = await engine.parse_from_url("https://example.com/job")

        mock_fetch.assert_awaited_once_with("https://example.com/job")
        assert isinstance(result, JDAnalysis)
        # The LLM should have been called (extract_structured)
        mock_client.extract_structured.assert_awaited_once()
