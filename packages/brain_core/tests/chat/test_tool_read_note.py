"""Tests for the read_note tool."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from brain_core.chat.tools.base import ToolContext
from brain_core.chat.tools.read_note import ReadNoteTool
from brain_core.vault.paths import ScopeError


@pytest.fixture
def ctx(tmp_path: Path) -> Iterator[ToolContext]:
    vault = tmp_path / "vault"
    research = vault / "research" / "notes"
    research.mkdir(parents=True)
    (research / "karpathy.md").write_text(
        "---\ntitle: Karpathy\ntags: [llm, research]\n---\nLLM wiki pattern body.\n",
        encoding="utf-8",
    )
    (vault / "personal" / "notes").mkdir(parents=True)
    (vault / "personal" / "notes" / "secret.md").write_text(
        "---\ntitle: Secret\n---\ndon't leak me",
        encoding="utf-8",
    )
    yield ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        open_doc_path=None,
        retrieval=None,
        pending_store=None,
        state_db=None,
        source_thread="t.md",
        mode_name="ask",
    )


def test_reads_in_scope_note(ctx: ToolContext) -> None:
    result = ReadNoteTool().run({"path": "research/notes/karpathy.md"}, ctx)
    assert "LLM wiki pattern body" in result.text
    assert result.data is not None
    assert result.data["frontmatter"]["title"] == "Karpathy"
    assert result.data["path"] == "research/notes/karpathy.md"


def test_out_of_scope_raises(ctx: ToolContext) -> None:
    with pytest.raises(ScopeError):
        ReadNoteTool().run({"path": "personal/notes/secret.md"}, ctx)


def test_missing_file_raises_friendly(ctx: ToolContext) -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        ReadNoteTool().run({"path": "research/notes/missing.md"}, ctx)


def test_note_without_frontmatter_falls_back(ctx: ToolContext) -> None:
    """Raw markdown (no `---` fence) must not raise — lenient fallback returns empty fm."""
    raw_body = "# Raw note\n\nNo frontmatter fence here.\n"
    (ctx.vault_root / "research" / "notes" / "raw.md").write_text(raw_body, encoding="utf-8")
    result = ReadNoteTool().run({"path": "research/notes/raw.md"}, ctx)
    assert result.data is not None
    assert result.data["frontmatter"] == {}
    assert result.data["body"] == raw_body
    assert result.text == raw_body


def test_absolute_path_rejected(ctx: ToolContext) -> None:
    absolute = (ctx.vault_root / "research" / "notes" / "karpathy.md").as_posix()
    with pytest.raises(ValueError, match="vault-relative"):
        ReadNoteTool().run({"path": absolute}, ctx)
