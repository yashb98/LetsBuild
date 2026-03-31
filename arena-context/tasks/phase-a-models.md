# Phase A: Models + Foundation

## Goal
Create the Pydantic models and module skeleton for AgentForge Arena.

## Pre-read (load these before starting)
- `letsbuild/models/forge_models.py` — pattern to follow for enums, models, Field usage
- `letsbuild/models/shared.py` — StructuredError, reuse as-is
- `letsbuild/pipeline/state.py` — PipelineState pattern to mirror for TournamentState

## Files to Create

### 1. `letsbuild/arena/__init__.py`
```python
"""AgentForge Arena — Competitive AI agent tournament platform."""
```

### 2. `letsbuild/arena/agents/__init__.py`
Empty init.

### 3. `letsbuild/models/arena_models.py`

Define these (Pydantic v2, `ConfigDict(strict=True)`, Field descriptions on every field):

**Enums:**
- `TournamentFormat`: DUEL, STANDARD, LEAGUE, GRAND_PRIX
- `TournamentPhase`: PREP, RESEARCH, ARCHITECTURE, BUILD, CROSS_REVIEW, FIX_SPRINT, JUDGING, COMPLETE
- `ArenaAgentRole`: ARCHITECT, BUILDER, FRONTEND, TESTER, CRITIC, TUTOR

**Config Models:**
- `AgentConfig`: role (ArenaAgentRole), model (str), system_prompt_override (str|None), max_turns (int=30)
- `TeamConfig`: team_id (str, uuid4 default), team_name (str), agents (list[AgentConfig]), sandbox_id (str|None)
- `PhaseTimeLimit`: phase (TournamentPhase), seconds (int)

**Result Models:**
- `PhaseResult`: phase, team_id, duration_seconds, artifacts (dict[str,str]), tokens_used, errors (list[StructuredError])
- `ScoreDimension`: dimension (str), weight (float), score (float 0-100), details (str), source (Literal["automated","llm_judge"])
- `MatchResult`: match_id, teams (list[str]), scores (dict[str, list[ScoreDimension]]), composite_scores (dict[str,float]), winner (str), duration_seconds, phase_results (list[PhaseResult])
- `ELORating`: config_id, rating (float=1200.0), confidence_lower, confidence_upper, matches_played (int=0), win_rate (float=0.0)

**Challenge Model:**
- `Challenge`: challenge_id, name, description, requirements (list[str]), bonus_features (list[str]), constraints (dict), judging_weights (dict[str,float]), hidden_test_path (str|None), time_limits (list[PhaseTimeLimit]), difficulty (int 1-10), category (str)

**State Model:**
- `TournamentState`: tournament_id (uuid4), format (TournamentFormat), current_phase (TournamentPhase=PREP), challenge (Challenge|None), teams (list[TeamConfig]), phase_results (dict mapping team_id→list[PhaseResult]), match_results (list[MatchResult]), started_at (datetime|None), errors (list[StructuredError])

### 4. `letsbuild/arena/worktree.py`

Git worktree manager for team isolation.

```python
class WorktreeManager:
    async def create_team_worktree(self, team_id: str, base_path: str) -> str:
        """git worktree add {base_path}/arena-{team_id} -b arena/{team_id}"""

    async def cleanup_worktrees(self, team_ids: list[str], base_path: str) -> None:
        """git worktree remove + branch delete for each team"""

    async def copy_for_cross_review(self, source_path: str, dest_path: str) -> None:
        """cp -r source to read-only dest for cross-review"""
```

Use `asyncio.create_subprocess_exec` for git commands. Log with structlog.

### 5. Test Files

- `tests/arena/__init__.py`
- `tests/arena/conftest.py` — fixtures: `sample_team_config()`, `sample_challenge()`, `sample_tournament_state()`
- `tests/arena/test_models.py` — test all model creation, validation, serialization
- `tests/arena/test_worktree.py` — test create/cleanup (mock subprocess calls)

## Verification
```bash
ruff check letsbuild/models/arena_models.py letsbuild/arena/ --fix && ruff format .
mypy --strict letsbuild/models/arena_models.py letsbuild/arena/worktree.py
pytest tests/arena/ -v
```
