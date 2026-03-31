"""Tests for AgentForge Arena scoring and judging system."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from letsbuild.arena.scoring import ELOCalculator, JudgePanel
from letsbuild.models.arena_models import (
    Challenge,
    ELORating,
    MatchResult,
    PhaseTimeLimit,
    ScoreDimension,
    TournamentPhase,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_challenge() -> Challenge:
    """Challenge with standard judging weights."""
    return Challenge(
        name="Test Challenge",
        description="Build something cool.",
        requirements=["req1"],
        judging_weights={
            "functionality": 0.30,
            "code_quality": 0.20,
            "test_coverage": 0.15,
            "architecture": 0.10,
            "ux_design": 0.15,
            "innovation": 0.10,
        },
        time_limits=[PhaseTimeLimit(phase=TournamentPhase.BUILD, seconds=1800)],
        difficulty=5,
        category="backend",
    )


@pytest.fixture()
def mock_sandbox() -> MagicMock:
    """A mock Sandbox object."""
    sandbox = MagicMock()
    sandbox.container_id = "test-container"
    sandbox.workspace_path = "/mnt/workspace"
    return sandbox


@pytest.fixture()
def mock_sandbox_manager() -> MagicMock:
    """A mock SandboxManager that returns configurable ExecResult-like objects."""
    manager = MagicMock()

    async def fake_execute(sandbox: object, command: str, timeout: int = 60) -> MagicMock:
        result = MagicMock()
        result.exit_code = 0
        result.timed_out = False

        if "pytest" in command and "cov" not in command:
            result.stdout = "10 passed, 2 failed in 1.5s"
        elif "ruff" in command:
            result.stdout = "All checks passed!"
        elif "cov" in command:
            result.stdout = "TOTAL    500    100    80%"
        else:
            result.stdout = ""
        return result

    manager.execute = AsyncMock(side_effect=fake_execute)
    return manager


# ---------------------------------------------------------------------------
# JudgePanel: Automated Scoring
# ---------------------------------------------------------------------------


class TestJudgePanelAutomated:
    """Test automated scoring with mocked sandbox."""

    @pytest.mark.asyncio()
    async def test_run_automated_returns_three_dimensions(
        self,
        mock_sandbox_manager: MagicMock,
        mock_sandbox: MagicMock,
        sample_challenge: Challenge,
    ) -> None:
        panel = JudgePanel(sandbox_manager=mock_sandbox_manager)
        dims = await panel._run_automated(mock_sandbox, sample_challenge)
        assert len(dims) == 3
        dim_names = {d.dimension for d in dims}
        assert dim_names == {"functionality", "code_quality", "test_coverage"}

    @pytest.mark.asyncio()
    async def test_run_automated_all_sources_are_automated(
        self,
        mock_sandbox_manager: MagicMock,
        mock_sandbox: MagicMock,
        sample_challenge: Challenge,
    ) -> None:
        panel = JudgePanel(sandbox_manager=mock_sandbox_manager)
        dims = await panel._run_automated(mock_sandbox, sample_challenge)
        assert all(d.source == "automated" for d in dims)

    @pytest.mark.asyncio()
    async def test_score_team_without_llm_returns_automated_only(
        self,
        mock_sandbox_manager: MagicMock,
        mock_sandbox: MagicMock,
        sample_challenge: Challenge,
    ) -> None:
        panel = JudgePanel(sandbox_manager=mock_sandbox_manager, llm_client=None)
        dims = await panel.score_team("team-1", mock_sandbox, sample_challenge)
        assert len(dims) == 3  # Only automated, no LLM


# ---------------------------------------------------------------------------
# JudgePanel: Pytest Parser
# ---------------------------------------------------------------------------


class TestPytestParser:
    """Test _parse_pytest_score."""

    def test_all_passed(self) -> None:
        assert JudgePanel._parse_pytest_score("10 passed in 1.5s") == 100.0

    def test_some_failed(self) -> None:
        score = JudgePanel._parse_pytest_score("8 passed, 2 failed in 2.0s")
        assert score == pytest.approx(80.0)

    def test_no_tests(self) -> None:
        assert JudgePanel._parse_pytest_score("no tests ran") == 0.0

    def test_empty_output(self) -> None:
        assert JudgePanel._parse_pytest_score("") == 0.0


# ---------------------------------------------------------------------------
# JudgePanel: Ruff Parser
# ---------------------------------------------------------------------------


class TestRuffParser:
    """Test _parse_ruff_score."""

    def test_all_passed(self) -> None:
        assert JudgePanel._parse_ruff_score("All checks passed!") == 100.0

    def test_errors_found(self) -> None:
        assert JudgePanel._parse_ruff_score("Found 4 errors") == 80.0

    def test_many_errors(self) -> None:
        assert JudgePanel._parse_ruff_score("Found 25 errors") == 0.0

    def test_unknown_format(self) -> None:
        assert JudgePanel._parse_ruff_score("something unexpected") == 70.0


# ---------------------------------------------------------------------------
# JudgePanel: Coverage Parser
# ---------------------------------------------------------------------------


class TestCoverageParser:
    """Test _parse_coverage_score."""

    def test_standard_output(self) -> None:
        output = "TOTAL    500    100    80%"
        assert JudgePanel._parse_coverage_score(output) == 80.0

    def test_no_coverage(self) -> None:
        assert JudgePanel._parse_coverage_score("") == 0.0


# ---------------------------------------------------------------------------
# JudgePanel: Composite Score
# ---------------------------------------------------------------------------


class TestCompositeScore:
    """Test composite_score is deterministic."""

    def test_weighted_average(self) -> None:
        dims = [
            ScoreDimension(dimension="a", weight=0.6, score=80.0, details="", source="automated"),
            ScoreDimension(dimension="b", weight=0.4, score=60.0, details="", source="automated"),
        ]
        # (80*0.6 + 60*0.4) / (0.6+0.4) = (48+24)/1.0 = 72.0
        assert JudgePanel.composite_score(dims) == pytest.approx(72.0)

    def test_empty_dimensions(self) -> None:
        assert JudgePanel.composite_score([]) == 0.0

    def test_single_dimension(self) -> None:
        dims = [
            ScoreDimension(dimension="x", weight=1.0, score=95.0, details="", source="automated"),
        ]
        assert JudgePanel.composite_score(dims) == pytest.approx(95.0)

    def test_deterministic(self) -> None:
        dims = [
            ScoreDimension(dimension="a", weight=0.5, score=70.0, details="", source="automated"),
            ScoreDimension(dimension="b", weight=0.5, score=90.0, details="", source="llm_judge"),
        ]
        score1 = JudgePanel.composite_score(dims)
        score2 = JudgePanel.composite_score(dims)
        assert score1 == score2


# ---------------------------------------------------------------------------
# ELOCalculator: Expected Win Rate
# ---------------------------------------------------------------------------


class TestExpectedWinRate:
    """Test ELO expected_win_rate math."""

    def test_equal_ratings(self) -> None:
        rate = ELOCalculator.expected_win_rate(1200.0, 1200.0)
        assert rate == pytest.approx(0.5)

    def test_higher_rated_favored(self) -> None:
        rate = ELOCalculator.expected_win_rate(1400.0, 1200.0)
        assert rate > 0.5
        assert rate < 1.0

    def test_lower_rated_underdog(self) -> None:
        rate = ELOCalculator.expected_win_rate(1200.0, 1400.0)
        assert rate < 0.5
        assert rate > 0.0

    def test_symmetry(self) -> None:
        rate_a = ELOCalculator.expected_win_rate(1400.0, 1200.0)
        rate_b = ELOCalculator.expected_win_rate(1200.0, 1400.0)
        assert rate_a + rate_b == pytest.approx(1.0)

    def test_400_point_gap(self) -> None:
        # 400-point gap should give ~0.909 expected win rate
        rate = ELOCalculator.expected_win_rate(1600.0, 1200.0)
        assert rate == pytest.approx(0.909, abs=0.01)


# ---------------------------------------------------------------------------
# ELOCalculator: Update Ratings
# ---------------------------------------------------------------------------


class TestUpdateRatings:
    """Test ELO rating updates."""

    def test_winner_rating_increases(self) -> None:
        dim = ScoreDimension(dimension="x", weight=1.0, score=80.0, details="", source="automated")
        match = MatchResult(
            teams=["team-a", "team-b"],
            scores={"team-a": [dim], "team-b": [dim]},
            composite_scores={"team-a": 80.0, "team-b": 60.0},
            winner="team-a",
            duration_seconds=100.0,
        )
        ratings: dict[str, ELORating] = {}
        calc = ELOCalculator()
        updated = calc.update_ratings(match, ratings)

        assert updated["team-a"].rating > 1200.0
        assert updated["team-b"].rating < 1200.0

    def test_ratings_sum_preserved(self) -> None:
        """Total rating points should be conserved (zero-sum)."""
        dim = ScoreDimension(dimension="x", weight=1.0, score=90.0, details="", source="automated")
        match = MatchResult(
            teams=["a", "b"],
            scores={"a": [dim], "b": [dim]},
            composite_scores={"a": 90.0, "b": 70.0},
            winner="a",
            duration_seconds=50.0,
        )
        ratings: dict[str, ELORating] = {}
        calc = ELOCalculator()
        updated = calc.update_ratings(match, ratings)
        total = updated["a"].rating + updated["b"].rating
        assert total == pytest.approx(2400.0, abs=0.5)

    def test_matches_played_increments(self) -> None:
        dim = ScoreDimension(dimension="x", weight=1.0, score=80.0, details="", source="automated")
        match = MatchResult(
            teams=["a", "b"],
            scores={"a": [dim], "b": [dim]},
            composite_scores={"a": 80.0, "b": 60.0},
            winner="a",
            duration_seconds=100.0,
        )
        calc = ELOCalculator()
        updated = calc.update_ratings(match, {})
        assert updated["a"].matches_played == 1
        assert updated["b"].matches_played == 1


# ---------------------------------------------------------------------------
# ELOCalculator: Winner Determination
# ---------------------------------------------------------------------------


class TestDetermineWinner:
    """Test winner determination with tiebreakers."""

    def test_clear_winner(self) -> None:
        match = MatchResult(
            teams=["a", "b"],
            scores={},
            composite_scores={"a": 85.0, "b": 70.0},
            winner="a",
            duration_seconds=100.0,
        )
        assert ELOCalculator.determine_winner(match) == "a"

    def test_tiebreak_functionality(self) -> None:
        func_a = ScoreDimension(
            dimension="functionality",
            weight=0.3,
            score=90.0,
            details="",
            source="automated",
        )
        func_b = ScoreDimension(
            dimension="functionality",
            weight=0.3,
            score=80.0,
            details="",
            source="automated",
        )
        match = MatchResult(
            teams=["a", "b"],
            scores={"a": [func_a], "b": [func_b]},
            composite_scores={"a": 80.0, "b": 80.0},  # Tied
            winner="a",
            duration_seconds=100.0,
        )
        assert ELOCalculator.determine_winner(match) == "a"

    def test_tiebreak_coverage(self) -> None:
        func = ScoreDimension(
            dimension="functionality",
            weight=0.3,
            score=80.0,
            details="",
            source="automated",
        )
        cov_a = ScoreDimension(
            dimension="test_coverage",
            weight=0.15,
            score=90.0,
            details="",
            source="automated",
        )
        cov_b = ScoreDimension(
            dimension="test_coverage",
            weight=0.15,
            score=70.0,
            details="",
            source="automated",
        )
        match = MatchResult(
            teams=["a", "b"],
            scores={"a": [func, cov_a], "b": [func, cov_b]},
            composite_scores={"a": 80.0, "b": 80.0},  # Tied
            winner="a",
            duration_seconds=100.0,
        )
        assert ELOCalculator.determine_winner(match) == "a"
