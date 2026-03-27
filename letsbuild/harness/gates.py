"""Compiled policy gates for the LetsBuild pipeline.

Four deterministic gates that enforce quality, security, budget, and publish
readiness at pipeline layer boundaries. These are pure Python -- no LLM calls.
"""

from __future__ import annotations

import re
from collections.abc import Callable  # noqa: TC003

import structlog

from letsbuild.models.forge_models import ReviewVerdict
from letsbuild.models.shared import GateResult
from letsbuild.pipeline.state import PipelineState  # noqa: TC001

logger = structlog.get_logger()

# Regex patterns for known secret prefixes in generated code.
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-ant-[A-Za-z0-9]"),
    re.compile(r"ghp_[A-Za-z0-9]"),
    re.compile(r"gho_[A-Za-z0-9]"),
    re.compile(r"AKIA[A-Z0-9]"),
]


def publish_gate(state: PipelineState) -> GateResult:
    """Check that the forge output is present, reviewed, and validated.

    Blocks publishing if:
    - forge_output is missing
    - review_verdict is not PASS or PASS_WITH_SUGGESTIONS
    - quality_score is negative (should never happen with valid ForgeOutput)
    """
    if state.forge_output is None:
        return GateResult(
            passed=False,
            reason="forge_output is None -- Code Forge has not run.",
            blocking=True,
            gate_name="PublishGate",
        )

    verdict = state.forge_output.review_verdict
    passing_verdicts = {ReviewVerdict.PASS, ReviewVerdict.PASS_WITH_SUGGESTIONS}
    if verdict not in passing_verdicts:
        return GateResult(
            passed=False,
            reason=(
                f"review_verdict is '{verdict.value}' -- expected PASS or PASS_WITH_SUGGESTIONS."
            ),
            blocking=True,
            gate_name="PublishGate",
        )

    if state.forge_output.quality_score < 0:
        return GateResult(
            passed=False,
            reason=(f"quality_score is {state.forge_output.quality_score} -- must be >= 0."),
            blocking=True,
            gate_name="PublishGate",
        )

    return GateResult(
        passed=True,
        reason="Forge output present, review passed, quality score valid.",
        blocking=True,
        gate_name="PublishGate",
    )


def security_gate(state: PipelineState) -> GateResult:
    """Scan code modules for known secret patterns.

    Checks every code module's content for prefixes that indicate leaked
    API keys or tokens: sk-ant-, ghp_, gho_, AKIA.
    """
    if state.forge_output is None:
        return GateResult(
            passed=False,
            reason="forge_output is None -- nothing to scan.",
            blocking=True,
            gate_name="SecurityGate",
        )

    findings: list[str] = []
    for module in state.forge_output.code_modules:
        for pattern in _SECRET_PATTERNS:
            if pattern.search(module.content):
                findings.append(f"Secret pattern '{pattern.pattern}' found in {module.module_path}")

    if findings:
        return GateResult(
            passed=False,
            reason=f"Security scan found {len(findings)} issue(s): {'; '.join(findings)}",
            blocking=True,
            gate_name="SecurityGate",
        )

    return GateResult(
        passed=True,
        reason="No secret patterns detected in code modules.",
        blocking=True,
        gate_name="SecurityGate",
    )


def quality_gate(state: PipelineState, threshold: float = 70.0) -> GateResult:
    """Check that the forge output quality score meets the threshold.

    Non-blocking by default -- logs a warning but does not halt the pipeline.
    The threshold can be overridden per-skill config.
    """
    if state.forge_output is None:
        return GateResult(
            passed=False,
            reason="forge_output is None -- cannot evaluate quality.",
            blocking=False,
            gate_name="QualityGate",
        )

    score = state.forge_output.quality_score
    if score < threshold:
        return GateResult(
            passed=False,
            reason=(f"quality_score {score:.1f} is below threshold {threshold:.1f}."),
            blocking=False,
            gate_name="QualityGate",
        )

    return GateResult(
        passed=True,
        reason=f"quality_score {score:.1f} meets threshold {threshold:.1f}.",
        blocking=False,
        gate_name="QualityGate",
    )


def budget_gate(state: PipelineState) -> GateResult:
    """Check that the pipeline run has not exceeded its API budget.

    Blocks the pipeline if budget_remaining is zero or negative.
    """
    if state.budget_remaining > 0:
        return GateResult(
            passed=True,
            reason=f"Budget remaining: {state.budget_remaining:.2f} GBP.",
            blocking=True,
            gate_name="BudgetGate",
        )

    return GateResult(
        passed=False,
        reason=(
            f"Budget exhausted: {state.budget_remaining:.2f} GBP remaining. "
            f"Pipeline cannot continue."
        ),
        blocking=True,
        gate_name="BudgetGate",
    )


def evaluate_gates(
    state: PipelineState,
    gates: list[Callable[[PipelineState], GateResult]],
) -> list[GateResult]:
    """Run a list of gate functions against the current pipeline state.

    Logs each gate result and returns the full list of GateResults.
    """
    results: list[GateResult] = []
    for gate_fn in gates:
        result = gate_fn(state)
        log = logger.bind(
            gate=result.gate_name,
            passed=result.passed,
            blocking=result.blocking,
        )
        if result.passed:
            log.info("gate_passed", reason=result.reason)
        else:
            log.warning("gate_failed", reason=result.reason)
        results.append(result)
    return results
