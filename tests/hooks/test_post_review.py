"""Tests for the PostReview hook."""

from __future__ import annotations

import pytest

from letsbuild.hooks.post_review import PostReviewAction, PostReviewHook
from letsbuild.models.forge_models import ReviewVerdict


@pytest.fixture
def hook() -> PostReviewHook:
    return PostReviewHook()


@pytest.mark.asyncio
async def test_fail_verdict_returns_retry(hook: PostReviewHook) -> None:
    """A FAIL verdict must route to RETRY."""
    result = await hook.run(ReviewVerdict.FAIL)
    assert result.action == PostReviewAction.RETRY
    assert result.retry_context is not None


@pytest.mark.asyncio
async def test_pass_verdict_returns_proceed(hook: PostReviewHook) -> None:
    """A PASS verdict must route to PROCEED."""
    result = await hook.run(ReviewVerdict.PASS)
    assert result.action == PostReviewAction.PROCEED
    assert result.retry_context is None


@pytest.mark.asyncio
async def test_pass_with_suggestions_returns_proceed(hook: PostReviewHook) -> None:
    """A PASS_WITH_SUGGESTIONS verdict must route to PROCEED."""
    result = await hook.run(ReviewVerdict.PASS_WITH_SUGGESTIONS)
    assert result.action == PostReviewAction.PROCEED
    assert result.retry_context is None
