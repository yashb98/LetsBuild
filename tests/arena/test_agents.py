"""Tests for AgentForge Arena agents."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from letsbuild.arena.agents.architect import ArenaArchitect
from letsbuild.arena.agents.builder import ArenaBuilder
from letsbuild.arena.agents.critic import DISALLOWED_TOOLS, ArenaCritic
from letsbuild.arena.agents.frontend import ArenaFrontend
from letsbuild.arena.agents.tutor import ArenaTutor
from letsbuild.forge.base_agent import BaseAgent
from letsbuild.models.arena_models import ArenaAgentRole
from letsbuild.models.forge_models import AgentOutput

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_AGENTS: list[type[BaseAgent]] = [
    ArenaArchitect,
    ArenaBuilder,
    ArenaFrontend,
    ArenaCritic,
    ArenaTutor,
]

WRITE_TOOL_NAMES = frozenset({"write_file", "edit_file", "install_package", "docker_build"})


def _make_mock_llm_client() -> MagicMock:
    """Create a mock LLMClient with a working run_agent_loop."""
    client = MagicMock()
    client.total_tokens = 0

    # Simulate a simple end_turn response
    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_response.content = [MagicMock(type="text", text="Done")]

    async def fake_run_agent_loop(**kwargs: Any) -> MagicMock:
        client.total_tokens += 100
        return mock_response

    client.run_agent_loop = AsyncMock(side_effect=fake_run_agent_loop)
    return client


# ---------------------------------------------------------------------------
# Subclass Tests
# ---------------------------------------------------------------------------


class TestAgentSubclass:
    """Every arena agent must be a subclass of BaseAgent."""

    @pytest.mark.parametrize("agent_cls", ALL_AGENTS)
    def test_is_base_agent_subclass(self, agent_cls: type[BaseAgent]) -> None:
        assert issubclass(agent_cls, BaseAgent)


# ---------------------------------------------------------------------------
# Tool Count Tests
# ---------------------------------------------------------------------------


class TestToolCount:
    """Every agent must have ≤ 5 tools."""

    @pytest.mark.parametrize("agent_cls", ALL_AGENTS)
    def test_tool_count_le_five(self, agent_cls: type[BaseAgent]) -> None:
        agent = agent_cls()
        tools = agent.tools()
        assert len(tools) <= 5, f"{agent_cls.__name__} has {len(tools)} tools (max 5)"


# ---------------------------------------------------------------------------
# System Prompt Tests
# ---------------------------------------------------------------------------


class TestSystemPrompt:
    """Every agent must return a non-empty system prompt."""

    @pytest.mark.parametrize("agent_cls", ALL_AGENTS)
    def test_system_prompt_non_empty(self, agent_cls: type[BaseAgent]) -> None:
        agent = agent_cls()
        prompt = agent.system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0


# ---------------------------------------------------------------------------
# Run Tests (mocked LLM)
# ---------------------------------------------------------------------------


class TestAgentRun:
    """run() with mocked LLM must return AgentOutput."""

    @pytest.mark.asyncio()
    async def test_architect_run_returns_agent_output(self) -> None:
        client = _make_mock_llm_client()
        agent = ArenaArchitect(llm_client=client)
        result = await agent.run("Build a REST API")
        assert isinstance(result, AgentOutput)
        assert result.success is True

    @pytest.mark.asyncio()
    async def test_builder_run_returns_agent_output(self) -> None:
        client = _make_mock_llm_client()
        agent = ArenaBuilder(llm_client=client)
        result = await agent.run("Implement user auth")
        assert isinstance(result, AgentOutput)
        assert result.success is True

    @pytest.mark.asyncio()
    async def test_frontend_run_returns_agent_output(self) -> None:
        client = _make_mock_llm_client()
        agent = ArenaFrontend(llm_client=client)
        result = await agent.run("Build login page")
        assert isinstance(result, AgentOutput)
        assert result.success is True

    @pytest.mark.asyncio()
    async def test_critic_run_returns_agent_output(self) -> None:
        client = _make_mock_llm_client()
        agent = ArenaCritic(llm_client=client)
        result = await agent.run("Review the submitted code")
        assert isinstance(result, AgentOutput)
        assert result.success is True

    @pytest.mark.asyncio()
    async def test_tutor_run_returns_agent_output(self) -> None:
        client = _make_mock_llm_client()
        agent = ArenaTutor(llm_client=client)
        result = await agent.run("Comment on current build progress")
        assert isinstance(result, AgentOutput)
        assert result.success is True


# ---------------------------------------------------------------------------
# Critic Read-Only Tests
# ---------------------------------------------------------------------------


class TestCriticReadOnly:
    """Critic must have NO write tools."""

    def test_critic_has_no_write_tools(self) -> None:
        agent = ArenaCritic()
        tool_names = {str(t["name"]) for t in agent.tools()}
        write_tools_present = tool_names & WRITE_TOOL_NAMES
        assert not write_tools_present, f"Critic has disallowed write tools: {write_tools_present}"

    def test_disallowed_tools_constant_matches(self) -> None:
        """The DISALLOWED_TOOLS constant must include key write tools."""
        assert "write_file" in DISALLOWED_TOOLS
        assert "edit_file" in DISALLOWED_TOOLS


# ---------------------------------------------------------------------------
# Builder Wraps CoderAgent Tests
# ---------------------------------------------------------------------------


class TestBuilderWrapsCoderAgent:
    """Builder must wrap CoderAgent, not reimplement."""

    def test_builder_has_coder_attribute(self) -> None:
        from letsbuild.forge.agents.coder import CoderAgent

        builder = ArenaBuilder()
        assert hasattr(builder, "_coder")
        assert isinstance(builder._coder, CoderAgent)

    def test_builder_tools_match_coder_tools(self) -> None:
        from letsbuild.forge.agents.coder import CoderAgent

        builder = ArenaBuilder()
        coder = CoderAgent()
        builder_tool_names = [str(t["name"]) for t in builder.tools()]
        coder_tool_names = [str(t["name"]) for t in coder.tools()]
        assert builder_tool_names == coder_tool_names

    def test_builder_system_prompt_matches_coder(self) -> None:
        from letsbuild.forge.agents.coder import CoderAgent

        builder = ArenaBuilder()
        coder = CoderAgent()
        assert builder.system_prompt() == coder.system_prompt()


# ---------------------------------------------------------------------------
# Arena Role Tests
# ---------------------------------------------------------------------------


class TestArenaRoles:
    """Each agent must declare the correct arena_role."""

    def test_architect_arena_role(self) -> None:
        assert ArenaArchitect.arena_role == ArenaAgentRole.ARCHITECT

    def test_builder_arena_role(self) -> None:
        assert ArenaBuilder.arena_role == ArenaAgentRole.BUILDER

    def test_frontend_arena_role(self) -> None:
        assert ArenaFrontend.arena_role == ArenaAgentRole.FRONTEND

    def test_critic_arena_role(self) -> None:
        assert ArenaCritic.arena_role == ArenaAgentRole.CRITIC

    def test_tutor_arena_role(self) -> None:
        assert ArenaTutor.arena_role == ArenaAgentRole.TUTOR


# ---------------------------------------------------------------------------
# Tutor Tools Tests
# ---------------------------------------------------------------------------


class TestTutorTools:
    """Tutor must have ≤ 3 read-only tools."""

    def test_tutor_max_three_tools(self) -> None:
        agent = ArenaTutor()
        assert len(agent.tools()) <= 3

    def test_tutor_has_no_write_tools(self) -> None:
        agent = ArenaTutor()
        tool_names = {str(t["name"]) for t in agent.tools()}
        write_tools_present = tool_names & WRITE_TOOL_NAMES
        assert not write_tools_present, f"Tutor has disallowed write tools: {write_tools_present}"
