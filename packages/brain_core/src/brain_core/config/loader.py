"""Layered config resolution: defaults → config.json → env → CLI overrides.

Plan 11 D7: the file-read step is a fallback chain rather than a hard
failure. When the primary ``config.json`` is missing or unparseable the
loader falls back to ``config.json.bak`` (the writer's atomic-rename
backup, see :mod:`brain_core.config.writer`); when both are missing /
unparseable the loader falls back to ``Config()`` defaults. Every
fallback step emits a structured ``config_load_fallback`` warning so a
later ``brain doctor`` run can surface the corruption without bricking
startup.

Environment and CLI overlays are applied on top of whichever layer
succeeded — the fallback only governs the file-read base layer.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import structlog

from brain_core.config.schema import Config

logger = structlog.get_logger(__name__)

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
    """Build a Config by merging layers; later layers override earlier ones.

    File-read fallback chain (Plan 11 D7):
      1. ``config_file`` — the caller-supplied primary path.
      2. ``<parent>/<name>.bak`` — the writer's rotation backup.
      3. ``Config()`` defaults.

    Each step that fails (missing file or parse error) logs a
    ``config_load_fallback`` warning and proceeds to the next step.
    """
    data: dict[str, Any] = {}

    if config_file is not None:
        loaded = _try_read_config_file(config_file)
        if loaded is None:
            # Plan 11 D7: ``.bak`` lookup uses ``path.name + ".bak"`` so the
            # extension is preserved. ``path.stem`` would drop ``.json`` and
            # produce ``config.bak`` — that is NOT what the writer creates.
            backup = config_file.parent / f"{config_file.name}.bak"
            loaded = _try_read_config_file(backup)
        if loaded is not None:
            data.update(loaded)

    for env_key, field in ENV_MAP.items():
        if env_key in env:
            data[field] = _coerce(field, env[env_key])

    data.update(cli_overrides)
    return Config(**data)


def _try_read_config_file(path: Path) -> dict[str, Any] | None:
    """Read and parse a config JSON file, or return ``None`` and warn.

    Returns the parsed JSON object on success. Returns ``None`` and emits
    a ``config_load_fallback`` warning on either of:
      * file does not exist / cannot be opened (``reason="missing"``)
      * file exists but is not valid JSON (``reason="parse_error"``)
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning(
            "config_load_fallback",
            attempted=str(path),
            reason="missing",
        )
        return None
    except OSError as exc:
        # Permission errors / unreadable file — treat the same as missing
        # for fallback purposes; the ``error`` key disambiguates in logs.
        logger.warning(
            "config_load_fallback",
            attempted=str(path),
            reason="missing",
            error=str(exc),
        )
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning(
            "config_load_fallback",
            attempted=str(path),
            reason="parse_error",
            error=str(exc),
        )
        return None

    if not isinstance(parsed, dict):
        # JSON parsed cleanly but the top-level wasn't an object — treat
        # as a parse error from the loader's perspective. ``Config(**data)``
        # would otherwise fail with a less actionable message.
        logger.warning(
            "config_load_fallback",
            attempted=str(path),
            reason="parse_error",
            error=f"top-level JSON value is {type(parsed).__name__}, expected object",
        )
        return None

    return parsed


def _coerce(field: str, raw: str) -> Any:
    if field in {"web_port"}:
        return int(raw)
    if field in {"autonomous_mode", "log_llm_payloads"}:
        return raw.lower() in {"1", "true", "yes", "on"}
    if field == "vault_path":
        return Path(raw).expanduser()
    return raw
