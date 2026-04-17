"""Tests for brain_config_get and brain_config_set."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from brain_mcp.tools.base import ToolContext
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
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await set_handle({"key": "active_domain", "value": "work"}, ctx)
    data = json.loads(out[1].text)
    assert data["status"] == "updated"
    assert data["key"] == "active_domain"


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
