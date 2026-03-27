"""Sandbox tool definitions and executors for Code Forge agents."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import ClassVar

import structlog

from letsbuild.harness.sandbox import Sandbox, SandboxManager  # noqa: TC001

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Tool Schema Definitions (Claude tool_use format)
# ---------------------------------------------------------------------------

WRITE_FILE_TOOL: dict[str, object] = {
    "name": "write_file",
    "description": (
        "Write content to a file at the given path inside the sandbox workspace. "
        "Creates parent directories automatically. Overwrites if the file exists."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Relative or absolute path to the file inside the sandbox.",
            },
            "content": {
                "type": "string",
                "description": "Full text content to write to the file.",
            },
        },
        "required": ["file_path", "content"],
    },
}

READ_FILE_TOOL: dict[str, object] = {
    "name": "read_file",
    "description": ("Read the contents of a file at the given path inside the sandbox workspace."),
    "input_schema": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Relative or absolute path to the file inside the sandbox.",
            },
        },
        "required": ["file_path"],
    },
}

BASH_EXECUTE_TOOL: dict[str, object] = {
    "name": "bash_execute",
    "description": (
        "Execute a bash command inside the sandbox container. "
        "Returns stdout, stderr, and exit code."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute.",
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum seconds to wait before killing the command.",
                "default": 60,
            },
        },
        "required": ["command"],
    },
}

INSTALL_PACKAGE_TOOL: dict[str, object] = {
    "name": "install_package",
    "description": (
        "Install one or more packages using the specified package manager "
        "(pip, npm, apt, cargo, etc.) inside the sandbox."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "package_manager": {
                "type": "string",
                "description": "Package manager to use: 'pip', 'npm', 'apt', 'cargo'.",
                "enum": ["pip", "npm", "apt", "cargo"],
            },
            "packages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of package names to install.",
            },
        },
        "required": ["package_manager", "packages"],
    },
}

LIST_DIRECTORY_TOOL: dict[str, object] = {
    "name": "list_directory",
    "description": ("List files and directories at the given path inside the sandbox workspace."),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path to list. Defaults to the workspace root.",
                "default": ".",
            },
        },
        "required": [],
    },
}

DOCKER_BUILD_TOOL: dict[str, object] = {
    "name": "docker_build",
    "description": ("Build a Docker image from a Dockerfile inside the sandbox workspace."),
    "input_schema": {
        "type": "object",
        "properties": {
            "dockerfile_path": {
                "type": "string",
                "description": "Path to the Dockerfile relative to the workspace root.",
            },
            "tag": {
                "type": "string",
                "description": "Tag for the built image (e.g. 'myapp:latest').",
            },
        },
        "required": ["dockerfile_path", "tag"],
    },
}

_ALL_TOOL_SCHEMAS: list[dict[str, object]] = [
    WRITE_FILE_TOOL,
    READ_FILE_TOOL,
    BASH_EXECUTE_TOOL,
    INSTALL_PACKAGE_TOOL,
    LIST_DIRECTORY_TOOL,
    DOCKER_BUILD_TOOL,
]


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------


class ToolRegistry:
    """Registry mapping tool names to their Claude tool_use schema definitions."""

    ALL_TOOLS: ClassVar[dict[str, dict[str, object]]] = {
        str(t["name"]): t for t in _ALL_TOOL_SCHEMAS
    }

    @classmethod
    def get_tools(cls, names: list[str]) -> list[dict[str, object]]:
        """Return tool schemas for the given list of tool names.

        Raises ``KeyError`` if any name is not registered.
        """
        result: list[dict[str, object]] = []
        for name in names:
            if name not in cls.ALL_TOOLS:
                raise KeyError(f"Unknown tool: {name!r}")
            result.append(cls.ALL_TOOLS[name])
        return result

    @classmethod
    def get_schema(cls, name: str) -> dict[str, object]:
        """Return the schema for a single tool by name.

        Raises ``KeyError`` if not found.
        """
        if name not in cls.ALL_TOOLS:
            raise KeyError(f"Unknown tool: {name!r}")
        return cls.ALL_TOOLS[name]


# ---------------------------------------------------------------------------
# ToolExecutor
# ---------------------------------------------------------------------------

_INSTALL_COMMANDS: dict[str, str] = {
    "pip": "pip install",
    "npm": "npm install",
    "apt": "apt-get install -y",
    "cargo": "cargo install",
}


class ToolExecutor:
    """Dispatches tool calls to the appropriate handler.

    When a ``Sandbox`` is provided, commands run inside the Docker container.
    When no sandbox is available (e.g. during tests), a local filesystem
    fallback is used instead.
    """

    def __init__(
        self,
        sandbox: Sandbox | None = None,
        sandbox_manager: SandboxManager | None = None,
        *,
        workspace_root: Path | None = None,
    ) -> None:
        self._sandbox = sandbox
        self._sandbox_manager = sandbox_manager
        # Local fallback workspace (used when no sandbox).
        self._workspace_root = workspace_root or Path.cwd()

    # -- public dispatch -----------------------------------------------------

    async def execute(
        self,
        tool_name: str,
        tool_input: dict[str, object],
    ) -> dict[str, object]:
        """Execute a tool call and return a structured result dict.

        Returns
        -------
        dict with keys:
            success : bool
            result  : str
            error   : str | None
        """
        handler_map: dict[str, object] = {
            "write_file": self._write_file,
            "read_file": self._read_file,
            "bash_execute": self._bash_execute,
            "install_package": self._install_package,
            "list_directory": self._list_directory,
            "docker_build": self._docker_build,
        }

        handler = handler_map.get(tool_name)
        if handler is None:
            logger.warning("tool_executor.unknown_tool", tool_name=tool_name)
            return {
                "success": False,
                "result": "",
                "error": f"Unknown tool: {tool_name!r}",
                "error_category": "validation",
                "is_retryable": False,
            }

        try:
            # All handlers are async callables.
            return await handler(tool_input)  # type: ignore[operator]
        except Exception as exc:
            logger.error(
                "tool_executor.handler_failed",
                tool_name=tool_name,
                error=str(exc),
            )
            return {
                "success": False,
                "result": "",
                "error": str(exc),
                "error_category": "transient",
                "is_retryable": True,
            }

    # -- private handlers ----------------------------------------------------

    def _resolve_path(self, file_path: str) -> Path:
        """Resolve a file path relative to the workspace root (local mode)."""
        p = Path(file_path)
        if p.is_absolute():
            return p
        return self._workspace_root / p

    async def _write_file(self, inp: dict[str, object]) -> dict[str, object]:
        file_path = str(inp["file_path"])
        content = str(inp["content"])

        if self._sandbox and self._sandbox_manager:
            cmd = (
                f"mkdir -p \"$(dirname '{file_path}')\" && "
                f"cat > '{file_path}' << 'LETSBUILD_EOF'\n{content}\nLETSBUILD_EOF"
            )
            result = await self._sandbox_manager.execute(self._sandbox, cmd)
            if result.exit_code != 0:
                return {
                    "success": False,
                    "result": result.stderr or result.stdout,
                    "error": f"write_file failed with exit code {result.exit_code}",
                    "error_category": "transient",
                    "is_retryable": True,
                }
            return {"success": True, "result": f"Wrote {file_path}", "error": None}

        # Local fallback
        resolved = self._resolve_path(file_path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return {"success": True, "result": f"Wrote {resolved}", "error": None}

    async def _read_file(self, inp: dict[str, object]) -> dict[str, object]:
        file_path = str(inp["file_path"])

        if self._sandbox and self._sandbox_manager:
            result = await self._sandbox_manager.execute(self._sandbox, f"cat '{file_path}'")
            if result.exit_code != 0:
                return {
                    "success": False,
                    "result": "",
                    "error": f"read_file failed: {result.stderr or result.stdout}",
                    "error_category": "validation",
                    "is_retryable": False,
                }
            return {"success": True, "result": result.stdout, "error": None}

        # Local fallback
        resolved = self._resolve_path(file_path)
        if not resolved.exists():
            return {
                "success": False,
                "result": "",
                "error": f"File not found: {resolved}",
                "error_category": "validation",
                "is_retryable": False,
            }
        content = resolved.read_text(encoding="utf-8")
        return {"success": True, "result": content, "error": None}

    async def _bash_execute(self, inp: dict[str, object]) -> dict[str, object]:
        command = str(inp["command"])
        timeout = int(inp.get("timeout", 60) or 60)

        if self._sandbox and self._sandbox_manager:
            result = await self._sandbox_manager.execute(self._sandbox, command, timeout=timeout)
            return {
                "success": result.exit_code == 0,
                "result": result.stdout,
                "error": result.stderr if result.exit_code != 0 else None,
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
            }

        # Local fallback — run via asyncio subprocess
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._workspace_root),
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            stdout_str = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr_str = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            exit_code = proc.returncode or 0
            return {
                "success": exit_code == 0,
                "result": stdout_str,
                "error": stderr_str if exit_code != 0 else None,
                "exit_code": exit_code,
                "timed_out": False,
            }
        except TimeoutError:
            return {
                "success": False,
                "result": "",
                "error": f"Command timed out after {timeout}s",
                "exit_code": -1,
                "timed_out": True,
            }

    async def _install_package(self, inp: dict[str, object]) -> dict[str, object]:
        manager = str(inp["package_manager"])
        packages = [str(p) for p in inp["packages"]]  # type: ignore[union-attr]

        if manager not in _INSTALL_COMMANDS:
            return {
                "success": False,
                "result": "",
                "error": f"Unsupported package manager: {manager!r}",
                "error_category": "validation",
                "is_retryable": False,
            }

        cmd = f"{_INSTALL_COMMANDS[manager]} {' '.join(packages)}"
        return await self._bash_execute({"command": cmd, "timeout": 120})

    async def _list_directory(self, inp: dict[str, object]) -> dict[str, object]:
        path = str(inp.get("path", ".") or ".")

        if self._sandbox and self._sandbox_manager:
            result = await self._sandbox_manager.execute(self._sandbox, f"ls -la '{path}'")
            return {
                "success": result.exit_code == 0,
                "result": result.stdout,
                "error": result.stderr if result.exit_code != 0 else None,
            }

        # Local fallback
        resolved = self._resolve_path(path)
        if not resolved.exists():
            return {
                "success": False,
                "result": "",
                "error": f"Directory not found: {resolved}",
                "error_category": "validation",
                "is_retryable": False,
            }
        if not resolved.is_dir():
            return {
                "success": False,
                "result": "",
                "error": f"Not a directory: {resolved}",
                "error_category": "validation",
                "is_retryable": False,
            }
        entries = sorted(os.listdir(resolved))
        return {"success": True, "result": "\n".join(entries), "error": None}

    async def _docker_build(self, inp: dict[str, object]) -> dict[str, object]:
        dockerfile_path = str(inp["dockerfile_path"])
        tag = str(inp["tag"])

        cmd = f"docker build -f '{dockerfile_path}' -t '{tag}' ."
        return await self._bash_execute({"command": cmd, "timeout": 300})
