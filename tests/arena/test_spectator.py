"""Tests for SpectatorEngine event streaming."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from letsbuild.arena.spectator import SpectatorEngine
from letsbuild.models.arena_models import ArenaAgentRole, TournamentPhase

# ---------------------------------------------------------------------------
# Emit Tests
# ---------------------------------------------------------------------------


class TestEmit:
    """Test SpectatorEngine.emit()."""

    @pytest.mark.asyncio()
    async def test_emit_serializes_event_to_json(self) -> None:
        engine = SpectatorEngine()

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        mock_redis.publish = AsyncMock()

        with patch.object(engine, "_get_redis", AsyncMock(return_value=mock_redis)):
            await engine.emit("t-1", {"type": "test", "data": 42})

        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        channel = call_args[0][0]
        payload = call_args[0][1]
        assert channel == "arena:t-1"
        parsed = json.loads(payload)
        assert parsed["type"] == "test"
        assert parsed["data"] == 42

    @pytest.mark.asyncio()
    async def test_emit_graceful_when_redis_unavailable(self) -> None:
        engine = SpectatorEngine()
        with patch.object(engine, "_get_redis", AsyncMock(return_value=None)):
            # Should not raise
            await engine.emit("t-1", {"type": "test"})


# ---------------------------------------------------------------------------
# Convenience Method Tests
# ---------------------------------------------------------------------------


class TestEmitAgentAction:
    """Test emit_agent_action includes timestamp."""

    @pytest.mark.asyncio()
    async def test_includes_timestamp(self) -> None:
        engine = SpectatorEngine()
        emitted_events: list[dict[str, object]] = []

        async def capture_emit(tournament_id: str, event: dict[str, object]) -> None:
            emitted_events.append(event)

        with patch.object(engine, "emit", AsyncMock(side_effect=capture_emit)):
            await engine.emit_agent_action(
                "t-1", "team-a", ArenaAgentRole.BUILDER, "write_file", "Created main.py"
            )

        assert len(emitted_events) == 1
        event = emitted_events[0]
        assert event["type"] == "agent_action"
        assert event["team_id"] == "team-a"
        assert event["role"] == "builder"
        assert "timestamp" in event

    @pytest.mark.asyncio()
    async def test_emit_phase_transition(self) -> None:
        engine = SpectatorEngine()
        emitted: list[dict[str, object]] = []

        async def capture(tid: str, event: dict[str, object]) -> None:
            emitted.append(event)

        with patch.object(engine, "emit", AsyncMock(side_effect=capture)):
            await engine.emit_phase_transition("t-1", TournamentPhase.BUILD, 1800)

        assert emitted[0]["type"] == "phase_transition"
        assert emitted[0]["phase"] == "build"
        assert emitted[0]["time_remaining"] == 1800

    @pytest.mark.asyncio()
    async def test_emit_score_update(self) -> None:
        engine = SpectatorEngine()
        emitted: list[dict[str, object]] = []

        async def capture(tid: str, event: dict[str, object]) -> None:
            emitted.append(event)

        with patch.object(engine, "emit", AsyncMock(side_effect=capture)):
            await engine.emit_score_update("t-1", "team-a", "functionality", 85.0)

        assert emitted[0]["type"] == "score_update"
        assert emitted[0]["score"] == 85.0


# ---------------------------------------------------------------------------
# Graceful Fallback Tests
# ---------------------------------------------------------------------------


class TestGracefulFallback:
    """Test SpectatorEngine works without Redis."""

    @pytest.mark.asyncio()
    async def test_get_redis_returns_none_when_unavailable(self) -> None:
        engine = SpectatorEngine()
        with patch("letsbuild.arena.spectator.REDIS_AVAILABLE", False):
            result = await engine._get_redis()
        assert result is None

    @pytest.mark.asyncio()
    async def test_emit_methods_no_raise_without_redis(self) -> None:
        engine = SpectatorEngine()
        with patch.object(engine, "_get_redis", AsyncMock(return_value=None)):
            await engine.emit("t-1", {"type": "test"})
            await engine.emit_agent_action(
                "t-1", "team-a", ArenaAgentRole.ARCHITECT, "plan", "Planning"
            )
            await engine.emit_phase_transition("t-1", TournamentPhase.PREP, 0)
            await engine.emit_score_update("t-1", "team-a", "quality", 50.0)
