"""NotificationDispatch middleware — push real-time pipeline progress to configured channels.

Stage 8 in the 10-stage middleware chain.  Sends non-blocking notifications to
Telegram, Slack, Discord, and WebSocket channels as layers start and complete.
Failures in any channel are logged as warnings and never propagate to the pipeline.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import structlog

from letsbuild.harness.middleware import Middleware

if TYPE_CHECKING:
    from letsbuild.pipeline.state import PipelineState

__all__ = [
    "LogChannel",
    "NotificationChannel",
    "NotificationDispatchMiddleware",
    "TelegramChannel",
    "WebSocketChannel",
]

logger = structlog.get_logger()

# Human-readable layer names used in notification messages
_LAYER_NAMES: dict[int, str] = {
    0: "Agent Harness",
    1: "Intake Engine",
    2: "Company Intelligence",
    3: "Match & Score",
    4: "Project Architect",
    5: "Code Forge",
    6: "GitHub Publisher",
    7: "Content Factory",
    8: "Memory + ReasoningBank",
    9: "Agent Hooks",
}


# ---------------------------------------------------------------------------
# Channel protocol / base class
# ---------------------------------------------------------------------------


class NotificationChannel(ABC):
    """Abstract base class for notification channel implementations.

    Each channel handles the transport details for a single destination
    (Telegram, Slack, Discord, WebSocket, log sink, etc.).
    """

    @abstractmethod
    async def send(self, message: str, metadata: dict[str, Any] | None = None) -> None:
        """Send a notification message over this channel.

        Args:
            message: Human-readable notification text.
            metadata: Optional extra data (e.g. run_id, layer number) for
                structured logging or rich message formatting.
        """
        ...

    @property
    def name(self) -> str:
        """Human-readable channel name."""
        return self.__class__.__name__


# ---------------------------------------------------------------------------
# Built-in channel implementations
# ---------------------------------------------------------------------------


class LogChannel(NotificationChannel):
    """Default notification channel — writes to structlog.

    Always present; provides an audit trail even when no external channels
    are configured.
    """

    async def send(self, message: str, metadata: dict[str, Any] | None = None) -> None:
        """Log the notification via structlog.

        Args:
            message: Notification text.
            metadata: Optional key/value pairs appended to the log entry.
        """
        await logger.ainfo(
            "notification_dispatched",
            channel="log",
            message=message,
            **(metadata or {}),
        )


class TelegramChannel(NotificationChannel):
    """Stub notification channel for Telegram.

    Delegates to a ``TelegramBot.send_notification`` call if a bot instance
    is provided; otherwise falls back to structured logging.  The full
    implementation is wired up in ``letsbuild/gateway/telegram_bot.py``.
    """

    def __init__(self, chat_id: str, bot: Any | None = None) -> None:
        """Initialise the Telegram channel.

        Args:
            chat_id: The Telegram chat ID to send notifications to.
            bot: Optional ``TelegramBot`` instance. When ``None`` the channel
                operates in stub mode and logs instead of sending.
        """
        self._chat_id = chat_id
        self._bot = bot

    async def send(self, message: str, metadata: dict[str, Any] | None = None) -> None:
        """Send a notification to the configured Telegram chat.

        Args:
            message: Notification text.
            metadata: Unused in Telegram; kept for interface compatibility.
        """
        if self._bot is not None:
            await self._bot.send_notification(self._chat_id, message)
        else:
            await logger.ainfo(
                "notification_dispatched",
                channel="telegram_stub",
                chat_id=self._chat_id,
                message=message,
                **(metadata or {}),
            )


class WebSocketChannel(NotificationChannel):
    """Stub notification channel for WebSocket connections.

    A real implementation would hold a ``websockets.WebSocketServerProtocol``
    reference and call ``ws.send(json.dumps({...}))``. This stub logs instead
    so the middleware chain works end-to-end without a live WebSocket server.
    """

    def __init__(self, connection_id: str, websocket: Any | None = None) -> None:
        """Initialise the WebSocket channel.

        Args:
            connection_id: Unique identifier for the WebSocket connection.
            websocket: Optional live WebSocket connection object. When ``None``
                the channel operates in stub mode.
        """
        self._connection_id = connection_id
        self._ws = websocket

    async def send(self, message: str, metadata: dict[str, Any] | None = None) -> None:
        """Send a notification over the WebSocket connection.

        Args:
            message: Notification text.
            metadata: Optional structured data to include in the JSON payload.
        """
        if self._ws is not None:
            import json

            payload = {"message": message, **(metadata or {})}
            await self._ws.send(json.dumps(payload))
        else:
            await logger.ainfo(
                "notification_dispatched",
                channel="websocket_stub",
                connection_id=self._connection_id,
                message=message,
                **(metadata or {}),
            )


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class NotificationDispatchMiddleware(Middleware):
    """Send pipeline progress notifications to all configured channels.

    Stage 8 in the 10-stage middleware chain.

    ``before()``:  Fires a "Starting layer N" notification.
    ``after()``:   Fires a "Completed layer N" notification with a short
                   summary.  If the state has accumulated errors, those are
                   included in the notification.

    All ``channel.send()`` calls are wrapped in ``asyncio.create_task`` so
    slow or failing channels never block the pipeline.  Failures are caught
    and logged as warnings.

    Args:
        channels: List of ``NotificationChannel`` instances to dispatch to.
            If ``None`` or empty, a single ``LogChannel`` is used as the
            default so there is always at least one audit trail.
    """

    def __init__(self, channels: list[NotificationChannel] | None = None) -> None:
        self._channels: list[NotificationChannel] = channels or [LogChannel()]
        self._log = structlog.get_logger(component="NotificationDispatchMiddleware")

    async def before(self, state: PipelineState) -> PipelineState:
        """Send "Starting layer N" notification to all channels.

        Args:
            state: Current pipeline state.

        Returns:
            Unchanged pipeline state (notifications are purely side-effects).
        """
        layer_name = _LAYER_NAMES.get(state.current_layer, f"Layer {state.current_layer}")
        message = f"[{state.thread_id[:8]}] Starting {layer_name} (L{state.current_layer})…"
        metadata: dict[str, Any] = {
            "thread_id": state.thread_id,
            "layer": state.current_layer,
            "event": "layer_start",
        }
        await self._dispatch(message, metadata)
        return state

    async def after(self, state: PipelineState) -> PipelineState:
        """Send "Completed layer N" notification with optional error summary.

        Args:
            state: Current pipeline state (with layer results populated).

        Returns:
            Unchanged pipeline state.
        """
        layer_name = _LAYER_NAMES.get(state.current_layer, f"Layer {state.current_layer}")
        error_count = len(state.errors)

        if error_count == 0:
            status_text = "Completed"
        elif error_count < 3:
            status_text = f"Completed with {error_count} error(s)"
        else:
            status_text = "FAILED (pipeline aborting)"

        message = f"[{state.thread_id[:8]}] {status_text}: {layer_name} (L{state.current_layer})"

        if error_count > 0:
            # Append a brief error summary (categories only, not full tracebacks)
            categories = ", ".join(
                {e.error_category for e in state.errors[-3:]}  # last 3 errors
            )
            message += f"\n  Errors: {categories}"

        metadata: dict[str, Any] = {
            "thread_id": state.thread_id,
            "layer": state.current_layer,
            "event": "layer_complete",
            "error_count": error_count,
        }
        await self._dispatch(message, metadata)
        return state

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _dispatch(self, message: str, metadata: dict[str, Any]) -> None:
        """Fire-and-forget: schedule send on all channels via create_task.

        Each channel runs in its own task so failures are isolated.

        Args:
            message: Notification text.
            metadata: Structured metadata passed to each channel.
        """
        for channel in self._channels:
            asyncio.create_task(  # noqa: RUF006 (fire-and-forget is intentional)
                self._safe_send(channel, message, metadata),
                name=f"notify_{channel.name}",
            )

    async def _safe_send(
        self,
        channel: NotificationChannel,
        message: str,
        metadata: dict[str, Any],
    ) -> None:
        """Send to a single channel, swallowing all exceptions.

        Args:
            channel: The target channel.
            message: Notification text.
            metadata: Structured metadata.
        """
        try:
            await channel.send(message, metadata)
        except Exception as exc:
            await self._log.awarning(
                "notification_channel_error",
                channel=channel.name,
                error=str(exc),
                error_type=type(exc).__name__,
                message_preview=message[:80],
            )
