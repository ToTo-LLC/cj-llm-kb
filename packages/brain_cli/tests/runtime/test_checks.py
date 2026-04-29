"""Unit tests for each diagnostic check in :mod:`brain_cli.runtime.checks`.

Plan 08 Task 4. We mock every shell-out + network call — the only check
that actually touches the filesystem is ``check_sqlite`` (we create a real
tmp sqlite file because ``sqlite3.connect`` + ``PRAGMA integrity_check``
is cheap and hermetic).
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from brain_cli.runtime import checks

# ---------- check_uv -------------------------------------------------------


def test_check_uv_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """``uv --version`` reports 0.8.12 → PASS with a friendly message."""

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, "uv 0.8.12\n", "")

    monkeypatch.setattr(checks.subprocess, "run", fake_run)
    result = checks.check_uv()
    assert result.status == "pass"
    assert "0.8.12" in result.message


def test_check_uv_fail_not_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """``uv`` missing from PATH → FAIL with the install hint."""

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(2, "No such file or directory: 'uv'")

    monkeypatch.setattr(checks.subprocess, "run", fake_run)
    result = checks.check_uv()
    assert result.status == "fail"
    assert result.fix_hint is not None
    assert "astral.sh/uv" in result.fix_hint


# ---------- check_install_dir ---------------------------------------------


def test_check_install_dir_pass(tmp_path: Path) -> None:
    """``<install>`` exists + has ``.venv/`` → PASS."""
    install = tmp_path / "brain"
    (install / ".venv").mkdir(parents=True)
    result = checks.check_install_dir(install_dir=install)
    assert result.status == "pass"
    assert str(install) in result.message


def test_check_install_dir_fail_missing(tmp_path: Path) -> None:
    """Missing install dir → FAIL with reinstall hint."""
    missing = tmp_path / "nope"
    result = checks.check_install_dir(install_dir=missing)
    assert result.status == "fail"
    assert result.fix_hint is not None
    assert "install.sh" in result.fix_hint or "Reinstall" in result.fix_hint


# ---------- check_venv -----------------------------------------------------


def test_check_venv_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The subprocess successfully imports brain_core → PASS."""
    install = tmp_path / "brain"
    (install / ".venv").mkdir(parents=True)

    captured: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "OK\n", "")

    monkeypatch.setattr(checks.shutil, "which", lambda name: "/fake/bin/uv")
    monkeypatch.setattr(checks.subprocess, "run", fake_run)
    result = checks.check_venv(install_dir=install)
    assert result.status == "pass"
    # Must use the absolute ``uv`` path from shutil.which, not a bare
    # ``"uv"`` — regression guard for the Plan 09 Task 11 PATH bug.
    assert captured["cmd"][0] == "/fake/bin/uv"


def test_check_venv_fail_import_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``uv run python -c 'import brain_core'`` exits non-zero → FAIL."""
    install = tmp_path / "brain"
    (install / ".venv").mkdir(parents=True)

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, "", "ModuleNotFoundError: brain_core\n")

    monkeypatch.setattr(checks.shutil, "which", lambda name: "/fake/bin/uv")
    monkeypatch.setattr(checks.subprocess, "run", fake_run)
    result = checks.check_venv(install_dir=install)
    assert result.status == "fail"
    assert result.fix_hint is not None
    assert "uv sync" in result.fix_hint


def test_check_venv_fail_uv_not_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``shutil.which("uv")`` returns ``None`` → FAIL with install hint.

    Regression: before the Plan 09 Task 11 fix, this relied on the bare
    ``["uv", ...]`` Popen raising FileNotFoundError at runtime. We now
    detect it up front via ``shutil.which`` so doctor reports a clean
    error instead of a subprocess traceback.
    """
    install = tmp_path / "brain"
    (install / ".venv").mkdir(parents=True)

    monkeypatch.setattr(checks.shutil, "which", lambda name: None)
    result = checks.check_venv(install_dir=install)
    assert result.status == "fail"
    assert "uv not on PATH" in result.message


# ---------- check_node -----------------------------------------------------


def test_check_node_pass_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``node`` on PATH → INFO with version (node is never FAIL)."""
    install = tmp_path / "brain"
    install.mkdir()

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, "v20.13.1\n", "")

    monkeypatch.setattr(checks.shutil, "which", lambda name: "/usr/local/bin/node")
    monkeypatch.setattr(checks.subprocess, "run", fake_run)
    result = checks.check_node(install_dir=install)
    assert result.status == "info"
    assert "20.13.1" in result.message


def test_check_node_info_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No node on PATH + no fnm copy → INFO (never FAIL — not required at runtime)."""
    install = tmp_path / "brain"
    install.mkdir()
    monkeypatch.setattr(checks.shutil, "which", lambda name: None)
    result = checks.check_node(install_dir=install)
    assert result.status == "info"
    # Plain-English message mentions that Node isn't required at runtime.
    assert "not required" in result.message.lower() or "not found" in result.message.lower()


# ---------- check_ports ----------------------------------------------------


def test_check_ports_pass_when_free(monkeypatch: pytest.MonkeyPatch) -> None:
    """All 14 ports free → PASS with ``14/14`` in message."""
    monkeypatch.setattr(checks.portprobe, "is_port_free", lambda _port: True)
    result = checks.check_ports()
    assert result.status == "pass"
    assert "14/14" in result.message


def test_check_ports_fail_when_all_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    """All 14 ports bound → FAIL with a rogue-server hint."""
    monkeypatch.setattr(checks.portprobe, "is_port_free", lambda _port: False)
    result = checks.check_ports()
    assert result.status == "fail"
    assert "0/14" in result.message


# ---------- check_vault ----------------------------------------------------


def test_check_vault_pass(tmp_path: Path) -> None:
    """Existing writable vault dir → PASS."""
    vault = tmp_path / "vault"
    vault.mkdir()
    result = checks.check_vault(vault_root=vault)
    assert result.status == "pass"


def test_check_vault_fail_missing(tmp_path: Path) -> None:
    """Missing vault dir → FAIL with a "create vault" hint."""
    missing = tmp_path / "no-vault"
    result = checks.check_vault(vault_root=missing)
    assert result.status == "fail"
    assert result.fix_hint is not None


# ---------- check_token ----------------------------------------------------


def test_check_token_pass(tmp_path: Path) -> None:
    """Token file exists with 0600 mode on Unix → PASS."""
    vault = tmp_path / "vault"
    run = vault / ".brain" / "run"
    run.mkdir(parents=True)
    token = run / "api-secret.txt"
    token.write_text("a" * 32, encoding="utf-8")
    if sys.platform != "win32":
        token.chmod(0o600)
    result = checks.check_token(vault_root=vault)
    assert result.status == "pass"


def test_check_token_fail_missing(tmp_path: Path) -> None:
    """No token file → FAIL with a regenerate hint."""
    vault = tmp_path / "vault"
    vault.mkdir()
    result = checks.check_token(vault_root=vault)
    assert result.status == "fail"
    assert result.fix_hint is not None
    assert "brain setup" in result.fix_hint


@pytest.mark.skipif(sys.platform == "win32", reason="NTFS uses ACLs, not POSIX mode bits")
def test_check_token_warn_on_bad_mode(tmp_path: Path) -> None:
    """Token present but world-readable (0644) on Unix → WARN."""
    vault = tmp_path / "vault"
    run = vault / ".brain" / "run"
    run.mkdir(parents=True)
    token = run / "api-secret.txt"
    token.write_text("a" * 32, encoding="utf-8")
    token.chmod(0o644)
    result = checks.check_token(vault_root=vault)
    assert result.status == "warn"


# ---------- check_config ---------------------------------------------------


def test_check_config_pass(tmp_path: Path) -> None:
    """Valid JSON config parsing against Config schema → PASS."""
    vault = tmp_path / "vault"
    cfg_dir = vault / ".brain"
    cfg_dir.mkdir(parents=True)
    cfg_path = cfg_dir / "config.json"
    cfg_path.write_text(
        '{"vault_path": "' + str(vault).replace("\\", "\\\\") + '", "active_domain": "research"}',
        encoding="utf-8",
    )
    result = checks.check_config(vault_root=vault)
    assert result.status == "pass"


def test_check_config_fail_invalid_json(tmp_path: Path) -> None:
    """Malformed JSON → FAIL with reset hint."""
    vault = tmp_path / "vault"
    cfg_dir = vault / ".brain"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.json").write_text("{not json", encoding="utf-8")
    result = checks.check_config(vault_root=vault)
    assert result.status == "fail"
    assert result.fix_hint is not None
    assert "config" in result.fix_hint.lower()


def test_check_config_warn_when_missing(tmp_path: Path) -> None:
    """Missing config.json → WARN (defaults are used; not a fatal)."""
    vault = tmp_path / "vault"
    vault.mkdir()
    result = checks.check_config(vault_root=vault)
    assert result.status == "warn"


# ---------- check_sqlite ---------------------------------------------------


def test_check_sqlite_pass(tmp_path: Path) -> None:
    """Healthy state.sqlite + costs.sqlite (real files) → PASS."""
    vault = tmp_path / "vault"
    brain = vault / ".brain"
    brain.mkdir(parents=True)
    for name in ("state.sqlite", "costs.sqlite"):
        conn = sqlite3.connect(brain / name)
        conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER)")
        conn.commit()
        conn.close()
    result = checks.check_sqlite(vault_root=vault)
    assert result.status == "pass"


def test_check_sqlite_fail_corrupt(tmp_path: Path) -> None:
    """A file that isn't valid sqlite → FAIL with rebuild hint."""
    vault = tmp_path / "vault"
    brain = vault / ".brain"
    brain.mkdir(parents=True)
    (brain / "state.sqlite").write_bytes(b"not a sqlite database at all")
    (brain / "costs.sqlite").write_bytes(b"also not a database")
    result = checks.check_sqlite(vault_root=vault)
    assert result.status == "fail"
    assert result.fix_hint is not None


# ---------- check_ui_bundle ------------------------------------------------


def test_check_ui_bundle_pass(tmp_path: Path) -> None:
    """``<install>/web/out/index.html`` exists → PASS."""
    install = tmp_path / "brain"
    out = install / "web" / "out"
    out.mkdir(parents=True)
    (out / "index.html").write_text("<!doctype html>", encoding="utf-8")
    result = checks.check_ui_bundle(install_dir=install)
    assert result.status == "pass"


def test_check_ui_bundle_fail_missing(tmp_path: Path) -> None:
    """No index.html anywhere → FAIL with rebuild hint."""
    install = tmp_path / "brain"
    install.mkdir()
    result = checks.check_ui_bundle(install_dir=install)
    assert result.status == "fail"
    assert result.fix_hint is not None
    assert "brain upgrade" in result.fix_hint or "pnpm" in result.fix_hint
