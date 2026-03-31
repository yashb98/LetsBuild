"""Tests for TournamentController — tournament phase orchestration."""

from __future__ import annotations

import pytest

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

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_state(num_teams: int = 2) -> TournamentState:
    """Create a TournamentState with the given number of teams."""
    teams = []
    for i in range(num_teams):
        teams.append(
            TeamConfig(
                team_name=f"Team {chr(65 + i)}",
                agents=[
                    AgentConfig(role=ArenaAgentRole.ARCHITECT, model="claude-opus-4-6"),
                    AgentConfig(role=ArenaAgentRole.BUILDER, model="claude-sonnet-4-6"),
                ],
            )
        )

    challenge = Challenge(
        name="Test Challenge",
        description="Build something.",
        requirements=["req1"],
        judging_weights={"functionality": 0.5, "code_quality": 0.5},
        time_limits=[
            PhaseTimeLimit(phase=TournamentPhase.RESEARCH, seconds=10),
            PhaseTimeLimit(phase=TournamentPhase.ARCHITECTURE, seconds=10),
            PhaseTimeLimit(phase=TournamentPhase.BUILD, seconds=10),
            PhaseTimeLimit(phase=TournamentPhase.CROSS_REVIEW, seconds=10),
            PhaseTimeLimit(phase=TournamentPhase.FIX_SPRINT, seconds=10),
            PhaseTimeLimit(phase=TournamentPhase.JUDGING, seconds=10),
        ],
        difficulty=5,
        category="backend",
    )

    return TournamentState(
        format=TournamentFormat.DUEL,
        challenge=challenge,
        teams=teams,
    )


# ---------------------------------------------------------------------------
# Phase Transition Tests
# ---------------------------------------------------------------------------


class TestPhaseTransitions:
    """Test that run_tournament transitions through all phases."""

    @pytest.mark.asyncio()
    async def test_reaches_complete(self) -> None:
        controller = TournamentController()
        state = _make_state()
        result = await controller.run_tournament(state)
        assert result.current_phase == TournamentPhase.COMPLETE

    @pytest.mark.asyncio()
    async def test_started_at_set(self) -> None:
        controller = TournamentController()
        state = _make_state()
        result = await controller.run_tournament(state)
        assert result.started_at is not None

    @pytest.mark.asyncio()
    async def test_phase_results_populated(self) -> None:
        controller = TournamentController()
        state = _make_state()
        result = await controller.run_tournament(state)
        # Each team should have phase results
        for team in result.teams:
            assert team.team_id in result.phase_results
            assert len(result.phase_results[team.team_id]) > 0


# ---------------------------------------------------------------------------
# Parallel Execution Tests
# ---------------------------------------------------------------------------


class TestParallelExecution:
    """Test that teams run concurrently within phases."""

    @pytest.mark.asyncio()
    async def test_two_teams_both_get_results(self) -> None:
        controller = TournamentController()
        state = _make_state(num_teams=2)
        result = await controller.run_tournament(state)
        assert len(result.phase_results) == 2

    @pytest.mark.asyncio()
    async def test_single_team_works(self) -> None:
        controller = TournamentController()
        state = _make_state(num_teams=1)
        result = await controller.run_tournament(state)
        assert result.current_phase == TournamentPhase.COMPLETE


# ---------------------------------------------------------------------------
# Time Limit Tests
# ---------------------------------------------------------------------------


class TestTimeLimits:
    """Test time limit lookup."""

    def test_get_time_limit_from_challenge(self) -> None:
        controller = TournamentController()
        state = _make_state()
        limit = controller._get_time_limit(state, TournamentPhase.BUILD)
        assert limit == 10  # From fixture

    def test_default_time_limit_no_challenge(self) -> None:
        controller = TournamentController()
        state = TournamentState(format=TournamentFormat.DUEL)
        limit = controller._get_time_limit(state, TournamentPhase.BUILD)
        assert limit == 1800  # Default


# ---------------------------------------------------------------------------
# Error Accumulation Tests
# ---------------------------------------------------------------------------


class TestErrorAccumulation:
    """Test error handling and accumulation."""

    @pytest.mark.asyncio()
    async def test_no_errors_clean_run(self) -> None:
        controller = TournamentController()
        state = _make_state()
        result = await controller.run_tournament(state)
        assert len(result.errors) == 0

    @pytest.mark.asyncio()
    async def test_empty_teams_no_crash(self) -> None:
        controller = TournamentController()
        state = TournamentState(format=TournamentFormat.DUEL, teams=[])
        result = await controller.run_tournament(state)
        assert result.current_phase == TournamentPhase.COMPLETE


# ---------------------------------------------------------------------------
# Cross Review Tests
# ---------------------------------------------------------------------------


class TestCrossReview:
    """Test cross-review phase behavior."""

    @pytest.mark.asyncio()
    async def test_cross_review_creates_phase_results(self) -> None:
        controller = TournamentController()
        state = _make_state()
        result = await controller._phase_cross_review(state)
        for team in result.teams:
            team_results = result.phase_results.get(team.team_id, [])
            cross_results = [r for r in team_results if r.phase == TournamentPhase.CROSS_REVIEW]
            assert len(cross_results) == 1


# ---------------------------------------------------------------------------
# Judging Tests
# ---------------------------------------------------------------------------


class TestJudging:
    """Test judging phase behavior."""

    @pytest.mark.asyncio()
    async def test_judging_without_judge_panel(self) -> None:
        """Judging without JudgePanel still records phase results."""
        controller = TournamentController()
        state = _make_state()
        result = await controller._phase_judging(state)
        for team in result.teams:
            team_results = result.phase_results.get(team.team_id, [])
            judging_results = [r for r in team_results if r.phase == TournamentPhase.JUDGING]
            assert len(judging_results) == 1

    @pytest.mark.asyncio()
    async def test_judging_no_match_result_without_scores(self) -> None:
        """Without JudgePanel, no MatchResult is created."""
        controller = TournamentController()
        state = _make_state()
        result = await controller._phase_judging(state)
        assert len(result.match_results) == 0
