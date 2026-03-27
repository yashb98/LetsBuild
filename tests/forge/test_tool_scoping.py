"""Tests for Code Forge tool scoping enforcement."""

from __future__ import annotations

import pytest

from letsbuild.forge.tool_scoping import AGENT_TOOL_SCOPES, ToolScopingEnforcer
from letsbuild.models.forge_models import AgentRole


@pytest.fixture
def enforcer() -> ToolScopingEnforcer:
    """Create a fresh ToolScopingEnforcer for each test."""
    return ToolScopingEnforcer()


# ---------------------------------------------------------------------------
# Allowed-tools-per-role tests
# ---------------------------------------------------------------------------


def test_planner_allowed_tools(enforcer: ToolScopingEnforcer) -> None:
    """Planner should only have read_file and list_directory."""
    allowed = enforcer.get_allowed_tools(AgentRole.PLANNER)
    assert set(allowed) == {"read_file", "list_directory"}


def test_coder_allowed_tools(enforcer: ToolScopingEnforcer) -> None:
    """Coder should have write_file, bash_execute, install_package, read_file."""
    allowed = enforcer.get_allowed_tools(AgentRole.CODER)
    assert set(allowed) == {"write_file", "bash_execute", "install_package", "read_file"}


def test_reviewer_allowed_tools(enforcer: ToolScopingEnforcer) -> None:
    """Reviewer should only have read_file and list_directory."""
    allowed = enforcer.get_allowed_tools(AgentRole.REVIEWER)
    assert set(allowed) == {"read_file", "list_directory"}


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


def test_validate_no_violations(enforcer: ToolScopingEnforcer) -> None:
    """Valid tools for a role should return an empty violations list."""
    violations = enforcer.validate_tools(AgentRole.CODER, ["read_file", "write_file"])
    assert violations == []


def test_validate_violations(enforcer: ToolScopingEnforcer) -> None:
    """Unauthorized tool should appear in the violations list."""
    violations = enforcer.validate_tools(
        AgentRole.PLANNER, ["read_file", "write_file", "bash_execute"]
    )
    assert "write_file" in violations
    assert "bash_execute" in violations
    assert "read_file" not in violations


# ---------------------------------------------------------------------------
# Enforce tests
# ---------------------------------------------------------------------------


def test_enforce_raises_on_violation(enforcer: ToolScopingEnforcer) -> None:
    """enforce() should raise ValueError when unauthorized tools are requested."""
    with pytest.raises(ValueError, match=r"not allowed tools"):
        enforcer.enforce(AgentRole.REVIEWER, ["read_file", "docker_build"])


def test_enforce_passes_on_valid(enforcer: ToolScopingEnforcer) -> None:
    """enforce() should not raise when all tools are authorized."""
    enforcer.enforce(AgentRole.TESTER, ["read_file", "bash_execute", "write_file"])


# ---------------------------------------------------------------------------
# Filter tools test
# ---------------------------------------------------------------------------


def test_filter_tools(enforcer: ToolScopingEnforcer) -> None:
    """filter_tools() should remove unauthorized tools from the full list."""
    all_tools: list[dict[str, object]] = [
        {"name": "read_file", "description": "Read a file"},
        {"name": "write_file", "description": "Write a file"},
        {"name": "bash_execute", "description": "Execute bash"},
        {"name": "docker_build", "description": "Build Docker image"},
        {"name": "list_directory", "description": "List directory"},
    ]
    filtered = enforcer.filter_tools(AgentRole.PLANNER, all_tools)
    names = [t["name"] for t in filtered]
    assert set(names) == {"read_file", "list_directory"}


# ---------------------------------------------------------------------------
# Max 5 tools per role
# ---------------------------------------------------------------------------


def test_max_five_tools_per_role() -> None:
    """No role should have more than 5 allowed tools."""
    for role, tools in AGENT_TOOL_SCOPES.items():
        assert len(tools) <= 5, f"{role.value} has {len(tools)} tools, max is 5"
