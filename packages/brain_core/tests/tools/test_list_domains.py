"""Smoke test for brain_core.tools.list_domains — ToolResult shape."""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.config.schema import Config
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.list_domains import NAME, handle


def _mk_ctx(
    vault: Path,
    *,
    allowed_domains: tuple[str, ...] = ("research",),
    config: Config | None = None,
) -> ToolContext:
    """Build a ToolContext for list_domains tests.

    Plan 13 Task 1 / D1: ``list_domains`` now raises ``RuntimeError`` when
    ``ctx.config is None``, so tests must supply a real ``Config`` (production
    shape post-Plan 12 D6 — both brain_api and brain_mcp wrappers thread
    Config through). ``config=None`` is reserved for the strict-policy pin
    test that exercises the raise.
    """
    return ToolContext(
        vault_root=vault,
        allowed_domains=allowed_domains,
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
    assert NAME == "brain_list_domains"


async def test_lists_non_empty_domains(tmp_path: Path) -> None:
    (tmp_path / "research" / "notes").mkdir(parents=True)
    (tmp_path / "research" / "notes" / "x.md").write_text("x", encoding="utf-8")
    (tmp_path / "personal" / "notes").mkdir(parents=True)
    (tmp_path / "personal" / "notes" / "y.md").write_text("y", encoding="utf-8")

    cfg = Config(domains=["research", "personal"], active_domain="research")
    result = await handle({}, _mk_ctx(tmp_path, config=cfg))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert "research" in result.data["domains"]
    assert "personal" in result.data["domains"]
    # Plan 11 Task 6: response carries ``active_domain`` so the frontend
    # can hydrate scope on first mount. Plan 13 Task 1 / D1: ctx.config is
    # always supplied in production-shape paths (no DEFAULT_DOMAINS fallback).
    assert result.data["active_domain"] == "research"


async def test_raises_when_ctx_config_none(tmp_path: Path) -> None:
    """Plan 13 Task 1 / D1: ``list_domains`` raises ``RuntimeError`` when
    ``ctx.config is None``. Mirrors ``brain_config_get``'s strict policy
    (Plan 12 Task 3) — a None config is a lifecycle violation, not a
    fallback case. The brain_api lifespan (Plan 11 Task 7) and brain_mcp
    ``_build_ctx`` (Plan 12 Task 4) are the regression guard.
    """
    with pytest.raises(RuntimeError, match=r"ctx\.config to be a Config"):
        await handle({}, _mk_ctx(tmp_path, config=None))


async def test_returns_union_with_configured_and_on_disk_flags(tmp_path: Path) -> None:
    """Plan 10 Task 5: ``data.entries`` carries the configured/on_disk
    flags for each slug in the union of Config.domains + on-disk dirs.

    Wires a fake config with ``domains=["research", "work", "personal"]``
    and seeds only ``research`` + ``imported`` on disk. Expected union:
    {research (both), work (configured-only), personal (configured-only),
    imported (on-disk only)}.
    """
    from brain_core.config.schema import Config

    cfg = Config(domains=["research", "work", "personal"])
    (tmp_path / "research" / "notes").mkdir(parents=True)
    (tmp_path / "research" / "notes" / "x.md").write_text("x", encoding="utf-8")
    (tmp_path / "imported" / "notes").mkdir(parents=True)
    (tmp_path / "imported" / "notes" / "y.md").write_text("y", encoding="utf-8")

    ctx = ToolContext(
        vault_root=tmp_path,
        allowed_domains=("research", "work", "personal", "imported"),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
        config=cfg,
    )
    result = await handle({}, ctx)

    assert result.data is not None
    assert result.data["domains"] == ["imported", "personal", "research", "work"]
    by_slug = {e["slug"]: e for e in result.data["entries"]}
    assert by_slug["research"] == {"slug": "research", "configured": True, "on_disk": True}
    assert by_slug["work"] == {"slug": "work", "configured": True, "on_disk": False}
    assert by_slug["personal"] == {"slug": "personal", "configured": True, "on_disk": False}
    assert by_slug["imported"] == {"slug": "imported", "configured": False, "on_disk": True}
    # Plan 11 Task 6: with a real Config wired in, active_domain is read
    # live. Default Config(domains=[...]) keeps active_domain="research".
    assert result.data["active_domain"] == "research"
