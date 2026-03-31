"""Shared fixtures for AgentForge Arena tests."""

from __future__ import annotations

import pytest

from letsbuild.models.arena_models import (
    AgentConfig,
    ArenaAgentRole,
    Challenge,
    PhaseTimeLimit,
    TeamConfig,
    TournamentFormat,
    TournamentPhase,
    TournamentState,
)


@pytest.fixture()
def sample_agent_config() -> AgentConfig:
    """A minimal agent configuration for testing."""
    return AgentConfig(
        role=ArenaAgentRole.BUILDER,
        model="claude-sonnet-4-6",
    )


@pytest.fixture()
def sample_team_config() -> TeamConfig:
    """A team configuration with two agents."""
    return TeamConfig(
        team_name="Alpha Team",
        agents=[
            AgentConfig(role=ArenaAgentRole.ARCHITECT, model="claude-opus-4-6"),
            AgentConfig(role=ArenaAgentRole.BUILDER, model="claude-sonnet-4-6"),
            AgentConfig(role=ArenaAgentRole.TESTER, model="claude-sonnet-4-6"),
        ],
    )


@pytest.fixture()
def sample_challenge() -> Challenge:
    """A sample coding challenge for testing."""
    return Challenge(
        name="Real-Time Chat API",
        description="Build a real-time chat API with WebSocket support.",
        requirements=[
            "WebSocket endpoint for real-time messaging",
            "REST endpoints for room management",
            "Message persistence with SQLite",
        ],
        bonus_features=["Typing indicators", "Read receipts"],
        judging_weights={
            "code_quality": 0.3,
            "test_coverage": 0.2,
            "architecture": 0.25,
            "functionality": 0.25,
        },
        time_limits=[
            PhaseTimeLimit(phase=TournamentPhase.RESEARCH, seconds=300),
            PhaseTimeLimit(phase=TournamentPhase.BUILD, seconds=1800),
        ],
        difficulty=6,
        category="backend",
    )


@pytest.fixture()
def sample_tournament_state(
    sample_team_config: TeamConfig,
    sample_challenge: Challenge,
) -> TournamentState:
    """A tournament state with one team and a challenge loaded."""
    return TournamentState(
        format=TournamentFormat.DUEL,
        challenge=sample_challenge,
        teams=[sample_team_config],
    )
