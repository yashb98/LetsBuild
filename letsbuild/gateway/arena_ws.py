"""WebSocket manager for Arena tournament spectating."""

from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import WebSocket, WebSocketDisconnect

logger = structlog.get_logger()

# Graceful Redis import
try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    aioredis = None  # type: ignore[assignment]
    REDIS_AVAILABLE = False


class ArenaWebSocketManager:
    """Manages WebSocket connections for tournament spectating.

    Each tournament has its own connection pool. Events from Redis
    pub/sub are relayed to all connected WebSocket clients.
    """

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}
        self._log = logger.bind(component="arena_ws")

    async def connect(self, websocket: WebSocket, tournament_id: str) -> None:
        """Accept and register a WebSocket connection for a tournament."""
        await websocket.accept()
        if tournament_id not in self._connections:
            self._connections[tournament_id] = []
        self._connections[tournament_id].append(websocket)
        self._log.info(
            "ws_connected",
            tournament_id=tournament_id,
            total=len(self._connections[tournament_id]),
        )

    async def disconnect(self, websocket: WebSocket, tournament_id: str) -> None:
        """Remove a WebSocket connection from a tournament's pool."""
        if tournament_id in self._connections:
            conns = self._connections[tournament_id]
            if websocket in conns:
                conns.remove(websocket)
            if not conns:
                del self._connections[tournament_id]
        self._log.info("ws_disconnected", tournament_id=tournament_id)

    async def broadcast(self, tournament_id: str, data: dict[str, Any]) -> None:
        """Send data to all connected WebSocket clients for a tournament."""
        conns = self._connections.get(tournament_id, [])
        payload = json.dumps(data, default=str)
        disconnected: list[WebSocket] = []

        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            await self.disconnect(ws, tournament_id)

    async def relay_from_redis(
        self,
        tournament_id: str,
        redis_url: str = "redis://localhost:6379/0",
    ) -> None:
        """Subscribe to Redis channel and forward events to all connected WebSockets.

        Runs indefinitely until the Redis connection is lost or no clients remain.
        Falls back gracefully if Redis is unavailable.
        """
        if not REDIS_AVAILABLE or aioredis is None:
            self._log.warning("relay_skipped_no_redis")
            return

        try:
            client = aioredis.from_url(redis_url)
            pubsub = client.pubsub()
            channel = f"arena:{tournament_id}"
            await pubsub.subscribe(channel)  # type: ignore[misc,unused-ignore]

            self._log.info("relay_started", channel=channel)

            async for message in pubsub.listen():  # type: ignore[union-attr,unused-ignore]
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    await self.broadcast(tournament_id, data)

                # Stop if no more clients
                if not self._connections.get(tournament_id):
                    break

            await pubsub.unsubscribe(channel)  # type: ignore[misc,unused-ignore]
            await client.aclose()  # type: ignore[misc,unused-ignore]
        except Exception:
            self._log.warning("relay_failed", tournament_id=tournament_id, exc_info=True)

    def connection_count(self, tournament_id: str) -> int:
        """Return number of active connections for a tournament."""
        return len(self._connections.get(tournament_id, []))


# ---------------------------------------------------------------------------
# FastAPI endpoint factory
# ---------------------------------------------------------------------------

_ws_manager = ArenaWebSocketManager()


async def arena_websocket_endpoint(websocket: WebSocket, tournament_id: str) -> None:
    """FastAPI WebSocket endpoint for tournament spectating.

    Register with: app.websocket("/arena/ws/{tournament_id}")(arena_websocket_endpoint)
    """
    await _ws_manager.connect(websocket, tournament_id)
    try:
        while True:
            # Keep connection alive — client can send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        await _ws_manager.disconnect(websocket, tournament_id)
