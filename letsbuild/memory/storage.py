"""Async SQLite storage layer for all Layer 8 memory types.

Tables:
  - judge_verdicts
  - distilled_patterns
  - memory_records (company_profiles, user_profiles, portfolio_registry)
  - pipeline_metrics
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from types import TracebackType

import aiosqlite
import structlog

from letsbuild.models.memory_models import (
    DistilledPattern,
    JudgeVerdict,
    MemoryRecord,
    VerdictOutcome,
)
from letsbuild.models.shared import PipelineMetrics

__all__ = ["MemoryStorage"]

logger = structlog.get_logger(__name__)

_CREATE_JUDGE_VERDICTS = """
CREATE TABLE IF NOT EXISTS judge_verdicts (
    verdict_id      TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL,
    outcome         TEXT NOT NULL,
    sandbox_passed  INTEGER NOT NULL,
    quality_score   REAL NOT NULL,
    retry_count_total INTEGER NOT NULL,
    api_cost_gbp    REAL NOT NULL,
    generation_time_seconds REAL NOT NULL,
    failure_reasons TEXT NOT NULL,
    judged_at       TEXT NOT NULL
)
"""

_CREATE_JUDGE_VERDICTS_IDX = """
CREATE INDEX IF NOT EXISTS idx_judge_verdicts_judged_at
    ON judge_verdicts (judged_at)
"""

_CREATE_DISTILLED_PATTERNS = """
CREATE TABLE IF NOT EXISTS distilled_patterns (
    pattern_id      TEXT PRIMARY KEY,
    pattern_text    TEXT NOT NULL,
    source_verdicts TEXT NOT NULL,
    confidence      REAL NOT NULL,
    tech_stack_tags TEXT NOT NULL,
    success_rate    REAL NOT NULL,
    sample_count    INTEGER NOT NULL,
    distilled_at    TEXT NOT NULL
)
"""

_CREATE_DISTILLED_PATTERNS_IDX = """
CREATE INDEX IF NOT EXISTS idx_distilled_patterns_confidence
    ON distilled_patterns (confidence)
"""

_CREATE_MEMORY_RECORDS = """
CREATE TABLE IF NOT EXISTS memory_records (
    record_id   TEXT PRIMARY KEY,
    record_type TEXT NOT NULL,
    data        TEXT NOT NULL,
    embedding   TEXT,
    created_at  TEXT NOT NULL,
    expires_at  TEXT
)
"""

_CREATE_MEMORY_RECORDS_TYPE_IDX = """
CREATE INDEX IF NOT EXISTS idx_memory_records_record_type
    ON memory_records (record_type)
"""

_CREATE_MEMORY_RECORDS_EXPIRES_IDX = """
CREATE INDEX IF NOT EXISTS idx_memory_records_expires_at
    ON memory_records (expires_at)
"""

_CREATE_PIPELINE_METRICS = """
CREATE TABLE IF NOT EXISTS pipeline_metrics (
    run_id                  TEXT PRIMARY KEY,
    total_duration_seconds  REAL NOT NULL,
    layer_durations         TEXT NOT NULL,
    total_tokens_used       INTEGER NOT NULL,
    total_api_cost_gbp      REAL NOT NULL,
    retries_by_layer        TEXT NOT NULL,
    quality_score           REAL NOT NULL
)
"""


class MemoryStorage:
    """Async SQLite wrapper for all LetsBuild memory types."""

    def __init__(self, db_path: str = "letsbuild_memory.db") -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def init_db(self) -> None:
        """Open the database connection and create tables if they do not exist."""
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

        for stmt in (
            _CREATE_JUDGE_VERDICTS,
            _CREATE_JUDGE_VERDICTS_IDX,
            _CREATE_DISTILLED_PATTERNS,
            _CREATE_DISTILLED_PATTERNS_IDX,
            _CREATE_MEMORY_RECORDS,
            _CREATE_MEMORY_RECORDS_TYPE_IDX,
            _CREATE_MEMORY_RECORDS_EXPIRES_IDX,
            _CREATE_PIPELINE_METRICS,
        ):
            await self._conn.execute(stmt)

        await self._conn.commit()
        logger.info("memory_storage.init_db.done", db_path=self._db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            logger.info("memory_storage.closed", db_path=self._db_path)

    # Context manager support

    async def __aenter__(self) -> MemoryStorage:
        await self.init_db()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _db(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("MemoryStorage not initialised — call await init_db() first.")
        return self._conn

    # ------------------------------------------------------------------
    # judge_verdicts
    # ------------------------------------------------------------------

    async def save_verdict(self, verdict: JudgeVerdict) -> None:
        """Insert or replace a JudgeVerdict row."""
        db = self._db()
        await db.execute(
            """
            INSERT OR REPLACE INTO judge_verdicts
                (verdict_id, run_id, outcome, sandbox_passed, quality_score,
                 retry_count_total, api_cost_gbp, generation_time_seconds,
                 failure_reasons, judged_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                verdict.verdict_id,
                verdict.run_id,
                verdict.outcome.value,
                int(verdict.sandbox_passed),
                verdict.quality_score,
                verdict.retry_count_total,
                verdict.api_cost_gbp,
                verdict.generation_time_seconds,
                json.dumps(verdict.failure_reasons),
                verdict.judged_at.isoformat(),
            ),
        )
        await db.commit()
        logger.debug("memory_storage.save_verdict", verdict_id=verdict.verdict_id)

    async def get_verdict(self, verdict_id: str) -> JudgeVerdict | None:
        """Fetch a single JudgeVerdict by ID, or None if not found."""
        db = self._db()
        async with db.execute(
            "SELECT * FROM judge_verdicts WHERE verdict_id = ?", (verdict_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_verdict(row)

    async def list_verdicts(self, limit: int = 50) -> list[JudgeVerdict]:
        """Return the most recent verdicts ordered by judged_at DESC."""
        db = self._db()
        async with db.execute(
            "SELECT * FROM judge_verdicts ORDER BY judged_at DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_verdict(r) for r in rows]

    async def get_verdicts_since(self, since: datetime) -> list[JudgeVerdict]:
        """Return all verdicts judged at or after *since*."""
        db = self._db()
        async with db.execute(
            "SELECT * FROM judge_verdicts WHERE judged_at >= ? ORDER BY judged_at ASC",
            (since.isoformat(),),
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_verdict(r) for r in rows]

    async def count_verdicts(self) -> int:
        """Return the total number of stored verdicts."""
        db = self._db()
        async with db.execute("SELECT COUNT(*) FROM judge_verdicts") as cursor:
            row = await cursor.fetchone()
        return int(row[0]) if row else 0

    @staticmethod
    def _row_to_verdict(row: Any) -> JudgeVerdict:
        return JudgeVerdict(
            verdict_id=row["verdict_id"],
            run_id=row["run_id"],
            outcome=VerdictOutcome(row["outcome"]),
            sandbox_passed=bool(row["sandbox_passed"]),
            quality_score=row["quality_score"],
            retry_count_total=row["retry_count_total"],
            api_cost_gbp=row["api_cost_gbp"],
            generation_time_seconds=row["generation_time_seconds"],
            failure_reasons=json.loads(row["failure_reasons"]),
            judged_at=datetime.fromisoformat(row["judged_at"]),
        )

    # ------------------------------------------------------------------
    # distilled_patterns
    # ------------------------------------------------------------------

    async def save_pattern(self, pattern: DistilledPattern) -> None:
        """Insert or replace a DistilledPattern row."""
        db = self._db()
        await db.execute(
            """
            INSERT OR REPLACE INTO distilled_patterns
                (pattern_id, pattern_text, source_verdicts, confidence,
                 tech_stack_tags, success_rate, sample_count, distilled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pattern.pattern_id,
                pattern.pattern_text,
                json.dumps(pattern.source_verdicts),
                pattern.confidence,
                json.dumps(pattern.tech_stack_tags),
                pattern.success_rate,
                pattern.sample_count,
                pattern.distilled_at.isoformat(),
            ),
        )
        await db.commit()
        logger.debug("memory_storage.save_pattern", pattern_id=pattern.pattern_id)

    async def get_pattern(self, pattern_id: str) -> DistilledPattern | None:
        """Fetch a single DistilledPattern by ID, or None if not found."""
        db = self._db()
        async with db.execute(
            "SELECT * FROM distilled_patterns WHERE pattern_id = ?", (pattern_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_pattern(row)

    async def list_patterns(
        self,
        tech_stack_filter: list[str] | None = None,
        min_confidence: float = 0.0,
    ) -> list[DistilledPattern]:
        """Return patterns filtered by minimum confidence.

        When *tech_stack_filter* is provided, only patterns whose
        tech_stack_tags overlap with the filter are returned (post-query
        filtering in Python to avoid complex JSON SQL).
        """
        db = self._db()
        async with db.execute(
            "SELECT * FROM distilled_patterns WHERE confidence >= ? ORDER BY confidence DESC",
            (min_confidence,),
        ) as cursor:
            rows = await cursor.fetchall()

        patterns = [self._row_to_pattern(r) for r in rows]

        if tech_stack_filter:
            filter_set = {tag.lower() for tag in tech_stack_filter}
            patterns = [
                p
                for p in patterns
                if filter_set.intersection({t.lower() for t in p.tech_stack_tags})
            ]

        return patterns

    @staticmethod
    def _row_to_pattern(row: Any) -> DistilledPattern:
        return DistilledPattern(
            pattern_id=row["pattern_id"],
            pattern_text=row["pattern_text"],
            source_verdicts=json.loads(row["source_verdicts"]),
            confidence=row["confidence"],
            tech_stack_tags=json.loads(row["tech_stack_tags"]),
            success_rate=row["success_rate"],
            sample_count=row["sample_count"],
            distilled_at=datetime.fromisoformat(row["distilled_at"]),
        )

    # ------------------------------------------------------------------
    # memory_records
    # ------------------------------------------------------------------

    async def save_record(self, record: MemoryRecord) -> None:
        """Insert or replace a MemoryRecord row."""
        db = self._db()
        await db.execute(
            """
            INSERT OR REPLACE INTO memory_records
                (record_id, record_type, data, embedding, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.record_id,
                record.record_type,
                json.dumps(record.data),
                json.dumps(record.embedding) if record.embedding is not None else None,
                record.created_at.isoformat(),
                record.expires_at.isoformat() if record.expires_at is not None else None,
            ),
        )
        await db.commit()
        logger.debug("memory_storage.save_record", record_id=record.record_id)

    async def get_record(self, record_id: str) -> MemoryRecord | None:
        """Fetch a single MemoryRecord by ID, or None if not found."""
        db = self._db()
        async with db.execute(
            "SELECT * FROM memory_records WHERE record_id = ?", (record_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    async def find_records(self, record_type: str, limit: int = 50) -> list[MemoryRecord]:
        """Return records of a given type ordered by created_at DESC."""
        db = self._db()
        async with db.execute(
            "SELECT * FROM memory_records WHERE record_type = ? ORDER BY created_at DESC LIMIT ?",
            (record_type, limit),
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_record(r) for r in rows]

    async def delete_expired(self) -> int:
        """Delete all records whose expires_at is in the past. Returns count deleted."""
        now_iso = datetime.now(UTC).isoformat()
        db = self._db()
        async with db.execute(
            "DELETE FROM memory_records WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now_iso,),
        ) as cursor:
            count = cursor.rowcount
        await db.commit()
        logger.info("memory_storage.delete_expired", deleted=count)
        return count

    @staticmethod
    def _row_to_record(row: Any) -> MemoryRecord:
        raw_embedding = row["embedding"]
        embedding: list[float] | None = json.loads(raw_embedding) if raw_embedding else None
        raw_expires = row["expires_at"]
        expires_at: datetime | None = datetime.fromisoformat(raw_expires) if raw_expires else None
        return MemoryRecord(
            record_id=row["record_id"],
            record_type=row["record_type"],
            data=json.loads(row["data"]),
            embedding=embedding,
            created_at=datetime.fromisoformat(row["created_at"]),
            expires_at=expires_at,
        )

    # ------------------------------------------------------------------
    # pipeline_metrics
    # ------------------------------------------------------------------

    async def save_metrics(self, run_id: str, metrics: PipelineMetrics) -> None:
        """Insert or replace a PipelineMetrics row keyed by run_id."""
        db = self._db()
        await db.execute(
            """
            INSERT OR REPLACE INTO pipeline_metrics
                (run_id, total_duration_seconds, layer_durations,
                 total_tokens_used, total_api_cost_gbp, retries_by_layer, quality_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                metrics.total_duration_seconds,
                json.dumps(metrics.layer_durations),
                metrics.total_tokens_used,
                metrics.total_api_cost_gbp,
                json.dumps(metrics.retries_by_layer),
                metrics.quality_score,
            ),
        )
        await db.commit()
        logger.debug("memory_storage.save_metrics", run_id=run_id)

    async def get_metrics(self, run_id: str) -> PipelineMetrics | None:
        """Fetch PipelineMetrics for a given run_id, or None if not found."""
        db = self._db()
        async with db.execute(
            "SELECT * FROM pipeline_metrics WHERE run_id = ?", (run_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return PipelineMetrics(
            total_duration_seconds=row["total_duration_seconds"],
            layer_durations=json.loads(row["layer_durations"]),
            total_tokens_used=row["total_tokens_used"],
            total_api_cost_gbp=row["total_api_cost_gbp"],
            retries_by_layer=json.loads(row["retries_by_layer"]),
            quality_score=row["quality_score"],
        )
