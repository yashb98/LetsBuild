# Phase C: Scoring + Judging

## Goal
Build the automated + LLM judge panel and ELO rating system.

## Pre-read
- `letsbuild/harness/sandbox.py` — SandboxManager.execute() for running pytest/ruff inside containers
- `letsbuild/harness/llm_client.py` — LLMClient for LLM judge calls
- `letsbuild/models/arena_models.py` — ScoreDimension, MatchResult, ELORating

## Files to Create

### 1. `letsbuild/arena/scoring.py`

Two classes:

**JudgePanel** — scores a team's output:
```python
class JudgePanel:
    def __init__(self, sandbox_manager: SandboxManager, llm_client: LLMClient | None = None): ...

    async def score_team(self, team_id: str, sandbox: Sandbox, challenge: Challenge) -> list[ScoreDimension]:
        """Run all judges, return scored dimensions."""
        automated = await self._run_automated(sandbox, challenge)
        llm_scores = await self._run_llm_judge(sandbox, challenge) if self.llm_client else []
        return automated + llm_scores

    async def _run_automated(self, sandbox: Sandbox, challenge: Challenge) -> list[ScoreDimension]:
        """Run inside sandbox via SandboxManager.execute():
        - pytest (hidden test suite if exists) → functionality score
        - ruff check . --statistics → code quality score
        - pytest --cov --cov-report=json → test coverage score
        Parse each output into ScoreDimension with weight from challenge.judging_weights"""

    async def _run_llm_judge(self, sandbox: Sandbox, challenge: Challenge) -> list[ScoreDimension]:
        """Send code + challenge brief to Opus via tool_use.
        Tool schema returns: {architecture_score: int, ux_score: int, innovation_score: int, reasoning: str}
        Convert to ScoreDimension objects."""

    @staticmethod
    def composite_score(dimensions: list[ScoreDimension]) -> float:
        """Weighted average: sum(d.score * d.weight) / sum(d.weight). Deterministic."""
```

**ELOCalculator** — Bradley-Terry model:
```python
class ELOCalculator:
    def update_ratings(self, match: MatchResult, ratings: dict[str, ELORating]) -> dict[str, ELORating]:
        """Update ratings using Bradley-Terry MLE with scipy.optimize.minimize.
        Bootstrap 1000 permutations for confidence intervals.
        K-factor: 32 for new configs (<10 matches), 16 for established."""

    @staticmethod
    def expected_win_rate(rating_a: float, rating_b: float) -> float:
        """1 / (1 + 10^((rating_b - rating_a) / 400))"""

    @staticmethod
    def determine_winner(match: MatchResult) -> str:
        """Return team_id with highest composite_score. Tiebreak: functionality > coverage > build_time."""
```

### 2. Tests

`tests/arena/test_scoring.py`:
- Test JudgePanel._run_automated with mocked sandbox.execute() responses
- Test JudgePanel.composite_score is deterministic
- Test ELOCalculator.expected_win_rate math
- Test ELOCalculator.update_ratings produces valid ratings
- Test winner determination with tiebreakers

## Verification
```bash
ruff check letsbuild/arena/scoring.py --fix && ruff format .
mypy --strict letsbuild/arena/scoring.py
pytest tests/arena/test_scoring.py -v
```
