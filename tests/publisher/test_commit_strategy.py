"""Tests for CommitStrategyEngine — multi-phase commit plan generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from letsbuild.models.publisher_models import CommitPhase
from letsbuild.publisher.commit_strategy import CommitStrategyEngine

if TYPE_CHECKING:
    from letsbuild.models.architect_models import ProjectSpec
    from letsbuild.models.forge_models import ForgeOutput

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Conventional Commits prefixes we expect to appear in messages
_CONVENTIONAL_PREFIXES = ("feat", "fix", "docs", "chore", "test", "ci", "refactor", "style")


def _is_conventional_commit(message: str) -> bool:
    """Return True if the message starts with a conventional-commit prefix."""
    lower = message.lower()
    return any(lower.startswith(prefix) for prefix in _CONVENTIONAL_PREFIXES)


# ---------------------------------------------------------------------------
# Basic plan generation
# ---------------------------------------------------------------------------


def test_generate_plan_returns_commit_plan(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """generate_plan should return a CommitPlan with commits and metadata."""
    engine = CommitStrategyEngine(spread_days=3, seed=42)
    plan = engine.generate_plan(sample_project_spec, sample_forge_output)

    assert plan.total_commits == len(plan.commits)
    assert plan.total_commits > 0
    assert plan.spread_days == 3


def test_generate_plan_produces_at_least_two_commits(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """Even with minimal input there should be at least 2 commits (bootstrap + POLISH)."""
    engine = CommitStrategyEngine(spread_days=3, seed=1)
    plan = engine.generate_plan(sample_project_spec, sample_forge_output)

    assert plan.total_commits >= 2


def test_generate_plan_always_ends_with_polish_commit(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """The last commit in the plan MUST be a POLISH entry."""
    engine = CommitStrategyEngine(spread_days=5, seed=99)
    plan = engine.generate_plan(sample_project_spec, sample_forge_output)

    last = plan.commits[-1]
    assert last.phase == CommitPhase.POLISH


def test_generate_plan_commit_count_matches_total_commits_field(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """total_commits must equal len(commits)."""
    engine = CommitStrategyEngine(spread_days=5, seed=7)
    plan = engine.generate_plan(sample_project_spec, sample_forge_output)

    assert plan.total_commits == len(plan.commits)


# ---------------------------------------------------------------------------
# Phase coverage
# ---------------------------------------------------------------------------


def test_generate_plan_includes_scaffolding_phase_when_pyproject_present(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """A pyproject.toml module should produce a SCAFFOLDING phase commit."""
    engine = CommitStrategyEngine(spread_days=5, seed=0)
    plan = engine.generate_plan(sample_project_spec, sample_forge_output)

    phases = {entry.phase for entry in plan.commits}
    assert CommitPhase.SCAFFOLDING in phases


def test_generate_plan_includes_tests_phase_when_test_files_present(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """test_api.py should produce a TESTS phase commit."""
    engine = CommitStrategyEngine(spread_days=5, seed=0)
    plan = engine.generate_plan(sample_project_spec, sample_forge_output)

    phases = {entry.phase for entry in plan.commits}
    assert CommitPhase.TESTS in phases


def test_generate_plan_includes_ci_cd_phase_when_workflow_present(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """A .github/workflows file should produce a CI_CD phase commit."""
    engine = CommitStrategyEngine(spread_days=5, seed=0)
    plan = engine.generate_plan(sample_project_spec, sample_forge_output)

    phases = {entry.phase for entry in plan.commits}
    assert CommitPhase.CI_CD in phases


def test_generate_plan_includes_adrs_phase_when_adr_list_non_empty(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """A non-empty adr_list should produce an ADRS phase commit."""
    assert len(sample_project_spec.adr_list) > 0
    engine = CommitStrategyEngine(spread_days=5, seed=0)
    plan = engine.generate_plan(sample_project_spec, sample_forge_output)

    phases = {entry.phase for entry in plan.commits}
    assert CommitPhase.ADRS in phases


def test_generate_plan_includes_core_modules_phase(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """src/main.py and src/api.py should be classified as CORE_MODULES."""
    engine = CommitStrategyEngine(spread_days=5, seed=0)
    plan = engine.generate_plan(sample_project_spec, sample_forge_output)

    phases = {entry.phase for entry in plan.commits}
    assert CommitPhase.CORE_MODULES in phases


# ---------------------------------------------------------------------------
# Conventional Commit messages
# ---------------------------------------------------------------------------


def test_all_commit_messages_follow_conventional_format(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """Every commit message should begin with a valid Conventional Commits prefix."""
    engine = CommitStrategyEngine(spread_days=5, seed=42)
    plan = engine.generate_plan(sample_project_spec, sample_forge_output)

    for entry in plan.commits:
        assert _is_conventional_commit(entry.message), (
            f"Non-conventional commit message: {entry.message!r}"
        )


def test_scaffolding_commit_uses_feat_prefix(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """The SCAFFOLDING commit should use 'feat: scaffold...' message."""
    engine = CommitStrategyEngine(spread_days=5, seed=0)
    plan = engine.generate_plan(sample_project_spec, sample_forge_output)

    scaffolding_commits = [e for e in plan.commits if e.phase == CommitPhase.SCAFFOLDING]
    assert len(scaffolding_commits) > 0
    for entry in scaffolding_commits:
        assert entry.message.startswith("feat:"), f"Expected 'feat:' prefix, got: {entry.message}"


def test_ci_cd_commit_uses_ci_prefix(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """The CI_CD commit should use 'ci:' prefix."""
    engine = CommitStrategyEngine(spread_days=5, seed=0)
    plan = engine.generate_plan(sample_project_spec, sample_forge_output)

    ci_commits = [e for e in plan.commits if e.phase == CommitPhase.CI_CD]
    assert len(ci_commits) > 0
    for entry in ci_commits:
        assert entry.message.startswith("ci:"), f"Expected 'ci:' prefix, got: {entry.message}"


def test_adr_commit_message_contains_adr_title(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """ADR commit messages should reference the ADR title."""
    engine = CommitStrategyEngine(spread_days=5, seed=0)
    plan = engine.generate_plan(sample_project_spec, sample_forge_output)

    adr_commits = [e for e in plan.commits if e.phase == CommitPhase.ADRS]
    assert len(adr_commits) > 0
    # The first ADR title is "Use FastAPI for REST API"
    combined = " ".join(e.message for e in adr_commits)
    assert "FastAPI" in combined or "ADR" in combined


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------


def test_timestamps_are_monotonically_increasing(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """timestamp_offset_hours must be strictly increasing across commits."""
    engine = CommitStrategyEngine(spread_days=5, seed=42)
    plan = engine.generate_plan(sample_project_spec, sample_forge_output)

    offsets = [e.timestamp_offset_hours for e in plan.commits]
    for i in range(1, len(offsets)):
        assert offsets[i] > offsets[i - 1], (
            f"Timestamp not monotonically increasing at index {i}: {offsets[i - 1]} -> {offsets[i]}"
        )


def test_timestamps_spread_across_configured_days(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """The span of timestamp offsets should be consistent with spread_days."""
    spread_days = 5
    engine = CommitStrategyEngine(spread_days=spread_days, seed=42)
    plan = engine.generate_plan(sample_project_spec, sample_forge_output)

    offsets = [e.timestamp_offset_hours for e in plan.commits]
    total_span_hours = offsets[-1] - offsets[0]

    # Span should not exceed the configured working hours across spread_days
    # (at most spread_days * 24 hours)
    assert total_span_hours <= spread_days * 24


def test_timestamps_all_positive(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """All timestamp offsets must be positive (start ≥ 0 from base time)."""
    engine = CommitStrategyEngine(spread_days=3, seed=1)
    plan = engine.generate_plan(sample_project_spec, sample_forge_output)

    for entry in plan.commits:
        assert entry.timestamp_offset_hours >= 0


# ---------------------------------------------------------------------------
# Deterministic output with same seed
# ---------------------------------------------------------------------------


def test_same_seed_produces_identical_plans(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """Two engines with the same seed should produce identical commit plans."""
    engine_a = CommitStrategyEngine(spread_days=5, seed=123)
    engine_b = CommitStrategyEngine(spread_days=5, seed=123)

    plan_a = engine_a.generate_plan(sample_project_spec, sample_forge_output)
    plan_b = engine_b.generate_plan(sample_project_spec, sample_forge_output)

    assert plan_a.total_commits == plan_b.total_commits
    for ca, cb in zip(plan_a.commits, plan_b.commits, strict=True):
        assert ca.message == cb.message
        assert ca.phase == cb.phase
        assert ca.timestamp_offset_hours == cb.timestamp_offset_hours


def test_different_seeds_may_produce_different_timestamps(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """Different seeds should generally produce different timestamp sequences."""
    engine_a = CommitStrategyEngine(spread_days=5, seed=1)
    engine_b = CommitStrategyEngine(spread_days=5, seed=9999)

    plan_a = engine_a.generate_plan(sample_project_spec, sample_forge_output)
    plan_b = engine_b.generate_plan(sample_project_spec, sample_forge_output)

    offsets_a = [e.timestamp_offset_hours for e in plan_a.commits]
    offsets_b = [e.timestamp_offset_hours for e in plan_b.commits]
    # At least one offset should differ (extremely unlikely to collide)
    assert offsets_a != offsets_b


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_generate_plan_with_empty_code_modules(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """With no code modules, the plan should still produce at least a POLISH commit."""
    from letsbuild.models.forge_models import ForgeOutput, ReviewVerdict, SwarmTopology

    empty_forge = ForgeOutput(
        code_modules=[],
        test_results={
            "pip install -e .": True,
            "pytest tests/ -v": True,
            "ruff check .": True,
        },
        review_verdict=ReviewVerdict.PASS,
        quality_score=75.0,
        total_tokens_used=1000,
        total_retries=0,
        topology_used=SwarmTopology.HIERARCHICAL,
    )

    engine = CommitStrategyEngine(spread_days=3, seed=0)
    plan = engine.generate_plan(sample_project_spec, empty_forge)

    # ADR entries are added from project_spec even without code_modules
    assert plan.total_commits >= 1
    last = plan.commits[-1]
    assert last.phase == CommitPhase.POLISH


def test_spread_days_less_than_one_raises_value_error() -> None:
    """Initialising with spread_days < 1 must raise ValueError."""
    with pytest.raises(ValueError, match="spread_days must be at least 1"):
        CommitStrategyEngine(spread_days=0)
