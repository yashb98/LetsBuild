"""Integrator agent — assembles modules, runs integration tests, and builds Docker images."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from letsbuild.forge.base_agent import BaseAgent
from letsbuild.forge.tools import (
    BASH_EXECUTE_TOOL,
    DOCKER_BUILD_TOOL,
    READ_FILE_TOOL,
    WRITE_FILE_TOOL,
)
from letsbuild.models.forge_models import (
    AgentOutput,
    AgentRole,
    CodeModule,
)

if TYPE_CHECKING:
    from letsbuild.harness.llm_client import LLMClient

logger = structlog.get_logger()


class IntegratorAgent(BaseAgent):
    """Assembles code modules, runs integration tests, and performs Docker builds.

    The Integrator has full sandbox access: ``read_file``, ``write_file``,
    ``bash_execute``, and ``docker_build``.  When no LLM client is available
    it falls back to :meth:`_integrate_heuristic`.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        workspace_path: str | None = None,
    ) -> None:
        super().__init__(
            role=AgentRole.INTEGRATOR,
            llm_client=llm_client,
            model=None,
        )
        self.workspace_path = workspace_path or "/mnt/workspace"

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def system_prompt(self) -> str:
        """Return the system prompt for the Integrator agent."""
        return (
            "You are the Integrator agent in the LetsBuild Code Forge.\n\n"
            "Your job is to assemble all code modules into a cohesive project, "
            "run integration tests, and perform Docker builds inside the sandbox "
            f"workspace at {self.workspace_path}.\n\n"
            "Rules:\n"
            "1. Read each module to understand its public interface and dependencies.\n"
            "2. Write any missing glue code (e.g. __init__.py, entry points, configs).\n"
            "3. Run integration tests with bash_execute to verify modules work together.\n"
            "4. If a Dockerfile exists, build the Docker image with docker_build.\n"
            "5. Fix integration issues by writing targeted patches — do not rewrite modules.\n"
            "6. When finished, confirm all integration tests pass and the project builds."
        )

    def tools(self) -> list[dict[str, object]]:
        """Return the tool set for the Integrator (read, write, bash, docker_build)."""
        return [READ_FILE_TOOL, WRITE_FILE_TOOL, BASH_EXECUTE_TOOL, DOCKER_BUILD_TOOL]

    async def process_result(self, response: object) -> AgentOutput:
        """Extract integration result from the LLM response.

        Returns a minimal successful AgentOutput; the base ``run`` method
        wraps timing and token information.
        """
        return AgentOutput(
            agent_role=AgentRole.INTEGRATOR,
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

    async def integrate(
        self,
        code_modules: list[CodeModule],
        integration_plan: str,
    ) -> AgentOutput:
        """Assemble *code_modules* and run integration according to *integration_plan*.

        If no LLM client is configured the heuristic fallback is used.
        """
        if self.llm_client is None:
            logger.info("integrator.heuristic_fallback", module_count=len(code_modules))
            return self._integrate_heuristic(code_modules)

        module_listing = "\n".join(
            f"- {m.module_path} ({m.language}, {m.loc} LOC)" for m in code_modules
        )

        context = (
            f"Integration plan:\n{integration_plan}\n\n"
            f"Modules to integrate ({len(code_modules)} total):\n{module_listing}\n\n"
            f"Workspace: {self.workspace_path}\n\n"
            "Assemble the modules, write any glue code, run integration tests, "
            "and build Docker images if applicable."
        )

        return await self.run(context)

    # ------------------------------------------------------------------
    # Heuristic fallback
    # ------------------------------------------------------------------

    def _integrate_heuristic(self, code_modules: list[CodeModule]) -> AgentOutput:
        """Return success with the combined modules (no LLM needed)."""
        return AgentOutput(
            agent_role=AgentRole.INTEGRATOR,
            task_id="integration",
            success=True,
            output_modules=list(code_modules),
            tokens_used=0,
            execution_time_seconds=0.0,
            retry_count=0,
        )
