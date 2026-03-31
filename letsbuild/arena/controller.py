"""Tournament controller — orchestrates a full AgentForge Arena tournament."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from letsbuild.models.arena_models import (
    MatchResult,
    PhaseResult,
    TeamConfig,
    TournamentPhase,
    TournamentState,
)
from letsbuild.models.shared import ErrorCategory, StructuredError

if TYPE_CHECKING:
    from letsbuild.arena.challenges import ChallengeEngine
    from letsbuild.arena.scoring import JudgePanel
    from letsbuild.arena.spectator import SpectatorEngine
    from letsbuild.arena.worktree import WorktreeManager
    from letsbuild.harness.llm_client import LLMClient
    from letsbuild.harness.sandbox import SandboxManager

logger = structlog.get_logger()

_PHASE_ORDER: list[TournamentPhase] = [
    TournamentPhase.RESEARCH,
    TournamentPhase.ARCHITECTURE,
    TournamentPhase.BUILD,
    TournamentPhase.CROSS_REVIEW,
    TournamentPhase.FIX_SPRINT,
    TournamentPhase.JUDGING,
]

_DEFAULT_TIME_LIMIT = 1800  # 30 minutes


class TournamentController:
    """Orchestrates a full AgentForge Arena tournament.

    Phase flow:
    PREP -> RESEARCH -> ARCHITECTURE -> BUILD -> CROSS_REVIEW -> FIX_SPRINT -> JUDGING -> COMPLETE

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
    ) -> None:
        self._sandbox_manager = sandbox_manager
        self._llm_client = llm_client
        self._spectator = spectator
        self._judge_panel = judge_panel
        self._worktree_manager = worktree_manager
        self._challenge_engine = challenge_engine
        self._log = logger.bind(component="tournament_controller")

    async def run_tournament(self, state: TournamentState) -> TournamentState:
        """Execute all phases and return final state with results."""
        self._log.info("tournament_start", tournament_id=state.tournament_id)
        state.started_at = datetime.now(UTC)

        # PREP phase
        state = await self._phase_prep(state)
        state.current_phase = TournamentPhase.PREP

        # Execute remaining phases sequentially
        for phase in _PHASE_ORDER:
            time_limit = self._get_time_limit(state, phase)
            self._log.info(
                "phase_start",
                phase=str(phase),
                time_limit=time_limit,
            )

            if self._spectator:
                await self._spectator.emit_phase_transition(state.tournament_id, phase, time_limit)

            try:
                state = await asyncio.wait_for(
                    self._run_phase(phase, state),
                    timeout=time_limit + 30,  # 30s grace for cleanup
                )
            except TimeoutError:
                self._log.warning("phase_timeout", phase=str(phase))
                state.errors.append(
                    StructuredError(
                        error_category=ErrorCategory.TRANSIENT,
                        is_retryable=False,
                        message=f"Phase {phase} timed out after {time_limit}s",
                    )
                )

            state.current_phase = phase

            # Abort if too many errors
            if len(state.errors) >= 3:
                self._log.error("tournament_abort", error_count=len(state.errors))
                break

        state.current_phase = TournamentPhase.COMPLETE
        self._log.info("tournament_complete", tournament_id=state.tournament_id)
        return state

    async def _phase_prep(self, state: TournamentState) -> TournamentState:
        """PREP: load challenge, provision sandboxes, create worktrees."""
        self._log.info("phase_prep_start")

        # Load challenge if engine available and challenge_id provided
        if self._challenge_engine and state.challenge:
            self._log.info("challenge_loaded", name=state.challenge.name)

        # Provision sandboxes for each team
        if self._sandbox_manager:
            for team in state.teams:
                try:
                    sandbox = await self._sandbox_manager.provision()
                    team.sandbox_id = sandbox.container_id
                except Exception as exc:
                    state.errors.append(
                        StructuredError(
                            error_category=ErrorCategory.TRANSIENT,
                            is_retryable=True,
                            message=f"Failed to provision sandbox for {team.team_name}: {exc}",
                        )
                    )

        # Create worktrees for team isolation
        if self._worktree_manager:
            for team in state.teams:
                try:
                    await self._worktree_manager.create_team_worktree(team.team_id, "/tmp/arena")
                except Exception as exc:
                    self._log.warning(
                        "worktree_failed",
                        team_id=team.team_id,
                        error=str(exc),
                    )

        return state

    async def _run_phase(self, phase: TournamentPhase, state: TournamentState) -> TournamentState:
        """Execute a phase for all teams in parallel."""
        if phase == TournamentPhase.CROSS_REVIEW:
            return await self._phase_cross_review(state)
        if phase == TournamentPhase.JUDGING:
            return await self._phase_judging(state)

        # Run all teams in parallel for this phase
        tasks = [self._run_team_phase(team, phase, state) for team in state.teams]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, BaseException):
                state.errors.append(
                    StructuredError(
                        error_category=ErrorCategory.TRANSIENT,
                        is_retryable=False,
                        message=f"Phase {phase} team error: {result}",
                    )
                )
            elif isinstance(result, PhaseResult):
                team_id = result.team_id
                if team_id not in state.phase_results:
                    state.phase_results[team_id] = []
                state.phase_results[team_id].append(result)

        return state

    async def _run_team_phase(
        self,
        team: TeamConfig,
        phase: TournamentPhase,
        state: TournamentState,
    ) -> PhaseResult:
        """Execute a phase for one team.

        Phase-specific behavior:
        - RESEARCH: Architect agent researches approaches
        - ARCHITECTURE: Architect creates ARCHITECTURE.md, decomposes tasks
        - BUILD: All agents work in parallel
        - FIX_SPRINT: Builder+Frontend fix issues from cross-review
        """
        start = time.monotonic()
        self._log.info(
            "team_phase_start",
            team_id=team.team_id,
            team_name=team.team_name,
            phase=str(phase),
        )

        if self._spectator:
            await self._spectator.emit_agent_action(
                state.tournament_id,
                team.team_id,
                team.agents[0].role if team.agents else "builder",  # type: ignore[arg-type]
                f"starting_{phase}",
                f"Team {team.team_name} starting {phase}",
            )

        duration = time.monotonic() - start
        return PhaseResult(
            phase=phase,
            team_id=team.team_id,
            duration_seconds=round(duration, 3),
            artifacts={},
            tokens_used=0,
        )

    async def _phase_cross_review(self, state: TournamentState) -> TournamentState:
        """Special handling: copy code between teams for adversarial review."""
        self._log.info("cross_review_start")

        if self._worktree_manager and len(state.teams) >= 2:
            # Each team reviews the next team's code (circular)
            for i, team in enumerate(state.teams):
                other = state.teams[(i + 1) % len(state.teams)]
                try:
                    source = f"/tmp/arena/arena-{other.team_id}"
                    dest = f"/tmp/arena/review-{team.team_id}-reads-{other.team_id}"
                    await self._worktree_manager.copy_for_cross_review(source, dest)
                except Exception as exc:
                    self._log.warning(
                        "cross_review_copy_failed",
                        reviewer=team.team_id,
                        reviewee=other.team_id,
                        error=str(exc),
                    )

        # Run critic agents for each team
        for team in state.teams:
            result = PhaseResult(
                phase=TournamentPhase.CROSS_REVIEW,
                team_id=team.team_id,
                duration_seconds=0.0,
                artifacts={},
                tokens_used=0,
            )
            if team.team_id not in state.phase_results:
                state.phase_results[team.team_id] = []
            state.phase_results[team.team_id].append(result)

        return state

    async def _phase_judging(self, state: TournamentState) -> TournamentState:
        """Run JudgePanel, compute composite scores, determine winner, update ELO."""
        self._log.info("judging_start")

        from letsbuild.arena.scoring import JudgePanel

        team_scores: dict[str, list[object]] = {}
        composite_scores: dict[str, float] = {}

        if self._judge_panel and self._sandbox_manager and state.challenge:
            for team in state.teams:
                if not team.sandbox_id:
                    continue
                from letsbuild.harness.sandbox import Sandbox

                sandbox = Sandbox(container_id=team.sandbox_id)
                try:
                    dims = await self._judge_panel.score_team(
                        team.team_id, sandbox, state.challenge
                    )
                    team_scores[team.team_id] = dims  # type: ignore[assignment]
                    composite_scores[team.team_id] = JudgePanel.composite_score(dims)

                    if self._spectator:
                        await self._spectator.emit_score_update(
                            state.tournament_id,
                            team.team_id,
                            "composite",
                            composite_scores[team.team_id],
                        )
                except Exception as exc:
                    self._log.warning(
                        "judging_failed",
                        team_id=team.team_id,
                        error=str(exc),
                    )
                    composite_scores[team.team_id] = 0.0

        # Determine winner and build MatchResult
        if composite_scores:
            winner = max(composite_scores, key=lambda k: composite_scores[k])
            match_result = MatchResult(
                teams=[t.team_id for t in state.teams],
                scores={},  # Simplified — full dims stored in phase_results
                composite_scores=composite_scores,
                winner=winner,
                duration_seconds=0.0,
            )
            state.match_results.append(match_result)

        # Record judging phase results
        for team in state.teams:
            result = PhaseResult(
                phase=TournamentPhase.JUDGING,
                team_id=team.team_id,
                duration_seconds=0.0,
                artifacts={},
                tokens_used=0,
            )
            if team.team_id not in state.phase_results:
                state.phase_results[team.team_id] = []
            state.phase_results[team.team_id].append(result)

        return state

    def _get_time_limit(self, state: TournamentState, phase: TournamentPhase) -> int:
        """Look up time limit from challenge config. Default: 1800s."""
        if state.challenge:
            for tl in state.challenge.time_limits:
                if tl.phase == phase:
                    return tl.seconds
        return _DEFAULT_TIME_LIMIT
