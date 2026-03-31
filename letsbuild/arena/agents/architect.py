"""Architect agent — lead architect for Arena tournament teams."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from letsbuild.forge.base_agent import BaseAgent
from letsbuild.forge.tools import BASH_EXECUTE_TOOL, READ_FILE_TOOL, WRITE_FILE_TOOL
from letsbuild.models.arena_models import ArenaAgentRole
from letsbuild.models.forge_models import AgentOutput, AgentRole

if TYPE_CHECKING:
    from letsbuild.harness.llm_client import LLMClient

logger = structlog.get_logger()

# Arena-specific tool schemas

WEB_SEARCH_TOOL: dict[str, object] = {
    "name": "web_search",
    "description": (
        "Search the web for information about technologies, frameworks, "
        "patterns, or approaches relevant to the challenge."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            },
        },
        "required": ["query"],
    },
}

SPAWN_SUBTASK_TOOL: dict[str, object] = {
    "name": "spawn_subtask",
    "description": (
        "Create and assign a subtask to a team member agent. Returns a task ID for tracking."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "agent_role": {
                "type": "string",
                "description": "Target agent role: 'builder', 'frontend', 'tester'.",
                "enum": ["builder", "frontend", "tester"],
            },
            "description": {
                "type": "string",
                "description": "What the agent should accomplish.",
            },
            "dependencies": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Task IDs that must complete before this subtask starts.",
            },
        },
        "required": ["agent_role", "description"],
    },
}


class ArenaArchitect(BaseAgent):
    """Lead architect for a competitive hackathon team.

    Analyzes the challenge brief, researches approaches, creates
    ARCHITECTURE.md with stack decisions and component design, and
    decomposes work into tasks for Builder/Frontend/Tester.
    """

    arena_role: ArenaAgentRole = ArenaAgentRole.ARCHITECT

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        model: str = "claude-opus-4-6",
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
        """Return the system prompt for the Arena Architect."""
        return (
            "You are the lead architect for a competitive hackathon team.\n\n"
            "Your job:\n"
            "1. Analyze the challenge brief thoroughly.\n"
            "2. Research approaches — web search for relevant repos, papers, patterns.\n"
            "3. Create ARCHITECTURE.md with stack decisions and component design.\n"
            "4. Decompose work into tasks for Builder, Frontend, and Tester agents.\n"
            "5. Write clear task descriptions with dependencies between them.\n\n"
            "Rules:\n"
            "- Choose technologies that maximize quality within the time limit.\n"
            "- Prefer battle-tested stacks over bleeding-edge experiments.\n"
            "- Every architectural decision must be justified in ARCHITECTURE.md.\n"
            "- Tasks must be independently implementable with clear interfaces.\n"
            "- Consider judging criteria when making design trade-offs."
        )

    def tools(self) -> list[dict[str, object]]:
        """Return tools: web_search, read_file, write_file, bash, spawn_subtask."""
        return [
            WEB_SEARCH_TOOL,
            READ_FILE_TOOL,
            WRITE_FILE_TOOL,
            BASH_EXECUTE_TOOL,
            SPAWN_SUBTASK_TOOL,
        ]

    async def process_result(self, response: object) -> AgentOutput:
        """Extract ARCHITECTURE.md content and task list from final response."""
        return AgentOutput(
            agent_role=AgentRole.PLANNER,
            task_id="",
            success=True,
            output_modules=[],
            tokens_used=0,
            execution_time_seconds=0.0,
            retry_count=0,
        )
