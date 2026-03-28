"""MemoryPersistence middleware — async write of results to memory after layer execution.

Ninth middleware in the 10-stage chain. After each pipeline layer completes, this
middleware persists CompanyProfile, portfolio entries, and pipeline metrics to the
MemoryStorage SQLite database for future retrieval.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog

from letsbuild.harness.middleware import Middleware
from letsbuild.memory.storage import MemoryStorage  # noqa: TC001
from letsbuild.models.memory_models import MemoryRecord

if TYPE_CHECKING:
    from letsbuild.pipeline.state import PipelineState

__all__ = ["MemoryPersistenceMiddleware"]

logger = structlog.get_logger(__name__)

_COMPANY_PROFILE_TTL_DAYS = 90


class MemoryPersistenceMiddleware(Middleware):
    """Persist pipeline results to memory storage after each layer completes.

    before(): No-op — returns state unchanged.

    after():
        1. If state.company_profile is set, save it as a MemoryRecord with
           record_type="company_profile" and a 90-day TTL.
        2. If state.publish_result is set, save it as a MemoryRecord with
           record_type="portfolio_entry" (no expiry — permanent).
        3. Save state.metrics as pipeline_metrics keyed by thread_id.
        4. Log what was persisted.

    All persistence operations are wrapped in try/except so memory failures
    never crash the pipeline — warnings are logged and execution continues.
    """

    def __init__(self, storage: MemoryStorage) -> None:
        self._storage = storage
        self._log = structlog.get_logger(component="MemoryPersistenceMiddleware")

    async def before(self, state: PipelineState) -> PipelineState:
        """No-op pre-processing hook.

        Args:
            state: The current pipeline state.

        Returns:
            The pipeline state unchanged.
        """
        return state

    async def after(self, state: PipelineState) -> PipelineState:
        """Persist CompanyProfile, portfolio entry, and metrics to memory storage.

        All write operations are wrapped in try/except so that storage failures
        never crash the pipeline. Warnings are logged for each failed write.

        Args:
            state: The current pipeline state (with layer results).

        Returns:
            The pipeline state unchanged.
        """
        persisted: list[str] = []

        # --- 1. CompanyProfile ---
        if state.company_profile is not None:
            try:
                await self._persist_company_profile(state)
                persisted.append("company_profile")
            except Exception as exc:
                await self._log.awarning(
                    "memory_persistence.company_profile.error",
                    thread_id=state.thread_id,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        # --- 2. PublishResult (portfolio entry) ---
        if state.publish_result is not None:
            try:
                await self._persist_portfolio_entry(state)
                persisted.append("portfolio_entry")
            except Exception as exc:
                await self._log.awarning(
                    "memory_persistence.portfolio_entry.error",
                    thread_id=state.thread_id,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        # --- 3. Pipeline metrics ---
        try:
            await self._persist_metrics(state)
            persisted.append("pipeline_metrics")
        except Exception as exc:
            await self._log.awarning(
                "memory_persistence.metrics.error",
                thread_id=state.thread_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )

        if persisted:
            await self._log.ainfo(
                "memory_persistence.persisted",
                thread_id=state.thread_id,
                persisted=persisted,
                layer=state.current_layer,
            )

        return state

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _persist_company_profile(self, state: PipelineState) -> None:
        """Save CompanyProfile as a MemoryRecord with a 90-day TTL."""
        profile = state.company_profile
        assert profile is not None  # guarded by caller

        now = datetime.now(UTC)
        expires_at = now + timedelta(days=_COMPANY_PROFILE_TTL_DAYS)

        # Serialise via model_dump for Pydantic v2 compatibility
        profile_data: dict[str, object] = profile.model_dump(mode="json")

        record = MemoryRecord(
            record_type="company_profile",
            data=profile_data,
            created_at=now,
            expires_at=expires_at,
        )
        await self._storage.save_record(record)
        await self._log.ainfo(
            "memory_persistence.company_profile.saved",
            company_name=profile.company_name,
            record_id=record.record_id,
            expires_at=expires_at.isoformat(),
        )

    async def _persist_portfolio_entry(self, state: PipelineState) -> None:
        """Save PublishResult as a permanent MemoryRecord in the portfolio registry."""
        publish_result = state.publish_result
        assert publish_result is not None  # guarded by caller

        entry_data: dict[str, object] = publish_result.model_dump(mode="json")

        # Enrich with JD context if available
        if state.jd_analysis is not None:
            entry_data["role_title"] = state.jd_analysis.role_title
            entry_data["company_name"] = state.jd_analysis.company_name
            entry_data["role_category"] = state.jd_analysis.role_category.value

        record = MemoryRecord(
            record_type="portfolio_entry",
            data=entry_data,
            created_at=datetime.now(UTC),
            expires_at=None,  # permanent
        )
        await self._storage.save_record(record)
        await self._log.ainfo(
            "memory_persistence.portfolio_entry.saved",
            repo_url=publish_result.repo_url,
            record_id=record.record_id,
        )

    async def _persist_metrics(self, state: PipelineState) -> None:
        """Save pipeline metrics keyed by thread_id."""
        await self._storage.save_metrics(state.thread_id, state.metrics)
        await self._log.ainfo(
            "memory_persistence.metrics.saved",
            thread_id=state.thread_id,
            quality_score=state.metrics.quality_score,
            total_duration_seconds=state.metrics.total_duration_seconds,
        )
