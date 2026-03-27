"""JD fetcher — retrieves job description text from URLs.

Supports HTML pages, plain text, and basic PDF content detection.
Uses httpx for async HTTP requests and regex-based HTML stripping.
"""

from __future__ import annotations

import html
import re

import httpx
import structlog

logger = structlog.get_logger()

# Timeout for HTTP requests in seconds.
_REQUEST_TIMEOUT = 30.0

# Patterns for stripping HTML content.
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_MAIN_CONTENT_RE = re.compile(
    r"<(?:main|article)[^>]*>(.*?)</(?:main|article)>",
    re.DOTALL | re.IGNORECASE,
)
_JOB_DIV_RE = re.compile(
    r'<div[^>]*class="[^"]*job[^"]*"[^>]*>(.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)


class JDFetcher:
    """Fetches job description text from a URL.

    Handles HTML pages (with tag stripping and main-content extraction),
    plain text, and basic PDF content-type detection.
    """

    def __init__(self) -> None:
        self._log = logger.bind(component="jd_fetcher")

    async def fetch(self, url: str) -> str:
        """Fetch and extract text content from *url*.

        Returns cleaned text suitable for LLM intake.  Raises on network
        errors or unsupported content types.
        """
        self._log.info("fetch_start", url=url)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(_REQUEST_TIMEOUT),
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        raw = response.text

        if "text/html" in content_type or "<html" in raw[:500].lower():
            text = self._extract_html_text(raw)
        elif "application/pdf" in content_type:
            # Basic PDF handling — full extraction would require a dedicated
            # library (e.g. pdfplumber).  For now return whatever text is
            # decodable from the response body.
            self._log.warning("pdf_basic_extraction", url=url)
            text = raw
        else:
            # Assume plain text.
            text = raw

        cleaned = self._sanitise(text)

        if not cleaned.strip():
            msg = f"No text content could be extracted from {url}"
            raise ValueError(msg)

        self._log.info("fetch_complete", url=url, chars=len(cleaned))
        return cleaned

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_html_text(self, raw_html: str) -> str:
        """Strip HTML to plain text, preferring main/article content."""
        # Try to isolate the main content area first.
        for pattern in (_MAIN_CONTENT_RE, _JOB_DIV_RE):
            match = pattern.search(raw_html)
            if match:
                raw_html = match.group(1)
                break

        # Remove script and style blocks.
        text = _SCRIPT_STYLE_RE.sub("", raw_html)
        # Strip remaining HTML tags.
        text = _HTML_TAG_RE.sub(" ", text)
        # Decode HTML entities.
        text = html.unescape(text)
        # Normalise whitespace.
        text = _WHITESPACE_RE.sub(" ", text).strip()
        return text

    @staticmethod
    def _sanitise(text: str) -> str:
        """Sanitise extracted text — decode entities and normalise whitespace."""
        text = html.unescape(text)
        text = _WHITESPACE_RE.sub(" ", text).strip()
        return text
