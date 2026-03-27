"""Commit Strategy Engine for Layer 6: GitHub Publisher.

Generates a realistic multi-day commit plan from ForgeOutput and ProjectSpec,
grouping files into 7 phases and spreading timestamps across working hours.
"""

from __future__ import annotations

import random
from collections import defaultdict
from typing import TYPE_CHECKING

import structlog

from letsbuild.models.publisher_models import CommitEntry, CommitPhase, CommitPlan

if TYPE_CHECKING:
    from letsbuild.models.architect_models import ProjectSpec
    from letsbuild.models.forge_models import ForgeOutput

__all__ = ["CommitStrategyEngine"]

logger = structlog.get_logger(__name__)

# Patterns that map file paths to commit phases (checked in order)
_PHASE_PATTERNS: list[tuple[CommitPhase, tuple[str, ...]]] = [
    (
        CommitPhase.CI_CD,
        (
            ".github/",
            "dockerfile",
            "docker-compose",
            ".dockerignore",
            ".travis.yml",
            "jenkins",
            "circle",
            ".gitlab-ci",
        ),
    ),
    (
        CommitPhase.TESTS,
        (
            "test_",
            "_test.",
            "/tests/",
            "tests/",
            "spec/",
            ".spec.",
            "_spec.",
        ),
    ),
    (
        CommitPhase.ADRS,
        (
            "docs/decisions/",
            "adr",
        ),
    ),
    (
        CommitPhase.DOCS,
        (
            "readme",
            "docs/",
            "contributing",
            "changelog",
            "license",
            "authors",
            ".md",
        ),
    ),
    (
        CommitPhase.SCAFFOLDING,
        (
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "poetry.lock",
            "requirements",
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "go.mod",
            "go.sum",
            "cargo.toml",
            "cargo.lock",
            "__init__.py",
            ".gitignore",
            ".gitattributes",
            "makefile",
            ".env.example",
            ".editorconfig",
            ".pre-commit-config",
            "mypy.ini",
            ".mypy.ini",
            "ruff.toml",
            ".ruff.toml",
            "pyrightconfig.json",
            "tsconfig.json",
            ".eslintrc",
            ".prettierrc",
        ),
    ),
]

# Working-hour offsets within a day (hours from midnight)
_WORK_START_HOUR = 9
_WORK_END_HOUR = 18


def _classify_file(path: str) -> CommitPhase:
    """Determine commit phase for a file based on its path.

    Checks patterns in priority order: CI/CD > Tests > ADRs > Docs >
    Scaffolding > Core Modules (default). Returns POLISH only when
    explicitly assigned by the caller for cleanup entries.
    """
    normalised = path.lower().replace("\\", "/")

    for phase, patterns in _PHASE_PATTERNS:
        for pat in patterns:
            if pat in normalised:
                return phase

    return CommitPhase.CORE_MODULES


def _generate_timestamps(
    num_commits: int,
    spread_days: int,
    rng: random.Random,
) -> list[float]:
    """Create realistic timestamp offsets (hours from t=0) for *num_commits* commits.

    Commits are distributed across *spread_days* with working-hour clustering
    and intentional gaps between phases.  The sequence is strictly monotonically
    increasing.
    """
    if num_commits == 0:
        return []

    total_work_hours = spread_days * (_WORK_END_HOUR - _WORK_START_HOUR)
    # Base spacing with slight randomness
    base_spacing = total_work_hours / max(num_commits, 1)

    offsets: list[float] = []
    current: float = _WORK_START_HOUR  # Start at 9 AM on day 0

    for i in range(num_commits):
        # Add some jitter (±30% of base spacing) to avoid perfect uniformity
        jitter = rng.uniform(-0.3 * base_spacing, 0.3 * base_spacing)
        step = max(0.25, base_spacing + jitter)  # At least 15 minutes apart

        if i > 0:
            current += step

        # Keep within working hours: wrap to next day's 9 AM if past 6 PM
        day = int(current // 24)
        hour_of_day = current % 24
        if hour_of_day >= _WORK_END_HOUR:
            day += 1
            hour_of_day = _WORK_START_HOUR + rng.uniform(0.0, 1.0)
            current = day * 24 + hour_of_day
        elif hour_of_day < _WORK_START_HOUR:
            hour_of_day = _WORK_START_HOUR + rng.uniform(0.0, 0.5)
            current = day * 24 + hour_of_day

        offsets.append(round(current, 4))

    # Guarantee strict monotonicity (safety pass)
    for idx in range(1, len(offsets)):
        if offsets[idx] <= offsets[idx - 1]:
            offsets[idx] = offsets[idx - 1] + 0.25

    return offsets


class CommitStrategyEngine:
    """Generate a realistic multi-phase commit plan from forge output.

    Parameters
    ----------
    spread_days:
        Number of calendar days across which to spread commits (3-7).
    seed:
        Optional random seed for deterministic output (useful in tests).
    """

    def __init__(self, spread_days: int = 5, seed: int | None = None) -> None:
        if spread_days < 1:
            msg = "spread_days must be at least 1"
            raise ValueError(msg)
        self._spread_days = spread_days
        self._rng = random.Random(seed)

    def generate_plan(
        self,
        project_spec: ProjectSpec,
        forge_output: ForgeOutput,
    ) -> CommitPlan:
        """Build a CommitPlan from a ProjectSpec and ForgeOutput.

        Groups CodeModules into phases, creates Conventional Commit messages,
        and assigns realistic timestamp offsets.
        """
        log = logger.bind(
            project=project_spec.project_name,
            spread_days=self._spread_days,
            modules=len(forge_output.code_modules),
        )
        log.info("generating_commit_plan")

        # 1. Classify modules into phases
        phase_to_files: dict[CommitPhase, list[str]] = defaultdict(list)
        for module in forge_output.code_modules:
            phase = _classify_file(module.module_path)
            phase_to_files[phase].append(module.module_path)

        # 2. Add ADR files from project_spec (may not be in forge_output)
        for idx, adr in enumerate(project_spec.adr_list, start=1):
            adr_path = f"docs/decisions/ADR-{idx:03d}-{_slugify(adr.title)}.md"
            # Only add if not already captured
            if adr_path not in phase_to_files[CommitPhase.ADRS]:
                phase_to_files[CommitPhase.ADRS].append(adr_path)

        # 3. Build commit entries per phase in canonical order
        phase_order: list[CommitPhase] = [
            CommitPhase.SCAFFOLDING,
            CommitPhase.CORE_MODULES,
            CommitPhase.TESTS,
            CommitPhase.ADRS,
            CommitPhase.DOCS,
            CommitPhase.CI_CD,
            CommitPhase.POLISH,
        ]

        raw_entries: list[tuple[CommitPhase, list[str], str]] = []

        for phase in phase_order:
            files = phase_to_files.get(phase, [])
            if not files:
                continue
            entries = self._phase_entries(phase, files, project_spec)
            raw_entries.extend(entries)

        # 4. Always emit a POLISH entry as the final commit
        polish_files = phase_to_files.get(CommitPhase.POLISH, [])
        polish_extra: list[str] = []
        if not polish_files and not any(p == CommitPhase.POLISH for p, _, _ in raw_entries):
            polish_extra = ["pyproject.toml", ".ruff.toml"]  # representative
        raw_entries.append(
            (
                CommitPhase.POLISH,
                polish_files or polish_extra,
                "chore: format and polish codebase",
            )
        )

        # 5. Generate timestamps
        timestamps = _generate_timestamps(len(raw_entries), self._spread_days, self._rng)

        # 6. Assemble CommitEntry list
        commits: list[CommitEntry] = []
        for (phase, files, message), ts in zip(raw_entries, timestamps, strict=True):
            commits.append(
                CommitEntry(
                    message=message,
                    files=files,
                    phase=phase,
                    timestamp_offset_hours=ts,
                )
            )

        log.info(
            "commit_plan_generated",
            total_commits=len(commits),
        )

        return CommitPlan(
            commits=commits,
            total_commits=len(commits),
            spread_days=self._spread_days,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _phase_entries(
        self,
        phase: CommitPhase,
        files: list[str],
        project_spec: ProjectSpec,
    ) -> list[tuple[CommitPhase, list[str], str]]:
        """Build one or more commit tuples for a given phase.

        SCAFFOLDING and CI_CD are typically one commit; CORE_MODULES and TESTS
        may be split per module for a more realistic history.
        """
        if phase == CommitPhase.SCAFFOLDING:
            return [(phase, files, "feat: scaffold project structure")]

        if phase == CommitPhase.CI_CD:
            return [(phase, files, "ci: add GitHub Actions workflow and Docker setup")]

        if phase == CommitPhase.DOCS:
            return [(phase, files, "docs: add README and project documentation")]

        if phase == CommitPhase.ADRS:
            entries: list[tuple[CommitPhase, list[str], str]] = []
            for idx, adr in enumerate(project_spec.adr_list, start=1):
                adr_path = f"docs/decisions/ADR-{idx:03d}-{_slugify(adr.title)}.md"
                entries.append((phase, [adr_path], f"docs(adr): add ADR-{idx:03d} — {adr.title}"))
            # If ADR list is empty but files exist, fall back to a single commit
            if not entries:
                entries = [(phase, files, "docs(adr): add architecture decision records")]
            return entries

        if phase == CommitPhase.CORE_MODULES:
            return self._split_by_module(phase, files, "feat({name}): add {name} module")

        if phase == CommitPhase.TESTS:
            return self._split_by_module(phase, files, "test: add unit tests for {name}")

        if phase == CommitPhase.POLISH:
            return [(phase, files, "chore: format and polish codebase")]

        # Fallback
        return [(phase, files, f"chore: {phase.value} updates")]

    @staticmethod
    def _split_by_module(
        phase: CommitPhase,
        files: list[str],
        message_template: str,
    ) -> list[tuple[CommitPhase, list[str], str]]:
        """Group files by inferred module name and create per-module commits."""
        module_groups: dict[str, list[str]] = defaultdict(list)

        for path in files:
            name = _infer_module_name(path)
            module_groups[name].append(path)

        entries: list[tuple[CommitPhase, list[str], str]] = []
        for name, group_files in module_groups.items():
            message = message_template.format(name=name)
            entries.append((phase, group_files, message))

        return entries


# ------------------------------------------------------------------
# Module-level utility functions
# ------------------------------------------------------------------


def _infer_module_name(path: str) -> str:
    """Derive a human-readable module name from a file path."""
    import os

    basename = os.path.basename(path)
    # Strip common prefixes and suffixes
    name = basename
    for prefix in ("test_",):
        if name.startswith(prefix):
            name = name[len(prefix) :]
    for suffix in (".py", ".ts", ".js", ".go", ".rs", ".java", "_test.py"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.replace("_", "-") or "core"


def _slugify(text: str) -> str:
    """Convert a title string to a kebab-case slug for file names."""
    import re

    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "decision"
