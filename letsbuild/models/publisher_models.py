"""Pydantic v2 models for Layer 6: GitHub Publisher."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class CommitPhase(StrEnum):
    """Phase of the commit strategy for realistic git history."""

    SCAFFOLDING = "scaffolding"
    CORE_MODULES = "core_modules"
    TESTS = "tests"
    ADRS = "adrs"
    DOCS = "docs"
    CI_CD = "ci_cd"
    POLISH = "polish"


class CommitEntry(BaseModel):
    """A single commit in the planned commit sequence."""

    model_config = ConfigDict(strict=True)

    message: str = Field(
        description="Conventional Commit message for this commit.",
    )
    files: list[str] = Field(
        description="List of file paths included in this commit.",
    )
    phase: CommitPhase = Field(
        description="Which phase of the commit strategy this belongs to.",
    )
    timestamp_offset_hours: float = Field(
        description="Offset in hours from the start of the commit sequence.",
    )


class CommitPlan(BaseModel):
    """Plan describing the full sequence of commits for a generated repository."""

    model_config = ConfigDict(strict=True)

    commits: list[CommitEntry] = Field(
        description="Ordered list of commits to create.",
    )
    total_commits: int = Field(
        description="Total number of commits in the plan.",
    )
    spread_days: int = Field(
        default=5,
        description="Number of days to spread commits across for realistic history.",
    )


class RepoConfig(BaseModel):
    """Configuration for the GitHub repository to be created."""

    model_config = ConfigDict(strict=True)

    repo_name: str = Field(
        description="SEO-optimised repository name (kebab-case).",
    )
    description: str = Field(
        description="Short repository description for GitHub.",
    )
    private: bool = Field(
        default=True,
        description="Whether the repository is created as private.",
    )
    topics: list[str] = Field(
        description="GitHub topics for discoverability.",
    )
    has_wiki: bool = Field(
        default=False,
        description="Whether the repository has a wiki enabled.",
    )
    has_issues: bool = Field(
        default=True,
        description="Whether the repository has issues enabled.",
    )
    default_branch: str = Field(
        default="main",
        description="Default branch name for the repository.",
    )


class PublishResult(BaseModel):
    """Output from Layer 6: GitHub Publisher."""

    model_config = ConfigDict(strict=True)

    publish_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this publish operation.",
    )
    repo_url: str = Field(
        description="Full URL of the created GitHub repository.",
    )
    commit_shas: list[str] = Field(
        description="SHA hashes of all commits pushed to the repository.",
    )
    readme_url: str = Field(
        description="Direct URL to the repository README.",
    )
    repo_config: RepoConfig = Field(
        description="Configuration used to create the repository.",
    )
    commit_plan: CommitPlan = Field(
        description="Commit plan that was executed.",
    )
    published_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the repository was published (UTC).",
    )
