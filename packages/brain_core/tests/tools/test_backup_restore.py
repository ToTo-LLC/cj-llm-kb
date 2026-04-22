"""Tests for brain_core.tools.backup_restore."""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.backup import create_snapshot
from brain_core.tools.backup_restore import NAME, handle
from brain_core.tools.base import ToolContext, ToolResult


def _mk_ctx(vault: Path) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )


def _seed_vault(vault: Path, body: str) -> None:
    vault.mkdir(parents=True, exist_ok=True)
    (vault / "research").mkdir(exist_ok=True)
    (vault / "research" / "note.md").write_text(
        f"---\ntitle: Note\n---\n{body}\n", encoding="utf-8"
    )


def test_name() -> None:
    assert NAME == "brain_backup_restore"


async def test_requires_typed_confirm(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_vault(vault, "original")
    meta = create_snapshot(vault, trigger="manual")
    with pytest.raises(PermissionError, match="typed_confirm"):
        await handle(
            {"backup_id": meta.backup_id, "typed_confirm": False},
            _mk_ctx(vault),
        )
    # Nothing was moved to trash.
    assert (vault / "research" / "note.md").exists()


async def test_restore_replaces_contents_and_moves_prior_to_trash(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    _seed_vault(vault, "original")
    meta = create_snapshot(vault, trigger="manual")
    # Mutate the vault after the snapshot.
    _seed_vault(vault, "mutated-after-snapshot")

    result = await handle(
        {"backup_id": meta.backup_id, "typed_confirm": True},
        _mk_ctx(vault),
    )
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "restored"
    assert Path(result.data["trash_path"]).exists()

    # The restored note has the original content.
    restored = (vault / "research" / "note.md").read_text(encoding="utf-8")
    assert "original" in restored
    assert "mutated-after-snapshot" not in restored


async def test_unknown_backup_id_raises(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_vault(vault, "x")
    with pytest.raises(FileNotFoundError):
        await handle(
            {"backup_id": "20260101T000000000000-manual", "typed_confirm": True},
            _mk_ctx(vault),
        )
