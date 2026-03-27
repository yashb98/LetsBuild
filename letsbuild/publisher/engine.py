"""Publisher Integration Engine for Layer 6: GitHub Publisher.

Orchestrates the full publishing flow:
  1. PrePublish gates (quality, review, sandbox, security, readme)
  2. README generation
  3. Commit plan generation
  4. GitHub repo creation
  5. Commit-by-commit history push (backdated for realism)
  6. Topic tagging
  7. PublishResult assembly
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog

from letsbuild.hooks.pre_publish import PrePublishHook
from letsbuild.models.publisher_models import CommitPlan, PublishResult, RepoConfig
from letsbuild.publisher.commit_strategy import CommitStrategyEngine
from letsbuild.publisher.github_client import GitHubClient
from letsbuild.publisher.readme_generator import ReadmeGenerator

if TYPE_CHECKING:
    from letsbuild.models.architect_models import ProjectSpec
    from letsbuild.models.forge_models import ForgeOutput

__all__ = ["PublisherEngine"]

logger = structlog.get_logger(__name__)

# GitHub API file-mode for regular blob
_BLOB_MODE = "100644"

# Maximum topics GitHub allows per repository
_MAX_TOPICS = 20

# Base timestamp: treat commit timestamp offsets relative to 7 days before now so
# the generated repo looks like it was worked on recently but not started today.
_HISTORY_BASE_DAYS_AGO = 7


def _slugify(name: str) -> str:
    """Convert a project name to a kebab-case GitHub repo slug."""
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "letsbuild-project"


def _derive_topics(project_spec: ProjectSpec) -> list[str]:
    """Derive GitHub topics from ProjectSpec tech_stack and skill_name.

    Topics are lowercased, stripped to ≤35 chars, and capped at _MAX_TOPICS.
    """
    raw: list[str] = []

    # Always include letsbuild attribution
    raw.append("letsbuild")
    raw.append("portfolio")

    # Add tech stack items as topics
    for tech in project_spec.tech_stack:
        slug = re.sub(r"[^a-z0-9-]", "-", tech.lower())
        slug = re.sub(r"-+", "-", slug).strip("-")
        if slug and slug not in raw:
            raw.append(slug)

    # Add the skill name as a topic
    skill_slug = re.sub(r"[^a-z0-9-]", "-", project_spec.skill_name.lower()).strip("-")
    if skill_slug and skill_slug not in raw:
        raw.append(skill_slug)

    # Sanitise: GitHub topics must be ≤35 chars, lowercase, alphanumeric + hyphens
    topics: list[str] = []
    for t in raw:
        t = t[:35].rstrip("-")
        if t and t not in topics:
            topics.append(t)

    return topics[:_MAX_TOPICS]


def _offset_to_iso(base: datetime, offset_hours: float) -> str:
    """Convert a float hour offset to an ISO 8601 datetime string (UTC)."""
    dt = base + timedelta(hours=offset_hours)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class PublisherEngine:
    """Orchestrates the complete Layer 6 publishing flow.

    Parameters
    ----------
    github_token:
        Personal access token or fine-grained token with ``repo`` scope.
    owner:
        GitHub user or organisation login that will own the repository.
    org:
        If provided, the repo is created under this organisation instead of the
        authenticated user.
    quality_threshold:
        Minimum quality score required to pass the PrePublish quality gate.
    spread_days:
        Number of calendar days over which to spread the commit history.
    commit_seed:
        Optional random seed passed to CommitStrategyEngine for deterministic
        commit timestamp generation (useful in tests).
    """

    def __init__(
        self,
        github_token: str,
        owner: str,
        org: str | None = None,
        quality_threshold: float = 70.0,
        spread_days: int = 5,
        commit_seed: int | None = None,
    ) -> None:
        self._token = github_token
        self._owner = owner
        self._org = org
        self._quality_threshold = quality_threshold
        self._spread_days = spread_days
        self._commit_seed = commit_seed

        self._pre_publish = PrePublishHook(quality_threshold=quality_threshold)
        self._readme_gen = ReadmeGenerator()
        self._commit_engine = CommitStrategyEngine(
            spread_days=spread_days,
            seed=commit_seed,
        )
        self._log = logger.bind(component="PublisherEngine", owner=owner)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def publish(
        self,
        project_spec: ProjectSpec,
        forge_output: ForgeOutput,
    ) -> PublishResult:
        """Run the full publishing pipeline and return a :class:`PublishResult`.

        Steps:
        1. Generate README (needed for PrePublish readme gate).
        2. Run PrePublishHook — abort if any blocking gate fails.
        3. Generate CommitPlan.
        4. Build RepoConfig from ProjectSpec.
        5. Create GitHub repository.
        6. Bootstrap empty repo with an initial empty-tree commit so the branch ref exists.
        7. For each CommitEntry: collect files → create tree → create commit → update ref.
        8. Set repository topics.
        9. Return PublishResult.

        Raises:
            RuntimeError: if any blocking PrePublish gate fails.
            ValueError: propagated from GitHubClient on GitHub API errors.
        """
        log = self._log.bind(project=project_spec.project_name)
        log.info("publisher_engine.publish_started")

        # --- Step 1: Generate README ---
        readme_content = self._readme_gen.generate(project_spec, forge_output)
        log.debug("publisher_engine.readme_generated", chars=len(readme_content))

        # --- Step 2: PrePublish gates ---
        gate_results = await self._pre_publish.run(
            project_spec=project_spec,
            forge_output=forge_output,
            readme_content=readme_content,
        )
        blocking_failures = [r for r in gate_results if not r.passed and r.blocking]
        if blocking_failures:
            failure_summaries = "; ".join(f"{r.gate_name}: {r.reason}" for r in blocking_failures)
            log.error(
                "publisher_engine.blocked_by_gates",
                gates=[r.gate_name for r in blocking_failures],
            )
            msg = f"Publishing blocked by {len(blocking_failures)} gate(s): {failure_summaries}"
            raise RuntimeError(msg)

        log.info("publisher_engine.gates_passed", total=len(gate_results))

        # --- Step 3: Commit plan ---
        commit_plan = self._commit_engine.generate_plan(project_spec, forge_output)
        log.info("publisher_engine.commit_plan_ready", commits=commit_plan.total_commits)

        # --- Step 4: RepoConfig ---
        repo_config = self._build_repo_config(project_spec)
        log.info("publisher_engine.repo_config_built", repo_name=repo_config.repo_name)

        # --- Steps 5-8: GitHub operations ---
        async with GitHubClient(self._token) as client:
            # Create repo
            repo_data = await client.create_repo(repo_config, org=self._org)
            repo_url: str = repo_data["html_url"]
            log.info("publisher_engine.repo_created", url=repo_url)

            # Build module path → content lookup
            module_map: dict[str, str] = {
                m.module_path: m.content for m in forge_output.code_modules
            }
            # Inject the generated README
            module_map["README.md"] = readme_content

            # Base timestamp for backdating
            base_time = datetime.now(UTC) - timedelta(days=_HISTORY_BASE_DAYS_AGO)

            # Push commits sequentially
            commit_shas = await self._push_commits(
                client=client,
                repo_config=repo_config,
                commit_plan=commit_plan,
                module_map=module_map,
                base_time=base_time,
                project_spec=project_spec,
                log=log,
            )

            # Set topics
            await client.set_topics(
                owner=self._owner,
                repo=repo_config.repo_name,
                topics=repo_config.topics,
            )
            log.info("publisher_engine.topics_set", topics=repo_config.topics)

        repo_name = repo_config.repo_name
        readme_url = f"{repo_url}/blob/{repo_config.default_branch}/README.md"

        result = PublishResult(
            repo_url=repo_url,
            commit_shas=commit_shas,
            readme_url=readme_url,
            repo_config=repo_config,
            commit_plan=commit_plan,
        )

        log.info(
            "publisher_engine.publish_complete",
            repo=repo_name,
            commits=len(commit_shas),
        )
        return result

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _build_repo_config(self, project_spec: ProjectSpec) -> RepoConfig:
        """Derive a :class:`RepoConfig` from a :class:`ProjectSpec`.

        - repo_name: kebab-case slug of the project name
        - description: one_liner trimmed to 255 chars (GitHub limit)
        - topics: derived from tech_stack + skill_name
        """
        repo_name = _slugify(project_spec.project_name)
        description = project_spec.one_liner[:255]
        topics = _derive_topics(project_spec)

        return RepoConfig(
            repo_name=repo_name,
            description=description,
            private=True,
            topics=topics,
        )

    async def _push_commits(
        self,
        client: GitHubClient,
        repo_config: RepoConfig,
        commit_plan: CommitPlan,
        module_map: dict[str, str],
        base_time: datetime,
        project_spec: ProjectSpec,
        log: Any,
    ) -> list[str]:
        """Execute the commit plan against the GitHub Git Data API.

        For each :class:`CommitEntry`:
        - Collect file contents from ``module_map`` (files missing from
          module_map are skipped with a warning so a bad plan never aborts
          publication entirely).
        - Create a Git tree.
        - Create a backdated commit.
        - Update the branch ref.

        Returns the ordered list of commit SHAs pushed.
        """
        branch = repo_config.default_branch
        ref_name = f"heads/{branch}"
        repo_name = repo_config.repo_name
        shas: list[str] = []
        parent_shas: list[str] = []

        # Bootstrap: create an initial commit so the branch ref exists before
        # we start pushing via the Git Data API.  The Contents API
        # auto-initialises the branch on the first file.
        init_response = await client.create_or_update_file(
            owner=self._owner,
            repo=repo_name,
            path=".letsbuild",
            content="# Generated by LetsBuild\n",
            message="chore: initialise repository",
            branch=branch,
        )
        # The Contents API returns the commit SHA under commit.sha
        init_sha: str = init_response["commit"]["sha"]
        shas.append(init_sha)
        parent_shas = [init_sha]
        log.debug("publisher_engine.bootstrap_commit", sha=init_sha[:8])

        for entry in commit_plan.commits:
            # Collect files that exist in our module map
            tree_items: list[dict[str, Any]] = []
            skipped: list[str] = []

            for file_path in entry.files:
                content = module_map.get(file_path)
                if content is None:
                    skipped.append(file_path)
                    continue
                tree_items.append(
                    {
                        "path": file_path,
                        "mode": _BLOB_MODE,
                        "type": "blob",
                        "content": content,
                    }
                )

            if skipped:
                log.warning(
                    "publisher_engine.files_missing_from_forge",
                    phase=entry.phase,
                    skipped=skipped,
                )

            if not tree_items:
                log.debug(
                    "publisher_engine.commit_skipped_no_files",
                    message=entry.message,
                    phase=entry.phase,
                )
                continue

            # Fetch the tree SHA of the current HEAD so we can build on top of it.
            # We use the parent commit SHA we already track — fetch it via the
            # Git Data API rather than the ref API to avoid an extra round-trip.
            base_tree_sha = await self._get_tree_sha_for_commit(client, repo_name, parent_shas[0])

            # Create tree
            tree_data = await client.create_tree(
                owner=self._owner,
                repo=repo_name,
                tree_items=tree_items,
                base_tree=base_tree_sha,
            )
            tree_sha: str = tree_data["sha"]

            # Backdate commit
            commit_iso = _offset_to_iso(base_time, entry.timestamp_offset_hours)
            author = self._make_author_iso(commit_iso, project_spec)

            # Create commit
            commit_data = await client.create_commit(
                owner=self._owner,
                repo=repo_name,
                message=entry.message,
                tree_sha=tree_sha,
                parent_shas=parent_shas,
                author=author,
            )
            commit_sha: str = commit_data["sha"]

            # Advance branch ref
            await client.update_ref(
                owner=self._owner,
                repo=repo_name,
                ref=ref_name,
                sha=commit_sha,
            )

            shas.append(commit_sha)
            parent_shas = [commit_sha]

            log.debug(
                "publisher_engine.commit_pushed",
                sha=commit_sha[:8],
                phase=entry.phase,
                message=entry.message[:60],
            )

        return shas

    async def _get_tree_sha_for_commit(
        self,
        client: GitHubClient,
        repo_name: str,
        commit_sha: str,
    ) -> str:
        """Return the tree SHA associated with a commit SHA.

        Uses the GitHubClient's internal ``_request`` helper via the public
        Git Data API endpoint.  The tree SHA is needed to build an incremental
        tree on top of the previous commit.
        """
        commit_data = await client._request(
            "GET",
            f"/repos/{self._owner}/{repo_name}/git/commits/{commit_sha}",
        )
        tree: dict[str, Any] = commit_data.get("tree", {})
        sha: str = tree.get("sha", "")
        return sha

    @staticmethod
    def _make_author_iso(iso: str, project_spec: ProjectSpec) -> dict[str, Any]:
        """Build a GitHub author dict from an ISO 8601 datetime string."""
        return {
            "name": project_spec.project_name,
            "email": "letsbuild@noreply.github.com",
            "date": iso,
        }
