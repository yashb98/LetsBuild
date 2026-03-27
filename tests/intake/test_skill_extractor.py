"""Tests for SkillExtractor (Layer 1 — rule-based skill extraction)."""

from __future__ import annotations

from pathlib import Path

import pytest

from letsbuild.intake.skill_extractor import SkillExtractor

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "sample_jds"


@pytest.fixture()
def extractor() -> SkillExtractor:
    """Return a SkillExtractor initialised with the default taxonomy."""
    return SkillExtractor()


class TestTaxonomyLoading:
    """Tests for taxonomy loading and lookup construction."""

    def test_taxonomy_loads_successfully(self) -> None:
        """SkillExtractor should initialise without error using the default taxonomy."""
        ext = SkillExtractor()
        assert ext is not None

    def test_lookup_has_entries(self) -> None:
        """The internal lookup dict should contain taxonomy entries."""
        ext = SkillExtractor()
        assert len(ext._lookup) > 0


class TestExtract:
    """Tests for SkillExtractor.extract."""

    def test_extract_finds_python(self, extractor: SkillExtractor) -> None:
        """Text mentioning 'Python' should produce a skill with canonical name 'python'."""
        skills = extractor.extract("We need someone with Python experience.")
        names = [s.name.lower() for s in skills]
        assert "python" in names

    def test_extract_finds_multiple_skills(self, extractor: SkillExtractor) -> None:
        """Text mentioning several technologies should return all of them."""
        text = "Proficiency in Python, React, and PostgreSQL required."
        skills = extractor.extract(text)
        names = {s.name.lower() for s in skills}
        assert "python" in names
        assert "react" in names
        assert "postgresql" in names

    def test_extract_case_insensitive(self, extractor: SkillExtractor) -> None:
        """Skill matching should be case-insensitive."""
        skills_upper = extractor.extract("REACT experience needed")
        skills_lower = extractor.extract("react experience needed")
        names_upper = {s.name.lower() for s in skills_upper}
        names_lower = {s.name.lower() for s in skills_lower}
        assert names_upper == names_lower
        assert "react" in names_upper

    def test_extract_deduplicates(self, extractor: SkillExtractor) -> None:
        """Same skill mentioned twice should result in one entry with higher confidence."""
        text = "Python is required. Strong Python skills needed."
        skills = extractor.extract(text)
        python_skills = [s for s in skills if s.name.lower() == "python"]
        assert len(python_skills) == 1
        # Confidence should be above the base 80.0 due to repeat bonus
        assert python_skills[0].confidence > 80.0

    def test_extract_bigram_match(self, extractor: SkillExtractor) -> None:
        """Multi-word skills like 'rest api' should be found as a single skill."""
        skills = extractor.extract("Experience building REST API services required.")
        names = {s.name.lower() for s in skills}
        assert "rest api" in names

    def test_extract_empty_text_returns_empty(self, extractor: SkillExtractor) -> None:
        """Empty input text should return an empty list."""
        skills = extractor.extract("")
        assert skills == []

    def test_extract_no_matches_returns_empty(self, extractor: SkillExtractor) -> None:
        """Text with no recognisable skills should return an empty list."""
        skills = extractor.extract("The weather is nice today and birds are singing.")
        assert skills == []


class TestExtractAgainstFixtures:
    """Test skill extraction against the sample JD fixtures."""

    @pytest.mark.parametrize(
        ("fixture_file", "expected_skills"),
        [
            (
                "senior_fullstack_fintech.txt",
                ["react", "typescript", "postgresql"],
            ),
            (
                "junior_data_science.txt",
                ["python", "sql"],
            ),
            (
                "mid_ml_engineer.txt",
                ["python", "docker", "fastapi"],
            ),
            (
                "senior_platform_eng.txt",
                ["kubernetes", "terraform", "go"],
            ),
            (
                "staff_agentic_ai.txt",
                ["python"],
            ),
        ],
    )
    def test_fixture_extraction_finds_expected_skills(
        self,
        extractor: SkillExtractor,
        fixture_file: str,
        expected_skills: list[str],
    ) -> None:
        """Each sample JD fixture should yield non-empty results with expected skills."""
        jd_path = _FIXTURES_DIR / fixture_file
        text = jd_path.read_text(encoding="utf-8")
        skills = extractor.extract(text)
        assert len(skills) > 0, f"Expected non-empty skills from {fixture_file}"
        names = {s.name.lower() for s in skills}
        for expected in expected_skills:
            assert expected in names, (
                f"Expected '{expected}' in skills from {fixture_file}, got {names}"
            )
