"""PrePublish hook — final gate before GitHub publishing."""

from __future__ import annotations

import re

import structlog

from letsbuild.models.architect_models import ProjectSpec  # noqa: TC001
from letsbuild.models.forge_models import ForgeOutput, ReviewVerdict
from letsbuild.models.shared import GateResult

__all__ = ["PrePublishHook"]

logger = structlog.get_logger()

# Minimum README length (characters) for the README gate (non-blocking).
_README_MIN_LENGTH = 100

# Patterns that indicate hardcoded secrets in generated code.
# Each tuple is (compiled regex, description).
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "Anthropic API key (sk-ant-...)"),
    (re.compile(r"ghp_[A-Za-z0-9]{36,}"), "GitHub personal access token (ghp_)"),
    (re.compile(r"gho_[A-Za-z0-9]{36,}"), "GitHub OAuth token (gho_)"),
    (re.compile(r"ghs_[A-Za-z0-9]{36,}"), "GitHub server-to-server token (ghs_)"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key ID (AKIA...)"),
    (re.compile(r"Bearer\s+[A-Za-z0-9_\-.]{20,}"), "Hardcoded Bearer token"),
    (
        re.compile(
            r"""(?:key|token|secret|password|passwd|pwd)\s*[:=]\s*['"][A-Za-z0-9_\-]{32,}['"]""",
            re.IGNORECASE,
        ),
        "Hardcoded high-entropy credential literal",
    ),
]


class PrePublishHook:
    """Runs all pre-publication checks before the GitHub Publisher creates the repo.

    Corresponds to the ``PrePublish`` hook in the Layer 9 hooks table
    (ARCHITECTURE.md).  Returns a list of :class:`GateResult` objects so the
    caller can inspect each check individually.  The pipeline MUST NOT proceed
    if any blocking gate has ``passed=False``.

    Gates (in evaluation order):
    1. Quality Gate     — ``forge_output.quality_score >= quality_threshold`` (blocking)
    2. Review Gate      — ``forge_output.review_verdict`` is "pass" (blocking)
    3. Sandbox Gate     — all sandbox validation commands recorded as passed (blocking)
    4. Security Gate    — no hardcoded secrets found in code modules (blocking)
    5. README Gate      — readme_content present and long enough (non-blocking)

    Gates are deterministic Python code — no LLM calls are made here.
    """

    def __init__(self, quality_threshold: float = 70.0) -> None:
        self.quality_threshold = quality_threshold
        self.log = structlog.get_logger(hook="PrePublish")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        project_spec: ProjectSpec,
        forge_output: ForgeOutput,
        readme_content: str | None = None,
    ) -> list[GateResult]:
        """Evaluate all pre-publish gates and return their results.

        Args:
            project_spec: Spec produced by the Project Architect (Layer 4).
            forge_output: Output produced by the Code Forge (Layer 5).
            readme_content: Rendered README string, if available.

        Returns:
            List of :class:`GateResult` objects — one per gate.  Callers
            should block publication if any entry has ``passed=False`` and
            ``blocking=True``.
        """
        results: list[GateResult] = [
            self._check_quality(forge_output),
            self._check_review(forge_output),
            self._check_sandbox(project_spec, forge_output),
            self._check_security(forge_output),
            self._check_readme(readme_content),
        ]

        passed_count = sum(1 for r in results if r.passed)
        blocking_failures = [r for r in results if not r.passed and r.blocking]

        self.log.info(
            "pre_publish_gates_evaluated",
            total=len(results),
            passed=passed_count,
            blocking_failures=len(blocking_failures),
        )

        if blocking_failures:
            self.log.warning(
                "pre_publish_blocked",
                gates=[r.gate_name for r in blocking_failures],
            )

        return results

    # ------------------------------------------------------------------
    # Gate implementations — all deterministic, no LLM calls
    # ------------------------------------------------------------------

    def _check_quality(self, forge_output: ForgeOutput) -> GateResult:
        """Gate 1: quality score must meet the configured threshold."""
        score = forge_output.quality_score
        passed = score >= self.quality_threshold
        if passed:
            reason = f"Quality score {score:.1f} meets threshold {self.quality_threshold:.1f}."
        else:
            reason = f"Quality score {score:.1f} is below threshold {self.quality_threshold:.1f}."
        self.log.debug("quality_gate", score=score, threshold=self.quality_threshold, passed=passed)
        return GateResult(gate_name="QualityGate", passed=passed, reason=reason, blocking=True)

    def _check_review(self, forge_output: ForgeOutput) -> GateResult:
        """Gate 2: independent Reviewer must have issued a passing verdict."""
        verdict = forge_output.review_verdict
        passed = verdict in (ReviewVerdict.PASS, ReviewVerdict.PASS_WITH_SUGGESTIONS)
        if passed:
            reason = f"Review verdict is '{verdict}' — code passed independent review."
        else:
            reason = f"Review verdict is '{verdict}' — code must pass review before publishing."
        self.log.debug("review_gate", verdict=verdict, passed=passed)
        return GateResult(gate_name="ReviewGate", passed=passed, reason=reason, blocking=True)

    def _check_sandbox(self, project_spec: ProjectSpec, forge_output: ForgeOutput) -> GateResult:
        """Gate 3: all sandbox validation commands must have passed.

        The forge records test results as a mapping of test name → bool.
        Commands in the ``SandboxValidationPlan`` are matched by their command
        string; if no matching key is found the gate treats it as unverified
        and marks the gate as failed.
        """
        plan = project_spec.sandbox_validation_plan
        commands = plan.commands
        test_results = forge_output.test_results

        failed_commands: list[str] = []
        unverified_commands: list[str] = []

        for cmd in commands:
            key = cmd.command
            if key in test_results:
                if not test_results[key]:
                    failed_commands.append(key)
            else:
                # Fall back to a substring search across recorded result keys.
                matching_keys = [k for k in test_results if key in k or k in key]
                if matching_keys:
                    if not all(test_results[k] for k in matching_keys):
                        failed_commands.append(key)
                else:
                    unverified_commands.append(key)

        if failed_commands:
            reason = (
                f"{len(failed_commands)} sandbox validation command(s) failed: "
                + "; ".join(failed_commands[:3])
                + ("..." if len(failed_commands) > 3 else "")
            )
            passed = False
        elif unverified_commands:
            reason = (
                f"{len(unverified_commands)} sandbox validation command(s) have no recorded "
                "result — sandbox may not have run. Cannot verify."
            )
            passed = False
        else:
            reason = f"All {len(commands)} sandbox validation command(s) passed."
            passed = True

        self.log.debug(
            "sandbox_gate",
            total_commands=len(commands),
            failed=len(failed_commands),
            unverified=len(unverified_commands),
            passed=passed,
        )
        return GateResult(gate_name="SandboxGate", passed=passed, reason=reason, blocking=True)

    def _check_security(self, forge_output: ForgeOutput) -> GateResult:
        """Gate 4: no hardcoded secrets may appear in any code module."""
        findings: list[str] = []

        for module in forge_output.code_modules:
            module_findings = self._scan_secrets(module.content)
            for description in module_findings:
                findings.append(f"{module.module_path}: {description}")

        passed = len(findings) == 0
        if passed:
            reason = f"No secrets detected across {len(forge_output.code_modules)} code module(s)."
        else:
            reason = (
                f"{len(findings)} potential secret(s) detected — publishing blocked. "
                "Findings: " + "; ".join(findings[:3]) + ("..." if len(findings) > 3 else "")
            )

        self.log.debug(
            "security_gate",
            modules_scanned=len(forge_output.code_modules),
            findings=len(findings),
            passed=passed,
        )
        if not passed:
            self.log.warning("secrets_detected_pre_publish", count=len(findings))

        return GateResult(gate_name="SecurityGate", passed=passed, reason=reason, blocking=True)

    def _check_readme(self, readme_content: str | None) -> GateResult:
        """Gate 5: README must be present and meet minimum length (non-blocking)."""
        if readme_content is None:
            return GateResult(
                gate_name="ReadmeGate",
                passed=False,
                reason="README content was not provided — repository may publish without a README.",
                blocking=False,
            )

        length = len(readme_content)
        if length < _README_MIN_LENGTH:
            reason = (
                f"README is only {length} characters — below minimum of {_README_MIN_LENGTH}. "
                "Consider expanding the README before publishing."
            )
            passed = False
        else:
            reason = f"README is {length} characters — meets minimum length requirement."
            passed = True

        self.log.debug("readme_gate", length=length, passed=passed)
        return GateResult(gate_name="ReadmeGate", passed=passed, reason=reason, blocking=False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _scan_secrets(content: str) -> list[str]:
        """Return descriptions of detected secret patterns (never the secrets themselves)."""
        detected: list[str] = []
        for pattern, description in _SECRET_PATTERNS:
            if pattern.search(content):
                detected.append(description)
        return detected
