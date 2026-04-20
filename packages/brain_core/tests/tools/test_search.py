"""Smoke test for brain_core.tools.search — ToolResult shape.

The happy path requires a BM25VaultIndex; keeping the smoke test focused on the
empty-query path avoids duplicating brain_mcp's full retrieval coverage while
still asserting the ToolResult contract.
"""

from __future__ import annotations

from pathlib import Path

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.search import NAME, handle


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
    assert NAME == "brain_search"


async def test_empty_query_returns_empty_hits(tmp_path: Path) -> None:
    result = await handle({"query": "  "}, _mk_ctx(tmp_path))

    assert isinstance(result, ToolResult)
    assert result.text == "(empty query)"
    assert result.data is not None
    assert result.data["hits"] == []
    assert result.data["top_k_used"] == 5
