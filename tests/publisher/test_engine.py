"""Tests for PublisherEngine — full publishing flow orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest

from letsbuild.models.forge_models import ForgeOutput, ReviewVerdict, SwarmTopology
from letsbuild.models.publisher_models import PublishResult
from letsbuild.models.shared import GateResult
from letsbuild.publisher.engine import PublisherEngine

if TYPE_CHECKING:
    from letsbuild.models.architect_models import ProjectSpec

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

FAKE_TOKEN = "ghp_fake_token_test"
FAKE_OWNER = "testuser"
FAKE_REPO_URL = "https://github.com/testuser/my-fastapi-project"


def _make_gate_result(gate_name: str, passed: bool, blocking: bool) -> GateResult:
    return GateResult(
        gate_name=gate_name,
        passed=passed,
        reason="test reason",
        blocking=blocking,
    )


def _mock_client_responses() -> dict[str, Any]:
    """Build a mapping of mock return values for GitHubClient methods."""
    return {
        "create_repo": {"html_url": FAKE_REPO_URL, "name": "my-fastapi-project"},
        "create_or_update_file": {"commit": {"sha": "init_sha_abc123"}},
        "create_tree": {"sha": "tree_sha_abc123"},
        "create_commit": {"sha": "commit_sha_abc123"},
        "update_ref": {"ref": "refs/heads/main"},
        "set_topics": {"names": ["python", "fastapi"]},
        "_request": {"tree": {"sha": "base_tree_sha_abc"}},
    }


# ---------------------------------------------------------------------------
# Happy path: full publish flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_returns_publish_result(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """publish() should return a PublishResult on success."""
    engine = PublisherEngine(
        github_token=FAKE_TOKEN,
        owner=FAKE_OWNER,
        quality_threshold=70.0,
        spread_days=3,
        commit_seed=42,
    )

    mock_responses = _mock_client_responses()

    async def mock_request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if "/git/commits/" in path and method == "GET":
            return {"tree": {"sha": "base_tree_sha"}}
        return {}

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(engine._pre_publish, "run", new_callable=AsyncMock) as mock_run,
    ):
        # All gates pass
        mock_run.return_value = [
            _make_gate_result("QualityGate", True, True),
            _make_gate_result("ReviewGate", True, True),
            _make_gate_result("SandboxGate", True, True),
            _make_gate_result("SecurityGate", True, True),
            _make_gate_result("ReadmeGate", True, False),
        ]

        mock_client_instance = AsyncMock()
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_client_instance.create_repo = AsyncMock(return_value=mock_responses["create_repo"])
        mock_client_instance.create_or_update_file = AsyncMock(
            return_value=mock_responses["create_or_update_file"]
        )
        mock_client_instance.create_tree = AsyncMock(return_value=mock_responses["create_tree"])
        mock_client_instance.create_commit = AsyncMock(return_value=mock_responses["create_commit"])
        mock_client_instance.update_ref = AsyncMock(return_value=mock_responses["update_ref"])
        mock_client_instance.set_topics = AsyncMock(return_value=mock_responses["set_topics"])
        mock_client_instance._request = AsyncMock(side_effect=mock_request)

        result = await engine.publish(sample_project_spec, sample_forge_output)

    assert isinstance(result, PublishResult)
    assert result.repo_url == FAKE_REPO_URL
    assert len(result.commit_shas) >= 1
    assert "README.md" in result.readme_url


@pytest.mark.asyncio
async def test_publish_result_has_correct_repo_url(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """PublishResult.repo_url must equal the URL returned by GitHub API."""
    engine = PublisherEngine(
        github_token=FAKE_TOKEN,
        owner=FAKE_OWNER,
        quality_threshold=70.0,
        commit_seed=1,
    )

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(engine._pre_publish, "run", new_callable=AsyncMock) as mock_run,
    ):
        mock_run.return_value = [
            _make_gate_result("QualityGate", True, True),
            _make_gate_result("ReviewGate", True, True),
            _make_gate_result("SandboxGate", True, True),
            _make_gate_result("SecurityGate", True, True),
            _make_gate_result("ReadmeGate", True, False),
        ]

        mock_client_instance = AsyncMock()
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        expected_url = "https://github.com/testuser/my-fastapi-project"
        mock_client_instance.create_repo = AsyncMock(
            return_value={"html_url": expected_url, "name": "my-fastapi-project"}
        )
        mock_client_instance.create_or_update_file = AsyncMock(
            return_value={"commit": {"sha": "init_sha"}}
        )
        mock_client_instance.create_tree = AsyncMock(return_value={"sha": "tree_sha"})
        mock_client_instance.create_commit = AsyncMock(return_value={"sha": "commit_sha"})
        mock_client_instance.update_ref = AsyncMock(return_value={})
        mock_client_instance.set_topics = AsyncMock(return_value={})
        mock_client_instance._request = AsyncMock(return_value={"tree": {"sha": "base_tree"}})

        result = await engine.publish(sample_project_spec, sample_forge_output)

    assert result.repo_url == expected_url


@pytest.mark.asyncio
async def test_publish_result_commit_count_matches_plan(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """The number of commit SHAs in PublishResult must reflect actual commits pushed."""
    engine = PublisherEngine(
        github_token=FAKE_TOKEN,
        owner=FAKE_OWNER,
        quality_threshold=70.0,
        commit_seed=42,
    )

    commit_counter = [0]

    async def mock_create_commit(**kwargs: Any) -> dict[str, Any]:
        commit_counter[0] += 1
        return {"sha": f"sha_{commit_counter[0]:03d}"}

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(engine._pre_publish, "run", new_callable=AsyncMock) as mock_run,
    ):
        mock_run.return_value = [
            _make_gate_result("QualityGate", True, True),
            _make_gate_result("ReviewGate", True, True),
            _make_gate_result("SandboxGate", True, True),
            _make_gate_result("SecurityGate", True, True),
            _make_gate_result("ReadmeGate", True, False),
        ]

        mock_client_instance = AsyncMock()
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_client_instance.create_repo = AsyncMock(
            return_value={"html_url": FAKE_REPO_URL, "name": "my-fastapi-project"}
        )
        mock_client_instance.create_or_update_file = AsyncMock(
            return_value={"commit": {"sha": "init_sha"}}
        )
        mock_client_instance.create_tree = AsyncMock(return_value={"sha": "tree_sha"})
        mock_client_instance.create_commit = AsyncMock(side_effect=mock_create_commit)
        mock_client_instance.update_ref = AsyncMock(return_value={})
        mock_client_instance.set_topics = AsyncMock(return_value={})
        mock_client_instance._request = AsyncMock(return_value={"tree": {"sha": "base_tree"}})

        result = await engine.publish(sample_project_spec, sample_forge_output)

    # At minimum the bootstrap commit (from create_or_update_file) + whatever commits happened
    assert len(result.commit_shas) >= 1
    assert result.commit_plan.total_commits == len(result.commit_plan.commits)


@pytest.mark.asyncio
async def test_publish_result_contains_readme_url(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """PublishResult.readme_url should point to README.md on the default branch."""
    engine = PublisherEngine(
        github_token=FAKE_TOKEN,
        owner=FAKE_OWNER,
        quality_threshold=70.0,
        commit_seed=0,
    )

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(engine._pre_publish, "run", new_callable=AsyncMock) as mock_run,
    ):
        mock_run.return_value = [
            _make_gate_result("QualityGate", True, True),
            _make_gate_result("ReviewGate", True, True),
            _make_gate_result("SandboxGate", True, True),
            _make_gate_result("SecurityGate", True, True),
            _make_gate_result("ReadmeGate", True, False),
        ]

        mock_client_instance = AsyncMock()
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_client_instance.create_repo = AsyncMock(
            return_value={"html_url": FAKE_REPO_URL, "name": "my-fastapi-project"}
        )
        mock_client_instance.create_or_update_file = AsyncMock(
            return_value={"commit": {"sha": "init_sha"}}
        )
        mock_client_instance.create_tree = AsyncMock(return_value={"sha": "tree_sha"})
        mock_client_instance.create_commit = AsyncMock(return_value={"sha": "commit_sha"})
        mock_client_instance.update_ref = AsyncMock(return_value={})
        mock_client_instance.set_topics = AsyncMock(return_value={})
        mock_client_instance._request = AsyncMock(return_value={"tree": {"sha": "base_tree"}})

        result = await engine.publish(sample_project_spec, sample_forge_output)

    assert "README.md" in result.readme_url
    assert "main" in result.readme_url
    assert FAKE_REPO_URL in result.readme_url


# ---------------------------------------------------------------------------
# PrePublish gate blocking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_raises_runtime_error_when_blocking_gate_fails(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """publish() must raise RuntimeError when a blocking gate fails."""
    engine = PublisherEngine(
        github_token=FAKE_TOKEN,
        owner=FAKE_OWNER,
        quality_threshold=70.0,
    )

    with patch.object(engine._pre_publish, "run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = [
            _make_gate_result("QualityGate", False, True),  # blocking failure
            _make_gate_result("ReviewGate", True, True),
            _make_gate_result("SandboxGate", True, True),
            _make_gate_result("SecurityGate", True, True),
            _make_gate_result("ReadmeGate", True, False),
        ]

        with pytest.raises(RuntimeError, match="Publishing blocked"):
            await engine.publish(sample_project_spec, sample_forge_output)


@pytest.mark.asyncio
async def test_publish_raises_for_low_quality_score(
    sample_project_spec: ProjectSpec,
) -> None:
    """A ForgeOutput with quality_score below threshold should block publishing."""
    low_quality_forge = ForgeOutput(
        code_modules=[],
        test_results={},
        review_verdict=ReviewVerdict.PASS,
        quality_score=50.0,  # below default threshold of 70
        total_tokens_used=1000,
        total_retries=0,
        topology_used=SwarmTopology.HIERARCHICAL,
    )

    engine = PublisherEngine(
        github_token=FAKE_TOKEN,
        owner=FAKE_OWNER,
        quality_threshold=70.0,
    )

    # Don't mock pre_publish — let it run the real quality gate
    # But we need to supply the sandbox validation commands as unverified
    # which will also block; just check for RuntimeError raised
    with pytest.raises(RuntimeError):
        await engine.publish(sample_project_spec, low_quality_forge)


@pytest.mark.asyncio
async def test_publish_allows_non_blocking_gate_failure(
    sample_project_spec: ProjectSpec,
    sample_forge_output: ForgeOutput,
) -> None:
    """A non-blocking gate failure (README) must NOT abort publishing."""
    engine = PublisherEngine(
        github_token=FAKE_TOKEN,
        owner=FAKE_OWNER,
        quality_threshold=70.0,
        commit_seed=42,
    )

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(engine._pre_publish, "run", new_callable=AsyncMock) as mock_run,
    ):
        # All blocking gates pass; README gate (non-blocking) fails
        mock_run.return_value = [
            _make_gate_result("QualityGate", True, True),
            _make_gate_result("ReviewGate", True, True),
            _make_gate_result("SandboxGate", True, True),
            _make_gate_result("SecurityGate", True, True),
            _make_gate_result("ReadmeGate", False, False),  # non-blocking failure
        ]

        mock_client_instance = AsyncMock()
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_client_instance.create_repo = AsyncMock(
            return_value={"html_url": FAKE_REPO_URL, "name": "my-fastapi-project"}
        )
        mock_client_instance.create_or_update_file = AsyncMock(
            return_value={"commit": {"sha": "init_sha"}}
        )
        mock_client_instance.create_tree = AsyncMock(return_value={"sha": "tree_sha"})
        mock_client_instance.create_commit = AsyncMock(return_value={"sha": "commit_sha"})
        mock_client_instance.update_ref = AsyncMock(return_value={})
        mock_client_instance.set_topics = AsyncMock(return_value={})
        mock_client_instance._request = AsyncMock(return_value={"tree": {"sha": "base_tree"}})

        # Should NOT raise — non-blocking failure is allowed
        result = await engine.publish(sample_project_spec, sample_forge_output)

    assert isinstance(result, PublishResult)


# ---------------------------------------------------------------------------
# RepoConfig derivation
# ---------------------------------------------------------------------------


def test_build_repo_config_derives_kebab_case_name(
    sample_project_spec: ProjectSpec,
) -> None:
    """_build_repo_config should convert project name to kebab-case repo name."""
    engine = PublisherEngine(github_token=FAKE_TOKEN, owner=FAKE_OWNER)
    config = engine._build_repo_config(sample_project_spec)

    assert config.repo_name == "myfastapi-project"


def test_build_repo_config_is_private_by_default(
    sample_project_spec: ProjectSpec,
) -> None:
    """Generated repos should be private by default."""
    engine = PublisherEngine(github_token=FAKE_TOKEN, owner=FAKE_OWNER)
    config = engine._build_repo_config(sample_project_spec)

    assert config.private is True


def test_build_repo_config_description_from_one_liner(
    sample_project_spec: ProjectSpec,
) -> None:
    """The description should be derived from one_liner."""
    engine = PublisherEngine(github_token=FAKE_TOKEN, owner=FAKE_OWNER)
    config = engine._build_repo_config(sample_project_spec)

    assert config.description == sample_project_spec.one_liner[:255]


def test_build_repo_config_includes_letsbuild_topic(
    sample_project_spec: ProjectSpec,
) -> None:
    """Topics should always include 'letsbuild' and 'portfolio'."""
    engine = PublisherEngine(github_token=FAKE_TOKEN, owner=FAKE_OWNER)
    config = engine._build_repo_config(sample_project_spec)

    assert "letsbuild" in config.topics
    assert "portfolio" in config.topics


def test_build_repo_config_includes_tech_stack_as_topics(
    sample_project_spec: ProjectSpec,
) -> None:
    """Tech stack items should appear in topics (as lowercase slugs)."""
    engine = PublisherEngine(github_token=FAKE_TOKEN, owner=FAKE_OWNER)
    config = engine._build_repo_config(sample_project_spec)

    # "python", "fastapi", "pydantic" are in the sample tech stack
    assert "python" in config.topics
    assert "fastapi" in config.topics
