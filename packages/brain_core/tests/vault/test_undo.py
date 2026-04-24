from __future__ import annotations

from pathlib import Path

from brain_core.vault.types import Edit, NewFile, PatchSet
from brain_core.vault.undo import UndoLog
from brain_core.vault.writer import VaultWriter


def _seed(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


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


def test_undo_edit_restores_prior_when_content_contains_end_prev_sentinel(
    ephemeral_vault: Path,
) -> None:
    """Issue #25: prev content containing the literal ``END_PREV`` line must
    still revert correctly.

    The original parser used ``END_PREV`` as a sentinel and split on it,
    which truncated any prior content that happened to contain that exact
    line. The parser now slices by the recorded ``PREV_LEN`` byte count.
    """
    target = ephemeral_vault / "research" / "concepts" / "c.md"
    # Embed the literal sentinel inside the prior content. The line "END_PREV"
    # alone (no surrounding text) is what the old parser tripped on.
    prior = "---\ntitle: c\n---\n\nbefore\nEND_PREV\nafter\n"
    _seed(target, prior)

    vw = VaultWriter(vault_root=ephemeral_vault)
    r = vw.apply(
        PatchSet(edits=[Edit(path=target, old="before", new="changed")]),
        allowed_domains=("research",),
    )
    assert "changed" in target.read_text(encoding="utf-8")
    assert r.undo_id is not None

    UndoLog(vault_root=ephemeral_vault).revert(r.undo_id)
    restored = target.read_text(encoding="utf-8")
    assert restored == prior, (
        f"undo truncated at sentinel — expected exact prior content, got:\n{restored!r}"
    )
