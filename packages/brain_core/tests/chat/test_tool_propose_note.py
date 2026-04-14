"""Tests for the propose_note tool."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from brain_core.chat.pending import PendingPatchStore, PendingStatus
from brain_core.chat.tools.base import ToolContext
from brain_core.chat.tools.propose_note import ProposeNoteTool
from brain_core.chat.types import ChatMode
from brain_core.vault.paths import ScopeError


@pytest.fixture
def env(tmp_path: Path) -> Iterator[tuple[Path, ToolContext, PendingPatchStore]]:
    vault = tmp_path / "vault"
    (vault / "research").mkdir(parents=True)
    store = PendingPatchStore(tmp_path / ".brain" / "pending")
    ctx = ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        open_doc_path=None,
        retrieval=None,
        pending_store=store,
        state_db=None,
        source_thread="research/chats/2026-04-14-thread.md",
        mode_name=ChatMode.BRAINSTORM.value,
    )
    yield vault, ctx, store


def test_stages_a_pending_patch(env: tuple[Path, ToolContext, PendingPatchStore]) -> None:
    vault, ctx, store = env
    result = ProposeNoteTool().run(
        {
            "path": "research/notes/new-idea.md",
            "content": "# new idea\n\nbody",
            "reason": "brainstorm captured this",
        },
        ctx,
    )
    # Vault must be UNCHANGED.
    assert not (vault / "research" / "notes" / "new-idea.md").exists()
    # Exactly one pending patch.
    listed = store.list()
    assert len(listed) == 1
    env_obj = listed[0]
    assert env_obj.status == PendingStatus.PENDING
    assert env_obj.tool == "propose_note"
    assert env_obj.mode == ChatMode.BRAINSTORM
    assert env_obj.target_path == Path("research/notes/new-idea.md")
    assert env_obj.patchset.new_files[0].content == "# new idea\n\nbody"
    # Result carries the envelope and structured data.
    assert result.proposed_patch == env_obj
    assert result.data is not None
    assert result.data["patch_id"] == env_obj.patch_id
    assert result.data["target_path"] == "research/notes/new-idea.md"


def test_out_of_scope_path_raises(
    env: tuple[Path, ToolContext, PendingPatchStore],
) -> None:
    _, ctx, store = env
    with pytest.raises(ScopeError):
        ProposeNoteTool().run(
            {
                "path": "personal/notes/secret.md",
                "content": "leak",
                "reason": "no",
            },
            ctx,
        )
    assert store.list() == []


def test_absolute_path_rejected(
    env: tuple[Path, ToolContext, PendingPatchStore],
) -> None:
    vault, ctx, store = env
    absolute = (vault / "research" / "notes" / "x.md").as_posix()
    with pytest.raises(ValueError, match="vault-relative"):
        ProposeNoteTool().run(
            {"path": absolute, "content": "x", "reason": "no"},
            ctx,
        )
    assert store.list() == []


def test_requires_pending_store(tmp_path: Path) -> None:
    ctx = ToolContext(
        vault_root=tmp_path / "vault",
        allowed_domains=("research",),
        open_doc_path=None,
        retrieval=None,
        pending_store=None,
        state_db=None,
        source_thread="t.md",
        mode_name=ChatMode.BRAINSTORM.value,
    )
    with pytest.raises(RuntimeError, match="pending_store"):
        ProposeNoteTool().run(
            {"path": "research/notes/x.md", "content": "x", "reason": "x"},
            ctx,
        )
