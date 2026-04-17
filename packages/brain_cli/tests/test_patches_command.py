"""Tests for brain_cli.commands.patches."""

from __future__ import annotations

from pathlib import Path

from brain_cli.app import app
from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.types import ChatMode
from brain_core.vault.types import NewFile, PatchSet
from typer.testing import CliRunner


def _minimal_research_vault(tmp_path: Path) -> Path:
    """Minimal vault layout VaultWriter.apply is willing to touch."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".brain").mkdir()
    for sub in ("sources", "entities", "concepts", "synthesis", "notes"):
        (vault / "research" / sub).mkdir(parents=True)
    (vault / "research" / "index.md").write_text(
        "# research — index\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Synthesis\n",
        encoding="utf-8",
    )
    (vault / "research" / "log.md").write_text("# research — log\n", encoding="utf-8")
    (vault / "BRAIN.md").write_text("# BRAIN\n\nDefault schema doc.\n", encoding="utf-8")
    return vault


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


def test_patches_apply_with_vault_relative_new_file(tmp_path: Path) -> None:
    """Plan 04 Task 25 regression: the envelope stores vault-relative NewFile
    paths. ``brain patches apply`` must land the file under ``<vault>/…``, not
    under CWD. Previously this was silently broken because VaultWriter.apply
    passed the relative path straight to Path.resolve()."""
    vault = _minimal_research_vault(tmp_path)
    target_rel = Path("research/notes/cli-apply.md")
    store = PendingPatchStore(vault / ".brain" / "pending")
    patchset = PatchSet(
        new_files=[NewFile(path=target_rel, content="---\ntitle: CLI\n---\n\nbody\n")],
        reason="cli apply regression",
    )
    env = store.put(
        patchset=patchset,
        source_thread="cli-test",
        mode=ChatMode.ASK,
        tool="propose_note",
        target_path=target_rel,
        reason="cli apply regression",
    )

    result = CliRunner().invoke(
        app,
        ["patches", "apply", env.patch_id, "--yes", "--vault", str(vault)],
    )
    assert result.exit_code == 0, result.output
    assert f"applied {env.patch_id}" in result.output
    landed = vault / target_rel
    assert landed.exists(), f"file should land at {landed}; got output: {result.output}"
    assert landed.read_text(encoding="utf-8").startswith("---")


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
