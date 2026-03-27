"""Tests for letsbuild.harness.config — YAML loading, env overrides, type coercion."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import pytest  # noqa: TC002
import yaml

from letsbuild.harness.config import get_env_overrides, load_config
from letsbuild.models.config_models import AppConfig

# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_load_from_valid_yaml(self, tmp_path: Path) -> None:
        """Load a minimal valid YAML config and verify key fields are populated."""
        config_file = tmp_path / "letsbuild.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "project_name": "test-project",
                    "pipeline": {
                        "budget_per_run_gbp": 25.0,
                        "quality_threshold": 80.0,
                        "max_retries_per_layer": 3,
                    },
                    "sandbox": {
                        "image": "custom/sandbox:v1",
                        "cpu_limit": 2,
                        "memory_limit_gb": 4,
                    },
                }
            ),
            encoding="utf-8",
        )

        config = load_config(config_file)

        assert isinstance(config, AppConfig)
        assert config.project_name == "test-project"
        assert config.budget_limit_gbp == 25.0
        assert config.quality_threshold == 80.0
        assert config.max_retries_per_layer == 3
        assert config.sandbox.base_image == "custom/sandbox:v1"
        assert config.sandbox.cpu_limit == 2
        assert config.sandbox.memory_limit_gb == 4

    def test_missing_file_returns_default_config(self, tmp_path: Path) -> None:
        """When the config file does not exist, return a default AppConfig."""
        missing = tmp_path / "nonexistent.yaml"
        config = load_config(missing)

        assert isinstance(config, AppConfig)
        assert config.project_name == "letsbuild"
        assert config.budget_limit_gbp == 50.0
        assert config.quality_threshold == 70.0
        assert config.max_retries_per_layer == 2

    def test_env_var_overrides(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variables with LETSBUILD_ prefix override YAML values."""
        config_file = tmp_path / "letsbuild.yaml"
        config_file.write_text(
            yaml.dump({"pipeline": {"budget_per_run_gbp": 10.0}}),
            encoding="utf-8",
        )

        monkeypatch.setenv("LETSBUILD_PIPELINE_BUDGET_PER_RUN_GBP", "99.9")

        config = load_config(config_file)

        assert config.budget_limit_gbp == 99.9

    def test_type_coercion_float(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Float fields are coerced from string env vars."""
        monkeypatch.setenv("LETSBUILD_PIPELINE_QUALITY_THRESHOLD", "85.5")
        config_file = tmp_path / "letsbuild.yaml"
        config_file.write_text(yaml.dump({}), encoding="utf-8")

        config = load_config(config_file)

        assert config.quality_threshold == 85.5

    def test_type_coercion_int(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Int fields are coerced from string env vars."""
        monkeypatch.setenv("LETSBUILD_PIPELINE_MAX_RETRIES_PER_LAYER", "5")
        config_file = tmp_path / "letsbuild.yaml"
        config_file.write_text(yaml.dump({}), encoding="utf-8")

        config = load_config(config_file)

        assert config.max_retries_per_layer == 5

    def test_type_coercion_bool(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Bool fields are coerced from string env vars."""
        monkeypatch.setenv("LETSBUILD_NOTIFICATIONS_SLACK_ENABLED", "true")
        config_file = tmp_path / "letsbuild.yaml"
        config_file.write_text(yaml.dump({}), encoding="utf-8")

        config = load_config(config_file)

        assert config.notifications.slack_enabled is True

    def test_malformed_yaml_returns_defaults(self, tmp_path: Path) -> None:
        """Malformed YAML is handled gracefully and defaults are used."""
        config_file = tmp_path / "letsbuild.yaml"
        config_file.write_text(":: invalid yaml {{[", encoding="utf-8")

        config = load_config(config_file)

        assert isinstance(config, AppConfig)
        assert config.project_name == "letsbuild"

    def test_yaml_root_not_mapping_returns_defaults(self, tmp_path: Path) -> None:
        """YAML that parses to a non-dict (e.g. a list) uses defaults."""
        config_file = tmp_path / "letsbuild.yaml"
        config_file.write_text("- item1\n- item2\n", encoding="utf-8")

        config = load_config(config_file)

        assert isinstance(config, AppConfig)
        assert config.project_name == "letsbuild"


# ---------------------------------------------------------------------------
# get_env_overrides
# ---------------------------------------------------------------------------


class TestGetEnvOverrides:
    """Tests for the get_env_overrides function."""

    def test_no_letsbuild_vars_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When no LETSBUILD_ env vars exist, return an empty dict."""
        # Clear any existing LETSBUILD_ vars
        for _key in list(monkeypatch._env_setattr if hasattr(monkeypatch, "_env_setattr") else []):
            pass
        # Use a clean environment approach: delete all LETSBUILD_ vars
        import os

        for key in list(os.environ.keys()):
            if key.startswith("LETSBUILD_"):
                monkeypatch.delenv(key, raising=False)

        result = get_env_overrides()

        assert result == {}

    def test_single_var_parsed_correctly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A single LETSBUILD_SECTION_KEY env var is parsed into nested dict."""
        import os

        for key in list(os.environ.keys()):
            if key.startswith("LETSBUILD_"):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("LETSBUILD_PIPELINE_BUDGET_PER_RUN_GBP", "42.0")

        result = get_env_overrides()

        assert "pipeline" in result
        pipeline_section = result["pipeline"]
        assert isinstance(pipeline_section, dict)
        assert pipeline_section["budget_per_run_gbp"] == 42.0

    def test_multiple_vars_grouped_by_section(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Multiple LETSBUILD_ vars are grouped into the correct sections."""
        import os

        for key in list(os.environ.keys()):
            if key.startswith("LETSBUILD_"):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("LETSBUILD_PIPELINE_BUDGET_PER_RUN_GBP", "30.0")
        monkeypatch.setenv("LETSBUILD_PIPELINE_MAX_RETRIES_PER_LAYER", "4")
        monkeypatch.setenv("LETSBUILD_SANDBOX_CPU_LIMIT", "2")

        result = get_env_overrides()

        assert "pipeline" in result
        assert "sandbox" in result

        pipeline_section = result["pipeline"]
        assert isinstance(pipeline_section, dict)
        assert pipeline_section["budget_per_run_gbp"] == 30.0
        assert pipeline_section["max_retries_per_layer"] == 4

        sandbox_section = result["sandbox"]
        assert isinstance(sandbox_section, dict)
        assert sandbox_section["cpu_limit"] == 2
