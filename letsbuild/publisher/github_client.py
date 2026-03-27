"""Async GitHub API wrapper for Layer 6: GitHub Publisher."""

from __future__ import annotations

import base64
import contextlib
from typing import TYPE_CHECKING, Any

import httpx
import structlog

from letsbuild.models.shared import ErrorCategory, StructuredError

if TYPE_CHECKING:
    from types import TracebackType

    from letsbuild.models.publisher_models import RepoConfig

__all__ = ["GitHubClient"]

logger = structlog.get_logger(__name__)

# HTTP status codes and their error classifications
_RATE_LIMIT_STATUS = 429
_NOT_FOUND_STATUS = 404
_FORBIDDEN_STATUS = 403
_UNPROCESSABLE_STATUS = 422
_UNAUTHORIZED_STATUS = 401


def _classify_error(status_code: int, message: str, attempted_query: str) -> StructuredError:
    """Map an HTTP status code to a StructuredError with proper categorisation."""
    if status_code == _RATE_LIMIT_STATUS:
        return StructuredError(
            error_category=ErrorCategory.TRANSIENT,
            is_retryable=True,
            message=f"GitHub API rate limit exceeded: {message}",
            attempted_query=attempted_query,
        )
    if status_code == _NOT_FOUND_STATUS:
        return StructuredError(
            error_category=ErrorCategory.BUSINESS,
            is_retryable=False,
            message=f"GitHub resource not found: {message}",
            attempted_query=attempted_query,
        )
    if status_code == _UNAUTHORIZED_STATUS:
        return StructuredError(
            error_category=ErrorCategory.PERMISSION,
            is_retryable=False,
            message=f"GitHub API unauthorised — check token: {message}",
            attempted_query=attempted_query,
        )
    if status_code == _FORBIDDEN_STATUS:
        return StructuredError(
            error_category=ErrorCategory.PERMISSION,
            is_retryable=False,
            message=f"GitHub API forbidden: {message}",
            attempted_query=attempted_query,
        )
    if status_code == _UNPROCESSABLE_STATUS:
        return StructuredError(
            error_category=ErrorCategory.VALIDATION,
            is_retryable=False,
            message=f"GitHub API validation error: {message}",
            attempted_query=attempted_query,
        )
    # 5xx and other unexpected statuses are transient
    return StructuredError(
        error_category=ErrorCategory.TRANSIENT,
        is_retryable=True,
        message=f"GitHub API error (HTTP {status_code}): {message}",
        attempted_query=attempted_query,
    )


class GitHubClient:
    """Async HTTP client wrapping the GitHub REST API v3.

    Usage::

        async with GitHubClient(token="ghp_...") as client:
            repo = await client.create_repo(config)
    """

    def __init__(
        self,
        token: str,
        base_url: str = "https://api.github.com",
    ) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self._log = logger.bind(component="GitHubClient", base_url=self._base_url)

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> GitHubClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying httpx.AsyncClient."""
        await self._client.aclose()
        self._log.debug("github_client_closed")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request and return the parsed JSON body.

        Raises:
            StructuredError: on any non-2xx response.
        """
        self._log.debug("github_request", method=method, path=path)
        try:
            response = await self._client.request(
                method,
                path,
                json=json,
                params=params,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body: dict[str, Any] = {}
            with contextlib.suppress(Exception):
                body = exc.response.json()
            gh_message = body.get("message", str(exc))
            error = _classify_error(
                exc.response.status_code,
                str(gh_message),
                f"{method} {path}",
            )
            self._log.warning(
                "github_api_error",
                status_code=exc.response.status_code,
                error_category=error.error_category,
                message=error.message,
            )
            raise ValueError(error.model_dump_json()) from exc
        except httpx.RequestError as exc:
            error = StructuredError(
                error_category=ErrorCategory.TRANSIENT,
                is_retryable=True,
                message=f"Network error calling GitHub API: {exc}",
                attempted_query=f"{method} {path}",
            )
            self._log.warning("github_network_error", message=error.message)
            raise ValueError(error.model_dump_json()) from exc

        # 204 No Content — return empty dict
        if response.status_code == 204:
            return {}

        result: dict[str, Any] = response.json()
        self._log.debug("github_response_ok", method=method, path=path, status=response.status_code)
        return result

    # ------------------------------------------------------------------
    # Repository operations
    # ------------------------------------------------------------------

    async def create_repo(
        self,
        config: RepoConfig,
        org: str | None = None,
    ) -> dict[str, Any]:
        """Create a new GitHub repository.

        Args:
            config: Repository configuration (name, description, private, etc.).
            org: Optional organisation login. If given, creates under the org;
                 otherwise creates under the authenticated user.

        Returns:
            GitHub API response dict for the created repository.
        """
        path = f"/orgs/{org}/repos" if org else "/user/repos"
        payload: dict[str, Any] = {
            "name": config.repo_name,
            "description": config.description,
            "private": config.private,
            "has_wiki": config.has_wiki,
            "has_issues": config.has_issues,
            "auto_init": False,
        }
        self._log.info("create_repo", repo_name=config.repo_name, org=org)
        return await self._request("POST", path, json=payload)

    # ------------------------------------------------------------------
    # Contents API (single-file create/update)
    # ------------------------------------------------------------------

    async def create_or_update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str = "main",
        sha: str | None = None,
    ) -> dict[str, Any]:
        """Create or update a single file via the GitHub Contents API.

        Args:
            owner: Repository owner (user or org login).
            repo: Repository name.
            path: File path within the repository (e.g. "src/main.py").
            content: Raw file content (will be base64-encoded automatically).
            message: Commit message for this file change.
            branch: Target branch name.
            sha: Blob SHA of the existing file — required when updating.

        Returns:
            GitHub API response dict.
        """
        encoded = base64.b64encode(content.encode()).decode()
        api_path = f"/repos/{owner}/{repo}/contents/{path}"
        payload: dict[str, Any] = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        if sha is not None:
            payload["sha"] = sha

        self._log.info("create_or_update_file", owner=owner, repo=repo, path=path)
        return await self._request("PUT", api_path, json=payload)

    # ------------------------------------------------------------------
    # Git Data API (low-level tree / commit / ref)
    # ------------------------------------------------------------------

    async def create_tree(
        self,
        owner: str,
        repo: str,
        tree_items: list[dict[str, Any]],
        base_tree: str | None = None,
    ) -> dict[str, Any]:
        """Create a Git tree object.

        Args:
            owner: Repository owner.
            repo: Repository name.
            tree_items: List of tree items. Each item should include at minimum
                ``path``, ``mode``, ``type``, and either ``sha`` or ``content``.
            base_tree: SHA of an existing tree to build upon incrementally.

        Returns:
            GitHub API response dict containing the new tree SHA.
        """
        api_path = f"/repos/{owner}/{repo}/git/trees"
        payload: dict[str, Any] = {"tree": tree_items}
        if base_tree is not None:
            payload["base_tree"] = base_tree

        self._log.info("create_tree", owner=owner, repo=repo, num_items=len(tree_items))
        return await self._request("POST", api_path, json=payload)

    async def create_commit(
        self,
        owner: str,
        repo: str,
        message: str,
        tree_sha: str,
        parent_shas: list[str],
        author: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a Git commit object.

        Args:
            owner: Repository owner.
            repo: Repository name.
            message: Commit message (Conventional Commits format expected).
            tree_sha: SHA of the tree object for this commit.
            parent_shas: List of parent commit SHAs (empty for the root commit).
            author: Optional dict with ``name``, ``email``, and ``date`` keys.
                    If ``date`` is supplied it should be an ISO 8601 string so
                    that commits can be back-dated for realistic git history.

        Returns:
            GitHub API response dict containing the new commit SHA.
        """
        api_path = f"/repos/{owner}/{repo}/git/commits"
        payload: dict[str, Any] = {
            "message": message,
            "tree": tree_sha,
            "parents": parent_shas,
        }
        if author is not None:
            payload["author"] = author
            payload["committer"] = author

        self._log.info(
            "create_commit",
            owner=owner,
            repo=repo,
            message=message[:60],
            num_parents=len(parent_shas),
        )
        return await self._request("POST", api_path, json=payload)

    async def update_ref(
        self,
        owner: str,
        repo: str,
        ref: str,
        sha: str,
    ) -> dict[str, Any]:
        """Update a Git reference (branch pointer) to point to a new commit.

        Args:
            owner: Repository owner.
            repo: Repository name.
            ref: Reference name without the ``refs/`` prefix, e.g.
                 ``heads/main``.
            sha: The SHA the reference should point to.

        Returns:
            GitHub API response dict.
        """
        api_path = f"/repos/{owner}/{repo}/git/refs/{ref}"
        self._log.info("update_ref", owner=owner, repo=repo, ref=ref, sha=sha[:8])
        return await self._request("PATCH", api_path, json={"sha": sha, "force": False})

    async def get_ref(
        self,
        owner: str,
        repo: str,
        ref: str,
    ) -> dict[str, Any]:
        """Get a Git reference.

        Args:
            owner: Repository owner.
            repo: Repository name.
            ref: Reference path without leading ``refs/``, e.g. ``heads/main``.

        Returns:
            GitHub API response dict containing the reference object and SHA.
        """
        api_path = f"/repos/{owner}/{repo}/git/refs/{ref}"
        self._log.debug("get_ref", owner=owner, repo=repo, ref=ref)
        return await self._request("GET", api_path)

    # ------------------------------------------------------------------
    # Topics
    # ------------------------------------------------------------------

    async def set_topics(
        self,
        owner: str,
        repo: str,
        topics: list[str],
    ) -> dict[str, Any]:
        """Replace all topics on a repository.

        Args:
            owner: Repository owner.
            repo: Repository name.
            topics: List of topic strings (all lowercase, hyphens allowed).

        Returns:
            GitHub API response dict with the updated topic list.
        """
        api_path = f"/repos/{owner}/{repo}/topics"
        # Topics endpoint requires a special Accept header
        self._log.info("set_topics", owner=owner, repo=repo, topics=topics)
        # Temporarily override Accept header for this request
        response = await self._client.put(
            api_path,
            json={"names": topics},
            headers={"Accept": "application/vnd.github.mercy-preview+json"},
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body: dict[str, Any] = {}
            with contextlib.suppress(Exception):
                body = exc.response.json()
            gh_message = body.get("message", str(exc))
            error = _classify_error(
                exc.response.status_code,
                str(gh_message),
                f"PUT {api_path}",
            )
            raise ValueError(error.model_dump_json()) from exc

        result: dict[str, Any] = response.json()
        return result
