"""Pydantic v2 models for the Intake Engine (Layer 1).

Defines the structured output models for JD parsing, including
RoleCategory, SeniorityLevel, Skill, TechStack, and JDAnalysis.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RoleCategory(str, Enum):
    """Category of role extracted from a job description."""

    FULL_STACK = "full_stack_engineer"
    FRONTEND = "frontend_engineer"
    BACKEND = "backend_engineer"
    ML_ENGINEER = "ml_engineer"
    DATA_SCIENTIST = "data_scientist"
    DATA_ENGINEER = "data_engineer"
    PLATFORM_ENGINEER = "platform_engineer"
    DEVOPS = "devops_engineer"
    MOBILE = "mobile_engineer"
    SECURITY = "security_engineer"
    AGENTIC_AI = "agentic_ai_engineer"
    NLP_ENGINEER = "nlp_engineer"
    CV_ENGINEER = "cv_engineer"
    EMBEDDED_IOT = "embedded_iot_engineer"
    BLOCKCHAIN = "blockchain_engineer"
    OTHER = "other"


class SeniorityLevel(str, Enum):
    """Seniority level extracted from a job description."""

    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"
    PRINCIPAL = "principal"


class Skill(BaseModel):
    """A single skill extracted from a job description."""

    model_config = ConfigDict(strict=True)

    name: str = Field(
        description="Canonical name of the skill (e.g. 'Python', 'Kubernetes').",
    )
    category: str = Field(
        description="Category of the skill (e.g. 'language', 'framework', 'tool', 'methodology').",
    )
    confidence: float = Field(
        default=100.0,
        ge=0.0,
        le=100.0,
        description="Confidence score for this skill extraction (0.0-100.0).",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Known aliases for this skill (e.g. ['JS'] for 'JavaScript').",
    )
    is_primary: bool = Field(
        default=False,
        description="Whether this is a primary/must-have skill for the role.",
    )


class TechStack(BaseModel):
    """Technology stack extracted from a job description. All items are lowercase."""

    model_config = ConfigDict(strict=True)

    languages: list[str] = Field(
        default_factory=list,
        description="Programming languages (lowercase, e.g. ['python', 'typescript']).",
    )
    frameworks: list[str] = Field(
        default_factory=list,
        description="Frameworks and libraries (lowercase, e.g. ['fastapi', 'react']).",
    )
    databases: list[str] = Field(
        default_factory=list,
        description="Databases and data stores (lowercase, e.g. ['postgresql', 'redis']).",
    )
    cloud_providers: list[str] = Field(
        default_factory=list,
        description="Cloud providers and platforms (lowercase, e.g. ['aws', 'gcp']).",
    )
    tools: list[str] = Field(
        default_factory=list,
        description="Developer tools (lowercase, e.g. ['docker', 'terraform']).",
    )
    infrastructure: list[str] = Field(
        default_factory=list,
        description="Infrastructure components (lowercase, e.g. ['kubernetes', 'kafka']).",
    )

    @model_validator(mode="after")
    def enforce_lowercase(self) -> TechStack:
        """Ensure all tech stack items are lowercase."""
        self.languages = [item.lower() for item in self.languages]
        self.frameworks = [item.lower() for item in self.frameworks]
        self.databases = [item.lower() for item in self.databases]
        self.cloud_providers = [item.lower() for item in self.cloud_providers]
        self.tools = [item.lower() for item in self.tools]
        self.infrastructure = [item.lower() for item in self.infrastructure]
        return self


class JDAnalysis(BaseModel):
    """Structured analysis of a job description — primary output of the Intake Engine (L1).

    This model is used both for internal validation and as the Claude tool_use
    schema via tool_choice forced selection on 'extract_jd_analysis'.
    """

    model_config = ConfigDict(strict=True)

    jd_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this JD analysis (UUID4).",
    )
    role_title: str = Field(
        description="Exact role title from the job description.",
    )
    role_category: RoleCategory = Field(
        description="Categorised role type for skill and project matching.",
    )
    role_category_detail: str | None = Field(
        default=None,
        description="Detailed role description, only populated when role_category is OTHER.",
    )
    seniority: SeniorityLevel = Field(
        description="Seniority level of the role.",
    )
    company_name: str | None = Field(
        default=None,
        description="Name of the hiring company, if identifiable.",
    )
    company_url: str | None = Field(
        default=None,
        description="URL of the hiring company's website, if identifiable.",
    )
    required_skills: list[Skill] = Field(
        default_factory=list,
        description="Skills explicitly listed as required or must-have.",
    )
    preferred_skills: list[Skill] = Field(
        default_factory=list,
        description="Skills listed as preferred, nice-to-have, or bonus.",
    )
    tech_stack: TechStack = Field(
        default_factory=TechStack,
        description="Consolidated technology stack extracted from the JD.",
    )
    domain_keywords: list[str] = Field(
        default_factory=list,
        description="Domain-specific keywords (e.g. ['fintech', 'real-time', 'e-commerce']).",
    )
    key_responsibilities: list[str] = Field(
        default_factory=list,
        description="Key responsibilities and expectations listed in the JD.",
    )
    years_experience_min: int | None = Field(
        default=None,
        ge=0,
        description="Minimum years of experience required, if specified.",
    )
    years_experience_max: int | None = Field(
        default=None,
        ge=0,
        description="Maximum years of experience mentioned, if specified.",
    )
    location: str | None = Field(
        default=None,
        description="Job location (city, country, or region).",
    )
    remote_policy: str | None = Field(
        default=None,
        description="Remote work policy (e.g. 'fully remote', 'hybrid', 'on-site').",
    )
    salary_min_gbp: float | None = Field(
        default=None,
        ge=0.0,
        description="Minimum salary in GBP, if specified.",
    )
    salary_max_gbp: float | None = Field(
        default=None,
        ge=0.0,
        description="Maximum salary in GBP, if specified.",
    )
    raw_text: str = Field(
        description="Original raw text of the job description.",
    )
    source_url: str | None = Field(
        default=None,
        description="URL where the job description was sourced from.",
    )
    parsed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the JD was parsed (UTC).",
    )

    @model_validator(mode="after")
    def validate_role_category_detail(self) -> JDAnalysis:
        """Ensure role_category_detail is set when category is OTHER."""
        if self.role_category == RoleCategory.OTHER and not self.role_category_detail:
            msg = "role_category_detail must be provided when role_category is OTHER."
            raise ValueError(msg)
        if self.role_category != RoleCategory.OTHER and self.role_category_detail is not None:
            self.role_category_detail = None
        return self

    @model_validator(mode="after")
    def validate_experience_range(self) -> JDAnalysis:
        """Ensure min experience does not exceed max."""
        if (
            self.years_experience_min is not None
            and self.years_experience_max is not None
            and self.years_experience_min > self.years_experience_max
        ):
            msg = "years_experience_min cannot exceed years_experience_max."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_salary_range(self) -> JDAnalysis:
        """Ensure min salary does not exceed max."""
        if (
            self.salary_min_gbp is not None
            and self.salary_max_gbp is not None
            and self.salary_min_gbp > self.salary_max_gbp
        ):
            msg = "salary_min_gbp cannot exceed salary_max_gbp."
            raise ValueError(msg)
        return self
