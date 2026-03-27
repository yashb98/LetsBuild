"""Reviewer agent — independent code review with ZERO coder context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

from letsbuild.forge.base_agent import BaseAgent
from letsbuild.forge.tools import LIST_DIRECTORY_TOOL, READ_FILE_TOOL
from letsbuild.models.forge_models import (
    AgentOutput,
    AgentRole,
    CodeModule,
    ReviewVerdict,
)

if TYPE_CHECKING:
    from letsbuild.harness.llm_client import LLMClient

logger = structlog.get_logger()


@dataclass
class ReviewResult:
    """Result of an independent code review."""

    verdict: ReviewVerdict
    score: float
    comments: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)


class ReviewerAgent(BaseAgent):
    """Independent Reviewer agent for the Code Forge.

    IMPORTANT: The Reviewer has ZERO context from the Coder. It receives
    only the generated code, a project spec summary, and a quality checklist.
    It uses a FRESH client instance to enforce context isolation.
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        # Create a fresh client — never share context with the Coder.
        super().__init__(
            role=AgentRole.REVIEWER,
            llm_client=llm_client,
            model=None,
        )

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def system_prompt(self) -> str:
        """Return the critique-focused system prompt for the Reviewer."""
        return (
            "You are the independent Reviewer agent in the LetsBuild Code Forge.\n\n"
            "Your job is to review generated code for quality, correctness, and "
            "adherence to the project specification.\n\n"
            "Rules:\n"
            "1. You have NO context from the Coder who generated this code.\n"
            "2. Review only what you can see: code files and the project spec.\n"
            "3. Use read_file and list_directory to inspect the generated code.\n"
            "4. Evaluate: correctness, typing, docstrings, test coverage, "
            "architecture, error handling, and security.\n"
            "5. Score the code from 0 to 100.\n"
            "6. Identify blocking issues that MUST be fixed before publishing.\n"
            "7. Provide constructive suggestions for improvement.\n"
            "8. Render your final verdict: PASS, FAIL, or PASS_WITH_SUGGESTIONS."
        )

    def tools(self) -> list[dict[str, object]]:
        """Return read-only tools — the Reviewer cannot modify code."""
        return [READ_FILE_TOOL, LIST_DIRECTORY_TOOL]

    async def process_result(self, response: object) -> AgentOutput:
        """Extract review verdict from the LLM response."""
        return AgentOutput(
            agent_role=AgentRole.REVIEWER,
            task_id="",
            success=True,
            output_modules=[],
            tokens_used=0,
            execution_time_seconds=0.0,
            retry_count=0,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def review(
        self,
        code_modules: list[CodeModule],
        project_spec_summary: str,
        quality_checklist: list[str] | None = None,
    ) -> ReviewResult:
        """Perform an independent review of generated code.

        Parameters
        ----------
        code_modules:
            The code modules to review (NO coder conversation context).
        project_spec_summary:
            A summary of the project specification for reference.
        quality_checklist:
            Optional checklist items to verify.

        Returns
        -------
        ReviewResult
            The review verdict, score, comments, and blocking issues.
        """
        if self.llm_client is None:
            logger.info("reviewer.heuristic_fallback")
            return self._review_heuristic(code_modules)

        checklist_text = ""
        if quality_checklist:
            checklist_text = "\n\nQuality Checklist:\n" + "\n".join(
                f"- {item}" for item in quality_checklist
            )

        modules_text = "\n\n".join(
            f"### {m.module_path} ({m.language}, {m.loc} LOC)\n```\n{m.content}\n```"
            for m in code_modules
        )

        context = (
            f"## Project Specification\n{project_spec_summary}\n\n"
            f"## Code Modules to Review\n{modules_text}"
            f"{checklist_text}\n\n"
            "Review the code above. Provide your verdict, score (0-100), "
            "blocking issues, and suggestions."
        )

        output = await self.run(context)

        # Map agent output to ReviewResult.
        return ReviewResult(
            verdict=ReviewVerdict.PASS if output.success else ReviewVerdict.FAIL,
            score=75.0 if output.success else 30.0,
            comments=[],
            blocking_issues=[],
        )

    # ------------------------------------------------------------------
    # Heuristic fallback
    # ------------------------------------------------------------------

    def _review_heuristic(self, code_modules: list[CodeModule]) -> ReviewResult:
        """Basic heuristic review when no LLM client is available.

        Checks for non-empty modules, presence of test files, and
        reasonable lines of code.
        """
        comments: list[str] = []
        blocking_issues: list[str] = []

        if not code_modules:
            return ReviewResult(
                verdict=ReviewVerdict.FAIL,
                score=0.0,
                comments=["No code modules provided."],
                blocking_issues=["Empty code submission."],
            )

        empty_modules = [m for m in code_modules if not m.content.strip()]
        if empty_modules:
            paths = [m.module_path for m in empty_modules]
            blocking_issues.append(f"Empty modules detected: {', '.join(paths)}")

        has_tests = any(
            m.test_file_path is not None or "test" in m.module_path.lower() for m in code_modules
        )
        if not has_tests:
            comments.append("No test files detected — consider adding tests.")

        total_loc = sum(m.loc for m in code_modules)
        if total_loc < 10:
            comments.append(f"Very low total LOC ({total_loc}) — may be incomplete.")

        if blocking_issues:
            return ReviewResult(
                verdict=ReviewVerdict.FAIL,
                score=20.0,
                comments=comments,
                blocking_issues=blocking_issues,
            )

        score = 70.0
        if has_tests:
            score += 10.0
        if total_loc >= 50:
            score += 5.0

        return ReviewResult(
            verdict=ReviewVerdict.PASS_WITH_SUGGESTIONS,
            score=min(score, 100.0),
            comments=comments,
            blocking_issues=[],
        )
