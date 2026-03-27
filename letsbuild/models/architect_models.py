"""Pydantic v2 models for Layer 4: Project Architect."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ADRStatus(StrEnum):
    """Status of an Architecture Decision Record."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


class ADR(BaseModel):
    """Architecture Decision Record included in every generated project."""

    model_config = ConfigDict(strict=True)

    adr_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this ADR.",
    )
    title: str = Field(
        description="Short title describing the architectural decision.",
    )
    status: ADRStatus = Field(
        description="Current status of this ADR.",
    )
    context: str = Field(
        description="Background and motivation for the decision.",
    )
    decision: str = Field(
        description="The architectural decision that was made.",
    )
    consequences: str = Field(
        description="Trade-offs and consequences of the decision.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this ADR was created (UTC).",
    )


class FileTreeNode(BaseModel):
    """A node in the project file tree, supporting self-referential nesting."""

    model_config = ConfigDict(strict=True)

    path: str = Field(
        description="Relative path of this file or directory within the project.",
    )
    is_directory: bool = Field(
        description="Whether this node is a directory.",
    )
    description: str | None = Field(
        default=None,
        description="Optional description of the file or directory purpose.",
    )
    children: list[FileTreeNode] = Field(
        default_factory=list,
        description="Child nodes if this is a directory.",
    )


FileTreeNode.model_rebuild()


class SandboxValidationCommand(BaseModel):
    """A single command in the sandbox validation plan."""

    model_config = ConfigDict(strict=True)

    command: str = Field(
        description="Bash command to execute inside the sandbox.",
    )
    description: str = Field(
        description="Human-readable description of what this command validates.",
    )
    expected_exit_code: int = Field(
        default=0,
        description="Expected exit code for the command (0 = success).",
    )
    timeout_seconds: int = Field(
        default=60,
        description="Maximum seconds this command may run before timeout.",
    )


class SandboxValidationPlan(BaseModel):
    """Plan of commands that must pass inside the Docker sandbox before publishing."""

    model_config = ConfigDict(strict=True)

    commands: list[SandboxValidationCommand] = Field(
        min_length=3,
        description="Validation commands to run in order (minimum 3).",
    )
    base_image: str = Field(
        default="letsbuild/sandbox:latest",
        description="Docker base image for the sandbox.",
    )
    extra_packages: list[str] = Field(
        default_factory=list,
        description="Additional apt/pip/npm packages to install in the sandbox.",
    )
    timeout_minutes: int = Field(
        default=20,
        description="Maximum total minutes for the validation plan.",
    )


class FeatureSpec(BaseModel):
    """Specification for a single feature within a project."""

    model_config = ConfigDict(strict=True)

    feature_name: str = Field(
        description="Name of the feature.",
    )
    description: str = Field(
        description="What this feature does and why it matters.",
    )
    module_path: str = Field(
        description="Relative path to the module implementing this feature.",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Other feature names this feature depends on.",
    )
    estimated_complexity: int = Field(
        description="Estimated complexity on a 1-10 scale.",
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Concrete criteria that must be met for this feature to be complete.",
    )

    @field_validator("estimated_complexity")
    @classmethod
    def _validate_complexity(cls, v: int) -> int:
        if v < 1 or v > 10:
            msg = "estimated_complexity must be between 1 and 10"
            raise ValueError(msg)
        return v


class ProjectSpec(BaseModel):
    """Main output of Layer 4: complete project specification for Code Forge."""

    model_config = ConfigDict(strict=True)

    project_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this project.",
    )
    project_name: str = Field(
        description="SEO-friendly project name.",
    )
    one_liner: str = Field(
        description="One-sentence description of what the project does.",
    )
    tech_stack: list[str] = Field(
        description="Technologies used in this project.",
    )
    file_tree: list[FileTreeNode] = Field(
        description="Top-level file tree structure for the project.",
    )
    feature_specs: list[FeatureSpec] = Field(
        description="Specifications for each feature to be implemented.",
    )
    sandbox_validation_plan: SandboxValidationPlan = Field(
        description="Plan for validating the project inside the Docker sandbox.",
    )
    adr_list: list[ADR] = Field(
        default_factory=list,
        description="Architecture Decision Records for the project.",
    )
    skill_name: str = Field(
        description="Name of the skill file used to design this project.",
    )
    skill_coverage_map: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of skill name to how it is demonstrated in the project.",
    )
    complexity_score: float = Field(
        description="Overall complexity score for the project (1.0-10.0).",
    )
    estimated_loc: int = Field(
        description="Estimated lines of code for the complete project.",
    )
    seniority_target: str = Field(
        description="Target seniority level (e.g. junior, mid, senior, staff).",
    )
    designed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this project spec was created (UTC).",
    )

    @field_validator("complexity_score")
    @classmethod
    def _validate_complexity_score(cls, v: float) -> float:
        if v < 1.0 or v > 10.0:
            msg = "complexity_score must be between 1.0 and 10.0"
            raise ValueError(msg)
        return v
