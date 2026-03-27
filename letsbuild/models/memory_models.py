"""Pydantic v2 models for Layer 8: Memory + ReasoningBank."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class VerdictOutcome(StrEnum):
    """Outcome of a JUDGE verdict after a Code Forge run."""

    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"


class JudgeVerdict(BaseModel):
    """Structured verdict recorded after every Code Forge run."""

    model_config = ConfigDict(strict=True)

    verdict_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this verdict.",
    )
    run_id: str = Field(
        description="Pipeline run ID this verdict belongs to.",
    )
    outcome: VerdictOutcome = Field(
        description="Overall outcome of the Code Forge run.",
    )
    sandbox_passed: bool = Field(
        description="Whether all sandbox validation commands passed.",
    )
    quality_score: float = Field(
        description="Quality score from QualityGate (0.0-100.0).",
    )
    retry_count_total: int = Field(
        description="Total number of retries across all agents in the run.",
    )
    api_cost_gbp: float = Field(
        description="Total API cost for this run in GBP.",
    )
    generation_time_seconds: float = Field(
        description="Total wall-clock time for code generation in seconds.",
    )
    failure_reasons: list[str] = Field(
        default_factory=list,
        description="List of reasons if the run failed or partially failed.",
    )
    judged_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this verdict was recorded (UTC).",
    )


class DistilledPattern(BaseModel):
    """A learnable pattern extracted from JUDGE verdicts via DISTILL."""

    model_config = ConfigDict(strict=True)

    pattern_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this pattern.",
    )
    pattern_text: str = Field(
        description="Human-readable description of the learned pattern.",
    )
    source_verdicts: list[str] = Field(
        description="List of verdict IDs that contributed to this pattern.",
    )
    confidence: float = Field(
        description="Confidence score for this pattern (0.0-100.0).",
    )
    tech_stack_tags: list[str] = Field(
        description="Tech stack tags this pattern applies to.",
    )
    success_rate: float = Field(
        description="Success rate of runs using this pattern (0.0-100.0).",
    )
    sample_count: int = Field(
        description="Number of runs that contributed to this pattern.",
    )
    distilled_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this pattern was distilled (UTC).",
    )


class MemoryRecord(BaseModel):
    """A generic record stored in the memory subsystem."""

    model_config = ConfigDict(strict=True)

    record_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this memory record.",
    )
    record_type: str = Field(
        description=(
            "Type of record: 'company_profile', 'user_profile', "
            "'portfolio_entry', or 'reasoning_pattern'."
        ),
    )
    data: dict[str, object] = Field(
        description="Arbitrary data payload for this record.",
    )
    embedding: list[float] | None = Field(
        default=None,
        description="HNSW embedding vector for similarity search.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this record was created (UTC).",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="When this record expires (UTC), or None for permanent.",
    )


class ReasoningBankQuery(BaseModel):
    """Query parameters for searching the ReasoningBank."""

    model_config = ConfigDict(strict=True)

    query_text: str = Field(
        description="Natural language query to search for similar patterns.",
    )
    tech_stack_filter: list[str] = Field(
        default_factory=list,
        description="Filter results to patterns matching these tech stack tags.",
    )
    top_k: int = Field(
        default=5,
        description="Maximum number of results to return.",
    )
    min_confidence: float = Field(
        default=50.0,
        description="Minimum confidence threshold for returned patterns (0.0-100.0).",
    )
