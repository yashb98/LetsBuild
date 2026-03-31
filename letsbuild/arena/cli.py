"""CLI commands for AgentForge Arena — competitive agent tournaments."""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich import print as rprint
from rich.table import Table

from letsbuild.arena.challenges import ChallengeEngine
from letsbuild.arena.controller import TournamentController
from letsbuild.models.arena_models import (
    AgentConfig,
    ArenaAgentRole,
    TeamConfig,
    TournamentFormat,
    TournamentState,
)

arena_app = typer.Typer(
    name="arena",
    help="AgentForge Arena — competitive agent tournaments.",
)


@arena_app.command()
def duel(
    challenge: Annotated[
        str,
        typer.Argument(help="Challenge ID from skills/challenges/ (e.g. 'url-shortener')"),
    ],
    team_a_model: Annotated[
        str,
        typer.Option("--team-a-model", help="Model for Team Alpha"),
    ] = "claude-sonnet-4-6",
    team_b_model: Annotated[
        str,
        typer.Option("--team-b-model", help="Model for Team Beta"),
    ] = "claude-sonnet-4-6",
    build_time: Annotated[
        int,
        typer.Option("--build-time", help="Build phase time in seconds"),
    ] = 5400,
) -> None:
    """Run a duel between two agent teams."""
    rprint(f"[bold cyan]Arena Duel:[/] {challenge}")
    rprint(f"  Team Alpha: {team_a_model}")
    rprint(f"  Team Beta:  {team_b_model}")
    rprint(f"  Build time: {build_time}s")
    rprint()

    # Load challenge
    engine = ChallengeEngine()
    try:
        challenge_obj = engine.load(challenge)
    except FileNotFoundError:
        rprint(f"[bold red]Error:[/] Challenge '{challenge}' not found.")
        raise typer.Exit(code=1) from None

    # Build teams
    def _make_team(name: str, model: str) -> TeamConfig:
        return TeamConfig(
            team_name=name,
            agents=[
                AgentConfig(role=ArenaAgentRole.ARCHITECT, model=model),
                AgentConfig(role=ArenaAgentRole.BUILDER, model=model),
                AgentConfig(role=ArenaAgentRole.FRONTEND, model=model),
                AgentConfig(role=ArenaAgentRole.TESTER, model=model),
                AgentConfig(role=ArenaAgentRole.CRITIC, model=model),
            ],
        )

    team_a = _make_team("Team Alpha", team_a_model)
    team_b = _make_team("Team Beta", team_b_model)

    state = TournamentState(
        format=TournamentFormat.DUEL,
        challenge=challenge_obj,
        teams=[team_a, team_b],
    )

    # Run tournament
    controller = TournamentController()
    result = asyncio.run(controller.run_tournament(state))

    # Print results
    rprint()
    rprint(f"[bold green]Tournament Complete![/] Phase: {result.current_phase}")

    if result.match_results:
        match = result.match_results[0]
        rprint(f"[bold]Winner:[/] {match.winner}")

        table = Table(title="Scores")
        table.add_column("Team", style="cyan")
        table.add_column("Score", style="green")
        for team_id, score in match.composite_scores.items():
            team_name = next(
                (t.team_name for t in result.teams if t.team_id == team_id),
                team_id,
            )
            table.add_row(team_name, f"{score:.1f}")
        rprint(table)

    if result.errors:
        rprint(f"\n[bold yellow]Warnings:[/] {len(result.errors)} error(s)")


@arena_app.command()
def leaderboard(
    top: Annotated[
        int,
        typer.Option("--top", help="Number of entries to show"),
    ] = 20,
) -> None:
    """Show the ELO leaderboard."""
    rprint(f"[bold cyan]Arena Leaderboard[/] (top {top})")
    rprint("[dim]No matches played yet. Run 'letsbuild arena duel' to start.[/]")


@arena_app.command(name="challenges")
def list_challenges(
    category: Annotated[
        str | None,
        typer.Option("--category", help="Filter by category"),
    ] = None,
    difficulty: Annotated[
        int | None,
        typer.Option("--difficulty", help="Filter by difficulty (1-10)"),
    ] = None,
) -> None:
    """List available challenges."""
    engine = ChallengeEngine()
    challenges = engine.list_all(category=category, difficulty=difficulty)

    if not challenges:
        rprint("[dim]No challenges found.[/]")
        return

    table = Table(title="Available Challenges")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Difficulty", justify="center")
    table.add_column("Category", style="green")

    for c in challenges:
        diff_color = "green" if c.difficulty <= 4 else "yellow" if c.difficulty <= 7 else "red"
        table.add_row(
            c.challenge_id,
            c.name,
            f"[{diff_color}]{c.difficulty}/10[/{diff_color}]",
            c.category,
        )

    rprint(table)


@arena_app.command()
def replay(
    match_id: Annotated[
        str,
        typer.Argument(help="Match ID to replay"),
    ],
) -> None:
    """Replay a completed match."""
    rprint(f"[bold cyan]Replay:[/] match {match_id}")
    rprint("[dim]Match replay not yet implemented — coming soon.[/]")
