"""Integration tests for ``brain backup``.

Plan 08 Task 9. The CLI verb is a thin wrapper around
``brain_core.backup.create_snapshot``; these tests mock the core call so
they stay fast and do not materialize real tarballs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from brain_cli.app import app
from brain_cli.commands import backup as backup_cmd
from brain_core.backup import BackupMeta
from typer.testing import CliRunner

runner = CliRunner()


def _fake_meta(path: Path) -> BackupMeta:
    return BackupMeta(
        backup_id="20260422T143012000000-manual",
        path=path,
        trigger="manual",
        created_at=datetime(2026, 4, 22, 14, 30, 12, tzinfo=UTC),
        size_bytes=2_516_582,  # ~2.4 MB
        file_count=143,
    )


def test_backup_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Vault exists → ``brain backup`` prints path + human size + file count + exit 0."""
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("BRAIN_VAULT_ROOT", str(vault))

    tarball = vault / ".brain" / "backups" / "20260422T143012000000-manual.tar.gz"
    tarball.parent.mkdir(parents=True)
    tarball.write_bytes(b"fake tarball")

    captured: dict[str, object] = {}

    def fake_create(vault_root: Path, trigger: str = "manual") -> BackupMeta:
        captured["vault_root"] = vault_root
        captured["trigger"] = trigger
        return _fake_meta(tarball)

    monkeypatch.setattr(backup_cmd, "create_snapshot", fake_create)

    result = runner.invoke(app, ["backup"])
    assert result.exit_code == 0, result.output
    assert "Backup created" in result.output
    assert str(tarball) in result.output
    assert "2.4 MB" in result.output
    assert "143" in result.output
    assert "manual" in result.output
    assert captured["trigger"] == "manual"
    assert Path(str(captured["vault_root"])).resolve() == vault.resolve()


def test_backup_no_vault_exits_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing vault → plain-English error + exit 1 (before ``create_snapshot`` runs)."""
    missing_vault = tmp_path / "does-not-exist"
    monkeypatch.setenv("BRAIN_VAULT_ROOT", str(missing_vault))

    def fail_if_called(*args: object, **kwargs: object) -> BackupMeta:
        raise AssertionError("create_snapshot should not run when the vault is missing")

    monkeypatch.setattr(backup_cmd, "create_snapshot", fail_if_called)

    result = runner.invoke(app, ["backup"])
    assert result.exit_code == 1, result.output
    assert "No vault found" in result.output
    assert str(missing_vault) in result.output
    assert "brain doctor" in result.output


def test_backup_core_failure_surfaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``create_snapshot`` raising is not swallowed — user sees the error + exit 1."""
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("BRAIN_VAULT_ROOT", str(vault))

    def broken_create(vault_root: Path, trigger: str = "manual") -> BackupMeta:
        raise RuntimeError("disk full")

    monkeypatch.setattr(backup_cmd, "create_snapshot", broken_create)

    result = runner.invoke(app, ["backup"])
    assert result.exit_code == 1, result.output
    assert "Backup failed" in result.output
    assert "disk full" in result.output


def test_backup_json_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--json`` emits a single JSON object with the BackupMeta fields."""
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("BRAIN_VAULT_ROOT", str(vault))

    tarball = vault / ".brain" / "backups" / "20260422T143012000000-manual.tar.gz"
    tarball.parent.mkdir(parents=True)
    tarball.write_bytes(b"fake tarball")

    monkeypatch.setattr(
        backup_cmd,
        "create_snapshot",
        lambda vault_root, trigger="manual": _fake_meta(tarball),
    )

    result = runner.invoke(app, ["backup", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["backup_id"] == "20260422T143012000000-manual"
    assert payload["path"] == str(tarball)
    assert payload["trigger"] == "manual"
    assert payload["size_bytes"] == 2_516_582
    assert payload["file_count"] == 143
    assert payload["created_at"].startswith("2026-04-22T14:30:12")
