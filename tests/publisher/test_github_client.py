"""Tests for GitHubClient — async httpx wrapper for the GitHub REST API."""

from __future__ import annotations

import base64
import json

import httpx
import pytest
import respx

from letsbuild.models.publisher_models import RepoConfig
from letsbuild.models.shared import ErrorCategory
from letsbuild.publisher.github_client import GitHubClient, _classify_error

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GITHUB_BASE = "https://api.github.com"
FAKE_TOKEN = "ghp_test_token_fake"


@pytest.fixture
def repo_config() -> RepoConfig:
    return RepoConfig(
        repo_name="my-test-repo",
        description="A test repository.",
        private=True,
        topics=["python", "fastapi", "letsbuild"],
    )


# ---------------------------------------------------------------------------
# _classify_error unit tests
# ---------------------------------------------------------------------------


def test_classify_error_429_returns_transient_retryable() -> None:
    """HTTP 429 (rate limit) should map to TRANSIENT + is_retryable=True."""
    err = _classify_error(429, "rate limit exceeded", "POST /user/repos")
    assert err.error_category == ErrorCategory.TRANSIENT
    assert err.is_retryable is True
    assert "rate limit" in err.message.lower()


def test_classify_error_404_returns_business_not_retryable() -> None:
    """HTTP 404 (not found) should map to BUSINESS + is_retryable=False."""
    err = _classify_error(404, "not found", "GET /repos/foo/bar")
    assert err.error_category == ErrorCategory.BUSINESS
    assert err.is_retryable is False
    assert "not found" in err.message.lower()


def test_classify_error_401_returns_permission_not_retryable() -> None:
    """HTTP 401 (unauthorized) should map to PERMISSION + is_retryable=False."""
    err = _classify_error(401, "bad credentials", "POST /user/repos")
    assert err.error_category == ErrorCategory.PERMISSION
    assert err.is_retryable is False
    assert "unauthorised" in err.message.lower()


def test_classify_error_403_returns_permission_not_retryable() -> None:
    """HTTP 403 (forbidden) should map to PERMISSION + is_retryable=False."""
    err = _classify_error(403, "forbidden", "PUT /repos/owner/repo/contents/file.py")
    assert err.error_category == ErrorCategory.PERMISSION
    assert err.is_retryable is False


def test_classify_error_422_returns_validation_not_retryable() -> None:
    """HTTP 422 (unprocessable) should map to VALIDATION + is_retryable=False."""
    err = _classify_error(422, "validation failed", "POST /user/repos")
    assert err.error_category == ErrorCategory.VALIDATION
    assert err.is_retryable is False


def test_classify_error_500_returns_transient_retryable() -> None:
    """HTTP 5xx server errors should map to TRANSIENT + is_retryable=True."""
    err = _classify_error(503, "service unavailable", "GET /rate_limit")
    assert err.error_category == ErrorCategory.TRANSIENT
    assert err.is_retryable is True


def test_classify_error_includes_attempted_query() -> None:
    """The attempted_query field should be preserved in the StructuredError."""
    query = "POST /user/repos"
    err = _classify_error(429, "rate limit", query)
    assert err.attempted_query == query


# ---------------------------------------------------------------------------
# GitHubClient.create_repo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_create_repo_returns_response_dict(repo_config: RepoConfig) -> None:
    """create_repo should POST to /user/repos and return the GitHub API dict."""
    mock_response = {
        "id": 123456,
        "name": repo_config.repo_name,
        "html_url": f"https://github.com/testuser/{repo_config.repo_name}",
        "private": True,
    }
    respx.post(f"{GITHUB_BASE}/user/repos").mock(
        return_value=httpx.Response(201, json=mock_response)
    )

    async with GitHubClient(FAKE_TOKEN, base_url=GITHUB_BASE) as client:
        result = await client.create_repo(repo_config)

    assert result["name"] == repo_config.repo_name
    assert result["html_url"] == f"https://github.com/testuser/{repo_config.repo_name}"
    assert result["private"] is True


@pytest.mark.asyncio
@respx.mock
async def test_create_repo_with_org_posts_to_org_endpoint(repo_config: RepoConfig) -> None:
    """When org is given, create_repo should POST to /orgs/<org>/repos."""
    org = "myorg"
    mock_response = {
        "name": repo_config.repo_name,
        "html_url": f"https://github.com/{org}/{repo_config.repo_name}",
    }
    respx.post(f"{GITHUB_BASE}/orgs/{org}/repos").mock(
        return_value=httpx.Response(201, json=mock_response)
    )

    async with GitHubClient(FAKE_TOKEN, base_url=GITHUB_BASE) as client:
        result = await client.create_repo(repo_config, org=org)

    assert result["html_url"] == f"https://github.com/{org}/{repo_config.repo_name}"


@pytest.mark.asyncio
@respx.mock
async def test_create_repo_raises_on_401(repo_config: RepoConfig) -> None:
    """create_repo should raise ValueError (with StructuredError JSON) on HTTP 401."""
    respx.post(f"{GITHUB_BASE}/user/repos").mock(
        return_value=httpx.Response(401, json={"message": "Bad credentials"})
    )

    async with GitHubClient(FAKE_TOKEN, base_url=GITHUB_BASE) as client:
        with pytest.raises(ValueError) as exc_info:
            await client.create_repo(repo_config)

    # The ValueError message should contain StructuredError JSON
    err_data = json.loads(str(exc_info.value))
    assert err_data["error_category"] == ErrorCategory.PERMISSION
    assert err_data["is_retryable"] is False


@pytest.mark.asyncio
@respx.mock
async def test_create_repo_raises_on_429(repo_config: RepoConfig) -> None:
    """create_repo should raise ValueError with transient+retryable on HTTP 429."""
    respx.post(f"{GITHUB_BASE}/user/repos").mock(
        return_value=httpx.Response(429, json={"message": "rate limit exceeded"})
    )

    async with GitHubClient(FAKE_TOKEN, base_url=GITHUB_BASE) as client:
        with pytest.raises(ValueError) as exc_info:
            await client.create_repo(repo_config)

    err_data = json.loads(str(exc_info.value))
    assert err_data["error_category"] == ErrorCategory.TRANSIENT
    assert err_data["is_retryable"] is True


# ---------------------------------------------------------------------------
# GitHubClient.create_or_update_file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_file_encodes_content_to_base64() -> None:
    """create_or_update_file must base64-encode the content before sending."""
    raw_content = 'print("hello world")\n'
    expected_encoded = base64.b64encode(raw_content.encode()).decode()

    captured_body: dict = {}

    def capture_request(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return httpx.Response(
            201,
            json={
                "content": {"path": "src/main.py"},
                "commit": {"sha": "abc123def456", "message": "feat: add main"},
            },
        )

    respx.put(f"{GITHUB_BASE}/repos/testuser/testrepo/contents/src/main.py").mock(
        side_effect=capture_request
    )

    async with GitHubClient(FAKE_TOKEN, base_url=GITHUB_BASE) as client:
        result = await client.create_or_update_file(
            owner="testuser",
            repo="testrepo",
            path="src/main.py",
            content=raw_content,
            message="feat: add main",
        )

    assert captured_body["content"] == expected_encoded
    assert result["commit"]["sha"] == "abc123def456"


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_file_includes_sha_when_updating() -> None:
    """When sha is provided (file update), it must appear in the request body."""
    captured_body: dict = {}

    def capture_request(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"content": {}, "commit": {"sha": "newsha123"}},
        )

    respx.put(f"{GITHUB_BASE}/repos/owner/repo/contents/file.txt").mock(side_effect=capture_request)

    async with GitHubClient(FAKE_TOKEN, base_url=GITHUB_BASE) as client:
        await client.create_or_update_file(
            owner="owner",
            repo="repo",
            path="file.txt",
            content="updated content",
            message="fix: update file",
            sha="existingsha999",
        )

    assert captured_body.get("sha") == "existingsha999"


# ---------------------------------------------------------------------------
# GitHubClient context manager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_context_manager_aenter_returns_client() -> None:
    """GitHubClient used as async context manager should return self from __aenter__."""
    client = GitHubClient(FAKE_TOKEN, base_url=GITHUB_BASE)
    async with client as c:
        assert c is client


@pytest.mark.asyncio
@respx.mock
async def test_context_manager_aexit_closes_client() -> None:
    """After exiting the context manager, subsequent calls should be closed cleanly."""
    client = GitHubClient(FAKE_TOKEN, base_url=GITHUB_BASE)
    async with client:
        pass
    # Verify that the underlying httpx client is closed (is_closed attribute)
    assert client._client.is_closed


# ---------------------------------------------------------------------------
# GitHubClient.create_tree, create_commit, update_ref
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_create_tree_returns_sha() -> None:
    """create_tree should return the tree SHA from the API response."""
    tree_sha = "deadbeef1234567890abcdef"
    respx.post(f"{GITHUB_BASE}/repos/owner/repo/git/trees").mock(
        return_value=httpx.Response(201, json={"sha": tree_sha, "url": "https://..."})
    )

    async with GitHubClient(FAKE_TOKEN, base_url=GITHUB_BASE) as client:
        result = await client.create_tree(
            owner="owner",
            repo="repo",
            tree_items=[{"path": "src/main.py", "mode": "100644", "type": "blob", "content": "x"}],
        )

    assert result["sha"] == tree_sha


@pytest.mark.asyncio
@respx.mock
async def test_create_commit_returns_commit_sha() -> None:
    """create_commit should return the new commit SHA."""
    commit_sha = "1234567890abcdefdeadbeef"
    respx.post(f"{GITHUB_BASE}/repos/owner/repo/git/commits").mock(
        return_value=httpx.Response(
            201,
            json={"sha": commit_sha, "message": "feat: add module"},
        )
    )

    async with GitHubClient(FAKE_TOKEN, base_url=GITHUB_BASE) as client:
        result = await client.create_commit(
            owner="owner",
            repo="repo",
            message="feat: add module",
            tree_sha="treeshaabc",
            parent_shas=["parentsha123"],
        )

    assert result["sha"] == commit_sha


@pytest.mark.asyncio
@respx.mock
async def test_update_ref_sends_sha_and_force_false() -> None:
    """update_ref should PATCH the ref endpoint with sha and force=False."""
    captured_body: dict = {}

    def capture_request(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return httpx.Response(200, json={"ref": "refs/heads/main", "object": {"sha": "newsha"}})

    respx.patch(f"{GITHUB_BASE}/repos/owner/repo/git/refs/heads/main").mock(
        side_effect=capture_request
    )

    async with GitHubClient(FAKE_TOKEN, base_url=GITHUB_BASE) as client:
        await client.update_ref(owner="owner", repo="repo", ref="heads/main", sha="newsha123")

    assert captured_body["sha"] == "newsha123"
    assert captured_body["force"] is False


# ---------------------------------------------------------------------------
# GitHubClient.set_topics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_set_topics_returns_topics_dict() -> None:
    """set_topics should PUT to the topics endpoint and return the response."""
    topics = ["python", "fastapi", "letsbuild"]
    respx.put(f"{GITHUB_BASE}/repos/owner/repo/topics").mock(
        return_value=httpx.Response(200, json={"names": topics})
    )

    async with GitHubClient(FAKE_TOKEN, base_url=GITHUB_BASE) as client:
        result = await client.set_topics(owner="owner", repo="repo", topics=topics)

    assert result["names"] == topics
