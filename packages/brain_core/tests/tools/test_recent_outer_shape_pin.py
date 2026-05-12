"""Plan 19 T4.1 — pin the outer-shape key set of brain_recent's ToolResult.data.

The Plan 18 T2 audit surfaced a cosmetic-severity DRIFT row on the
``brain_recent`` handler: backend emits ``{items, limit_used}`` but the TS
wrapper in ``apps/brain_web/src/lib/api/tools.ts`` declared
``{items: RecentEntry[]}`` only. Plan 19 T4.1 widened the TS wrapper to
include ``limit_used: number``; this pin locks the backend's outer shape
so a future refactor cannot silently drop / rename / add a key without
the TS side lighting up RED first.

The pin is strict set-equality (``set(...) == {...}``): adding a
fifth key or dropping ``limit_used`` both fail. Mirrors the Plan 18 T3
pin pattern.
"""

from __future__ import annotations

from pathlib import Path

from brain_core.tools.base import ToolContext
from brain_core.tools.recent import handle


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


async def test_recent_outer_data_keys_pin(tmp_path: Path) -> None:
    """Plan 19 T4.1: brain_recent ToolResult.data must be exactly ``{items, limit_used}``."""
    # Empty vault is fine — handler returns ``items=[]`` and the
    # ``limit_used`` default (10). Outer shape is independent of content.
    result = await handle({}, _mk_ctx(tmp_path))

    assert result.data is not None
    assert set(result.data.keys()) == {"items", "limit_used"}


async def test_recent_outer_data_keys_pin_with_content(tmp_path: Path) -> None:
    """Plan 19 T4.1: the outer shape stays stable when ``items`` is non-empty.

    Defense-in-depth — the empty-vault test above could pass if the
    handler conditionally added/dropped keys depending on result size.
    This second case exercises the populated path.
    """
    (tmp_path / "research" / "notes").mkdir(parents=True)
    (tmp_path / "research" / "notes" / "a.md").write_text("a", encoding="utf-8")

    result = await handle({"limit": 5}, _mk_ctx(tmp_path))

    assert result.data is not None
    assert set(result.data.keys()) == {"items", "limit_used"}
    assert result.data["limit_used"] == 5  # the requested limit echoes back
