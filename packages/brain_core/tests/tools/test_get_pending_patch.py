"""Smoke test for brain_core.tools.get_pending_patch — ToolResult shape.

Unlike ``list_pending_patches`` (which uses an in-memory fake store because
it only needs the ``list()`` method), ``get_pending_patch`` exercises a real
:class:`PendingPatchStore` against a tmp vault so we pin the full
envelope+patchset round-trip. Two cases:

1. valid id → envelope metadata + patchset body both surface in ``data``.
2. unknown id → ``KeyError`` propagates (transport wraps to a 404-ish).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.types import ChatMode
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.get_pending_patch import NAME, handle
from brain_core.vault.types import NewFile, PatchSet


def _mk_ctx(vault: Path, store: PendingPatchStore) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=store,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )


def test_name() -> None:
    assert NAME == "brain_get_pending_patch"


async def test_returns_envelope_and_patchset(tmp_path: Path) -> None:
    """A staged patch round-trips: envelope metadata + full patchset body."""
    store = PendingPatchStore(tmp_path / ".brain" / "pending")
    patchset = PatchSet(
        new_files=[NewFile(path=Path("research/notes/x.md"), content="hello")],
        reason="r",
    )
    env = store.put(
        patchset=patchset,
        source_thread="thread-1",
        mode=ChatMode.BRAINSTORM,
        tool="brain_propose_note",
        target_path=Path("research/notes/x.md"),
        reason="because",
    )

    result = await handle({"patch_id": env.patch_id}, _mk_ctx(tmp_path, store))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    # Top-level split: envelope + patchset are separate keys.
    assert set(result.data.keys()) == {"envelope", "patchset"}
    envelope = result.data["envelope"]
    body = result.data["patchset"]

    # Envelope carries metadata but NOT the patchset body.
    assert envelope["patch_id"] == env.patch_id
    assert envelope["tool"] == "brain_propose_note"
    assert envelope["target_path"] == "research/notes/x.md"
    assert envelope["reason"] == "because"
    assert envelope["source_thread"] == "thread-1"
    assert envelope["mode"] == ChatMode.BRAINSTORM.value
    assert "created_at" in envelope
    assert "patchset" not in envelope

    # Patchset carries the typed PatchSet body fields.
    assert isinstance(body, dict)
    assert body["new_files"][0]["path"] == "research/notes/x.md"
    assert body["new_files"][0]["content"] == "hello"
    assert body["reason"] == "r"
    # Other PatchSet fields (edits/index_entries/log_entry) round-trip as
    # their default empty shapes — pin their presence so the UI can render
    # empty sections without guarding for missing keys.
    assert "edits" in body
    assert "index_entries" in body


async def test_unknown_id_raises_key_error(tmp_path: Path) -> None:
    store = PendingPatchStore(tmp_path / ".brain" / "pending")
    with pytest.raises(KeyError, match="not found"):
        await handle({"patch_id": "does-not-exist"}, _mk_ctx(tmp_path, store))
