"""Plan 22 T5 — pin tests for ``brain_core.tools.delete_orphan``.

Pins:

* INPUT_SCHEMA shape (``note_path`` required, ``typed_confirm`` optional).
* ToolResult.data shape (``{status, trash_path, undo_id}``).
* Hard rails per CLAUDE.md "destructive action requires typed
  confirmation": refuses without ``typed_confirm=True``.
* Branch coverage: typed_confirm missing/false, non-orphan note refused,
  missing note refused, happy path moves to trash + writes undo, undo
  round-trip recreates the note at the original path.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.delete_orphan import INPUT_SCHEMA, NAME, handle
from brain_core.vault.frontmatter import serialize_with_frontmatter
from brain_core.vault.paths import _orphan_cache_clear
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


def _seed_orphan(vault: Path, slug: str = "dead") -> Path:
    note_dir = vault / "research" / "sources"
    note_dir.mkdir(parents=True, exist_ok=True)
    fm = {
        "title": slug,
        "domain": "research",
        "type": "source",
        "orphaned": True,
        "orphaned_at": "2026-05-01",
    }
    note_path = note_dir / f"{slug}.md"
    note_path.write_text(
        serialize_with_frontmatter(fm, body="# body content\n"), encoding="utf-8"
    )
    return note_path


def _seed_alive(vault: Path, slug: str = "alive") -> Path:
    note_dir = vault / "research" / "sources"
    note_dir.mkdir(parents=True, exist_ok=True)
    fm = {
        "title": slug,
        "domain": "research",
        "type": "source",
    }
    note_path = note_dir / f"{slug}.md"
    note_path.write_text(
        serialize_with_frontmatter(fm, body="# body\n"), encoding="utf-8"
    )
    return note_path


def test_name() -> None:
    assert NAME == "brain_delete_orphan"


def test_input_schema_shape() -> None:
    assert INPUT_SCHEMA["type"] == "object"
    assert set(INPUT_SCHEMA["properties"].keys()) == {
        "note_path",
        "typed_confirm",
    }
    assert INPUT_SCHEMA["required"] == ["note_path"]
    assert INPUT_SCHEMA["properties"]["note_path"]["type"] == "string"
    assert INPUT_SCHEMA["properties"]["typed_confirm"]["type"] == "boolean"
    assert INPUT_SCHEMA["properties"]["typed_confirm"]["default"] is False


async def test_refuses_without_typed_confirm(tmp_path: Path) -> None:
    """CLAUDE.md hard rail: destructive op without typed_confirm raises."""
    _orphan_cache_clear()
    note = _seed_orphan(tmp_path)
    with pytest.raises(PermissionError, match="typed_confirm"):
        await handle({"note_path": str(note)}, _mk_ctx(tmp_path))
    # File still on disk.
    assert note.exists()


async def test_refuses_with_typed_confirm_false(tmp_path: Path) -> None:
    _orphan_cache_clear()
    note = _seed_orphan(tmp_path)
    with pytest.raises(PermissionError, match="typed_confirm"):
        await handle(
            {"note_path": str(note), "typed_confirm": False},
            _mk_ctx(tmp_path),
        )
    assert note.exists()


async def test_refuses_relative_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="absolute"):
        await handle(
            {"note_path": "rel/path.md", "typed_confirm": True},
            _mk_ctx(tmp_path),
        )


async def test_refuses_missing_note(tmp_path: Path) -> None:
    _orphan_cache_clear()
    (tmp_path / "research").mkdir()
    missing = tmp_path / "research" / "ghost.md"
    with pytest.raises(FileNotFoundError):
        await handle(
            {"note_path": str(missing), "typed_confirm": True},
            _mk_ctx(tmp_path),
        )


async def test_refuses_non_orphan(tmp_path: Path) -> None:
    """delete_orphan refuses to delete a note that isn't marked
    orphaned: true. The non-orphan delete path is intentionally not
    exposed via this tool."""
    _orphan_cache_clear()
    note = _seed_alive(tmp_path)
    with pytest.raises(ValueError, match="not orphaned"):
        await handle(
            {"note_path": str(note), "typed_confirm": True},
            _mk_ctx(tmp_path),
        )
    assert note.exists()


async def test_data_shape_pin_happy_path(tmp_path: Path) -> None:
    _orphan_cache_clear()
    note = _seed_orphan(tmp_path)
    result = await handle(
        {"note_path": str(note), "typed_confirm": True},
        _mk_ctx(tmp_path),
    )
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert set(result.data.keys()) == {"status", "trash_path", "undo_id"}
    assert result.data["status"] == "deleted"
    trash_path = Path(result.data["trash_path"])
    assert trash_path.exists()
    # Source path is gone (moved to trash).
    assert not note.exists()
    # Trash lives under .brain/trash/<YYYY-MM-DD>/.
    assert trash_path.parent.parent == tmp_path / ".brain" / "trash"


async def test_undo_recreates_note_at_original_path(tmp_path: Path) -> None:
    _orphan_cache_clear()
    note = _seed_orphan(tmp_path)
    original_content = note.read_text(encoding="utf-8")
    result = await handle(
        {"note_path": str(note), "typed_confirm": True},
        _mk_ctx(tmp_path),
    )
    assert result.data is not None
    undo_id = result.data["undo_id"]

    assert not note.exists()
    # Run the undo.
    log = UndoLog(vault_root=tmp_path)
    log.revert(undo_id)

    # Note is back at the original path with its original content.
    assert note.exists()
    assert note.read_text(encoding="utf-8") == original_content
    # Trash copy is preserved as an audit trail (belt-and-braces).
    trash_path = Path(result.data["trash_path"])
    assert trash_path.exists()
