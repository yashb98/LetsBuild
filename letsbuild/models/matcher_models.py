"""Pydantic v2 models for the Match & Score Engine (Layer 3)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GapCategory(StrEnum):
    """Category of a skill gap relative to a job description."""

    STRONG_MATCH = "strong_match"
    DEMONSTRABLE_GAP = "demonstrable_gap"
    LEARNABLE_GAP = "learnable_gap"
    HARD_GAP = "hard_gap"
    PORTFOLIO_REDUNDANCY = "portfolio_redundancy"


class MatchDimension(StrEnum):
    """Dimensions used for weighted match scoring."""

    HARD_SKILLS = "hard_skills"
    TECH_STACK = "tech_stack"
    DOMAIN = "domain"
    PORTFOLIO = "portfolio"
    SENIORITY = "seniority"
    SOFT_SKILLS = "soft_skills"


class GapItem(BaseModel):
    """A single skill gap or match item with categorisation evidence."""

    model_config = ConfigDict(strict=True)

    skill_name: str = Field(
        description="Name of the skill being evaluated.",
    )
    category: GapCategory = Field(
        description="Gap category for this skill.",
    )
    confidence: float = Field(
        ge=0.0,
        le=100.0,
        description="Confidence in the categorisation (0.0-100.0).",
    )
    evidence: str = Field(
        description="Explanation of why this categorisation was assigned.",
    )
    suggested_project_demo: str | None = Field(
        default=None,
        description="How to demonstrate this skill in a portfolio project, if applicable.",
    )


class DimensionScore(BaseModel):
    """Score for a single match dimension with its weight contribution."""

    model_config = ConfigDict(strict=True)

    dimension: MatchDimension = Field(
        description="Which match dimension this score represents.",
    )
    score: float = Field(
        ge=0.0,
        le=100.0,
        description="Raw score for this dimension (0.0-100.0).",
    )
    weight: float = Field(
        ge=0.0,
        le=1.0,
        description="Percentage weight for this dimension (e.g. 0.30 for 30%).",
    )
    weighted_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Score multiplied by weight (0.0-100.0).",
    )
    details: str = Field(
        description="Human-readable explanation of how this score was derived.",
    )


class MatchScore(BaseModel):
    """Aggregate match score across all dimensions."""

    model_config = ConfigDict(strict=True)

    overall_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Weighted overall match score (0.0-100.0).",
    )
    dimension_scores: list[DimensionScore] = Field(
        description="Individual scores for each match dimension.",
    )
    ats_predicted_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Predicted ATS (Applicant Tracking System) match score (0.0-100.0).",
    )

    @model_validator(mode="after")
    def validate_dimension_weights_sum(self) -> MatchScore:
        """Verify that dimension weights sum to approximately 1.0."""
        total_weight = sum(d.weight for d in self.dimension_scores)
        if self.dimension_scores and not (0.99 <= total_weight <= 1.01):
            msg = f"Dimension weights must sum to 1.0, got {total_weight:.4f}."
            raise ValueError(msg)
        return self


class GapAnalysis(BaseModel):
    """Main output of the Match & Score Engine (Layer 3).

    Categorises every skill from the JD into match/gap buckets and computes
    an overall match score across six weighted dimensions.
    """

    model_config = ConfigDict(strict=True)

    match_score: MatchScore = Field(
        description="Aggregate match score with per-dimension breakdown.",
    )
    strong_matches: list[GapItem] = Field(
        description="Skills where the candidate has strong existing evidence.",
    )
    demonstrable_gaps: list[GapItem] = Field(
        description="Skills that can be demonstrated through a targeted portfolio project.",
    )
    learnable_gaps: list[GapItem] = Field(
        description="Skills the candidate can credibly learn in a short timeframe.",
    )
    hard_gaps: list[GapItem] = Field(
        description="Skills that are difficult to address and may require longer-term investment.",
    )
    portfolio_redundancy: list[GapItem] = Field(
        description="Skills already well-covered by existing portfolio projects.",
    )
    recommended_project_focus: list[str] = Field(
        min_length=1,
        max_length=5,
        description="Top 3-5 skills to prioritise demonstrating in the generated project.",
    )
    analysis_summary: str = Field(
        description="Human-readable summary of the gap analysis findings.",
    )
    analysed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp of when this analysis was performed (UTC).",
    )
