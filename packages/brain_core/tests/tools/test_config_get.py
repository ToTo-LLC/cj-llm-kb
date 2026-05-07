"""Smoke test for brain_core.tools.config_get — ToolResult shape + secret refusal.

Covers the secret-refusal branch (fires before any snapshot traversal) and a
happy-path lookup on a known key. brain_mcp's existing
test_tool_config_get_set.py exercises the full dotted-key path + unknown-key
errors through the shim.

Plan 12 Task 3 / D5: ``brain_config_get`` now reads the LIVE ``ctx.config``
(not a defaults-backed ``Config()`` snapshot), so the fixture below attaches
a real ``Config`` instance — without it, the tool now raises ``RuntimeError``
to surface the lifecycle violation rather than silently returning defaults.

Plan 16 Task 24 / D24: ``_mk_ctx`` requires an explicit ``Config`` (no
default, no ``Config | None`` Optional union) — matches Plan 15 Task 9 D8
Path A applied to ``test_config_set.py``. The secret-refusal test still
passes a default ``Config()`` for shape only because ``handle`` checks
``_looks_like_secret`` BEFORE the cfg-None guard in ``_snapshot_config``,
so the refusal-path tests don't depend on the Config's contents. The
None-config raise behavior is pinned exclusively in
``test_errors_raise_if_no_config.py::test_config_get_uses_helper`` (Plan
15 Task 8); the previous local ``test_raises_runtime_error_when_ctx_config_is_none``
duplicate has been dropped.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.config.schema import Config
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.config_get import NAME, handle


def _mk_ctx(vault: Path, *, config: Config) -> ToolContext:
    """Build a minimal ToolContext for direct-handle tests.

    Plan 16 Task 24 / D24: ``config`` is a required ``Config`` (no default,
    no Optional union). The None-config raise behavior is pinned in
    ``test_errors_raise_if_no_config.py::test_config_get_uses_helper`` (Plan
    15 Task 8); this fixture intentionally cannot construct a None-config
    context so test authors don't accidentally exercise the
    ``ctx.config is None`` path or the live-Config path without explicit
    intent.
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
    """The secret-substring check fires in ``handle`` before
    ``_snapshot_config`` is invoked, so the refusal does not depend on the
    Config's contents — a default ``Config()`` is passed for shape only.
    """
    with pytest.raises(PermissionError, match="secret-like"):
        await handle({"key": "llm.api_key"}, _mk_ctx(tmp_path, config=Config()))


async def test_returns_vault_path_from_ctx(tmp_path: Path) -> None:
    """``vault_path`` is overlaid from ``ctx.vault_root`` after the Config
    dump — the loader's allowlist excludes ``vault_path`` from the
    persisted blob so the tool injects it explicitly.
    """
    result = await handle({"key": "vault_path"}, _mk_ctx(tmp_path, config=Config()))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["key"] == "vault_path"
    assert result.data["value"] == str(tmp_path)
