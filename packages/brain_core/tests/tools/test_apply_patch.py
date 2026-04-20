"""Smoke test for brain_core.tools.apply_patch — ToolResult shape.

Exercises the rate-limit refusal branch: the handler's first line consumes
from the ``patches`` bucket and returns a refusal ToolResult without touching
the pending store, writer, or vault. brain_mcp's existing
test_tool_apply_patch.py covers the full apply flow end-to-end through the
shim so the transport wrapper + domain-scope + writer apply are still
exhaustively tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from brain_core.tools.apply_patch import NAME, handle
from brain_core.tools.base import ToolContext, ToolResult


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
    assert NAME == "brain_apply_patch"


async def test_rate_limit_refusal_short_circuits(tmp_path: Path) -> None:
    result = await handle({"patch_id": "abc123"}, _mk_ctx(tmp_path))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "rate_limited"
    assert result.data["bucket"] == "patches"
