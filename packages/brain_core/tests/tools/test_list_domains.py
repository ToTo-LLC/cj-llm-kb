"""Smoke test for brain_core.tools.list_domains — ToolResult shape."""

from __future__ import annotations

from pathlib import Path

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.list_domains import NAME, handle


def _mk_ctx(vault: Path, *, allowed_domains: tuple[str, ...] = ("research",)) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=allowed_domains,
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
    assert NAME == "brain_list_domains"


async def test_lists_non_empty_domains(tmp_path: Path) -> None:
    (tmp_path / "research" / "notes").mkdir(parents=True)
    (tmp_path / "research" / "notes" / "x.md").write_text("x", encoding="utf-8")
    (tmp_path / "personal" / "notes").mkdir(parents=True)
    (tmp_path / "personal" / "notes" / "y.md").write_text("y", encoding="utf-8")

    result = await handle({}, _mk_ctx(tmp_path))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert "research" in result.data["domains"]
    assert "personal" in result.data["domains"]
