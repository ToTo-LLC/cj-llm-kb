"""Tests for the edit_open_doc tool."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.tools.base import ToolContext
from brain_core.chat.tools.edit_open_doc import EditOpenDocTool
from brain_core.chat.types import ChatMode


@pytest.fixture
def env(tmp_path: Path) -> Iterator[tuple[Path, ToolContext, PendingPatchStore]]:
    vault = tmp_path / "vault"
    (vault / "research").mkdir(parents=True)
    doc = vault / "research" / "drafting.md"
    doc.write_text(
        "# drafting\n\nThe first paragraph has a unique sentence.\nAnother line.\n",
        encoding="utf-8",
    )
    store = PendingPatchStore(tmp_path / ".brain" / "pending")
    ctx = ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        open_doc_path=Path("research/drafting.md"),
        retrieval=None,
        pending_store=store,
        state_db=None,
        source_thread="research/chats/2026-04-14-draft.md",
        mode_name=ChatMode.DRAFT.value,
    )
    yield vault, ctx, store


def test_stages_an_edit(env: tuple[Path, ToolContext, PendingPatchStore]) -> None:
    vault, ctx, store = env
    result = EditOpenDocTool().run(
        {
            "old": "The first paragraph has a unique sentence.",
            "new": "The first paragraph has been rewritten entirely.",
            "reason": "clarify tone",
        },
        ctx,
    )
    # Doc on disk is UNCHANGED.
    doc_body = (vault / "research" / "drafting.md").read_text(encoding="utf-8")
    assert "unique sentence" in doc_body
    assert "rewritten entirely" not in doc_body
    # One pending patch.
    listed = store.list()
    assert len(listed) == 1
    env_obj = listed[0]
    assert env_obj.tool == "edit_open_doc"
    assert env_obj.mode == ChatMode.DRAFT
    assert env_obj.target_path == Path("research/drafting.md")
    assert env_obj.patchset.edits[0].old == "The first paragraph has a unique sentence."
    assert env_obj.patchset.edits[0].new == "The first paragraph has been rewritten entirely."
    # Result shape.
    assert result.proposed_patch is not None
    assert result.data is not None
    assert result.data["patch_id"] == env_obj.patch_id


def test_requires_open_doc(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "research").mkdir(parents=True)
    store = PendingPatchStore(tmp_path / ".brain" / "pending")
    ctx = ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        open_doc_path=None,  # <-- unset
        retrieval=None,
        pending_store=store,
        state_db=None,
        source_thread="t.md",
        mode_name=ChatMode.DRAFT.value,
    )
    with pytest.raises(RuntimeError, match="open_doc_path"):
        EditOpenDocTool().run({"old": "x", "new": "y", "reason": "z"}, ctx)


def test_old_text_not_found_raises(env: tuple[Path, ToolContext, PendingPatchStore]) -> None:
    _, ctx, store = env
    with pytest.raises(ValueError, match="not found"):
        EditOpenDocTool().run(
            {"old": "this string is not in the doc", "new": "x", "reason": "z"},
            ctx,
        )
    assert store.list() == []


def test_old_text_not_unique_raises(
    env: tuple[Path, ToolContext, PendingPatchStore],
) -> None:
    vault, ctx, store = env
    # Overwrite the doc with a body where "line" appears twice.
    (vault / "research" / "drafting.md").write_text("one line\ntwo line\nthree\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not unique"):
        EditOpenDocTool().run(
            {"old": "line", "new": "LINE", "reason": "z"},
            ctx,
        )
    assert store.list() == []


def test_missing_open_doc_file_raises(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "research").mkdir(parents=True)
    # Do NOT create the open_doc file.
    store = PendingPatchStore(tmp_path / ".brain" / "pending")
    ctx = ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        open_doc_path=Path("research/ghost.md"),
        retrieval=None,
        pending_store=store,
        state_db=None,
        source_thread="t.md",
        mode_name=ChatMode.DRAFT.value,
    )
    with pytest.raises(FileNotFoundError, match="not found"):
        EditOpenDocTool().run({"old": "x", "new": "y", "reason": "z"}, ctx)
    assert store.list() == []
