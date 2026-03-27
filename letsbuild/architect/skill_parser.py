"""Skill file parser for .skill.md files with YAML frontmatter and markdown body."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import structlog
import yaml
from pydantic import ValidationError

from letsbuild.models.config_models import SkillConfig

logger = structlog.get_logger()

REQUIRED_SECTIONS: list[str] = [
    "Overview",
    "Project Templates",
    "Architecture Patterns",
    "File Tree Template",
    "Quality Criteria",
    "Sandbox Validation Plan",
    "ADR Templates",
    "Common Failure Modes",
]

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_SECTION_RE = re.compile(r"^## (.+)$", re.MULTILINE)


@dataclass
class ParsedSkill:
    """Result of parsing a .skill.md file."""

    config: SkillConfig
    sections: dict[str, str]
    raw_content: str
    file_path: str
    missing_sections: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True if no required sections are missing."""
        return len(self.missing_sections) == 0


class SkillParser:
    """Parses .skill.md files into structured ParsedSkill objects."""

    def __init__(self) -> None:
        self.log = structlog.get_logger(component="skill_parser")

    def parse(self, file_path: str | Path) -> ParsedSkill:
        """Read and parse a .skill.md file into a ParsedSkill.

        Args:
            file_path: Path to the skill file.

        Returns:
            ParsedSkill with config, sections, and validation results.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If YAML frontmatter is missing or unparseable.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Skill file not found: {path}")

        raw_content = path.read_text(encoding="utf-8")
        self.log.info("parsing_skill_file", file_path=str(path))

        frontmatter = self.parse_frontmatter(raw_content)
        sections = self.parse_body_sections(raw_content)
        missing = self.validate_sections(sections)

        config = self._build_config(frontmatter, str(path))

        parsed = ParsedSkill(
            config=config,
            sections=sections,
            raw_content=raw_content,
            file_path=str(path),
            missing_sections=missing,
        )

        if missing:
            self.log.warning(
                "skill_missing_sections",
                file_path=str(path),
                missing=missing,
            )
        else:
            self.log.info("skill_parsed_successfully", file_path=str(path))

        return parsed

    def parse_frontmatter(self, content: str) -> dict[str, object]:
        """Extract and parse YAML frontmatter from skill file content.

        Args:
            content: Full file content.

        Returns:
            Parsed YAML as a dict.

        Raises:
            ValueError: If frontmatter markers are missing or YAML is malformed.
        """
        match = _FRONTMATTER_RE.search(content)
        if match is None:
            raise ValueError("No YAML frontmatter found (expected --- markers).")

        yaml_text = match.group(1)
        try:
            parsed = yaml.safe_load(yaml_text)
        except yaml.YAMLError as exc:
            raise ValueError(f"Malformed YAML in frontmatter: {exc}") from exc

        if not isinstance(parsed, dict):
            raise ValueError("Frontmatter YAML must be a mapping, got {type(parsed).__name__}.")

        return parsed  # type: ignore[return-value]

    def parse_body_sections(self, content: str) -> dict[str, str]:
        """Split the body (after frontmatter) into sections keyed by ## heading.

        Args:
            content: Full file content.

        Returns:
            Dict mapping section name to its content (without the heading line).
        """
        # Strip frontmatter to get body
        fm_match = _FRONTMATTER_RE.search(content)
        body = content[fm_match.end() :] if fm_match else content

        sections: dict[str, str] = {}
        headings = list(_SECTION_RE.finditer(body))

        for i, heading_match in enumerate(headings):
            name = heading_match.group(1).strip()
            start = heading_match.end()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(body)
            sections[name] = body[start:end].strip()

        return sections

    def validate_sections(self, sections: dict[str, str]) -> list[str]:
        """Check that all required sections are present.

        Args:
            sections: Dict of section_name -> content.

        Returns:
            List of missing section names (empty means all present).
        """
        return [name for name in REQUIRED_SECTIONS if name not in sections]

    def _build_config(self, frontmatter: dict[str, object], file_path: str) -> SkillConfig:
        """Build a SkillConfig from raw frontmatter dict.

        Handles the nested tech_stacks and sandbox_requirements keys by
        flattening them to match the SkillConfig schema.

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        flat: dict[str, object] = {}

        # Direct fields
        for key in (
            "name",
            "display_name",
            "category",
            "role_categories",
            "seniority_range",
            "complexity_range",
            "estimated_loc",
            "topology",
        ):
            if key in frontmatter:
                flat[key] = frontmatter[key]

        # Flatten nested tech_stacks
        tech_stacks = frontmatter.get("tech_stacks")
        if isinstance(tech_stacks, dict):
            flat["tech_stacks_primary"] = tech_stacks.get("primary", [])
            flat["tech_stacks_alternatives"] = tech_stacks.get("alternatives", [])
        elif "tech_stacks_primary" in frontmatter:
            flat["tech_stacks_primary"] = frontmatter["tech_stacks_primary"]
            flat["tech_stacks_alternatives"] = frontmatter.get("tech_stacks_alternatives", [])

        try:
            return SkillConfig.model_validate(flat)
        except ValidationError as exc:
            self.log.error("skill_config_invalid", file_path=file_path, error=str(exc))
            raise ValueError(f"Invalid skill frontmatter in {file_path}: {exc}") from exc
