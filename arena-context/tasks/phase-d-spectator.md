# Phase D: Spectator + Streaming

## Goal
Build real-time event streaming for spectators watching tournaments.

## Pre-read
- `letsbuild/gateway/mcp_server.py` — existing FastAPI app to add WebSocket endpoint to
- `letsbuild/models/arena_models.py` — TournamentPhase, ArenaAgentRole

## Files to Create

### 1. `letsbuild/arena/spectator.py`

```python
class SpectatorEngine:
    """Publishes tournament events to Redis pub/sub for WebSocket relay."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis_url = redis_url
        self._log = structlog.get_logger()

    async def emit(self, tournament_id: str, event: dict) -> None:
        """Publish event dict to Redis channel 'arena:{tournament_id}'."""

    async def emit_agent_action(self, tournament_id: str, team_id: str,
                                 role: ArenaAgentRole, action: str, details: str) -> None:
        """Convenience: emit agent action event with timestamp."""

    async def emit_phase_transition(self, tournament_id: str,
                                     phase: TournamentPhase, time_remaining: int) -> None:
        """Convenience: emit phase change event."""

    async def emit_score_update(self, tournament_id: str, team_id: str,
                                 dimension: str, score: float) -> None:
        """Convenience: emit real-time score update."""
```

Use `redis.asyncio` for async Redis. Fallback gracefully if Redis unavailable (log warning, skip emit).

### 2. `letsbuild/gateway/arena_ws.py`

```python
from fastapi import WebSocket, WebSocketDisconnect

class ArenaWebSocketManager:
    """Manages WebSocket connections for tournament spectating."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}  # tournament_id → connections

    async def connect(self, websocket: WebSocket, tournament_id: str) -> None: ...
    async def disconnect(self, websocket: WebSocket, tournament_id: str) -> None: ...
    async def relay_from_redis(self, tournament_id: str) -> None:
        """Subscribe to Redis channel and forward to all connected WebSockets."""

# FastAPI endpoint to register in mcp_server.py:
# @app.websocket("/arena/ws/{tournament_id}")
# async def arena_ws(websocket: WebSocket, tournament_id: str): ...
```

### 3. Tests

`tests/arena/test_spectator.py`:
- Test emit() serializes event to JSON
- Test emit_agent_action includes timestamp
- Test graceful fallback when Redis unavailable

`tests/arena/test_arena_ws.py`:
- Test WebSocket connect/disconnect lifecycle
- Test multiple connections per tournament

## Verification
```bash
ruff check letsbuild/arena/spectator.py letsbuild/gateway/arena_ws.py --fix && ruff format .
pytest tests/arena/test_spectator.py -v
```
