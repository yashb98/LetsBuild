"""Tests for Layer 2: CompanyCache."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path  # noqa: TC003

import pytest

from letsbuild.intelligence.cache import CacheStatus, CompanyCache
from letsbuild.models.intelligence_models import CompanyProfile


def _make_profile(
    company_name: str = "Acme Corp",
    researched_at: datetime | None = None,
) -> CompanyProfile:
    """Create a minimal CompanyProfile for testing."""
    return CompanyProfile(
        company_name=company_name,
        confidence_score=80.0,
        researched_at=researched_at or datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_put_and_get_fresh(tmp_path: Path) -> None:
    """Storing a profile and retrieving it within 30 days returns FRESH status."""
    cache = CompanyCache(cache_dir=str(tmp_path))
    profile = _make_profile()
    await cache.put(profile)

    result, status = await cache.get("Acme Corp")

    assert status == CacheStatus.FRESH
    assert result is not None
    assert result.company_name == "Acme Corp"
    assert result.confidence_score == 80.0


@pytest.mark.asyncio
async def test_get_missing_returns_none(tmp_path: Path) -> None:
    """Looking up a company that was never cached returns None and MISS."""
    cache = CompanyCache(cache_dir=str(tmp_path))

    result, status = await cache.get("NonExistent Inc")

    assert result is None
    assert status == CacheStatus.MISS


@pytest.mark.asyncio
async def test_get_expired_returns_none(tmp_path: Path) -> None:
    """A profile older than 90 days returns None and EXPIRED status."""
    cache = CompanyCache(cache_dir=str(tmp_path))
    old_time = datetime.now(UTC) - timedelta(days=91)
    profile = _make_profile(researched_at=old_time)
    await cache.put(profile)

    result, status = await cache.get("Acme Corp")

    assert result is None
    assert status == CacheStatus.EXPIRED


@pytest.mark.asyncio
async def test_get_stale_returns_profile(tmp_path: Path) -> None:
    """A profile between 30 and 90 days old returns the profile with STALE status."""
    cache = CompanyCache(cache_dir=str(tmp_path))
    stale_time = datetime.now(UTC) - timedelta(days=45)
    profile = _make_profile(researched_at=stale_time)
    await cache.put(profile)

    result, status = await cache.get("Acme Corp")

    assert status == CacheStatus.STALE
    assert result is not None
    assert result.company_name == "Acme Corp"
