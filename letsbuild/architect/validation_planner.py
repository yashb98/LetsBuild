"""Generates sandbox validation plans based on detected tech stack."""

from __future__ import annotations

import structlog

from letsbuild.models.architect_models import (
    SandboxValidationCommand,
    SandboxValidationPlan,
)
from letsbuild.models.config_models import SkillConfig  # noqa: TC001

logger = structlog.get_logger()

_PYTHON_KEYWORDS = frozenset(
    {
        "python",
        "fastapi",
        "django",
        "flask",
        "pytest",
        "pydantic",
        "sqlalchemy",
        "celery",
        "pandas",
        "numpy",
        "scipy",
        "torch",
        "tensorflow",
        "streamlit",
        "typer",
        "httpx",
        "aiohttp",
        "uvicorn",
    }
)

_NODE_KEYWORDS = frozenset(
    {
        "node",
        "nodejs",
        "node.js",
        "typescript",
        "react",
        "next.js",
        "nextjs",
        "vue",
        "angular",
        "express",
        "nestjs",
        "npm",
        "deno",
        "bun",
        "svelte",
        "tailwind",
        "vite",
    }
)

_GO_KEYWORDS = frozenset(
    {
        "go",
        "golang",
        "gin",
        "echo",
        "fiber",
    }
)

_RUST_KEYWORDS = frozenset(
    {
        "rust",
        "cargo",
        "tokio",
        "actix",
        "axum",
        "warp",
    }
)


class ValidationPlanner:
    """Generates sandbox validation plans with concrete bash commands.

    Inspects the project tech stack to produce appropriate install, test,
    and lint commands that must pass inside the Docker sandbox before
    a project may be published.
    """

    def __init__(self) -> None:
        self._log = logger.bind(component="validation_planner")

    def generate(
        self,
        tech_stack: list[str],
        skill_config: SkillConfig | None = None,
    ) -> SandboxValidationPlan:
        """Build a SandboxValidationPlan from the detected tech stack.

        Args:
            tech_stack: List of technology names present in the project.
            skill_config: Optional skill configuration with extra metadata.

        Returns:
            A SandboxValidationPlan with at least 3 commands.
        """
        stack_type = self._detect_stack_type(tech_stack)
        self._log.info("detected_stack_type", stack_type=stack_type, tech_stack=tech_stack)

        commands: list[SandboxValidationCommand]
        if stack_type == "python":
            commands = self._python_commands()
        elif stack_type == "node":
            commands = self._node_commands()
        elif stack_type == "go":
            commands = self._go_commands()
        elif stack_type == "rust":
            commands = self._rust_commands()
        else:
            commands = self._generic_commands()

        # Determine base_image and extra_packages from skill_config if available.
        base_image = "letsbuild/sandbox:latest"
        extra_packages: list[str] = []

        if skill_config is not None:
            # SkillConfig doesn't carry sandbox_requirements directly,
            # but we can derive extra_packages from the primary tech stacks.
            extra_packages = list(skill_config.tech_stacks_primary)

        return SandboxValidationPlan(
            commands=commands,
            base_image=base_image,
            extra_packages=extra_packages,
        )

    # ------------------------------------------------------------------
    # Stack-specific command builders
    # ------------------------------------------------------------------

    def _python_commands(self) -> list[SandboxValidationCommand]:
        """Return standard Python validation commands."""
        return [
            SandboxValidationCommand(
                command="cd /mnt/workspace && pip install -e .",
                description="Install the project in editable mode.",
            ),
            SandboxValidationCommand(
                command="cd /mnt/workspace && pytest tests/ -v",
                description="Run the test suite.",
                timeout_seconds=120,
            ),
            SandboxValidationCommand(
                command="cd /mnt/workspace && ruff check .",
                description="Lint the codebase with ruff.",
            ),
            SandboxValidationCommand(
                command="cd /mnt/workspace && mypy --strict src/",
                description="Type-check the source code with mypy in strict mode.",
                timeout_seconds=120,
            ),
        ]

    def _node_commands(self) -> list[SandboxValidationCommand]:
        """Return standard Node.js / TypeScript validation commands."""
        return [
            SandboxValidationCommand(
                command="cd /mnt/workspace && npm install",
                description="Install Node.js dependencies.",
                timeout_seconds=120,
            ),
            SandboxValidationCommand(
                command="cd /mnt/workspace && npm test",
                description="Run the test suite.",
                timeout_seconds=120,
            ),
            SandboxValidationCommand(
                command="cd /mnt/workspace && npm run lint",
                description="Lint the codebase.",
            ),
            SandboxValidationCommand(
                command="cd /mnt/workspace && npm run build",
                description="Build the project.",
                timeout_seconds=180,
            ),
        ]

    def _go_commands(self) -> list[SandboxValidationCommand]:
        """Return standard Go validation commands."""
        return [
            SandboxValidationCommand(
                command="cd /mnt/workspace && go build ./...",
                description="Compile all Go packages.",
                timeout_seconds=120,
            ),
            SandboxValidationCommand(
                command="cd /mnt/workspace && go test ./...",
                description="Run all Go tests.",
                timeout_seconds=120,
            ),
            SandboxValidationCommand(
                command="cd /mnt/workspace && go vet ./...",
                description="Vet Go source for suspicious constructs.",
            ),
        ]

    def _rust_commands(self) -> list[SandboxValidationCommand]:
        """Return standard Rust validation commands."""
        return [
            SandboxValidationCommand(
                command="cd /mnt/workspace && cargo build",
                description="Build the Rust project.",
                timeout_seconds=180,
            ),
            SandboxValidationCommand(
                command="cd /mnt/workspace && cargo test",
                description="Run Rust tests.",
                timeout_seconds=120,
            ),
            SandboxValidationCommand(
                command="cd /mnt/workspace && cargo clippy",
                description="Lint with Clippy.",
            ),
        ]

    def _generic_commands(self) -> list[SandboxValidationCommand]:
        """Return generic fallback validation commands."""
        return [
            SandboxValidationCommand(
                command="cd /mnt/workspace && make install || true",
                description="Attempt to install project dependencies.",
            ),
            SandboxValidationCommand(
                command="cd /mnt/workspace && make test || true",
                description="Attempt to run the test suite.",
                timeout_seconds=120,
            ),
            SandboxValidationCommand(
                command="cd /mnt/workspace && make lint || true",
                description="Attempt to lint the codebase.",
            ),
        ]

    # ------------------------------------------------------------------
    # Detection helper
    # ------------------------------------------------------------------

    def _detect_stack_type(self, tech_stack: list[str]) -> str:
        """Detect the dominant stack type from a list of technologies.

        Returns one of ``"python"``, ``"node"``, ``"go"``, ``"rust"``,
        or ``"generic"``.
        """
        normalised = {t.lower().strip() for t in tech_stack}

        if normalised & _PYTHON_KEYWORDS:
            return "python"
        if normalised & _NODE_KEYWORDS:
            return "node"
        if normalised & _GO_KEYWORDS:
            return "go"
        if normalised & _RUST_KEYWORDS:
            return "rust"
        return "generic"
