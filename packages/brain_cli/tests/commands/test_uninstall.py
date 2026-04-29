"""Tests for ``brain uninstall`` — Plan 08 Task 6.

The vault is sacred: every path through this command must either preserve
the vault or require a typed-confirm string. The command also has to do
the right thing non-interactively (``--yes``) without silently removing
anything the user didn't opt into.

All tests mock:

* ``brain_core.integrations.claude_desktop`` (``verify`` + ``uninstall``)
  so we never touch a real Claude Desktop config.
* ``supervisor.stop_brain_api`` + ``pidfile`` so no real daemon is
  involved.

Real disk I/O happens against ``tmp_path``: install dir + vault + shim
all live under the test's scratch directory, and we assert on real
filesystem state post-invocation.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from brain_cli.app import app
from brain_cli.commands import uninstall as uninstall_mod
from typer.testing import CliRunner

runner = CliRunner()


# --------------------------------------------------------------------------
# Fixture helpers
# --------------------------------------------------------------------------


@dataclass
class _FakeVerify:
    """Stand-in for ``claude_desktop.VerifyResult``."""

    entry_present: bool


def _point_at_scratch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build a scratch install dir + vault + shim path. Returns all three."""
    install = tmp_path / "brain"
    install.mkdir()
    (install / ".venv").mkdir()
    (install / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    (install / "pyproject.toml").write_text("[project]\nname = 'brain'\n", encoding="utf-8")

    vault = tmp_path / "vault"
    (vault / ".brain" / "run").mkdir(parents=True)
    (vault / ".brain" / "backups").mkdir(parents=True)
    (vault / "Research").mkdir()
    (vault / "BRAIN.md").write_text("# brain\n", encoding="utf-8")
    (vault / ".brain" / "backups" / "snap-1.tar.gz").write_bytes(b"fake-tar-1")
    (vault / ".brain" / "backups" / "snap-2.tar.gz").write_bytes(b"fake-tar-2")

    # Shim dir — we point BRAIN_SHIM_DIR so the command uses this scratch
    # location instead of touching the real ~/.local/bin.
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    shim_name = "brain.cmd" if sys.platform == "win32" else "brain"
    shim = shim_dir / shim_name
    shim.write_text("#!/usr/bin/env bash\necho stub\n", encoding="utf-8")

    monkeypatch.setenv("BRAIN_INSTALL_DIR", str(install))
    monkeypatch.setenv("BRAIN_VAULT_ROOT", str(vault))
    monkeypatch.setenv("BRAIN_SHIM_DIR", str(shim_dir))

    return install, vault, shim


def _stub_claude_desktop(monkeypatch: pytest.MonkeyPatch, *, installed: bool) -> dict[str, int]:
    """Stub ``claude_desktop.verify`` / ``uninstall``.

    Returns a ``calls`` dict mutated as the command invokes the module,
    so tests can assert on whether the uninstall ran.
    """
    calls = {"verify": 0, "uninstall": 0}

    def _fake_verify(**_kwargs: object) -> _FakeVerify:
        calls["verify"] += 1
        return _FakeVerify(entry_present=installed)

    def _fake_uninstall(**_kwargs: object) -> None:
        calls["uninstall"] += 1

    monkeypatch.setattr(uninstall_mod.claude_desktop, "verify", _fake_verify)
    monkeypatch.setattr(uninstall_mod.claude_desktop, "uninstall", _fake_uninstall)
    # Also stub ``detect_config_path`` so we never touch the user's real
    # Claude Desktop config during tests (env override does that, but
    # this is belt-and-suspenders).
    monkeypatch.setattr(
        uninstall_mod.claude_desktop,
        "detect_config_path",
        lambda: Path("/nonexistent/claude_desktop_config.json"),
    )
    return calls


def _stub_no_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the ``brain stop`` step a no-op — no daemon running."""
    monkeypatch.setattr(uninstall_mod.pidfile, "read_pid", lambda _p: None)
    monkeypatch.setattr(uninstall_mod.pidfile, "is_alive", lambda _pid: False)

    def _no_stop(_pid: int) -> None:
        return None

    monkeypatch.setattr(uninstall_mod.supervisor, "stop_brain_api", _no_stop)


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


def test_uninstall_happy_path_interactive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """UNINSTALL + remove MCP + keep vault + remove backups → all expected effects."""
    install, vault, shim = _point_at_scratch(monkeypatch, tmp_path)
    calls = _stub_claude_desktop(monkeypatch, installed=True)
    _stub_no_daemon(monkeypatch)

    # Prompt sequence:
    # 1. typed UNINSTALL for code removal
    # 2. y for MCP removal
    # 3. [Enter] (default yes) to keep vault
    # 4. [Enter] (default yes) to remove backups
    stdin = "UNINSTALL\ny\n\n\n"
    result = runner.invoke(app, ["uninstall"], input=stdin)

    assert result.exit_code == 0, result.output
    assert not install.exists(), "install dir must be removed"
    assert vault.exists(), "vault must be preserved"
    assert (vault / "BRAIN.md").exists(), "vault content must survive"
    assert not (vault / ".brain" / "backups").exists(), "backups must be removed"
    assert not shim.exists(), "shim must be removed"
    assert calls["uninstall"] == 1
    assert "Uninstall complete" in result.output


def test_uninstall_keeps_vault_by_default_at_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pressing Enter at the vault prompt preserves the vault (default Y)."""
    install, vault, _shim = _point_at_scratch(monkeypatch, tmp_path)
    _stub_claude_desktop(monkeypatch, installed=False)  # MCP prompt skipped
    _stub_no_daemon(monkeypatch)

    # 1. UNINSTALL (code)
    # 2. Enter (keep vault — default Y)
    # 3. y (remove backups default)
    stdin = "UNINSTALL\n\ny\n"
    result = runner.invoke(app, ["uninstall"], input=stdin)

    assert result.exit_code == 0, result.output
    assert not install.exists()
    assert vault.exists()
    assert (vault / "BRAIN.md").exists()
    assert not (vault / ".brain" / "backups").exists()


def test_uninstall_delete_vault_typed_confirm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DELETE-VAULT typed-confirm removes vault; no backup prompt follows."""
    install, vault, _shim = _point_at_scratch(monkeypatch, tmp_path)
    _stub_claude_desktop(monkeypatch, installed=False)
    _stub_no_daemon(monkeypatch)

    # 1. UNINSTALL
    # 2. n (do not keep vault)
    # 3. DELETE-VAULT (typed-confirm)
    stdin = "UNINSTALL\nn\nDELETE-VAULT\n"
    result = runner.invoke(app, ["uninstall"], input=stdin)

    assert result.exit_code == 0, result.output
    assert not install.exists(), "install dir must be gone"
    assert not vault.exists(), "vault must be gone (DELETE-VAULT typed)"
    # Backups also gone because they lived inside the deleted vault.


def test_uninstall_wrong_word_cancels_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anything other than ``UNINSTALL`` at step 1 cancels with no side effects."""
    install, vault, shim = _point_at_scratch(monkeypatch, tmp_path)
    calls = _stub_claude_desktop(monkeypatch, installed=True)
    _stub_no_daemon(monkeypatch)

    # User types the wrong thing.
    result = runner.invoke(app, ["uninstall"], input="uninstall\n")

    assert result.exit_code == 0, result.output
    assert "cancelled" in result.output.lower()
    assert install.exists(), "install dir must be untouched"
    assert vault.exists()
    assert shim.exists()
    assert calls["uninstall"] == 0, "Claude Desktop must be untouched on cancel"


def test_uninstall_non_interactive_yes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--yes`` removes code + MCP + backups; preserves vault by default."""
    install, vault, shim = _point_at_scratch(monkeypatch, tmp_path)
    calls = _stub_claude_desktop(monkeypatch, installed=True)
    _stub_no_daemon(monkeypatch)

    result = runner.invoke(app, ["uninstall", "--yes"])

    assert result.exit_code == 0, result.output
    assert not install.exists()
    assert vault.exists(), "--yes alone must preserve vault (belt + suspenders)"
    assert (vault / "BRAIN.md").exists()
    assert not (vault / ".brain" / "backups").exists(), "backups removed by default"
    assert not shim.exists()
    assert calls["uninstall"] == 1


def test_uninstall_non_interactive_delete_vault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--yes --delete-vault`` removes everything non-interactively."""
    install, vault, _shim = _point_at_scratch(monkeypatch, tmp_path)
    _stub_claude_desktop(monkeypatch, installed=True)
    _stub_no_daemon(monkeypatch)

    result = runner.invoke(app, ["uninstall", "--yes", "--delete-vault"])

    assert result.exit_code == 0, result.output
    assert not install.exists()
    assert not vault.exists(), "vault must be removed with --delete-vault"


def test_uninstall_skips_mcp_prompt_when_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When verify says "not installed", the MCP prompt is skipped silently."""
    install, vault, _shim = _point_at_scratch(monkeypatch, tmp_path)
    calls = _stub_claude_desktop(monkeypatch, installed=False)
    _stub_no_daemon(monkeypatch)

    # Since MCP isn't installed, we only need prompts for code + vault + backup:
    # 1. UNINSTALL
    # 2. Enter (keep vault)
    # 3. Enter (default yes: remove backups)
    stdin = "UNINSTALL\n\n\n"
    result = runner.invoke(app, ["uninstall"], input=stdin)

    assert result.exit_code == 0, result.output
    assert not install.exists()
    assert vault.exists(), "vault preserved"
    # MCP prompt must NOT have asked the user; we never called uninstall.
    assert calls["verify"] >= 1
    assert calls["uninstall"] == 0
    # No "Claude Desktop" line in the summary because there was nothing to do.
    assert "Claude Desktop MCP entry removed" not in result.output


# Silence a false-positive "unused" warning on the Any import when editors
# strip the import on save. ``Any`` is used indirectly via monkeypatch.
_ = Any
