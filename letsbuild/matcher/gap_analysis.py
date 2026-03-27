"""Gap analysis utilities for categorising skills against user profile."""

from __future__ import annotations

import structlog

from letsbuild.models.matcher_models import GapCategory

logger = structlog.get_logger()

# Mapping of skill names to related skill groups for detecting demonstrable gaps.
# Keys and values are all lowercase for consistent matching.
_SKILL_FAMILY: dict[str, set[str]] = {
    "python": {"java", "c++", "go", "rust", "ruby", "c#"},
    "java": {"python", "c++", "go", "c#", "kotlin"},
    "javascript": {"typescript", "coffeescript"},
    "typescript": {"javascript"},
    "react": {"vue", "angular", "svelte", "next.js", "nextjs"},
    "vue": {"react", "angular", "svelte", "nuxt"},
    "angular": {"react", "vue", "svelte"},
    "next.js": {"react", "nuxt", "remix", "gatsby"},
    "nextjs": {"react", "nuxt", "remix", "gatsby"},
    "fastapi": {"flask", "django", "express", "spring"},
    "flask": {"fastapi", "django", "express"},
    "django": {"flask", "fastapi", "rails", "laravel"},
    "express": {"fastapi", "flask", "koa", "nestjs"},
    "postgresql": {"mysql", "mariadb", "sqlite", "sql server"},
    "mysql": {"postgresql", "mariadb", "sqlite"},
    "mongodb": {"dynamodb", "couchdb", "firestore"},
    "redis": {"memcached", "valkey"},
    "aws": {"gcp", "azure"},
    "gcp": {"aws", "azure"},
    "azure": {"aws", "gcp"},
    "docker": {"podman", "containerd"},
    "kubernetes": {"docker swarm", "nomad", "ecs"},
    "terraform": {"pulumi", "cloudformation", "cdk"},
    "pytorch": {"tensorflow", "jax", "keras"},
    "tensorflow": {"pytorch", "jax", "keras"},
    "pandas": {"polars", "dask", "pyspark"},
    "kafka": {"rabbitmq", "pulsar", "nats"},
    "rabbitmq": {"kafka", "pulsar", "nats"},
    "graphql": {"rest", "grpc", "trpc"},
    "rest": {"graphql", "grpc"},
    "ci/cd": {"github actions", "jenkins", "circleci", "gitlab ci"},
    "github actions": {"ci/cd", "jenkins", "circleci", "gitlab ci"},
}

# Skills considered easy to pick up if you already have general software experience.
_LEARNABLE_SKILLS: set[str] = {
    "git",
    "github",
    "jira",
    "confluence",
    "slack",
    "agile",
    "scrum",
    "kanban",
    "rest",
    "graphql",
    "markdown",
    "yaml",
    "json",
    "css",
    "html",
    "tailwind",
    "figma",
    "postman",
    "swagger",
    "openapi",
    "redis",
    "sqlite",
    "linux",
    "bash",
    "shell",
    "vscode",
    "vim",
    "docker",
    "docker compose",
}


class GapAnalyser:
    """Categorises individual skills and computes overlap metrics."""

    def __init__(self) -> None:
        self._log = logger.bind(component="gap_analyser")

    def categorise_skill(
        self,
        skill_name: str,
        user_skills: set[str],
        taxonomy: dict[str, set[str]] | None = None,
    ) -> GapCategory:
        """Categorise a single skill relative to the user's existing skills.

        Args:
            skill_name: Name of the skill to categorise.
            user_skills: Set of skill names the user already has (lowercase).
            taxonomy: Optional override for the skill-family mapping.

        Returns:
            The appropriate GapCategory for this skill.
        """
        families = taxonomy if taxonomy is not None else _SKILL_FAMILY
        normalised = skill_name.lower().strip()
        normalised_user = {s.lower().strip() for s in user_skills}

        # Direct match → strong match
        if normalised in normalised_user:
            return GapCategory.STRONG_MATCH

        # Check for alias / substring match (e.g. user has "react" and skill is "react.js")
        for user_skill in normalised_user:
            if normalised in user_skill or user_skill in normalised:
                return GapCategory.STRONG_MATCH

        # Related skill in same family → demonstrable gap
        related = families.get(normalised, set())
        if related & normalised_user:
            self._log.debug(
                "demonstrable_gap_detected",
                skill=normalised,
                related_match=list(related & normalised_user),
            )
            return GapCategory.DEMONSTRABLE_GAP

        # Check reverse: if the user has a skill whose family includes this skill
        for user_skill in normalised_user:
            family_of_user = families.get(user_skill, set())
            if normalised in family_of_user:
                self._log.debug(
                    "demonstrable_gap_via_reverse",
                    skill=normalised,
                    user_skill=user_skill,
                )
                return GapCategory.DEMONSTRABLE_GAP

        # Generally easy to learn → learnable gap
        if normalised in _LEARNABLE_SKILLS:
            return GapCategory.LEARNABLE_GAP

        # Hard gap — no connection found
        return GapCategory.HARD_GAP

    def compute_skill_overlap(
        self,
        required: list[str],
        user_has: list[str],
    ) -> float:
        """Compute percentage overlap between required skills and user skills.

        Args:
            required: List of required skill names from JD.
            user_has: List of skill names the user possesses.

        Returns:
            Overlap percentage from 0.0 to 100.0.
        """
        if not required:
            return 100.0

        required_lower = {s.lower().strip() for s in required}
        user_lower = {s.lower().strip() for s in user_has}

        matched = 0
        for req in required_lower:
            if req in user_lower:
                matched += 1
                continue
            # Substring / alias match
            for user_skill in user_lower:
                if req in user_skill or user_skill in req:
                    matched += 1
                    break

        return round((matched / len(required_lower)) * 100.0, 2)
