"""Builder agent — tournament-aware code builder wrapping CoderAgent."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from letsbuild.forge.agents.coder import CoderAgent
from letsbuild.forge.base_agent import BaseAgent
from letsbuild.models.arena_models import ArenaAgentRole
from letsbuild.models.forge_models import AgentOutput, AgentRole

if TYPE_CHECKING:
    from letsbuild.harness.llm_client import LLMClient

logger = structlog.get_logger()


class ArenaBuilder(BaseAgent):
    """Tournament-aware code builder. Wraps CoderAgent with challenge context.

    Does NOT reimplement code generation — delegates to the existing
    :class:`CoderAgent` with additional tournament context (challenge brief,
    ARCHITECTURE.md, time remaining) injected into the task context.
    """

    arena_role: ArenaAgentRole = ArenaAgentRole.BUILDER

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        model: str = "claude-sonnet-4-6",
    ) -> None:
        super().__init__(
            role=AgentRole.CODER,
            llm_client=llm_client,
            model=model,
        )
        self._coder = CoderAgent(llm_client=llm_client)

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def system_prompt(self) -> str:
        """Return the system prompt for the Arena Builder."""
        return self._coder.system_prompt()

    def tools(self) -> list[dict[str, object]]:
        """Return the same tools as CoderAgent."""
        return self._coder.tools()

    async def process_result(self, response: object) -> AgentOutput:
        """Delegate result processing to wrapped CoderAgent."""
        return await self._coder.process_result(response)

    # ------------------------------------------------------------------
    # Public convenience API
    # ------------------------------------------------------------------

    async def build(
        self,
        task_description: str,
        challenge_brief: str,
        architecture_md: str,
        time_remaining_seconds: int | None = None,
    ) -> AgentOutput:
        """Build code for a task with full tournament context.

        Injects challenge brief, architecture decisions, and time
        remaining into the task context before delegating to the
        underlying CoderAgent's run loop.
        """
        time_info = ""
        if time_remaining_seconds is not None:
            minutes = time_remaining_seconds // 60
            time_info = f"\n\nTime remaining: {minutes} minutes. Prioritise correctness."

        context = (
            f"## Challenge Brief\n{challenge_brief}\n\n"
            f"## Architecture\n{architecture_md}\n\n"
            f"## Task\n{task_description}"
            f"{time_info}\n\n"
            "Implement this task. Write all necessary files and verify they work."
        )

        return await self.run(context)
