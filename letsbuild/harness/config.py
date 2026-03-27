"""Configuration loader for LetsBuild pipeline.

Loads AppConfig from letsbuild.yaml with environment variable overrides.
Secrets (API keys, tokens) are NEVER read from YAML — only from env vars.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog
import yaml

from letsbuild.models.config_models import (
    AppConfig,
    ModelTaskMapping,
    NotificationConfig,
    SandboxConfig,
)

logger = structlog.get_logger()

_DEFAULT_CONFIG_FILENAME = "letsbuild.yaml"

# Fields that require specific type coercion from env var strings.
_FLOAT_FIELDS: frozenset[str] = frozenset(
    {
        "budget_per_run_gbp",
        "budget_limit_gbp",
        "quality_threshold",
    }
)
_INT_FIELDS: frozenset[str] = frozenset(
    {
        "max_retries_per_layer",
        "max_retries_per_task",
        "cpu_limit",
        "memory_limit_gb",
        "disk_limit_gb",
        "lifetime_minutes",
        "pool_size",
        "sandbox_timeout_minutes",
        "experience_years",
        "distill_every_n_runs",
        "company_cache_ttl_days",
        "judge_verdict_ttl_days",
    }
)
_BOOL_FIELDS: frozenset[str] = frozenset(
    {
        "enabled",
        "enable_learning",
        "enable_consolidation",
        "enable_ci_cd",
        "topics_auto_generate",
        "network_outbound",
        "network_inbound",
        "telegram_enabled",
        "slack_enabled",
        "discord_enabled",
        "websocket_enabled",
    }
)


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load application configuration from YAML file with env var overrides.

    Args:
        config_path: Path to the YAML config file. Defaults to
            ``letsbuild.yaml`` in the current working directory.

    Returns:
        A validated ``AppConfig`` instance.
    """
    if config_path is None:
        config_path = Path.cwd() / _DEFAULT_CONFIG_FILENAME

    yaml_data: dict[str, object] = {}

    if config_path.exists():
        logger.info("config.loading", path=str(config_path))
        try:
            raw = config_path.read_text(encoding="utf-8")
            parsed = yaml.safe_load(raw)
            if isinstance(parsed, dict):
                yaml_data = parsed
            else:
                logger.warning(
                    "config.malformed_yaml",
                    path=str(config_path),
                    detail="YAML root is not a mapping; using defaults.",
                )
        except yaml.YAMLError as exc:
            logger.error(
                "config.yaml_parse_error",
                path=str(config_path),
                error=str(exc),
                error_category="validation",
                is_retryable=False,
            )
    else:
        logger.warning(
            "config.file_not_found",
            path=str(config_path),
            detail="No config file found; using defaults with env overrides.",
        )

    env_overrides = get_env_overrides()
    merged = _merge_config(yaml_data, env_overrides)

    app_config = _map_to_app_config(merged)
    logger.info("config.loaded", project_name=app_config.project_name)
    return app_config


def get_env_overrides() -> dict[str, object]:
    """Scan environment for ``LETSBUILD_*`` variables and parse into a nested dict.

    Variable naming convention: ``LETSBUILD_<SECTION>_<KEY>``
    e.g. ``LETSBUILD_PIPELINE_BUDGET_PER_RUN_GBP=30.0`` becomes
    ``{"pipeline": {"budget_per_run_gbp": 30.0}}``.

    Returns:
        Nested dictionary of overrides with coerced types.
    """
    prefix = "LETSBUILD_"
    overrides: dict[str, object] = {}

    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue

        # Strip prefix and lowercase
        remainder = key[len(prefix) :].lower()
        parts = remainder.split("_", 1)

        if len(parts) < 2:
            # Single-level key like LETSBUILD_SOMETHING — store at top level
            overrides[remainder] = _coerce_value(remainder, value)
            continue

        section = parts[0]
        field_name = parts[1]
        coerced = _coerce_value(field_name, value)

        section_dict = overrides.get(section)
        if not isinstance(section_dict, dict):
            section_dict = {}
            overrides[section] = section_dict
        section_dict[field_name] = coerced

    if overrides:
        logger.debug("config.env_overrides", keys=list(overrides.keys()))

    return overrides


def _merge_config(
    yaml_data: dict[str, object],
    env_overrides: dict[str, object],
) -> dict[str, object]:
    """Deep-merge env overrides onto YAML data. Env vars take precedence.

    Args:
        yaml_data: Configuration parsed from YAML.
        env_overrides: Overrides from environment variables.

    Returns:
        Merged configuration dictionary.
    """
    result: dict[str, object] = {}

    # Copy all yaml keys
    for key, val in yaml_data.items():
        if isinstance(val, dict):
            result[key] = dict(val)
        else:
            result[key] = val

    # Overlay env overrides
    for key, val in env_overrides.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(val, dict):
            # Deep merge one level
            merged_section = dict(existing)
            merged_section.update(val)
            result[key] = merged_section
        else:
            result[key] = val

    return result


def _coerce_value(field_name: str, raw: str) -> object:
    """Coerce a string env var value to the appropriate Python type.

    Args:
        field_name: The lowercase field name used for type lookup.
        raw: The raw string value from the environment.

    Returns:
        The coerced value (float, int, bool, or str).
    """
    if field_name in _FLOAT_FIELDS:
        try:
            return float(raw)
        except ValueError:
            logger.warning("config.coerce_failed", field=field_name, value=raw, expected="float")
            return raw

    if field_name in _INT_FIELDS:
        try:
            return int(raw)
        except ValueError:
            logger.warning("config.coerce_failed", field=field_name, value=raw, expected="int")
            return raw

    if field_name in _BOOL_FIELDS:
        return raw.lower() in ("true", "1", "yes")

    return raw


def _map_to_app_config(data: dict[str, object]) -> AppConfig:
    """Map the merged config dictionary to an AppConfig Pydantic model.

    Translates the YAML structure (which has sections like ``pipeline``,
    ``sandbox``, ``models``) into the flat/nested AppConfig fields.

    Args:
        data: Merged configuration dictionary.

    Returns:
        Validated AppConfig instance.
    """
    pipeline: dict[str, Any] = _as_dict(data.get("pipeline", {}))
    sandbox_raw: dict[str, Any] = _as_dict(data.get("sandbox", {}))
    notifications_raw: dict[str, Any] = _as_dict(data.get("notifications", {}))
    models_raw: dict[str, Any] = _as_dict(data.get("models", {}))

    # Build SandboxConfig from the sandbox section
    sandbox = SandboxConfig(
        base_image=sandbox_raw.get("image", SandboxConfig.model_fields["base_image"].default),
        cpu_limit=sandbox_raw.get("cpu_limit", SandboxConfig.model_fields["cpu_limit"].default),
        memory_limit_gb=sandbox_raw.get(
            "memory_limit_gb",
            SandboxConfig.model_fields["memory_limit_gb"].default,
        ),
        disk_limit_gb=sandbox_raw.get(
            "disk_limit_gb",
            SandboxConfig.model_fields["disk_limit_gb"].default,
        ),
        lifetime_minutes=pipeline.get(
            "sandbox_timeout_minutes",
            SandboxConfig.model_fields["lifetime_minutes"].default,
        ),
        pool_size=sandbox_raw.get("pool_size", SandboxConfig.model_fields["pool_size"].default),
    )

    # Build NotificationConfig from the notifications section
    notifications = NotificationConfig(
        telegram_enabled=_nested_bool(notifications_raw, "telegram", "enabled", default=False),
        slack_enabled=_nested_bool(notifications_raw, "slack", "enabled", default=False),
        discord_enabled=_nested_bool(notifications_raw, "discord", "enabled", default=False),
    )

    # Build model task mappings from the models section
    model_mappings: list[ModelTaskMapping] = []
    anthropic_models: dict[str, Any] = _as_dict(models_raw.get("anthropic", {}))
    fallback_models: dict[str, Any] = _as_dict(models_raw.get("fallback", {}))

    model_task_map: dict[str, tuple[str, str | None]] = {
        "architect_model": ("architecture", None),
        "code_gen_model": ("code_gen", "code_gen"),
        "review_model": ("review", None),
        "extraction_model": ("skill_extract", None),
    }

    for yaml_key, (task_name, fallback_key) in model_task_map.items():
        model_id = anthropic_models.get(yaml_key)
        if model_id is not None:
            fallback_id = fallback_models.get(fallback_key) if fallback_key else None
            model_mappings.append(
                ModelTaskMapping(
                    task_name=task_name,
                    model_id=str(model_id),
                    fallback_model_id=str(fallback_id) if fallback_id else None,
                )
            )

    # Determine default model
    default_model = str(
        anthropic_models.get(
            "code_gen_model",
            AppConfig.model_fields["anthropic_model_default"].default,
        )
    )

    return AppConfig(
        project_name=str(data.get("project_name", "letsbuild")),
        anthropic_model_default=default_model,
        model_mappings=model_mappings,
        sandbox=sandbox,
        notifications=notifications,
        budget_limit_gbp=float(
            pipeline.get(
                "budget_per_run_gbp",
                AppConfig.model_fields["budget_limit_gbp"].default,
            )
        ),
        quality_threshold=float(
            pipeline.get(
                "quality_threshold",
                AppConfig.model_fields["quality_threshold"].default,
            )
        ),
        max_retries_per_layer=int(
            pipeline.get(
                "max_retries_per_layer",
                AppConfig.model_fields["max_retries_per_layer"].default,
            )
        ),
    )


def _as_dict(value: object) -> dict[str, Any]:
    """Safely cast a value to dict, returning empty dict if not a mapping."""
    if isinstance(value, dict):
        return value
    return {}


def _nested_bool(
    data: dict[str, Any],
    section: str,
    key: str,
    *,
    default: bool,
) -> bool:
    """Extract a boolean from a nested dict section.

    Handles both flat (``telegram_enabled: true``) and nested
    (``telegram: {enabled: true}``) YAML styles.
    """
    section_data = data.get(section)
    if isinstance(section_data, dict):
        val = section_data.get(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes")
    # Also check flat key (e.g. from env override)
    flat_key = f"{section}_{key}"
    flat_val = data.get(flat_key)
    if isinstance(flat_val, bool):
        return flat_val
    return default
