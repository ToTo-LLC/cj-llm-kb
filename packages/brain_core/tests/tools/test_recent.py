"""Smoke test for brain_core.tools.recent — ToolResult shape."""

from __future__ import annotations

from pathlib import Path

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.recent import NAME, handle


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
    assert NAME == "brain_recent"


async def test_lists_recent_notes(tmp_path: Path) -> None:
    (tmp_path / "research" / "notes").mkdir(parents=True)
    (tmp_path / "research" / "notes" / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "research" / "notes" / "b.md").write_text("b", encoding="utf-8")
    # chats/ entries must be excluded.
    (tmp_path / "research" / "chats").mkdir()
    (tmp_path / "research" / "chats" / "thread.md").write_text("c", encoding="utf-8")

    result = await handle({}, _mk_ctx(tmp_path))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    paths = [n["path"] for n in result.data["notes"]]
    assert "research/notes/a.md" in paths
    assert "research/notes/b.md" in paths
    assert not any("chats" in p for p in paths)
    assert result.data["limit_used"] == 10
