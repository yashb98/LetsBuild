"""Tests for the PostCodeGeneration hook."""

from __future__ import annotations

import pytest

from letsbuild.hooks.post_code_gen import PostCodeGenerationHook
from letsbuild.models.forge_models import CodeModule


def _make_module(content: str, path: str = "src/main.py") -> CodeModule:
    return CodeModule(
        module_path=path,
        content=content,
        language="python",
        loc=content.count("\n") + 1,
    )


@pytest.fixture
def hook() -> PostCodeGenerationHook:
    return PostCodeGenerationHook()


# ------------------------------------------------------------------
# Secret scanning
# ------------------------------------------------------------------


def test_scan_clean_code_no_secrets(hook: PostCodeGenerationHook) -> None:
    """Clean code should produce zero secret findings."""
    findings = hook._scan_secrets("def hello():\n    return 'world'")
    assert findings == []


def test_scan_detects_anthropic_key(hook: PostCodeGenerationHook) -> None:
    """An Anthropic API key pattern must be detected."""
    code = 'API_KEY = "sk-ant-abc123XYZ-longstringhere"'
    findings = hook._scan_secrets(code)
    assert len(findings) == 1
    assert "Anthropic" in findings[0]


def test_scan_detects_github_token(hook: PostCodeGenerationHook) -> None:
    """A GitHub personal access token pattern must be detected."""
    code = 'GITHUB_TOKEN = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789"'
    findings = hook._scan_secrets(code)
    assert len(findings) == 1
    assert "GitHub" in findings[0]


def test_scan_detects_aws_key(hook: PostCodeGenerationHook) -> None:
    """An AWS access key ID pattern must be detected."""
    code = 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"'
    findings = hook._scan_secrets(code)
    assert len(findings) == 1
    assert "AWS" in findings[0]


# ------------------------------------------------------------------
# Full run
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_returns_result_with_metadata(hook: PostCodeGenerationHook) -> None:
    """run() should return a PostCodeGenResult with metadata tags."""
    modules = [
        _make_module("print('hello')", "src/a.py"),
        _make_module("x = 1", "src/b.py"),
    ]
    result = await hook.run(modules)

    assert result.modules_scanned == 2
    assert result.has_secrets is False
    assert result.secrets_found == []
    assert "generator" in result.metadata_tags
    assert "generated_at" in result.metadata_tags
