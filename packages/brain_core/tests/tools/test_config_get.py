"""Smoke test for brain_core.tools.config_get — ToolResult shape + secret refusal.

Covers the secret-refusal branch (fires before any snapshot traversal) and a
happy-path lookup on a known key. brain_mcp's existing
test_tool_config_get_set.py exercises the full dotted-key path + unknown-key
errors through the shim.

Plan 12 Task 3 / D5: ``brain_config_get`` now reads the LIVE ``ctx.config``
(not a defaults-backed ``Config()`` snapshot), so the fixture below attaches
a real ``Config`` instance — without it, the tool now raises ``RuntimeError``
to surface the lifecycle violation rather than silently returning defaults.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.config.schema import Config
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.config_get import NAME, handle


def _mk_ctx(vault: Path, config: Config | None) -> ToolContext:
    """Build a minimal ToolContext for direct-handle tests.

    ``config`` is a required argument (no implicit default-Config fallback)
    so test authors don't accidentally exercise the ``ctx.config is None``
    raise path or the live-Config path without explicit intent.
    """
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
        config=config,
    )


def test_name() -> None:
    assert NAME == "brain_config_get"


async def test_refuses_secret_like_key(tmp_path: Path) -> None:
    """The secret-substring check fires before any Config traversal — and
    crucially before the ``ctx.config is None`` check, so a bad key on a
    misconfigured ctx still raises ``PermissionError`` (not ``RuntimeError``).
    """
    with pytest.raises(PermissionError, match="secret-like"):
        await handle({"key": "llm.api_key"}, _mk_ctx(tmp_path, config=None))


async def test_returns_vault_path_from_ctx(tmp_path: Path) -> None:
    """``vault_path`` is overlaid from ``ctx.vault_root`` after the Config
    dump — the loader's allowlist excludes ``vault_path`` from the
    persisted blob so the tool injects it explicitly.
    """
    result = await handle({"key": "vault_path"}, _mk_ctx(tmp_path, Config()))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["key"] == "vault_path"
    assert result.data["value"] == str(tmp_path)


async def test_raises_runtime_error_when_ctx_config_is_none(tmp_path: Path) -> None:
    """Plan 12 Task 3 / D5: a ``None`` config is a lifecycle violation —
    the wrapper (brain_api lifespan / brain_mcp _build_ctx) is responsible
    for threading the loaded Config through. Silently returning ``Config()``
    defaults would make Settings reads lie about the resolved config
    (Plan 11 lesson 343 anti-pattern).
    """
    ctx = _mk_ctx(tmp_path, config=None)
    with pytest.raises(RuntimeError, match="ctx.config"):
        await handle({"key": "active_domain"}, ctx)
