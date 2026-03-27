"""Tests for the skill file parser."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import pytest

from letsbuild.architect.skill_parser import ParsedSkill, SkillParser

VALID_SKILL_CONTENT = """\
---
name: fullstack
display_name: "Full-Stack Web Application"
category: project
role_categories:
  - full_stack_engineer
  - frontend_engineer
seniority_range: [junior, mid, senior, staff]
tech_stacks:
  primary: ["React", "Next.js", "FastAPI", "PostgreSQL"]
  alternatives: ["Vue", "Django"]
complexity_range: [3, 8]
estimated_loc: [800, 3000]
topology: hierarchical
---

## Overview

This skill generates full-stack web applications.

## Project Templates

Template 1: E-commerce dashboard.

## Architecture Patterns

All projects must have API + frontend + DB layers.

## File Tree Template

```
src/
  api/
  frontend/
  db/
```

## Quality Criteria

Must pass type checking and linting.

## Sandbox Validation Plan

```yaml
sandbox_validation_plan:
  - "cd /mnt/workspace && pip install -e ."
  - "cd /mnt/workspace && pytest tests/ -v"
```

## ADR Templates

ADR-001: Choice of framework.

## Common Failure Modes

Database migrations failing in sandbox.
"""

MINIMAL_FRONTMATTER_CONTENT = """\
---
name: test-skill
display_name: "Test Skill"
category: project
role_categories:
  - backend_engineer
seniority_range: [mid]
tech_stacks:
  primary: ["Python"]
complexity_range: [1, 5]
estimated_loc: [100, 500]
---

## Overview

Just an overview, missing other sections.
"""


@pytest.fixture()
def parser() -> SkillParser:
    return SkillParser()


@pytest.fixture()
def valid_skill_file(tmp_path: Path) -> Path:
    p = tmp_path / "fullstack.skill.md"
    p.write_text(VALID_SKILL_CONTENT, encoding="utf-8")
    return p


@pytest.fixture()
def minimal_skill_file(tmp_path: Path) -> Path:
    p = tmp_path / "minimal.skill.md"
    p.write_text(MINIMAL_FRONTMATTER_CONTENT, encoding="utf-8")
    return p


class TestParseValidSkillFile:
    def test_parse_valid_skill_file(
        self, parser: SkillParser, valid_skill_file: Path
    ) -> None:
        result = parser.parse(valid_skill_file)

        assert isinstance(result, ParsedSkill)
        assert result.is_valid is True
        assert result.missing_sections == []
        assert result.config.name == "fullstack"
        assert result.config.display_name == "Full-Stack Web Application"
        assert result.config.category == "project"
        assert result.config.topology == "hierarchical"
        assert "React" in result.config.tech_stacks_primary
        assert result.file_path == str(valid_skill_file)
        assert len(result.raw_content) > 0


class TestParseFrontmatter:
    def test_parse_frontmatter_extracts_yaml(self, parser: SkillParser) -> None:
        fm = parser.parse_frontmatter(VALID_SKILL_CONTENT)

        assert fm["name"] == "fullstack"
        assert fm["display_name"] == "Full-Stack Web Application"
        assert fm["category"] == "project"
        assert isinstance(fm["role_categories"], list)
        assert "full_stack_engineer" in fm["role_categories"]
        assert isinstance(fm["tech_stacks"], dict)
        assert fm["tech_stacks"]["primary"] == ["React", "Next.js", "FastAPI", "PostgreSQL"]
        assert fm["complexity_range"] == [3, 8]

    def test_parse_frontmatter_missing_markers_raises(self, parser: SkillParser) -> None:
        with pytest.raises(ValueError, match=r"No YAML frontmatter found"):
            parser.parse_frontmatter("No frontmatter here.")


class TestParseBodySections:
    def test_parse_body_sections_splits_correctly(self, parser: SkillParser) -> None:
        sections = parser.parse_body_sections(VALID_SKILL_CONTENT)

        assert "Overview" in sections
        assert "Project Templates" in sections
        assert "Architecture Patterns" in sections
        assert "File Tree Template" in sections
        assert "Quality Criteria" in sections
        assert "Sandbox Validation Plan" in sections
        assert "ADR Templates" in sections
        assert "Common Failure Modes" in sections
        assert len(sections) == 8

        assert "full-stack web applications" in sections["Overview"]
        assert "E-commerce dashboard" in sections["Project Templates"]

    def test_parse_body_sections_no_frontmatter(self, parser: SkillParser) -> None:
        content = "## Section A\n\nContent A.\n\n## Section B\n\nContent B."
        sections = parser.parse_body_sections(content)
        assert "Section A" in sections
        assert "Section B" in sections


class TestValidateSections:
    def test_validate_sections_all_present(self, parser: SkillParser) -> None:
        sections = parser.parse_body_sections(VALID_SKILL_CONTENT)
        missing = parser.validate_sections(sections)
        assert missing == []

    def test_validate_sections_missing_returns_names(self, parser: SkillParser) -> None:
        sections = {"Overview": "text", "Project Templates": "text"}
        missing = parser.validate_sections(sections)

        assert "Architecture Patterns" in missing
        assert "File Tree Template" in missing
        assert "Quality Criteria" in missing
        assert "Sandbox Validation Plan" in missing
        assert "ADR Templates" in missing
        assert "Common Failure Modes" in missing
        assert len(missing) == 6

    def test_validate_sections_empty_dict(self, parser: SkillParser) -> None:
        missing = parser.validate_sections({})
        assert len(missing) == 8


class TestParseMissingFile:
    def test_parse_missing_file_raises(self, parser: SkillParser) -> None:
        with pytest.raises(FileNotFoundError, match=r"Skill file not found"):
            parser.parse("/nonexistent/path/skill.skill.md")


class TestParseMalformedYaml:
    def test_parse_malformed_yaml_handles_gracefully(
        self, parser: SkillParser, tmp_path: Path
    ) -> None:
        bad_file = tmp_path / "bad.skill.md"
        bad_file.write_text(
            "---\nname: [invalid yaml\n  bad: {{\n---\n\n## Overview\n\nContent.\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match=r"Malformed YAML"):
            parser.parse(bad_file)

    def test_parse_invalid_frontmatter_fields_raises(
        self, parser: SkillParser, tmp_path: Path
    ) -> None:
        """Frontmatter YAML is valid but fields don't match SkillConfig schema."""
        bad_file = tmp_path / "bad_fields.skill.md"
        bad_file.write_text(
            "---\nname: test\n---\n\n## Overview\n\nContent.\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match=r"Invalid skill frontmatter"):
            parser.parse(bad_file)


class TestParsedSkillWithMissingSections:
    def test_parsed_skill_missing_sections_not_valid(
        self, parser: SkillParser, minimal_skill_file: Path
    ) -> None:
        result = parser.parse(minimal_skill_file)

        assert result.is_valid is False
        assert len(result.missing_sections) == 7
        assert "Overview" not in result.missing_sections
        assert "Project Templates" in result.missing_sections
