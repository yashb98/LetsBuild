"""Project Architect engine (Layer 4) — designs project specs from JD analysis."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

from letsbuild.models.architect_models import (
    ADR,
    ADRStatus,
    FeatureSpec,
    FileTreeNode,
    ProjectSpec,
    SandboxValidationCommand,
    SandboxValidationPlan,
)
from letsbuild.models.intake_models import JDAnalysis, SeniorityLevel

if TYPE_CHECKING:
    from letsbuild.harness.llm_client import LLMClient
    from letsbuild.models.config_models import SkillConfig
    from letsbuild.models.intelligence_models import CompanyProfile
    from letsbuild.models.matcher_models import GapAnalysis

logger = structlog.get_logger()

_SENIORITY_COMPLEXITY: dict[str, float] = {
    SeniorityLevel.JUNIOR: 3.0,
    SeniorityLevel.MID: 5.0,
    SeniorityLevel.SENIOR: 7.0,
    SeniorityLevel.STAFF: 9.0,
    SeniorityLevel.PRINCIPAL: 10.0,
}

_SENIORITY_LOC: dict[str, int] = {
    SeniorityLevel.JUNIOR: 800,
    SeniorityLevel.MID: 1500,
    SeniorityLevel.SENIOR: 2500,
    SeniorityLevel.STAFF: 3500,
    SeniorityLevel.PRINCIPAL: 4500,
}

_TOOL_NAME = "design_project"


class ProjectArchitect:
    """Designs a ProjectSpec from JD analysis, company profile, and gap analysis.

    Uses an LLM with forced tool_choice when available, falling back to a
    deterministic heuristic for testing or budget-constrained environments.
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client
        self._log = logger.bind(component="project_architect")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def design(
        self,
        jd_analysis: JDAnalysis,
        company_profile: CompanyProfile | None = None,
        gap_analysis: GapAnalysis | None = None,
        skill_config: SkillConfig | None = None,
    ) -> ProjectSpec:
        """Design a complete ProjectSpec for the given JD.

        When an LLM client is available, uses Claude Opus with forced
        ``tool_choice`` on ``design_project`` to generate the spec.
        Otherwise falls back to ``_design_heuristic()``.
        """
        if self._llm is None:
            self._log.info("design_heuristic_fallback", reason="no_llm_client")
            return self._design_heuristic(jd_analysis, company_profile, gap_analysis, skill_config)

        system = self._build_system_prompt(jd_analysis, company_profile, gap_analysis)
        tool_schema = self._build_tool_schema()

        user_message = (
            f"Design a portfolio project for the following JD:\n\n"
            f"Role: {jd_analysis.role_title} ({jd_analysis.role_category.value})\n"
            f"Seniority: {jd_analysis.seniority.value}\n"
            f"Tech stack: {', '.join(jd_analysis.tech_stack.languages + jd_analysis.tech_stack.frameworks)}\n"
            f"Key responsibilities: {'; '.join(jd_analysis.key_responsibilities[:5])}\n"
        )

        if skill_config is not None:
            user_message += (
                f"\nSkill: {skill_config.display_name} ({skill_config.name})\n"
                f"Primary tech: {', '.join(skill_config.tech_stacks_primary)}\n"
                f"Complexity range: {skill_config.complexity_range}\n"
            )

        self._log.info("design_llm_start", role=jd_analysis.role_title)

        raw = await self._llm.extract_structured(
            messages=[{"role": "user", "content": user_message}],
            system=system,
            tool_schema=tool_schema,
            tool_name=_TOOL_NAME,
            model="claude-opus-4-6",
        )

        spec = ProjectSpec.model_validate(raw, strict=False)
        self._log.info(
            "design_complete",
            project_name=spec.project_name,
            features=len(spec.feature_specs),
        )
        return spec

    # ------------------------------------------------------------------
    # Heuristic fallback
    # ------------------------------------------------------------------

    def _design_heuristic(
        self,
        jd: JDAnalysis,
        company: CompanyProfile | None,
        gap: GapAnalysis | None,
        skill: SkillConfig | None,
    ) -> ProjectSpec:
        """Deterministic fallback that builds a reasonable ProjectSpec without LLM."""
        project_name = self._generate_project_name(jd, company)
        tech_items = jd.tech_stack.languages + jd.tech_stack.frameworks
        if not tech_items:
            tech_items = ["python"]

        one_liner = (
            f"A {jd.seniority.value}-level {jd.role_category.value.replace('_', ' ')} "
            f"portfolio project showcasing {', '.join(tech_items[:3])}."
        )

        file_tree = self._build_file_tree(tech_items, project_name)
        feature_specs = self._build_feature_specs(jd)
        validation_plan = self._build_validation_plan(tech_items)
        adrs = self._build_default_adrs(tech_items, skill)
        complexity = _SENIORITY_COMPLEXITY.get(jd.seniority.value, 5.0)
        estimated_loc = _SENIORITY_LOC.get(jd.seniority.value, 1500)
        skill_name = skill.name if skill is not None else "general"

        # Build skill coverage map from gap analysis demonstrable gaps
        coverage: dict[str, str] = {}
        if gap is not None:
            for item in gap.demonstrable_gaps[:5]:
                coverage[item.skill_name] = item.suggested_project_demo or "Demonstrated in project"

        return ProjectSpec(
            project_name=project_name,
            one_liner=one_liner,
            tech_stack=tech_items,
            file_tree=file_tree,
            feature_specs=feature_specs,
            sandbox_validation_plan=validation_plan,
            adr_list=adrs,
            skill_name=skill_name,
            skill_coverage_map=coverage,
            complexity_score=complexity,
            estimated_loc=estimated_loc,
            seniority_target=jd.seniority.value,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _generate_project_name(self, jd: JDAnalysis, company: CompanyProfile | None) -> str:
        """Generate an SEO-friendly project name from JD and company."""
        parts: list[str] = []

        if company is not None and company.industry:
            parts.append(company.industry.lower().split()[0])
        elif jd.domain_keywords:
            parts.append(jd.domain_keywords[0].lower())

        role_short = jd.role_category.value.replace("_engineer", "").replace("_", "-")
        parts.append(role_short)

        tech = jd.tech_stack.languages[:1] or jd.tech_stack.frameworks[:1]
        if tech:
            parts.append(tech[0].lower())

        parts.append("platform")

        name = "-".join(parts)
        # Sanitise to kebab-case
        name = re.sub(r"[^a-z0-9-]", "", name)
        name = re.sub(r"-+", "-", name).strip("-")
        return name or "portfolio-project"

    def _build_file_tree(self, tech_stack: list[str], project_name: str) -> list[FileTreeNode]:
        """Build a standard project file tree based on the detected tech stack."""
        tech_lower = {t.lower() for t in tech_stack}

        is_python = bool(tech_lower & {"python", "fastapi", "django", "flask"})
        is_node = bool(tech_lower & {"typescript", "javascript", "react", "next.js", "node", "vue"})

        nodes: list[FileTreeNode] = []

        if is_python:
            nodes.extend(self._python_file_tree(project_name))
        elif is_node:
            nodes.extend(self._node_file_tree(project_name))
        else:
            # Default to Python structure
            nodes.extend(self._python_file_tree(project_name))

        # Common files always present
        nodes.extend(
            [
                FileTreeNode(path="README.md", is_directory=False, description="Project readme."),
                FileTreeNode(
                    path=".gitignore",
                    is_directory=False,
                    description="Git ignore rules.",
                ),
                FileTreeNode(
                    path="docs/",
                    is_directory=True,
                    description="Project documentation.",
                    children=[
                        FileTreeNode(
                            path="docs/decisions/",
                            is_directory=True,
                            description="Architecture Decision Records.",
                        ),
                    ],
                ),
            ]
        )

        return nodes

    def _python_file_tree(self, project_name: str) -> list[FileTreeNode]:
        """Standard Python project structure."""
        pkg = project_name.replace("-", "_")
        return [
            FileTreeNode(
                path="src/",
                is_directory=True,
                description="Source code.",
                children=[
                    FileTreeNode(
                        path=f"src/{pkg}/",
                        is_directory=True,
                        description="Main package.",
                        children=[
                            FileTreeNode(
                                path=f"src/{pkg}/__init__.py",
                                is_directory=False,
                                description="Package init.",
                            ),
                        ],
                    ),
                ],
            ),
            FileTreeNode(
                path="tests/",
                is_directory=True,
                description="Test suite.",
                children=[
                    FileTreeNode(
                        path="tests/__init__.py",
                        is_directory=False,
                        description="Tests package init.",
                    ),
                ],
            ),
            FileTreeNode(
                path="pyproject.toml",
                is_directory=False,
                description="Python project configuration.",
            ),
        ]

    def _node_file_tree(self, _project_name: str) -> list[FileTreeNode]:
        """Standard Node/TypeScript project structure."""
        return [
            FileTreeNode(
                path="src/",
                is_directory=True,
                description="Source code.",
                children=[
                    FileTreeNode(
                        path="src/index.ts",
                        is_directory=False,
                        description="Application entry point.",
                    ),
                ],
            ),
            FileTreeNode(
                path="tests/",
                is_directory=True,
                description="Test suite.",
            ),
            FileTreeNode(
                path="package.json",
                is_directory=False,
                description="Node package configuration.",
            ),
            FileTreeNode(
                path="tsconfig.json",
                is_directory=False,
                description="TypeScript configuration.",
            ),
        ]

    def _build_feature_specs(self, jd: JDAnalysis) -> list[FeatureSpec]:
        """Create feature specs from JD key responsibilities."""
        features: list[FeatureSpec] = []
        responsibilities = jd.key_responsibilities[:5] if jd.key_responsibilities else []

        if not responsibilities:
            # Fallback: generate a generic feature
            responsibilities = [f"Core {jd.role_category.value.replace('_', ' ')} functionality"]

        for i, resp in enumerate(responsibilities):
            short_name = resp[:40].strip().replace(" ", "_").lower()
            short_name = re.sub(r"[^a-z0-9_]", "", short_name)
            features.append(
                FeatureSpec(
                    feature_name=short_name or f"feature_{i}",
                    description=resp,
                    module_path=f"src/{short_name or f'feature_{i}'}.py",
                    dependencies=[],
                    estimated_complexity=min(
                        max(int(_SENIORITY_COMPLEXITY.get(jd.seniority.value, 5.0)), 1), 10
                    ),
                    acceptance_criteria=[f"Implements: {resp}"],
                ),
            )

        return features

    def _build_validation_plan(self, tech_stack: list[str]) -> SandboxValidationPlan:
        """Build a sandbox validation plan with standard commands."""
        tech_lower = {t.lower() for t in tech_stack}
        is_python = bool(tech_lower & {"python", "fastapi", "django", "flask"})

        commands: list[SandboxValidationCommand] = []

        if is_python:
            commands.extend(
                [
                    SandboxValidationCommand(
                        command="cd /mnt/workspace && pip install -e .",
                        description="Install project dependencies.",
                    ),
                    SandboxValidationCommand(
                        command="cd /mnt/workspace && pytest tests/ -v",
                        description="Run test suite.",
                    ),
                    SandboxValidationCommand(
                        command="cd /mnt/workspace && ruff check .",
                        description="Run linter checks.",
                    ),
                ]
            )
        else:
            commands.extend(
                [
                    SandboxValidationCommand(
                        command="cd /mnt/workspace && npm install",
                        description="Install project dependencies.",
                    ),
                    SandboxValidationCommand(
                        command="cd /mnt/workspace && npm test",
                        description="Run test suite.",
                    ),
                    SandboxValidationCommand(
                        command="cd /mnt/workspace && npm run lint",
                        description="Run linter checks.",
                    ),
                ]
            )

        return SandboxValidationPlan(commands=commands)

    def _build_default_adrs(self, tech_stack: list[str], skill: SkillConfig | None) -> list[ADR]:
        """Build 2-3 default ADRs."""
        adrs: list[ADR] = []

        primary_tech = tech_stack[0] if tech_stack else "Python"
        adrs.append(
            ADR(
                title=f"Use {primary_tech} as primary technology",
                status=ADRStatus.ACCEPTED,
                context=(
                    f"The JD requires {primary_tech} expertise. "
                    "We need to choose a primary technology for the project."
                ),
                decision=f"Use {primary_tech} as the primary implementation language/framework.",
                consequences=(
                    f"Team must be proficient in {primary_tech}. "
                    "Leverages JD-specified technology stack."
                ),
            ),
        )

        adrs.append(
            ADR(
                title="Adopt test-driven development approach",
                status=ADRStatus.ACCEPTED,
                context="Portfolio projects must demonstrate testing best practices.",
                decision="Write tests alongside implementation with >80% coverage target.",
                consequences="Slower initial development but higher confidence and code quality.",
            ),
        )

        if skill is not None and skill.topology != "hierarchical":
            adrs.append(
                ADR(
                    title=f"Use {skill.topology} agent topology",
                    status=ADRStatus.ACCEPTED,
                    context=f"Skill '{skill.display_name}' specifies {skill.topology} topology.",
                    decision=f"Agents communicate via {skill.topology} pattern.",
                    consequences="More complex coordination but better suited for this project type.",
                ),
            )

        return adrs

    def _build_system_prompt(
        self,
        jd: JDAnalysis,
        company: CompanyProfile | None,
        gap: GapAnalysis | None,
    ) -> str:
        """Construct the system prompt for the LLM design call."""
        parts: list[str] = [
            "You are a senior software architect designing a portfolio project.",
            "Design a project that demonstrates the candidate's skills for the given job description.",
            "The project must be company-relevant, skill-showcasing, seniority-calibrated, "
            "and sandbox-validated.",
            "",
            "## Case Facts",
            f"- Role: {jd.role_title} ({jd.role_category.value})",
            f"- Seniority: {jd.seniority.value}",
            f"- Tech stack: {', '.join(jd.tech_stack.languages + jd.tech_stack.frameworks)}",
        ]

        if company is not None:
            parts.append("")
            parts.append("## Company Context")
            parts.append(f"- Company: {company.company_name}")
            if company.industry:
                parts.append(f"- Industry: {company.industry}")
            if company.tech_stack_signals:
                parts.append(f"- Tech signals: {', '.join(company.tech_stack_signals[:10])}")
            if company.business_context:
                parts.append(f"- Business: {company.business_context}")

        if gap is not None:
            parts.append("")
            parts.append("## Gap Analysis")
            parts.append(f"- Overall score: {gap.match_score.overall_score}")
            parts.append(f"- Focus areas: {', '.join(gap.recommended_project_focus[:5])}")
            if gap.demonstrable_gaps:
                demo_names = [g.skill_name for g in gap.demonstrable_gaps[:5]]
                parts.append(f"- Demonstrable gaps: {', '.join(demo_names)}")

        parts.extend(
            [
                "",
                "## Requirements",
                "- Generate an SEO-friendly project_name",
                "- Include 3-5 feature_specs based on key responsibilities",
                "- Include a sandbox_validation_plan with >=3 commands",
                "- Include 2-3 ADRs demonstrating senior-level thinking",
                "- Set complexity_score appropriate for the seniority level",
                "- All tech_stack items must be lowercase",
            ]
        )

        return "\n".join(parts)

    def _build_tool_schema(self) -> dict[str, object]:
        """Return the tool definition for forced tool_use with ProjectSpec schema."""
        return {
            "name": _TOOL_NAME,
            "description": (
                "Design a complete project specification for a portfolio project. "
                "The spec includes file tree, features, validation plan, and ADRs."
            ),
            "input_schema": ProjectSpec.model_json_schema(),
        }
