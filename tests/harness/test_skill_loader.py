"""Tests for SkillLoaderMiddleware — progressive skill loading based on JD role category."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import pytest

from letsbuild.harness.middlewares.skill_loader import SkillLoaderMiddleware
from letsbuild.models.config_models import SkillConfig
from letsbuild.models.intake_models import JDAnalysis, RoleCategory, SeniorityLevel
from letsbuild.pipeline.state import PipelineState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_FRONTMATTER = """\
---
name: fullstack
display_name: "Full-Stack Web Application"
category: project
role_categories:
  - full_stack_engineer
  - frontend_engineer
  - backend_engineer
seniority_range: [junior, mid, senior, staff]
tech_stacks:
  primary: ["React", "Next.js", "FastAPI", "PostgreSQL"]
  alternatives: ["Vue", "Django"]
complexity_range: [3, 8]
estimated_loc: [800, 3000]
topology: hierarchical
---

## Overview

Generates full-stack web applications.
"""

_ML_FRONTMATTER = """\
---
name: ml-pipeline
display_name: "ML Pipeline"
category: project
role_categories:
  - ml_engineer
  - data_scientist
seniority_range: [mid, senior]
tech_stacks:
  primary: ["Python", "PyTorch", "MLflow"]
  alternatives: ["TensorFlow"]
complexity_range: [5, 9]
estimated_loc: [1000, 5000]
topology: sequential
---

## Overview

Generates ML pipeline projects.
"""

_INVALID_YAML = """\
---
name: broken
display_name: [this is not valid: yaml: {{{}}}
---

Some content.
"""

_NO_FRONTMATTER = """\
# Just a markdown file without YAML frontmatter

Some content here.
"""

_MISSING_FIELDS = """\
---
name: incomplete
display_name: "Incomplete Skill"
---

Missing required fields.
"""


def _make_jd_analysis(role_category: RoleCategory) -> JDAnalysis:
    """Create a minimal JDAnalysis for testing."""
    return JDAnalysis(
        role_title="Software Engineer",
        role_category=role_category,
        seniority=SeniorityLevel.MID,
        raw_text="Test JD text",
    )


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    """Create a temporary skills directory with sample skill files."""
    d = tmp_path / "skills"
    d.mkdir()
    (d / "fullstack.skill.md").write_text(_VALID_FRONTMATTER, encoding="utf-8")
    (d / "ml-pipeline.skill.md").write_text(_ML_FRONTMATTER, encoding="utf-8")
    return d


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loads_matching_skills(skills_dir: Path) -> None:
    """Skills matching the JD role_category are loaded; others are excluded."""
    middleware = SkillLoaderMiddleware(skills_directory=str(skills_dir))
    state = PipelineState(jd_analysis=_make_jd_analysis(RoleCategory.FULL_STACK))

    result = await middleware.before(state)

    assert len(result.skill_configs) == 1
    assert result.skill_configs[0].name == "fullstack"
    assert "full_stack_engineer" in result.skill_configs[0].role_categories


@pytest.mark.asyncio
async def test_no_jd_analysis_loads_all(skills_dir: Path) -> None:
    """When no JD analysis is available, all parseable skills are loaded."""
    middleware = SkillLoaderMiddleware(skills_directory=str(skills_dir))
    state = PipelineState()

    result = await middleware.before(state)

    assert len(result.skill_configs) == 2
    names = {s.name for s in result.skill_configs}
    assert names == {"fullstack", "ml-pipeline"}


@pytest.mark.asyncio
async def test_parse_frontmatter_valid(skills_dir: Path) -> None:
    """Valid YAML frontmatter is correctly parsed into a SkillConfig."""
    middleware = SkillLoaderMiddleware(skills_directory=str(skills_dir))
    config = middleware._parse_frontmatter(skills_dir / "fullstack.skill.md")

    assert config is not None
    assert isinstance(config, SkillConfig)
    assert config.name == "fullstack"
    assert config.display_name == "Full-Stack Web Application"
    assert config.category == "project"
    assert config.tech_stacks_primary == ["React", "Next.js", "FastAPI", "PostgreSQL"]
    assert config.tech_stacks_alternatives == ["Vue", "Django"]
    assert config.complexity_range == [3, 8]
    assert config.topology == "hierarchical"


@pytest.mark.asyncio
async def test_parse_frontmatter_invalid_returns_none(tmp_path: Path) -> None:
    """Invalid YAML or missing fields result in None (no crash)."""
    d = tmp_path / "skills"
    d.mkdir()

    # Invalid YAML
    invalid_file = d / "broken.skill.md"
    invalid_file.write_text(_INVALID_YAML, encoding="utf-8")

    # No frontmatter markers
    no_fm_file = d / "nofm.skill.md"
    no_fm_file.write_text(_NO_FRONTMATTER, encoding="utf-8")

    # Missing required fields
    missing_file = d / "incomplete.skill.md"
    missing_file.write_text(_MISSING_FIELDS, encoding="utf-8")

    middleware = SkillLoaderMiddleware(skills_directory=str(d))

    assert middleware._parse_frontmatter(invalid_file) is None
    assert middleware._parse_frontmatter(no_fm_file) is None
    assert middleware._parse_frontmatter(missing_file) is None


@pytest.mark.asyncio
async def test_no_skills_directory_handles_gracefully(tmp_path: Path) -> None:
    """Missing skills directory does not crash; state is returned unchanged."""
    nonexistent = tmp_path / "does_not_exist"
    middleware = SkillLoaderMiddleware(skills_directory=str(nonexistent))
    state = PipelineState()

    result = await middleware.before(state)

    assert result.skill_configs == []


@pytest.mark.asyncio
async def test_after_is_noop(skills_dir: Path) -> None:
    """after() returns state unchanged."""
    middleware = SkillLoaderMiddleware(skills_directory=str(skills_dir))
    state = PipelineState()
    state.skill_configs = [
        SkillConfig(
            name="test",
            display_name="Test",
            category="project",
            role_categories=["full_stack_engineer"],
            seniority_range=["mid"],
            tech_stacks_primary=["Python"],
            complexity_range=[1, 5],
            estimated_loc=[100, 500],
        ),
    ]

    result = await middleware.after(state)

    assert len(result.skill_configs) == 1
    assert result.skill_configs[0].name == "test"


@pytest.mark.asyncio
async def test_matches_role_method() -> None:
    """_matches_role correctly checks role_category membership."""
    middleware = SkillLoaderMiddleware()
    config = SkillConfig(
        name="test",
        display_name="Test",
        category="project",
        role_categories=["ml_engineer", "data_scientist"],
        seniority_range=["mid"],
        tech_stacks_primary=["Python"],
        complexity_range=[1, 5],
        estimated_loc=[100, 500],
    )

    assert middleware._matches_role(config, "ml_engineer") is True
    assert middleware._matches_role(config, "full_stack_engineer") is False
