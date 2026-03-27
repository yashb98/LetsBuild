"""Context compression and management for Code Forge agents.

Implements PostToolUse trimming, structured case-facts blocks, and
conversation compression to keep agent context windows under budget.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger()

_TRIM_PLACEHOLDER = "... [trimmed {n} chars] ..."


class ContextManager:
    """Manages context window budget for Code Forge agents.

    Provides three complementary strategies from the architecture spec:
    1. **PostToolUse trimming** of verbose tool output.
    2. **Structured case-facts** block at context start.
    3. **Conversation compression** that keeps recent turns and summarises older ones.
    """

    def __init__(self, max_context_chars: int = 100_000) -> None:
        self.max_context_chars = max_context_chars
        self.log = structlog.get_logger(component="ContextManager")

    # ------------------------------------------------------------------
    # 1. PostToolUse trimming
    # ------------------------------------------------------------------

    def trim_tool_output(self, tool_output: str, max_chars: int = 5000) -> str:
        """Trim verbose tool output, keeping head and tail with a marker.

        If *tool_output* is already within *max_chars* it is returned unchanged.
        Otherwise the first ``max_chars // 2`` and last ``max_chars // 2``
        characters are kept with a trimmed-indicator in between.
        """
        if len(tool_output) <= max_chars:
            return tool_output

        half = max_chars // 2
        trimmed_count = len(tool_output) - max_chars
        placeholder = _TRIM_PLACEHOLDER.format(n=trimmed_count)
        result = tool_output[:half] + placeholder + tool_output[-half:]
        self.log.debug("tool_output_trimmed", original=len(tool_output), trimmed=len(result))
        return result

    # ------------------------------------------------------------------
    # 2. Structured case-facts block
    # ------------------------------------------------------------------

    def build_case_facts(
        self,
        project_spec_summary: str,
        current_task: str,
        relevant_code: str | None = None,
    ) -> str:
        """Build a position-aware case-facts block placed at context start.

        Key findings are ordered first so the model attends to them in the
        primacy region of the context window.
        """
        sections: list[str] = [
            "=== CASE FACTS ===",
            "",
            "## Current Task",
            current_task,
            "",
            "## Project Specification",
            project_spec_summary,
        ]

        if relevant_code is not None:
            sections.extend(["", "## Relevant Code", relevant_code])

        sections.append("")
        sections.append("=== END CASE FACTS ===")
        return "\n".join(sections)

    # ------------------------------------------------------------------
    # 3. Conversation compression
    # ------------------------------------------------------------------

    def compress_conversation(
        self,
        messages: list[dict[str, object]],
        keep_last_n: int = 10,
    ) -> list[dict[str, object]]:
        """Keep the system message and last *keep_last_n* messages.

        Older messages are replaced by a single summary message so the agent
        retains high-level awareness without consuming the full context budget.
        """
        if len(messages) <= keep_last_n + 1:
            # Nothing to compress (the +1 accounts for a possible system message).
            return list(messages)

        # Separate system message(s) from the rest.
        system_msgs: list[dict[str, object]] = []
        non_system: list[dict[str, object]] = []
        for msg in messages:
            if msg.get("role") == "system":
                system_msgs.append(msg)
            else:
                non_system.append(msg)

        if len(non_system) <= keep_last_n:
            return list(messages)

        older = non_system[:-keep_last_n]
        recent = non_system[-keep_last_n:]

        summary_text = self._summarise_messages(older)
        summary_msg: dict[str, object] = {
            "role": "user",
            "content": f"[Compressed context from {len(older)} earlier messages]\n{summary_text}",
        }

        return [*system_msgs, summary_msg, *recent]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _summarise_messages(messages: list[dict[str, object]]) -> str:
        """Produce a brief textual summary of *messages*."""
        role_counts: dict[str, int] = {}
        for msg in messages:
            role = str(msg.get("role", "unknown"))
            role_counts[role] = role_counts.get(role, 0) + 1

        parts = [f"{count} {role} message(s)" for role, count in role_counts.items()]
        return "Earlier conversation contained: " + ", ".join(parts) + "."
