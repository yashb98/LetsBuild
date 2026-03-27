"""Tests for the ATSPredictor (Layer 3)."""

from __future__ import annotations

from letsbuild.matcher.ats_predictor import ATSPredictor
from letsbuild.models.intake_models import (
    JDAnalysis,
    RoleCategory,
    SeniorityLevel,
    Skill,
    TechStack,
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_jd(
    *,
    required_skill_names: list[str] | None = None,
    preferred_skill_names: list[str] | None = None,
    tech_languages: list[str] | None = None,
    domain_keywords: list[str] | None = None,
    years_experience_min: int | None = None,
) -> JDAnalysis:
    """Build a minimal valid JDAnalysis for ATS prediction tests."""
    required = [Skill(name=n, category="language") for n in (required_skill_names or [])]
    preferred = [Skill(name=n, category="framework") for n in (preferred_skill_names or [])]
    return JDAnalysis(
        role_title="Software Engineer",
        role_category=RoleCategory.BACKEND,
        seniority=SeniorityLevel.MID,
        required_skills=required,
        preferred_skills=preferred,
        tech_stack=TechStack(languages=tech_languages or []),
        domain_keywords=domain_keywords or [],
        key_responsibilities=[],
        years_experience_min=years_experience_min,
        raw_text="Test JD text.",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_predict_high_match() -> None:
    """User matching most JD skills produces a high ATS score."""
    jd = _make_jd(
        required_skill_names=["Python", "FastAPI", "PostgreSQL"],
        tech_languages=["python"],
        domain_keywords=["fintech"],
    )
    predictor = ATSPredictor()
    score = predictor.predict(jd, ["Python", "FastAPI", "PostgreSQL", "fintech"])
    assert score >= 60.0


def test_predict_low_match() -> None:
    """User matching few JD skills produces a low ATS score."""
    jd = _make_jd(
        required_skill_names=["Haskell", "Erlang", "Prolog"],
        tech_languages=["haskell", "erlang", "prolog"],
        domain_keywords=["quantum computing"],
    )
    predictor = ATSPredictor()
    score = predictor.predict(jd, ["Woodworking"])
    assert score < 50.0


def test_predict_returns_bounded_score() -> None:
    """ATS score is always between 0.0 and 100.0."""
    jd = _make_jd(required_skill_names=["Python"])
    predictor = ATSPredictor()

    score_match = predictor.predict(jd, ["Python"])
    assert 0.0 <= score_match <= 100.0

    score_none = predictor.predict(jd, [])
    assert 0.0 <= score_none <= 100.0


def test_predict_empty_skills() -> None:
    """JD with no skills listed returns a neutral score."""
    jd = _make_jd()  # No required or preferred skills
    predictor = ATSPredictor()
    score = predictor.predict(jd, ["Python", "Docker"])
    # With no skills to compare, keyword_overlap returns 50 (neutral).
    assert 30.0 <= score <= 80.0
