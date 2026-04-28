"""Plan 12 Task 3 / D5 — targeted regression for the seed offender.

Before this fix, ``brain_config_get`` constructed ``defaults = Config()``
inside ``_snapshot_config`` and read every key off that defaults-backed
snapshot. The Settings UI's reads therefore reflected SCHEMA defaults,
not the session's actual ``ctx.config`` state — so any prior
``brain_config_set`` mutations or ``load_config`` overrides were invisible.

This test pins the fix at the per-tool level: build a sentinel-bearing
``Config``, attach to ``ctx.config``, invoke ``brain_config_get`` for a
field set on that Config, and assert the response carries the sentinel
value (NOT the schema default).

Companion to ``test_read_tools_thread_ctx_config.py`` (the parametrized
contract test); this one targets the seed offender directly with explicit
field-by-field assertions, so a regression on any single field surfaces
with a focused failure message rather than a single-row parametrize failure.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.config.schema import Config
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.config_get import handle


def _mk_ctx(vault: Path, config: Config | None) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research", "work", "personal", "sentinel-domain"),
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


async def test_active_domain_reflects_ctx_config_not_defaults(tmp_path: Path) -> None:
    """The sentinel ``"sentinel-domain"`` is NOT a Config default — if
    ``brain_config_get`` returned it, the tool MUST be reading
    ``ctx.config`` rather than ``Config()``.
    """
    cfg = Config(
        active_domain="sentinel-domain",
        domains=["research", "work", "personal", "sentinel-domain"],
    )
    ctx = _mk_ctx(tmp_path, cfg)

    result = await handle({"key": "active_domain"}, ctx)
    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["key"] == "active_domain"
    # Schema default is ``"research"``; the sentinel proves we read live ctx.config.
    assert result.data["value"] == "sentinel-domain"


async def test_domains_list_reflects_ctx_config_not_defaults(tmp_path: Path) -> None:
    """The default ``Config().domains`` is ``["research", "work", "personal"]``;
    a custom list including a sentinel proves the tool dumps ``ctx.config``,
    not a fresh snapshot.
    """
    cfg = Config(
        domains=["research", "work", "personal", "sentinel-domain"],
        active_domain="research",
    )
    ctx = _mk_ctx(tmp_path, cfg)

    result = await handle({"key": "domains"}, ctx)
    assert result.data is not None
    assert result.data["key"] == "domains"
    assert result.data["value"] == ["research", "work", "personal", "sentinel-domain"]


async def test_nested_field_reflects_ctx_config_not_defaults(tmp_path: Path) -> None:
    """Dotted-key lookup walks the live Config dump — set a non-default
    ``budget.daily_usd`` and assert the lookup returns it, not the schema
    default.
    """
    cfg = Config()
    cfg.budget.daily_usd = 42.5  # non-default sentinel value
    ctx = _mk_ctx(tmp_path, cfg)

    result = await handle({"key": "budget.daily_usd"}, ctx)
    assert result.data is not None
    assert result.data["value"] == pytest.approx(42.5)


async def test_log_llm_payloads_flag_reflects_ctx_config(tmp_path: Path) -> None:
    """Top-level boolean fields also flow through ``ctx.config``."""
    cfg = Config(log_llm_payloads=True)  # default is False
    ctx = _mk_ctx(tmp_path, cfg)

    result = await handle({"key": "log_llm_payloads"}, ctx)
    assert result.data is not None
    assert result.data["value"] is True


async def test_vault_path_overlays_ctx_vault_root_not_config(tmp_path: Path) -> None:
    """``vault_path`` is overlaid from ``ctx.vault_root`` AFTER the Config
    dump (the loader's allowlist excludes it from the persisted blob).
    Pin that the overlay still happens even though ``_snapshot_config``
    now starts from ``ctx.config`` instead of ``Config()``.
    """
    cfg = Config()  # whatever ``vault_path`` Config defaults to is irrelevant
    ctx = _mk_ctx(tmp_path, cfg)

    result = await handle({"key": "vault_path"}, ctx)
    assert result.data is not None
    assert result.data["value"] == str(tmp_path)


async def test_raises_runtime_error_when_ctx_config_is_none(tmp_path: Path) -> None:
    """Plan 12 Task 3 / D5 lifecycle contract: a ``None`` config means the
    wrapper hasn't wired Config in. Raise loudly rather than silently
    falling back to ``Config()`` defaults — that fallback was the
    Plan 11 lesson 343 anti-pattern.
    """
    ctx = _mk_ctx(tmp_path, config=None)
    with pytest.raises(RuntimeError, match="ctx.config"):
        await handle({"key": "active_domain"}, ctx)
