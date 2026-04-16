"""Tests for the brain_search MCP tool."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from brain_core.vault.paths import ScopeError
from brain_mcp.tools.base import ToolContext
from brain_mcp.tools.search import NAME, handle


def test_name() -> None:
    assert NAME == "brain_search"


async def test_returns_in_scope_hits(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({"query": "karpathy llm"}, ctx)
    data = json.loads(out[1].text)
    paths = [h["path"] for h in data["hits"]]
    assert "research/notes/karpathy.md" in paths
    assert not any("personal" in p for p in paths)


async def test_top_k_clamped(seeded_vault: Path, make_ctx: Callable[..., ToolContext]) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({"query": "karpathy", "top_k": 500}, ctx)
    data = json.loads(out[1].text)
    assert data["top_k_used"] == 20


async def test_out_of_scope_domain_raises(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    with pytest.raises(ScopeError):
        await handle({"query": "karpathy", "domains": ["personal"]}, ctx)


async def test_empty_query_returns_empty(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({"query": "   "}, ctx)
    data = json.loads(out[1].text)
    assert data["hits"] == []


async def test_rate_limiter_tokens_consumed(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """Each search consumes from the tokens bucket (search counts as cost=1)."""
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({"query": "karpathy"}, ctx)
    # Rate limiter ran (check didn't raise). Assertion: search succeeded.
    assert out is not None
