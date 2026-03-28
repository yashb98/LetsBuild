"""MemoryRetrieval middleware — queries memory for cached data before pipeline layers run.

Fifth middleware in the 10-stage chain. Retrieves cached CompanyProfile, portfolio
registry entries, and ReasoningBank patterns and injects them into PipelineState so
downstream layers can skip expensive work or bias toward proven designs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from letsbuild.harness.middleware import Middleware
from letsbuild.memory.hnsw_index import HNSWIndex, simple_text_embedding
from letsbuild.memory.storage import MemoryStorage  # noqa: TC001
from letsbuild.models.intelligence_models import CompanyProfile

if TYPE_CHECKING:
    from letsbuild.pipeline.state import PipelineState

__all__ = ["MemoryRetrievalMiddleware"]

logger = structlog.get_logger(__name__)

_COMPANY_PROFILE_FRESHNESS_DAYS = 30


class MemoryRetrievalMiddleware(Middleware):
    """Retrieve cached memory records and inject them into PipelineState before layer execution.

    before():
        1. If jd_analysis has a company_name, look up a cached CompanyProfile. If the
           record is younger than 30 days, inject it into state.company_profile so L2
           research can be skipped.
        2. Query the portfolio registry to surface existing similar projects.
        3. If an HNSW index is available and the JD has text context, query for
           relevant ReasoningBank patterns and log them for L4/L5 to consume.

    after(): No-op — returns state unchanged.
    """

    def __init__(
        self,
        storage: MemoryStorage,
        hnsw_index: HNSWIndex | None = None,
    ) -> None:
        self._storage = storage
        self._hnsw_index = hnsw_index
        self._log = structlog.get_logger(component="MemoryRetrievalMiddleware")

    async def before(self, state: PipelineState) -> PipelineState:
        """Retrieve cached company profile, portfolio entries, and ReasoningBank patterns.

        All retrieval operations are wrapped in try/except so that memory failures
        never crash the pipeline — a warning is logged and the run continues without
        the cached data.

        Args:
            state: The current pipeline state.

        Returns:
            The pipeline state, possibly with company_profile populated from cache.
        """
        # --- 1. Cached CompanyProfile ---
        if state.jd_analysis is not None and state.jd_analysis.company_name:
            company_name = state.jd_analysis.company_name
            try:
                await self._retrieve_company_profile(state, company_name)
            except Exception as exc:
                await self._log.awarning(
                    "memory_retrieval.company_profile.error",
                    company_name=company_name,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        # --- 2. Portfolio registry check ---
        try:
            await self._retrieve_portfolio_entries(state)
        except Exception as exc:
            await self._log.awarning(
                "memory_retrieval.portfolio.error",
                error=str(exc),
                error_type=type(exc).__name__,
            )

        # --- 3. ReasoningBank patterns via HNSW ---
        if self._hnsw_index is not None:
            try:
                await self._retrieve_reasoning_patterns(state)
            except Exception as exc:
                await self._log.awarning(
                    "memory_retrieval.reasoning_bank.error",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        return state

    async def after(self, state: PipelineState) -> PipelineState:
        """No-op post-processing hook.

        Args:
            state: The current pipeline state.

        Returns:
            The pipeline state unchanged.
        """
        return state

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _retrieve_company_profile(self, state: PipelineState, company_name: str) -> None:
        """Look up and inject a fresh CompanyProfile cache hit."""
        records = await self._storage.find_records("company_profile", limit=50)

        # Find the most recent record for this company
        matching = [
            r
            for r in records
            if isinstance(r.data.get("company_name"), str)
            and r.data["company_name"].lower() == company_name.lower()
        ]
        if not matching:
            await self._log.ainfo(
                "memory_retrieval.company_profile.miss",
                company_name=company_name,
            )
            return

        # Use the most recently created record
        record = max(matching, key=lambda r: r.created_at)
        age_days = (datetime.now(UTC) - record.created_at).days

        if age_days > _COMPANY_PROFILE_FRESHNESS_DAYS:
            await self._log.ainfo(
                "memory_retrieval.company_profile.stale",
                company_name=company_name,
                age_days=age_days,
                threshold_days=_COMPANY_PROFILE_FRESHNESS_DAYS,
            )
            return

        # Deserialise and inject
        try:
            profile = CompanyProfile.model_validate(record.data)
        except Exception as exc:
            await self._log.awarning(
                "memory_retrieval.company_profile.deserialise_error",
                record_id=record.record_id,
                error=str(exc),
            )
            return

        # Only inject if the pipeline has not already resolved a profile
        if state.company_profile is None:
            state.company_profile = profile
            await self._log.ainfo(
                "memory_retrieval.company_profile.hit",
                company_name=company_name,
                record_id=record.record_id,
                age_days=age_days,
            )

    async def _retrieve_portfolio_entries(self, state: PipelineState) -> None:
        """Query the portfolio registry for existing projects."""
        records = await self._storage.find_records("portfolio_entry", limit=20)

        if records:
            await self._log.ainfo(
                "memory_retrieval.portfolio.found",
                count=len(records),
                thread_id=state.thread_id,
            )
        else:
            await self._log.ainfo(
                "memory_retrieval.portfolio.empty",
                thread_id=state.thread_id,
            )

    async def _retrieve_reasoning_patterns(self, state: PipelineState) -> None:
        """Query HNSW index for relevant ReasoningBank patterns."""
        # Build a query text from available JD context
        query_parts: list[str] = []
        if state.jd_analysis is not None:
            jd = state.jd_analysis
            query_parts.append(jd.role_title)
            query_parts.append(jd.role_category.value)
            if jd.tech_stack.languages:
                query_parts.extend(jd.tech_stack.languages[:3])
            if jd.tech_stack.frameworks:
                query_parts.extend(jd.tech_stack.frameworks[:3])
        elif state.jd_text:
            query_parts.append(state.jd_text[:500])

        if not query_parts:
            return

        query_text = " ".join(query_parts)
        embedding = simple_text_embedding(query_text)

        index = self._hnsw_index
        if index is None or len(index) == 0:
            await self._log.ainfo(
                "memory_retrieval.reasoning_bank.empty_index",
                thread_id=state.thread_id,
            )
            return

        results = index.query(embedding, top_k=5)
        if results:
            pattern_ids = [r[0] for r in results]
            await self._log.ainfo(
                "memory_retrieval.reasoning_bank.patterns_found",
                count=len(results),
                pattern_ids=pattern_ids,
                thread_id=state.thread_id,
            )
        else:
            await self._log.ainfo(
                "memory_retrieval.reasoning_bank.no_patterns",
                thread_id=state.thread_id,
            )
