"""Tests for brain_core.chat.retrieval.BM25VaultIndex."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from brain_core.chat.retrieval import BM25VaultIndex
from brain_core.state.db import StateDB


def _write_note(vault: Path, rel: str, *, title: str, body: str) -> None:
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntitle: {title}\n---\n{body}\n", encoding="utf-8")


@pytest.fixture
def vault_with_notes(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "research").mkdir(parents=True)
    _write_note(
        vault,
        "research/notes/karpathy.md",
        title="Karpathy",
        body="Andrej Karpathy wrote about the LLM wiki pattern for personal knowledge bases.",
    )
    _write_note(
        vault,
        "research/notes/rag.md",
        title="Retrieval",
        body="Retrieval-augmented generation uses vector embeddings over raw documents.",
    )
    _write_note(
        vault,
        "research/index.md",
        title="research index",
        body="- [[karpathy]]\n- [[rag]]",
    )
    # This chat thread MUST be excluded from the index.
    _write_note(
        vault,
        "research/chats/2026-04-14-old-thread.md",
        title="old chat",
        body="karpathy karpathy karpathy karpathy karpathy",
    )
    return vault


@pytest.fixture
def db(tmp_path: Path) -> Iterator[StateDB]:
    d = StateDB.open(tmp_path / ".brain" / "state.sqlite")
    yield d
    d.close()


class TestBuildAndSearch:
    def test_build_then_search_returns_relevant_hit(
        self, vault_with_notes: Path, db: StateDB
    ) -> None:
        idx = BM25VaultIndex(vault_root=vault_with_notes, db=db)
        idx.build(("research",))
        hits = idx.search("karpathy llm wiki", domains=("research",), top_k=5)
        assert len(hits) >= 1
        assert hits[0].path == Path("research/notes/karpathy.md")
        assert hits[0].title == "Karpathy"
        assert hits[0].score > 0

    def test_search_excludes_chats_directory(self, vault_with_notes: Path, db: StateDB) -> None:
        idx = BM25VaultIndex(vault_root=vault_with_notes, db=db)
        idx.build(("research",))
        hits = idx.search("karpathy", domains=("research",), top_k=10)
        paths = [h.path for h in hits]
        assert Path("research/chats/2026-04-14-old-thread.md") not in paths
        assert all("chats" not in h.path.parts for h in hits)

    def test_search_returns_snippet(self, vault_with_notes: Path, db: StateDB) -> None:
        idx = BM25VaultIndex(vault_root=vault_with_notes, db=db)
        idx.build(("research",))
        hits = idx.search("karpathy", domains=("research",), top_k=1)
        assert len(hits) == 1
        assert "karpathy" in hits[0].snippet.lower()
        assert len(hits[0].snippet) <= 250


class TestCacheHit:
    def test_second_build_uses_cache(self, vault_with_notes: Path, db: StateDB) -> None:
        idx = BM25VaultIndex(vault_root=vault_with_notes, db=db)
        idx.build(("research",))
        assert idx.was_cache_hit("research") is False

        idx2 = BM25VaultIndex(vault_root=vault_with_notes, db=db)
        idx2.build(("research",))
        assert idx2.was_cache_hit("research") is True

    def test_cache_invalidated_on_file_change(self, vault_with_notes: Path, db: StateDB) -> None:
        idx = BM25VaultIndex(vault_root=vault_with_notes, db=db)
        idx.build(("research",))

        _write_note(
            vault_with_notes,
            "research/notes/new.md",
            title="New Topic",
            body="Completely new content about embeddings and transformers.",
        )

        idx2 = BM25VaultIndex(vault_root=vault_with_notes, db=db)
        idx2.build(("research",))
        assert idx2.was_cache_hit("research") is False

        hits = idx2.search("transformers embeddings", domains=("research",), top_k=5)
        assert any(h.path == Path("research/notes/new.md") for h in hits)


class TestSafety:
    def test_search_without_build_raises(self, vault_with_notes: Path, db: StateDB) -> None:
        idx = BM25VaultIndex(vault_root=vault_with_notes, db=db)
        with pytest.raises(RuntimeError, match="not built"):
            idx.search("anything", domains=("research",), top_k=5)
