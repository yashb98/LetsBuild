"""Tests for sandbox tool definitions and executors."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import pytest

from letsbuild.forge.tools import (
    BASH_EXECUTE_TOOL,
    DOCKER_BUILD_TOOL,
    INSTALL_PACKAGE_TOOL,
    LIST_DIRECTORY_TOOL,
    READ_FILE_TOOL,
    WRITE_FILE_TOOL,
    ToolExecutor,
    ToolRegistry,
)

# ---------------------------------------------------------------------------
# Tool Schema Tests
# ---------------------------------------------------------------------------

_ALL_SCHEMAS = [
    WRITE_FILE_TOOL,
    READ_FILE_TOOL,
    BASH_EXECUTE_TOOL,
    INSTALL_PACKAGE_TOOL,
    LIST_DIRECTORY_TOOL,
    DOCKER_BUILD_TOOL,
]


def test_all_tools_have_required_fields() -> None:
    """Every tool schema must have name, description, and input_schema."""
    for schema in _ALL_SCHEMAS:
        assert "name" in schema, f"Missing 'name' in {schema}"
        assert "description" in schema, f"Missing 'description' in {schema}"
        assert "input_schema" in schema, f"Missing 'input_schema' in {schema}"
        input_schema = schema["input_schema"]
        assert isinstance(input_schema, dict)
        assert input_schema.get("type") == "object"


# ---------------------------------------------------------------------------
# ToolRegistry Tests
# ---------------------------------------------------------------------------


def test_tool_registry_get_tools() -> None:
    """get_tools returns the correct schemas for the requested names."""
    names = ["write_file", "read_file"]
    tools = ToolRegistry.get_tools(names)
    assert len(tools) == 2
    assert tools[0]["name"] == "write_file"
    assert tools[1]["name"] == "read_file"


def test_tool_registry_get_tools_unknown_raises() -> None:
    """get_tools raises KeyError for unknown tool names."""
    with pytest.raises(KeyError, match="no_such_tool"):
        ToolRegistry.get_tools(["no_such_tool"])


def test_tool_registry_get_schema() -> None:
    """get_schema returns a single tool schema by name."""
    schema = ToolRegistry.get_schema("bash_execute")
    assert schema["name"] == "bash_execute"
    assert "input_schema" in schema


def test_tool_registry_get_schema_unknown_raises() -> None:
    """get_schema raises KeyError for unknown tool name."""
    with pytest.raises(KeyError, match="nope"):
        ToolRegistry.get_schema("nope")


# ---------------------------------------------------------------------------
# ToolExecutor Tests (local fallback, no sandbox)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_executor_write_file(tmp_path: Path) -> None:
    """write_file creates a file with expected content using local fallback."""
    executor = ToolExecutor(workspace_root=tmp_path)
    result = await executor.execute(
        "write_file",
        {"file_path": "subdir/hello.txt", "content": "hello world"},
    )
    assert result["success"] is True
    assert (tmp_path / "subdir" / "hello.txt").read_text() == "hello world"


@pytest.mark.asyncio
async def test_tool_executor_read_file(tmp_path: Path) -> None:
    """read_file returns the content of an existing file."""
    target = tmp_path / "data.txt"
    target.write_text("some data")

    executor = ToolExecutor(workspace_root=tmp_path)
    result = await executor.execute("read_file", {"file_path": "data.txt"})
    assert result["success"] is True
    assert result["result"] == "some data"


@pytest.mark.asyncio
async def test_tool_executor_read_file_not_found(tmp_path: Path) -> None:
    """read_file returns error for missing file."""
    executor = ToolExecutor(workspace_root=tmp_path)
    result = await executor.execute("read_file", {"file_path": "missing.txt"})
    assert result["success"] is False
    assert "not found" in str(result["error"]).lower()


@pytest.mark.asyncio
async def test_tool_executor_bash_execute(tmp_path: Path) -> None:
    """bash_execute runs a simple echo command and captures stdout."""
    executor = ToolExecutor(workspace_root=tmp_path)
    result = await executor.execute(
        "bash_execute",
        {"command": "echo hello"},
    )
    assert result["success"] is True
    assert "hello" in str(result["result"])


@pytest.mark.asyncio
async def test_tool_executor_list_directory(tmp_path: Path) -> None:
    """list_directory returns entries in the given directory."""
    (tmp_path / "aaa.txt").write_text("a")
    (tmp_path / "bbb.txt").write_text("b")

    executor = ToolExecutor(workspace_root=tmp_path)
    result = await executor.execute("list_directory", {"path": "."})
    assert result["success"] is True
    assert "aaa.txt" in str(result["result"])
    assert "bbb.txt" in str(result["result"])


@pytest.mark.asyncio
async def test_tool_executor_unknown_tool_returns_error(tmp_path: Path) -> None:
    """Calling an unknown tool returns a structured error, not an exception."""
    executor = ToolExecutor(workspace_root=tmp_path)
    result = await executor.execute("nonexistent_tool", {})
    assert result["success"] is False
    assert "Unknown tool" in str(result["error"])
    assert result["error_category"] == "validation"
    assert result["is_retryable"] is False
