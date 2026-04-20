"""Smoke test for brain_core.tools.propose_note — ToolResult shape.

Covers the rate-limit refusal path (fires before scope_guard / pending_store)
so we don't need to wire a real PendingPatchStore for this smoke test.
brain_mcp's existing test_tool_propose_note.py still exercises the full
staging flow through the transport shim.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.propose_note import NAME, handle


@dataclass
class _AlwaysRefusingLimiter:
    """Minimal rate-limiter stand-in: every ``check`` refuses."""

    def check(self, bucket: str, *, cost: int = 1) -> bool:
        return False


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
        rate_limiter=_AlwaysRefusingLimiter(),
        undo_log=None,
    )


def test_name() -> None:
    assert NAME == "brain_propose_note"


async def test_rate_limit_refusal_short_circuits(tmp_path: Path) -> None:
    result = await handle(
        {"path": "research/notes/x.md", "content": "hi", "reason": "why"},
        _mk_ctx(tmp_path),
    )

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "rate_limited"
    assert result.data["bucket"] == "patches"
