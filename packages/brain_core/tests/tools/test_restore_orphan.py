"""Plan 22 T5 — pin tests for ``brain_core.tools.restore_orphan``.

Pins:

* INPUT_SCHEMA shape (``note_path`` required).
* ToolResult.data shape (``{status, note_path, undo_id}``).
* Branch coverage: not-orphaned refusal, missing-path refusal,
  non-absolute path refusal, happy path flips orphaned → false and
  clears orphaned_at, undo record persisted.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.restore_orphan import INPUT_SCHEMA, NAME, handle
from brain_core.vault.frontmatter import (
    Frontmatter,
    parse_frontmatter,
    serialize_with_frontmatter,
)
from brain_core.vault.paths import _orphan_cache_clear
from brain_core.vault.writer import VaultWriter


def _mk_ctx(vault: Path) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=VaultWriter(vault_root=vault),
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )


def _seed_orphan_note(*, vault: Path, slug: str = "dead") -> Path:
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
        serialize_with_frontmatter(fm, body="# body\n"), encoding="utf-8"
    )
    return note_path


def _seed_alive_note(*, vault: Path, slug: str = "alive") -> Path:
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
    assert NAME == "brain_restore_orphan"


def test_input_schema_shape() -> None:
    assert INPUT_SCHEMA == {
        "type": "object",
        "properties": {
            "note_path": {
                "type": "string",
                "description": "Absolute path to the vault note to restore.",
            },
        },
        "required": ["note_path"],
    }


async def test_refuses_relative_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="absolute"):
        await handle({"note_path": "relative/path.md"}, _mk_ctx(tmp_path))


async def test_refuses_missing_note(tmp_path: Path) -> None:
    _orphan_cache_clear()
    # Path is inside an allowed domain folder so scope_guard passes,
    # but the file itself doesn't exist.
    (tmp_path / "research").mkdir()
    missing = tmp_path / "research" / "ghost.md"
    with pytest.raises(FileNotFoundError):
        await handle({"note_path": str(missing)}, _mk_ctx(tmp_path))


async def test_refuses_non_orphan_note(tmp_path: Path) -> None:
    _orphan_cache_clear()
    note = _seed_alive_note(vault=tmp_path)
    with pytest.raises(ValueError, match="not orphaned"):
        await handle({"note_path": str(note)}, _mk_ctx(tmp_path))


async def test_data_shape_pin_and_flips_frontmatter(tmp_path: Path) -> None:
    _orphan_cache_clear()
    note = _seed_orphan_note(vault=tmp_path)
    result = await handle({"note_path": str(note)}, _mk_ctx(tmp_path))
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert set(result.data.keys()) == {"status", "note_path", "undo_id"}
    assert result.data["status"] == "restored"
    assert result.data["note_path"] == str(note)
    assert result.data["undo_id"] is not None

    # Frontmatter flipped on disk.
    fm_dict, body = parse_frontmatter(note.read_text(encoding="utf-8"))
    fm = Frontmatter.from_dict(fm_dict)
    assert fm.orphaned is False
    assert fm.orphaned_at is None
    # Body untouched.
    assert body == "# body\n"


async def test_undo_record_written(tmp_path: Path) -> None:
    """The VaultWriter mutation persists an undo record."""
    _orphan_cache_clear()
    note = _seed_orphan_note(vault=tmp_path)
    result = await handle({"note_path": str(note)}, _mk_ctx(tmp_path))
    assert result.data is not None
    undo_id = result.data["undo_id"]
    undo_file = tmp_path / ".brain" / "undo" / f"{undo_id}.txt"
    assert undo_file.exists()
    body = undo_file.read_text(encoding="utf-8")
    # Per-file format: PATH + PREV_LEN markers.
    assert "PATH\t" in body
    assert "PREV_LEN\t" in body
