from __future__ import annotations

from pathlib import Path

from brain_core.vault.types import Edit, NewFile, PatchSet
from brain_core.vault.undo import UndoLog
from brain_core.vault.writer import VaultWriter


def test_undo_new_file(ephemeral_vault: Path) -> None:
    vw = VaultWriter(vault_root=ephemeral_vault)
    target = ephemeral_vault / "research" / "sources" / "x.md"
    ps = PatchSet(new_files=[NewFile(path=target, content="---\ntitle: x\n---\n")])
    r = vw.apply(ps, allowed_domains=("research",))
    assert target.exists()
    assert r.undo_id is not None
    UndoLog(vault_root=ephemeral_vault).revert(r.undo_id)
    assert not target.exists()


def test_undo_edit_restores_prior(ephemeral_vault: Path) -> None:
    target = ephemeral_vault / "research" / "concepts" / "c.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("---\ntitle: c\n---\n\nv1\n", encoding="utf-8")
    vw = VaultWriter(vault_root=ephemeral_vault)
    r = vw.apply(
        PatchSet(edits=[Edit(path=target, old="v1", new="v2")]),
        allowed_domains=("research",),
    )
    assert "v2" in target.read_text(encoding="utf-8")
    assert r.undo_id is not None
    UndoLog(vault_root=ephemeral_vault).revert(r.undo_id)
    assert "v1" in target.read_text(encoding="utf-8")
