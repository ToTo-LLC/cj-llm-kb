"""Smoke test for brain_core.tools.config_get — ToolResult shape + secret refusal.

Covers the secret-refusal branch (fires before any snapshot traversal) and a
happy-path lookup on a known key. brain_mcp's existing
test_tool_config_get_set.py exercises the full dotted-key path + unknown-key
errors through the shim.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.config_get import NAME, handle


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
    assert NAME == "brain_config_get"


async def test_refuses_secret_like_key(tmp_path: Path) -> None:
    with pytest.raises(PermissionError, match="secret-like"):
        await handle({"key": "llm.api_key"}, _mk_ctx(tmp_path))


async def test_returns_vault_path_from_ctx(tmp_path: Path) -> None:
    result = await handle({"key": "vault_path"}, _mk_ctx(tmp_path))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["key"] == "vault_path"
    assert result.data["value"] == str(tmp_path)
