"""PostCodeGeneration hook — security scan and metadata tagging after code generation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog

from letsbuild.models.forge_models import CodeModule  # noqa: TC001

logger = structlog.get_logger()

# Patterns that indicate hardcoded secrets.  Each tuple is (compiled regex, description).
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "Anthropic API key (sk-ant-...)"),
    (re.compile(r"ghp_[A-Za-z0-9]{36,}"), "GitHub personal access token (ghp_)"),
    (re.compile(r"gho_[A-Za-z0-9]{36,}"), "GitHub OAuth token (gho_)"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key ID (AKIA...)"),
    (re.compile(r"Bearer\s+[A-Za-z0-9_\-.]{20,}"), "Hardcoded Bearer token"),
    (
        re.compile(r"""(?:password|passwd|pwd)\s*[:=]\s*['"][^'"]{8,}['"]""", re.IGNORECASE),
        "Hardcoded password literal",
    ),
]

_GENERATOR_VERSION = "letsbuild-3.0.0-alpha"


@dataclass
class PostCodeGenResult:
    """Result returned by the PostCodeGeneration hook."""

    secrets_found: list[str]
    has_secrets: bool
    modules_scanned: int
    metadata_tags: dict[str, str] = field(default_factory=dict)


class PostCodeGenerationHook:
    """Runs after every Coder batch to scan for secrets and tag metadata.

    Corresponds to the ``PostCodeGeneration`` hook in the Layer 9 hooks table
    (ARCHITECTURE.md).  Must complete within 5 seconds per security rules.
    """

    def __init__(self) -> None:
        self.log = structlog.get_logger(hook="PostCodeGeneration")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, code_modules: list[CodeModule]) -> PostCodeGenResult:
        """Scan *code_modules* for secrets and attach generation metadata."""
        all_secrets: list[str] = []

        for module in code_modules:
            findings = self._scan_secrets(module.content)
            if findings:
                self.log.warning(
                    "secrets_detected",
                    module_path=module.module_path,
                    count=len(findings),
                )
                all_secrets.extend(findings)

        metadata_tags = {
            "generator": _GENERATOR_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "modules_count": str(len(code_modules)),
        }

        result = PostCodeGenResult(
            secrets_found=all_secrets,
            has_secrets=len(all_secrets) > 0,
            modules_scanned=len(code_modules),
            metadata_tags=metadata_tags,
        )

        self.log.info(
            "post_code_gen_complete",
            modules_scanned=result.modules_scanned,
            has_secrets=result.has_secrets,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scan_secrets(self, content: str) -> list[str]:
        """Return descriptions of detected secret patterns (never the secrets themselves)."""
        detected: list[str] = []
        for pattern, description in _SECRET_PATTERNS:
            if pattern.search(content):
                detected.append(description)
        return detected
