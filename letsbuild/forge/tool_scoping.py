"""Tool scoping enforcement for Code Forge agents.

Each agent gets a limited set of tools (max 5) to prevent cross-specialisation.
This module enforces those boundaries as deterministic Python code, not prompts.
"""

from __future__ import annotations

import structlog

from letsbuild.models.forge_models import AgentRole

logger = structlog.get_logger()

AGENT_TOOL_SCOPES: dict[AgentRole, list[str]] = {
    AgentRole.PLANNER: ["read_file", "list_directory"],
    AgentRole.CODER: ["write_file", "bash_execute", "install_package", "read_file"],
    AgentRole.TESTER: ["read_file", "bash_execute", "write_file"],
    AgentRole.REVIEWER: ["read_file", "list_directory"],
    AgentRole.INTEGRATOR: ["read_file", "write_file", "bash_execute", "docker_build"],
}


class ToolScopingEnforcer:
    """Enforces that agents only use their allowed tools."""

    def __init__(self) -> None:
        self._log = structlog.get_logger(component="tool_scoping_enforcer")

    def validate_tools(self, role: AgentRole, requested_tools: list[str]) -> list[str]:
        """Check each requested tool against the allowed scope for *role*.

        Returns a list of unauthorized tool names (empty if all OK).
        """
        allowed = set(AGENT_TOOL_SCOPES[role])
        return [t for t in requested_tools if t not in allowed]

    def enforce(self, role: AgentRole, requested_tools: list[str]) -> None:
        """Raise ``ValueError`` if any requested tool is not allowed for *role*."""
        violations = self.validate_tools(role, requested_tools)
        if violations:
            self._log.warning(
                "tool_scoping_violation",
                role=role.value,
                violations=violations,
                allowed=AGENT_TOOL_SCOPES[role],
            )
            msg = (
                f"Agent role {role.value!r} is not allowed tools: "
                f"{', '.join(violations)}. "
                f"Allowed: {AGENT_TOOL_SCOPES[role]}"
            )
            raise ValueError(msg)

    def filter_tools(
        self, role: AgentRole, all_tools: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """Return only the tools from *all_tools* that are allowed for *role*.

        Each tool dict is expected to have a ``"name"`` key.
        """
        allowed = set(AGENT_TOOL_SCOPES[role])
        return [t for t in all_tools if t.get("name") in allowed]

    def get_allowed_tools(self, role: AgentRole) -> list[str]:
        """Return the list of allowed tool names for *role*."""
        return list(AGENT_TOOL_SCOPES[role])
