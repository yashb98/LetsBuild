# Phase F: Tournament Controller

## Goal
Build the main orchestrator that runs the full tournament phase flow.

## Pre-read
- `letsbuild/pipeline/controller.py` — PipelineController pattern you're mirroring
- `letsbuild/pipeline/state.py` — PipelineState accumulation pattern
- `letsbuild/harness/sandbox.py` — SandboxManager for per-team sandboxes
- `letsbuild/forge/executor.py` — ForgeExecutor for parallel within-team work
- `letsbuild/arena/scoring.py` — JudgePanel (your Phase C output)
- `letsbuild/arena/spectator.py` — SpectatorEngine (your Phase D output)
- `letsbuild/arena/worktree.py` — WorktreeManager (your Phase A output)
- `letsbuild/arena/challenges.py` — ChallengeEngine (your Phase E output)

## Files to Create

### 1. `letsbuild/arena/controller.py`

```python
class TournamentController:
    """Orchestrates a full AgentForge Arena tournament.

    Phase flow:
    PREP → RESEARCH → ARCHITECTURE → BUILD → CROSS_REVIEW → FIX_SPRINT → JUDGING → COMPLETE

    Mirrors PipelineController pattern: sequential phase execution,
    parallel team execution within phases, error accumulation, gate validation.
    """

    def __init__(
        self,
        sandbox_manager: SandboxManager | None = None,
        llm_client: LLMClient | None = None,
        spectator: SpectatorEngine | None = None,
        judge_panel: JudgePanel | None = None,
        worktree_manager: WorktreeManager | None = None,
        challenge_engine: ChallengeEngine | None = None,
    ) -> None: ...

    async def run_tournament(self, state: TournamentState) -> TournamentState:
        """Execute all phases and return final state with results."""
        state = await self._phase_prep(state)
        for phase in [RESEARCH, ARCHITECTURE, BUILD, CROSS_REVIEW, FIX_SPRINT, JUDGING]:
            time_limit = self._get_time_limit(state, phase)
            try:
                state = await asyncio.wait_for(
                    self._run_phase(phase, state),
                    timeout=time_limit + 30,  # 30s grace for cleanup
                )
            except asyncio.TimeoutError:
                # Phase timed out — emit event, mark phase complete, continue
                ...
            state.current_phase = phase
        state.current_phase = TournamentPhase.COMPLETE
        return state

    async def _phase_prep(self, state: TournamentState) -> TournamentState:
        """PREP: provision sandboxes, create worktrees, load challenge, deploy hooks."""
        # 1. Load challenge via ChallengeEngine
        # 2. Provision sandbox pool via SandboxManager.provision_pool(len(teams))
        # 3. Create git worktrees via WorktreeManager
        # 4. Copy challenge brief to each worktree
        # 5. Emit prep_complete event

    async def _run_phase(self, phase: TournamentPhase, state: TournamentState) -> TournamentState:
        """Execute a phase for all teams in parallel."""
        # 1. Emit phase_start event
        # 2. asyncio.gather(*[self._run_team_phase(team, phase, state) for team in state.teams])
        # 3. Collect PhaseResults, update state
        # 4. Emit phase_complete event

    async def _run_team_phase(self, team: TeamConfig, phase: TournamentPhase,
                               state: TournamentState) -> PhaseResult:
        """Execute a phase for one team in its sandbox."""
        # RESEARCH: Architect agent researches (web search, GitHub, papers)
        # ARCHITECTURE: Architect creates ARCHITECTURE.md, decomposes tasks
        # BUILD: All agents work in parallel via ForgeExecutor pattern
        # CROSS_REVIEW: Critic reviews OTHER team's code (read-only copy)
        # FIX_SPRINT: Builder+Frontend fix issues from cross-review
        # JUDGING: JudgePanel.score_team()

    async def _phase_cross_review(self, state: TournamentState) -> TournamentState:
        """Special handling: copy code between teams for adversarial review."""
        # For each team pair:
        # 1. WorktreeManager.copy_for_cross_review(team_a_path, team_b_review_path)
        # 2. Team B's Critic reviews Team A's code (and vice versa)
        # 3. Critic writes REVIEW.md in reviewing team's workspace

    async def _phase_judging(self, state: TournamentState) -> TournamentState:
        """Run JudgePanel, compute composite scores, determine winner, update ELO."""
        # 1. JudgePanel.score_team() for each team
        # 2. Composite scores via JudgePanel.composite_score()
        # 3. ELOCalculator.determine_winner()
        # 4. ELOCalculator.update_ratings()
        # 5. Build MatchResult, append to state

    def _get_time_limit(self, state: TournamentState, phase: TournamentPhase) -> int:
        """Look up time limit from challenge config. Default: 1800s."""
```

### 2. Tests

`tests/arena/test_controller.py`:
- Test run_tournament transitions through all phases
- Test phase timeout handling (asyncio.TimeoutError)
- Test parallel team execution (two teams run concurrently)
- Test cross_review copies code correctly
- Test judging produces MatchResult with winner
- Test error accumulation (abort if >= 2 teams fail)
- Mock all external deps: SandboxManager, LLMClient, Redis

## Verification
```bash
ruff check letsbuild/arena/controller.py --fix && ruff format .
mypy --strict letsbuild/arena/controller.py
pytest tests/arena/test_controller.py -v
```
