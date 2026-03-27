"""Shared models used across all pipeline layers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ErrorCategory(str, Enum):
    """Category of error for structured error handling."""

    TRANSIENT = "transient"
    VALIDATION = "validation"
    BUSINESS = "business"
    PERMISSION = "permission"


class StructuredError(BaseModel):
    """Structured error returned by every tool and sub-agent on failure."""

    model_config = ConfigDict(strict=True)

    error_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this error instance.",
    )
    error_category: ErrorCategory = Field(
        description="Category of the error for routing retry logic."
    )
    is_retryable: bool = Field(
        description="Whether this error can be retried."
    )
    message: str = Field(
        description="Human-readable error message."
    )
    partial_results: dict[str, object] | None = Field(
        default=None,
        description="Any partial results obtained before failure.",
    )
    attempted_query: str | None = Field(
        default=None,
        description="The query or operation that was attempted.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the error occurred (UTC).",
    )


class GateResult(BaseModel):
    """Result from a compiled policy gate evaluation."""

    model_config = ConfigDict(strict=True)

    passed: bool = Field(
        description="Whether the gate check passed."
    )
    reason: str = Field(
        description="Explanation of why the gate passed or failed."
    )
    blocking: bool = Field(
        description="Whether failure should halt the pipeline."
    )
    gate_name: str = Field(
        description="Name of the gate that produced this result.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the gate was evaluated (UTC).",
    )


class PipelineMetrics(BaseModel):
    """Metrics collected during a pipeline run."""

    model_config = ConfigDict(strict=True)

    total_duration_seconds: float = Field(
        default=0.0,
        description="Total wall-clock time for the pipeline run in seconds.",
    )
    layer_durations: dict[str, float] = Field(
        default_factory=dict,
        description="Duration in seconds for each layer, keyed by layer name.",
    )
    total_tokens_used: int = Field(
        default=0,
        description="Total LLM tokens consumed across all layers.",
    )
    total_api_cost_gbp: float = Field(
        default=0.0,
        description="Total API cost in GBP.",
    )
    retries_by_layer: dict[str, int] = Field(
        default_factory=dict,
        description="Number of retries per layer.",
    )
    quality_score: float = Field(
        default=0.0,
        description="Final quality score from QualityGate (0.0-100.0).",
    )


class BudgetInfo(BaseModel):
    """Budget tracking for a pipeline run."""

    model_config = ConfigDict(strict=True)

    budget_limit_gbp: float = Field(
        default=50.0,
        description="Maximum allowed API cost in GBP for this run.",
    )
    spent_gbp: float = Field(
        default=0.0,
        description="Amount spent so far in GBP.",
    )
    remaining_gbp: float = Field(
        default=50.0,
        description="Budget remaining in GBP.",
    )
    cost_by_model: dict[str, float] = Field(
        default_factory=dict,
        description="Cost breakdown by model name.",
    )

    def record_cost(self, model: str, cost: float) -> None:
        """Record a cost against a specific model."""
        self.spent_gbp += cost
        self.remaining_gbp = self.budget_limit_gbp - self.spent_gbp
        self.cost_by_model[model] = self.cost_by_model.get(model, 0.0) + cost

    def is_over_budget(self) -> bool:
        """Check if spending has exceeded the budget limit."""
        return self.spent_gbp > self.budget_limit_gbp


class ModelConfig(BaseModel):
    """Configuration for an LLM model used in the pipeline."""

    model_config = ConfigDict(strict=True)

    model_id: str = Field(
        description="Model identifier (e.g. 'claude-sonnet-4-6').",
    )
    max_tokens: int = Field(
        default=4096,
        description="Maximum tokens for model responses.",
    )
    temperature: float = Field(
        default=0.0,
        description="Sampling temperature.",
    )
    cost_per_1k_input: float = Field(
        default=0.0,
        description="Cost per 1000 input tokens in GBP.",
    )
    cost_per_1k_output: float = Field(
        default=0.0,
        description="Cost per 1000 output tokens in GBP.",
    )
