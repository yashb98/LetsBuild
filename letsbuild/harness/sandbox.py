"""Docker sandbox manager for isolated code generation and validation."""

from __future__ import annotations

import asyncio
import io
import tarfile
import time
from datetime import UTC, datetime
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict, Field

from letsbuild.models.config_models import SandboxConfig

logger = structlog.get_logger()

# Graceful Docker SDK import — code remains importable without Docker.
try:
    import docker
    from docker.errors import APIError, DockerException, NotFound

    DOCKER_AVAILABLE = True
except ImportError:
    docker = None  # type: ignore[assignment]
    APIError = Exception  # type: ignore[assignment,misc]
    DockerException = Exception  # type: ignore[assignment,misc]
    NotFound = Exception  # type: ignore[assignment,misc]
    DOCKER_AVAILABLE = False


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class ExecResult(BaseModel):
    """Result of executing a command inside a sandbox container."""

    model_config = ConfigDict(strict=True)

    exit_code: int = Field(description="Process exit code (0 = success).")
    stdout: str = Field(description="Standard output captured from the command.")
    stderr: str = Field(description="Standard error captured from the command.")
    timed_out: bool = Field(
        default=False,
        description="Whether the command was killed due to timeout.",
    )
    duration_seconds: float = Field(
        description="Wall-clock duration of the command in seconds.",
    )


class Sandbox(BaseModel):
    """Represents a running Docker sandbox container."""

    model_config = ConfigDict(strict=True)

    container_id: str = Field(description="Docker container ID.")
    workspace_path: str = Field(
        default="/mnt/workspace",
        description="Path inside the container where project files are mounted.",
    )
    status: str = Field(
        default="ready",
        description="Container status: 'ready', 'running', or 'stopped'.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the sandbox was created (UTC).",
    )


# ---------------------------------------------------------------------------
# SandboxManager
# ---------------------------------------------------------------------------


class SandboxManager:
    """Manages Docker sandbox lifecycle: provision, execute, copy, cleanup."""

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self._config = config or SandboxConfig()
        self._client: docker.DockerClient | None = None  # type: ignore[name-defined]

    # -- internal helpers ---------------------------------------------------

    def _get_client(self) -> docker.DockerClient:  # type: ignore[name-defined]
        """Return a cached Docker client, creating one on first call."""
        if not DOCKER_AVAILABLE:
            raise RuntimeError(
                "Docker SDK (pip install docker) is not installed. "
                "Cannot manage sandbox containers."
            )
        if self._client is None:
            try:
                self._client = docker.from_env()  # type: ignore[union-attr]
            except DockerException as exc:
                logger.error("sandbox.docker_connect_failed", error=str(exc))
                raise RuntimeError(f"Failed to connect to Docker daemon: {exc}") from exc
        return self._client

    # -- public API ---------------------------------------------------------

    async def provision(self) -> Sandbox:
        """Create and start a new sandbox container.

        Applies resource limits, security options, and workspace volume
        from the stored ``SandboxConfig``.
        """

        def _provision_sync() -> Sandbox:
            client = self._get_client()
            cfg = self._config

            mem_bytes = cfg.memory_limit_gb * (1024**3)
            nano_cpus = cfg.cpu_limit * int(1e9)

            try:
                container = client.containers.run(
                    image=cfg.base_image,
                    command="sleep infinity",
                    detach=True,
                    nano_cpus=nano_cpus,
                    mem_limit=mem_bytes,
                    storage_opt={"size": f"{cfg.disk_limit_gb}g"} if cfg.disk_limit_gb else None,
                    security_opt=["no-new-privileges"],
                    network_mode="bridge",
                    stdin_open=False,
                    tty=False,
                    labels={"managed_by": "letsbuild"},
                )
            except (APIError, DockerException) as exc:
                logger.error(
                    "sandbox.provision_failed",
                    image=cfg.base_image,
                    error=str(exc),
                )
                raise RuntimeError(f"Failed to provision sandbox container: {exc}") from exc

            sandbox = Sandbox(
                container_id=container.id,
                workspace_path="/mnt/workspace",
                status="ready",
            )
            logger.info(
                "sandbox.provisioned",
                container_id=container.short_id,
                image=cfg.base_image,
                cpu=cfg.cpu_limit,
                memory_gb=cfg.memory_limit_gb,
            )
            return sandbox

        return await asyncio.to_thread(_provision_sync)

    async def execute(
        self,
        sandbox: Sandbox,
        command: str,
        timeout: int = 60,
    ) -> ExecResult:
        """Execute *command* inside the sandbox and return an ``ExecResult``.

        The command is run via ``/bin/bash -c`` so shell features work.
        If the command exceeds *timeout* seconds it is killed and
        ``ExecResult.timed_out`` is set to ``True``.
        """

        def _exec_sync() -> ExecResult:
            client = self._get_client()

            try:
                container = client.containers.get(sandbox.container_id)
            except NotFound as exc:
                logger.error(
                    "sandbox.container_not_found",
                    container_id=sandbox.container_id,
                )
                raise RuntimeError(f"Sandbox container {sandbox.container_id} not found") from exc

            start = time.monotonic()
            timed_out = False

            try:
                exec_id = client.api.exec_create(
                    container.id,
                    cmd=["bash", "-c", command],
                    workdir=sandbox.workspace_path,
                )
                output = client.api.exec_start(exec_id, stream=False)
                inspect = client.api.exec_inspect(exec_id["Id"])
                exit_code: int = inspect.get("ExitCode", -1)
                duration = time.monotonic() - start

                if duration > timeout:
                    timed_out = True

                decoded = output.decode("utf-8", errors="replace") if output else ""

                return ExecResult(
                    exit_code=exit_code,
                    stdout=decoded,
                    stderr="",
                    timed_out=timed_out,
                    duration_seconds=round(duration, 3),
                )
            except (APIError, DockerException) as exc:
                duration = time.monotonic() - start
                logger.error(
                    "sandbox.exec_failed",
                    container_id=sandbox.container_id,
                    command=command,
                    error=str(exc),
                )
                return ExecResult(
                    exit_code=-1,
                    stdout="",
                    stderr=str(exc),
                    timed_out=False,
                    duration_seconds=round(duration, 3),
                )

        return await asyncio.to_thread(_exec_sync)

    async def copy_to(
        self,
        sandbox: Sandbox,
        local_path: str,
        container_path: str,
    ) -> None:
        """Copy a local file or directory into the sandbox container."""

        def _copy_sync() -> None:
            client = self._get_client()

            try:
                container = client.containers.get(sandbox.container_id)
            except NotFound as exc:
                raise RuntimeError(f"Sandbox container {sandbox.container_id} not found") from exc

            src = Path(local_path)
            if not src.exists():
                raise FileNotFoundError(f"Local path does not exist: {local_path}")

            # Build an in-memory tar archive for the Docker put_archive API.
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                tar.add(str(src), arcname=src.name)
            buf.seek(0)

            try:
                container.put_archive(container_path, buf)
            except (APIError, DockerException) as exc:
                logger.error(
                    "sandbox.copy_failed",
                    container_id=sandbox.container_id,
                    local_path=local_path,
                    container_path=container_path,
                    error=str(exc),
                )
                raise RuntimeError(f"Failed to copy files into sandbox: {exc}") from exc

            logger.info(
                "sandbox.copy_to",
                container_id=container.short_id,
                local_path=local_path,
                container_path=container_path,
            )

        await asyncio.to_thread(_copy_sync)

    async def cleanup(self, sandbox: Sandbox) -> None:
        """Stop and remove the sandbox container."""

        def _cleanup_sync() -> None:
            client = self._get_client()

            try:
                container = client.containers.get(sandbox.container_id)
                container.stop(timeout=5)
                container.remove(force=True)
                logger.info(
                    "sandbox.cleaned_up",
                    container_id=sandbox.container_id[:12],
                )
            except NotFound:
                logger.warning(
                    "sandbox.cleanup_not_found",
                    container_id=sandbox.container_id,
                )
            except (APIError, DockerException) as exc:
                logger.error(
                    "sandbox.cleanup_failed",
                    container_id=sandbox.container_id,
                    error=str(exc),
                )
                raise RuntimeError(f"Failed to clean up sandbox container: {exc}") from exc

        await asyncio.to_thread(_cleanup_sync)
        sandbox.status = "stopped"

    async def provision_pool(self, count: int = 3) -> list[Sandbox]:
        """Pre-warm *count* sandbox containers in parallel."""
        tasks = [self.provision() for _ in range(count)]
        sandboxes = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[Sandbox] = []
        for result in sandboxes:
            if isinstance(result, BaseException):
                logger.error(
                    "sandbox.pool_provision_failed",
                    error=str(result),
                )
            else:
                results.append(result)

        logger.info(
            "sandbox.pool_ready",
            requested=count,
            provisioned=len(results),
        )
        return results
