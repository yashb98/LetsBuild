"""SkillLoader middleware — progressive skill loading based on JD role category.

Fourth middleware in the 10-stage chain. Scans the skills directory for
``.skill.md`` files, parses their YAML frontmatter, and loads only the skills
whose ``role_categories`` match the current JD's ``role_category``. If no JD
analysis is available yet, all parseable skills are loaded as a fallback.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import structlog
import yaml

from letsbuild.harness.middleware import Middleware
from letsbuild.models.config_models import SkillConfig

if TYPE_CHECKING:
    from letsbuild.pipeline.state import PipelineState

logger = structlog.get_logger()

# Project root is three levels up from this file:
# letsbuild/harness/middlewares/skill_loader.py -> project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DEFAULT_SKILLS_DIR = _PROJECT_ROOT / "skills"


class SkillLoaderMiddleware(Middleware):
    """Load skill configurations from ``.skill.md`` files based on JD role category.

    before(): Scans the skills directory, parses YAML frontmatter from each
    ``.skill.md`` file, filters by the JD's ``role_category``, and stores
    matched ``SkillConfig`` objects in ``state.skill_configs``.

    after(): No-op — returns state unchanged.
    """

    def __init__(self, skills_directory: str | None = None) -> None:
        self._skills_dir = Path(skills_directory) if skills_directory else _DEFAULT_SKILLS_DIR
        self._log = structlog.get_logger(component="SkillLoader")

    async def before(self, state: PipelineState) -> PipelineState:
        """Scan skills directory and load matching skill configurations.

        If ``state.jd_analysis`` is set, only skills whose ``role_categories``
        contain the JD's ``role_category`` value are loaded. Otherwise all
        parseable skills are loaded as a fallback.

        Args:
            state: The current pipeline state.

        Returns:
            The pipeline state with ``skill_configs`` populated.
        """
        if not self._skills_dir.is_dir():
            await self._log.awarning(
                "skill_loader_directory_missing",
                path=str(self._skills_dir),
            )
            return state

        skill_files = sorted(self._skills_dir.glob("*.skill.md"))

        if not skill_files:
            await self._log.ainfo(
                "skill_loader_no_skill_files",
                path=str(self._skills_dir),
            )
            return state

        # Parse all skill files
        all_skills: list[SkillConfig] = []
        for skill_file in skill_files:
            config = self._parse_frontmatter(skill_file)
            if config is not None:
                all_skills.append(config)

        # Filter by role category if JD analysis is available
        if state.jd_analysis is not None:
            role_category = state.jd_analysis.role_category.value
            matched = [
                skill
                for skill in all_skills
                if self._matches_role(skill, role_category)
            ]
            await self._log.ainfo(
                "skill_loader_filtered",
                total_skills=len(all_skills),
                matched_skills=len(matched),
                role_category=role_category,
                skill_names=[s.name for s in matched],
            )
            state.skill_configs = matched
        else:
            await self._log.ainfo(
                "skill_loader_no_jd_analysis_loading_all",
                total_skills=len(all_skills),
                skill_names=[s.name for s in all_skills],
            )
            state.skill_configs = all_skills

        return state

    async def after(self, state: PipelineState) -> PipelineState:
        """No-op post-processing.

        Args:
            state: The current pipeline state.

        Returns:
            The pipeline state unchanged.
        """
        return state

    def _parse_frontmatter(self, file_path: Path) -> SkillConfig | None:
        """Parse YAML frontmatter from a ``.skill.md`` file into a SkillConfig.

        Frontmatter is delimited by ``---`` markers at the start of the file.
        If parsing fails or required fields are missing, returns ``None`` and
        logs a warning.

        Args:
            file_path: Path to the ``.skill.md`` file.

        Returns:
            A ``SkillConfig`` if parsing succeeds, otherwise ``None``.
        """
        try:
            text = file_path.read_text(encoding="utf-8")
        except OSError:
            self._log.warning(
                "skill_loader_file_read_error",
                path=str(file_path),
            )
            return None

        # Extract YAML between --- markers
        parts = text.split("---", maxsplit=2)
        if len(parts) < 3:
            self._log.warning(
                "skill_loader_no_frontmatter",
                path=str(file_path),
            )
            return None

        yaml_text = parts[1]
        try:
            data = yaml.safe_load(yaml_text)
        except yaml.YAMLError:
            self._log.warning(
                "skill_loader_yaml_parse_error",
                path=str(file_path),
            )
            return None

        if not isinstance(data, dict):
            self._log.warning(
                "skill_loader_invalid_frontmatter",
                path=str(file_path),
            )
            return None

        # Map nested tech_stacks to flat fields expected by SkillConfig
        tech_stacks = data.get("tech_stacks", {})
        if isinstance(tech_stacks, dict):
            primary = tech_stacks.get("primary", [])
            alternatives = tech_stacks.get("alternatives", [])
        else:
            primary = []
            alternatives = []

        try:
            config = SkillConfig(
                name=data["name"],
                display_name=data["display_name"],
                category=data["category"],
                role_categories=data["role_categories"],
                seniority_range=data["seniority_range"],
                tech_stacks_primary=primary,
                tech_stacks_alternatives=alternatives,
                complexity_range=data["complexity_range"],
                estimated_loc=data["estimated_loc"],
                topology=data.get("topology", "hierarchical"),
            )
        except (KeyError, ValueError) as exc:
            self._log.warning(
                "skill_loader_config_validation_error",
                path=str(file_path),
                error=str(exc),
            )
            return None

        return config

    def _matches_role(self, skill_config: SkillConfig, role_category: str) -> bool:
        """Check if a skill config matches the given role category.

        Args:
            skill_config: The parsed skill configuration.
            role_category: The role category value from the JD analysis.

        Returns:
            ``True`` if the role category is listed in the skill's role_categories.
        """
        return role_category in skill_config.role_categories
