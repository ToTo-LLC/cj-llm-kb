"""Tests for the brain_undo_last MCP tool.

``brain_undo_last`` reverts a previously applied PatchSet by replaying the
undo record on disk. When called with an explicit ``undo_id`` it reverts
exactly that record; when called without one it scans ``<vault>/.brain/undo/``
for the lex-last filename (undo_ids are sortable UTC timestamps) and reverts
that. If the undo directory is missing or empty, the tool returns
``nothing_to_undo`` rather than raising.

The tool is intentionally unrate-limited: undo is a safety/exit-ramp
operation, so gating it behind the same bucket that guards forward writes
would be counterproductive.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from brain_core.vault.types import NewFile, PatchSet
from brain_mcp.tools.base import ToolContext
from brain_mcp.tools.undo_last import NAME, handle


def test_name() -> None:
    assert NAME == "brain_undo_last"


async def test_undo_explicit_id(seeded_vault: Path, make_ctx: Callable[..., ToolContext]) -> None:
    """An explicit undo_id reverts exactly that record."""
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    # VaultWriter.apply requires absolute paths that resolve under vault_root.
    patchset = PatchSet(
        new_files=[NewFile(path=seeded_vault / "research/notes/new.md", content="# hi")],
        reason="x",
    )
    receipt = ctx.writer.apply(patchset, allowed_domains=("research",))
    assert (seeded_vault / "research" / "notes" / "new.md").exists()

    out = await handle({"undo_id": receipt.undo_id}, ctx)
    data = json.loads(out[1].text)
    assert data["status"] == "reverted"
    assert data["undo_id"] == receipt.undo_id
    assert not (seeded_vault / "research" / "notes" / "new.md").exists()


async def test_undo_last_without_id(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """With no argument, the most recent undo record is reverted."""
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    patchset = PatchSet(
        new_files=[NewFile(path=seeded_vault / "research/notes/new.md", content="# hi")],
        reason="x",
    )
    ctx.writer.apply(patchset, allowed_domains=("research",))
    assert (seeded_vault / "research" / "notes" / "new.md").exists()

    out = await handle({}, ctx)
    data = json.loads(out[1].text)
    assert data["status"] == "reverted"
    assert not (seeded_vault / "research" / "notes" / "new.md").exists()


async def test_undo_no_history(tmp_path: Path, make_ctx: Callable[..., ToolContext]) -> None:
    """An empty vault (no .brain/undo/ entries) returns nothing_to_undo."""
    vault = tmp_path / "empty"
    (vault / "research").mkdir(parents=True)
    ctx = make_ctx(vault, allowed_domains=("research",))
    out = await handle({}, ctx)
    data = json.loads(out[1].text)
    assert data["status"] == "nothing_to_undo"


async def test_undo_unknown_id_raises(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """An unknown undo_id propagates FileNotFoundError from UndoLog.revert.

    ``UndoLog.revert`` reads ``<vault>/.brain/undo/<undo_id>.txt``; a missing
    file raises ``FileNotFoundError`` and the tool lets it propagate so the
    MCP session error wrapper surfaces it uniformly.
    """
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    with pytest.raises(FileNotFoundError):
        await handle({"undo_id": "20990101T000000000000"}, ctx)
