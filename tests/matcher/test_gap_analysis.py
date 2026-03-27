"""Tests for the GapAnalyser utility (Layer 3)."""

from __future__ import annotations

from letsbuild.matcher.gap_analysis import GapAnalyser
from letsbuild.models.matcher_models import GapCategory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _analyser() -> GapAnalyser:
    return GapAnalyser()


# ---------------------------------------------------------------------------
# categorise_skill tests
# ---------------------------------------------------------------------------


def test_categorise_skill_strong_match() -> None:
    """User possessing the exact skill returns STRONG_MATCH."""
    analyser = _analyser()
    result = analyser.categorise_skill("Python", {"python", "docker"})
    assert result == GapCategory.STRONG_MATCH


def test_categorise_skill_hard_gap() -> None:
    """User having nothing related returns HARD_GAP."""
    analyser = _analyser()
    result = analyser.categorise_skill("Cobol", {"python", "react"})
    assert result == GapCategory.HARD_GAP


# ---------------------------------------------------------------------------
# compute_skill_overlap tests
# ---------------------------------------------------------------------------


def test_compute_overlap_full() -> None:
    """100% overlap when user has all required skills."""
    analyser = _analyser()
    result = analyser.compute_skill_overlap(
        required=["Python", "Docker"],
        user_has=["python", "docker", "aws"],
    )
    assert result == 100.0


def test_compute_overlap_none() -> None:
    """0% overlap when user has none of the required skills."""
    analyser = _analyser()
    result = analyser.compute_skill_overlap(
        required=["Haskell", "Erlang"],
        user_has=["python", "docker"],
    )
    assert result == 0.0


def test_compute_overlap_partial() -> None:
    """50% overlap when user matches half the required skills."""
    analyser = _analyser()
    result = analyser.compute_skill_overlap(
        required=["Python", "Go"],
        user_has=["python"],
    )
    assert result == 50.0
