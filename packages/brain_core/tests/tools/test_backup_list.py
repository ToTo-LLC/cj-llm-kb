"""Tests for brain_core.tools.backup_list."""

from __future__ import annotations

from pathlib import Path

from brain_core.backup import create_snapshot
from brain_core.tools.backup_list import NAME, handle
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


def _seed_vault(vault: Path) -> None:
    vault.mkdir(parents=True, exist_ok=True)
    (vault / "research").mkdir()
    (vault / "research" / "note.md").write_text("---\ntitle: Note\n---\nhello\n", encoding="utf-8")


def test_name() -> None:
    assert NAME == "brain_backup_list"


async def test_empty_backup_dir_returns_empty_list(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_vault(vault)
    result = await handle({}, _mk_ctx(vault))
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["backups"] == []
    assert result.text == "(no backups)"


async def test_lists_snapshots_newest_first(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_vault(vault)
    first = create_snapshot(vault, trigger="manual")
    second = create_snapshot(vault, trigger="daily")

    result = await handle({}, _mk_ctx(vault))
    assert result.data is not None
    ids = [b["backup_id"] for b in result.data["backups"]]
    assert len(ids) == 2
    # Newest first.
    assert ids[0] == second.backup_id
    assert ids[1] == first.backup_id


async def test_malformed_filename_is_skipped(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_vault(vault)
    create_snapshot(vault, trigger="manual")
    bogus = vault / ".brain" / "backups" / "not-a-real-snapshot.tar.gz"
    bogus.write_bytes(b"garbage")

    result = await handle({}, _mk_ctx(vault))
    assert result.data is not None
    assert len(result.data["backups"]) == 1  # garbage file ignored
