"""Layered config resolution: defaults → config.json → env → CLI overrides."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from brain_core.config.schema import Config

ENV_MAP: dict[str, str] = {
    "BRAIN_VAULT": "vault_path",
    "BRAIN_ACTIVE_DOMAIN": "active_domain",
    "BRAIN_AUTONOMOUS": "autonomous_mode",
    "BRAIN_WEB_PORT": "web_port",
    "BRAIN_LOG_LLM_PAYLOADS": "log_llm_payloads",
}


def load_config(
    *,
    config_file: Path | None,
    env: Mapping[str, str],
    cli_overrides: Mapping[str, Any],
) -> Config:
    """Build a Config by merging layers; later layers override earlier ones."""
    data: dict[str, Any] = {}

    if config_file is not None:
        try:
            data.update(json.loads(config_file.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise ValueError(f"config file {config_file} is not valid JSON: {exc}") from exc

    for env_key, field in ENV_MAP.items():
        if env_key in env:
            data[field] = _coerce(field, env[env_key])

    data.update(cli_overrides)
    return Config(**data)


def _coerce(field: str, raw: str) -> Any:
    if field in {"web_port"}:
        return int(raw)
    if field in {"autonomous_mode", "log_llm_payloads"}:
        return raw.lower() in {"1", "true", "yes", "on"}
    if field == "vault_path":
        return Path(raw).expanduser()
    return raw
