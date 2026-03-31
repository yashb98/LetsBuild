"""Tutor agent — AI sports commentator for Arena spectator mode."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from letsbuild.forge.base_agent import BaseAgent
from letsbuild.forge.tools import READ_FILE_TOOL
from letsbuild.models.arena_models import ArenaAgentRole
from letsbuild.models.forge_models import AgentOutput, AgentRole

if TYPE_CHECKING:
    from letsbuild.harness.llm_client import LLMClient

logger = structlog.get_logger()

# Read-only search tools (same schemas as critic)

GREP_TOOL: dict[str, object] = {
    "name": "grep",
    "description": (
        "Search file contents for a pattern using regex. "
        "Returns matching lines with file paths and line numbers."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for.",
            },
            "path": {
                "type": "string",
                "description": "Directory or file to search in. Defaults to workspace root.",
                "default": ".",
            },
        },
        "required": ["pattern"],
    },
}

GLOB_TOOL: dict[str, object] = {
    "name": "glob",
    "description": "Find files matching a glob pattern. Returns a list of matching file paths.",
    "input_schema": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern (e.g. '**/*.py', 'src/**/*.ts').",
            },
        },
        "required": ["pattern"],
    },
}


class ArenaTutor(BaseAgent):
    """AI sports commentator watching a live coding competition.

    Reads agent activity logs and code to explain what's happening,
    what strategies teams are using, and what a spectator should
    pay attention to. Engaging but technical.

    Uses Haiku for speed over depth — commentary must be fast.
    """

    arena_role: ArenaAgentRole = ArenaAgentRole.TUTOR

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        model: str = "claude-haiku-4-5-20251001",
    ) -> None:
        super().__init__(
            role=AgentRole.PLANNER,
            llm_client=llm_client,
            model=model,
        )

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def system_prompt(self) -> str:
        """Return the commentator system prompt for the Tutor."""
        return (
            "You are an AI sports commentator watching a live coding competition.\n\n"
            "Your job:\n"
            "1. Read agent activity logs and explain what's happening.\n"
            "2. Identify strategies teams are using.\n"
            "3. Highlight interesting technical decisions.\n"
            "4. Point out what spectators should pay attention to.\n"
            "5. Compare team approaches when both are visible.\n\n"
            "Style:\n"
            "- Be engaging but technical — your audience are developers.\n"
            "- Use analogies to sports/competitions where helpful.\n"
            "- Note momentum shifts: when a team pivots, hits a wall, or breaks through.\n"
            "- Keep commentary concise — new updates arrive frequently.\n"
            "- You are read-only — you observe and comment, never intervene."
        )

    def tools(self) -> list[dict[str, object]]:
        """Return read-only tools — Tutor only observes."""
        return [READ_FILE_TOOL, GREP_TOOL, GLOB_TOOL]

    async def process_result(self, response: object) -> AgentOutput:
        """Extract commentary from the LLM response."""
        return AgentOutput(
            agent_role=AgentRole.PLANNER,
            task_id="",
            success=True,
            output_modules=[],
            tokens_used=0,
            execution_time_seconds=0.0,
            retry_count=0,
        )
