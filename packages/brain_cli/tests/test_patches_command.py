"""Tests for brain_cli.commands.patches."""

from __future__ import annotations

from pathlib import Path

from brain_cli.app import app
from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.types import ChatMode
from brain_core.vault.types import PatchSet
from typer.testing import CliRunner


def _stage_patch(vault: Path, *, target: Path, reason: str) -> str:
    store = PendingPatchStore(vault / ".brain" / "pending")
    patchset = PatchSet(reason=reason)
    env = store.put(
        patchset=patchset,
        source_thread="test-thread",
        mode=ChatMode.ASK,
        tool="propose_note",
        target_path=target,
        reason=reason,
    )
    return env.patch_id


def test_patches_list_empty(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    result = CliRunner().invoke(app, ["patches", "list", "--vault", str(vault)])
    assert result.exit_code == 0, result.output
    assert "no pending patches" in result.output


def test_patches_list_shows_staged(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    patch_id = _stage_patch(vault, target=Path("research/notes/foo.md"), reason="add a new note")
    result = CliRunner().invoke(app, ["patches", "list", "--vault", str(vault)])
    assert result.exit_code == 0, result.output
    assert patch_id in result.output
    assert "research/notes/foo.md" in result.output
    assert "propose_note" in result.output


def test_patches_reject_moves_patch(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    patch_id = _stage_patch(vault, target=Path("research/notes/foo.md"), reason="original reason")
    result = CliRunner().invoke(
        app,
        [
            "patches",
            "reject",
            patch_id,
            "--reason",
            "not useful",
            "--vault",
            str(vault),
        ],
    )
    assert result.exit_code == 0, result.output
    assert f"rejected {patch_id}" in result.output

    pending_root = vault / ".brain" / "pending"
    assert not (pending_root / f"{patch_id}.json").exists()
    assert (pending_root / "rejected" / f"{patch_id}.json").exists()


def test_patches_reject_missing_patch(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    result = CliRunner().invoke(
        app,
        [
            "patches",
            "reject",
            "nonexistent",
            "--reason",
            "gone",
            "--vault",
            str(vault),
        ],
    )
    assert result.exit_code == 1
    assert "not found" in result.output
