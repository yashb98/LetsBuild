"""Integration tests for AgentForge Arena — full duel flow and CLI."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from letsbuild.arena.controller import TournamentController
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

runner = CliRunner()


# ---------------------------------------------------------------------------
# Full Duel Flow
# ---------------------------------------------------------------------------


class TestFullDuelFlow:
    """End-to-end tournament flow with mocked external deps."""

    @pytest.mark.asyncio()
    async def test_duel_transitions_prep_to_complete(self) -> None:
        """Full duel with two teams reaches COMPLETE."""
        challenge = Challenge(
            name="Integration Test Challenge",
            description="Build a test app.",
            requirements=["req1", "req2"],
            judging_weights={"functionality": 0.5, "code_quality": 0.5},
            time_limits=[
                PhaseTimeLimit(phase=TournamentPhase.RESEARCH, seconds=5),
                PhaseTimeLimit(phase=TournamentPhase.ARCHITECTURE, seconds=5),
                PhaseTimeLimit(phase=TournamentPhase.BUILD, seconds=5),
                PhaseTimeLimit(phase=TournamentPhase.CROSS_REVIEW, seconds=5),
                PhaseTimeLimit(phase=TournamentPhase.FIX_SPRINT, seconds=5),
                PhaseTimeLimit(phase=TournamentPhase.JUDGING, seconds=5),
            ],
            difficulty=5,
            category="backend",
        )

        teams = [
            TeamConfig(
                team_name="Alpha",
                agents=[
                    AgentConfig(role=ArenaAgentRole.ARCHITECT, model="claude-opus-4-6"),
                    AgentConfig(role=ArenaAgentRole.BUILDER, model="claude-sonnet-4-6"),
                ],
            ),
            TeamConfig(
                team_name="Beta",
                agents=[
                    AgentConfig(role=ArenaAgentRole.ARCHITECT, model="claude-opus-4-6"),
                    AgentConfig(role=ArenaAgentRole.BUILDER, model="claude-sonnet-4-6"),
                ],
            ),
        ]

        state = TournamentState(
            format=TournamentFormat.DUEL,
            challenge=challenge,
            teams=teams,
        )

        controller = TournamentController()
        result = await controller.run_tournament(state)

        assert result.current_phase == TournamentPhase.COMPLETE
        assert result.started_at is not None
        assert len(result.errors) == 0

        # Both teams should have phase results
        for team in result.teams:
            assert team.team_id in result.phase_results
            results = result.phase_results[team.team_id]
            phases = {r.phase for r in results}
            # Should have at least CROSS_REVIEW and JUDGING results
            assert TournamentPhase.CROSS_REVIEW in phases
            assert TournamentPhase.JUDGING in phases


# ---------------------------------------------------------------------------
# CLI Command Tests
# ---------------------------------------------------------------------------


class TestCLICommands:
    """Test CLI commands via Typer test runner."""

    def test_arena_help(self) -> None:
        from letsbuild.cli import app

        result = runner.invoke(app, ["arena", "--help"])
        assert result.exit_code == 0
        assert "AgentForge Arena" in result.output

    def test_challenges_list(self) -> None:
        from letsbuild.cli import app

        result = runner.invoke(app, ["arena", "challenges"])
        assert result.exit_code == 0
        assert "Available Challenges" in result.output

    def test_challenges_filter_category(self) -> None:
        from letsbuild.cli import app

        result = runner.invoke(app, ["arena", "challenges", "--category", "backend"])
        assert result.exit_code == 0

    def test_duel_help(self) -> None:
        from letsbuild.cli import app

        result = runner.invoke(app, ["arena", "duel", "--help"])
        assert result.exit_code == 0
        assert "challenge" in result.output.lower()

    def test_leaderboard(self) -> None:
        from letsbuild.cli import app

        result = runner.invoke(app, ["arena", "leaderboard"])
        assert result.exit_code == 0
        assert "Leaderboard" in result.output

    def test_duel_nonexistent_challenge(self) -> None:
        from letsbuild.cli import app

        result = runner.invoke(app, ["arena", "duel", "nonexistent"])
        assert result.exit_code == 1
