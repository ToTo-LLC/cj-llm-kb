"""Tests for brain_core.tools.export_thread (issue #17)."""

from __future__ import annotations

from pathlib import Path

import pytest

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.export_thread import NAME, handle


def _mk_ctx(
    vault: Path,
    *,
    allowed: tuple[str, ...] = ("research", "work"),
) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=allowed,
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )


def _seed_thread(vault: Path, domain: str, thread_id: str, body: str) -> Path:
    p = vault / domain / "chats" / f"{thread_id}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_name() -> None:
    assert NAME == "brain_export_thread"


async def test_returns_markdown_for_in_scope_thread(tmp_path: Path) -> None:
    body = "---\nmode: ask\nscope: research\n---\n\n## User\n\nhello\n"
    _seed_thread(tmp_path, "research", "t-1", body)

    result = await handle({"thread_id": "t-1"}, _mk_ctx(tmp_path))

    assert isinstance(result, ToolResult)
    assert result.data is not None
    assert result.data["thread_id"] == "t-1"
    assert result.data["path"] == "research/chats/t-1.md"
    assert result.data["domain"] == "research"
    assert result.data["markdown"] == body
    assert result.data["filename"] == "t-1.md"
    assert result.data["byte_length"] == len(body.encode("utf-8"))


async def test_searches_across_allowed_domains(tmp_path: Path) -> None:
    """Thread file lives in ``work``; allowed_domains lists research first.
    The search walks both and returns the first match."""
    body = "## User\nhi\n"
    _seed_thread(tmp_path, "work", "t-w", body)

    result = await handle(
        {"thread_id": "t-w"},
        _mk_ctx(tmp_path, allowed=("research", "work")),
    )
    assert result.data is not None
    assert result.data["domain"] == "work"
    assert result.data["path"] == "work/chats/t-w.md"


async def test_out_of_scope_thread_not_found(tmp_path: Path) -> None:
    """A thread in ``personal`` is invisible to a research-only session.

    Honors the global scope-guard rule (CLAUDE.md principle #2).
    """
    _seed_thread(tmp_path, "personal", "t-secret", "## User\n")
    with pytest.raises(FileNotFoundError, match="not found in any allowed domain"):
        await handle(
            {"thread_id": "t-secret"},
            _mk_ctx(tmp_path, allowed=("research",)),
        )


async def test_missing_thread_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await handle({"thread_id": "t-missing"}, _mk_ctx(tmp_path))


async def test_rejects_path_traversal_segments(tmp_path: Path) -> None:
    """A defensive check: thread_id must be a plain slug, never a path."""
    for evil in ["../etc/passwd", "..\\..\\foo", "research/notes/x", ".secrets"]:
        with pytest.raises(ValueError, match="must be a plain slug"):
            await handle({"thread_id": evil}, _mk_ctx(tmp_path))


async def test_rejects_empty_or_non_string_thread_id(tmp_path: Path) -> None:
    for bad in [None, "", 42]:
        with pytest.raises(ValueError, match="non-empty string"):
            await handle({"thread_id": bad}, _mk_ctx(tmp_path))
