"""Tests for the brain_read_note MCP tool."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from brain_core.tools.base import ToolContext
from brain_core.vault.paths import ScopeError
from brain_mcp.tools.read_note import NAME, handle


def test_name() -> None:
    assert NAME == "brain_read_note"


async def test_reads_in_scope_note(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({"path": "research/notes/karpathy.md"}, ctx)
    assert "LLM wiki pattern" in out[0].text


async def test_out_of_scope_raises(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    with pytest.raises(ScopeError):
        await handle({"path": "personal/notes/secret.md"}, ctx)


async def test_missing_file_raises(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    with pytest.raises(FileNotFoundError, match="not found"):
        await handle({"path": "research/notes/nope.md"}, ctx)


async def test_absolute_path_rejected(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    absolute = str(seeded_vault / "research" / "notes" / "karpathy.md")
    with pytest.raises(ValueError, match="vault-relative"):
        await handle({"path": absolute}, ctx)
