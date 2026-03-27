"""Tests for letsbuild.forge.agents.tester — TesterAgent."""

from __future__ import annotations

from letsbuild.forge.agents.tester import TesterAgent
from letsbuild.models.forge_models import AgentRole, CodeModule


def test_tester_has_correct_tools() -> None:
    """TesterAgent declares exactly read_file, bash_execute, write_file."""
    agent = TesterAgent()
    tool_names = [t["name"] for t in agent.tools()]
    assert tool_names == ["read_file", "bash_execute", "write_file"]
    assert len(tool_names) <= 5


def test_tester_heuristic_returns_pass() -> None:
    """Heuristic fallback produces a successful AgentOutput without an LLM."""
    modules = [
        CodeModule(
            module_path="src/app.py",
            content="print('hello')",
            language="python",
            loc=1,
        ),
    ]
    result = TesterAgent._test_heuristic(modules)

    assert result.success is True
    assert result.agent_role == AgentRole.TESTER
    assert result.tokens_used == 0
    assert len(result.output_modules) == 1
    assert "src/app.py" in result.output_modules[0].content
