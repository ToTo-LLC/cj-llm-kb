"""Integration tests for ``brain doctor``.

We mock every individual check so the command logic (ordering, output,
exit code, ``--json`` mode) is tested hermetically.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from brain_cli.app import app
from brain_cli.runtime import checks
from typer.testing import CliRunner

runner = CliRunner()


def _patch_all_passing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch every check function to return a PASS CheckResult."""
    names = [
        "check_uv",
        "check_install_dir",
        "check_venv",
        "check_node",
        "check_ports",
        "check_vault",
        "check_token",
        "check_config",
        "check_sqlite",
        "check_ui_bundle",
    ]
    for name in names:
        # Note: ``check_node`` normally returns INFO. Keep PASS for this
        # fixture — the command counts PASS+INFO+WARN as "not failing".
        status = "info" if name == "check_node" else "pass"
        monkeypatch.setattr(
            checks,
            name,
            _make_stub(name.replace("check_", ""), status),
        )


def _make_stub(name: str, status: str):  # type: ignore[no-untyped-def]
    def _stub(*args, **kwargs):  # type: ignore[no-untyped-def]
        return checks.CheckResult(name=name, status=status, message="ok")

    return _stub


def test_doctor_all_pass_exit_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every check passes → summary ``10/10`` + exit 0."""
    monkeypatch.setenv("BRAIN_VAULT_ROOT", str(tmp_path / "vault"))
    monkeypatch.setenv("BRAIN_INSTALL_DIR", str(tmp_path / "install"))
    _patch_all_passing(monkeypatch)

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "10/10" in result.output


def test_doctor_with_failure_exits_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A single FAIL flips the exit code to 1 and shows the fix hint."""
    monkeypatch.setenv("BRAIN_VAULT_ROOT", str(tmp_path / "vault"))
    monkeypatch.setenv("BRAIN_INSTALL_DIR", str(tmp_path / "install"))
    _patch_all_passing(monkeypatch)

    def failing_token(*args, **kwargs):  # type: ignore[no-untyped-def]
        return checks.CheckResult(
            name="token",
            status="fail",
            message="missing",
            fix_hint="run `brain setup` to regenerate the token.",
        )

    monkeypatch.setattr(checks, "check_token", failing_token)

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1, result.output
    assert "[FAIL]" in result.output
    assert "brain setup" in result.output
    # Summary still prints a count — 9 of 10.
    assert "9/10" in result.output


def test_doctor_json_mode_emits_valid_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``brain doctor --json`` must emit a JSON array of 10 check dicts."""
    monkeypatch.setenv("BRAIN_VAULT_ROOT", str(tmp_path / "vault"))
    monkeypatch.setenv("BRAIN_INSTALL_DIR", str(tmp_path / "install"))
    _patch_all_passing(monkeypatch)

    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output.strip())
    assert isinstance(data, list)
    assert len(data) == 10
    for item in data:
        assert set(item.keys()) >= {"name", "status", "message"}
        assert item["status"] in {"pass", "warn", "fail", "info"}
