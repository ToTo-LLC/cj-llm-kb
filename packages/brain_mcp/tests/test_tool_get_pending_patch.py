"""Tests for the brain_get_pending_patch MCP tool.

``brain_get_pending_patch`` returns the FULL envelope + patchset body for a
staged patch, so Task 16's pending-approval detail pane can render
``new_files`` / ``edits`` / ``log_entry`` / ``index_entries``. This is the
complement to ``brain_list_pending_patches`` (metadata only, no body).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from brain_core.chat.types import ChatMode
from brain_core.tools.base import ToolContext
from brain_core.vault.types import NewFile, PatchSet
from brain_mcp.tools.get_pending_patch import NAME, handle


def test_name() -> None:
    assert NAME == "brain_get_pending_patch"


async def test_returns_envelope_and_patchset(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    env = ctx.pending_store.put(
        patchset=PatchSet(
            new_files=[NewFile(path=Path("research/notes/x.md"), content="body")],
            reason="r",
        ),
        source_thread="t",
        mode=ChatMode.BRAINSTORM,
        tool="brain_propose_note",
        target_path=Path("research/notes/x.md"),
        reason="because",
    )

    out = await handle({"patch_id": env.patch_id}, ctx)
    data = json.loads(out[1].text)
    assert "envelope" in data
    assert "patchset" in data
    assert data["envelope"]["patch_id"] == env.patch_id
    assert data["envelope"]["tool"] == "brain_propose_note"
    # Full body exposed — this is the critical difference vs list.
    assert data["patchset"]["new_files"][0]["content"] == "body"


async def test_unknown_id_raises_key_error(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    with pytest.raises(KeyError, match="not found"):
        await handle({"patch_id": "nope"}, ctx)
