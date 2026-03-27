"""End-to-end tests for the pipeline controller running layers 1-7.

All LLM calls and GitHub API calls are mocked.  These tests verify that the
PipelineController correctly orchestrates L1 Intake through L7 Content Factory,
accumulating results into PipelineState including populated content_outputs.

Key verifications:
- state.content_outputs is non-empty after L7
- Each ContentOutput has the correct ContentFormat
- Content references the project name
- Pipeline works with and without L6 (PublishResult)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from letsbuild.models.content_models import ContentFormat
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

FAKE_TOKEN = "ghp_fake_token_e2e_l7"
FAKE_OWNER = "testuser"
FAKE_REPO_URL = "https://github.com/testuser/senior-full-stack-engineer-fintech"


# ------------------------------------------------------------------
# Fixtures & helpers (shared pattern from test_e2e_l1_l6.py)
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
        "create_or_update_file": {"commit": {"sha": "init_sha_e2e_l7_abc123"}},
        "create_tree": {"sha": "tree_sha_e2e_l7_abc123"},
        "create_commit": {"sha": "commit_sha_e2e_l7_abc123"},
        "update_ref": {"ref": "refs/heads/main"},
        "set_topics": {"names": ["python", "fastapi", "letsbuild"]},
    }


def _make_publisher_engine() -> PublisherEngine:
    """Create a PublisherEngine with fake credentials (GitHub calls are mocked)."""
    return PublisherEngine(
        github_token=FAKE_TOKEN,
        owner=FAKE_OWNER,
        quality_threshold=50.0,
        spread_days=3,
        commit_seed=42,
    )


def _make_controller_with_publisher() -> PipelineController:
    """Create a PipelineController with L1, L2, and GitHub API calls mocked.

    L3-L5 are pure-Python heuristic engines.
    L6 publisher engine is injected.
    """
    controller = PipelineController(publisher_engine=_make_publisher_engine())

    controller.intake_engine.parse_jd = AsyncMock(  # type: ignore[assignment]
        return_value=_make_jd_analysis(),
    )
    controller.intelligence_coordinator.research_company = AsyncMock(  # type: ignore[assignment]
        return_value=_make_research_result(),
    )

    return controller


def _make_controller_without_publisher() -> PipelineController:
    """Create a PipelineController without a publisher engine (L6 skipped)."""
    controller = PipelineController()

    controller.intake_engine.parse_jd = AsyncMock(  # type: ignore[assignment]
        return_value=_make_jd_analysis(),
    )
    controller.intelligence_coordinator.research_company = AsyncMock(  # type: ignore[assignment]
        return_value=_make_research_result(),
    )

    return controller


def _patch_github_client(mock_responses: dict[str, Any]) -> Any:
    """Return a mock GitHubClient instance with patched responses."""

    async def mock_request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if "/git/commits/" in path and method == "GET":
            return {"tree": {"sha": "base_tree_sha_e2e_l7"}}
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


_ALL_GATES_PASS = [
    _make_gate_result("QualityGate", True, True),
    _make_gate_result("ReviewGate", True, True),
    _make_gate_result("SandboxGate", True, True),
    _make_gate_result("SecurityGate", True, True),
    _make_gate_result("ReadmeGate", True, False),
]


# ------------------------------------------------------------------
# Test 1: L1-L7 (with L6) produces non-empty content_outputs
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l7_content_outputs_non_empty_with_publisher() -> None:
    """Run L1-L7 with L6 publisher active and verify content_outputs is non-empty."""
    controller = _make_controller_with_publisher()
    mock_client_instance = _patch_github_client(_mock_github_responses())

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(
            controller.publisher_engine._pre_publish,  # type: ignore[union-attr]
            "run",
            new_callable=AsyncMock,
            return_value=_ALL_GATES_PASS,
        ),
    ):
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        state = await controller.run(jd_text=_RAW_JD_TEXT)

    assert state.content_outputs, "content_outputs must be non-empty after L7"


# ------------------------------------------------------------------
# Test 2: content_outputs contains all 5 ContentFormat values
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l7_content_outputs_has_all_formats() -> None:
    """content_outputs should contain one entry per ContentFormat."""
    controller = _make_controller_with_publisher()
    mock_client_instance = _patch_github_client(_mock_github_responses())

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(
            controller.publisher_engine._pre_publish,  # type: ignore[union-attr]
            "run",
            new_callable=AsyncMock,
            return_value=_ALL_GATES_PASS,
        ),
    ):
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        state = await controller.run(jd_text=_RAW_JD_TEXT)

    formats_generated = {c.format for c in state.content_outputs}
    assert formats_generated == set(ContentFormat), (
        f"Expected all 5 formats, got: {formats_generated}"
    )


# ------------------------------------------------------------------
# Test 3: Each ContentOutput has the correct format field
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l7_each_content_output_has_correct_format() -> None:
    """Each ContentOutput format field must match a known ContentFormat value."""
    controller = _make_controller_with_publisher()
    mock_client_instance = _patch_github_client(_mock_github_responses())

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(
            controller.publisher_engine._pre_publish,  # type: ignore[union-attr]
            "run",
            new_callable=AsyncMock,
            return_value=_ALL_GATES_PASS,
        ),
    ):
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        state = await controller.run(jd_text=_RAW_JD_TEXT)

    valid_formats = set(ContentFormat)
    for output in state.content_outputs:
        assert output.format in valid_formats, f"Unknown format: {output.format}"


# ------------------------------------------------------------------
# Test 4: Content references the project name
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l7_content_references_project_name() -> None:
    """At least one ContentOutput should reference the project_spec.project_name."""
    controller = _make_controller_with_publisher()
    mock_client_instance = _patch_github_client(_mock_github_responses())

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(
            controller.publisher_engine._pre_publish,  # type: ignore[union-attr]
            "run",
            new_callable=AsyncMock,
            return_value=_ALL_GATES_PASS,
        ),
    ):
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        state = await controller.run(jd_text=_RAW_JD_TEXT)

    assert state.project_spec is not None
    project_name = state.project_spec.project_name

    project_name_found = any(
        project_name in output.content or project_name in output.title
        for output in state.content_outputs
    )
    assert project_name_found, f"No ContentOutput references project name '{project_name}'"


# ------------------------------------------------------------------
# Test 5: All ContentOutputs have non-empty content
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l7_all_content_outputs_non_empty() -> None:
    """Every ContentOutput must have non-empty content and title."""
    controller = _make_controller_with_publisher()
    mock_client_instance = _patch_github_client(_mock_github_responses())

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(
            controller.publisher_engine._pre_publish,  # type: ignore[union-attr]
            "run",
            new_callable=AsyncMock,
            return_value=_ALL_GATES_PASS,
        ),
    ):
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        state = await controller.run(jd_text=_RAW_JD_TEXT)

    for output in state.content_outputs:
        assert output.content.strip(), f"{output.format}: content must not be empty"
        assert output.title.strip(), f"{output.format}: title must not be empty"


# ------------------------------------------------------------------
# Test 6: L7 runs even when L6 is skipped (no publisher token)
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l7_content_generated_without_publisher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Content Factory must still generate outputs when L6 (Publisher) is skipped."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_OWNER", raising=False)

    controller = _make_controller_without_publisher()

    state = await controller.run(jd_text=_RAW_JD_TEXT)

    # L6 was skipped
    assert state.publish_result is None, "publish_result must be None (L6 skipped)"

    # L7 should still run
    assert state.content_outputs, "content_outputs must be non-empty even when L6 skipped"
    assert len(state.content_outputs) == len(ContentFormat)


# ------------------------------------------------------------------
# Test 7: L7 content uses placeholder repo_url when L6 skipped
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l7_content_uses_placeholder_url_when_no_publisher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When L6 is skipped, content should reference a placeholder URL."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_OWNER", raising=False)

    controller = _make_controller_without_publisher()

    state = await controller.run(jd_text=_RAW_JD_TEXT)

    assert state.content_outputs
    # Each content piece should have some URL-like string in the content
    for output in state.content_outputs:
        assert "github.com" in output.content.lower() or "github" in output.content.lower(), (
            f"{output.format}: content should reference github"
        )


# ------------------------------------------------------------------
# Test 8: Pipeline metrics include content layer duration
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l7_metrics_include_content_duration() -> None:
    """Pipeline metrics must record the 'content' layer duration after L7."""
    controller = _make_controller_with_publisher()
    mock_client_instance = _patch_github_client(_mock_github_responses())

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(
            controller.publisher_engine._pre_publish,  # type: ignore[union-attr]
            "run",
            new_callable=AsyncMock,
            return_value=_ALL_GATES_PASS,
        ),
    ):
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        state = await controller.run(jd_text=_RAW_JD_TEXT)

    assert "content" in state.metrics.layer_durations
    assert state.metrics.layer_durations["content"] >= 0.0


# ------------------------------------------------------------------
# Test 9: Full L1-L7 state accumulation (regression guard)
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l7_full_state_accumulation() -> None:
    """All layer outputs must be populated in a successful L1-L7 run."""
    controller = _make_controller_with_publisher()
    mock_client_instance = _patch_github_client(_mock_github_responses())

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(
            controller.publisher_engine._pre_publish,  # type: ignore[union-attr]
            "run",
            new_callable=AsyncMock,
            return_value=_ALL_GATES_PASS,
        ),
    ):
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        state = await controller.run(jd_text=_RAW_JD_TEXT)

    assert state.jd_analysis is not None, "L1: jd_analysis must be set"
    assert state.company_profile is not None, "L2: company_profile must be set"
    assert state.gap_analysis is not None, "L3: gap_analysis must be set"
    assert state.project_spec is not None, "L4: project_spec must be set"
    assert state.forge_output is not None, "L5: forge_output must be set"
    assert state.publish_result is not None, "L6: publish_result must be set"
    assert state.content_outputs, "L7: content_outputs must be non-empty"
    assert len(state.errors) == 0, f"Expected no errors, got: {state.errors}"


# ------------------------------------------------------------------
# Test 10: Content word counts are positive
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l7_content_word_counts_positive() -> None:
    """All ContentOutput word_count values must be positive integers."""
    controller = _make_controller_with_publisher()
    mock_client_instance = _patch_github_client(_mock_github_responses())

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(
            controller.publisher_engine._pre_publish,  # type: ignore[union-attr]
            "run",
            new_callable=AsyncMock,
            return_value=_ALL_GATES_PASS,
        ),
    ):
        mock_github_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_github_client.return_value.__aexit__ = AsyncMock(return_value=None)

        state = await controller.run(jd_text=_RAW_JD_TEXT)

    for output in state.content_outputs:
        assert output.word_count > 0, f"{output.format}: word_count must be positive"


# ------------------------------------------------------------------
# Test 11: forge review_verdict passes (L1-L7 regression guard)
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_l1_l7_forge_review_verdict_passes() -> None:
    """Forge review_verdict must be PASS or PASS_WITH_SUGGESTIONS in L1-L7 flow."""
    controller = _make_controller_with_publisher()
    mock_client_instance = _patch_github_client(_mock_github_responses())

    with (
        patch("letsbuild.publisher.engine.GitHubClient") as mock_github_client,
        patch.object(
            controller.publisher_engine._pre_publish,  # type: ignore[union-attr]
            "run",
            new_callable=AsyncMock,
            return_value=_ALL_GATES_PASS,
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
