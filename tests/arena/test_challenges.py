"""Tests for ChallengeEngine — challenge file loading and management."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import pytest

from letsbuild.arena.challenges import ChallengeEngine
from letsbuild.models.arena_models import Challenge

CHALLENGES_DIR = "skills/challenges"


@pytest.fixture()
def engine() -> ChallengeEngine:
    """ChallengeEngine pointed at the real challenges directory."""
    return ChallengeEngine(challenges_dir=CHALLENGES_DIR)


# ---------------------------------------------------------------------------
# Load Tests
# ---------------------------------------------------------------------------


class TestLoad:
    """Test ChallengeEngine.load()."""

    def test_load_url_shortener(self, engine: ChallengeEngine) -> None:
        challenge = engine.load("url-shortener")
        assert isinstance(challenge, Challenge)
        assert challenge.name == "URL Shortener Service"
        assert challenge.difficulty == 5
        assert challenge.category == "backend"
        assert len(challenge.requirements) >= 5

    def test_load_task_manager(self, engine: ChallengeEngine) -> None:
        challenge = engine.load("task-manager")
        assert challenge.difficulty == 6
        assert len(challenge.judging_weights) > 0

    def test_load_cli_file_organizer(self, engine: ChallengeEngine) -> None:
        challenge = engine.load("cli-file-organizer")
        assert challenge.difficulty == 4
        assert challenge.category == "cli"

    def test_load_weather_dashboard(self, engine: ChallengeEngine) -> None:
        challenge = engine.load("weather-dashboard")
        assert challenge.difficulty == 5
        assert challenge.category == "fullstack"

    def test_load_code_review_bot(self, engine: ChallengeEngine) -> None:
        challenge = engine.load("code-review-bot")
        assert challenge.difficulty == 8
        assert challenge.category == "agentic"

    def test_load_nonexistent_raises(self, engine: ChallengeEngine) -> None:
        with pytest.raises(FileNotFoundError):
            engine.load("nonexistent-challenge")

    def test_load_has_time_limits(self, engine: ChallengeEngine) -> None:
        challenge = engine.load("url-shortener")
        assert len(challenge.time_limits) > 0

    def test_load_has_hidden_test_path(self, engine: ChallengeEngine) -> None:
        challenge = engine.load("url-shortener")
        assert challenge.hidden_test_path is not None


# ---------------------------------------------------------------------------
# List Tests
# ---------------------------------------------------------------------------


class TestListAll:
    """Test ChallengeEngine.list_all()."""

    def test_list_returns_all_five(self, engine: ChallengeEngine) -> None:
        challenges = engine.list_all()
        assert len(challenges) == 5

    def test_filter_by_category(self, engine: ChallengeEngine) -> None:
        backend = engine.list_all(category="backend")
        assert len(backend) >= 1
        assert all(c.category == "backend" for c in backend)

    def test_filter_by_difficulty(self, engine: ChallengeEngine) -> None:
        easy = engine.list_all(difficulty=4)
        assert len(easy) >= 1
        assert all(c.difficulty == 4 for c in easy)

    def test_filter_no_match(self, engine: ChallengeEngine) -> None:
        result = engine.list_all(category="nonexistent")
        assert result == []

    def test_list_nonexistent_dir(self) -> None:
        engine = ChallengeEngine(challenges_dir="/nonexistent/dir")
        assert engine.list_all() == []


# ---------------------------------------------------------------------------
# Brief Generation Tests
# ---------------------------------------------------------------------------


class TestGenerateBrief:
    """Test ChallengeEngine.generate_brief()."""

    def test_brief_non_empty(self, engine: ChallengeEngine) -> None:
        challenge = engine.load("url-shortener")
        brief = engine.generate_brief(challenge)
        assert len(brief) > 100

    def test_brief_contains_name(self, engine: ChallengeEngine) -> None:
        challenge = engine.load("url-shortener")
        brief = engine.generate_brief(challenge)
        assert challenge.name in brief

    def test_brief_contains_requirements(self, engine: ChallengeEngine) -> None:
        challenge = engine.load("url-shortener")
        brief = engine.generate_brief(challenge)
        assert "Requirements" in brief


# ---------------------------------------------------------------------------
# Invalid File Tests
# ---------------------------------------------------------------------------


class TestInvalidFiles:
    """Test error handling for malformed challenge files."""

    def test_load_invalid_yaml_raises(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.challenge.md"
        bad_file.write_text("no frontmatter here")
        engine = ChallengeEngine(challenges_dir=str(tmp_path))
        with pytest.raises(ValueError, match="No YAML frontmatter"):
            engine.load("bad")
