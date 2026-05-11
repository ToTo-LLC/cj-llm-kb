"""Smoke test for brain_core.tools.lint — ToolResult shape.

brain_lint is a stub until Plan 09 lands the real engine; the handler always
returns ``status=not_implemented``. Pin that contract.
"""

from __future__ import annotations

from pathlib import Path

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.lint import NAME, handle


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
    assert NAME == "brain_lint"


async def test_stub_returns_not_implemented(tmp_path: Path) -> None:
    result = await handle({}, _mk_ctx(tmp_path))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["status"] == "not_implemented"
    assert "Plan 09" in result.data["message"]


async def test_data_keys_pin(tmp_path: Path) -> None:
    """Plan 18 T3.4 drift pin: backend stub must emit exactly these
    keys in `ToolResult.data` (and the TS `lint()` interface at
    `apps/brain_web/src/lib/api/tools.ts` must mirror them). When Plan
    09 lands the real lint engine and changes the backend shape, this
    test will fail RED and the TS interface will need to be widened in
    lockstep.
    """
    result = await handle({}, _mk_ctx(tmp_path))
    assert result.data is not None
    assert set(result.data.keys()) == {"status", "message"}
