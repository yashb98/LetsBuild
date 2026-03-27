"""Tests for JDFetcher (Layer 1 — URL fetching and HTML stripping)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from letsbuild.intake.fetcher import JDFetcher


class TestExtractHtmlText:
    """Tests for JDFetcher._extract_html_text."""

    def test_extract_html_text_strips_tags(self) -> None:
        """HTML tags should be removed, leaving only text content."""
        fetcher = JDFetcher()
        result = fetcher._extract_html_text("<p>Hello <b>World</b></p>")
        assert "Hello" in result
        assert "World" in result
        assert "<p>" not in result
        assert "<b>" not in result

    def test_extract_html_text_strips_scripts(self) -> None:
        """Script tags and their contents should be completely removed."""
        fetcher = JDFetcher()
        html = "<div>Visible</div><script>alert('xss')</script><div>Also visible</div>"
        result = fetcher._extract_html_text(html)
        assert "Visible" in result
        assert "Also visible" in result
        assert "alert" not in result
        assert "script" not in result

    def test_extract_html_text_strips_styles(self) -> None:
        """Style tags and their contents should be completely removed."""
        fetcher = JDFetcher()
        html = "<div>Content</div><style>.red { color: red; }</style>"
        result = fetcher._extract_html_text(html)
        assert "Content" in result
        assert "color" not in result
        assert "style" not in result.lower()

    def test_extract_html_text_decodes_entities(self) -> None:
        """HTML entities should be decoded to their character equivalents."""
        fetcher = JDFetcher()
        html = "<p>Tom &amp; Jerry &lt;3 &gt; 2</p>"
        result = fetcher._extract_html_text(html)
        assert "Tom & Jerry" in result
        assert "<3" in result
        assert "> 2" in result

    def test_extract_html_text_normalises_whitespace(self) -> None:
        """Excessive whitespace should be collapsed to single spaces."""
        fetcher = JDFetcher()
        html = "<p>Hello     World</p>"
        result = fetcher._extract_html_text(html)
        assert "Hello World" in result


class TestFetch:
    """Tests for JDFetcher.fetch with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_fetch_with_mocked_httpx(self) -> None:
        """fetch should return cleaned text from an HTML response."""
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html><body><p>Senior Engineer needed</p></body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("letsbuild.intake.fetcher.httpx.AsyncClient", return_value=mock_client):
            fetcher = JDFetcher()
            result = await fetcher.fetch("https://example.com/job")

        assert "Senior Engineer needed" in result

    @pytest.mark.asyncio
    async def test_fetch_plain_text_passthrough(self) -> None:
        """fetch should return plain text responses without HTML stripping."""
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.text = "Software Engineer - Remote"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("letsbuild.intake.fetcher.httpx.AsyncClient", return_value=mock_client):
            fetcher = JDFetcher()
            result = await fetcher.fetch("https://example.com/job.txt")

        assert "Software Engineer - Remote" in result

    @pytest.mark.asyncio
    async def test_fetch_empty_content_raises(self) -> None:
        """fetch should raise ValueError when no text can be extracted."""
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html><body><script>only script</script></body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("letsbuild.intake.fetcher.httpx.AsyncClient", return_value=mock_client):
            fetcher = JDFetcher()
            with pytest.raises(ValueError, match=r"No text content"):
                await fetcher.fetch("https://example.com/empty")
