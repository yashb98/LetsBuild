"""Tests for RequestValidationMiddleware (Layer 0 — first in the 10-stage chain)."""

from __future__ import annotations

import pytest

from letsbuild.harness.middlewares.request_validation import RequestValidationMiddleware
from letsbuild.pipeline.state import PipelineState


def _state(**kwargs: object) -> PipelineState:
    """Build a minimal PipelineState with overrides."""
    return PipelineState(**kwargs)  # type: ignore[arg-type]


@pytest.fixture
def middleware() -> RequestValidationMiddleware:
    return RequestValidationMiddleware()


# ------------------------------------------------------------------ #
# before() — valid inputs
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_valid_jd_text_passes(middleware: RequestValidationMiddleware) -> None:
    """Plain-text jd_text passes validation without error."""
    state = _state(jd_text="Senior Python engineer needed for backend work.")
    result = await middleware.before(state)
    assert result.jd_text == "Senior Python engineer needed for backend work."
    assert not result.errors


@pytest.mark.asyncio
async def test_valid_jd_url_passes(middleware: RequestValidationMiddleware) -> None:
    """A well-formed https URL passes validation."""
    state = _state(jd_url="https://example.com/job")
    result = await middleware.before(state)
    assert result.jd_url == "https://example.com/job"
    assert not result.errors


# ------------------------------------------------------------------ #
# before() — missing input
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_empty_jd_text_and_jd_url_raises(middleware: RequestValidationMiddleware) -> None:
    """Both jd_text and jd_url missing raises ValueError."""
    state = _state()
    with pytest.raises(ValueError, match=r"at least one of jd_text or jd_url"):
        await middleware.before(state)
    assert len(state.errors) == 1
    assert state.errors[0].error_category == "validation"


@pytest.mark.asyncio
async def test_blank_strings_treated_as_missing(middleware: RequestValidationMiddleware) -> None:
    """Whitespace-only jd_text and jd_url are treated as empty."""
    state = _state(jd_text="   ", jd_url="  ")
    with pytest.raises(ValueError, match=r"at least one of jd_text or jd_url"):
        await middleware.before(state)


# ------------------------------------------------------------------ #
# before() — URL validation
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_file_scheme_rejected(middleware: RequestValidationMiddleware) -> None:
    """file:// URLs are rejected."""
    state = _state(jd_url="file:///etc/passwd")
    with pytest.raises(ValueError, match=r"not allowed"):
        await middleware.before(state)


@pytest.mark.asyncio
async def test_localhost_rejected(middleware: RequestValidationMiddleware) -> None:
    """localhost URLs are rejected as private addresses."""
    state = _state(jd_url="http://localhost:8080/job")
    with pytest.raises(ValueError, match=r"private or loopback"):
        await middleware.before(state)


@pytest.mark.asyncio
async def test_private_ip_10_rejected(middleware: RequestValidationMiddleware) -> None:
    """10.x.x.x private IPs are rejected."""
    state = _state(jd_url="http://10.0.0.1/job")
    with pytest.raises(ValueError, match=r"private or loopback"):
        await middleware.before(state)


@pytest.mark.asyncio
async def test_private_ip_192_168_rejected(middleware: RequestValidationMiddleware) -> None:
    """192.168.x.x private IPs are rejected."""
    state = _state(jd_url="http://192.168.1.1/job")
    with pytest.raises(ValueError, match=r"private or loopback"):
        await middleware.before(state)


# ------------------------------------------------------------------ #
# before() — HTML sanitisation
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_html_tags_stripped(middleware: RequestValidationMiddleware) -> None:
    """HTML tags are removed from jd_text."""
    state = _state(jd_text="<p>Senior <b>Python</b> engineer</p>")
    result = await middleware.before(state)
    assert result.jd_text == "Senior Python engineer"


@pytest.mark.asyncio
async def test_script_tags_stripped(middleware: RequestValidationMiddleware) -> None:
    """Script tags and their contents are removed from jd_text."""
    state = _state(jd_text='Hello<script>alert("xss")</script> World')
    result = await middleware.before(state)
    assert result.jd_text == "Hello World"


@pytest.mark.asyncio
async def test_jd_text_only_html_rejected(middleware: RequestValidationMiddleware) -> None:
    """jd_text that becomes empty after stripping HTML is rejected."""
    state = _state(jd_text="<div><span></span></div>")
    with pytest.raises(ValueError, match=r"empty after HTML sanitisation"):
        await middleware.before(state)


@pytest.mark.asyncio
async def test_whitespace_only_after_strip_rejected(
    middleware: RequestValidationMiddleware,
) -> None:
    """jd_text that is only whitespace wrapped in tags is rejected."""
    state = _state(jd_text="<p>   </p>")
    with pytest.raises(ValueError, match=r"empty after HTML sanitisation"):
        await middleware.before(state)


# ------------------------------------------------------------------ #
# after() — no-op
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_after_returns_state_unchanged(middleware: RequestValidationMiddleware) -> None:
    """after() is a no-op and returns the state as-is."""
    state = _state(jd_text="Some valid text")
    result = await middleware.after(state)
    assert result is state
