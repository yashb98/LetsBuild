"""Frontend agent — UI/frontend engineer for Arena tournament teams."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from letsbuild.forge.base_agent import BaseAgent
from letsbuild.forge.tools import (
    BASH_EXECUTE_TOOL,
    LIST_DIRECTORY_TOOL,
    READ_FILE_TOOL,
    WRITE_FILE_TOOL,
)
from letsbuild.models.arena_models import ArenaAgentRole
from letsbuild.models.forge_models import AgentOutput, AgentRole

if TYPE_CHECKING:
    from letsbuild.harness.llm_client import LLMClient

logger = structlog.get_logger()

# Arena-specific tool schema

WEB_SEARCH_TOOL: dict[str, object] = {
    "name": "web_search",
    "description": (
        "Search the web for UI patterns, component libraries, "
        "design references, or framework documentation."
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


class ArenaFrontend(BaseAgent):
    """Frontend/UI engineer for a competitive hackathon team.

    Builds responsive, polished user interfaces using modern frameworks
    (React/Next.js/Tailwind or whatever ARCHITECTURE.md specifies).
    """

    arena_role: ArenaAgentRole = ArenaAgentRole.FRONTEND

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

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def system_prompt(self) -> str:
        """Return the system prompt for the Arena Frontend agent."""
        return (
            "You are a frontend/UI engineer for a competitive hackathon.\n\n"
            "Your job:\n"
            "1. Build responsive, polished user interfaces.\n"
            "2. Use modern frameworks — React/Next.js/Tailwind or whatever "
            "ARCHITECTURE.md specifies.\n"
            "3. Follow the component structure defined in the architecture.\n"
            "4. Write clean, typed components with proper props interfaces.\n\n"
            "Rules:\n"
            "- Mobile-first responsive design.\n"
            "- Accessibility matters — use semantic HTML and ARIA attributes.\n"
            "- Use bash for npm/vite commands to install packages and run builds.\n"
            "- Verify your UI builds successfully before marking tasks complete.\n"
            "- Search the web for component patterns and best practices when needed."
        )

    def tools(self) -> list[dict[str, object]]:
        """Return tools: read_file, write_file, bash, list_files, web_search."""
        return [
            READ_FILE_TOOL,
            WRITE_FILE_TOOL,
            BASH_EXECUTE_TOOL,
            LIST_DIRECTORY_TOOL,
            WEB_SEARCH_TOOL,
        ]

    async def process_result(self, response: object) -> AgentOutput:
        """Extract frontend module output from the LLM response."""
        return AgentOutput(
            agent_role=AgentRole.CODER,
            task_id="",
            success=True,
            output_modules=[],
            tokens_used=0,
            execution_time_seconds=0.0,
            retry_count=0,
        )
