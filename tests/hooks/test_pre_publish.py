"""Tests for PrePublishHook — deterministic pre-publication gate checks."""

from __future__ import annotations

import pytest

from letsbuild.hooks.pre_publish import _README_MIN_LENGTH, PrePublishHook
from letsbuild.models.architect_models import (
    FeatureSpec,
    FileTreeNode,
    ProjectSpec,
    SandboxValidationCommand,
    SandboxValidationPlan,
)
from letsbuild.models.forge_models import CodeModule, ForgeOutput, ReviewVerdict, SwarmTopology

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_code_module(content: str, path: str = "src/main.py") -> CodeModule:
    return CodeModule(
        module_path=path,
        content=content,
        language="python",
        loc=content.count("\n") + 1,
    )


def _make_minimal_project_spec(
    commands: list[SandboxValidationCommand] | None = None,
) -> ProjectSpec:
    """Minimal ProjectSpec for hook tests."""
    if commands is None:
        commands = [
            SandboxValidationCommand(command="pip install -e .", description="Install"),
            SandboxValidationCommand(command="pytest tests/ -v", description="Test"),
            SandboxValidationCommand(command="ruff check .", description="Lint"),
        ]
    return ProjectSpec(
        project_name="Test Project",
        one_liner="A test project.",
        tech_stack=["python"],
        file_tree=[FileTreeNode(path="src", is_directory=True)],
        feature_specs=[
            FeatureSpec(
                feature_name="Core",
                description="Core module.",
                module_path="src/core.py",
                estimated_complexity=3,
            )
        ],
        sandbox_validation_plan=SandboxValidationPlan(commands=commands),
        adr_list=[],
        skill_name="fullstack",
        complexity_score=3.0,
        estimated_loc=100,
        seniority_target="junior",
    )


def _make_forge_output(
    quality_score: float = 85.0,
    review_verdict: ReviewVerdict = ReviewVerdict.PASS,
    test_results: dict[str, bool] | None = None,
    code_modules: list[CodeModule] | None = None,
) -> ForgeOutput:
    if test_results is None:
        test_results = {
            "pip install -e .": True,
            "pytest tests/ -v": True,
            "ruff check .": True,
        }
    if code_modules is None:
        code_modules = [_make_code_module("def hello():\n    pass\n")]
    return ForgeOutput(
        code_modules=code_modules,
        test_results=test_results,
        review_verdict=review_verdict,
        quality_score=quality_score,
        total_tokens_used=5000,
        total_retries=0,
        topology_used=SwarmTopology.HIERARCHICAL,
    )


# ---------------------------------------------------------------------------
# Quality Gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quality_gate_passes_when_score_meets_threshold() -> None:
    """QualityGate must pass when quality_score >= quality_threshold."""
    hook = PrePublishHook(quality_threshold=70.0)
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output(quality_score=70.0)

    results = await hook.run(project_spec, forge_output)
    quality_result = next(r for r in results if r.gate_name == "QualityGate")

    assert quality_result.passed is True
    assert quality_result.blocking is True


@pytest.mark.asyncio
async def test_quality_gate_passes_when_score_above_threshold() -> None:
    """QualityGate must pass when quality_score > quality_threshold."""
    hook = PrePublishHook(quality_threshold=70.0)
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output(quality_score=95.0)

    results = await hook.run(project_spec, forge_output)
    quality_result = next(r for r in results if r.gate_name == "QualityGate")

    assert quality_result.passed is True


@pytest.mark.asyncio
async def test_quality_gate_fails_when_score_below_threshold() -> None:
    """QualityGate must fail when quality_score < quality_threshold."""
    hook = PrePublishHook(quality_threshold=70.0)
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output(quality_score=69.9)

    results = await hook.run(project_spec, forge_output)
    quality_result = next(r for r in results if r.gate_name == "QualityGate")

    assert quality_result.passed is False
    assert quality_result.blocking is True


@pytest.mark.asyncio
async def test_quality_gate_uses_configured_threshold() -> None:
    """PrePublishHook should use the quality_threshold passed at construction."""
    hook_strict = PrePublishHook(quality_threshold=90.0)
    hook_lenient = PrePublishHook(quality_threshold=50.0)
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output(quality_score=75.0)

    results_strict = await hook_strict.run(project_spec, forge_output)
    results_lenient = await hook_lenient.run(project_spec, forge_output)

    strict_qg = next(r for r in results_strict if r.gate_name == "QualityGate")
    lenient_qg = next(r for r in results_lenient if r.gate_name == "QualityGate")

    assert strict_qg.passed is False
    assert lenient_qg.passed is True


@pytest.mark.asyncio
async def test_quality_gate_reason_includes_score_and_threshold() -> None:
    """QualityGate reason string should mention both the score and threshold."""
    hook = PrePublishHook(quality_threshold=70.0)
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output(quality_score=60.0)

    results = await hook.run(project_spec, forge_output)
    quality_result = next(r for r in results if r.gate_name == "QualityGate")

    assert "60" in quality_result.reason
    assert "70" in quality_result.reason


# ---------------------------------------------------------------------------
# Review Gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_gate_passes_on_pass_verdict() -> None:
    """ReviewGate must pass when review_verdict is PASS."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output(review_verdict=ReviewVerdict.PASS)

    results = await hook.run(project_spec, forge_output)
    review_result = next(r for r in results if r.gate_name == "ReviewGate")

    assert review_result.passed is True
    assert review_result.blocking is True


@pytest.mark.asyncio
async def test_review_gate_passes_on_pass_with_suggestions_verdict() -> None:
    """ReviewGate must pass when review_verdict is PASS_WITH_SUGGESTIONS."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output(review_verdict=ReviewVerdict.PASS_WITH_SUGGESTIONS)

    results = await hook.run(project_spec, forge_output)
    review_result = next(r for r in results if r.gate_name == "ReviewGate")

    assert review_result.passed is True


@pytest.mark.asyncio
async def test_review_gate_fails_on_fail_verdict() -> None:
    """ReviewGate must fail when review_verdict is FAIL."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output(review_verdict=ReviewVerdict.FAIL)

    results = await hook.run(project_spec, forge_output)
    review_result = next(r for r in results if r.gate_name == "ReviewGate")

    assert review_result.passed is False
    assert review_result.blocking is True


@pytest.mark.asyncio
async def test_review_gate_reason_mentions_verdict() -> None:
    """ReviewGate reason should mention the actual verdict value."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output(review_verdict=ReviewVerdict.FAIL)

    results = await hook.run(project_spec, forge_output)
    review_result = next(r for r in results if r.gate_name == "ReviewGate")

    assert "fail" in review_result.reason.lower()


# ---------------------------------------------------------------------------
# Sandbox Gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sandbox_gate_passes_when_all_commands_pass() -> None:
    """SandboxGate must pass when all validation commands are in test_results as True."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output(
        test_results={
            "pip install -e .": True,
            "pytest tests/ -v": True,
            "ruff check .": True,
        }
    )

    results = await hook.run(project_spec, forge_output)
    sandbox_result = next(r for r in results if r.gate_name == "SandboxGate")

    assert sandbox_result.passed is True
    assert sandbox_result.blocking is True


@pytest.mark.asyncio
async def test_sandbox_gate_fails_when_command_explicitly_failed() -> None:
    """SandboxGate must fail when a validation command has a False test result."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output(
        test_results={
            "pip install -e .": True,
            "pytest tests/ -v": False,  # explicit failure
            "ruff check .": True,
        }
    )

    results = await hook.run(project_spec, forge_output)
    sandbox_result = next(r for r in results if r.gate_name == "SandboxGate")

    assert sandbox_result.passed is False
    assert sandbox_result.blocking is True


@pytest.mark.asyncio
async def test_sandbox_gate_fails_when_command_not_in_results() -> None:
    """SandboxGate must fail when a validation command has no recorded result."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output(
        test_results={
            # "pip install -e ." and "ruff check ." missing → unverified
            "pytest tests/ -v": True,
        }
    )

    results = await hook.run(project_spec, forge_output)
    sandbox_result = next(r for r in results if r.gate_name == "SandboxGate")

    assert sandbox_result.passed is False


# ---------------------------------------------------------------------------
# Security Gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_security_gate_passes_with_clean_code() -> None:
    """SecurityGate must pass when no secret patterns are present in code."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output(
        code_modules=[_make_code_module("def clean():\n    return 42\n")]
    )

    results = await hook.run(project_spec, forge_output)
    security_result = next(r for r in results if r.gate_name == "SecurityGate")

    assert security_result.passed is True
    assert security_result.blocking is True


@pytest.mark.asyncio
async def test_security_gate_fails_on_anthropic_api_key() -> None:
    """SecurityGate must fail when an Anthropic API key pattern is detected."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    # Embed a fake Anthropic key
    code_with_secret = 'API_KEY = "sk-ant-api03-AAABBBCCC111222333DDD"\n'
    forge_output = _make_forge_output(code_modules=[_make_code_module(code_with_secret)])

    results = await hook.run(project_spec, forge_output)
    security_result = next(r for r in results if r.gate_name == "SecurityGate")

    assert security_result.passed is False
    assert security_result.blocking is True
    assert "Anthropic" in security_result.reason


@pytest.mark.asyncio
async def test_security_gate_fails_on_github_token() -> None:
    """SecurityGate must fail when a GitHub PAT pattern is detected."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    code_with_token = 'TOKEN = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789"\n'
    forge_output = _make_forge_output(code_modules=[_make_code_module(code_with_token)])

    results = await hook.run(project_spec, forge_output)
    security_result = next(r for r in results if r.gate_name == "SecurityGate")

    assert security_result.passed is False
    assert "GitHub" in security_result.reason


@pytest.mark.asyncio
async def test_security_gate_fails_on_aws_access_key() -> None:
    """SecurityGate must fail when an AWS access key ID is detected."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    code_with_aws = 'AWS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"\n'
    forge_output = _make_forge_output(code_modules=[_make_code_module(code_with_aws)])

    results = await hook.run(project_spec, forge_output)
    security_result = next(r for r in results if r.gate_name == "SecurityGate")

    assert security_result.passed is False
    assert "AWS" in security_result.reason


@pytest.mark.asyncio
async def test_security_gate_fails_on_bearer_token() -> None:
    """SecurityGate must fail when a hardcoded Bearer token is detected."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    code_with_bearer = (
        'headers = {"Authorization": "Bearer abcdefghijklmnopqrstuvwxyz1234567890"}\n'
    )
    forge_output = _make_forge_output(code_modules=[_make_code_module(code_with_bearer)])

    results = await hook.run(project_spec, forge_output)
    security_result = next(r for r in results if r.gate_name == "SecurityGate")

    assert security_result.passed is False


@pytest.mark.asyncio
async def test_security_gate_scans_all_modules() -> None:
    """SecurityGate must scan every code module — not just the first."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    modules = [
        _make_code_module("def clean():\n    pass\n", "src/clean.py"),
        # Secret is in the second module
        _make_code_module('TOKEN = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789"\n', "src/secret.py"),
    ]
    forge_output = _make_forge_output(code_modules=modules)

    results = await hook.run(project_spec, forge_output)
    security_result = next(r for r in results if r.gate_name == "SecurityGate")

    assert security_result.passed is False
    assert "src/secret.py" in security_result.reason


@pytest.mark.asyncio
async def test_security_gate_passes_with_no_code_modules() -> None:
    """SecurityGate must pass (trivially) when there are no code modules."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output(code_modules=[])

    results = await hook.run(project_spec, forge_output)
    security_result = next(r for r in results if r.gate_name == "SecurityGate")

    assert security_result.passed is True


# ---------------------------------------------------------------------------
# README Gate (non-blocking)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_readme_gate_passes_with_sufficient_content() -> None:
    """ReadmeGate must pass when readme_content is long enough."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output()
    long_readme = "# My Project\n" + "x" * (_README_MIN_LENGTH + 50)

    results = await hook.run(project_spec, forge_output, readme_content=long_readme)
    readme_result = next(r for r in results if r.gate_name == "ReadmeGate")

    assert readme_result.passed is True
    assert readme_result.blocking is False


@pytest.mark.asyncio
async def test_readme_gate_fails_when_content_too_short() -> None:
    """ReadmeGate must fail when readme_content is below the minimum length."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output()
    short_readme = "# hi"  # well below 100 chars

    results = await hook.run(project_spec, forge_output, readme_content=short_readme)
    readme_result = next(r for r in results if r.gate_name == "ReadmeGate")

    assert readme_result.passed is False
    assert readme_result.blocking is False  # non-blocking!


@pytest.mark.asyncio
async def test_readme_gate_fails_when_content_is_none() -> None:
    """ReadmeGate must fail (non-blocking) when readme_content is None."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output()

    results = await hook.run(project_spec, forge_output, readme_content=None)
    readme_result = next(r for r in results if r.gate_name == "ReadmeGate")

    assert readme_result.passed is False
    assert readme_result.blocking is False


@pytest.mark.asyncio
async def test_readme_gate_non_blocking_does_not_stop_other_gates() -> None:
    """A failed (non-blocking) ReadmeGate should not affect other gate results."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output()

    results = await hook.run(project_spec, forge_output, readme_content=None)

    # All 5 gates should still be evaluated
    assert len(results) == 5
    gate_names = {r.gate_name for r in results}
    assert "QualityGate" in gate_names
    assert "ReviewGate" in gate_names
    assert "SandboxGate" in gate_names
    assert "SecurityGate" in gate_names
    assert "ReadmeGate" in gate_names


# ---------------------------------------------------------------------------
# Full run — gate ordering and count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_returns_five_gate_results() -> None:
    """run() must return exactly 5 GateResult objects."""
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output()

    results = await hook.run(project_spec, forge_output)

    assert len(results) == 5


@pytest.mark.asyncio
async def test_run_all_pass_with_valid_inputs() -> None:
    """With valid inputs (quality ≥ 70, PASS verdict, correct test_results, no secrets),
    all blocking gates should pass."""
    hook = PrePublishHook(quality_threshold=70.0)
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output(
        quality_score=80.0,
        review_verdict=ReviewVerdict.PASS,
        test_results={
            "pip install -e .": True,
            "pytest tests/ -v": True,
            "ruff check .": True,
        },
        code_modules=[_make_code_module("def hello():\n    return 42\n")],
    )
    long_readme = "# Test Project\n\n" + "description " * 20

    results = await hook.run(project_spec, forge_output, readme_content=long_readme)

    blocking_results = [r for r in results if r.blocking]
    for gate in blocking_results:
        assert gate.passed is True, f"Blocking gate {gate.gate_name} unexpectedly failed"


@pytest.mark.asyncio
async def test_run_gate_names_match_expected_set() -> None:
    """The set of gate names returned by run() must match the documented gates."""
    expected_names = {"QualityGate", "ReviewGate", "SandboxGate", "SecurityGate", "ReadmeGate"}
    hook = PrePublishHook()
    project_spec = _make_minimal_project_spec()
    forge_output = _make_forge_output()

    results = await hook.run(project_spec, forge_output)
    actual_names = {r.gate_name for r in results}

    assert actual_names == expected_names


# ---------------------------------------------------------------------------
# _scan_secrets unit tests
# ---------------------------------------------------------------------------


def test_scan_secrets_returns_empty_for_clean_code() -> None:
    """_scan_secrets should return [] for code with no secret patterns."""
    hook = PrePublishHook()
    findings = hook._scan_secrets("def greet(name: str) -> str:\n    return f'Hello {name}'\n")
    assert findings == []


def test_scan_secrets_detects_anthropic_key() -> None:
    """_scan_secrets must detect the sk-ant- pattern."""
    hook = PrePublishHook()
    code = 'key = "sk-ant-api03-longkeyvaluehere123XYZ"'
    findings = hook._scan_secrets(code)
    assert len(findings) >= 1
    assert any("Anthropic" in f for f in findings)


def test_scan_secrets_never_returns_the_secret_value_itself() -> None:
    """_scan_secrets must return descriptions only — never the raw secret value."""
    hook = PrePublishHook()
    secret = "sk-ant-api03-verysecretvaluelongstring"
    code = f'API_KEY = "{secret}"'
    findings = hook._scan_secrets(code)

    for finding in findings:
        assert secret not in finding, "Raw secret value must not appear in scan findings"
