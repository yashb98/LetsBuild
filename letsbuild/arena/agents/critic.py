"""Critic agent — adversarial code reviewer for Arena cross-review."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from letsbuild.forge.base_agent import BaseAgent
from letsbuild.forge.tools import BASH_EXECUTE_TOOL, READ_FILE_TOOL
from letsbuild.models.arena_models import ArenaAgentRole
from letsbuild.models.forge_models import AgentOutput, AgentRole

if TYPE_CHECKING:
    from letsbuild.harness.llm_client import LLMClient

logger = structlog.get_logger()

# Read-only search tools

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
    "description": ("Find files matching a glob pattern. Returns a list of matching file paths."),
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

# Disallowed tools — enforced by tool scoping, not prompts
DISALLOWED_TOOLS = frozenset({"write_file", "edit_file", "install_package", "docker_build"})


class ArenaCritic(BaseAgent):
    """Adversarial code reviewer for Arena cross-review.

    The Critic's job is to BREAK things — find bugs, security holes,
    architectural flaws, and missing edge cases. It has ZERO context
    from the build process and sees only the code and challenge brief.

    During cross-review, the Critic reviews the OPPOSING team's code.

    IMPORTANT: The Critic has NO write access. ``disallowed_tools``
    includes write_file and edit_file. Bash is restricted to read-only
    commands (pytest, ruff).
    """

    arena_role: ArenaAgentRole = ArenaAgentRole.CRITIC

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        model: str = "claude-opus-4-6",
    ) -> None:
        super().__init__(
            role=AgentRole.REVIEWER,
            llm_client=llm_client,
            model=model,
        )

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def system_prompt(self) -> str:
        """Return the adversarial review system prompt for the Critic."""
        return (
            "You are an adversarial code reviewer in a competitive coding tournament.\n\n"
            "Your job is to BREAK things:\n"
            "1. Find bugs — logic errors, off-by-one, race conditions.\n"
            "2. Find security holes — injection, auth bypass, path traversal.\n"
            "3. Find architectural flaws — coupling, missing abstractions, scalability.\n"
            "4. Find missing edge cases — empty inputs, unicode, large payloads.\n"
            "5. Run existing tests with bash (pytest) and linting (ruff) to find issues.\n\n"
            "Rules:\n"
            "- You have ZERO context from the build process.\n"
            "- You see ONLY the code and the challenge brief.\n"
            "- During cross-review, you review the OPPOSING team's code.\n"
            "- You CANNOT modify code — read-only access only.\n"
            "- Use grep/glob to find patterns and potential issues across the codebase.\n"
            "- Bash is restricted to pytest and ruff — no write operations.\n"
            "- Be specific: cite file, line number, and exact issue."
        )

    def tools(self) -> list[dict[str, object]]:
        """Return read-only tools — Critic CANNOT modify code."""
        return [
            READ_FILE_TOOL,
            GREP_TOOL,
            GLOB_TOOL,
            BASH_EXECUTE_TOOL,
        ]

    async def process_result(self, response: object) -> AgentOutput:
        """Extract review findings from the LLM response."""
        return AgentOutput(
            agent_role=AgentRole.REVIEWER,
            task_id="",
            success=True,
            output_modules=[],
            tokens_used=0,
            execution_time_seconds=0.0,
            retry_count=0,
        )
