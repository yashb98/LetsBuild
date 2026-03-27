"""Tests for the ContextManager (forge context compression)."""

from __future__ import annotations

from letsbuild.forge.context import ContextManager


def _make_manager() -> ContextManager:
    return ContextManager(max_context_chars=100_000)


# ------------------------------------------------------------------
# trim_tool_output
# ------------------------------------------------------------------


def test_trim_short_output_unchanged() -> None:
    """Output shorter than max_chars should be returned unchanged."""
    mgr = _make_manager()
    short = "hello world"
    assert mgr.trim_tool_output(short, max_chars=5000) == short


def test_trim_long_output_truncated() -> None:
    """Output exceeding max_chars should be trimmed with a marker."""
    mgr = _make_manager()
    long_text = "x" * 10_000
    result = mgr.trim_tool_output(long_text, max_chars=200)
    assert "trimmed" in result
    assert len(result) < len(long_text)


# ------------------------------------------------------------------
# build_case_facts
# ------------------------------------------------------------------


def test_build_case_facts_nonempty() -> None:
    """Case facts block should contain the task and spec summary."""
    mgr = _make_manager()
    facts = mgr.build_case_facts(
        project_spec_summary="Build a REST API",
        current_task="Implement /users endpoint",
    )
    assert "CASE FACTS" in facts
    assert "Implement /users endpoint" in facts
    assert "Build a REST API" in facts


# ------------------------------------------------------------------
# compress_conversation
# ------------------------------------------------------------------


def test_compress_conversation_keeps_recent() -> None:
    """Only the system message and last N messages should be retained."""
    mgr = _make_manager()
    messages: list[dict[str, object]] = [
        {"role": "system", "content": "You are a coder."},
    ]
    for i in range(20):
        messages.append({"role": "user", "content": f"msg-{i}"})

    compressed = mgr.compress_conversation(messages, keep_last_n=5)

    # system + summary + last 5
    assert len(compressed) == 7
    assert compressed[0]["role"] == "system"
    assert "Compressed context" in str(compressed[1]["content"])
    assert compressed[-1]["content"] == "msg-19"
