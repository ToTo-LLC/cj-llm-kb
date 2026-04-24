"""Tests for ``brain_mcp.tools.base`` — MCP-specific transport helpers.

After issue #39 (2026-04-24) the module surface shrank to a single symbol:
``text_result``. ``ToolContext`` / ``ToolResult`` / ``ToolModule`` /
``scope_guard_path`` no longer live here — every call site pulls them from
``brain_core.tools`` / ``brain_core.tools.base`` directly. The previous
re-export identity test (``assert CoreCtx is McpCtx``) is therefore
obsolete and has been removed.

The frozen-dataclass behavior and ``scope_guard_path`` semantics are
exercised in ``packages/brain_core/tests/tools/test_base.py``; the tests
here focus on ``text_result``.
"""

from __future__ import annotations

import json
from pathlib import Path

from brain_core.tools.base import ToolContext, ToolResult
from brain_mcp.tools.base import text_result


def _ctx(vault_root: Path) -> ToolContext:
    # ToolContext construction is smoke-only here — the brain_core
    # test_base.py pins the full field contract (issue #31 added
    # ``config`` bringing it to 11 fields).
    return ToolContext(
        vault_root=vault_root,
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


def test_text_result_plain() -> None:
    out = text_result("hello world")
    assert len(out) == 1
    assert out[0].type == "text"
    assert out[0].text == "hello world"


def test_text_result_with_data() -> None:
    out = text_result("summary", data={"key": "value", "count": 3})
    assert len(out) == 2
    assert out[0].text == "summary"
    assert out[1].type == "text"
    parsed = json.loads(out[1].text)
    assert parsed == {"key": "value", "count": 3}


def test_text_result_accepts_tool_result() -> None:
    """Task 5/6 shim form: ``text_result(ToolResult(...))`` unwraps text+data."""
    out = text_result(ToolResult(text="summary", data={"count": 3}))
    assert len(out) == 2
    assert out[0].text == "summary"
    parsed = json.loads(out[1].text)
    assert parsed == {"count": 3}


def test_text_result_tool_result_without_data() -> None:
    """A ToolResult with no ``data`` produces one TextContent, not two."""
    out = text_result(ToolResult(text="summary"))
    assert len(out) == 1
    assert out[0].text == "summary"


def test_smoke_ctx_construct(tmp_path: Path) -> None:
    """Smoke check that ``ToolContext`` is still importable and constructible
    via the ``brain_core.tools.base`` path. Full contract tests live in
    ``brain_core/tests/tools/test_base.py``."""
    ctx = _ctx(tmp_path)
    assert ctx.vault_root == tmp_path
    assert ctx.allowed_domains == ("research",)
