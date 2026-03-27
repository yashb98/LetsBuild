"""Tests for the Match & Score Engine (Layer 3) — MatchEngine."""

from __future__ import annotations

import pytest

from letsbuild.matcher.engine import _DIMENSION_WEIGHTS, MatchEngine
from letsbuild.models.intake_models import (
    JDAnalysis,
    RoleCategory,
    SeniorityLevel,
    Skill,
    TechStack,
)
from letsbuild.models.matcher_models import MatchDimension

# ---------------------------------------------------------------------------
# Helper: build a minimal valid JDAnalysis
# ---------------------------------------------------------------------------


def _make_jd(
    *,
    required_skill_names: list[str] | None = None,
    preferred_skill_names: list[str] | None = None,
    tech_languages: list[str] | None = None,
    tech_frameworks: list[str] | None = None,
    domain_keywords: list[str] | None = None,
    key_responsibilities: list[str] | None = None,
    role_title: str = "Software Engineer",
    role_category: RoleCategory = RoleCategory.BACKEND,
    seniority: SeniorityLevel = SeniorityLevel.MID,
) -> JDAnalysis:
    """Build a minimal valid JDAnalysis for testing."""
    required = [Skill(name=n, category="language") for n in (required_skill_names or [])]
    preferred = [Skill(name=n, category="framework") for n in (preferred_skill_names or [])]
    return JDAnalysis(
        role_title=role_title,
        role_category=role_category,
        seniority=seniority,
        required_skills=required,
        preferred_skills=preferred,
        tech_stack=TechStack(
            languages=tech_languages or [],
            frameworks=tech_frameworks or [],
        ),
        domain_keywords=domain_keywords or [],
        key_responsibilities=key_responsibilities or [],
        raw_text="Test JD text.",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyse_returns_gap_analysis() -> None:
    """Valid input produces a GapAnalysis with all expected fields populated."""
    jd = _make_jd(required_skill_names=["Python", "FastAPI"])
    engine = MatchEngine(user_skills=["Python"])
    result = await engine.analyse(jd)

    assert result.match_score is not None
    assert result.analysis_summary
    assert result.recommended_project_focus
    assert result.analysed_at is not None


@pytest.mark.asyncio
async def test_perfect_match_high_score() -> None:
    """User possessing all required skills produces a high overall score."""
    skills = ["Python", "FastAPI", "PostgreSQL"]
    jd = _make_jd(
        required_skill_names=skills,
        tech_languages=["python"],
        tech_frameworks=["fastapi"],
    )
    engine = MatchEngine(user_skills=skills)
    result = await engine.analyse(jd)

    # Hard-skills and tech-stack dimensions should be 100 %; overall must be high.
    assert result.match_score.overall_score >= 50.0


@pytest.mark.asyncio
async def test_no_match_low_score() -> None:
    """User with zero relevant skills produces a low overall score."""
    jd = _make_jd(
        required_skill_names=["Haskell", "Erlang", "Prolog"],
        tech_languages=["haskell", "erlang", "prolog"],
    )
    engine = MatchEngine(user_skills=["Woodworking", "Pottery"])
    result = await engine.analyse(jd)

    # Hard-skills dimension should be 0; weighted overall stays low.
    hard_dim = next(
        d for d in result.match_score.dimension_scores if d.dimension == MatchDimension.HARD_SKILLS
    )
    assert hard_dim.score == 0.0
    assert result.match_score.overall_score < 50.0


@pytest.mark.asyncio
async def test_partial_match_medium_score() -> None:
    """User with some matching skills lands between perfect and zero."""
    jd = _make_jd(
        required_skill_names=["Python", "Go", "Rust", "Terraform"],
        tech_languages=["python", "go", "rust"],
    )
    engine = MatchEngine(user_skills=["Python", "Go"])
    result = await engine.analyse(jd)

    hard_dim = next(
        d for d in result.match_score.dimension_scores if d.dimension == MatchDimension.HARD_SKILLS
    )
    assert 20.0 <= hard_dim.score <= 80.0


def test_dimension_weights_sum_to_one() -> None:
    """Canonical dimension weights must sum to exactly 1.0."""
    total = sum(_DIMENSION_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9


@pytest.mark.asyncio
async def test_strong_matches_populated() -> None:
    """Skills the user already has appear in strong_matches."""
    jd = _make_jd(required_skill_names=["Python", "Docker"])
    engine = MatchEngine(user_skills=["Python", "Docker"])
    result = await engine.analyse(jd)

    strong_names = {item.skill_name for item in result.strong_matches}
    assert "Python" in strong_names
    assert "Docker" in strong_names


@pytest.mark.asyncio
async def test_demonstrable_gaps_populated() -> None:
    """Related skills are categorised as demonstrable gaps."""
    # User has "React" which is related to "Vue" via skill family.
    jd = _make_jd(required_skill_names=["Vue"])
    engine = MatchEngine(user_skills=["React"])
    result = await engine.analyse(jd)

    demo_names = {item.skill_name for item in result.demonstrable_gaps}
    assert "Vue" in demo_names


@pytest.mark.asyncio
async def test_recommended_focus_nonempty() -> None:
    """Recommended project focus always contains at least one item."""
    jd = _make_jd(required_skill_names=["Python"])
    engine = MatchEngine(user_skills=[])
    result = await engine.analyse(jd)

    assert len(result.recommended_project_focus) >= 1


@pytest.mark.asyncio
async def test_analysis_summary_nonempty() -> None:
    """Analysis summary is a non-empty string with score info."""
    jd = _make_jd(required_skill_names=["Python", "FastAPI"])
    engine = MatchEngine(user_skills=["Python"])
    result = await engine.analyse(jd)

    assert isinstance(result.analysis_summary, str)
    assert len(result.analysis_summary) > 0
    assert "overall score" in result.analysis_summary.lower()
