"""Telegram bot gateway for the LetsBuild pipeline.

Provides a conversational interface: users send a JD URL, receive a match
score and ProjectSpec preview, approve or reject, and receive the published
repo link when done.

Bidirectional progress updates are pushed via ``send_notification`` which
calls the Telegram Bot API through httpx.

This module is a skeleton — webhook/polling registration will be wired in
a later step. The handler methods contain the full routing and response logic.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import httpx
import structlog

if TYPE_CHECKING:
    from letsbuild.pipeline.controller import PipelineController

__all__ = ["TelegramBot"]

logger = structlog.get_logger()

_TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"

# Simple URL detection regex
_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)

# Commands
_CMD_STATUS = "/status"
_CMD_APPROVE = "/approve"
_CMD_REJECT = "/reject"
_CMD_HELP = "/help"
_CMD_START = "/start"


class TelegramBot:
    """Bidirectional Telegram interface for the LetsBuild pipeline.

    Handles incoming messages from users and sends progress updates back.
    All Telegram API calls go through a single ``_post`` helper so they can
    be patched easily in tests.

    Args:
        bot_token: The Telegram Bot API token (``BOT_TOKEN`` env var).
        pipeline_controller: Optional pipeline controller instance. When
            ``None`` the bot operates in demo mode returning placeholder
            responses (useful for testing the routing logic without a real
            pipeline).
    """

    def __init__(
        self,
        bot_token: str,
        pipeline_controller: PipelineController | None = None,
    ) -> None:
        self._token = bot_token
        self._api_base = _TELEGRAM_API_BASE.format(token=bot_token)
        self._controller = pipeline_controller
        # In-memory store of active runs per chat: {chat_id: run_id}
        self._active_runs: dict[str, str] = {}
        self._log = structlog.get_logger(component="TelegramBot")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def handle_message(self, chat_id: str, text: str) -> str:
        """Route an incoming Telegram message to the appropriate handler.

        Args:
            chat_id: Telegram chat identifier (string representation).
            text: The raw message text from the user.

        Returns:
            The reply string that should be sent back to the user.
        """
        text = text.strip()

        if text.startswith(_CMD_START) or text.startswith(_CMD_HELP):
            return self._help_text()

        if text.startswith(_CMD_STATUS):
            return await self.handle_status(chat_id)

        if text.startswith(_CMD_APPROVE):
            parts = text.split(maxsplit=1)
            run_id = parts[1].strip() if len(parts) > 1 else self._active_runs.get(chat_id, "")
            return await self.handle_approve(chat_id, run_id)

        if text.startswith(_CMD_REJECT):
            parts = text.split(maxsplit=1)
            run_id = parts[1].strip() if len(parts) > 1 else self._active_runs.get(chat_id, "")
            return await self._handle_reject(chat_id, run_id)

        # If message contains a URL, treat it as a JD submission
        url_match = _URL_PATTERN.search(text)
        if url_match:
            return await self.handle_jd_url(chat_id, url_match.group(0))

        return (
            "I didn't understand that. Send me a job description URL to get started, "
            "or type /help for a list of commands."
        )

    async def handle_jd_url(self, chat_id: str, url: str) -> str:
        """Start a pipeline run for the given JD URL.

        Sends an acknowledgement message to the user, then kicks off ingestion
        in the background. Progress updates are pushed via ``send_notification``.

        Args:
            chat_id: Telegram chat identifier.
            url: The job description URL to process.

        Returns:
            Acknowledgement message string.
        """
        await self._log.ainfo("telegram_jd_url_received", chat_id=chat_id, url=url)

        if self._controller is not None:
            # Full pipeline integration — start async run and store run_id
            # TODO: wire up real pipeline_controller.start_run(jd_url=url) call
            run_id = "stub-run-id"  # placeholder until controller API is finalised
            self._active_runs[chat_id] = run_id
            return (
                f"Got it! I'm analysing the job description at:\n{url}\n\n"
                f"Run ID: `{run_id}`\n"
                "I'll send you updates as the pipeline progresses. "
                "This usually takes 5-15 minutes."
            )

        # Demo mode — no real pipeline
        demo_run_id = "demo-run-00000000"
        self._active_runs[chat_id] = demo_run_id
        return (
            f"[Demo mode] Received JD URL:\n{url}\n\n"
            f"Run ID: `{demo_run_id}`\n"
            "No pipeline controller configured — this is a stub response."
        )

    async def handle_status(self, chat_id: str) -> str:
        """Return the current pipeline run status for this chat.

        Args:
            chat_id: Telegram chat identifier.

        Returns:
            Human-readable status string.
        """
        run_id = self._active_runs.get(chat_id)
        if not run_id:
            return "No active pipeline run for this chat. Send a job description URL to start one."

        await self._log.ainfo("telegram_status_requested", chat_id=chat_id, run_id=run_id)

        if self._controller is not None:
            # TODO: fetch real status from pipeline_controller.get_status(run_id)
            return f"Run `{run_id}` is in progress (status integration pending)."

        return f"[Demo mode] Run `{run_id}` — status check stub."

    async def handle_approve(self, chat_id: str, run_id: str) -> str:
        """Approve a pending ProjectSpec so code generation can proceed.

        Args:
            chat_id: Telegram chat identifier.
            run_id: The pipeline run ID to approve.

        Returns:
            Confirmation message string.
        """
        if not run_id:
            return (
                "Please specify a run ID: /approve <run_id>\n"
                "Or just /approve if you have an active run."
            )

        await self._log.ainfo(
            "telegram_approve_requested", chat_id=chat_id, run_id=run_id, approved=True
        )

        if self._controller is not None:
            # TODO: call pipeline_controller.approve(run_id=run_id)
            return (
                f"ProjectSpec approved! Code generation is now underway for run `{run_id}`. "
                "I'll notify you when it's published to GitHub."
            )

        return f"[Demo mode] Approval recorded for run `{run_id}` (stub)."

    async def send_notification(self, chat_id: str, message: str) -> None:
        """Send a text notification to a Telegram chat.

        Calls the Telegram Bot API ``sendMessage`` method via httpx.
        Failures are logged as warnings — they must not crash the pipeline.

        Args:
            chat_id: Telegram chat identifier.
            message: The message text to send (Markdown V2 supported).
        """
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{self._api_base}/sendMessage", json=payload)
                response.raise_for_status()
                await self._log.ainfo(
                    "telegram_notification_sent",
                    chat_id=chat_id,
                    message_preview=message[:80],
                )
        except httpx.HTTPError as exc:
            await self._log.awarning(
                "telegram_notification_failed",
                chat_id=chat_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
        except Exception as exc:
            await self._log.awarning(
                "telegram_notification_unexpected_error",
                chat_id=chat_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _handle_reject(self, chat_id: str, run_id: str) -> str:
        """Reject a pending ProjectSpec and abort the run."""
        if not run_id:
            return (
                "Please specify a run ID: /reject <run_id>\n"
                "Or just /reject if you have an active run."
            )

        await self._log.ainfo(
            "telegram_reject_requested", chat_id=chat_id, run_id=run_id, approved=False
        )
        self._active_runs.pop(chat_id, None)

        if self._controller is not None:
            # TODO: call pipeline_controller.reject(run_id=run_id)
            return f"Run `{run_id}` has been aborted. Send a new JD URL to start again."

        return f"[Demo mode] Run `{run_id}` rejected (stub)."

    @staticmethod
    def _help_text() -> str:
        """Return the help message shown to new users."""
        return (
            "*LetsBuild Bot* — Autonomous Portfolio Factory\n\n"
            "Send me a job description URL and I'll build you a tailored GitHub repo.\n\n"
            "*Commands:*\n"
            "• Just paste a JD URL to start\n"
            "• /status — check your current run\n"
            "• /approve [run_id] — approve the project spec\n"
            "• /reject [run_id] — abort the current run\n"
            "• /help — show this message"
        )
