"""Tests for BaseAgent abstract base class."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from letsbuild.forge.base_agent import BaseAgent
from letsbuild.models.forge_models import AgentOutput, AgentRole

# ------------------------------------------------------------------
# Concrete subclass for testing
# ------------------------------------------------------------------


class _StubAgent(BaseAgent):
    """Minimal concrete implementation for testing the ABC."""

    def __init__(
        self,
        role: AgentRole = AgentRole.CODER,
        llm_client: Any = None,
        model: str | None = None,
        tool_schemas: list[dict[str, object]] | None = None,
    ) -> None:
        super().__init__(role=role, llm_client=llm_client, model=model)
        self._tool_schemas = (
            tool_schemas
            if tool_schemas is not None
            else [
                {"name": "write_file", "description": "Write a file."},
                {"name": "read_file", "description": "Read a file."},
            ]
        )

    def system_prompt(self) -> str:
        return "You are a stub agent."

    def tools(self) -> list[dict[str, object]]:
        return self._tool_schemas

    async def process_result(self, response: object) -> AgentOutput:
        return AgentOutput(
            agent_role=self.role,
            task_id="stub-task",
            success=True,
            output_modules=[],
            error=None,
            tokens_used=0,
            execution_time_seconds=0.0,
            retry_count=0,
        )


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestBaseAgentABC:
    """Verify ABC enforcement."""

    def test_cannot_instantiate_abstract(self) -> None:
        """BaseAgent cannot be instantiated directly — it has abstract methods."""
        with pytest.raises(TypeError, match="abstract method"):
            BaseAgent(role=AgentRole.CODER)  # type: ignore[abstract]


class TestToolCountLimit:
    """Verify the <=5 tool scoping rule."""

    @pytest.mark.asyncio
    async def test_tool_count_limit_raises(self) -> None:
        """Running an agent with >5 tools raises ValueError."""
        six_tools: list[dict[str, object]] = [
            {"name": f"tool_{i}", "description": f"Tool {i}"} for i in range(6)
        ]
        agent = _StubAgent(
            llm_client=MagicMock(),
            tool_schemas=six_tools,
        )
        with pytest.raises(ValueError, match="maximum is 5"):
            await agent.run("do something")

    @pytest.mark.asyncio
    async def test_exactly_five_tools_ok(self) -> None:
        """Exactly 5 tools should not raise on the count check."""
        five_tools: list[dict[str, object]] = [
            {"name": f"tool_{i}", "description": f"Tool {i}"} for i in range(5)
        ]
        mock_client = MagicMock()
        mock_client.total_tokens = 0
        mock_client.run_agent_loop = AsyncMock(return_value=MagicMock())

        agent = _StubAgent(llm_client=mock_client, tool_schemas=five_tools)
        result = await agent.run("do something")
        assert result.success is True


class TestAllowedToolsProperty:
    """Verify the allowed_tools property."""

    def test_allowed_tools_property(self) -> None:
        """allowed_tools returns tool names from the tools() method."""
        agent = _StubAgent()
        assert agent.allowed_tools == ["write_file", "read_file"]

    def test_allowed_tools_empty(self) -> None:
        """An agent with no tools returns an empty list."""
        agent = _StubAgent(tool_schemas=[])
        assert agent.allowed_tools == []


class TestRunReturnsAgentOutput:
    """Verify the run() method returns a proper AgentOutput."""

    @pytest.mark.asyncio
    async def test_run_returns_agent_output(self) -> None:
        """A successful run returns AgentOutput with success=True."""
        mock_response = MagicMock()
        mock_client = MagicMock()
        mock_client.run_agent_loop = AsyncMock(return_value=mock_response)
        # Use PropertyMock so total_tokens can change between calls.
        type(mock_client).total_tokens = PropertyMock(side_effect=[0, 100])

        agent = _StubAgent(llm_client=mock_client)
        result = await agent.run("generate a file", task_id="task-123")

        assert isinstance(result, AgentOutput)
        assert result.success is True
        assert result.agent_role == AgentRole.CODER
        assert result.task_id == "task-123"
        assert result.tokens_used == 100
        assert result.execution_time_seconds >= 0.0


class TestRunErrorReturnsFailed:
    """Verify that exceptions during the loop produce a failed output."""

    @pytest.mark.asyncio
    async def test_run_error_returns_failed_output(self) -> None:
        """When the LLM client raises, run() returns success=False with StructuredError."""
        mock_client = MagicMock()
        mock_client.run_agent_loop = AsyncMock(side_effect=RuntimeError("API exploded"))
        type(mock_client).total_tokens = PropertyMock(return_value=0)

        agent = _StubAgent(llm_client=mock_client)
        result = await agent.run("generate a file")

        assert isinstance(result, AgentOutput)
        assert result.success is False
        assert result.error is not None
        assert "API exploded" in result.error.message
        assert result.error.is_retryable is True
