"""Tests for the independent Reviewer agent."""

from __future__ import annotations

from letsbuild.forge.agents.reviewer import ReviewerAgent, ReviewResult
from letsbuild.models.forge_models import CodeModule, ReviewVerdict


def test_reviewer_has_read_only_tools() -> None:
    """Reviewer must only have read_file and list_directory — no write access."""
    reviewer = ReviewerAgent(llm_client=None)
    tool_names = [str(t["name"]) for t in reviewer.tools()]
    assert tool_names == ["read_file", "list_directory"]
    assert "write_file" not in tool_names
    assert "bash_execute" not in tool_names


def test_reviewer_heuristic_nonempty_code_passes() -> None:
    """Non-empty code modules should pass the heuristic review."""
    reviewer = ReviewerAgent(llm_client=None)
    modules = [
        CodeModule(
            module_path="src/app.py",
            content='"""App module."""\n\ndef main() -> str:\n    return "hello"\n',
            language="python",
            loc=4,
        ),
        CodeModule(
            module_path="tests/test_app.py",
            content='"""Tests."""\n\ndef test_main() -> None:\n    assert True\n',
            language="python",
            loc=4,
            test_file_path="tests/test_app.py",
        ),
    ]
    result = reviewer._review_heuristic(modules)

    assert result.verdict == ReviewVerdict.PASS_WITH_SUGGESTIONS
    assert result.score > 0.0
    assert len(result.blocking_issues) == 0


def test_reviewer_heuristic_empty_code_fails() -> None:
    """Empty code modules should fail the heuristic review."""
    reviewer = ReviewerAgent(llm_client=None)
    # Completely empty submission
    result_empty = reviewer._review_heuristic([])
    assert result_empty.verdict == ReviewVerdict.FAIL
    assert result_empty.score == 0.0
    assert len(result_empty.blocking_issues) > 0

    # Modules with empty content
    modules_blank = [
        CodeModule(
            module_path="src/blank.py",
            content="   ",
            language="python",
            loc=0,
        ),
    ]
    result_blank = reviewer._review_heuristic(modules_blank)
    assert result_blank.verdict == ReviewVerdict.FAIL
    assert result_blank.score <= 30.0


def test_review_result_has_verdict_and_score() -> None:
    """ReviewResult dataclass must have verdict, score, comments, blocking_issues."""
    result = ReviewResult(
        verdict=ReviewVerdict.PASS,
        score=85.0,
        comments=["Looks good overall."],
        blocking_issues=[],
    )
    assert result.verdict == ReviewVerdict.PASS
    assert result.score == 85.0
    assert len(result.comments) == 1
    assert isinstance(result.blocking_issues, list)
