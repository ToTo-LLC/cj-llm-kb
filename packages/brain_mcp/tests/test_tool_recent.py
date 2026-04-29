"""Tests for the brain_recent MCP tool."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from brain_core.tools.base import ToolContext
from brain_core.vault.paths import ScopeError
from brain_mcp.tools.recent import NAME, handle


def test_name() -> None:
    assert NAME == "brain_recent"


async def test_returns_recent_sorted(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    # Touch one note to make it most recent.
    target = seeded_vault / "research" / "notes" / "rag.md"
    now = time.time()
    os.utime(target, (now, now))
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({"limit": 5}, ctx)
    data = json.loads(out[1].text)
    assert data["notes"][0]["path"] == "research/notes/rag.md"


async def test_default_limit_is_10(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({}, ctx)
    data = json.loads(out[1].text)
    assert data["limit_used"] == 10


async def test_excludes_chats_directory(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    (seeded_vault / "research" / "chats").mkdir(exist_ok=True)
    (seeded_vault / "research" / "chats" / "old.md").write_text("x", encoding="utf-8")
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({}, ctx)
    data = json.loads(out[1].text)
    paths = [n["path"] for n in data["notes"]]
    assert not any("chats" in p for p in paths)


async def test_out_of_scope_domain_raises(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    with pytest.raises(ScopeError):
        await handle({"domain": "personal"}, ctx)
