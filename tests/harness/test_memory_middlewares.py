"""Tests for MemoryRetrievalMiddleware and MemoryPersistenceMiddleware."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from letsbuild.harness.middlewares.memory_persistence import MemoryPersistenceMiddleware
from letsbuild.harness.middlewares.memory_retrieval import MemoryRetrievalMiddleware
from letsbuild.memory.storage import MemoryStorage
from letsbuild.models.intake_models import JDAnalysis, RoleCategory, SeniorityLevel, TechStack
from letsbuild.models.intelligence_models import CompanyProfile
from letsbuild.models.memory_models import MemoryRecord
from letsbuild.models.publisher_models import (
    CommitEntry,
    CommitPhase,
    CommitPlan,
    PublishResult,
    RepoConfig,
)
from letsbuild.models.shared import PipelineMetrics
from letsbuild.pipeline.state import PipelineState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def storage(tmp_path: pytest.TempPathFactory) -> MemoryStorage:  # type: ignore[type-arg]
    """Provide an initialised MemoryStorage backed by a temp SQLite file."""
    db_path = str(tmp_path / "mw_test.db")
    store = MemoryStorage(db_path=db_path)
    async with store:
        yield store


def make_jd_analysis(company_name: str | None = "Acme Corp") -> JDAnalysis:
    """Create a minimal JDAnalysis."""
    return JDAnalysis(
        role_title="Backend Engineer",
        role_category=RoleCategory.BACKEND,
        seniority=SeniorityLevel.MID,
        company_name=company_name,
        tech_stack=TechStack(languages=["python"], frameworks=["fastapi"]),
        raw_text="We are looking for a backend engineer with Python and FastAPI experience.",
    )


def make_company_profile(company_name: str = "Acme Corp") -> CompanyProfile:
    """Create a minimal CompanyProfile."""
    return CompanyProfile(
        company_name=company_name,
        confidence_score=85.0,
    )


def make_state(
    *,
    jd_analysis: JDAnalysis | None = None,
    company_profile: CompanyProfile | None = None,
    publish_result: PublishResult | None = None,
) -> PipelineState:
    """Create a minimal PipelineState."""
    state = PipelineState()
    state.jd_analysis = jd_analysis
    state.company_profile = company_profile
    state.publish_result = publish_result
    return state


def make_publish_result() -> PublishResult:
    """Create a minimal PublishResult for testing."""
    commit_entry = CommitEntry(
        message="feat: initial scaffolding",
        files=["README.md"],
        phase=CommitPhase.SCAFFOLDING,
        timestamp_offset_hours=0.0,
    )
    commit_plan = CommitPlan(commits=[commit_entry], total_commits=1, spread_days=3)
    repo_config = RepoConfig(
        repo_name="acme-backend-api",
        description="Backend API for Acme Corp",
        topics=["python", "fastapi"],
    )
    return PublishResult(
        repo_url="https://github.com/testuser/acme-backend-api",
        commit_shas=["abc123"],
        readme_url="https://github.com/testuser/acme-backend-api/blob/main/README.md",
        repo_config=repo_config,
        commit_plan=commit_plan,
    )


# ---------------------------------------------------------------------------
# MemoryRetrievalMiddleware — cached company profile
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieval_middleware_injects_cached_company_profile(
    storage: MemoryStorage,
) -> None:
    """before() should inject a cached company profile when it exists and is fresh."""
    profile = make_company_profile("Acme Corp")
    profile_data: dict[str, object] = profile.model_dump(mode="json")

    # Save a fresh record (created now, expires in 90 days)
    record = MemoryRecord(
        record_type="company_profile",
        data=profile_data,
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=90),
    )
    await storage.save_record(record)

    jd = make_jd_analysis(company_name="Acme Corp")
    state = make_state(jd_analysis=jd)

    middleware = MemoryRetrievalMiddleware(storage=storage)
    result = await middleware.before(state)

    assert result.company_profile is not None
    assert result.company_profile.company_name == "Acme Corp"


@pytest.mark.asyncio
async def test_retrieval_middleware_skips_stale_cache(storage: MemoryStorage) -> None:
    """before() should NOT inject a cached profile older than 30 days."""
    profile = make_company_profile("OldCorp")
    profile_data: dict[str, object] = profile.model_dump(mode="json")

    stale_created_at = datetime.now(UTC) - timedelta(days=40)
    record = MemoryRecord(
        record_type="company_profile",
        data=profile_data,
        created_at=stale_created_at,
        expires_at=datetime.now(UTC) + timedelta(days=50),
    )
    await storage.save_record(record)

    jd = make_jd_analysis(company_name="OldCorp")
    state = make_state(jd_analysis=jd)

    middleware = MemoryRetrievalMiddleware(storage=storage)
    result = await middleware.before(state)

    # Stale cache should be skipped — company_profile stays None
    assert result.company_profile is None


@pytest.mark.asyncio
async def test_retrieval_middleware_does_not_overwrite_existing_profile(
    storage: MemoryStorage,
) -> None:
    """before() should not overwrite state.company_profile if it is already set."""
    profile = make_company_profile("Acme Corp")
    profile_data: dict[str, object] = profile.model_dump(mode="json")

    record = MemoryRecord(
        record_type="company_profile",
        data=profile_data,
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=90),
    )
    await storage.save_record(record)

    # Pre-populate state.company_profile with a different company
    existing_profile = make_company_profile("AlreadySet Corp")
    jd = make_jd_analysis(company_name="Acme Corp")
    state = make_state(jd_analysis=jd, company_profile=existing_profile)

    middleware = MemoryRetrievalMiddleware(storage=storage)
    result = await middleware.before(state)

    assert result.company_profile.company_name == "AlreadySet Corp"


@pytest.mark.asyncio
async def test_retrieval_middleware_no_jd_does_not_crash(storage: MemoryStorage) -> None:
    """before() should handle state with no jd_analysis without crashing."""
    state = make_state(jd_analysis=None)
    middleware = MemoryRetrievalMiddleware(storage=storage)
    result = await middleware.before(state)
    assert result is state


@pytest.mark.asyncio
async def test_retrieval_middleware_after_is_noop(storage: MemoryStorage) -> None:
    """after() should return state unchanged."""
    state = make_state()
    middleware = MemoryRetrievalMiddleware(storage=storage)
    result = await middleware.after(state)
    assert result is state


@pytest.mark.asyncio
async def test_retrieval_middleware_does_not_crash_on_storage_error() -> None:
    """before() should catch storage errors and continue without crashing."""
    bad_storage = MagicMock(spec=MemoryStorage)
    bad_storage.find_records = AsyncMock(side_effect=RuntimeError("DB is down"))

    jd = make_jd_analysis(company_name="Acme Corp")
    state = make_state(jd_analysis=jd)

    middleware = MemoryRetrievalMiddleware(storage=bad_storage)
    # Should not raise
    result = await middleware.before(state)
    assert result.company_profile is None


# ---------------------------------------------------------------------------
# MemoryPersistenceMiddleware
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persistence_middleware_before_is_noop(storage: MemoryStorage) -> None:
    """before() should return state unchanged."""
    state = make_state()
    middleware = MemoryPersistenceMiddleware(storage=storage)
    result = await middleware.before(state)
    assert result is state


@pytest.mark.asyncio
async def test_persistence_middleware_saves_company_profile(storage: MemoryStorage) -> None:
    """after() should save a company profile MemoryRecord with 90-day TTL."""
    profile = make_company_profile("Acme Corp")
    state = make_state(company_profile=profile)

    middleware = MemoryPersistenceMiddleware(storage=storage)
    await middleware.after(state)

    records = await storage.find_records("company_profile")
    assert len(records) == 1
    saved = records[0]
    assert saved.data["company_name"] == "Acme Corp"
    assert saved.expires_at is not None
    # TTL should be ~90 days
    assert (saved.expires_at - datetime.now(UTC)).days >= 88


@pytest.mark.asyncio
async def test_persistence_middleware_saves_portfolio_entry(storage: MemoryStorage) -> None:
    """after() should save a portfolio_entry MemoryRecord with no expiry."""
    publish = make_publish_result()
    state = make_state(publish_result=publish)

    middleware = MemoryPersistenceMiddleware(storage=storage)
    await middleware.after(state)

    records = await storage.find_records("portfolio_entry")
    assert len(records) == 1
    saved = records[0]
    assert saved.data["repo_url"] == "https://github.com/testuser/acme-backend-api"
    assert saved.expires_at is None  # permanent


@pytest.mark.asyncio
async def test_persistence_middleware_enriches_portfolio_with_jd_context(
    storage: MemoryStorage,
) -> None:
    """after() should add role_title, company_name, and role_category to portfolio entries."""
    publish = make_publish_result()
    jd = make_jd_analysis(company_name="Acme Corp")
    state = make_state(jd_analysis=jd, publish_result=publish)

    middleware = MemoryPersistenceMiddleware(storage=storage)
    await middleware.after(state)

    records = await storage.find_records("portfolio_entry")
    assert len(records) == 1
    data = records[0].data
    assert data["role_title"] == "Backend Engineer"
    assert data["company_name"] == "Acme Corp"
    assert data["role_category"] == RoleCategory.BACKEND.value


@pytest.mark.asyncio
async def test_persistence_middleware_saves_pipeline_metrics(storage: MemoryStorage) -> None:
    """after() should persist pipeline metrics keyed by thread_id."""
    state = make_state()
    state.metrics = PipelineMetrics(
        total_duration_seconds=400.0,
        quality_score=88.0,
        total_api_cost_gbp=3.0,
    )

    middleware = MemoryPersistenceMiddleware(storage=storage)
    await middleware.after(state)

    metrics = await storage.get_metrics(state.thread_id)
    assert metrics is not None
    assert abs(metrics.quality_score - 88.0) < 0.001
    assert abs(metrics.total_duration_seconds - 400.0) < 0.001


@pytest.mark.asyncio
async def test_persistence_middleware_does_not_crash_on_storage_error() -> None:
    """after() should catch storage errors and continue without crashing."""
    bad_storage = MagicMock(spec=MemoryStorage)
    bad_storage.save_record = AsyncMock(side_effect=RuntimeError("Disk full"))
    bad_storage.save_metrics = AsyncMock(side_effect=RuntimeError("Disk full"))

    profile = make_company_profile("Acme Corp")
    state = make_state(company_profile=profile)

    middleware = MemoryPersistenceMiddleware(storage=bad_storage)
    # Should not raise — errors are caught and logged
    result = await middleware.after(state)
    assert result is state


@pytest.mark.asyncio
async def test_persistence_middleware_skips_profile_when_not_set(
    storage: MemoryStorage,
) -> None:
    """after() should not write a company_profile record when company_profile is None."""
    state = make_state(company_profile=None)

    middleware = MemoryPersistenceMiddleware(storage=storage)
    await middleware.after(state)

    records = await storage.find_records("company_profile")
    assert len(records) == 0


@pytest.mark.asyncio
async def test_persistence_middleware_skips_portfolio_when_not_set(
    storage: MemoryStorage,
) -> None:
    """after() should not write a portfolio_entry record when publish_result is None."""
    state = make_state(publish_result=None)

    middleware = MemoryPersistenceMiddleware(storage=storage)
    await middleware.after(state)

    records = await storage.find_records("portfolio_entry")
    assert len(records) == 0
