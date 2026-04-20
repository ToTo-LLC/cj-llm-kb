"""Smoke test for brain_core.tools.list_pending_patches — ToolResult shape.

The handler has no rate-limit branch and is read-only, so we exercise the
happy path by handing it a tiny in-memory fake store that returns zero
envelopes. That pins the ``count=0`` + ``patches=[]`` + empty-state text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.list_pending_patches import NAME, handle


@dataclass
class _EmptyStore:
    """PendingPatchStore stand-in returning an empty list."""

    envelopes: list[Any] = field(default_factory=list)

    def list(self) -> list[Any]:
        return list(self.envelopes)


def _mk_ctx(vault: Path, store: _EmptyStore) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=store,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )


def test_name() -> None:
    assert NAME == "brain_list_pending_patches"


async def test_empty_store_returns_count_zero(tmp_path: Path) -> None:
    result = await handle({}, _mk_ctx(tmp_path, _EmptyStore()))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["count"] == 0
    assert result.data["patches"] == []
    assert "(no pending patches)" in result.text
