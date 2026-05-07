"""Plan 16 Task 41 — pin tests for ``brain config migrate``.

The CLI is a thin wrapper around
:func:`brain_core.config.migrate.migrate_config_file`; the comprehensive
behavior coverage lives in ``brain_core/tests/config/test_migrate.py``.
These tests pin the user-facing surface:

  * Exit codes (0 / 1 / 2).
  * stdout framing on happy-path migrate vs. happy-path no-op.
  * stderr framing + exit code on missing file / malformed JSON.
  * Default-path resolution when ``path`` argument is omitted.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from brain_cli.app import app
from brain_cli.commands import config as config_cmd
from typer.testing import CliRunner

runner = CliRunner()


def _legacy_payload() -> dict[str, object]:
    """Pre-T38 flat autonomous shape — guaranteed to trigger a migration."""
    return {
        "domains": ["research"],
        "autonomous": {
            "ingest": True,
            "entities": False,
            "concepts": False,
            "index_rewrites": False,
            "draft": False,
        },
    }


def _new_shape_payload() -> dict[str, object]:
    """Post-T38 nested shape — migration is a no-op on this input."""
    return {
        "domains": ["research"],
        "autonomous": {
            "research": {
                "new_files": True,
                "edits": False,
                "index_entries": True,
                "concepts": False,
                "draft": False,
            }
        },
    }


def test_migrate_old_shape_succeeds(tmp_path: Path) -> None:
    """Old-shape file → exit 0 + ``Migrated`` framing + backup mentioned."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(_legacy_payload()), encoding="utf-8")

    result = runner.invoke(app, ["config", "migrate", str(cfg_path)])

    assert result.exit_code == 0, result.output
    assert "Migrated" in result.output
    assert str(cfg_path) in result.output
    assert "Backup:" in result.output
    assert "config.json.pre-migrate.bak" in result.output
    assert "Change: autonomous: flat → nested" in result.output

    # The file on disk really is in the new shape now.
    rewritten = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert "research" in rewritten["autonomous"]
    assert rewritten["autonomous"]["research"]["new_files"] is True


def test_migrate_new_shape_is_no_op(tmp_path: Path) -> None:
    """Already-migrated file → exit 0 + ``No migration needed`` framing."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(_new_shape_payload()), encoding="utf-8")

    result = runner.invoke(app, ["config", "migrate", str(cfg_path)])

    assert result.exit_code == 0, result.output
    assert "No migration needed" in result.output
    assert str(cfg_path) in result.output
    # No backup created on a no-op.
    assert not cfg_path.with_name("config.json.pre-migrate.bak").exists()


def test_migrate_missing_file_exits_one(tmp_path: Path) -> None:
    """Nonexistent path → exit 1 + plain-English error + path mentioned.

    Click 8.2+ ``CliRunner.Result`` exposes ``stderr`` separately from
    ``stdout`` by default (the legacy ``mix_stderr`` kwarg was removed).
    """
    missing = tmp_path / "nope.json"
    result = runner.invoke(app, ["config", "migrate", str(missing)])

    assert result.exit_code == 1, result.output
    assert "not found" in result.stderr
    assert str(missing) in result.stderr


def test_migrate_malformed_json_exits_two(tmp_path: Path) -> None:
    """Malformed JSON → exit 2 + ``failed to parse`` framing on stderr."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{ this is not json", encoding="utf-8")

    result = runner.invoke(app, ["config", "migrate", str(cfg_path)])

    assert result.exit_code == 2, result.output
    assert "failed to parse" in result.stderr
    assert str(cfg_path) in result.stderr


def test_migrate_non_dict_top_level_exits_two(tmp_path: Path) -> None:
    """JSON array at top level → exit 2 (same surface as malformed JSON)."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    result = runner.invoke(app, ["config", "migrate", str(cfg_path)])

    assert result.exit_code == 2, result.output
    assert "failed to parse" in result.stderr


def test_migrate_default_path_used_when_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No ``path`` argument → ``_default_config_path()`` is consulted."""
    fake_default = tmp_path / "fake-default.json"
    fake_default.write_text(json.dumps(_legacy_payload()), encoding="utf-8")
    monkeypatch.setattr(config_cmd, "_default_config_path", lambda: fake_default)

    result = runner.invoke(app, ["config", "migrate"])

    assert result.exit_code == 0, result.output
    assert "Migrated" in result.output
    assert str(fake_default) in result.output
