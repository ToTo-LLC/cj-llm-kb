from __future__ import annotations

import json
from pathlib import Path

import pytest
from brain_core.config.loader import load_config
from brain_core.config.schema import Config
from structlog.testing import capture_logs


def test_defaults_when_no_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAIN_VAULT", raising=False)
    cfg = load_config(config_file=None, env={}, cli_overrides={})
    assert cfg.active_domain == "research"
    assert cfg.web_port == 4317


def test_env_overrides_defaults() -> None:
    cfg = load_config(config_file=None, env={"BRAIN_WEB_PORT": "5000"}, cli_overrides={})
    assert cfg.web_port == 5000


def test_config_file_beats_defaults_but_loses_to_env(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"web_port": 6000, "active_domain": "work"}), encoding="utf-8")
    cfg = load_config(
        config_file=cfg_path,
        env={"BRAIN_WEB_PORT": "7000"},
        cli_overrides={},
    )
    assert cfg.active_domain == "work"  # from file
    assert cfg.web_port == 7000  # env wins


def test_cli_overrides_beat_everything(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"web_port": 6000}), encoding="utf-8")
    cfg = load_config(
        config_file=cfg_path,
        env={"BRAIN_WEB_PORT": "7000"},
        cli_overrides={"web_port": 8000},
    )
    assert cfg.web_port == 8000


def test_invalid_config_file_falls_back_to_defaults_when_no_bak(tmp_path: Path) -> None:
    # Plan 11 D7 changed the v0.1 raise-on-bad-JSON behaviour to fall
    # back to ``config.json.bak`` and then to defaults, with a structured
    # warning emitted at each step. With no ``.bak`` present and the
    # primary file unparseable the loader returns ``Config()`` defaults.
    bad = tmp_path / "config.json"
    bad.write_text("{not json", encoding="utf-8")

    with capture_logs() as cap_logs:
        cfg = load_config(config_file=bad, env={}, cli_overrides={})

    # Identical, field-for-field, to a fresh ``Config()``.
    assert cfg == Config()

    # Two warnings: one for the corrupt primary, one for the missing bak.
    fallback_logs = [log for log in cap_logs if log.get("event") == "config_load_fallback"]
    assert any(
        log.get("attempted") == str(bad) and log.get("reason") == "parse_error"
        for log in fallback_logs
    ), f"expected parse_error warning for {bad}, got {fallback_logs!r}"
    assert any(
        log.get("attempted") == str(bad.parent / "config.json.bak")
        and log.get("reason") == "missing"
        for log in fallback_logs
    ), f"expected missing warning for .bak, got {fallback_logs!r}"
