"""Integration tests for the Project Architect layer (Layer 4).

These tests exercise the architect pipeline end-to-end using the
heuristic fallback (no real LLM calls) and verify cross-component
interactions between engine, skill_parser, adr_generator,
validation_planner, and memory_advisor.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from letsbuild.architect.adr_generator import ADRGenerator
from letsbuild.architect.engine import ProjectArchitect
from letsbuild.architect.memory_advisor import MemoryAdvisor
from letsbuild.architect.skill_parser import SkillParser
from letsbuild.architect.validation_planner import ValidationPlanner
from letsbuild.models.architect_models import (
    ADR,
    ADRStatus,
    FeatureSpec,
    FileTreeNode,
    ProjectSpec,
    SandboxValidationPlan,
)
from letsbuild.models.config_models import SkillConfig
from letsbuild.models.intake_models import (
    JDAnalysis,
    RoleCategory,
    SeniorityLevel,
    Skill,
    TechStack,
)
from letsbuild.models.intelligence_models import CompanyProfile
from letsbuild.models.matcher_models import (
    DimensionScore,
    GapAnalysis,
    GapCategory,
    GapItem,
    MatchDimension,
    MatchScore,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"

# ---------------------------------------------------------------------------
# Helpers — build test model instances
# ---------------------------------------------------------------------------


def make_jd_analysis(
    *,
    role_title: str = "Senior Backend Engineer",
    role_category: RoleCategory = RoleCategory.BACKEND,
    seniority: SeniorityLevel = SeniorityLevel.SENIOR,
    languages: list[str] | None = None,
    frameworks: list[str] | None = None,
    databases: list[str] | None = None,
    domain_keywords: list[str] | None = None,
    key_responsibilities: list[str] | None = None,
    company_name: str | None = "TestCo",
) -> JDAnalysis:
    """Build a JDAnalysis with sensible defaults for integration tests."""
    return JDAnalysis(
        role_title=role_title,
        role_category=role_category,
        seniority=seniority,
        company_name=company_name,
        required_skills=[
            Skill(name="Python", category="language", is_primary=True),
        ],
        tech_stack=TechStack(
            languages=languages or ["python"],
            frameworks=frameworks or ["fastapi"],
            databases=databases or ["postgresql"],
        ),
        domain_keywords=domain_keywords or ["fintech"],
        key_responsibilities=key_responsibilities
        or [
            "Design and build REST APIs",
            "Implement authentication and authorisation",
            "Write comprehensive test suites",
        ],
        raw_text="Integration test JD placeholder text.",
    )


def make_company_profile(
    *,
    company_name: str = "Acme Corp",
    industry: str = "Fintech",
    tech_stack_signals: list[str] | None = None,
    business_context: str | None = "Leading digital payments platform.",
) -> CompanyProfile:
    """Build a CompanyProfile for integration tests."""
    return CompanyProfile(
        company_name=company_name,
        industry=industry,
        tech_stack_signals=tech_stack_signals or ["python", "fastapi", "postgresql"],
        business_context=business_context,
        confidence_score=85.0,
    )


def make_gap_analysis(
    *,
    overall_score: float = 72.0,
    demonstrable_gaps: list[GapItem] | None = None,
    recommended_focus: list[str] | None = None,
) -> GapAnalysis:
    """Build a GapAnalysis with demonstrable gaps for integration tests."""
    if demonstrable_gaps is None:
        demonstrable_gaps = [
            GapItem(
                skill_name="Kubernetes",
                category=GapCategory.DEMONSTRABLE_GAP,
                confidence=80.0,
                evidence="Not in existing portfolio.",
                suggested_project_demo="Add container orchestration to project.",
            ),
            GapItem(
                skill_name="CI/CD",
                category=GapCategory.DEMONSTRABLE_GAP,
                confidence=75.0,
                evidence="No CI/CD examples in portfolio.",
                suggested_project_demo="Include GitHub Actions workflows.",
            ),
        ]

    return GapAnalysis(
        match_score=MatchScore(
            overall_score=overall_score,
            dimension_scores=[
                DimensionScore(
                    dimension=MatchDimension.HARD_SKILLS,
                    score=80.0,
                    weight=0.30,
                    weighted_score=24.0,
                    details="Strong Python skills.",
                ),
                DimensionScore(
                    dimension=MatchDimension.TECH_STACK,
                    score=70.0,
                    weight=0.20,
                    weighted_score=14.0,
                    details="Missing Kubernetes.",
                ),
                DimensionScore(
                    dimension=MatchDimension.DOMAIN,
                    score=60.0,
                    weight=0.15,
                    weighted_score=9.0,
                    details="Some fintech exposure.",
                ),
                DimensionScore(
                    dimension=MatchDimension.PORTFOLIO,
                    score=50.0,
                    weight=0.15,
                    weighted_score=7.5,
                    details="Portfolio gaps exist.",
                ),
                DimensionScore(
                    dimension=MatchDimension.SENIORITY,
                    score=80.0,
                    weight=0.10,
                    weighted_score=8.0,
                    details="Experience aligns.",
                ),
                DimensionScore(
                    dimension=MatchDimension.SOFT_SKILLS,
                    score=95.0,
                    weight=0.10,
                    weighted_score=9.5,
                    details="Good communication.",
                ),
            ],
            ats_predicted_score=72.0,
        ),
        strong_matches=[
            GapItem(
                skill_name="Python",
                category=GapCategory.STRONG_MATCH,
                confidence=95.0,
                evidence="Extensive Python experience.",
            ),
        ],
        demonstrable_gaps=demonstrable_gaps,
        learnable_gaps=[],
        hard_gaps=[],
        portfolio_redundancy=[],
        recommended_project_focus=recommended_focus or ["Kubernetes", "CI/CD", "observability"],
        analysis_summary="Candidate has strong Python skills but gaps in Kubernetes and CI/CD.",
    )


def make_skill_config(
    *,
    name: str = "backend-api",
    display_name: str = "Backend API Service",
    topology: str = "hierarchical",
) -> SkillConfig:
    """Build a minimal SkillConfig for integration tests."""
    return SkillConfig(
        name=name,
        display_name=display_name,
        category="project",
        role_categories=["backend_engineer"],
        seniority_range=["junior", "mid", "senior"],
        tech_stacks_primary=["Python", "FastAPI"],
        complexity_range=[3, 8],
        estimated_loc=[800, 2500],
        topology=topology,
    )


# ---------------------------------------------------------------------------
# 1. Full pipeline — heuristic fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_full_architect_pipeline() -> None:
    """Full architect pipeline via heuristic fallback produces complete ProjectSpec."""
    jd = make_jd_analysis()
    company = make_company_profile()
    gap = make_gap_analysis()
    skill = make_skill_config()

    architect = ProjectArchitect(llm_client=None)
    spec = await architect.design(
        jd_analysis=jd,
        company_profile=company,
        gap_analysis=gap,
        skill_config=skill,
    )

    assert isinstance(spec, ProjectSpec)

    # project_name is populated and kebab-case
    assert spec.project_name
    assert " " not in spec.project_name

    # file_tree is non-empty and has directories
    assert len(spec.file_tree) > 0
    assert any(node.is_directory for node in spec.file_tree)

    # feature_specs derived from key_responsibilities
    assert len(spec.feature_specs) >= 1
    for feat in spec.feature_specs:
        assert isinstance(feat, FeatureSpec)
        assert feat.feature_name
        assert feat.description

    # validation_plan meets the >=3 commands minimum
    assert isinstance(spec.sandbox_validation_plan, SandboxValidationPlan)
    assert len(spec.sandbox_validation_plan.commands) >= 3

    # adr_list is populated
    assert len(spec.adr_list) >= 1
    for adr in spec.adr_list:
        assert isinstance(adr, ADR)
        assert adr.title
        assert adr.status in ADRStatus

    # skill_name set from SkillConfig
    assert spec.skill_name == "backend-api"

    # seniority and complexity populated
    assert spec.seniority_target == "senior"
    assert 1.0 <= spec.complexity_score <= 10.0
    assert spec.estimated_loc > 0


# ---------------------------------------------------------------------------
# 2. Architect with real skill file parsing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_architect_with_skill_parser() -> None:
    """Parse fullstack.skill.md, extract SkillConfig, pass to architect."""
    skill_path = _SKILLS_DIR / "fullstack.skill.md"
    assert skill_path.exists(), f"Skill file not found: {skill_path}"

    parser = SkillParser()
    parsed = parser.parse(skill_path)
    assert parsed.config.name == "fullstack"

    jd = make_jd_analysis(
        role_category=RoleCategory.FULL_STACK,
        frameworks=["react", "fastapi"],
    )

    architect = ProjectArchitect(llm_client=None)
    spec = await architect.design(jd_analysis=jd, skill_config=parsed.config)

    assert isinstance(spec, ProjectSpec)
    assert spec.skill_name == "fullstack"
    assert spec.project_name
    assert len(spec.feature_specs) >= 1


# ---------------------------------------------------------------------------
# 3. Validation plan matches tech stack
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_architect_validation_plan_matches_tech() -> None:
    """Python tech stack produces pip/pytest commands in validation plan."""
    jd = make_jd_analysis(languages=["python"], frameworks=["fastapi"])

    architect = ProjectArchitect(llm_client=None)
    spec = await architect.design(jd_analysis=jd)

    commands_text = " ".join(cmd.command for cmd in spec.sandbox_validation_plan.commands)
    assert "pip" in commands_text
    assert "pytest" in commands_text


@pytest.mark.asyncio()
async def test_architect_validation_plan_node_tech() -> None:
    """Node/TypeScript tech stack produces npm commands in validation plan."""
    jd = make_jd_analysis(
        role_category=RoleCategory.FRONTEND,
        languages=["typescript"],
        frameworks=["react"],
        databases=[],
    )

    architect = ProjectArchitect(llm_client=None)
    spec = await architect.design(jd_analysis=jd)

    commands_text = " ".join(cmd.command for cmd in spec.sandbox_validation_plan.commands)
    assert "npm" in commands_text


# ---------------------------------------------------------------------------
# 4. ADR generation reflects technology choices
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_architect_adr_generation() -> None:
    """Design with React + FastAPI produces ADRs that mention these technologies."""
    jd = make_jd_analysis(
        role_category=RoleCategory.FULL_STACK,
        languages=["python", "typescript"],
        frameworks=["react", "fastapi"],
    )

    # Use the standalone ADRGenerator to verify tech-driven ADRs.
    gen = ADRGenerator()
    adrs = gen.generate(
        project_name="fullstack-demo",
        tech_choices=["react", "fastapi", "postgresql"],
    )

    adr_titles_lower = " ".join(a.title.lower() for a in adrs)
    assert "react" in adr_titles_lower
    assert "fastapi" in adr_titles_lower

    # Also verify via the full architect path.
    architect = ProjectArchitect(llm_client=None)
    spec = await architect.design(jd_analysis=jd)

    # The heuristic ADRs reference the primary tech.
    all_adr_text = " ".join(a.title.lower() + " " + a.context.lower() for a in spec.adr_list)
    assert "python" in all_adr_text or "fastapi" in all_adr_text


# ---------------------------------------------------------------------------
# 5. Complexity varies by seniority
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_architect_complexity_by_seniority() -> None:
    """Junior, mid, and senior produce different complexity scores."""
    architect = ProjectArchitect(llm_client=None)

    specs: dict[str, ProjectSpec] = {}
    for level in [SeniorityLevel.JUNIOR, SeniorityLevel.MID, SeniorityLevel.SENIOR]:
        jd = make_jd_analysis(seniority=level)
        spec = await architect.design(jd_analysis=jd)
        specs[level.value] = spec

    assert specs["junior"].complexity_score < specs["mid"].complexity_score
    assert specs["mid"].complexity_score < specs["senior"].complexity_score

    # Estimated LOC should also increase with seniority.
    assert specs["junior"].estimated_loc < specs["mid"].estimated_loc
    assert specs["mid"].estimated_loc < specs["senior"].estimated_loc


# ---------------------------------------------------------------------------
# 6. Company context influences design
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_architect_with_company_context() -> None:
    """CompanyProfile influences the generated project name."""
    company = make_company_profile(
        company_name="HealthTech Inc",
        industry="Healthcare Technology",
    )
    jd = make_jd_analysis(domain_keywords=["healthtech", "ehr"])

    architect = ProjectArchitect(llm_client=None)
    spec = await architect.design(jd_analysis=jd, company_profile=company)

    assert isinstance(spec, ProjectSpec)
    # Industry keyword "healthcare" should influence project name.
    assert "healthcare" in spec.project_name or "healthtech" in spec.project_name.replace("-", "")


# ---------------------------------------------------------------------------
# 7. Gap analysis drives skill coverage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_architect_with_gap_analysis() -> None:
    """Demonstrable gaps from GapAnalysis appear in skill_coverage_map."""
    gap = make_gap_analysis(
        demonstrable_gaps=[
            GapItem(
                skill_name="GraphQL",
                category=GapCategory.DEMONSTRABLE_GAP,
                confidence=85.0,
                evidence="No GraphQL in portfolio.",
                suggested_project_demo="Add a GraphQL API layer.",
            ),
            GapItem(
                skill_name="Redis caching",
                category=GapCategory.DEMONSTRABLE_GAP,
                confidence=70.0,
                evidence="No caching examples.",
                suggested_project_demo="Implement Redis caching for hot paths.",
            ),
        ],
    )
    jd = make_jd_analysis()

    architect = ProjectArchitect(llm_client=None)
    spec = await architect.design(jd_analysis=jd, gap_analysis=gap)

    assert len(spec.skill_coverage_map) > 0
    assert "GraphQL" in spec.skill_coverage_map
    assert "Redis caching" in spec.skill_coverage_map


# ---------------------------------------------------------------------------
# 8. All skill files parse successfully
# ---------------------------------------------------------------------------


def test_skill_files_all_parse() -> None:
    """All .skill.md files in skills/ parse without errors."""
    skill_files = sorted(_SKILLS_DIR.glob("*.skill.md"))
    assert len(skill_files) == 5, f"Expected 5 skill files, found {len(skill_files)}"

    parser = SkillParser()
    for skill_file in skill_files:
        parsed = parser.parse(skill_file)
        assert parsed.config.name, f"Skill name empty in {skill_file.name}"
        assert parsed.config.display_name, f"Skill display_name empty in {skill_file.name}"
        assert parsed.config.category, f"Skill category empty in {skill_file.name}"
        assert len(parsed.config.role_categories) >= 1, f"No role_categories in {skill_file.name}"
        assert len(parsed.config.tech_stacks_primary) >= 1, (
            f"No tech_stacks_primary in {skill_file.name}"
        )
        assert len(parsed.config.complexity_range) == 2, (
            f"complexity_range not [min, max] in {skill_file.name}"
        )


# ---------------------------------------------------------------------------
# 9. ValidationPlanner standalone integration
# ---------------------------------------------------------------------------


def test_validation_planner_python_stack() -> None:
    """ValidationPlanner produces pip/pytest/ruff for Python tech stacks."""
    planner = ValidationPlanner()
    plan = planner.generate(tech_stack=["python", "fastapi", "postgresql"])

    assert len(plan.commands) >= 3
    commands_text = " ".join(c.command for c in plan.commands)
    assert "pip install" in commands_text
    assert "pytest" in commands_text
    assert "ruff" in commands_text


def test_validation_planner_node_stack() -> None:
    """ValidationPlanner produces npm commands for Node tech stacks."""
    planner = ValidationPlanner()
    plan = planner.generate(tech_stack=["typescript", "react", "next.js"])

    assert len(plan.commands) >= 3
    commands_text = " ".join(c.command for c in plan.commands)
    assert "npm install" in commands_text
    assert "npm test" in commands_text


def test_validation_planner_go_stack() -> None:
    """ValidationPlanner produces go build/test for Go tech stacks."""
    planner = ValidationPlanner()
    plan = planner.generate(tech_stack=["go", "gin"])

    assert len(plan.commands) >= 3
    commands_text = " ".join(c.command for c in plan.commands)
    assert "go build" in commands_text
    assert "go test" in commands_text


def test_validation_planner_rust_stack() -> None:
    """ValidationPlanner produces cargo commands for Rust tech stacks."""
    planner = ValidationPlanner()
    plan = planner.generate(tech_stack=["rust", "tokio"])

    assert len(plan.commands) >= 3
    commands_text = " ".join(c.command for c in plan.commands)
    assert "cargo build" in commands_text
    assert "cargo test" in commands_text


# ---------------------------------------------------------------------------
# 10. MemoryAdvisor cold start
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_memory_advisor_cold_start() -> None:
    """MemoryAdvisor with no store returns empty recommendations."""
    advisor = MemoryAdvisor(memory_store=None)
    jd = make_jd_analysis()

    advice = await advisor.get_recommendations(jd)
    assert advice.cold_start is True
    assert advice.confidence == 0.0
    assert len(advice.patterns) == 0
    assert len(advice.suggestions) == 0


# ---------------------------------------------------------------------------
# 11. ADRGenerator minimum guarantee
# ---------------------------------------------------------------------------


def test_adr_generator_minimum_two() -> None:
    """ADRGenerator always produces at least 2 ADRs even with unknown tech."""
    gen = ADRGenerator()
    adrs = gen.generate(project_name="unknown-project", tech_choices=["obscure-lang"])

    assert len(adrs) >= 2
    for adr in adrs:
        assert adr.title
        assert adr.context
        assert adr.decision
        assert adr.consequences
        assert adr.status == ADRStatus.ACCEPTED


def test_adr_generator_with_templates() -> None:
    """ADRGenerator expands skill ADR templates into full ADRs."""
    gen = ADRGenerator()
    templates = ["Use event sourcing for audit trail", "Implement CQRS pattern"]
    adrs = gen.generate(
        project_name="event-driven-app",
        tech_choices=["fastapi"],
        skill_adr_templates=templates,
    )

    # Should have fastapi ADR + 2 template ADRs.
    assert len(adrs) >= 3
    titles = [a.title for a in adrs]
    assert any("event sourcing" in t.lower() for t in titles)
    assert any("cqrs" in t.lower() for t in titles)


# ---------------------------------------------------------------------------
# 12. End-to-end: Architect + ADRGenerator + ValidationPlanner combined
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_architect_end_to_end_all_components() -> None:
    """Full integration: architect design + standalone planner + ADR gen produce consistent output."""
    jd = make_jd_analysis(
        role_category=RoleCategory.FULL_STACK,
        languages=["python", "typescript"],
        frameworks=["fastapi", "react"],
    )
    company = make_company_profile(industry="E-commerce")
    gap = make_gap_analysis()
    skill = make_skill_config(name="fullstack-app", display_name="Full-Stack Application")

    # Design via architect.
    architect = ProjectArchitect(llm_client=None)
    spec = await architect.design(
        jd_analysis=jd,
        company_profile=company,
        gap_analysis=gap,
        skill_config=skill,
    )

    # Separately generate validation plan and ADRs.
    planner = ValidationPlanner()
    plan = planner.generate(
        tech_stack=jd.tech_stack.languages + jd.tech_stack.frameworks,
        skill_config=skill,
    )

    gen = ADRGenerator()
    adrs = gen.generate(
        project_name=spec.project_name,
        tech_choices=jd.tech_stack.frameworks,
    )

    # All outputs are valid.
    assert isinstance(spec, ProjectSpec)
    assert len(plan.commands) >= 3
    assert len(adrs) >= 2

    # Architect's own plan and standalone plan should agree on stack type.
    architect_cmds = " ".join(c.command for c in spec.sandbox_validation_plan.commands)
    standalone_cmds = " ".join(c.command for c in plan.commands)
    # Both should target Python since python is in the tech stack.
    assert "pip" in architect_cmds
    assert "pip" in standalone_cmds


# ---------------------------------------------------------------------------
# 13. Architect without any optional inputs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_architect_minimal_inputs() -> None:
    """Architect produces valid ProjectSpec with only JDAnalysis (no company, gap, or skill)."""
    jd = make_jd_analysis()

    architect = ProjectArchitect(llm_client=None)
    spec = await architect.design(jd_analysis=jd)

    assert isinstance(spec, ProjectSpec)
    assert spec.project_name
    assert spec.skill_name == "general"
    assert len(spec.file_tree) > 0
    assert len(spec.feature_specs) >= 1
    assert len(spec.sandbox_validation_plan.commands) >= 3
    assert len(spec.adr_list) >= 1
    assert spec.skill_coverage_map == {}


# ---------------------------------------------------------------------------
# 14. File tree matches detected stack type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_architect_file_tree_python_structure() -> None:
    """Python tech stack produces pyproject.toml and src/ in the file tree."""
    jd = make_jd_analysis(languages=["python"], frameworks=["fastapi"])

    architect = ProjectArchitect(llm_client=None)
    spec = await architect.design(jd_analysis=jd)

    all_paths = _collect_file_tree_paths(spec.file_tree)
    assert "pyproject.toml" in all_paths
    assert any(p.startswith("src/") for p in all_paths)
    assert any(p.startswith("tests/") for p in all_paths)
    # Common files always present
    assert "README.md" in all_paths
    assert ".gitignore" in all_paths
    assert any("docs/decisions/" in p for p in all_paths)


@pytest.mark.asyncio()
async def test_architect_file_tree_node_structure() -> None:
    """TypeScript/React tech stack produces package.json and tsconfig.json."""
    jd = make_jd_analysis(
        role_category=RoleCategory.FRONTEND,
        languages=["typescript"],
        frameworks=["react"],
        databases=[],
    )

    architect = ProjectArchitect(llm_client=None)
    spec = await architect.design(jd_analysis=jd)

    all_paths = _collect_file_tree_paths(spec.file_tree)
    assert "package.json" in all_paths
    assert "tsconfig.json" in all_paths


# ---------------------------------------------------------------------------
# 15. Project name sanitisation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_architect_project_name_kebab_case() -> None:
    """Project name is always valid kebab-case (lowercase, hyphens, alphanumeric)."""
    import re

    cases = [
        {"domain_keywords": ["E-Commerce"], "company_name": "Acme Corp!"},
        {"domain_keywords": ["Machine Learning"], "company_name": None},
        {"domain_keywords": [], "company_name": None},
    ]

    architect = ProjectArchitect(llm_client=None)
    for kwargs in cases:
        jd = make_jd_analysis(**kwargs)  # type: ignore[arg-type]
        spec = await architect.design(jd_analysis=jd)
        assert re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", spec.project_name), (
            f"Invalid project name: {spec.project_name!r}"
        )


# ---------------------------------------------------------------------------
# 16. Staff and principal seniority levels
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_architect_staff_and_principal_seniority() -> None:
    """Staff and principal produce higher complexity than senior."""
    architect = ProjectArchitect(llm_client=None)

    senior_spec = await architect.design(
        jd_analysis=make_jd_analysis(seniority=SeniorityLevel.SENIOR)
    )
    staff_spec = await architect.design(
        jd_analysis=make_jd_analysis(seniority=SeniorityLevel.STAFF)
    )
    principal_spec = await architect.design(
        jd_analysis=make_jd_analysis(seniority=SeniorityLevel.PRINCIPAL)
    )

    assert staff_spec.complexity_score > senior_spec.complexity_score
    assert principal_spec.complexity_score > staff_spec.complexity_score
    assert principal_spec.estimated_loc > staff_spec.estimated_loc


# ---------------------------------------------------------------------------
# 17. Feature specs derived from key responsibilities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_architect_feature_specs_from_responsibilities() -> None:
    """Each key responsibility produces a corresponding feature spec."""
    responsibilities = [
        "Build real-time data pipeline",
        "Implement user authentication system",
        "Design rate limiting middleware",
        "Create monitoring dashboard",
    ]
    jd = make_jd_analysis(key_responsibilities=responsibilities)

    architect = ProjectArchitect(llm_client=None)
    spec = await architect.design(jd_analysis=jd)

    assert len(spec.feature_specs) == len(responsibilities)
    for feat in spec.feature_specs:
        assert feat.description in responsibilities
        assert feat.module_path
        assert 1 <= feat.estimated_complexity <= 10
        assert len(feat.acceptance_criteria) >= 1


# ---------------------------------------------------------------------------
# 18. Empty key responsibilities fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_architect_empty_responsibilities_fallback() -> None:
    """Architect creates a fallback feature when key_responsibilities is empty."""
    # Build JDAnalysis directly to bypass the helper's default key_responsibilities.
    jd = JDAnalysis(
        role_title="Backend Engineer",
        role_category=RoleCategory.BACKEND,
        seniority=SeniorityLevel.MID,
        tech_stack=TechStack(languages=["python"], frameworks=["fastapi"]),
        key_responsibilities=[],
        raw_text="Empty responsibilities test.",
    )

    architect = ProjectArchitect(llm_client=None)
    spec = await architect.design(jd_analysis=jd)

    assert len(spec.feature_specs) >= 1
    # Fallback feature should reference the role category
    assert "backend" in spec.feature_specs[0].description.lower()


# ---------------------------------------------------------------------------
# 19. Non-hierarchical topology in skill triggers ADR
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_architect_non_hierarchical_topology_adr() -> None:
    """A skill with mesh topology adds a topology ADR to the spec."""
    skill = make_skill_config(topology="mesh")
    jd = make_jd_analysis()

    architect = ProjectArchitect(llm_client=None)
    spec = await architect.design(jd_analysis=jd, skill_config=skill)

    topology_adrs = [a for a in spec.adr_list if "mesh" in a.title.lower()]
    assert len(topology_adrs) >= 1
    assert "mesh" in topology_adrs[0].context.lower()


# ---------------------------------------------------------------------------
# 20. Skill parser validates missing sections
# ---------------------------------------------------------------------------


def test_skill_parser_missing_sections_reported() -> None:
    """SkillParser reports missing sections without raising exceptions."""
    import tempfile

    content = (
        "---\n"
        "name: test-partial\n"
        "display_name: Partial Skill\n"
        "category: project\n"
        "role_categories: [backend_engineer]\n"
        "seniority_range: [junior, mid]\n"
        "tech_stacks:\n"
        "  primary: [Python]\n"
        "  alternatives: []\n"
        "complexity_range: [2, 5]\n"
        "estimated_loc: [300, 800]\n"
        "topology: sequential\n"
        "---\n\n"
        "## Overview\n\nA test skill.\n\n"
        "## Project Templates\n\nTemplate content.\n"
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".skill.md", delete=False) as f:
        f.write(content)
        f.flush()
        parser = SkillParser()
        parsed = parser.parse(f.name)

    assert not parsed.is_valid
    assert len(parsed.missing_sections) > 0
    # Should be missing sections like Architecture Patterns, File Tree Template, etc.
    assert "Architecture Patterns" in parsed.missing_sections
    assert parsed.config.name == "test-partial"
    assert parsed.config.topology == "sequential"


# ---------------------------------------------------------------------------
# 21. ADRGenerator deduplicates tech entries
# ---------------------------------------------------------------------------


def test_adr_generator_deduplicates_tech() -> None:
    """ADRGenerator does not produce duplicate ADRs for repeated tech entries."""
    gen = ADRGenerator()
    adrs = gen.generate(
        project_name="dedup-test",
        tech_choices=["react", "React", "REACT", "react"],
    )

    react_adrs = [a for a in adrs if "react" in a.title.lower()]
    assert len(react_adrs) == 1


# ---------------------------------------------------------------------------
# 22. MemoryAdvisor with mock store
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_memory_advisor_with_mock_store() -> None:
    """MemoryAdvisor with a mock store returns patterns and suggestions."""
    from letsbuild.models.memory_models import DistilledPattern

    mock_pattern = DistilledPattern(
        pattern_id="pat-001",
        pattern_text="Use repository pattern for data access",
        source_verdicts=["verdict-001", "verdict-002"],
        tech_stack_tags=["python", "fastapi"],
        confidence=85.0,
        success_rate=90.0,
        sample_count=15,
    )

    class MockMemoryStore:
        async def query_patterns(self, query: object) -> list[DistilledPattern]:
            return [mock_pattern]

    advisor = MemoryAdvisor(memory_store=MockMemoryStore())  # type: ignore[arg-type]
    jd = make_jd_analysis()

    advice = await advisor.get_recommendations(jd)
    assert advice.cold_start is False
    assert len(advice.patterns) == 1
    assert len(advice.suggestions) == 1
    assert advice.confidence > 0.0
    assert "repository pattern" in advice.suggestions[0].lower()


# ---------------------------------------------------------------------------
# 23. ValidationPlanner with skill config
# ---------------------------------------------------------------------------


def test_validation_planner_with_skill_config() -> None:
    """ValidationPlanner uses skill config to set extra_packages."""
    skill = make_skill_config()
    planner = ValidationPlanner()
    plan = planner.generate(tech_stack=["python", "fastapi"], skill_config=skill)

    assert len(plan.commands) >= 3
    assert plan.base_image == "letsbuild/sandbox:latest"
    assert len(plan.extra_packages) > 0


# ---------------------------------------------------------------------------
# 24. Each skill file parses with valid sections
# ---------------------------------------------------------------------------


def test_all_skill_files_have_overview_and_templates() -> None:
    """Every skill file has at least Overview and Project Templates sections."""
    skill_files = sorted(_SKILLS_DIR.glob("*.skill.md"))
    parser = SkillParser()

    for skill_file in skill_files:
        parsed = parser.parse(skill_file)
        assert "Overview" in parsed.sections, f"Missing Overview in {skill_file.name}"
        assert "Project Templates" in parsed.sections, (
            f"Missing Project Templates in {skill_file.name}"
        )
        # Overview should have substantive content
        assert len(parsed.sections["Overview"]) > 50, f"Overview too short in {skill_file.name}"


# ---------------------------------------------------------------------------
# 25. Architect with ML role category
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_architect_ml_role_category() -> None:
    """ML engineer role produces valid spec with ML-relevant structure."""
    jd = make_jd_analysis(
        role_title="ML Engineer",
        role_category=RoleCategory.ML_ENGINEER,
        languages=["python"],
        frameworks=["pytorch", "fastapi"],
        domain_keywords=["machine-learning", "deep-learning"],
        key_responsibilities=[
            "Train and evaluate ML models",
            "Build model serving API",
            "Implement data preprocessing pipeline",
        ],
    )

    architect = ProjectArchitect(llm_client=None)
    spec = await architect.design(jd_analysis=jd)

    assert isinstance(spec, ProjectSpec)
    assert len(spec.feature_specs) == 3
    # Python stack should be detected
    commands_text = " ".join(c.command for c in spec.sandbox_validation_plan.commands)
    assert "pip" in commands_text or "pytest" in commands_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_file_tree_paths(nodes: list[FileTreeNode]) -> list[str]:
    """Recursively collect all paths from a file tree."""
    paths: list[str] = []
    for node in nodes:
        paths.append(node.path)
        if node.children:
            paths.extend(_collect_file_tree_paths(node.children))
    return paths
