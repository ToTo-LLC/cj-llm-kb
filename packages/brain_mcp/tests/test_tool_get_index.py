"""Tests for the brain_get_index MCP tool."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from brain_core.vault.paths import ScopeError
from brain_mcp.tools.base import ToolContext
from brain_mcp.tools.get_index import NAME, handle


def test_name() -> None:
    assert NAME == "brain_get_index"


async def test_default_domain_reads_first_allowed(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({}, ctx)
    text = out[0].text
    assert "karpathy" in text


async def test_explicit_domain(seeded_vault: Path, make_ctx: Callable[..., ToolContext]) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({"domain": "research"}, ctx)
    assert "karpathy" in out[0].text


async def test_out_of_scope_raises(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    with pytest.raises(ScopeError):
        await handle({"domain": "personal"}, ctx)


async def test_missing_index_returns_empty(
    tmp_path: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """Plan 04 Task 25: the miss-path data dict has the same shape as the
    happy path so clients can unconditionally read data["frontmatter"] and
    data["body"] without a KeyError."""
    import json

    # Fresh vault with no index.md.
    vault = tmp_path / "empty"
    (vault / "research").mkdir(parents=True)
    ctx = make_ctx(vault, allowed_domains=("research",))
    out = await handle({}, ctx)
    assert out[0].text == "(no index yet)"
    data = json.loads(out[1].text)
    # Shape parity with the happy path.
    assert data == {"domain": "research", "frontmatter": {}, "body": ""}
