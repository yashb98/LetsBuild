"""End-to-end tests for the pipeline controller running layers 1-6.

All LLM calls and GitHub API calls are mocked.  These tests verify that the
PipelineController correctly orchestrates L1 Intake through L6 Publisher,
accumulating results into PipelineState including a populated PublishResult.

Key verifications:
- state.publish_result is populated after L6
- publish_result.repo_url is set
- publish_result.commit_shas is non-empty
- publish_result.commit_plan has commits
- publish_result.readme_url is set
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from letsbuild.models.forge_models import ReviewVerdict
from letsbuild.models.intake_models import (
    JDAnalysis,
    RoleCategory,
    SeniorityLevel,
    Skill,
    TechStack,
)
from letsbuild.models.intelligence_models import (
    CompanyProfile,
    ResearchResult,
    SubAgentResult,
    SubAgentType,
)
from letsbuild.models.shared import GateResult
from letsbuild.pipeline.controller import PipelineController
from letsbuild.publisher.engine import PublisherEngine

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

_RAW_JD_TEXT = "Senior Full-Stack Engineer at Fintech Co"

FAKE_TOKEN = "ghp_fake_token_e2e"
FAKE_OWNER = "testuser"
FAKE_REPO_URL = "https://github.com/testuser/senior-full-stack-engineer-fintech"


# ------------------------------------------------------------------
# Fixtures & helpers
# ------------------------------------------------------------------


def _make_jd_analysis() -> JDAnalysis:
    """Build a valid JDAnalysis for a senior full-stack engineer role."""
    return JDAnalysis(
        role_title="Senior Full-Stack Engineer",
        role_category=RoleCategory.FULL_STACK,
        seniority=SeniorityLevel.SENIOR,
        required_skills=[
            Skill(name="python", category="languages", confidence=90.0),
            Skill(name="react", category="frameworks", confidence=85.0),
        ],
        tech_stack=TechStack(
            languages=["python", "typescript"],
            frameworks=["react", "fastapi"],
        ),
        domain_keywords=["fintech"],
        key_responsibilities=["Build REST APIs", "Design React components"],
        raw_text=_RAW_JD_TEXT,
    )


def _make_company_profile() -> CompanyProfile:
    """Build a minimal CompanyProfile for tests."""
    return CompanyProfile(
        company_name="Unknown Company",
        industry="fintech",
        tech_stack_signals=["python", "react", "fastapi"],
        confidence_score=60.0,
        data_sources=[],
        sub_agent_results=[
            SubAgentResult(
                agent_type=SubAgentType.WEB_PRESENCE,
                success=True,
                execution_time_seconds=0.1,
            ),
        ],
    )


def _make_research_result() -> ResearchResult:
    """Build a ResearchResult wrapping the fake company profile."""
    return ResearchResult(
        company_profile=_make_company_profile(),
        total_execution_time_seconds=0.3,
        agents_succeeded=4,
        agents_failed=2,
        partial=True,
    )


def _make_gate_result(gate_name: str, passed: bool, blocking: bool) -> GateResult:
    """Build a GateResult for mocking the PrePublishHook."""
    return GateResult(
        gate_name=gate_name,
        passed=passed,
        reason="test gate",
        blocking=blocking,
    )


def _mock_github_responses() -> dict[str, Any]:
    """Return mock payloads for all GitHubClient methods used by PublisherEngine."""
    return {
        "create_repo": {"html_url": FAKE_REPO_URL, "name": "senior-full-stack-engineer-fintech"},
        "create_or_update_file": {"commit": {"sha": "init_sha_e2e_abc123"}},
        "create_tree": {"sha": "tree_sha_e2e_abc123"},
        "create_commit": {"sha": "commit_sha_e2e_abc123"},
        "update_ref": {"ref": "refs/heads/main"},
        "set_topics": {"names": ["python", "fastapi", "letsbuild"]},
    }


def _make_publisher_engine() -> PublisherEngine:
    """Create a PublisherEngine with fake credentials (GitHub calls are mocked)."""
    return PublisherEngine(
        github_token=FAKE_TOKEN,
        owner=FAKE_OWNER,
        quality_threshold=50.0,  # Low threshold so heuristic forge output passes
        spread_days=3,
        commit_seed=42,
    )


def _make_controller() -> PipelineController:
    """Create a PipelineController with L1, L2, and GitHub API calls mocked.

    L3 (MatchEngine), L4 (ProjectArchitect), and L5 (Code Forge) are
    pure-Python / heuristic engines that do not call the LLM.
    L6 (PublisherEngine) is injected with a pre-built instance whose GitHub
    network calls are patched in each test.
    """
    controller = PipelineController(publisher_engine=_make_publisher_engine())

    controller.intake_engine.parse_jd = AsyncMock(  # type: ignore[assignment]
        return_value=_make_jd_analysis(),
    )
    controller.intelligence_coordinator.research_company = AsyncMock(  # type: ignore[assignment]
        return_value=_make_research_result(),
    )

    return controller


def _patch_github_client(mock_responses: dict[str, Any]) -> Any:
    """Return a context manager that patches GitHubClient with mock responses."""

    async def mock_request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        # Used by _get_tree_sha_for_commit
        if "/git/commits/" in path and method == "GET":
            return {"tree": {"sha": "base_tree_sha_e2e"}}
        return {}

    mock_client_instance = AsyncMock()
    mock_client_instance.create_repo = AsyncMock(return_value=mock_responses["create_repo"])
    mock_client_instance.create_or_update_file = AsyncMock(
        return_value=mock_responses["create_or_update_file"]
    )
    mock_client_instance.create_tree = AsyncMock(return_value=mock_responses["create_tree"])
    mock_client_instance.create_commit = AsyncMock(return_value=mock_responses["create_commit"])
    mock_client_instance.update_ref = AsyncMock(return_value=mock_responses["update_ref"])
    mock_client_instance.set_topics = AsyncMock(return_value=mock_responses["set_topics"])
    mock_client_instance._request = AsyncMock(side_effect=mock_request)

    return mock_client_instance


# ------------------------------------------------------------------
# Test 1: L1-L6 produces a PublishResult
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l6_produces_publish_result() -> None:
    """Run L1-L6 and verify a PublishResult is populated in state."""
    controller = _make_controller()
    mock_responses = _mock_github_responses()
    mock_client_instance = _patch_github_client(mock_responses)

    all_gates_pass = [
        _make_gate_result("QualityGate", True, True),
        _make_gate_result("ReviewGate", True, True),
        _make_gate_result("SandboxGate", True, True),
        _make_gate_result("SecurityGate", True, True),
        _make_gate_result("ReadmeGate", True, False),
    ]

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(
            controller.publisher_engine._pre_publish,  # type: ignore[union-attr]
            "run",
            new_callable=AsyncMock,
            return_value=all_gates_pass,
        ),
    ):
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        state = await controller.run(jd_text=_RAW_JD_TEXT)

    # L1-L5 outputs must be present
    assert state.jd_analysis is not None
    assert state.company_profile is not None
    assert state.gap_analysis is not None
    assert state.project_spec is not None
    assert state.forge_output is not None

    # L6 output: PublishResult
    assert state.publish_result is not None, "publish_result should be set after L6"


# ------------------------------------------------------------------
# Test 2: PublishResult has a valid repo_url
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l6_publish_result_repo_url() -> None:
    """publish_result.repo_url should be the GitHub URL returned by the API."""
    controller = _make_controller()
    mock_responses = _mock_github_responses()
    mock_client_instance = _patch_github_client(mock_responses)

    all_gates_pass = [
        _make_gate_result("QualityGate", True, True),
        _make_gate_result("ReviewGate", True, True),
        _make_gate_result("SandboxGate", True, True),
        _make_gate_result("SecurityGate", True, True),
        _make_gate_result("ReadmeGate", True, False),
    ]

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(
            controller.publisher_engine._pre_publish,  # type: ignore[union-attr]
            "run",
            new_callable=AsyncMock,
            return_value=all_gates_pass,
        ),
    ):
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        state = await controller.run(jd_text=_RAW_JD_TEXT)

    assert state.publish_result is not None
    assert state.publish_result.repo_url == FAKE_REPO_URL


# ------------------------------------------------------------------
# Test 3: PublishResult has non-empty commit_shas
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l6_publish_result_commit_shas_non_empty() -> None:
    """publish_result.commit_shas must be non-empty (init commit + plan commits)."""
    controller = _make_controller()
    mock_responses = _mock_github_responses()
    mock_client_instance = _patch_github_client(mock_responses)

    all_gates_pass = [
        _make_gate_result("QualityGate", True, True),
        _make_gate_result("ReviewGate", True, True),
        _make_gate_result("SandboxGate", True, True),
        _make_gate_result("SecurityGate", True, True),
        _make_gate_result("ReadmeGate", True, False),
    ]

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(
            controller.publisher_engine._pre_publish,  # type: ignore[union-attr]
            "run",
            new_callable=AsyncMock,
            return_value=all_gates_pass,
        ),
    ):
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        state = await controller.run(jd_text=_RAW_JD_TEXT)

    assert state.publish_result is not None
    assert len(state.publish_result.commit_shas) > 0, "commit_shas should be non-empty"


# ------------------------------------------------------------------
# Test 4: PublishResult.commit_plan has commits
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l6_publish_result_commit_plan_has_commits() -> None:
    """publish_result.commit_plan should contain at least one commit entry."""
    controller = _make_controller()
    mock_responses = _mock_github_responses()
    mock_client_instance = _patch_github_client(mock_responses)

    all_gates_pass = [
        _make_gate_result("QualityGate", True, True),
        _make_gate_result("ReviewGate", True, True),
        _make_gate_result("SandboxGate", True, True),
        _make_gate_result("SecurityGate", True, True),
        _make_gate_result("ReadmeGate", True, False),
    ]

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(
            controller.publisher_engine._pre_publish,  # type: ignore[union-attr]
            "run",
            new_callable=AsyncMock,
            return_value=all_gates_pass,
        ),
    ):
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        state = await controller.run(jd_text=_RAW_JD_TEXT)

    assert state.publish_result is not None
    assert len(state.publish_result.commit_plan.commits) > 0, "commit_plan must have entries"


# ------------------------------------------------------------------
# Test 5: PublishResult.readme_url is set
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l6_publish_result_readme_url() -> None:
    """publish_result.readme_url should point to the README on the main branch."""
    controller = _make_controller()
    mock_responses = _mock_github_responses()
    mock_client_instance = _patch_github_client(mock_responses)

    all_gates_pass = [
        _make_gate_result("QualityGate", True, True),
        _make_gate_result("ReviewGate", True, True),
        _make_gate_result("SandboxGate", True, True),
        _make_gate_result("SecurityGate", True, True),
        _make_gate_result("ReadmeGate", True, False),
    ]

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(
            controller.publisher_engine._pre_publish,  # type: ignore[union-attr]
            "run",
            new_callable=AsyncMock,
            return_value=all_gates_pass,
        ),
    ):
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        state = await controller.run(jd_text=_RAW_JD_TEXT)

    assert state.publish_result is not None
    assert "README.md" in state.publish_result.readme_url
    assert state.publish_result.readme_url.startswith("https://github.com/")


# ------------------------------------------------------------------
# Test 6: L6 skipped when no publisher_engine configured
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l6_skips_publisher_when_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pipeline should complete successfully without publish_result when no token."""
    # Ensure env vars are absent
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_OWNER", raising=False)

    # Build controller WITHOUT an injected publisher_engine
    controller = PipelineController()
    controller.intake_engine.parse_jd = AsyncMock(  # type: ignore[assignment]
        return_value=_make_jd_analysis(),
    )
    controller.intelligence_coordinator.research_company = AsyncMock(  # type: ignore[assignment]
        return_value=_make_research_result(),
    )

    state = await controller.run(jd_text=_RAW_JD_TEXT)

    # L1-L5 should succeed; L6 was skipped
    assert state.forge_output is not None, "forge_output should be set even when L6 skipped"
    assert state.publish_result is None, "publish_result must be None when publisher skipped"
    assert len(state.errors) == 0


# ------------------------------------------------------------------
# Test 7: Pipeline metrics include publisher layer duration
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l6_metrics_include_publisher_duration() -> None:
    """Pipeline metrics must record the 'publisher' layer duration."""
    controller = _make_controller()
    mock_responses = _mock_github_responses()
    mock_client_instance = _patch_github_client(mock_responses)

    all_gates_pass = [
        _make_gate_result("QualityGate", True, True),
        _make_gate_result("ReviewGate", True, True),
        _make_gate_result("SandboxGate", True, True),
        _make_gate_result("SecurityGate", True, True),
        _make_gate_result("ReadmeGate", True, False),
    ]

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(
            controller.publisher_engine._pre_publish,  # type: ignore[union-attr]
            "run",
            new_callable=AsyncMock,
            return_value=all_gates_pass,
        ),
    ):
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        state = await controller.run(jd_text=_RAW_JD_TEXT)

    assert "publisher" in state.metrics.layer_durations
    assert state.metrics.layer_durations["publisher"] >= 0.0


# ------------------------------------------------------------------
# Test 8: Forge output has a passing review verdict (regression guard)
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l6_forge_review_verdict_passes() -> None:
    """Forge review_verdict must be PASS or PASS_WITH_SUGGESTIONS in L1-L6 flow."""
    controller = _make_controller()
    mock_responses = _mock_github_responses()
    mock_client_instance = _patch_github_client(mock_responses)

    all_gates_pass = [
        _make_gate_result("QualityGate", True, True),
        _make_gate_result("ReviewGate", True, True),
        _make_gate_result("SandboxGate", True, True),
        _make_gate_result("SecurityGate", True, True),
        _make_gate_result("ReadmeGate", True, False),
    ]

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(
            controller.publisher_engine._pre_publish,  # type: ignore[union-attr]
            "run",
            new_callable=AsyncMock,
            return_value=all_gates_pass,
        ),
    ):
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        state = await controller.run(jd_text=_RAW_JD_TEXT)

    assert state.forge_output is not None
    assert state.forge_output.review_verdict in (
        ReviewVerdict.PASS,
        ReviewVerdict.PASS_WITH_SUGGESTIONS,
    )
