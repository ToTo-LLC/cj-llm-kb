"""Smoke test for brain_core.tools.read_note — ToolResult shape."""

from __future__ import annotations

from pathlib import Path

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.read_note import NAME, handle


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
    assert NAME == "brain_read_note"


async def test_reads_note(tmp_path: Path) -> None:
    (tmp_path / "research" / "notes").mkdir(parents=True)
    (tmp_path / "research" / "notes" / "x.md").write_text(
        "---\ntitle: Karpathy\n---\nhello world\n", encoding="utf-8"
    )

    result = await handle({"path": "research/notes/x.md"}, _mk_ctx(tmp_path))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["path"] == "research/notes/x.md"
    assert result.data["frontmatter"] == {"title": "Karpathy"}
    assert "hello world" in result.data["body"]
