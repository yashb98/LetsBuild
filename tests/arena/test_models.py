"""Tests for AgentForge Arena Pydantic models."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from letsbuild.models.arena_models import (
    AgentConfig,
    ArenaAgentRole,
    Challenge,
    ELORating,
    MatchResult,
    PhaseResult,
    PhaseTimeLimit,
    ScoreDimension,
    TeamConfig,
    TournamentFormat,
    TournamentPhase,
    TournamentState,
)


# --- Enum Tests ---


class TestEnums:
    """Test enum definitions and values."""

    def test_tournament_format_values(self) -> None:
        assert TournamentFormat.DUEL == "duel"
        assert TournamentFormat.STANDARD == "standard"
        assert TournamentFormat.LEAGUE == "league"
        assert TournamentFormat.GRAND_PRIX == "grand_prix"

    def test_tournament_phase_values(self) -> None:
        assert TournamentPhase.PREP == "prep"
        assert TournamentPhase.RESEARCH == "research"
        assert TournamentPhase.ARCHITECTURE == "architecture"
        assert TournamentPhase.BUILD == "build"
        assert TournamentPhase.CROSS_REVIEW == "cross_review"
        assert TournamentPhase.FIX_SPRINT == "fix_sprint"
        assert TournamentPhase.JUDGING == "judging"
        assert TournamentPhase.COMPLETE == "complete"

    def test_arena_agent_role_values(self) -> None:
        assert ArenaAgentRole.ARCHITECT == "architect"
        assert ArenaAgentRole.BUILDER == "builder"
        assert ArenaAgentRole.FRONTEND == "frontend"
        assert ArenaAgentRole.TESTER == "tester"
        assert ArenaAgentRole.CRITIC == "critic"
        assert ArenaAgentRole.TUTOR == "tutor"


# --- Config Model Tests ---


class TestAgentConfig:
    """Test AgentConfig model."""

    def test_create_minimal(self) -> None:
        config = AgentConfig(role=ArenaAgentRole.BUILDER, model="claude-sonnet-4-6")
        assert config.role == ArenaAgentRole.BUILDER
        assert config.model == "claude-sonnet-4-6"
        assert config.system_prompt_override is None
        assert config.max_turns == 30

    def test_create_with_all_fields(self) -> None:
        config = AgentConfig(
            role=ArenaAgentRole.ARCHITECT,
            model="claude-opus-4-6",
            system_prompt_override="Custom prompt",
            max_turns=50,
        )
        assert config.system_prompt_override == "Custom prompt"
        assert config.max_turns == 50

    def test_serialization_roundtrip(self) -> None:
        config = AgentConfig(role=ArenaAgentRole.TESTER, model="claude-haiku-4-5-20251001")
        data = config.model_dump()
        restored = AgentConfig.model_validate(data)
        assert restored == config


class TestTeamConfig:
    """Test TeamConfig model."""

    def test_create_with_defaults(self) -> None:
        config = TeamConfig(
            team_name="Test Team",
            agents=[AgentConfig(role=ArenaAgentRole.BUILDER, model="claude-sonnet-4-6")],
        )
        assert config.team_name == "Test Team"
        assert len(config.agents) == 1
        assert config.sandbox_id is None
        # team_id should be a valid UUID
        uuid.UUID(config.team_id)

    def test_create_with_sandbox(self) -> None:
        config = TeamConfig(
            team_name="Sandboxed",
            agents=[AgentConfig(role=ArenaAgentRole.BUILDER, model="claude-sonnet-4-6")],
            sandbox_id="container-abc123",
        )
        assert config.sandbox_id == "container-abc123"

    def test_fixture_team_config(self, sample_team_config: TeamConfig) -> None:
        assert sample_team_config.team_name == "Alpha Team"
        assert len(sample_team_config.agents) == 3


class TestPhaseTimeLimit:
    """Test PhaseTimeLimit model."""

    def test_create(self) -> None:
        limit = PhaseTimeLimit(phase=TournamentPhase.BUILD, seconds=1800)
        assert limit.phase == TournamentPhase.BUILD
        assert limit.seconds == 1800


# --- Result Model Tests ---


class TestPhaseResult:
    """Test PhaseResult model."""

    def test_create_minimal(self) -> None:
        result = PhaseResult(
            phase=TournamentPhase.BUILD,
            team_id="team-1",
            duration_seconds=120.5,
            tokens_used=5000,
        )
        assert result.phase == TournamentPhase.BUILD
        assert result.artifacts == {}
        assert result.errors == []

    def test_create_with_artifacts(self) -> None:
        result = PhaseResult(
            phase=TournamentPhase.ARCHITECTURE,
            team_id="team-2",
            duration_seconds=60.0,
            artifacts={"design_doc": "/tmp/design.md"},
            tokens_used=2000,
        )
        assert result.artifacts["design_doc"] == "/tmp/design.md"


class TestScoreDimension:
    """Test ScoreDimension model."""

    def test_create_automated(self) -> None:
        dim = ScoreDimension(
            dimension="test_coverage",
            weight=0.2,
            score=85.0,
            details="85% line coverage",
            source="automated",
        )
        assert dim.source == "automated"

    def test_create_llm_judge(self) -> None:
        dim = ScoreDimension(
            dimension="code_quality",
            weight=0.3,
            score=72.5,
            details="Good structure, minor naming issues",
            source="llm_judge",
        )
        assert dim.source == "llm_judge"

    def test_score_below_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            ScoreDimension(
                dimension="test",
                weight=0.1,
                score=-1.0,
                details="invalid",
                source="automated",
            )

    def test_score_above_100_raises(self) -> None:
        with pytest.raises(ValidationError):
            ScoreDimension(
                dimension="test",
                weight=0.1,
                score=101.0,
                details="invalid",
                source="automated",
            )

    def test_weight_below_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            ScoreDimension(
                dimension="test",
                weight=-0.1,
                score=50.0,
                details="invalid",
                source="automated",
            )

    def test_weight_above_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            ScoreDimension(
                dimension="test",
                weight=1.1,
                score=50.0,
                details="invalid",
                source="automated",
            )

    def test_invalid_source_raises(self) -> None:
        with pytest.raises(ValidationError):
            ScoreDimension(
                dimension="test",
                weight=0.1,
                score=50.0,
                details="invalid",
                source="manual",  # type: ignore[arg-type]
            )


class TestMatchResult:
    """Test MatchResult model."""

    def test_create(self) -> None:
        dim = ScoreDimension(
            dimension="quality",
            weight=1.0,
            score=80.0,
            details="Good",
            source="automated",
        )
        result = MatchResult(
            teams=["team-a", "team-b"],
            scores={"team-a": [dim], "team-b": [dim]},
            composite_scores={"team-a": 80.0, "team-b": 75.0},
            winner="team-a",
            duration_seconds=3600.0,
        )
        assert result.winner == "team-a"
        assert len(result.teams) == 2
        uuid.UUID(result.match_id)

    def test_serialization_roundtrip(self) -> None:
        dim = ScoreDimension(
            dimension="quality",
            weight=1.0,
            score=90.0,
            details="Excellent",
            source="llm_judge",
        )
        result = MatchResult(
            teams=["t1"],
            scores={"t1": [dim]},
            composite_scores={"t1": 90.0},
            winner="t1",
            duration_seconds=100.0,
        )
        data = result.model_dump()
        restored = MatchResult.model_validate(data)
        assert restored.winner == result.winner


class TestELORating:
    """Test ELORating model."""

    def test_create_defaults(self) -> None:
        rating = ELORating(
            config_id="config-1",
            confidence_lower=1100.0,
            confidence_upper=1300.0,
        )
        assert rating.rating == 1200.0
        assert rating.matches_played == 0
        assert rating.win_rate == 0.0

    def test_create_with_history(self) -> None:
        rating = ELORating(
            config_id="config-2",
            rating=1450.0,
            confidence_lower=1400.0,
            confidence_upper=1500.0,
            matches_played=25,
            win_rate=0.72,
        )
        assert rating.rating == 1450.0
        assert rating.win_rate == 0.72

    def test_win_rate_above_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            ELORating(
                config_id="x",
                confidence_lower=1100.0,
                confidence_upper=1300.0,
                win_rate=1.5,
            )

    def test_win_rate_below_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            ELORating(
                config_id="x",
                confidence_lower=1100.0,
                confidence_upper=1300.0,
                win_rate=-0.1,
            )


# --- Challenge Model Tests ---


class TestChallenge:
    """Test Challenge model."""

    def test_create_from_fixture(self, sample_challenge: Challenge) -> None:
        assert sample_challenge.name == "Real-Time Chat API"
        assert len(sample_challenge.requirements) == 3
        assert sample_challenge.difficulty == 6
        assert sample_challenge.category == "backend"

    def test_difficulty_below_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            Challenge(
                name="Bad",
                description="Invalid",
                requirements=["req"],
                judging_weights={"q": 1.0},
                difficulty=0,
                category="test",
            )

    def test_difficulty_above_ten_raises(self) -> None:
        with pytest.raises(ValidationError):
            Challenge(
                name="Bad",
                description="Invalid",
                requirements=["req"],
                judging_weights={"q": 1.0},
                difficulty=11,
                category="test",
            )

    def test_serialization_roundtrip(self, sample_challenge: Challenge) -> None:
        data = sample_challenge.model_dump()
        restored = Challenge.model_validate(data)
        assert restored.name == sample_challenge.name
        assert restored.requirements == sample_challenge.requirements


# --- TournamentState Tests ---


class TestTournamentState:
    """Test TournamentState model."""

    def test_create_from_fixture(self, sample_tournament_state: TournamentState) -> None:
        assert sample_tournament_state.format == TournamentFormat.DUEL
        assert sample_tournament_state.current_phase == TournamentPhase.PREP
        assert sample_tournament_state.challenge is not None
        assert len(sample_tournament_state.teams) == 1
        assert sample_tournament_state.started_at is None
        assert sample_tournament_state.errors == []
        assert sample_tournament_state.phase_results == {}
        assert sample_tournament_state.match_results == []

    def test_default_uuid_generated(self) -> None:
        state = TournamentState(format=TournamentFormat.STANDARD)
        uuid.UUID(state.tournament_id)

    def test_serialization_roundtrip(self, sample_tournament_state: TournamentState) -> None:
        data = sample_tournament_state.model_dump()
        restored = TournamentState.model_validate(data)
        assert restored.format == sample_tournament_state.format
        assert restored.tournament_id == sample_tournament_state.tournament_id
