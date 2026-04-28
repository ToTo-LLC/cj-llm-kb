"""Tests for brain_config_get and brain_config_set."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from brain_core.tools.base import ToolContext
from brain_mcp.tools.config_get import NAME as GET_NAME
from brain_mcp.tools.config_get import handle as get_handle
from brain_mcp.tools.config_set import NAME as SET_NAME
from brain_mcp.tools.config_set import handle as set_handle


def test_name() -> None:
    assert GET_NAME == "brain_config_get"
    assert SET_NAME == "brain_config_set"


async def test_config_get_public_field(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await get_handle({"key": "active_domain"}, ctx)
    data = json.loads(out[1].text)
    assert "value" in data
    assert data["key"] == "active_domain"


async def test_config_get_refuses_secret_key(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    with pytest.raises(PermissionError, match="secret"):
        await get_handle({"key": "llm.api_key"}, ctx)


async def test_config_set_settable_field(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """Plan 04 Task 25: settable keys are (budget.daily_usd, log_llm_payloads).
    active_domain was removed from the allowlist — mid-session scope changes
    are dodgy; scope is set per-session via allowed_domains, not via config.
    budget.daily_cap_usd was renamed to budget.daily_usd to match
    BudgetConfig.daily_usd.

    Plan 12 Task 3 update: the conftest fixture now wires a default
    ``Config()`` into ToolContext (so ``brain_config_get`` doesn't raise on
    the lifecycle-violation path), which means ``brain_config_set``
    actually persists — flipping ``persisted`` from False to True. This
    matches the brain_api production path post-Plan 11 Task 7.
    """
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await set_handle({"key": "budget.daily_usd", "value": 10.0}, ctx)
    data = json.loads(out[1].text)
    assert data["status"] == "updated"
    assert data["key"] == "budget.daily_usd"
    assert data["persisted"] is True


async def test_config_set_refuses_active_domain(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """active_domain is no longer settable via MCP (Plan 04 Task 25)."""
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    with pytest.raises(PermissionError, match="not settable"):
        await set_handle({"key": "active_domain", "value": "work"}, ctx)


async def test_config_set_refuses_secret_key(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    with pytest.raises(PermissionError, match="secret"):
        await set_handle({"key": "llm.api_key", "value": "sk-leak"}, ctx)


async def test_config_set_refuses_non_whitelisted_key(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    with pytest.raises(PermissionError, match="not settable"):
        await set_handle({"key": "vault_root", "value": "/tmp/hack"}, ctx)
