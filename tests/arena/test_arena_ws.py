"""Tests for ArenaWebSocketManager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from letsbuild.gateway.arena_ws import ArenaWebSocketManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_websocket() -> MagicMock:
    """Create a mock WebSocket that tracks accept/send/receive calls."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.receive_text = AsyncMock(return_value="ping")
    return ws


# ---------------------------------------------------------------------------
# Connection Lifecycle Tests
# ---------------------------------------------------------------------------


class TestConnectionLifecycle:
    """Test WebSocket connect/disconnect."""

    @pytest.mark.asyncio()
    async def test_connect_accepts_websocket(self) -> None:
        manager = ArenaWebSocketManager()
        ws = _make_mock_websocket()
        await manager.connect(ws, "t-1")
        ws.accept.assert_called_once()

    @pytest.mark.asyncio()
    async def test_connect_tracks_connection(self) -> None:
        manager = ArenaWebSocketManager()
        ws = _make_mock_websocket()
        await manager.connect(ws, "t-1")
        assert manager.connection_count("t-1") == 1

    @pytest.mark.asyncio()
    async def test_disconnect_removes_connection(self) -> None:
        manager = ArenaWebSocketManager()
        ws = _make_mock_websocket()
        await manager.connect(ws, "t-1")
        await manager.disconnect(ws, "t-1")
        assert manager.connection_count("t-1") == 0

    @pytest.mark.asyncio()
    async def test_disconnect_nonexistent_is_safe(self) -> None:
        manager = ArenaWebSocketManager()
        ws = _make_mock_websocket()
        # Should not raise
        await manager.disconnect(ws, "nonexistent")


# ---------------------------------------------------------------------------
# Multiple Connections Tests
# ---------------------------------------------------------------------------


class TestMultipleConnections:
    """Test multiple connections per tournament."""

    @pytest.mark.asyncio()
    async def test_multiple_connections_same_tournament(self) -> None:
        manager = ArenaWebSocketManager()
        ws1 = _make_mock_websocket()
        ws2 = _make_mock_websocket()
        ws3 = _make_mock_websocket()

        await manager.connect(ws1, "t-1")
        await manager.connect(ws2, "t-1")
        await manager.connect(ws3, "t-1")

        assert manager.connection_count("t-1") == 3

    @pytest.mark.asyncio()
    async def test_connections_across_tournaments(self) -> None:
        manager = ArenaWebSocketManager()
        ws1 = _make_mock_websocket()
        ws2 = _make_mock_websocket()

        await manager.connect(ws1, "t-1")
        await manager.connect(ws2, "t-2")

        assert manager.connection_count("t-1") == 1
        assert manager.connection_count("t-2") == 1

    @pytest.mark.asyncio()
    async def test_broadcast_sends_to_all(self) -> None:
        manager = ArenaWebSocketManager()
        ws1 = _make_mock_websocket()
        ws2 = _make_mock_websocket()

        await manager.connect(ws1, "t-1")
        await manager.connect(ws2, "t-1")

        await manager.broadcast("t-1", {"type": "test"})

        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_broadcast_removes_failed_connections(self) -> None:
        manager = ArenaWebSocketManager()
        ws_good = _make_mock_websocket()
        ws_bad = _make_mock_websocket()
        ws_bad.send_text = AsyncMock(side_effect=RuntimeError("connection closed"))

        await manager.connect(ws_good, "t-1")
        await manager.connect(ws_bad, "t-1")

        await manager.broadcast("t-1", {"type": "test"})

        # Bad connection should be removed
        assert manager.connection_count("t-1") == 1
