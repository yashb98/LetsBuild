"""Pydantic v2 models for AgentForge Arena — competitive AI agent tournament platform."""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from letsbuild.models.shared import StructuredError  # noqa: TC001

# --- Enums ---


class TournamentFormat(StrEnum):
    """Format determining how teams compete in a tournament."""

    DUEL = "duel"
    STANDARD = "standard"
    LEAGUE = "league"
    GRAND_PRIX = "grand_prix"


class TournamentPhase(StrEnum):
    """Current phase of a tournament's lifecycle."""

    PREP = "prep"
    RESEARCH = "research"
    ARCHITECTURE = "architecture"
    BUILD = "build"
    CROSS_REVIEW = "cross_review"
    FIX_SPRINT = "fix_sprint"
    JUDGING = "judging"
    COMPLETE = "complete"


class ArenaAgentRole(StrEnum):
    """Role of an agent within an Arena team."""

    ARCHITECT = "architect"
    BUILDER = "builder"
    FRONTEND = "frontend"
    TESTER = "tester"
    CRITIC = "critic"
    TUTOR = "tutor"


# --- Config Models ---


class AgentConfig(BaseModel):
    """Configuration for a single agent within an Arena team."""

    model_config = ConfigDict(strict=True)

    role: ArenaAgentRole = Field(
        description="The role this agent fulfills within its team.",
    )
    model: str = Field(
        description="LLM model identifier to use for this agent (e.g. 'claude-sonnet-4-6').",
    )
    system_prompt_override: str | None = Field(
        default=None,
        description="Optional custom system prompt replacing the default for this role.",
    )
    max_turns: int = Field(
        default=30,
        description="Maximum number of agentic loop turns before safety cutoff.",
    )


class TeamConfig(BaseModel):
    """Configuration for a competing team in the Arena."""

    model_config = ConfigDict(strict=True)

    team_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this team (UUID4).",
    )
    team_name: str = Field(
        description="Human-readable name for the team.",
    )
    agents: list[AgentConfig] = Field(
        description="List of agent configurations that compose this team.",
    )
    sandbox_id: str | None = Field(
        default=None,
        description="Docker sandbox container ID assigned to this team.",
    )


class PhaseTimeLimit(BaseModel):
    """Time limit configuration for a specific tournament phase."""

    model_config = ConfigDict(strict=True)

    phase: TournamentPhase = Field(
        description="The tournament phase this time limit applies to.",
    )
    seconds: int = Field(
        description="Maximum duration in seconds allowed for this phase.",
    )


# --- Result Models ---


class PhaseResult(BaseModel):
    """Result of a single phase execution for one team."""

    model_config = ConfigDict(strict=True)

    phase: TournamentPhase = Field(
        description="The tournament phase that produced this result.",
    )
    team_id: str = Field(
        description="ID of the team that produced this result.",
    )
    duration_seconds: float = Field(
        description="Wall-clock time in seconds for this phase execution.",
    )
    artifacts: dict[str, str] = Field(
        default_factory=dict,
        description="Artifacts produced during this phase, keyed by name to file path.",
    )
    tokens_used: int = Field(
        description="Total LLM tokens consumed during this phase.",
    )
    errors: list[StructuredError] = Field(
        default_factory=list,
        description="Structured errors encountered during this phase.",
    )


class ScoreDimension(BaseModel):
    """A single scored dimension within a match evaluation."""

    model_config = ConfigDict(strict=True)

    dimension: str = Field(
        description="Name of the scoring dimension (e.g. 'code_quality', 'test_coverage').",
    )
    weight: float = Field(
        description="Weight of this dimension in the composite score (0.0-1.0).",
    )
    score: float = Field(
        description="Score for this dimension (0.0-100.0).",
    )
    details: str = Field(
        description="Explanation of how the score was determined.",
    )
    source: Literal["automated", "llm_judge"] = Field(
        description="Whether this score came from automated metrics or an LLM judge.",
    )

    @field_validator("score")
    @classmethod
    def validate_score(cls, v: float) -> float:
        """Ensure score is within the 0-100 range."""
        if v < 0.0 or v > 100.0:
            msg = "score must be between 0.0 and 100.0"
            raise ValueError(msg)
        return v

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, v: float) -> float:
        """Ensure weight is within the 0-1 range."""
        if v < 0.0 or v > 1.0:
            msg = "weight must be between 0.0 and 1.0"
            raise ValueError(msg)
        return v


class MatchResult(BaseModel):
    """Result of a complete match between teams."""

    model_config = ConfigDict(strict=True)

    match_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this match (UUID4).",
    )
    teams: list[str] = Field(
        description="List of team IDs that participated in this match.",
    )
    scores: dict[str, list[ScoreDimension]] = Field(
        description="Detailed scores per team, keyed by team_id.",
    )
    composite_scores: dict[str, float] = Field(
        description="Weighted composite score per team, keyed by team_id.",
    )
    winner: str = Field(
        description="Team ID of the winning team.",
    )
    duration_seconds: float = Field(
        description="Total wall-clock time in seconds for the entire match.",
    )
    phase_results: list[PhaseResult] = Field(
        default_factory=list,
        description="Results from each phase of the match.",
    )


class ELORating(BaseModel):
    """ELO rating tracking for an agent configuration."""

    model_config = ConfigDict(strict=True)

    config_id: str = Field(
        description="Identifier for the agent configuration being rated.",
    )
    rating: float = Field(
        default=1200.0,
        description="Current ELO rating.",
    )
    confidence_lower: float = Field(
        description="Lower bound of the rating confidence interval.",
    )
    confidence_upper: float = Field(
        description="Upper bound of the rating confidence interval.",
    )
    matches_played: int = Field(
        default=0,
        description="Total number of matches played.",
    )
    win_rate: float = Field(
        default=0.0,
        description="Win rate as a fraction (0.0-1.0).",
    )

    @field_validator("win_rate")
    @classmethod
    def validate_win_rate(cls, v: float) -> float:
        """Ensure win_rate is within the 0-1 range."""
        if v < 0.0 or v > 1.0:
            msg = "win_rate must be between 0.0 and 1.0"
            raise ValueError(msg)
        return v


# --- Challenge Model ---


class Challenge(BaseModel):
    """A coding challenge that teams compete to solve."""

    model_config = ConfigDict(strict=True)

    challenge_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this challenge (UUID4).",
    )
    name: str = Field(
        description="Human-readable name for the challenge.",
    )
    description: str = Field(
        description="Detailed description of what must be built.",
    )
    requirements: list[str] = Field(
        description="Mandatory requirements that must be fulfilled.",
    )
    bonus_features: list[str] = Field(
        default_factory=list,
        description="Optional bonus features for extra credit.",
    )
    constraints: dict[str, object] = Field(
        default_factory=dict,
        description="Constraints on the solution (e.g. language, framework, time).",
    )
    judging_weights: dict[str, float] = Field(
        description="Weights for each judging dimension, keyed by dimension name.",
    )
    hidden_test_path: str | None = Field(
        default=None,
        description="Path to hidden test suite revealed during judging phase.",
    )
    time_limits: list[PhaseTimeLimit] = Field(
        default_factory=list,
        description="Time limits for each phase of the challenge.",
    )
    difficulty: int = Field(
        description="Difficulty rating on a 1-10 scale.",
    )
    category: str = Field(
        description="Category of the challenge (e.g. 'fullstack', 'ml', 'cli').",
    )

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: int) -> int:
        """Ensure difficulty is within the 1-10 range."""
        if v < 1 or v > 10:
            msg = "difficulty must be between 1 and 10"
            raise ValueError(msg)
        return v


# --- State Model ---


class TournamentState(BaseModel):
    """Central state object for a tournament, accumulating results across phases.

    Mirrors the PipelineState pattern: a single object flows through all phases,
    with each phase writing its results into the appropriate field.
    """

    model_config = ConfigDict(strict=True)

    tournament_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this tournament (UUID4).",
    )
    format: TournamentFormat = Field(
        description="Format of the tournament (duel, standard, league, grand_prix).",
    )
    current_phase: TournamentPhase = Field(
        default=TournamentPhase.PREP,
        description="Current phase of the tournament lifecycle.",
    )
    challenge: Challenge | None = Field(
        default=None,
        description="The challenge being competed on.",
    )
    teams: list[TeamConfig] = Field(
        default_factory=list,
        description="Teams participating in the tournament.",
    )
    phase_results: dict[str, list[PhaseResult]] = Field(
        default_factory=dict,
        description="Phase results per team, keyed by team_id.",
    )
    match_results: list[MatchResult] = Field(
        default_factory=list,
        description="Completed match results.",
    )
    started_at: datetime | None = Field(
        default=None,
        description="When the tournament started (UTC).",
    )
    errors: list[StructuredError] = Field(
        default_factory=list,
        description="Accumulated structured errors from all phases.",
    )
