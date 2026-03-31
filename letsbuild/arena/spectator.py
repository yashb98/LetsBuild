"""Real-time event streaming for Arena tournament spectators."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from letsbuild.models.arena_models import ArenaAgentRole, TournamentPhase

logger = structlog.get_logger()

# Graceful Redis import — code remains importable without redis.
try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    aioredis = None  # type: ignore[assignment]
    REDIS_AVAILABLE = False


class SpectatorEngine:
    """Publishes tournament events to Redis pub/sub for WebSocket relay.

    Falls back gracefully if Redis is unavailable — logs a warning and
    skips emitting. This means spectator features are optional.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis_url = redis_url
        self._redis: Any | None = None
        self._log = logger.bind(component="spectator")

    async def _get_redis(self) -> Any | None:
        """Return a cached async Redis connection, or None if unavailable."""
        if not REDIS_AVAILABLE:
            return None

        if self._redis is None:
            try:
                self._redis = aioredis.from_url(self._redis_url)  # type: ignore[union-attr,unused-ignore]
                await self._redis.ping()  # type: ignore[misc,unused-ignore]
            except Exception:
                self._log.warning(
                    "redis_unavailable",
                    url=self._redis_url,
                    exc_info=True,
                )
                self._redis = None
        return self._redis

    async def emit(self, tournament_id: str, event: dict[str, Any]) -> None:
        """Publish event dict to Redis channel 'arena:{tournament_id}'.

        Serializes event to JSON before publishing. Falls back gracefully
        if Redis is unavailable.
        """
        redis = await self._get_redis()
        if redis is None:
            self._log.debug("emit_skipped_no_redis", tournament_id=tournament_id)
            return

        channel = f"arena:{tournament_id}"
        payload = json.dumps(event, default=str)

        try:
            await redis.publish(channel, payload)
            self._log.debug("event_emitted", channel=channel, event_type=event.get("type"))
        except Exception:
            self._log.warning("emit_failed", channel=channel, exc_info=True)

    async def emit_agent_action(
        self,
        tournament_id: str,
        team_id: str,
        role: ArenaAgentRole,
        action: str,
        details: str,
    ) -> None:
        """Emit an agent action event with timestamp."""
        await self.emit(
            tournament_id,
            {
                "type": "agent_action",
                "team_id": team_id,
                "role": str(role),
                "action": action,
                "details": details,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    async def emit_phase_transition(
        self,
        tournament_id: str,
        phase: TournamentPhase,
        time_remaining: int,
    ) -> None:
        """Emit a phase change event."""
        await self.emit(
            tournament_id,
            {
                "type": "phase_transition",
                "phase": str(phase),
                "time_remaining": time_remaining,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    async def emit_score_update(
        self,
        tournament_id: str,
        team_id: str,
        dimension: str,
        score: float,
    ) -> None:
        """Emit a real-time score update event."""
        await self.emit(
            tournament_id,
            {
                "type": "score_update",
                "team_id": team_id,
                "dimension": dimension,
                "score": score,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
