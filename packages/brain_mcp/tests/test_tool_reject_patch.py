"""Tests for the brain_reject_patch MCP tool.

``brain_reject_patch`` wraps :meth:`PendingPatchStore.reject`, which moves the
envelope from ``.brain/pending/<id>.json`` to
``.brain/pending/rejected/<id>.json`` with an updated reason. It is read/
metadata-only with respect to the vault — ZERO vault writes, no VaultWriter
invocation. An unknown patch_id propagates as ``KeyError`` from the store.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from brain_core.chat.types import ChatMode
from brain_core.tools.base import ToolContext
from brain_core.vault.types import NewFile, PatchSet
from brain_mcp.tools.reject_patch import NAME, handle


def test_name() -> None:
    assert NAME == "brain_reject_patch"


async def test_reject_moves_patch(seeded_vault: Path, make_ctx: Callable[..., ToolContext]) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    patchset = PatchSet(
        new_files=[NewFile(path=Path("research/notes/x.md"), content="x")],
        reason="x",
    )
    env = ctx.pending_store.put(
        patchset=patchset,
        source_thread="t",
        mode=ChatMode.BRAINSTORM,
        tool="brain_propose_note",
        target_path=Path("research/notes/x.md"),
        reason="x",
    )
    out = await handle({"patch_id": env.patch_id, "reason": "not useful"}, ctx)
    data = json.loads(out[1].text)
    assert data["status"] == "rejected"
    # Pending/ no longer has it.
    assert ctx.pending_store.get(env.patch_id) is None
    # Rejected/ does.
    assert (seeded_vault / ".brain" / "pending" / "rejected" / f"{env.patch_id}.json").exists()


async def test_reject_unknown_raises(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    with pytest.raises(KeyError):
        await handle({"patch_id": "nope", "reason": "x"}, ctx)


def test_reject_requires_reason() -> None:
    from brain_mcp.tools.reject_patch import INPUT_SCHEMA

    assert "reason" in INPUT_SCHEMA["required"]
