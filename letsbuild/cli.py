"""LetsBuild CLI — Typer-based command interface for the autonomous portfolio factory."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import Annotated

import typer
from rich import print as rprint

from letsbuild import __version__

app = typer.Typer(
    name="letsbuild",
    help="LetsBuild — Autonomous Portfolio Factory. JD in, published GitHub repo out.",
)

memory_app = typer.Typer(
    name="memory",
    help="Memory + ReasoningBank queries and statistics.",
)
app.add_typer(memory_app, name="memory")


def _version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        rprint(f"[bold]letsbuild[/bold] v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            help="Show the application version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """LetsBuild — Autonomous Portfolio Factory."""


@app.command()
def ingest(
    url: Annotated[
        str | None,
        typer.Option("--url", help="URL of the job description to ingest."),
    ] = None,
    text: Annotated[
        str | None,
        typer.Option("--text", help="Raw job description text to ingest."),
    ] = None,
    file: Annotated[
        Path | None,
        typer.Option("--file", help="Path to a file containing the job description."),
    ] = None,
) -> None:
    """L1 Intake Engine — parse a job description into structured JDAnalysis."""
    if not any([url, text, file]):
        rprint("[bold red]Error:[/] Provide at least one of --url, --text, or --file.")
        raise typer.Exit(code=1)

    source = url or text or str(file)
    rprint(f"[bold cyan]Intake engine:[/] processing... [dim]({source})[/dim]")
    rprint("[bold green]\u2713 Command registered[/] \u2014 ingest not yet implemented")


@app.command()
def research(
    company: Annotated[
        str,
        typer.Option("--company", help="Company name to research."),
    ],
) -> None:
    """L2 Company Intelligence — run parallel research sub-agents on a company."""
    rprint(f"[bold cyan]Company Intelligence:[/] researching [bold]{company}[/bold]...")
    rprint("[bold green]\u2713 Command registered[/] \u2014 research not yet implemented")


@app.command()
def match(
    file: Annotated[
        Path,
        typer.Option("--file", help="Path to the JD file for gap analysis."),
    ],
) -> None:
    """L3 Match & Score Engine — compute 6-dimension match and gap analysis."""
    rprint(f"[bold cyan]Match & Score:[/] analysing [bold]{file}[/bold]...")
    rprint("[bold green]\u2713 Command registered[/] \u2014 match not yet implemented")


@app.command()
def architect(
    skill: Annotated[
        str,
        typer.Option("--skill", help="Skill name to load for project design."),
    ],
    jd: Annotated[
        Path,
        typer.Option("--jd", help="Path to the JD file or JDAnalysis JSON."),
    ],
) -> None:
    """L4 Project Architect — design a project spec from a skill and JD."""
    rprint(
        f"[bold cyan]Project Architect:[/] designing with skill "
        f"[bold]{skill}[/bold] from [bold]{jd}[/bold]..."
    )
    rprint("[bold green]\u2713 Command registered[/] \u2014 architect not yet implemented")


@app.command()
def forge(
    spec: Annotated[
        Path,
        typer.Option("--spec", help="Path to the ProjectSpec JSON file."),
    ],
) -> None:
    """L5 Code Forge — multi-agent sandboxed code generation from a ProjectSpec."""
    rprint(f"[bold cyan]Code Forge:[/] generating from [bold]{spec}[/bold]...")
    rprint("[bold green]\u2713 Command registered[/] \u2014 forge not yet implemented")


@app.command()
def publish(
    repo_name: Annotated[
        str,
        typer.Option("--repo-name", help="GitHub repository name to publish."),
    ],
) -> None:
    """L6 GitHub Publisher — publish generated project to GitHub with realistic commits."""
    rprint(f"[bold cyan]GitHub Publisher:[/] publishing to [bold]{repo_name}[/bold]...")
    rprint("[bold green]\u2713 Command registered[/] \u2014 publish not yet implemented")


@app.command()
def run(
    url: Annotated[
        str | None,
        typer.Option("--url", help="URL of the job description for full pipeline."),
    ] = None,
    file: Annotated[
        Path | None,
        typer.Option("--file", help="Path to a JD file for full pipeline."),
    ] = None,
) -> None:
    """Full pipeline — ingest a JD and run all layers (L1 through L7)."""
    if not any([url, file]):
        rprint("[bold red]Error:[/] Provide at least one of --url or --file.")
        raise typer.Exit(code=1)

    source = url or str(file)
    rprint(f"[bold cyan]Full Pipeline:[/] running all layers for [bold]{source}[/bold]...")
    rprint("[bold green]\u2713 Command registered[/] \u2014 run not yet implemented")


@app.command()
def status(
    thread_id: Annotated[
        str,
        typer.Option("--thread-id", help="Pipeline thread ID to check status for."),
    ],
) -> None:
    """Show pipeline status for a given thread ID."""
    rprint(f"[bold cyan]Pipeline Status:[/] checking thread [bold]{thread_id}[/bold]...")
    rprint("[bold green]\u2713 Command registered[/] \u2014 status not yet implemented")


@memory_app.command()
def query(
    text: Annotated[
        str,
        typer.Option("--text", help="Query text to search the ReasoningBank."),
    ],
) -> None:
    """Query the ReasoningBank for similar past patterns."""
    rprint(f"[bold cyan]Memory Query:[/] searching for [bold]{text}[/bold]...")
    rprint("[bold green]\u2713 Command registered[/] \u2014 memory query not yet implemented")


@memory_app.command()
def stats() -> None:
    """Show ReasoningBank statistics — record counts, JUDGE verdicts, DISTILL patterns."""
    rprint("[bold cyan]Memory Stats:[/] gathering statistics...")
    rprint("[bold green]\u2713 Command registered[/] \u2014 memory stats not yet implemented")


if __name__ == "__main__":
    app()
