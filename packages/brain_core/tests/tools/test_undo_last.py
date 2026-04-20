"""Smoke test for brain_core.tools.undo_last — ToolResult shape.

Covers the ``nothing_to_undo`` branch (missing ``.brain/undo/`` directory) —
which fires before any UndoLog call. brain_mcp's existing test_tool_undo_last.py
covers the happy ``reverted`` path end-to-end.
"""

from __future__ import annotations

from pathlib import Path

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.undo_last import NAME, _find_latest_undo_id, handle


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


def test_name() -> None:
    assert NAME == "brain_undo_last"


def test_find_latest_undo_id_empty(tmp_path: Path) -> None:
    """Missing `.brain/undo/` returns None cleanly."""
    assert _find_latest_undo_id(tmp_path) is None


def test_find_latest_undo_id_picks_lex_last(tmp_path: Path) -> None:
    undo_dir = tmp_path / ".brain" / "undo"
    undo_dir.mkdir(parents=True)
    (undo_dir / "20260101T000000000000.txt").write_text("a", encoding="utf-8")
    (undo_dir / "20260102T000000000000.txt").write_text("b", encoding="utf-8")
    assert _find_latest_undo_id(tmp_path) == "20260102T000000000000"


async def test_nothing_to_undo_when_no_history(tmp_path: Path) -> None:
    result = await handle({}, _mk_ctx(tmp_path))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "nothing_to_undo"
