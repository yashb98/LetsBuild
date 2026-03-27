"""Shared Pydantic models used across all layers of the LetsBuild pipeline.

This module is the foundation — every other model file imports from here.
All models use ConfigDict(strict=True) and full Field(description=...) annotations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "StructuredError",
    "GateResult",
    "PipelineMetrics",
    "BudgetInfo",
    "ModelConfig",
]


class StructuredError(BaseModel):
    """Structured error returned by every tool and agent on failure.

    All tool failures must return this model rather than raising bare exceptions.
    The error_category and is_retryable fields drive the pipeline retry logic.
    """

    model_config = ConfigDict(strict=True)

    error_category: Literal["transient", "validation", "business", "permission"] = Field(
        description=(
            "Category of the error. 'transient' = temporary (network, timeout); "
            "'validation' = bad input data; 'business' = rule violated; "
            "'permission' = access denied."
        )
    )
    is_retryable: bool = Field(
        description=(
            "Whether the operation can be retried. Transient errors are usually "
            "retryable; validation/permission errors are usually not."
        )
    )
    message: str = Field(
        description="Human-readable description of what went wrong."
    )
    partial_results: dict | None = Field(
        default=None,
        description=(
            "Any partial data recovered before the failure. Allows downstream "
            "layers to make use of incomplete results when possible."
        ),
    )
    attempted_query: str | None = Field(
        default=None,
        description=(
            "The query, URL, or operation string that was attempted when the "
            "error occurred. Used for debugging and retry logic."
        ),
    )
    timestamp: datetime = Field(
        description=(
            "UTC timestamp of when the error occurred. Must be timezone-aware "
            "with UTC offset."
        )
    )


class GateResult(BaseModel):
    """Result returned by all compiled policy gates.

    Gates are deterministic Python code (never LLM calls). There are four gates:
    PublishGate, SecurityGate, QualityGate, and BudgetGate. Each returns this model.
    """

    model_config = ConfigDict(strict=True)

    passed: bool = Field(
        description="Whether the gate check passed. False means the gate was triggered."
    )
    gate_name: str = Field(
        description=(
            "Identifier of the gate that produced this result, e.g. 'PublishGate', "
            "'SecurityGate', 'QualityGate', 'BudgetGate'."
        )
    )
    reason: str = Field(
        description=(
            "Human-readable explanation of why the gate passed or failed. "
            "Shown in pipeline logs and user notifications."
        )
    )
    blocking: bool = Field(
        description=(
            "If True and passed=False, the pipeline is halted immediately. "
            "Non-blocking gate failures are logged as warnings but do not stop execution."
        )
    )
    score: float | None = Field(
        default=None,
        description=(
            "Quality score in range [0.0, 100.0]. Populated by QualityGate only. "
            "None for gates that do not compute a score."
        ),
    )


class PipelineMetrics(BaseModel):
    """Timing, cost, and quality metrics tracked across the full pipeline run.

    Accumulated by the middleware chain and written to SQLite after pipeline completion.
    """

    model_config = ConfigDict(strict=True)

    start_time: datetime | None = Field(
        default=None,
        description="UTC timestamp when the pipeline run started.",
    )
    end_time: datetime | None = Field(
        default=None,
        description="UTC timestamp when the pipeline run completed or was aborted.",
    )
    total_api_cost_gbp: float = Field(
        default=0.0,
        description=(
            "Total API cost for this run in GBP (British pounds). "
            "Sum of all model invocation costs across all layers."
        ),
    )
    total_tokens_in: int = Field(
        default=0,
        description="Total input tokens consumed across all API calls in this run.",
    )
    total_tokens_out: int = Field(
        default=0,
        description="Total output tokens generated across all API calls in this run.",
    )
    layer_durations: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Wall-clock duration in seconds for each layer, keyed by layer name "
            "(e.g. {'intake': 4.2, 'intelligence': 12.7})."
        ),
    )
    retry_counts: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Number of retries performed in each layer, keyed by layer name "
            "(e.g. {'forge': 2}). Layers with zero retries may be omitted."
        ),
    )
    quality_score: float | None = Field(
        default=None,
        description=(
            "Overall quality score for this run in range [0.0, 100.0]. "
            "Set by the QualityGate after code review. None if the gate did not run."
        ),
    )


class BudgetInfo(BaseModel):
    """Budget tracking for a single pipeline run.

    Enforced by the BudgetGate. All monetary values are in GBP.
    """

    model_config = ConfigDict(strict=True)

    max_budget_gbp: float = Field(
        description=(
            "Maximum allowed API spend for this run in GBP. Configured per-run "
            "via letsbuild.yaml or the CLI --budget flag."
        )
    )
    spent_gbp: float = Field(
        default=0.0,
        description=(
            "Total amount spent so far in GBP. Updated after each API call. "
            "BudgetGate halts the pipeline when this reaches max_budget_gbp."
        ),
    )
    remaining_gbp: float = Field(
        default=0.0,
        description=(
            "Remaining budget in GBP (max_budget_gbp - spent_gbp). "
            "Computed automatically by the model validator."
        ),
    )
    cost_by_model: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Breakdown of spend in GBP by model ID "
            "(e.g. {'claude-opus-4-20250514': 3.12, 'claude-sonnet-4-20250514': 1.45})."
        ),
    )
    cost_by_layer: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Breakdown of spend in GBP by pipeline layer name "
            "(e.g. {'intelligence': 1.20, 'forge': 2.80})."
        ),
    )

    @model_validator(mode="after")
    def compute_remaining(self) -> BudgetInfo:
        """Recompute remaining_gbp from max_budget_gbp and spent_gbp."""
        self.remaining_gbp = round(self.max_budget_gbp - self.spent_gbp, 2)
        return self


class ModelConfig(BaseModel):
    """Configuration for a single AI model used within the pipeline.

    Used by the LearnedRouter and BudgetGuard to select and cost-estimate model calls.
    """

    model_config = ConfigDict(strict=True)

    model_id: str = Field(
        description=(
            "Fully qualified model identifier as used in API calls, "
            "e.g. 'claude-sonnet-4-20250514' or 'gpt-4o-2024-08-06'."
        )
    )
    provider: Literal["anthropic", "openai", "local"] = Field(
        description=(
            "API provider for this model. 'anthropic' uses the Anthropic SDK; "
            "'openai' uses the OpenAI-compatible API; 'local' uses vLLM."
        )
    )
    max_tokens: int = Field(
        description=(
            "Maximum number of output tokens this model can generate per request. "
            "Used to cap response length and estimate worst-case cost."
        )
    )
    temperature: float = Field(
        default=0.0,
        description=(
            "Sampling temperature for generation. 0.0 = deterministic (default). "
            "Higher values increase randomness. Range: [0.0, 1.0]."
        ),
    )
    cost_per_1k_input: float = Field(
        description=(
            "Cost in GBP per 1,000 input tokens for this model. "
            "Used by BudgetGuard to estimate and track spend."
        )
    )
    cost_per_1k_output: float = Field(
        description=(
            "Cost in GBP per 1,000 output tokens for this model. "
            "Used by BudgetGuard to estimate and track spend."
        )
    )
