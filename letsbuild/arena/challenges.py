"""Challenge engine for loading and managing Arena challenge files."""

from __future__ import annotations

import re
from pathlib import Path

import structlog
import yaml
from pydantic import ValidationError

from letsbuild.models.arena_models import Challenge, PhaseTimeLimit, TournamentPhase

logger = structlog.get_logger()

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class ChallengeEngine:
    """Loads, validates, and manages the challenge library.

    Challenge files are ``.challenge.md`` files with YAML frontmatter
    matching the :class:`Challenge` model schema, followed by a markdown
    body with the problem description.
    """

    def __init__(self, challenges_dir: str = "skills/challenges") -> None:
        self._dir = Path(challenges_dir)
        self._log = logger.bind(component="challenge_engine")

    def load(self, challenge_id: str) -> Challenge:
        """Load a .challenge.md file and parse into a Challenge model.

        Args:
            challenge_id: Kebab-case challenge name (e.g. 'url-shortener').

        Returns:
            Validated Challenge model.

        Raises:
            FileNotFoundError: If the challenge file does not exist.
            ValueError: If frontmatter is missing or invalid.
        """
        file_path = self._dir / f"{challenge_id}.challenge.md"
        if not file_path.exists():
            msg = f"Challenge file not found: {file_path}"
            raise FileNotFoundError(msg)

        raw = file_path.read_text(encoding="utf-8")
        self._log.info("loading_challenge", challenge_id=challenge_id)

        frontmatter = self._parse_frontmatter(raw, str(file_path))
        body = self._parse_body(raw)

        return self._build_challenge(frontmatter, body, challenge_id)

    def list_all(
        self,
        category: str | None = None,
        difficulty: int | None = None,
    ) -> list[Challenge]:
        """List available challenges, optionally filtered by category or difficulty.

        Returns an empty list if the challenges directory doesn't exist.
        """
        if not self._dir.exists():
            return []

        challenges: list[Challenge] = []
        for file_path in sorted(self._dir.glob("*.challenge.md")):
            challenge_id = file_path.stem.removesuffix(".challenge")
            try:
                challenge = self.load(challenge_id)
                if category and challenge.category != category:
                    continue
                if difficulty is not None and challenge.difficulty != difficulty:
                    continue
                challenges.append(challenge)
            except (FileNotFoundError, ValueError, ValidationError):
                self._log.warning("skip_invalid_challenge", file=str(file_path), exc_info=True)
                continue

        return challenges

    def generate_brief(self, challenge: Challenge) -> str:
        """Render the challenge as a markdown brief for teams to receive."""
        lines = [
            f"# {challenge.name}",
            "",
            challenge.description,
            "",
            "## Requirements",
            "",
        ]
        for i, req in enumerate(challenge.requirements, 1):
            lines.append(f"{i}. {req}")

        if challenge.bonus_features:
            lines.extend(["", "## Bonus Features", ""])
            for feat in challenge.bonus_features:
                lines.append(f"- {feat}")

        if challenge.constraints:
            lines.extend(["", "## Constraints", ""])
            for key, value in challenge.constraints.items():
                lines.append(f"- **{key}:** {value}")

        lines.extend(
            [
                "",
                f"**Difficulty:** {challenge.difficulty}/10",
                f"**Category:** {challenge.category}",
            ]
        )

        return "\n".join(lines)

    def get_hidden_tests(self, challenge: Challenge) -> str | None:
        """Return hidden test file content if exists, else None."""
        if not challenge.hidden_test_path:
            return None

        test_path = Path(challenge.hidden_test_path)
        if not test_path.exists():
            self._log.debug("hidden_tests_not_found", path=str(test_path))
            return None

        return test_path.read_text(encoding="utf-8")

    # --- Internal parsing ---

    @staticmethod
    def _parse_frontmatter(raw: str, file_path: str) -> dict[str, object]:
        """Extract YAML frontmatter from raw file content."""
        match = _FRONTMATTER_RE.match(raw)
        if not match:
            msg = f"No YAML frontmatter found in {file_path}"
            raise ValueError(msg)

        try:
            data: dict[str, object] = yaml.safe_load(match.group(1))
        except yaml.YAMLError as exc:
            msg = f"Invalid YAML frontmatter in {file_path}: {exc}"
            raise ValueError(msg) from exc

        return data

    @staticmethod
    def _parse_body(raw: str) -> str:
        """Extract the markdown body after frontmatter."""
        match = _FRONTMATTER_RE.match(raw)
        if match:
            return raw[match.end() :].strip()
        return raw.strip()

    def _build_challenge(
        self,
        frontmatter: dict[str, object],
        body: str,
        challenge_id: str,
    ) -> Challenge:
        """Build a Challenge model from parsed frontmatter and body."""
        # Parse time_limits from dict format to PhaseTimeLimit objects
        time_limits_raw = frontmatter.pop("time_limits", {})
        time_limits: list[PhaseTimeLimit] = []
        if isinstance(time_limits_raw, dict):
            for phase_name, seconds in time_limits_raw.items():
                try:
                    phase = TournamentPhase(phase_name)
                    time_limits.append(PhaseTimeLimit(phase=phase, seconds=int(str(seconds))))
                except (ValueError, KeyError):
                    self._log.warning(
                        "invalid_time_limit",
                        phase=phase_name,
                        challenge_id=challenge_id,
                    )

        raw_reqs = frontmatter.get("requirements", [])
        raw_bonus = frontmatter.get("bonus_features", [])
        raw_constraints = frontmatter.get("constraints", {})
        raw_weights = frontmatter.get("judging_weights", {})

        requirements = list(raw_reqs) if isinstance(raw_reqs, list) else []
        bonus_features = list(raw_bonus) if isinstance(raw_bonus, list) else []
        constraints = dict(raw_constraints) if isinstance(raw_constraints, dict) else {}
        judging_weights: dict[str, float] = {}
        if isinstance(raw_weights, dict):
            judging_weights = {str(k): float(str(v)) for k, v in raw_weights.items()}

        hidden_path_raw = frontmatter.get("hidden_test_path")
        hidden_path = str(hidden_path_raw) if hidden_path_raw else None

        return Challenge(
            challenge_id=challenge_id,
            name=str(frontmatter.get("display_name", challenge_id)),
            description=body or str(frontmatter.get("description", "")),
            requirements=[str(r) for r in requirements],
            bonus_features=[str(b) for b in bonus_features],
            constraints=constraints,
            judging_weights=judging_weights,
            hidden_test_path=hidden_path,
            time_limits=time_limits,
            difficulty=int(str(frontmatter.get("difficulty", 5))),
            category=str(frontmatter.get("category", "general")),
        )
