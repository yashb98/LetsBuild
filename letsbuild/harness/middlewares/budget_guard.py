"""BudgetGuard + LearnedRouter middleware — sixth in the 10-stage middleware chain.

Combines two responsibilities:
1. **LearnedRouter** — selects the optimal model for the current pipeline layer.
   Starts with a static routing table for the first 20 runs. After 20+ JUDGE
   verdicts are stored in the ReasoningBank, the router can switch to Q-learning
   based selection (TODO: Q-learning implementation once ReasoningBank is wired).

2. **BudgetGuard** — enforces a hard per-run API cost ceiling. If the estimated
   cost of the next layer would breach the budget, the pipeline is aborted.

Architecture position: middleware #6 in the chain (after MemoryRetrieval, before
QualityGate). This placement ensures budget/model decisions are made *after*
memory context is available (for routing signals) but *before* any expensive
layer execution begins.
"""

from __future__ import annotations

from typing import Final

import structlog

from letsbuild.harness.middleware import Middleware
from letsbuild.models.shared import (
    BudgetInfo,
    ErrorCategory,
    ModelConfig,
    StructuredError,
)
from letsbuild.pipeline.state import PipelineState  # noqa: TC001

__all__ = ["BudgetGuardMiddleware", "LearnedRouter"]

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Layer name constants (keyed by current_layer integer)
# ---------------------------------------------------------------------------

_LAYER_NAMES: Final[dict[int, str]] = {
    0: "harness",
    1: "intake",
    2: "intelligence",
    3: "matcher",
    4: "architect",
    5: "forge",
    6: "publisher",
    7: "content",
    8: "memory",
    9: "hooks",
}

# ---------------------------------------------------------------------------
# Default model configurations (approximate GBP costs at 2025 pricing)
# USD→GBP conversion ~0.79; costs listed per 1k tokens.
# ---------------------------------------------------------------------------

_DEFAULT_MODEL_CONFIGS: Final[dict[str, ModelConfig]] = {
    "claude-opus-4-20250514": ModelConfig(
        model_id="claude-opus-4-20250514",
        max_tokens=4096,
        temperature=0.0,
        # $15 / 1M input → $0.015 / 1k → ~£0.0119 / 1k
        cost_per_1k_input=0.0119,
        # $75 / 1M output → $0.075 / 1k → ~£0.0593 / 1k
        cost_per_1k_output=0.0593,
    ),
    "claude-sonnet-4-20250514": ModelConfig(
        model_id="claude-sonnet-4-20250514",
        max_tokens=8192,
        temperature=0.0,
        # $3 / 1M input → $0.003 / 1k → ~£0.00237 / 1k
        cost_per_1k_input=0.00237,
        # $15 / 1M output → $0.015 / 1k → ~£0.0119 / 1k
        cost_per_1k_output=0.0119,
    ),
    "claude-haiku-4-5-20251001": ModelConfig(
        model_id="claude-haiku-4-5-20251001",
        max_tokens=4096,
        temperature=0.0,
        # $0.80 / 1M input → $0.0008 / 1k → ~£0.000632 / 1k
        cost_per_1k_input=0.000632,
        # $4 / 1M output → $0.004 / 1k → ~£0.00316 / 1k
        cost_per_1k_output=0.00316,
    ),
}

# ---------------------------------------------------------------------------
# Per-layer cost estimates in GBP used for budget look-ahead.
# These are conservative upper-bound estimates drawn from the architecture doc.
# ---------------------------------------------------------------------------

_LAYER_COST_ESTIMATES_GBP: Final[dict[str, float]] = {
    "harness": 0.0,  # No LLM calls
    "intake": 0.50,  # Haiku + small input
    "intelligence": 3.0,  # Sonnet x 6 sub-agents
    "matcher": 0.50,  # Haiku
    "architect": 5.0,  # Opus
    "forge": 15.0,  # Sonnet x N coders + Opus reviewer
    "publisher": 0.50,  # Haiku
    "content": 5.0,  # Sonnet x 4 formats
    "memory": 0.0,  # No LLM calls (HNSW + SQLite)
    "hooks": 0.0,  # Deterministic code
}


# ---------------------------------------------------------------------------
# LearnedRouter
# ---------------------------------------------------------------------------


class LearnedRouter:
    """Routes pipeline layers to the optimal model.

    Static table is used unconditionally until the Q-learning implementation
    is added (TODO). The interface is designed so that swapping in Q-learning
    requires only overriding ``_select_model_id``.

    Static routing table (from architecture spec):
      intake      → claude-haiku-4-5-20251001   (cheap skill extraction)
      intelligence → claude-sonnet-4-20250514   (research)
      matcher     → claude-haiku-4-5-20251001   (scoring)
      architect   → claude-opus-4-20250514      (design decisions)
      forge       → claude-sonnet-4-20250514    (code generation)
      publisher   → claude-haiku-4-5-20251001   (commit messages)
      content     → claude-sonnet-4-20250514    (content generation)
    """

    # Static routing table: layer_name → model_id
    _STATIC_ROUTES: Final[dict[str, str]] = {
        "intake": "claude-haiku-4-5-20251001",
        "intelligence": "claude-sonnet-4-20250514",
        "matcher": "claude-haiku-4-5-20251001",
        "architect": "claude-opus-4-20250514",
        "forge": "claude-sonnet-4-20250514",
        "publisher": "claude-haiku-4-5-20251001",
        "content": "claude-sonnet-4-20250514",
        # Layers with no LLM calls — default to Haiku as a safe fallback
        "harness": "claude-haiku-4-5-20251001",
        "memory": "claude-haiku-4-5-20251001",
        "hooks": "claude-haiku-4-5-20251001",
    }

    # Minimum number of JUDGE verdicts required before Q-learning kicks in.
    _Q_LEARNING_THRESHOLD: Final[int] = 20

    def __init__(self, verdict_count: int = 0) -> None:
        """Initialise the router.

        Args:
            verdict_count: Number of JUDGE verdicts currently stored in the
                ReasoningBank. Used to decide whether Q-learning is active.
        """
        self._verdict_count = verdict_count

    def select_model(
        self,
        layer_name: str,
        model_configs: dict[str, ModelConfig],
    ) -> ModelConfig:
        """Return the ModelConfig for the given layer.

        Args:
            layer_name: The name of the pipeline layer (e.g. 'forge').
            model_configs: Available model configurations keyed by model_id.

        Returns:
            The selected ModelConfig.
        """
        model_id = self._select_model_id(layer_name)

        # Fallback: if the selected model is not in configs, use Sonnet.
        if model_id not in model_configs:
            fallback_id = "claude-sonnet-4-20250514"
            logger.warning(
                "learned_router_model_not_found",
                selected_model=model_id,
                layer=layer_name,
                fallback=fallback_id,
            )
            model_id = fallback_id

        return model_configs[model_id]

    def _select_model_id(self, layer_name: str) -> str:
        """Return the model ID for the given layer.

        Currently uses the static routing table for all runs.
        TODO: Implement Q-learning routing when verdict_count >= _Q_LEARNING_THRESHOLD.
              The Q-table should map (layer_name, context_features) → model_id where
              context_features include: seniority, domain, prior_success_rate.
              Use EWC++ to prevent catastrophic forgetting across domains.
        """
        if self._verdict_count >= self._Q_LEARNING_THRESHOLD:
            # TODO: Replace with Q-learning lookup when implemented.
            # For now, fall through to static routing even above the threshold.
            pass

        return self._STATIC_ROUTES.get(layer_name, "claude-sonnet-4-20250514")

    @property
    def is_learning_active(self) -> bool:
        """Return True once Q-learning has taken over from static routing."""
        # Always False until Q-learning is implemented.
        return False

    @property
    def verdict_count(self) -> int:
        """Number of JUDGE verdicts seen by this router."""
        return self._verdict_count


# ---------------------------------------------------------------------------
# BudgetGuardMiddleware
# ---------------------------------------------------------------------------


class BudgetGuardMiddleware(Middleware):
    """Enforce per-run API cost limits and inject optimal model selection.

    Responsibilities (in ``before``):
    1. Initialise ``BudgetInfo`` on first call if not already present in state.
    2. Estimate the cost of the upcoming layer and block execution if the
       remaining budget is insufficient.
    3. Select the optimal model via ``LearnedRouter`` and inject the choice
       into ``state.metadata`` under the key ``"selected_model_config"``.

    Responsibilities (in ``after``):
    1. Sync ``BudgetInfo`` spent/remaining figures from ``state.metrics``.

    Gate semantics: this middleware behaves as a *blocking gate* — a
    ``ValueError`` is raised (and a ``StructuredError`` appended) if the
    budget would be breached. The pipeline controller will catch this and
    abort the run.
    """

    _METADATA_KEY: Final[str] = "selected_model_config"
    _BUDGET_INFO_KEY: Final[str] = "budget_info"

    def __init__(
        self,
        max_budget_gbp: float = 50.0,
        model_configs: dict[str, ModelConfig] | None = None,
        verdict_count: int = 0,
    ) -> None:
        """Initialise BudgetGuardMiddleware.

        Args:
            max_budget_gbp: Hard cap on per-run API cost in GBP.
            model_configs: Model configurations keyed by model_id. Defaults to
                the built-in configs for Opus, Sonnet, and Haiku.
            verdict_count: Number of past JUDGE verdicts (forwarded to
                LearnedRouter to determine routing mode).
        """
        self._max_budget_gbp = max_budget_gbp
        self._model_configs: dict[str, ModelConfig] = (
            model_configs if model_configs is not None else dict(_DEFAULT_MODEL_CONFIGS)
        )
        self._router = LearnedRouter(verdict_count=verdict_count)
        self._log = structlog.get_logger(component=self.name)

    # ------------------------------------------------------------------ #
    # Middleware ABC
    # ------------------------------------------------------------------ #

    async def before(self, state: PipelineState) -> PipelineState:
        """Pre-execution budget check and model selection.

        1. Initialise ``BudgetInfo`` if absent.
        2. Check whether the upcoming layer fits within remaining budget.
        3. Select model and inject into state metadata.

        Args:
            state: Current pipeline state.

        Returns:
            Updated state with model selection injected.

        Raises:
            ValueError: If the estimated layer cost would exceed the budget.
        """
        # 1. Initialise BudgetInfo
        budget_info = self._get_or_init_budget_info(state)

        # 2. Budget look-ahead check
        layer_name = _LAYER_NAMES.get(state.current_layer, "unknown")
        estimated_cost = _LAYER_COST_ESTIMATES_GBP.get(layer_name, 0.0)

        if estimated_cost > 0.0 and (budget_info.remaining_gbp - estimated_cost) < 0.0:
            self._fail(
                state,
                budget_info,
                layer_name=layer_name,
                remaining=budget_info.remaining_gbp,
                estimated=estimated_cost,
            )

        # 3. Model selection
        selected = self._router.select_model(layer_name, self._model_configs)

        # Inject into metadata — PipelineState uses a dict[str, object] field.
        if not hasattr(state, "metadata"):
            # Guard: metadata field may not exist on all state versions.
            await self._log.awarning(
                "budget_guard_metadata_missing",
                thread_id=state.thread_id,
                layer=layer_name,
            )
        else:
            state.metadata[self._METADATA_KEY] = selected  # type: ignore[attr-defined]
            state.metadata[self._BUDGET_INFO_KEY] = budget_info  # type: ignore[attr-defined]

        await self._log.ainfo(
            "budget_guard_before_passed",
            thread_id=state.thread_id,
            layer=layer_name,
            layer_index=state.current_layer,
            estimated_cost_gbp=estimated_cost,
            remaining_gbp=budget_info.remaining_gbp,
            selected_model=selected.model_id,
            router_learning_active=self._router.is_learning_active,
        )

        return state

    async def after(self, state: PipelineState) -> PipelineState:
        """Post-execution budget reconciliation.

        Syncs ``BudgetInfo.spent_gbp`` from the authoritative
        ``state.metrics.total_api_cost_gbp`` and recomputes remaining.

        Args:
            state: Current pipeline state (with layer results).

        Returns:
            Updated state with refreshed budget figures.
        """
        budget_info = self._get_or_init_budget_info(state)

        # Sync from metrics (metrics is the authoritative cost source)
        actual_spent = state.metrics.total_api_cost_gbp
        delta = actual_spent - budget_info.spent_gbp

        if delta > 0.0:
            budget_info.spent_gbp = actual_spent
            budget_info.remaining_gbp = budget_info.budget_limit_gbp - actual_spent

        # Keep state.budget_remaining in sync for other middlewares/gates.
        state.budget_remaining = budget_info.remaining_gbp

        layer_name = _LAYER_NAMES.get(state.current_layer, "unknown")
        await self._log.ainfo(
            "budget_guard_after_reconciled",
            thread_id=state.thread_id,
            layer=layer_name,
            spent_gbp=budget_info.spent_gbp,
            remaining_gbp=budget_info.remaining_gbp,
            delta_gbp=round(delta, 6),
        )

        return state

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _get_or_init_budget_info(self, state: PipelineState) -> BudgetInfo:
        """Return existing BudgetInfo from state metadata, or create a new one.

        BudgetInfo is stored in ``state.metadata[_BUDGET_INFO_KEY]`` so it
        persists across before/after calls within a single run. If metadata
        is unavailable, a local instance is used (no persistence across hooks).
        """
        if hasattr(state, "metadata"):
            existing = state.metadata.get(self._BUDGET_INFO_KEY)  # type: ignore[attr-defined]
            if isinstance(existing, BudgetInfo):
                return existing
            # First call for this run — initialise from state.budget_remaining
            budget_info = BudgetInfo(
                budget_limit_gbp=self._max_budget_gbp,
                spent_gbp=self._max_budget_gbp - state.budget_remaining,
                remaining_gbp=state.budget_remaining,
            )
            state.metadata[self._BUDGET_INFO_KEY] = budget_info  # type: ignore[attr-defined]
            return budget_info

        # Fallback: no metadata dict — create a fresh instance each call.
        return BudgetInfo(
            budget_limit_gbp=self._max_budget_gbp,
            spent_gbp=self._max_budget_gbp - state.budget_remaining,
            remaining_gbp=state.budget_remaining,
        )

    def _fail(
        self,
        state: PipelineState,
        budget_info: BudgetInfo,
        *,
        layer_name: str,
        remaining: float,
        estimated: float,
    ) -> None:
        """Append a StructuredError and raise ValueError to abort the pipeline."""
        message = (
            f"BudgetGate blocked layer '{layer_name}': "
            f"estimated cost £{estimated:.2f} exceeds remaining budget £{remaining:.2f}. "
            f"Total budget: £{budget_info.budget_limit_gbp:.2f}, "
            f"spent: £{budget_info.spent_gbp:.2f}."
        )
        error = StructuredError(
            error_category=ErrorCategory.BUSINESS,
            is_retryable=False,
            message=message,
            attempted_query=f"execute layer {layer_name}",
        )
        state.add_error(error)
        raise ValueError(message)
