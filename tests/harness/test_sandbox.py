"""Tests for Docker sandbox models and SandboxManager (no real Docker required)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from letsbuild.harness.sandbox import ExecResult, Sandbox, SandboxManager
from letsbuild.models.config_models import SandboxConfig

# ---------------------------------------------------------------------------
# Model instantiation tests
# ---------------------------------------------------------------------------


class TestExecResult:
    """Tests for the ExecResult Pydantic model."""

    def test_instantiation_with_all_fields(self) -> None:
        """ExecResult can be created with every field explicitly set."""
        result = ExecResult(
            exit_code=0,
            stdout="hello world",
            stderr="",
            timed_out=False,
            duration_seconds=1.234,
        )
        assert result.exit_code == 0
        assert result.stdout == "hello world"
        assert result.stderr == ""
        assert result.timed_out is False
        assert result.duration_seconds == 1.234

    def test_timed_out_defaults_to_false(self) -> None:
        """timed_out should default to False when not provided."""
        result = ExecResult(
            exit_code=1,
            stdout="",
            stderr="error",
            duration_seconds=0.5,
        )
        assert result.timed_out is False


class TestSandboxModel:
    """Tests for the Sandbox Pydantic model."""

    def test_instantiation_with_defaults(self) -> None:
        """Sandbox can be created with only container_id; defaults fill in."""
        sandbox = Sandbox(container_id="abc123def456")
        assert sandbox.container_id == "abc123def456"
        assert sandbox.workspace_path == "/mnt/workspace"
        assert sandbox.status == "ready"
        assert isinstance(sandbox.created_at, datetime)

    def test_created_at_is_utc(self) -> None:
        """Default created_at timestamp should be UTC."""
        sandbox = Sandbox(container_id="test-container")
        assert sandbox.created_at.tzinfo is not None
        now = datetime.now(UTC)
        delta = abs((now - sandbox.created_at).total_seconds())
        assert delta < 5, "created_at should be close to current UTC time"

    def test_custom_workspace_path(self) -> None:
        """Sandbox accepts a custom workspace path."""
        sandbox = Sandbox(
            container_id="custom-123",
            workspace_path="/custom/path",
        )
        assert sandbox.workspace_path == "/custom/path"


# ---------------------------------------------------------------------------
# SandboxManager tests
# ---------------------------------------------------------------------------


class TestSandboxManagerCreation:
    """Tests for SandboxManager construction."""

    def test_default_config(self) -> None:
        """SandboxManager can be created with default SandboxConfig."""
        manager = SandboxManager()
        assert manager._config.base_image == "letsbuild/sandbox:latest"
        assert manager._config.cpu_limit == 4
        assert manager._config.memory_limit_gb == 8

    def test_custom_config(self) -> None:
        """SandboxManager accepts a custom SandboxConfig."""
        cfg = SandboxConfig(
            base_image="custom/image:v2",
            cpu_limit=2,
            memory_limit_gb=4,
            disk_limit_gb=10,
            lifetime_minutes=15,
            pool_size=1,
        )
        manager = SandboxManager(config=cfg)
        assert manager._config.base_image == "custom/image:v2"
        assert manager._config.cpu_limit == 2
        assert manager._config.memory_limit_gb == 4


class TestSandboxManagerProvision:
    """Tests for SandboxManager.provision (Docker mocked)."""

    @pytest.mark.asyncio
    async def test_provision_raises_when_docker_unavailable(self) -> None:
        """provision() raises RuntimeError when Docker daemon is not reachable."""
        manager = SandboxManager()
        # Import the DockerException alias used by the sandbox module
        from letsbuild.harness.sandbox import DockerException as SandboxDockerException

        with (
            patch("letsbuild.harness.sandbox.docker") as mock_docker_module,
            patch("letsbuild.harness.sandbox.DOCKER_AVAILABLE", True),
        ):
            mock_docker_module.from_env.side_effect = SandboxDockerException(
                "Cannot connect to Docker daemon"
            )
            # Reset cached client so _get_client attempts connection
            manager._client = None

            with pytest.raises(RuntimeError, match=r"Failed to connect to Docker daemon"):
                await manager.provision()

    @pytest.mark.asyncio
    async def test_provision_returns_sandbox_on_success(self) -> None:
        """provision() returns a Sandbox object when Docker is available."""
        manager = SandboxManager()

        mock_container = MagicMock()
        mock_container.id = "deadbeef1234567890"
        mock_container.short_id = "deadbeef12"

        mock_client = MagicMock()
        mock_client.containers.run.return_value = mock_container

        manager._client = mock_client

        with patch("letsbuild.harness.sandbox.DOCKER_AVAILABLE", True):
            sandbox = await manager.provision()

        assert isinstance(sandbox, Sandbox)
        assert sandbox.container_id == "deadbeef1234567890"
        assert sandbox.status == "ready"


class TestSandboxManagerExecute:
    """Tests for SandboxManager.execute (Docker mocked)."""

    @pytest.mark.asyncio
    async def test_execute_returns_exec_result(self) -> None:
        """execute() returns an ExecResult with command output."""
        manager = SandboxManager()

        mock_container = MagicMock()
        mock_container.id = "container123"

        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_client.api.exec_create.return_value = {"Id": "exec-abc"}
        mock_client.api.exec_start.return_value = b"test output\n"
        mock_client.api.exec_inspect.return_value = {"ExitCode": 0}

        manager._client = mock_client

        sandbox = Sandbox(container_id="container123")

        with patch("letsbuild.harness.sandbox.DOCKER_AVAILABLE", True):
            result = await manager.execute(sandbox, "echo test")

        assert isinstance(result, ExecResult)
        assert result.exit_code == 0
        assert "test output" in result.stdout
        assert result.timed_out is False


class TestSandboxManagerCleanup:
    """Tests for SandboxManager.cleanup (Docker mocked)."""

    @pytest.mark.asyncio
    async def test_cleanup_stops_and_removes_container(self) -> None:
        """cleanup() calls stop and remove on the container."""
        manager = SandboxManager()

        mock_container = MagicMock()
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container

        manager._client = mock_client

        sandbox = Sandbox(container_id="cleanup-container-id")

        with patch("letsbuild.harness.sandbox.DOCKER_AVAILABLE", True):
            await manager.cleanup(sandbox)

        mock_container.stop.assert_called_once_with(timeout=5)
        mock_container.remove.assert_called_once_with(force=True)
        assert sandbox.status == "stopped"

    @pytest.mark.asyncio
    async def test_cleanup_handles_not_found(self) -> None:
        """cleanup() gracefully handles a container that no longer exists."""
        manager = SandboxManager()

        mock_client = MagicMock()
        # Import the real or fallback NotFound used by the module
        from letsbuild.harness.sandbox import NotFound as SandboxNotFound

        mock_client.containers.get.side_effect = SandboxNotFound("gone")

        manager._client = mock_client

        sandbox = Sandbox(container_id="missing-container-id")

        with patch("letsbuild.harness.sandbox.DOCKER_AVAILABLE", True):
            # Should not raise
            await manager.cleanup(sandbox)

        assert sandbox.status == "stopped"
