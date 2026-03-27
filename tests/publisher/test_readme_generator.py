"""Tests for ReadmeGenerator — Jinja2 template-based README generation."""

from __future__ import annotations

from letsbuild.models.architect_models import (
    FeatureSpec,
    FileTreeNode,
    ProjectSpec,
    SandboxValidationCommand,
    SandboxValidationPlan,
)
from letsbuild.models.forge_models import ForgeOutput, ReviewVerdict, SwarmTopology
from letsbuild.publisher.readme_generator import ReadmeGenerator, _quality_badge_color

# ---------------------------------------------------------------------------
# _quality_badge_color unit tests
# ---------------------------------------------------------------------------


def test_quality_badge_color_above_90_is_brightgreen() -> None:
    assert _quality_badge_color(90.0) == "brightgreen"
    assert _quality_badge_color(95.0) == "brightgreen"
    assert _quality_badge_color(100.0) == "brightgreen"


def test_quality_badge_color_70_to_89_is_yellow() -> None:
    assert _quality_badge_color(70.0) == "yellow"
    assert _quality_badge_color(80.0) == "yellow"
    assert _quality_badge_color(89.9) == "yellow"


def test_quality_badge_color_below_70_is_red() -> None:
    assert _quality_badge_color(0.0) == "red"
    assert _quality_badge_color(50.0) == "red"
    assert _quality_badge_color(69.9) == "red"


# ---------------------------------------------------------------------------
# Required README sections
# ---------------------------------------------------------------------------


REQUIRED_SECTIONS = [
    "# MyFastAPI Project",  # title (h1)
    "## Architecture",  # mermaid diagram section
    "## Features",  # features section
    "## Quick Start",  # quick start
    "## Tech Stack",  # tech stack table
    "## Project Structure",  # file tree
    "## Architecture Decision Records",  # ADRs section
    "## Testing",  # testing section
    "## Contributing",  # contributing section
    "## License",  # license section
]


def test_generate_contains_all_required_sections(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """The generated README must contain all required sections."""
    gen = ReadmeGenerator()
    readme = gen.generate(sample_project_spec, sample_forge_output)

    for section in REQUIRED_SECTIONS:
        assert section in readme, f"Missing required section: {section!r}"


def test_generate_contains_project_name(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """The README h1 heading must be the project name."""
    gen = ReadmeGenerator()
    readme = gen.generate(sample_project_spec, sample_forge_output)

    assert f"# {sample_project_spec.project_name}" in readme


def test_generate_contains_one_liner(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """The project one_liner must appear in the README."""
    gen = ReadmeGenerator()
    readme = gen.generate(sample_project_spec, sample_forge_output)

    assert sample_project_spec.one_liner in readme


def test_generate_contains_quality_badge(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """A quality badge with score must appear in the README."""
    gen = ReadmeGenerator()
    readme = gen.generate(sample_project_spec, sample_forge_output)

    # Quality score is 85.0 → badge shows 85%
    assert "quality" in readme.lower()
    assert "85" in readme


def test_generate_contains_tech_stack_entries(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """Each tech stack item should appear in the README tech stack table."""
    gen = ReadmeGenerator()
    readme = gen.generate(sample_project_spec, sample_forge_output)

    for tech in sample_project_spec.tech_stack:
        assert tech in readme, f"Tech stack item missing from README: {tech!r}"


def test_generate_contains_feature_names(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """Each feature_spec name should appear in the README features section."""
    gen = ReadmeGenerator()
    readme = gen.generate(sample_project_spec, sample_forge_output)

    for feat in sample_project_spec.feature_specs:
        assert feat.feature_name in readme, f"Feature name missing: {feat.feature_name!r}"


def test_generate_contains_adr_titles_when_adrs_present(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """ADR titles should appear in the ADRs section when adr_list is non-empty."""
    assert len(sample_project_spec.adr_list) > 0
    gen = ReadmeGenerator()
    readme = gen.generate(sample_project_spec, sample_forge_output)

    for adr in sample_project_spec.adr_list:
        assert adr.title in readme, f"ADR title missing: {adr.title!r}"


def test_generate_contains_adr_directory_reference(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """The ADR section must include a reference to docs/decisions/."""
    assert len(sample_project_spec.adr_list) > 0
    gen = ReadmeGenerator()
    readme = gen.generate(sample_project_spec, sample_forge_output)

    assert "docs/decisions/" in readme


def test_generate_contains_mermaid_block(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """The README should include a mermaid flowchart block."""
    gen = ReadmeGenerator()
    readme = gen.generate(sample_project_spec, sample_forge_output)

    assert "```mermaid" in readme
    assert "flowchart TD" in readme


def test_generate_contains_repo_clone_slug(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """The quick-start section must include a git clone command with the slug."""
    gen = ReadmeGenerator()
    readme = gen.generate(sample_project_spec, sample_forge_output)

    # Project name "MyFastAPI Project" → slug "myfastapi-project"
    assert "myfastapi-project" in readme


def test_generate_contains_letsbuild_attribution(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """The README must credit LetsBuild as the generator."""
    gen = ReadmeGenerator()
    readme = gen.generate(sample_project_spec, sample_forge_output)

    assert "LetsBuild" in readme


# ---------------------------------------------------------------------------
# Badge colour coding
# ---------------------------------------------------------------------------


def test_generate_uses_brightgreen_badge_for_high_quality_score() -> None:
    """Quality score ≥ 90 should produce a brightgreen badge."""

    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output_with_score(95.0)

    gen = ReadmeGenerator()
    readme = gen.generate(project_spec, forge_output)

    assert "brightgreen" in readme


def test_generate_uses_yellow_badge_for_mid_quality_score() -> None:
    """Quality score between 70 and 89 should produce a yellow badge."""
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output_with_score(75.0)

    gen = ReadmeGenerator()
    readme = gen.generate(project_spec, forge_output)

    assert "yellow" in readme


def test_generate_uses_red_badge_for_low_quality_score() -> None:
    """Quality score below 70 should produce a red badge."""
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output_with_score(55.0)

    gen = ReadmeGenerator()
    readme = gen.generate(project_spec, forge_output)

    assert "red" in readme


# ---------------------------------------------------------------------------
# Minimal ProjectSpec (edge case)
# ---------------------------------------------------------------------------


def test_generate_with_no_adrs_shows_placeholder() -> None:
    """When adr_list is empty, README should show the 'No ADRs' placeholder."""
    project_spec = _make_minimal_project_spec()  # no ADRs
    forge_output = _make_forge_output_with_score(80.0)

    gen = ReadmeGenerator()
    readme = gen.generate(project_spec, forge_output)

    assert "No ADRs" in readme


def test_generate_with_no_test_results_omits_test_table() -> None:
    """When test_results is empty, the test table section should not appear."""
    project_spec = _make_minimal_project_spec()
    forge_output = ForgeOutput(
        code_modules=[],
        test_results={},  # empty
        review_verdict=ReviewVerdict.PASS,
        quality_score=80.0,
        total_tokens_used=0,
        total_retries=0,
        topology_used=SwarmTopology.HIERARCHICAL,
    )

    gen = ReadmeGenerator()
    readme = gen.generate(project_spec, forge_output)

    # "Test Results" subsection should not appear
    assert "### Test Results" not in readme


def test_generate_with_test_results_shows_test_table() -> None:
    """When test_results is populated, the test table should appear."""
    project_spec = _make_minimal_project_spec()
    forge_output = ForgeOutput(
        code_modules=[],
        test_results={"test_foo": True, "test_bar": False},
        review_verdict=ReviewVerdict.PASS,
        quality_score=80.0,
        total_tokens_used=0,
        total_retries=0,
        topology_used=SwarmTopology.HIERARCHICAL,
    )

    gen = ReadmeGenerator()
    readme = gen.generate(project_spec, forge_output)

    assert "### Test Results" in readme
    assert "test_foo" in readme
    assert "test_bar" in readme


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_minimal_project_spec() -> ProjectSpec:
    """Minimal ProjectSpec with no ADRs and one feature."""
    return ProjectSpec(
        project_name="Test Project",
        one_liner="A minimal test project.",
        tech_stack=["python"],
        file_tree=[FileTreeNode(path="src", is_directory=True)],
        feature_specs=[
            FeatureSpec(
                feature_name="Core",
                description="Core module.",
                module_path="src/core.py",
                estimated_complexity=3,
            )
        ],
        sandbox_validation_plan=SandboxValidationPlan(
            commands=[
                SandboxValidationCommand(command="pip install -e .", description="Install"),
                SandboxValidationCommand(command="pytest tests/", description="Test"),
                SandboxValidationCommand(command="ruff check .", description="Lint"),
            ]
        ),
        adr_list=[],  # no ADRs
        skill_name="fullstack",
        complexity_score=3.0,
        estimated_loc=100,
        seniority_target="junior",
    )


def _make_forge_output_with_score(score: float) -> ForgeOutput:
    return ForgeOutput(
        code_modules=[],
        test_results={},
        review_verdict=ReviewVerdict.PASS,
        quality_score=score,
        total_tokens_used=0,
        total_retries=0,
        topology_used=SwarmTopology.HIERARCHICAL,
    )
