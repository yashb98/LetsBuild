"""Abstract base class for all Code Forge agents."""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import structlog

from letsbuild.models.forge_models import AgentOutput, AgentRole
from letsbuild.models.shared import ErrorCategory, StructuredError

if TYPE_CHECKING:
    from letsbuild.harness.llm_client import LLMClient

_MAX_TOOLS = 5
_SAFETY_CAP_TURNS = 50

logger = structlog.get_logger()


class BaseAgent(ABC):
    """Abstract base class for all Code Forge agents.

    Subclasses must implement ``system_prompt``, ``tools``, and
    ``process_result``.  The canonical ``stop_reason``-based agentic loop
    is provided by :meth:`run`.
    """

    def __init__(
        self,
        role: AgentRole,
        llm_client: LLMClient | None = None,
        model: str | None = None,
    ) -> None:
        self.role = role
        self.llm_client = llm_client
        self.model = model
        self._log = logger.bind(agent_role=role)

    # ------------------------------------------------------------------
    # Abstract interface — override per agent
    # ------------------------------------------------------------------

    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        ...

    @abstractmethod
    def tools(self) -> list[dict[str, object]]:
        """Return the tool schemas for this agent (max 5)."""
        ...

    @abstractmethod
    async def process_result(self, response: object) -> AgentOutput:
        """Convert the final LLM response into an ``AgentOutput``."""
        ...

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, task_context: str, **kwargs: object) -> AgentOutput:
        """Execute the agent's agentic loop and return an ``AgentOutput``.

        Validates tool count, builds messages, delegates to the LLM client's
        ``run_agent_loop``, then calls ``process_result`` on the final
        response.  Tracks execution time and tokens.
        """
        tool_schemas = self.tools()
        if len(tool_schemas) > _MAX_TOOLS:
            msg = (
                f"Agent '{self.role}' declares {len(tool_schemas)} tools, "
                f"but the maximum is {_MAX_TOOLS}."
            )
            raise ValueError(msg)

        if self.llm_client is None:
            msg = "llm_client is required to run an agent."
            raise ValueError(msg)

        task_id = str(kwargs.get("task_id", str(uuid.uuid4())))
        messages = self._build_messages(task_context)
        start_time = time.monotonic()
        tokens_before = self.llm_client.total_tokens

        try:
            response = await self.llm_client.run_agent_loop(
                messages=messages,
                system=self.system_prompt(),
                tools=tool_schemas,
                tool_executor=self._execute_tool,
                model=self.model,
                max_turns=_SAFETY_CAP_TURNS,
            )

            output = await self.process_result(response)

            # Patch timing and token info onto the output.
            elapsed = time.monotonic() - start_time
            tokens_used = self.llm_client.total_tokens - tokens_before

            return AgentOutput(
                agent_role=self.role,
                task_id=task_id,
                success=output.success,
                output_modules=output.output_modules,
                error=output.error,
                tokens_used=tokens_used,
                execution_time_seconds=round(elapsed, 3),
                retry_count=output.retry_count,
            )

        except Exception as exc:
            elapsed = time.monotonic() - start_time
            tokens_used = self.llm_client.total_tokens - tokens_before
            self._log.error("agent_run_failed", error=str(exc))

            return AgentOutput(
                agent_role=self.role,
                task_id=task_id,
                success=False,
                output_modules=[],
                error=StructuredError(
                    error_category=ErrorCategory.TRANSIENT,
                    is_retryable=True,
                    message=str(exc),
                ),
                tokens_used=tokens_used,
                execution_time_seconds=round(elapsed, 3),
                retry_count=0,
            )

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def _execute_tool(self, response: Any) -> list[dict[str, object]]:
        """Default tool executor — iterate tool_use blocks and dispatch.

        Returns tool results in the Claude conversation format expected by
        ``run_agent_loop``.
        """
        results: list[dict[str, object]] = []
        for block in response.content:
            if block.type == "tool_use":
                try:
                    result = await self._dispatch_tool(block.name, dict(block.input))
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        }
                    )
                except Exception as exc:
                    self._log.warning(
                        "tool_dispatch_error",
                        tool=block.name,
                        error=str(exc),
                    )
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(
                                StructuredError(
                                    error_category=ErrorCategory.TRANSIENT,
                                    is_retryable=True,
                                    message=str(exc),
                                ).model_dump_json()
                            ),
                            "is_error": True,
                        }
                    )
        return results

    async def _dispatch_tool(
        self,
        tool_name: str,
        tool_input: dict[str, object],
    ) -> object:
        """Dispatch a tool call to its implementation.

        Subclasses override this to implement actual tool logic.
        """
        msg = (
            f"Tool '{tool_name}' is not implemented. "
            f"Override _dispatch_tool in {type(self).__name__}."
        )
        raise NotImplementedError(msg)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def allowed_tools(self) -> list[str]:
        """Return the list of tool names declared by this agent."""
        return [t["name"] for t in self.tools() if "name" in t]

    def _build_messages(self, task_context: str) -> list[dict[str, object]]:
        """Build the initial message list with the task context."""
        return [
            {
                "role": "user",
                "content": task_context,
            }
        ]
