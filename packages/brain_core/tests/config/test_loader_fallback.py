"""Plan 11 Task 3: ``config.json`` → ``config.json.bak`` → defaults fallback chain.

Tests pin the D7 behaviour: a corrupt or missing primary config file
must NOT brick startup. The loader walks the fallback chain, emits a
``config_load_fallback`` warning at each step that fails, and ends up
either with the first successful payload or with ``Config()`` defaults.
"""

from __future__ import annotations

import json
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

from brain_core.config.loader import load_config
from brain_core.config.schema import Config
from structlog.testing import capture_logs


def _fallback_logs(
    cap_logs: list[MutableMapping[str, Any]],
) -> list[MutableMapping[str, Any]]:
    return [log for log in cap_logs if log.get("event") == "config_load_fallback"]


def test_clean_read_no_warnings(tmp_path: Path) -> None:
    main = tmp_path / "config.json"
    main.write_text(json.dumps({"web_port": 5500, "active_domain": "work"}), encoding="utf-8")

    with capture_logs() as cap_logs:
        cfg = load_config(config_file=main, env={}, cli_overrides={})

    assert cfg.web_port == 5500
    assert cfg.active_domain == "work"
    # Behaviour parity: a clean read must NOT emit any fallback warning.
    assert _fallback_logs(cap_logs) == []


def test_corrupt_main_falls_back_to_bak(tmp_path: Path) -> None:
    main = tmp_path / "config.json"
    bak = tmp_path / "config.json.bak"
    main.write_text("{not json", encoding="utf-8")
    bak.write_text(json.dumps({"web_port": 6600, "active_domain": "work"}), encoding="utf-8")

    with capture_logs() as cap_logs:
        cfg = load_config(config_file=main, env={}, cli_overrides={})

    # Values come from the bak, not from defaults.
    assert cfg.web_port == 6600
    assert cfg.active_domain == "work"

    logs = _fallback_logs(cap_logs)
    # Exactly one fallback warning (for the corrupt primary). The bak
    # read succeeded so it must NOT log.
    assert len(logs) == 1
    assert logs[0]["attempted"] == str(main)
    assert logs[0]["reason"] == "parse_error"


def test_corrupt_main_and_bak_falls_back_to_defaults(tmp_path: Path) -> None:
    main = tmp_path / "config.json"
    bak = tmp_path / "config.json.bak"
    main.write_text("{not json", encoding="utf-8")
    bak.write_text("also not json", encoding="utf-8")

    with capture_logs() as cap_logs:
        cfg = load_config(config_file=main, env={}, cli_overrides={})

    assert cfg == Config()

    logs = _fallback_logs(cap_logs)
    assert len(logs) == 2
    # Order: primary first, then bak.
    assert logs[0]["attempted"] == str(main)
    assert logs[0]["reason"] == "parse_error"
    assert logs[1]["attempted"] == str(bak)
    assert logs[1]["reason"] == "parse_error"


def test_missing_main_with_valid_bak(tmp_path: Path) -> None:
    main = tmp_path / "config.json"  # never written
    bak = tmp_path / "config.json.bak"
    bak.write_text(json.dumps({"web_port": 7700}), encoding="utf-8")

    with capture_logs() as cap_logs:
        cfg = load_config(config_file=main, env={}, cli_overrides={})

    assert cfg.web_port == 7700

    logs = _fallback_logs(cap_logs)
    assert len(logs) == 1
    assert logs[0]["attempted"] == str(main)
    assert logs[0]["reason"] == "missing"


def test_missing_main_and_missing_bak_falls_back_to_defaults(tmp_path: Path) -> None:
    main = tmp_path / "config.json"  # never written
    # bak also absent.

    with capture_logs() as cap_logs:
        cfg = load_config(config_file=main, env={}, cli_overrides={})

    assert cfg == Config()

    logs = _fallback_logs(cap_logs)
    assert len(logs) == 2
    assert logs[0]["attempted"] == str(main)
    assert logs[0]["reason"] == "missing"
    assert logs[1]["attempted"] == str(tmp_path / "config.json.bak")
    assert logs[1]["reason"] == "missing"


def test_env_layer_still_applied_after_bak_fallback(tmp_path: Path) -> None:
    # Round-trip-realistic case: the writer persisted a Config (so
    # ``vault_path`` is NOT in the bak per D4); the primary then got
    # corrupted; ``BRAIN_VAULT`` is set in the environment. The loader
    # must take the bak's persisted fields, then re-apply env on top —
    # in particular ``vault_path`` must reflect the env, not the
    # default.
    main = tmp_path / "config.json"
    bak = tmp_path / "config.json.bak"
    main.write_text("{not json", encoding="utf-8")
    persisted = Config(active_domain="work").persisted_dict()
    bak.write_text(json.dumps(persisted, default=str), encoding="utf-8")

    env_vault = tmp_path / "elsewhere"
    cfg = load_config(
        config_file=main,
        env={"BRAIN_VAULT": str(env_vault)},
        cli_overrides={},
    )

    assert cfg.active_domain == "work"  # from bak
    assert cfg.vault_path == env_vault  # env wins over bak's missing field


def test_cli_overrides_still_win_after_bak_fallback(tmp_path: Path) -> None:
    main = tmp_path / "config.json"
    bak = tmp_path / "config.json.bak"
    main.write_text("{not json", encoding="utf-8")
    bak.write_text(json.dumps({"web_port": 6000}), encoding="utf-8")

    cfg = load_config(
        config_file=main,
        env={"BRAIN_WEB_PORT": "7000"},
        cli_overrides={"web_port": 8000},
    )
    # cli > env > bak > defaults
    assert cfg.web_port == 8000


def test_bak_path_uses_name_not_stem(tmp_path: Path) -> None:
    # Pin the subtle gotcha: ``Path("config.json").stem`` is ``"config"``
    # so ``parent / f"{path.stem}.bak"`` would resolve to
    # ``config.bak`` — NOT what the writer creates. The loader must
    # use ``path.name`` so the lookup matches ``config.json.bak``.
    main = tmp_path / "config.json"
    main.write_text("garbage", encoding="utf-8")
    wrong_bak = tmp_path / "config.bak"  # what the buggy version would look for
    wrong_bak.write_text(json.dumps({"web_port": 9999}), encoding="utf-8")
    right_bak = tmp_path / "config.json.bak"
    right_bak.write_text(json.dumps({"web_port": 1234}), encoding="utf-8")

    cfg = load_config(config_file=main, env={}, cli_overrides={})

    # If the loader used ``stem``, it would have read 9999. Asserting on
    # the right_bak value confirms ``name`` is what's in use.
    assert cfg.web_port == 1234


def test_top_level_non_object_treated_as_parse_error(tmp_path: Path) -> None:
    # Edge case: the JSON parses but the top-level value is a list or a
    # number. ``Config(**data)`` would fail with a confusing TypeError.
    # We treat this the same as a parse error so the bak / defaults
    # branches still get a chance.
    main = tmp_path / "config.json"
    bak = tmp_path / "config.json.bak"
    main.write_text("[1, 2, 3]", encoding="utf-8")
    bak.write_text(json.dumps({"web_port": 4242}), encoding="utf-8")

    with capture_logs() as cap_logs:
        cfg = load_config(config_file=main, env={}, cli_overrides={})

    assert cfg.web_port == 4242

    logs = _fallback_logs(cap_logs)
    assert len(logs) == 1
    assert logs[0]["attempted"] == str(main)
    assert logs[0]["reason"] == "parse_error"


def test_config_file_none_skips_fallback_chain(tmp_path: Path) -> None:
    # Behaviour parity with v0.1: ``config_file=None`` means the caller
    # explicitly didn't provide a file path. The loader must not fabricate
    # a ``.bak`` lookup or emit any fallback warning — it just goes
    # straight to defaults + env + cli.
    with capture_logs() as cap_logs:
        cfg = load_config(config_file=None, env={}, cli_overrides={})

    assert cfg == Config()
    assert _fallback_logs(cap_logs) == []
