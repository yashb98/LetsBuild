"""Intake Engine models — Layer 1 output schemas.

These models represent the structured output of the JD parsing pipeline.
All models use ConfigDict(strict=True) and full Field(description=...) annotations.
JSON schemas generated via .model_json_schema() are used directly as Claude tool schemas.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "RoleCategory",
    "Skill",
    "TechStack",
    "JDAnalysis",
]


class RoleCategory(str, Enum):
    """Extensible enumeration of engineering role categories.

    Used by the Intake Engine to classify the target role in a JD.
    New categories can be added without breaking existing data.
    Use OTHER + role_category_detail for roles that do not fit a named category.
    """

    FULL_STACK_ENGINEER = "full_stack_engineer"
    FRONTEND_ENGINEER = "frontend_engineer"
    BACKEND_ENGINEER = "backend_engineer"
    ML_ENGINEER = "ml_engineer"
    DATA_SCIENTIST = "data_scientist"
    DATA_ENGINEER = "data_engineer"
    DEVOPS_ENGINEER = "devops_engineer"
    PLATFORM_ENGINEER = "platform_engineer"
    MOBILE_ENGINEER = "mobile_engineer"
    SECURITY_ENGINEER = "security_engineer"
    QA_ENGINEER = "qa_engineer"
    EMBEDDED_ENGINEER = "embedded_engineer"
    BLOCKCHAIN_ENGINEER = "blockchain_engineer"
    NLP_ENGINEER = "nlp_engineer"
    CV_ENGINEER = "cv_engineer"
    AGENTIC_AI_ENGINEER = "agentic_ai_engineer"
    OTHER = "other"


class Skill(BaseModel):
    """A single skill extracted from a job description.

    Skills are normalised to lowercase and enriched with extraction metadata.
    The confidence score drives how aggressively the pipeline tries to demonstrate
    this skill in the generated portfolio project.
    """

    model_config = ConfigDict(strict=True)

    name: str = Field(
        description=(
            "Lowercase-normalised skill name, e.g. 'python', 'react', 'kubernetes'. "
            "Always lowercase; canonical form preferred over abbreviations."
        )
    )
    category: str = Field(
        description=(
            "Broad category of this skill. Common values: 'language', 'framework', "
            "'tool', 'concept', 'cloud', 'database', 'methodology'. "
            "Use the most specific applicable category."
        )
    )
    confidence: float = Field(
        description=(
            "Extraction confidence as a percentage in range [0.0, 100.0]. "
            "100 = explicitly stated as required; lower values indicate inferred skills."
        )
    )
    is_required: bool = Field(
        description=(
            "True if the JD marks this skill as required/must-have. "
            "False if it is listed as preferred, nice-to-have, or bonus."
        )
    )
    aliases: list[str] = Field(
        default_factory=list,
        description=(
            "Alternative names or abbreviations for this skill, e.g. ['py', 'python3'] "
            "for 'python' or ['k8s'] for 'kubernetes'. Used for deduplication and matching."
        ),
    )


class TechStack(BaseModel):
    """Extracted technology stack from the job description.

    Groups technologies into categories so the Project Architect can
    generate a project that matches the company's exact tooling choices.
    All items are lowercase strings.
    """

    model_config = ConfigDict(strict=True)

    languages: list[str] = Field(
        default_factory=list,
        description=(
            "Programming languages mentioned in the JD, e.g. ['python', 'typescript', 'go']. "
            "Lowercase. Excludes markup/config languages (HTML, YAML, etc.)."
        ),
    )
    frameworks: list[str] = Field(
        default_factory=list,
        description=(
            "Frameworks and libraries mentioned, e.g. ['fastapi', 'react', 'pytorch']. "
            "Includes both frontend and backend frameworks. Lowercase."
        ),
    )
    databases: list[str] = Field(
        default_factory=list,
        description=(
            "Database technologies mentioned, e.g. ['postgresql', 'redis', 'mongodb']. "
            "Includes both SQL and NoSQL. Lowercase."
        ),
    )
    cloud_platforms: list[str] = Field(
        default_factory=list,
        description=(
            "Cloud providers and managed services mentioned, e.g. ['aws', 'gcp', 'azure']. "
            "Also includes specific managed services like 's3', 'bigquery'. Lowercase."
        ),
    )
    tools: list[str] = Field(
        default_factory=list,
        description=(
            "Developer tools mentioned, e.g. ['docker', 'kubernetes', 'terraform', 'github-actions']. "
            "Includes CI/CD, container, and infrastructure tooling. Lowercase."
        ),
    )
    other: list[str] = Field(
        default_factory=list,
        description=(
            "Technologies that do not fit the other categories, e.g. message queues "
            "('kafka', 'rabbitmq'), search engines ('elasticsearch'), or protocols. Lowercase."
        ),
    )


class JDAnalysis(BaseModel):
    """Full structured output of the Intake Engine (Layer 1).

    Produced by the extract_jd_analysis tool call with forced tool_choice.
    Every field is populated from the raw JD text. Nullable fields are None
    when the information is not present or cannot be inferred.

    This model's JSON schema is used directly as the Claude tool schema for
    structured extraction, so all Field descriptions are written as Claude
    instructions rather than developer documentation.
    """

    model_config = ConfigDict(strict=True)

    role_title: str = Field(
        description=(
            "The exact job title as written in the JD, e.g. 'Senior Backend Engineer' "
            "or 'Staff Machine Learning Engineer'. Preserve original capitalisation."
        )
    )
    role_category: RoleCategory = Field(
        description=(
            "Best-matching engineering category for this role. Choose the most specific "
            "category that applies. Use 'other' only when no named category fits."
        )
    )
    role_category_detail: str | None = Field(
        default=None,
        description=(
            "Free-text description of the role type. ONLY populate when role_category "
            "is 'other'. Examples: 'site_reliability_engineer', 'solutions_architect'. "
            "Leave null for all named role categories."
        ),
    )
    seniority: Literal["junior", "mid", "senior", "staff", "principal"] = Field(
        description=(
            "Seniority level inferred from the JD. Use 'mid' when the JD says "
            "'software engineer' with no modifier. 'staff' and 'principal' imply "
            "cross-team technical leadership."
        )
    )
    company_name: str | None = Field(
        default=None,
        description=(
            "Company name as it appears in the JD. Null if not mentioned or if the "
            "JD is anonymised. Preserve official capitalisation (e.g. 'DeepMind', 'IBM')."
        ),
    )
    company_url: str | None = Field(
        default=None,
        description=(
            "Company website URL extracted from the JD or inferred from context. "
            "Must be a valid https:// URL. Null if not determinable."
        ),
    )
    required_skills: list[Skill] = Field(
        default_factory=list,
        description=(
            "Skills explicitly required in the JD. These are non-negotiable from the "
            "employer's perspective. is_required must be True for all items in this list."
        ),
    )
    preferred_skills: list[Skill] = Field(
        default_factory=list,
        description=(
            "Skills listed as preferred, nice-to-have, or bonus. is_required must be "
            "False for all items in this list. These still influence project design."
        ),
    )
    tech_stack: TechStack = Field(
        description=(
            "Aggregated technology stack extracted from the JD. Groups all mentioned "
            "technologies by category for use by the Project Architect."
        )
    )
    domain_keywords: list[str] = Field(
        default_factory=list,
        description=(
            "Business domain and industry keywords from the JD, e.g. ['fintech', 'payments', "
            "'real-time', 'high-throughput']. Used to tailor the portfolio project theme. "
            "Lowercase. Include max 15 most relevant keywords."
        ),
    )
    key_responsibilities: list[str] = Field(
        default_factory=list,
        description=(
            "Top 5-10 key responsibilities extracted verbatim or paraphrased from the JD. "
            "Each item is one concise sentence. Used to align project features with role expectations."
        ),
    )
    years_experience_min: int | None = Field(
        default=None,
        description=(
            "Minimum years of experience required, as an integer. "
            "Null if not specified. Example: if JD says '3-5 years', set to 3."
        ),
    )
    years_experience_max: int | None = Field(
        default=None,
        description=(
            "Maximum years of experience in the stated range, as an integer. "
            "Null if not specified or if only a minimum is given. "
            "Example: if JD says '3-5 years', set to 5."
        ),
    )
    remote_policy: Literal["remote", "hybrid", "onsite", "unspecified"] = Field(
        description=(
            "Remote work policy stated or implied in the JD. "
            "Use 'unspecified' if not mentioned. 'hybrid' implies some required office days."
        )
    )
    salary_min_gbp: float | None = Field(
        default=None,
        description=(
            "Minimum salary converted to GBP (British pounds). "
            "Null if salary is not mentioned. Convert from USD/EUR if necessary using "
            "approximate rates. Round to nearest 1000."
        ),
    )
    salary_max_gbp: float | None = Field(
        default=None,
        description=(
            "Maximum salary converted to GBP (British pounds). "
            "Null if salary is not mentioned or only a minimum is given. "
            "Round to nearest 1000."
        ),
    )
    raw_text: str = Field(
        description=(
            "The complete original JD text, preserved exactly as provided. "
            "Used for re-processing, audit trails, and future re-analysis."
        )
    )
