"""Scoring and judging system for AgentForge Arena tournaments."""

from __future__ import annotations

import json
import math
import re
from typing import TYPE_CHECKING

import structlog

from letsbuild.models.arena_models import (
    Challenge,
    ELORating,
    MatchResult,
    ScoreDimension,
)

if TYPE_CHECKING:
    from letsbuild.harness.llm_client import LLMClient
    from letsbuild.harness.sandbox import Sandbox, SandboxManager

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# JudgePanel
# ---------------------------------------------------------------------------


class JudgePanel:
    """Scores a team's output using automated metrics and optional LLM judge.

    Automated judges run pytest, ruff, and coverage inside the team's
    sandbox. The LLM judge evaluates architecture, UX, and innovation
    via tool_use.
    """

    def __init__(
        self,
        sandbox_manager: SandboxManager,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._sandbox_manager = sandbox_manager
        self._llm_client = llm_client
        self._log = logger.bind(component="judge_panel")

    async def score_team(
        self,
        team_id: str,
        sandbox: Sandbox,
        challenge: Challenge,
    ) -> list[ScoreDimension]:
        """Run all judges and return scored dimensions."""
        self._log.info("scoring_team", team_id=team_id)
        automated = await self._run_automated(sandbox, challenge)
        llm_scores: list[ScoreDimension] = []
        if self._llm_client is not None:
            llm_scores = await self._run_llm_judge(sandbox, challenge)
        return automated + llm_scores

    async def _run_automated(
        self,
        sandbox: Sandbox,
        challenge: Challenge,
    ) -> list[ScoreDimension]:
        """Run automated scoring inside the sandbox.

        Executes pytest (functionality), ruff (code quality), and
        coverage analysis. Parses each output into ScoreDimension
        with weights from challenge.judging_weights.
        """
        dimensions: list[ScoreDimension] = []

        # --- Functionality: pytest ---
        func_weight = challenge.judging_weights.get("functionality", 0.30)
        pytest_cmd = "pytest tests/ -v --tb=short 2>&1 || true"
        if challenge.hidden_test_path:
            pytest_cmd = f"pytest {challenge.hidden_test_path} -v --tb=short 2>&1 || true"

        result = await self._sandbox_manager.execute(sandbox, pytest_cmd, timeout=120)
        func_score = self._parse_pytest_score(result.stdout)
        dimensions.append(
            ScoreDimension(
                dimension="functionality",
                weight=func_weight,
                score=func_score,
                details=f"pytest: {result.stdout[-200:]}" if result.stdout else "no output",
                source="automated",
            )
        )

        # --- Code Quality: ruff ---
        quality_weight = challenge.judging_weights.get("code_quality", 0.20)
        ruff_result = await self._sandbox_manager.execute(
            sandbox, "ruff check . --statistics 2>&1 || true", timeout=60
        )
        quality_score = self._parse_ruff_score(ruff_result.stdout)
        dimensions.append(
            ScoreDimension(
                dimension="code_quality",
                weight=quality_weight,
                score=quality_score,
                details=f"ruff: {ruff_result.stdout[-200:]}" if ruff_result.stdout else "no output",
                source="automated",
            )
        )

        # --- Test Coverage ---
        coverage_weight = challenge.judging_weights.get("test_coverage", 0.15)
        cov_result = await self._sandbox_manager.execute(
            sandbox,
            "pytest tests/ --cov --cov-report=json --cov-report=term-missing 2>&1 || true",
            timeout=120,
        )
        coverage_score = self._parse_coverage_score(cov_result.stdout)
        dimensions.append(
            ScoreDimension(
                dimension="test_coverage",
                weight=coverage_weight,
                score=coverage_score,
                details=f"coverage: {coverage_score:.0f}%",
                source="automated",
            )
        )

        return dimensions

    async def _run_llm_judge(
        self,
        sandbox: Sandbox,
        challenge: Challenge,
    ) -> list[ScoreDimension]:
        """Send code + challenge brief to LLM for qualitative scoring.

        Uses tool_use to extract structured scores for architecture,
        UX design, and innovation.
        """
        if self._llm_client is None:
            return []

        # Read key files from sandbox
        code_result = await self._sandbox_manager.execute(
            sandbox,
            "find . -name '*.py' -o -name '*.ts' -o -name '*.tsx' | head -20 | "
            'xargs -I{} sh -c \'echo "=== {} ==="; cat "{}"\' 2>&1 || true',
            timeout=60,
        )

        tool_schema: dict[str, object] = {
            "name": "score_submission",
            "description": "Score a tournament submission on qualitative dimensions.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "architecture_score": {
                        "type": "integer",
                        "description": "Architecture quality score (0-100).",
                    },
                    "ux_score": {
                        "type": "integer",
                        "description": "UX/design quality score (0-100).",
                    },
                    "innovation_score": {
                        "type": "integer",
                        "description": "Innovation and creativity score (0-100).",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Brief reasoning for the scores.",
                    },
                },
                "required": [
                    "architecture_score",
                    "ux_score",
                    "innovation_score",
                    "reasoning",
                ],
            },
        }

        system = (
            "You are a code competition judge. Score the submission on "
            "architecture, UX, and innovation. Be fair and specific."
        )
        messages: list[dict[str, object]] = [
            {
                "role": "user",
                "content": (
                    f"Challenge: {challenge.name}\n"
                    f"Description: {challenge.description}\n\n"
                    f"Code:\n{code_result.stdout[:8000]}"
                ),
            }
        ]

        try:
            result = await self._llm_client.extract_structured(
                messages=messages,
                system=system,
                tool_schema=tool_schema,
                tool_name="score_submission",
                model="claude-opus-4-6",
            )
        except Exception:
            self._log.warning("llm_judge_failed", exc_info=True)
            return []

        dimensions: list[ScoreDimension] = []
        reasoning = str(result.get("reasoning", ""))

        def _clamp_score(raw: object) -> float:
            return float(min(max(int(str(raw)), 0), 100))

        arch_weight = challenge.judging_weights.get("architecture", 0.10)
        dimensions.append(
            ScoreDimension(
                dimension="architecture",
                weight=arch_weight,
                score=_clamp_score(result.get("architecture_score", 50)),
                details=reasoning,
                source="llm_judge",
            )
        )

        ux_weight = challenge.judging_weights.get("ux_design", 0.15)
        dimensions.append(
            ScoreDimension(
                dimension="ux_design",
                weight=ux_weight,
                score=_clamp_score(result.get("ux_score", 50)),
                details=reasoning,
                source="llm_judge",
            )
        )

        innovation_weight = challenge.judging_weights.get("innovation", 0.10)
        dimensions.append(
            ScoreDimension(
                dimension="innovation",
                weight=innovation_weight,
                score=_clamp_score(result.get("innovation_score", 50)),
                details=reasoning,
                source="llm_judge",
            )
        )

        return dimensions

    @staticmethod
    def composite_score(dimensions: list[ScoreDimension]) -> float:
        """Weighted average: sum(d.score * d.weight) / sum(d.weight).

        Deterministic — no LLM calls. Returns 0.0 if no dimensions.
        """
        total_weight = sum(d.weight for d in dimensions)
        if total_weight == 0.0:
            return 0.0
        return sum(d.score * d.weight for d in dimensions) / total_weight

    # --- Output parsers ---

    @staticmethod
    def _parse_pytest_score(output: str) -> float:
        """Parse pytest output to compute functionality score (0-100)."""
        # Look for "X passed, Y failed" or "X passed"
        match = re.search(r"(\d+)\s+passed", output)
        failed_match = re.search(r"(\d+)\s+failed", output)

        passed = int(match.group(1)) if match else 0
        failed = int(failed_match.group(1)) if failed_match else 0
        total = passed + failed

        if total == 0:
            return 0.0
        return min((passed / total) * 100.0, 100.0)

    @staticmethod
    def _parse_ruff_score(output: str) -> float:
        """Parse ruff output to compute code quality score (0-100).

        Fewer violations → higher score. 0 violations = 100.
        """
        # Look for "Found X error(s)" or "All checks passed"
        if "All checks passed" in output:
            return 100.0

        match = re.search(r"Found\s+(\d+)\s+error", output)
        if match:
            errors = int(match.group(1))
            # Deduct 5 points per error, floor at 0
            return max(100.0 - errors * 5.0, 0.0)

        return 70.0  # Unknown format — neutral score

    @staticmethod
    def _parse_coverage_score(output: str) -> float:
        """Parse coverage output to extract percentage (0-100)."""
        # Look for "TOTAL ... XX%" in coverage report
        match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
        if match:
            return float(match.group(1))

        # Try JSON coverage report
        try:
            if "coverage.json" in output or '"totals"' in output:
                json_match = re.search(r"\{.*\"totals\".*\}", output, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    return float(data.get("totals", {}).get("percent_covered", 0.0))
        except (json.JSONDecodeError, KeyError):
            pass

        return 0.0


# ---------------------------------------------------------------------------
# ELOCalculator
# ---------------------------------------------------------------------------


class ELOCalculator:
    """Bradley-Terry ELO rating system for Arena tournaments."""

    @staticmethod
    def expected_win_rate(rating_a: float, rating_b: float) -> float:
        """Compute expected win probability for player A vs player B.

        Formula: 1 / (1 + 10^((rating_b - rating_a) / 400))
        """
        return 1.0 / (1.0 + math.pow(10.0, (rating_b - rating_a) / 400.0))

    @staticmethod
    def determine_winner(match: MatchResult) -> str:
        """Return team_id with highest composite_score.

        Tiebreak order: functionality > test_coverage > build_time (duration).
        """
        if not match.composite_scores:
            return match.winner

        # Primary: highest composite score
        max_score = max(match.composite_scores.values())
        top_teams = [tid for tid, score in match.composite_scores.items() if score == max_score]

        if len(top_teams) == 1:
            return top_teams[0]

        # Tiebreak 1: functionality score
        def _dim_score(team_id: str, dim_name: str) -> float:
            dims = match.scores.get(team_id, [])
            for d in dims:
                if d.dimension == dim_name:
                    return d.score
            return 0.0

        func_scores = {tid: _dim_score(tid, "functionality") for tid in top_teams}
        max_func = max(func_scores.values())
        func_leaders = [tid for tid, s in func_scores.items() if s == max_func]

        if len(func_leaders) == 1:
            return func_leaders[0]

        # Tiebreak 2: test coverage
        cov_scores = {tid: _dim_score(tid, "test_coverage") for tid in func_leaders}
        max_cov = max(cov_scores.values())
        cov_leaders = [tid for tid, s in cov_scores.items() if s == max_cov]

        if len(cov_leaders) == 1:
            return cov_leaders[0]

        # Tiebreak 3: shorter duration wins
        return min(cov_leaders)  # Stable fallback: lexicographic team_id

    def update_ratings(
        self,
        match: MatchResult,
        ratings: dict[str, ELORating],
    ) -> dict[str, ELORating]:
        """Update ELO ratings based on match results.

        Uses Bradley-Terry model with K-factor:
        - K=32 for new configs (<10 matches)
        - K=16 for established configs

        Returns updated ratings dict (creates new entries for unknown configs).
        """
        winner = self.determine_winner(match)
        updated = dict(ratings)

        for team_id in match.teams:
            if team_id not in updated:
                updated[team_id] = ELORating(
                    config_id=team_id,
                    confidence_lower=1100.0,
                    confidence_upper=1300.0,
                )

        # Update each pair
        for i, team_a in enumerate(match.teams):
            for team_b in match.teams[i + 1 :]:
                rating_a = updated[team_a]
                rating_b = updated[team_b]

                expected_a = self.expected_win_rate(rating_a.rating, rating_b.rating)
                expected_b = 1.0 - expected_a

                actual_a = 1.0 if winner == team_a else 0.0
                actual_b = 1.0 - actual_a

                k_a = 32.0 if rating_a.matches_played < 10 else 16.0
                k_b = 32.0 if rating_b.matches_played < 10 else 16.0

                new_rating_a = rating_a.rating + k_a * (actual_a - expected_a)
                new_rating_b = rating_b.rating + k_b * (actual_b - expected_b)

                # Update ratings
                updated[team_a] = ELORating(
                    config_id=rating_a.config_id,
                    rating=round(new_rating_a, 1),
                    confidence_lower=round(new_rating_a - 100.0, 1),
                    confidence_upper=round(new_rating_a + 100.0, 1),
                    matches_played=rating_a.matches_played + 1,
                    win_rate=self._calc_win_rate(
                        rating_a.win_rate,
                        rating_a.matches_played,
                        winner == team_a,
                    ),
                )
                updated[team_b] = ELORating(
                    config_id=rating_b.config_id,
                    rating=round(new_rating_b, 1),
                    confidence_lower=round(new_rating_b - 100.0, 1),
                    confidence_upper=round(new_rating_b + 100.0, 1),
                    matches_played=rating_b.matches_played + 1,
                    win_rate=self._calc_win_rate(
                        rating_b.win_rate,
                        rating_b.matches_played,
                        winner == team_b,
                    ),
                )

        return updated

    @staticmethod
    def _calc_win_rate(current_rate: float, matches_played: int, won: bool) -> float:
        """Calculate updated win rate after a match."""
        total_wins = current_rate * matches_played + (1.0 if won else 0.0)
        new_total = matches_played + 1
        return round(total_wins / new_total, 4)
