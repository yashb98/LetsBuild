"""Tests for compiled policy gates (Layer 0 — deterministic Python, no LLM)."""

from __future__ import annotations

from letsbuild.harness.gates import (
    budget_gate,
    evaluate_gates,
    publish_gate,
    quality_gate,
    security_gate,
)
from letsbuild.models.forge_models import CodeModule, ForgeOutput, ReviewVerdict, SwarmTopology
from letsbuild.pipeline.state import PipelineState

# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #


def _forge_output(
    verdict: ReviewVerdict = ReviewVerdict.PASS,
    quality_score: float = 85.0,
    code_contents: list[str] | None = None,
) -> ForgeOutput:
    """Build a minimal ForgeOutput for gate testing."""
    modules = []
    if code_contents:
        for i, content in enumerate(code_contents):
            modules.append(
                CodeModule(
                    module_path=f"src/module_{i}.py",
                    content=content,
                    language="python",
                    loc=content.count("\n") + 1,
                )
            )
    else:
        modules.append(
            CodeModule(
                module_path="src/main.py",
                content="print('hello')",
                language="python",
                loc=1,
            )
        )
    return ForgeOutput(
        code_modules=modules,
        test_results={"test_basic": True},
        review_verdict=verdict,
        quality_score=quality_score,
        total_tokens_used=1000,
        total_retries=0,
        topology_used=SwarmTopology.HIERARCHICAL,
    )


def _state(
    forge_output: ForgeOutput | None = None,
    budget_remaining: float = 50.0,
) -> PipelineState:
    """Build a minimal PipelineState for gate testing."""
    return PipelineState(
        forge_output=forge_output,
        budget_remaining=budget_remaining,
    )


# ================================================================== #
# publish_gate
# ================================================================== #


class TestPublishGate:
    """Tests for the PublishGate — blocks publishing unless forge is reviewed and passed."""

    def test_passes_with_pass_verdict(self) -> None:
        state = _state(forge_output=_forge_output(ReviewVerdict.PASS))
        result = publish_gate(state)
        assert result.passed is True
        assert result.gate_name == "PublishGate"

    def test_passes_with_pass_with_suggestions(self) -> None:
        state = _state(forge_output=_forge_output(ReviewVerdict.PASS_WITH_SUGGESTIONS))
        result = publish_gate(state)
        assert result.passed is True

    def test_fails_when_forge_output_is_none(self) -> None:
        state = _state(forge_output=None)
        result = publish_gate(state)
        assert result.passed is False
        assert "None" in result.reason

    def test_fails_when_review_verdict_is_fail(self) -> None:
        state = _state(forge_output=_forge_output(ReviewVerdict.FAIL))
        result = publish_gate(state)
        assert result.passed is False
        assert "fail" in result.reason.lower()

    def test_is_blocking(self) -> None:
        state = _state(forge_output=_forge_output(ReviewVerdict.PASS))
        result = publish_gate(state)
        assert result.blocking is True

    def test_fail_result_is_also_blocking(self) -> None:
        state = _state(forge_output=None)
        result = publish_gate(state)
        assert result.blocking is True


# ================================================================== #
# security_gate
# ================================================================== #


class TestSecurityGate:
    """Tests for the SecurityGate — scans for leaked secrets in code modules."""

    def test_passes_with_clean_code(self) -> None:
        state = _state(forge_output=_forge_output(code_contents=["import os\nprint('clean')"]))
        result = security_gate(state)
        assert result.passed is True
        assert result.gate_name == "SecurityGate"

    def test_fails_with_anthropic_key(self) -> None:
        state = _state(forge_output=_forge_output(code_contents=["API_KEY = 'sk-ant-abc123xyz'"]))
        result = security_gate(state)
        assert result.passed is False
        assert "sk-ant-" in result.reason

    def test_fails_with_github_pat(self) -> None:
        state = _state(forge_output=_forge_output(code_contents=["TOKEN = 'ghp_abc123def456ghi'"]))
        result = security_gate(state)
        assert result.passed is False
        assert "ghp_" in result.reason

    def test_fails_with_aws_key(self) -> None:
        state = _state(
            forge_output=_forge_output(code_contents=["AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'"])
        )
        result = security_gate(state)
        assert result.passed is False
        assert "AKIA" in result.reason

    def test_is_blocking(self) -> None:
        state = _state(forge_output=_forge_output(code_contents=["clean code"]))
        result = security_gate(state)
        assert result.blocking is True

    def test_fails_when_forge_output_is_none(self) -> None:
        state = _state(forge_output=None)
        result = security_gate(state)
        assert result.passed is False


# ================================================================== #
# quality_gate
# ================================================================== #


class TestQualityGate:
    """Tests for the QualityGate — checks quality_score against threshold."""

    def test_passes_when_score_above_threshold(self) -> None:
        state = _state(forge_output=_forge_output(quality_score=85.0))
        result = quality_gate(state)
        assert result.passed is True
        assert result.gate_name == "QualityGate"

    def test_passes_when_score_equals_threshold(self) -> None:
        state = _state(forge_output=_forge_output(quality_score=70.0))
        result = quality_gate(state)
        assert result.passed is True

    def test_fails_when_score_below_threshold(self) -> None:
        state = _state(forge_output=_forge_output(quality_score=60.0))
        result = quality_gate(state)
        assert result.passed is False
        assert "60.0" in result.reason

    def test_default_threshold_is_70(self) -> None:
        state = _state(forge_output=_forge_output(quality_score=69.9))
        result = quality_gate(state)
        assert result.passed is False
        assert "70.0" in result.reason

    def test_custom_threshold_works(self) -> None:
        state = _state(forge_output=_forge_output(quality_score=55.0))
        result = quality_gate(state, threshold=50.0)
        assert result.passed is True

    def test_is_non_blocking(self) -> None:
        state = _state(forge_output=_forge_output(quality_score=85.0))
        result = quality_gate(state)
        assert result.blocking is False

    def test_fail_is_also_non_blocking(self) -> None:
        state = _state(forge_output=_forge_output(quality_score=30.0))
        result = quality_gate(state)
        assert result.blocking is False


# ================================================================== #
# budget_gate
# ================================================================== #


class TestBudgetGate:
    """Tests for the BudgetGate — blocks pipeline when budget is exhausted."""

    def test_passes_when_budget_remaining_positive(self) -> None:
        state = _state(budget_remaining=25.0)
        result = budget_gate(state)
        assert result.passed is True
        assert result.gate_name == "BudgetGate"

    def test_fails_when_budget_remaining_zero(self) -> None:
        state = _state(budget_remaining=0.0)
        result = budget_gate(state)
        assert result.passed is False

    def test_fails_when_budget_remaining_negative(self) -> None:
        state = _state(budget_remaining=-5.0)
        result = budget_gate(state)
        assert result.passed is False
        assert "exhausted" in result.reason.lower()

    def test_is_blocking(self) -> None:
        state = _state(budget_remaining=10.0)
        result = budget_gate(state)
        assert result.blocking is True

    def test_fail_is_also_blocking(self) -> None:
        state = _state(budget_remaining=0.0)
        result = budget_gate(state)
        assert result.blocking is True


# ================================================================== #
# evaluate_gates
# ================================================================== #


class TestEvaluateGates:
    """Tests for evaluate_gates — runs a list of gates and collects results."""

    def test_returns_all_results(self) -> None:
        state = _state(
            forge_output=_forge_output(quality_score=85.0),
            budget_remaining=25.0,
        )
        results = evaluate_gates(state, [publish_gate, security_gate, quality_gate, budget_gate])
        assert len(results) == 4

    def test_all_pass_when_state_is_healthy(self) -> None:
        state = _state(
            forge_output=_forge_output(quality_score=85.0),
            budget_remaining=25.0,
        )
        results = evaluate_gates(state, [publish_gate, security_gate, quality_gate, budget_gate])
        assert all(r.passed for r in results)

    def test_mixed_results(self) -> None:
        """Budget exhausted but forge output is fine — only budget gate fails."""
        state = _state(
            forge_output=_forge_output(quality_score=85.0),
            budget_remaining=0.0,
        )
        results = evaluate_gates(state, [publish_gate, budget_gate])
        assert results[0].passed is True  # publish_gate
        assert results[1].passed is False  # budget_gate
