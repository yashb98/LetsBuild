"""Tester agent for Code Forge — writes and runs tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from letsbuild.forge.base_agent import BaseAgent
from letsbuild.forge.tools import BASH_EXECUTE_TOOL, READ_FILE_TOOL, WRITE_FILE_TOOL
from letsbuild.models.forge_models import AgentOutput, AgentRole, CodeModule

if TYPE_CHECKING:
    from letsbuild.harness.llm_client import LLMClient

logger = structlog.get_logger()


class TesterAgent(BaseAgent):
    """Agent responsible for writing and running tests against generated code.

    Tools: ``read_file``, ``bash_execute``, ``write_file`` (max 3, within the
    5-tool cap).
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        super().__init__(
            role=AgentRole.TESTER,
            llm_client=llm_client,
        )

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def system_prompt(self) -> str:
        """Return the system prompt for the Tester agent."""
        return (
            "You are a meticulous software tester. Your job is to:\n"
            "1. Read the generated source code modules.\n"
            "2. Write comprehensive unit tests that cover happy paths, edge cases, "
            "and error conditions.\n"
            "3. Run the tests inside the sandbox and report results.\n"
            "4. If tests fail, provide clear diagnostics so the Coder can fix them.\n\n"
            "You have access to: read_file, bash_execute, write_file.\n"
            "Write tests in the same language as the source code. "
            "Use the project's configured test framework."
        )

    def tools(self) -> list[dict[str, object]]:
        """Return tool schemas for the Tester agent."""
        return [READ_FILE_TOOL, BASH_EXECUTE_TOOL, WRITE_FILE_TOOL]

    async def process_result(self, response: object) -> AgentOutput:
        """Extract test results from the final LLM response."""
        # Extract text content from the response.
        text_parts: list[str] = []
        if hasattr(response, "content"):
            for block in response.content:  # type: ignore[union-attr]
                if hasattr(block, "text"):
                    text_parts.append(block.text)

        summary = "\n".join(text_parts) if text_parts else "Tests completed."
        module = CodeModule(
            module_path="test_results.txt",
            content=summary,
            language="text",
            loc=summary.count("\n") + 1,
        )
        return AgentOutput(
            agent_role=AgentRole.TESTER,
            task_id="",
            success=True,
            output_modules=[module],
            tokens_used=0,
            execution_time_seconds=0.0,
        )

    # ------------------------------------------------------------------
    # Convenience API
    # ------------------------------------------------------------------

    async def test(
        self,
        code_modules: list[CodeModule],
        test_plan: str,
    ) -> AgentOutput:
        """Run tests for the given code modules.

        If no LLM client is configured, falls back to a deterministic
        heuristic that always passes.
        """
        if self.llm_client is None:
            return self._test_heuristic(code_modules)

        # Build context from code modules and the test plan.
        module_summaries = "\n".join(
            f"- {m.module_path} ({m.language}, {m.loc} LOC)" for m in code_modules
        )
        context = f"## Code Modules\n{module_summaries}\n\n## Test Plan\n{test_plan}"
        return await self.run(context)

    @staticmethod
    def _test_heuristic(code_modules: list[CodeModule]) -> AgentOutput:
        """Produce a deterministic pass result without an LLM."""
        paths = ", ".join(m.module_path for m in code_modules) if code_modules else "(none)"
        summary = f"Heuristic test pass for modules: {paths}"
        module = CodeModule(
            module_path="test_results.txt",
            content=summary,
            language="text",
            loc=1,
        )
        return AgentOutput(
            agent_role=AgentRole.TESTER,
            task_id="heuristic",
            success=True,
            output_modules=[module],
            tokens_used=0,
            execution_time_seconds=0.0,
        )
