# Phase G: CLI + Gateway

## Goal
Add arena CLI commands and register the WebSocket endpoint.

## Pre-read
- `letsbuild/cli.py` — existing Typer CLI to extend
- `letsbuild/gateway/mcp_server.py` — existing FastAPI app to add WS endpoint
- `letsbuild/gateway/arena_ws.py` — your Phase D WebSocket handler

## Files to Create/Modify

### 1. `letsbuild/arena/cli.py`

Create a Typer sub-app for arena commands:

```python
import typer
arena_app = typer.Typer(name="arena", help="AgentForge Arena — competitive agent tournaments")

@arena_app.command()
def duel(
    challenge: str = typer.Argument(help="Challenge ID from skills/challenges/"),
    team_a_model: str = typer.Option("claude-sonnet-4-6", help="Model for Team Alpha"),
    team_b_model: str = typer.Option("claude-sonnet-4-6", help="Model for Team Beta"),
    build_time: int = typer.Option(5400, help="Build phase time in seconds"),
) -> None:
    """Run a duel between two agent teams."""
    # 1. Build TeamConfigs with 5 agents each (architect, builder, frontend, tester, critic)
    # 2. Load challenge via ChallengeEngine
    # 3. Create TournamentState
    # 4. asyncio.run(TournamentController().run_tournament(state))
    # 5. Print results table with Rich

@arena_app.command()
def leaderboard(top: int = typer.Option(20, help="Number of entries")) -> None:
    """Show the ELO leaderboard."""
    # Load from SQLite/JSON, print with Rich table

@arena_app.command()
def challenges(category: str | None = typer.Option(None), difficulty: int | None = typer.Option(None)) -> None:
    """List available challenges."""
    # ChallengeEngine.list_all(), print with Rich table

@arena_app.command()
def replay(match_id: str = typer.Argument(help="Match ID to replay")) -> None:
    """Replay a completed match."""
    # Load match from storage, print phase-by-phase summary
```

### 2. Modify `letsbuild/cli.py`

Add one line to register the arena sub-app:
```python
from letsbuild.arena.cli import arena_app
app.add_typer(arena_app)
```

### 3. Modify `letsbuild/gateway/mcp_server.py`

Add WebSocket route:
```python
from letsbuild.gateway.arena_ws import ArenaWebSocketManager, arena_websocket_endpoint
# Add: app.websocket("/arena/ws/{tournament_id}")(arena_websocket_endpoint)
```

### 4. Integration Test

`tests/arena/test_integration.py`:
- Test full duel flow end-to-end with mocked LLM + mocked sandbox
- Test CLI command invocation via Typer testing runner
- Verify TournamentState transitions PREP → ... → COMPLETE
- Verify MatchResult has winner and scores

## Verification
```bash
ruff check letsbuild/arena/cli.py --fix && ruff format .
python -m letsbuild arena challenges --help  # verify CLI works
pytest tests/arena/test_integration.py -v
```
