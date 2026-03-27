"""RequestValidation middleware — first in the 10-stage middleware chain.

Validates and sanitises raw pipeline input (jd_text / jd_url) before any
processing begins.  Rejects missing input, malformed URLs, dangerous URL
schemes, and private-network targets.  Strips HTML tags / entities from
jd_text so downstream layers receive clean plaintext.
"""

from __future__ import annotations

import html
import ipaddress
import re
from urllib.parse import urlparse

import structlog

from letsbuild.harness.middleware import Middleware
from letsbuild.models.shared import ErrorCategory, StructuredError
from letsbuild.pipeline.state import PipelineState  # noqa: TC001

logger = structlog.get_logger()

# Pre-compiled patterns for HTML sanitisation
_SCRIPT_TAG_RE = re.compile(r"<script[\s\S]*?</script>", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Private IP networks (RFC 1918 + loopback)
_PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
)

_BLOCKED_SCHEMES = frozenset({"file", "ftp", "data", "javascript"})


def _is_private_host(hostname: str) -> bool:
    """Return True if *hostname* resolves to a private or loopback IP range."""
    if hostname.lower() in ("localhost", "localhost.localdomain"):
        return True
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        # Not a bare IP — could be a regular domain; allow it.
        return False
    return any(addr in net for net in _PRIVATE_NETWORKS)


def _sanitise_jd_text(raw: str) -> str:
    """Strip script tags, HTML tags, and decode HTML entities."""
    text = _SCRIPT_TAG_RE.sub("", raw)
    text = _HTML_TAG_RE.sub("", text)
    text = html.unescape(text)
    return text.strip()


class RequestValidationMiddleware(Middleware):
    """Validate and sanitise raw JD input at the start of every pipeline run.

    Checks performed (in order):
    1. At least one of ``jd_text`` / ``jd_url`` must be non-empty.
    2. If ``jd_url`` is provided it must use ``http`` or ``https`` and must not
       target a private / loopback address.
    3. ``jd_text`` is sanitised (HTML stripped, entities decoded) and must be
       non-empty after sanitisation.

    On failure a :class:`StructuredError` with ``error_category=VALIDATION``
    is appended to ``state.errors`` and a :class:`ValueError` is raised to
    abort the pipeline.
    """

    # --------------------------------------------------------------------- #
    # before()
    # --------------------------------------------------------------------- #
    async def before(self, state: PipelineState) -> PipelineState:
        """Validate and sanitise ``jd_text`` / ``jd_url`` on *state*."""
        has_text = bool(state.jd_text and state.jd_text.strip())
        has_url = bool(state.jd_url and state.jd_url.strip())

        # 1. At least one input source required
        if not has_text and not has_url:
            self._fail(
                state,
                "Pipeline input must include at least one of jd_text or jd_url.",
            )

        # 2. Validate URL (if provided)
        if has_url:
            assert state.jd_url is not None  # narrowing for type checker
            self._validate_url(state)

        # 3. Sanitise jd_text (if provided)
        if has_text:
            assert state.jd_text is not None  # narrowing for type checker
            sanitised = _sanitise_jd_text(state.jd_text)
            if not sanitised:
                self._fail(
                    state,
                    "jd_text is empty after HTML sanitisation.",
                )
            state.jd_text = sanitised
            await logger.ainfo(
                "request_validation_sanitised_text",
                original_len=len(state.jd_text),
                sanitised_len=len(sanitised),
            )

        await logger.ainfo(
            "request_validation_passed",
            has_text=has_text,
            has_url=has_url,
            thread_id=state.thread_id,
        )
        return state

    # --------------------------------------------------------------------- #
    # after()
    # --------------------------------------------------------------------- #
    async def after(self, state: PipelineState) -> PipelineState:
        """No-op — request validation has no post-processing step."""
        return state

    # --------------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------------- #
    def _validate_url(self, state: PipelineState) -> None:
        """Check scheme, host, and private-IP rules for ``state.jd_url``."""
        assert state.jd_url is not None
        url = state.jd_url.strip()

        parsed = urlparse(url)

        # Scheme check
        if parsed.scheme not in ("http", "https"):
            if parsed.scheme in _BLOCKED_SCHEMES:
                self._fail(
                    state,
                    f"URL scheme '{parsed.scheme}://' is not allowed. Use http:// or https://.",
                )
            self._fail(
                state,
                f"Invalid URL scheme '{parsed.scheme}'. Only http:// and https:// are accepted.",
            )

        # Hostname must be present
        hostname = parsed.hostname
        if not hostname:
            self._fail(state, "URL is missing a hostname.")

        # Private / loopback check
        if _is_private_host(hostname):
            self._fail(
                state,
                f"URL targets a private or loopback address ({hostname}). "
                "Only public URLs are accepted.",
            )

    @staticmethod
    def _fail(state: PipelineState, message: str) -> None:
        """Append a ``StructuredError`` to *state* and raise ``ValueError``."""
        error = StructuredError(
            error_category=ErrorCategory.VALIDATION,
            is_retryable=False,
            message=message,
        )
        state.add_error(error)
        raise ValueError(message)
