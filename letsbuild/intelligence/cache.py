"""Company profile cache with TTL-based freshness logic."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog
from pydantic import TypeAdapter

from letsbuild.models.intelligence_models import CompanyProfile

logger = structlog.get_logger()

_FRESH_TTL_DAYS = 30
_STALE_TTL_DAYS = 90

_profile_adapter = TypeAdapter(CompanyProfile)


class CacheStatus:
    """Describes the freshness of a cached profile."""

    FRESH = "fresh"  # <30 days — skip all research
    STALE = "stale"  # 30-90 days — partial refresh recommended
    EXPIRED = "expired"  # >90 days — full research needed
    MISS = "miss"  # not in cache


class CompanyCache:
    """Simple JSON-file cache for CompanyProfile objects."""

    def __init__(self, cache_dir: str | None = None) -> None:
        if cache_dir is None:
            self._cache_dir = Path.home() / ".letsbuild" / "cache" / "companies"
        else:
            self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._log = logger.bind(component="company_cache")

    async def get(self, company_name: str) -> tuple[CompanyProfile | None, str]:
        """Look up a cached profile by company name.

        Returns:
            A tuple of (profile_or_None, status) where status is one of
            CacheStatus.FRESH, CacheStatus.STALE, CacheStatus.EXPIRED,
            or CacheStatus.MISS.
        """
        path = self._path_for(company_name)
        if not path.exists():
            self._log.debug("cache_miss", company=company_name)
            return None, CacheStatus.MISS

        try:
            raw_text = path.read_text(encoding="utf-8")
            profile = _profile_adapter.validate_json(raw_text)
        except Exception as exc:
            self._log.warning("cache_corrupt", company=company_name, error=str(exc))
            return None, CacheStatus.MISS

        age = datetime.now(UTC) - profile.researched_at
        if age < timedelta(days=_FRESH_TTL_DAYS):
            self._log.info("cache_fresh", company=company_name, age_days=age.days)
            return profile, CacheStatus.FRESH
        if age < timedelta(days=_STALE_TTL_DAYS):
            self._log.info("cache_stale", company=company_name, age_days=age.days)
            return profile, CacheStatus.STALE

        self._log.info("cache_expired", company=company_name, age_days=age.days)
        return None, CacheStatus.EXPIRED

    async def put(self, profile: CompanyProfile) -> None:
        """Store a profile in the cache."""
        path = self._path_for(profile.company_name)
        data = profile.model_dump(mode="json")
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        self._log.info("cache_stored", company=profile.company_name, path=str(path))

    def _path_for(self, company_name: str) -> Path:
        """Derive a filesystem-safe cache file path from a company name."""
        safe_name = company_name.lower().replace(" ", "_").replace("/", "_")
        return self._cache_dir / f"{safe_name}.json"
