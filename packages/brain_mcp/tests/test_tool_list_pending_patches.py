"""Tests for the brain_list_pending_patches MCP tool.

``brain_list_pending_patches`` wraps ``ctx.pending_store.list()`` and returns
only envelope metadata (patch_id, created_at, tool, target_path, reason, mode).
It MUST NOT leak the patchset body — clients inspect bodies via a future
``brain_inspect_patch`` (out of scope for Plan 04). These tests pin that.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from brain_core.chat.types import ChatMode
from brain_core.vault.types import NewFile, PatchSet
from brain_mcp.tools.base import ToolContext
from brain_mcp.tools.list_pending_patches import NAME, handle


def test_name() -> None:
    assert NAME == "brain_list_pending_patches"


async def test_lists_pending_patches(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    # Stage 2 patches via the store directly.
    for i in range(2):
        ctx.pending_store.put(
            patchset=PatchSet(
                new_files=[NewFile(path=Path(f"research/notes/x{i}.md"), content="x")],
                reason=f"r{i}",
            ),
            source_thread="test",
            mode=ChatMode.BRAINSTORM,
            tool="brain_propose_note",
            target_path=Path(f"research/notes/x{i}.md"),
            reason=f"r{i}",
        )
    out = await handle({}, ctx)
    data = json.loads(out[1].text)
    assert data["count"] == 2
    assert len(data["patches"]) == 2
    # Must NOT include the full patchset body.
    assert "new_files" not in data["patches"][0]


async def test_empty_returns_empty(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({}, ctx)
    data = json.loads(out[1].text)
    assert data["count"] == 0
    assert data["patches"] == []


async def test_limit_capped(seeded_vault: Path, make_ctx: Callable[..., ToolContext]) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    for i in range(5):
        ctx.pending_store.put(
            patchset=PatchSet(
                new_files=[NewFile(path=Path(f"research/notes/x{i}.md"), content="x")],
                reason="r",
            ),
            source_thread="t",
            mode=ChatMode.BRAINSTORM,
            tool="brain_propose_note",
            target_path=Path(f"research/notes/x{i}.md"),
            reason="r",
        )
    out = await handle({"limit": 3}, ctx)
    data = json.loads(out[1].text)
    assert len(data["patches"]) == 3
