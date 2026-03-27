"""Tests for the IntegratorAgent in the Code Forge."""

from __future__ import annotations

import pytest

from letsbuild.forge.agents.integrator import IntegratorAgent
from letsbuild.models.forge_models import AgentRole, CodeModule

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_code_module(name: str = "main.py", loc: int = 20) -> CodeModule:
    """Create a minimal CodeModule for testing."""
    return CodeModule(
        module_path=f"src/{name}",
        content=f'"""Module {name}."""\n\ndef run() -> str:\n    return "ok"\n',
        language="python",
        loc=loc,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_integrator_has_correct_tools() -> None:
    """IntegratorAgent declares exactly 4 tools including docker_build."""
    agent = IntegratorAgent()
    tool_schemas = agent.tools()

    assert len(tool_schemas) == 4
    tool_names = [str(t["name"]) for t in tool_schemas]
    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "bash_execute" in tool_names
    assert "docker_build" in tool_names


def test_integrator_heuristic_returns_output() -> None:
    """Heuristic fallback returns a successful AgentOutput."""
    agent = IntegratorAgent()
    modules = [_make_code_module("a.py"), _make_code_module("b.py")]
    output = agent._integrate_heuristic(modules)

    assert output.success is True
    assert output.agent_role == AgentRole.INTEGRATOR
    assert len(output.output_modules) == 2
    assert output.tokens_used == 0


@pytest.mark.asyncio
async def test_integrator_combines_modules() -> None:
    """integrate() without LLM falls back to heuristic and returns combined modules."""
    agent = IntegratorAgent()
    modules = [
        _make_code_module("api.py", loc=50),
        _make_code_module("db.py", loc=30),
        _make_code_module("utils.py", loc=10),
    ]

    output = await agent.integrate(modules, integration_plan="Run pytest and build Docker image.")

    assert output.success is True
    assert output.agent_role == AgentRole.INTEGRATOR
    assert len(output.output_modules) == 3
    paths = [m.module_path for m in output.output_modules]
    assert "src/api.py" in paths
    assert "src/db.py" in paths
    assert "src/utils.py" in paths
