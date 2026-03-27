"""Pydantic v2 models for Layer 2: Company Intelligence."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from letsbuild.models.shared import StructuredError  # noqa: TC001


class DataSource(BaseModel):
    """A single data source consulted during company research."""

    model_config = ConfigDict(strict=True)

    name: str = Field(
        description="Human-readable name of the data source (e.g. 'Acme Corp Website').",
    )
    url: str | None = Field(
        default=None,
        description="URL of the data source, if applicable.",
    )
    source_type: str = Field(
        description=(
            "Type of data source — e.g. 'website', 'github', 'news', 'blog', 'glassdoor'."
        ),
    )
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the data was retrieved (UTC).",
    )
    reliability_score: float = Field(
        description="Reliability score for this source (0.0-100.0).",
        ge=0.0,
        le=100.0,
    )


class SubAgentType(StrEnum):
    """Enum of the six parallel sub-agents in Company Intelligence."""

    WEB_PRESENCE = "web_presence"
    TECH_BLOG = "tech_blog"
    GITHUB_ORG = "github_org"
    BUSINESS_INTEL = "business_intel"
    NEWS_MONITOR = "news_monitor"
    CULTURE_PROBE = "culture_probe"


class SubAgentResult(BaseModel):
    """Result from a single Company Intelligence sub-agent."""

    model_config = ConfigDict(strict=True)

    agent_type: SubAgentType = Field(
        description="Which sub-agent produced this result.",
    )
    success: bool = Field(
        description="Whether the sub-agent completed successfully.",
    )
    data: dict[str, object] = Field(
        default_factory=dict,
        description="Arbitrary key-value data gathered by the sub-agent.",
    )
    data_sources: list[DataSource] = Field(
        default_factory=list,
        description="Data sources consulted by this sub-agent.",
    )
    error: StructuredError | None = Field(
        default=None,
        description="Structured error if the sub-agent failed.",
    )
    execution_time_seconds: float = Field(
        description="Wall-clock execution time of this sub-agent in seconds.",
        ge=0.0,
    )


class EngineeringCulture(BaseModel):
    """Engineering culture signals gathered from company research."""

    model_config = ConfigDict(strict=True)

    open_source_active: bool = Field(
        description="Whether the company actively maintains open-source projects.",
    )
    tech_blog_active: bool = Field(
        description="Whether the company publishes a technical blog.",
    )
    engineering_team_size: str | None = Field(
        default=None,
        description="Estimated engineering team size range (e.g. '50-200').",
    )
    development_methodology: str | None = Field(
        default=None,
        description="Development methodology if known (e.g. 'agile', 'kanban', 'scrum').",
    )
    key_values: list[str] = Field(
        default_factory=list,
        description="Key engineering values or principles the company espouses.",
    )


class CompanyProfile(BaseModel):
    """Main output of Layer 2: a comprehensive company profile built from parallel research."""

    model_config = ConfigDict(strict=True)

    company_name: str = Field(
        description="Canonical company name.",
    )
    company_url: str | None = Field(
        default=None,
        description="Primary company website URL.",
    )
    industry: str | None = Field(
        default=None,
        description="Industry or vertical the company operates in.",
    )
    company_size: str | None = Field(
        default=None,
        description="Company size category (e.g. 'startup', 'mid-market', 'enterprise').",
    )
    tech_stack_signals: list[str] = Field(
        default_factory=list,
        description="Technologies detected from company research, lowercase.",
    )
    engineering_culture: EngineeringCulture | None = Field(
        default=None,
        description="Engineering culture signals, if available.",
    )
    business_context: str | None = Field(
        default=None,
        description="Brief description of what the company does and its market position.",
    )
    recent_news: list[str] = Field(
        default_factory=list,
        description="Recent news headlines or summaries about the company.",
    )
    github_org_url: str | None = Field(
        default=None,
        description="GitHub organisation URL, if the company has a public org.",
    )
    public_repos_count: int | None = Field(
        default=None,
        description="Number of public repositories in the company's GitHub org.",
    )
    top_languages: list[str] = Field(
        default_factory=list,
        description="Most-used programming languages in the company's public repos.",
    )
    funding_stage: str | None = Field(
        default=None,
        description="Funding stage if known (e.g. 'Series A', 'Series C', 'Public').",
    )
    confidence_score: float = Field(
        description="Overall confidence in the profile accuracy (0.0-100.0).",
        ge=0.0,
        le=100.0,
    )
    data_sources: list[DataSource] = Field(
        default_factory=list,
        description="All data sources consulted to build this profile.",
    )
    sub_agent_results: list[SubAgentResult] = Field(
        default_factory=list,
        description="Raw results from each of the six research sub-agents.",
    )
    researched_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this profile was researched (UTC).",
    )
    cache_expires_at: datetime | None = Field(
        default=None,
        description="When this cached profile expires and should be re-researched (UTC).",
    )


class ResearchResult(BaseModel):
    """Wrapper around CompanyProfile with execution metadata."""

    model_config = ConfigDict(strict=True)

    company_profile: CompanyProfile = Field(
        description="The full company profile produced by Layer 2.",
    )
    total_execution_time_seconds: float = Field(
        description="Total wall-clock time for all sub-agents in seconds.",
        ge=0.0,
    )
    agents_succeeded: int = Field(
        description="Number of sub-agents that completed successfully.",
        ge=0,
    )
    agents_failed: int = Field(
        description="Number of sub-agents that failed.",
        ge=0,
    )
    partial: bool = Field(
        description="Whether the result is partial due to one or more sub-agent failures.",
    )
