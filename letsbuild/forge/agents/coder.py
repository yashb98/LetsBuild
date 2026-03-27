"""Coder agent — implements coding tasks within the Code Forge sandbox."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from letsbuild.forge.base_agent import BaseAgent
from letsbuild.forge.tools import (
    BASH_EXECUTE_TOOL,
    INSTALL_PACKAGE_TOOL,
    READ_FILE_TOOL,
    WRITE_FILE_TOOL,
)
from letsbuild.models.forge_models import (
    AgentOutput,
    AgentRole,
    CodeModule,
    Task,
)

if TYPE_CHECKING:
    from letsbuild.harness.llm_client import LLMClient

logger = structlog.get_logger()


class CoderAgent(BaseAgent):
    """Implements a single coding task, producing one or more :class:`CodeModule` outputs.

    The Coder has full sandbox access: ``write_file``, ``bash_execute``,
    ``install_package``, and ``read_file``.  When no LLM client is
    available it falls back to :meth:`_code_heuristic`.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        workspace_path: str | None = None,
    ) -> None:
        super().__init__(
            role=AgentRole.CODER,
            llm_client=llm_client,
            model=None,
        )
        self.workspace_path = workspace_path or "/mnt/workspace"

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def system_prompt(self) -> str:
        """Return the system prompt for the Coder agent."""
        return (
            "You are the Coder agent in the LetsBuild Code Forge.\n\n"
            "Your job is to implement a coding task inside the sandbox workspace "
            f"at {self.workspace_path}.\n\n"
            "Rules:\n"
            "1. Write clean, production-quality code with proper typing and docstrings.\n"
            "2. Create parent directories before writing files.\n"
            "3. Install any required packages using install_package before importing them.\n"
            "4. After writing code, run it or its tests with bash_execute to verify correctness.\n"
            "5. If a test fails, read the error output carefully and fix the code — do not "
            "regenerate from scratch.\n"
            "6. When finished, confirm all files are written and tests pass.\n"
            "7. Use read_file to inspect existing code before modifying it."
        )

    def tools(self) -> list[dict[str, object]]:
        """Return the full sandbox tool set for the Coder."""
        return [WRITE_FILE_TOOL, BASH_EXECUTE_TOOL, INSTALL_PACKAGE_TOOL, READ_FILE_TOOL]

    async def process_result(self, response: object) -> AgentOutput:
        """Extract CodeModule list from the LLM response.

        Returns a minimal successful AgentOutput; the base ``run`` method
        wraps timing and token information.
        """
        return AgentOutput(
            agent_role=AgentRole.CODER,
            task_id="",
            success=True,
            output_modules=[],
            tokens_used=0,
            execution_time_seconds=0.0,
            retry_count=0,
        )

    # ------------------------------------------------------------------
    # Public convenience API
    # ------------------------------------------------------------------

    async def code(self, task: Task, project_context: str) -> AgentOutput:
        """Implement *task* within the project described by *project_context*.

        If no LLM client is configured the heuristic fallback is used.
        """
        if self.llm_client is None:
            logger.info("coder.heuristic_fallback", task_id=task.task_id)
            return self._code_heuristic(task)

        context = (
            f"Project context:\n{project_context}\n\n"
            f"Task: {task.module_name}\n"
            f"Description: {task.description}\n"
            f"Complexity: {task.estimated_complexity}/10\n"
            f"Workspace: {self.workspace_path}\n\n"
            "Implement this task. Write all necessary files and verify they work."
        )

        return await self.run(context, task_id=task.task_id)

    # ------------------------------------------------------------------
    # Heuristic fallback
    # ------------------------------------------------------------------

    def _code_heuristic(self, task: Task) -> AgentOutput:
        """Generate a simple Python module stub without an LLM call."""
        module_name = task.module_name.replace("/", ".").removesuffix(".py")
        safe_name = module_name.replace(".", "_")
        content = (
            f'"""Module: {module_name}\n\n'
            f"{task.description}\n"
            f'"""\n\n'
            f"from __future__ import annotations\n\n\n"
            f"def {safe_name}_main() -> str:\n"
            f'    """Entry point for {module_name}."""\n'
            f'    return "{module_name} stub"\n'
        )
        loc = content.count("\n")
        module = CodeModule(
            module_path=task.module_name,
            content=content,
            language="python",
            loc=loc,
        )
        return AgentOutput(
            agent_role=AgentRole.CODER,
            task_id=task.task_id,
            success=True,
            output_modules=[module],
            tokens_used=0,
            execution_time_seconds=0.0,
            retry_count=0,
        )
