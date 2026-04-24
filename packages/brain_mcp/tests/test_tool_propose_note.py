"""Tests for the brain_propose_note MCP tool.

``brain_propose_note`` stages a new-note PatchSet for later approval. It
MUST NOT write to the vault — the user applies the envelope separately via
``brain_apply_patch`` (Task 16). These tests pin that contract.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from brain_core.vault.paths import ScopeError
from brain_mcp.rate_limit import RateLimitConfig, RateLimiter
from brain_mcp.tools.base import ToolContext
from brain_mcp.tools.propose_note import NAME, handle


def test_name() -> None:
    assert NAME == "brain_propose_note"


async def test_stages_a_pending_patch(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle(
        {
            "path": "research/notes/new-idea.md",
            "content": "# new idea\n\nbody",
            "reason": "captured from MCP client",
        },
        ctx,
    )
    data = json.loads(out[1].text)
    assert "patch_id" in data
    # Vault unchanged.
    assert not (seeded_vault / "research" / "notes" / "new-idea.md").exists()
    # One pending patch.
    pending = ctx.pending_store.list()
    assert len(pending) == 1
    # Issue #30: MCP-staged patches carry ChatMode.MCP so the patch-queue UI
    # can distinguish them from chat-origin (BRAINSTORM/DRAFT) patches.
    from brain_core.chat.types import ChatMode
    assert pending[0].mode is ChatMode.MCP


async def test_out_of_scope_path_raises(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    with pytest.raises(ScopeError):
        await handle(
            {"path": "personal/notes/secret.md", "content": "x", "reason": "no"},
            ctx,
        )
    assert ctx.pending_store.list() == []


async def test_absolute_path_rejected(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    absolute = str(seeded_vault / "research" / "notes" / "x.md")
    with pytest.raises(ValueError, match="vault-relative"):
        await handle({"path": absolute, "content": "x", "reason": "no"}, ctx)


async def test_rate_limit_patches_bucket(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    base = make_ctx(seeded_vault, allowed_domains=("research",))
    limiter = RateLimiter(RateLimitConfig(patches_per_minute=1))
    limiter.check("patches", cost=1)  # drain
    ctx = replace(base, rate_limiter=limiter)
    out = await handle(
        {"path": "research/notes/x.md", "content": "x", "reason": "x"},
        ctx,
    )
    data = json.loads(out[1].text)
    assert data["status"] == "rate_limited"
