"""Async Anthropic SDK wrapper with budget tracking, retry logic, and agentic loops."""

from __future__ import annotations

from collections.abc import Awaitable, Callable  # noqa: TC003
from typing import Any

import anthropic
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from letsbuild.models.shared import BudgetInfo

logger = structlog.get_logger()

# Cost per million tokens in USD, converted to GBP at ~0.80 rate.
_MODEL_COSTS_GBP: dict[str, tuple[float, float]] = {
    # (input_per_million_gbp, output_per_million_gbp)
    "claude-opus-4-6": (15.0 * 0.80, 75.0 * 0.80),
    "claude-sonnet-4-6": (3.0 * 0.80, 15.0 * 0.80),
    "claude-haiku-4-5": (0.80 * 0.80, 4.0 * 0.80),
}

# Default rate used for unknown models (sonnet pricing).
_DEFAULT_COST_GBP: tuple[float, float] = (3.0 * 0.80, 15.0 * 0.80)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate the cost in GBP for a given model and token usage.

    Known models use their published per-million-token pricing converted at
    ~0.80 USD→GBP.  Unknown models fall back to Sonnet-tier pricing.
    """
    input_rate, output_rate = _MODEL_COSTS_GBP.get(model, _DEFAULT_COST_GBP)
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


class LLMClient:
    """Async wrapper around the Anthropic SDK with budget tracking and retry logic.

    Provides three call styles:
    * ``create_message`` — single request/response with automatic retries.
    * ``run_agent_loop`` — canonical ``stop_reason``-based agentic loop.
    * ``extract_structured`` — forced ``tool_use`` for guaranteed structured output.
    """

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str = "claude-sonnet-4-6",
    ) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.default_model = default_model
        self._budget = BudgetInfo()
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._log = logger.bind(component="llm_client")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def budget(self) -> BudgetInfo:
        """Return the current budget tracker."""
        return self._budget

    @property
    def total_tokens(self) -> int:
        """Return total tokens (input + output) used across all calls."""
        return self._total_input_tokens + self._total_output_tokens

    @property
    def total_cost_gbp(self) -> float:
        """Return total cost in GBP across all calls."""
        return self._budget.spent_gbp

    # ------------------------------------------------------------------
    # Core API call
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type(
            (
                anthropic.RateLimitError,
                anthropic.APIStatusError,
                anthropic.APIConnectionError,
            )
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def create_message(
        self,
        messages: list[dict[str, object]],
        system: str | None = None,
        tools: list[dict[str, object]] | None = None,
        tool_choice: dict[str, str] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> anthropic.types.Message:
        """Send a single message request to the Anthropic API.

        Retries up to 3 times with exponential back-off on transient errors
        (rate-limit, API status, and connection errors).  Tracks token usage
        and estimated cost in the budget tracker.
        """
        resolved_model = model or self.default_model

        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system is not None:
            kwargs["system"] = system
        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

        response: anthropic.types.Message = await self.client.messages.create(**kwargs)

        # Track usage -------------------------------------------------------
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens

        cost = estimate_cost(resolved_model, input_tokens, output_tokens)
        self._budget.record_cost(resolved_model, cost)

        self._log.info(
            "llm_request",
            model=resolved_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_gbp=round(cost, 6),
            stop_reason=response.stop_reason,
        )

        return response

    # ------------------------------------------------------------------
    # Agentic loop
    # ------------------------------------------------------------------

    async def run_agent_loop(
        self,
        messages: list[dict[str, object]],
        system: str,
        tools: list[dict[str, object]],
        tool_executor: Callable[[anthropic.types.Message], Awaitable[list[dict[str, object]]]],
        model: str | None = None,
        max_tokens: int = 4096,
        tool_choice: dict[str, str] | None = None,
        max_turns: int = 50,
    ) -> anthropic.types.Message:
        """Run the canonical ``stop_reason``-based agentic loop.

        The loop continues while the model returns ``stop_reason == "tool_use"``.
        It terminates when the model returns ``"end_turn"`` (the *primary*
        stopping mechanism).  ``max_turns`` is a **safety cap only** — not the
        design intent.
        """
        turn = 0
        while True:
            turn += 1
            if turn > max_turns:
                self._log.warning(
                    "agent_loop_safety_cap",
                    max_turns=max_turns,
                    message="Safety cap reached — breaking loop.",
                )
                break

            response = await self.create_message(
                messages=messages,
                system=system,
                tools=tools,
                tool_choice=tool_choice if turn == 1 else None,
                model=model,
                max_tokens=max_tokens,
            )

            self._log.info(
                "agent_loop_turn",
                turn=turn,
                stop_reason=response.stop_reason,
                tools_called=[block.name for block in response.content if block.type == "tool_use"],
            )

            if response.stop_reason == "tool_use":
                tool_results = await tool_executor(response)
                messages.append(
                    {"role": "assistant", "content": response.content},
                )
                messages.append(
                    {"role": "user", "content": tool_results},
                )
            elif response.stop_reason == "end_turn":
                break
            else:
                # Unexpected stop_reason — log and break to avoid infinite loop.
                self._log.warning(
                    "agent_loop_unexpected_stop",
                    stop_reason=response.stop_reason,
                )
                break

        return response

    # ------------------------------------------------------------------
    # Structured extraction helper
    # ------------------------------------------------------------------

    async def extract_structured(
        self,
        messages: list[dict[str, object]],
        system: str,
        tool_schema: dict[str, object],
        tool_name: str,
        model: str | None = None,
    ) -> dict[str, object]:
        """Force a single ``tool_use`` call and return the parsed tool input.

        Convenience wrapper for guaranteed structured output via
        ``tool_choice = {"type": "tool", "name": tool_name}``.
        """
        response = await self.create_message(
            messages=messages,
            system=system,
            tools=[tool_schema],
            tool_choice={"type": "tool", "name": tool_name},
            model=model,
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                return dict(block.input)  # type: ignore[arg-type]

        msg = f"Expected tool_use block with name '{tool_name}' not found in response."
        raise ValueError(msg)
