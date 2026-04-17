"""Tests for the brain_apply_patch MCP tool.

``brain_apply_patch`` is the only MCP entry point that actually mutates the
vault. It looks up a staged envelope by patch_id, derives the target domain
from the envelope's target_path, scope-checks the derived domain against
``ctx.allowed_domains``, and then calls :meth:`VaultWriter.apply`. On success
the envelope is moved to ``pending/applied/``. These tests pin that contract
and all the refusal paths (unknown id, cross-domain, rate limit).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from brain_core.chat.types import ChatMode
from brain_core.vault.paths import ScopeError
from brain_core.vault.types import NewFile, PatchSet
from brain_mcp.rate_limit import RateLimitConfig, RateLimiter
from brain_mcp.tools.apply_patch import NAME, handle
from brain_mcp.tools.base import ToolContext


def test_name() -> None:
    assert NAME == "brain_apply_patch"


async def test_apply_patch_writes_vault(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    patchset = PatchSet(
        new_files=[NewFile(path=Path("research/notes/applied.md"), content="# hi")],
        reason="x",
    )
    env = ctx.pending_store.put(
        patchset=patchset,
        source_thread="t",
        mode=ChatMode.BRAINSTORM,
        tool="brain_propose_note",
        target_path=Path("research/notes/applied.md"),
        reason="x",
    )
    out = await handle({"patch_id": env.patch_id}, ctx)
    data = json.loads(out[1].text)
    assert data["status"] == "applied"
    assert "undo_id" in data
    assert data["patch_id"] == env.patch_id
    assert data["applied_files"] == ["research/notes/applied.md"]
    # File now exists on disk.
    assert (seeded_vault / "research" / "notes" / "applied.md").exists()
    # Envelope moved out of pending/.
    assert ctx.pending_store.get(env.patch_id) is None


async def test_apply_unknown_patch_raises(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    with pytest.raises(KeyError):
        await handle({"patch_id": "nonexistent"}, ctx)


async def test_apply_cross_domain_refused(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """A patch targeting personal/ from a research-scoped session must refuse."""
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    # Stage a patch targeting personal/ via direct store write — the store
    # is scratch state and is not scope-guarded by design; the guard fires
    # at apply time.
    patchset = PatchSet(
        new_files=[NewFile(path=Path("personal/notes/sneaky.md"), content="x")],
        reason="x",
    )
    env = ctx.pending_store.put(
        patchset=patchset,
        source_thread="t",
        mode=ChatMode.BRAINSTORM,
        tool="brain_propose_note",
        target_path=Path("personal/notes/sneaky.md"),
        reason="x",
    )
    with pytest.raises(ScopeError):
        await handle({"patch_id": env.patch_id}, ctx)
    # Envelope stays pending; no vault write happened.
    assert ctx.pending_store.get(env.patch_id) is not None
    assert not (seeded_vault / "personal" / "notes" / "sneaky.md").exists()


async def test_apply_rate_limited(seeded_vault: Path, make_ctx: Callable[..., ToolContext]) -> None:
    base = make_ctx(seeded_vault, allowed_domains=("research",))
    limiter = RateLimiter(RateLimitConfig(patches_per_minute=1))
    limiter.check("patches", cost=1)  # drain
    ctx = replace(base, rate_limiter=limiter)
    # Stage a patch using base's pending_store (which the replaced ctx shares,
    # since replace() is a shallow copy of the frozen dataclass fields).
    patchset = PatchSet(
        new_files=[NewFile(path=Path("research/notes/x.md"), content="x")],
        reason="x",
    )
    env = base.pending_store.put(
        patchset=patchset,
        source_thread="t",
        mode=ChatMode.BRAINSTORM,
        tool="brain_propose_note",
        target_path=Path("research/notes/x.md"),
        reason="x",
    )
    out = await handle({"patch_id": env.patch_id}, ctx)
    data = json.loads(out[1].text)
    assert data["status"] == "rate_limited"
    assert data["bucket"] == "patches"
    # Envelope untouched; no vault write.
    assert ctx.pending_store.get(env.patch_id) is not None
    assert not (seeded_vault / "research" / "notes" / "x.md").exists()
