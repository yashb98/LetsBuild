"""Pydantic v2 models for application and runtime configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelTaskMapping(BaseModel):
    """Maps a pipeline task to a specific LLM model with fallback."""

    model_config = ConfigDict(strict=True)

    task_name: str = Field(
        description="Name of the pipeline task (e.g. 'architecture', 'code_gen', 'review').",
    )
    model_id: str = Field(
        description="Primary model identifier (e.g. 'claude-sonnet-4-6').",
    )
    fallback_model_id: str | None = Field(
        default=None,
        description="Fallback model if the primary is unavailable or over budget.",
    )
    tool_choice: str | None = Field(
        default=None,
        description="Tool choice mode: 'auto' or a forced tool name.",
    )


class SandboxConfig(BaseModel):
    """Configuration for Docker sandbox instances."""

    model_config = ConfigDict(strict=True)

    base_image: str = Field(
        default="letsbuild/sandbox:latest",
        description="Docker base image for sandbox containers.",
    )
    cpu_limit: int = Field(
        default=4,
        description="Maximum CPU cores allocated to each sandbox.",
    )
    memory_limit_gb: int = Field(
        default=8,
        description="Maximum memory in GB allocated to each sandbox.",
    )
    disk_limit_gb: int = Field(
        default=20,
        description="Maximum disk space in GB allocated to each sandbox.",
    )
    lifetime_minutes: int = Field(
        default=30,
        description="Maximum lifetime of a sandbox container in minutes.",
    )
    pool_size: int = Field(
        default=3,
        description="Number of pre-warmed standby sandbox containers.",
    )


class SkillConfig(BaseModel):
    """Configuration parsed from a skill file's YAML frontmatter."""

    model_config = ConfigDict(strict=True)

    name: str = Field(
        description="Kebab-case skill identifier.",
    )
    display_name: str = Field(
        description="Human-readable display name for the skill.",
    )
    category: str = Field(
        description="Skill category: 'project', 'codegen', 'research', 'content', or 'template'.",
    )
    role_categories: list[str] = Field(
        description="JD role categories that trigger this skill.",
    )
    seniority_range: list[str] = Field(
        description="Supported seniority levels (e.g. ['junior', 'mid', 'senior', 'staff']).",
    )
    tech_stacks_primary: list[str] = Field(
        description="Primary tech stack items for this skill.",
    )
    tech_stacks_alternatives: list[str] = Field(
        default_factory=list,
        description="Alternative tech stack items for variety.",
    )
    complexity_range: list[int] = Field(
        description="Complexity range as [min, max] on a 1-10 scale.",
    )
    estimated_loc: list[int] = Field(
        description="Estimated lines of code range as [min, max].",
    )
    topology: str = Field(
        default="hierarchical",
        description="Agent topology: 'hierarchical', 'mesh', 'sequential', or 'ring'.",
    )


class NotificationConfig(BaseModel):
    """Configuration for notification channels."""

    model_config = ConfigDict(strict=True)

    telegram_enabled: bool = Field(
        default=False,
        description="Whether Telegram notifications are enabled.",
    )
    slack_enabled: bool = Field(
        default=False,
        description="Whether Slack notifications are enabled.",
    )
    discord_enabled: bool = Field(
        default=False,
        description="Whether Discord notifications are enabled.",
    )
    websocket_enabled: bool = Field(
        default=True,
        description="Whether WebSocket notifications are enabled.",
    )


class AppConfig(BaseModel):
    """Top-level application configuration loaded from letsbuild.yaml."""

    model_config = ConfigDict(strict=True)

    project_name: str = Field(
        default="letsbuild",
        description="Name of the project.",
    )
    anthropic_model_default: str = Field(
        default="claude-sonnet-4-6",
        description="Default Anthropic model for tasks without explicit mapping.",
    )
    model_mappings: list[ModelTaskMapping] = Field(
        default_factory=list,
        description="Task-to-model mappings for multi-model strategy.",
    )
    sandbox: SandboxConfig = Field(
        default_factory=SandboxConfig,
        description="Docker sandbox configuration.",
    )
    notifications: NotificationConfig = Field(
        default_factory=NotificationConfig,
        description="Notification channel configuration.",
    )
    budget_limit_gbp: float = Field(
        default=50.0,
        description="Maximum allowed API cost per pipeline run in GBP.",
    )
    quality_threshold: float = Field(
        default=70.0,
        description="Minimum quality score to pass QualityGate (0.0-100.0).",
    )
    max_retries_per_layer: int = Field(
        default=2,
        description="Maximum retry attempts per pipeline layer.",
    )
