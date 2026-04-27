"""Tests for brain_core.tools.delete_domain."""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.delete_domain import NAME, handle
from brain_core.vault.undo import UndoLog


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
        undo_log=UndoLog(vault_root=vault),
    )


def _seed_domain(vault: Path, slug: str) -> None:
    domain_dir = vault / slug
    domain_dir.mkdir(parents=True, exist_ok=True)
    (domain_dir / "index.md").write_text(f"---\ntitle: {slug}\n---\n# {slug}\n", encoding="utf-8")
    (domain_dir / "note.md").write_text(
        f"---\ntitle: note\ndomain: {slug}\n---\nbody\n", encoding="utf-8"
    )


def _seed_two_non_personal_domains(vault: Path, target: str) -> None:
    """Seed ``target`` plus an extra non-personal domain so the
    Plan 10 Task 5 "last non-personal" guard doesn't fire when the
    test wants to delete ``target``. Used by tests that pre-date the
    guard.
    """
    _seed_domain(vault, target)
    extra = "research" if target != "research" else "work"
    _seed_domain(vault, extra)


def test_name() -> None:
    assert NAME == "brain_delete_domain"


async def test_requires_typed_confirm(tmp_path: Path) -> None:
    _seed_two_non_personal_domains(tmp_path, "music")
    with pytest.raises(PermissionError, match="typed_confirm"):
        await handle(
            {"slug": "music", "typed_confirm": False},
            _mk_ctx(tmp_path),
        )
    # Nothing happened.
    assert (tmp_path / "music" / "index.md").exists()


async def test_refuses_personal_slug(tmp_path: Path) -> None:
    _seed_domain(tmp_path, "personal")
    with pytest.raises(PermissionError, match="personal"):
        await handle(
            {"slug": "personal", "typed_confirm": True},
            _mk_ctx(tmp_path),
        )
    # Personal domain untouched.
    assert (tmp_path / "personal" / "index.md").exists()


async def test_moves_domain_to_trash_and_records_undo(tmp_path: Path) -> None:
    _seed_two_non_personal_domains(tmp_path, "music")
    result = await handle(
        {"slug": "music", "typed_confirm": True},
        _mk_ctx(tmp_path),
    )
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "deleted"
    trash_path = Path(result.data["trash_path"])
    assert trash_path.exists()
    assert not (tmp_path / "music").exists()
    # The undo record was written.
    undo_id = result.data["undo_id"]
    undo_file = tmp_path / ".brain" / "undo" / f"{undo_id}.txt"
    assert undo_file.exists()
    body = undo_file.read_text(encoding="utf-8")
    assert body.startswith("KIND\tdelete_domain")
    assert "SLUG\tmusic" in body


async def test_undo_restores_domain(tmp_path: Path) -> None:
    _seed_two_non_personal_domains(tmp_path, "music")
    ctx = _mk_ctx(tmp_path)
    result = await handle({"slug": "music", "typed_confirm": True}, ctx)
    assert result.data is not None
    undo_id = result.data["undo_id"]

    # Revert via UndoLog — the Task 25A extension should handle this kind.
    ctx.undo_log.revert(undo_id)

    restored = tmp_path / "music"
    assert restored.exists()
    assert (restored / "index.md").exists()
    assert (restored / "note.md").exists()


async def test_refuses_invalid_slug(tmp_path: Path) -> None:
    # Seed two non-personal domains so the Plan 10 last-non-personal
    # guard doesn't pre-empt the slug-format check.
    _seed_two_non_personal_domains(tmp_path, "research")
    with pytest.raises(ValueError, match="must match"):
        await handle(
            {"slug": "BAD-SLUG", "typed_confirm": True},
            _mk_ctx(tmp_path),
        )


async def test_refuses_missing_domain(tmp_path: Path) -> None:
    # Seed two non-personal domains so the Plan 10 last-non-personal
    # guard doesn't pre-empt the missing-domain check.
    _seed_two_non_personal_domains(tmp_path, "research")
    with pytest.raises(FileNotFoundError):
        await handle(
            {"slug": "nonexistent", "typed_confirm": True},
            _mk_ctx(tmp_path),
        )


async def test_refuses_last_non_personal_domain(tmp_path: Path) -> None:
    """Plan 10 Task 5 rail 3: deleting the last non-``personal`` domain
    is refused so the user can't end up with only ``personal`` configured.
    """
    _seed_domain(tmp_path, "music")  # only one non-personal domain on disk
    with pytest.raises(PermissionError, match="last non-"):
        await handle(
            {"slug": "music", "typed_confirm": True},
            _mk_ctx(tmp_path),
        )
    # Folder still there — guard fired before the move.
    assert (tmp_path / "music" / "index.md").exists()
