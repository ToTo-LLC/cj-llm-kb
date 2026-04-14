"""Tests for the search_vault tool."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from brain_core.chat.retrieval import BM25VaultIndex
from brain_core.chat.tools.base import ToolContext
from brain_core.chat.tools.search_vault import SearchVaultTool
from brain_core.state.db import StateDB
from brain_core.vault.paths import ScopeError


def _write_note(vault: Path, rel: str, *, title: str, body: str) -> None:
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntitle: {title}\n---\n{body}\n", encoding="utf-8")


@pytest.fixture
def env(tmp_path: Path) -> Iterator[ToolContext]:
    vault = tmp_path / "vault"
    _write_note(
        vault,
        "research/notes/llm.md",
        title="LLM Wiki",
        body="The LLM wiki pattern by Karpathy.",
    )
    _write_note(
        vault,
        "research/notes/rag.md",
        title="RAG",
        body="Retrieval augmented generation over documents.",
    )
    _write_note(
        vault,
        "research/notes/filler.md",
        title="Filler",
        body="Unrelated content about cooking recipes and gardening tips.",
    )
    _write_note(
        vault,
        "personal/notes/secret.md",
        title="Secret",
        body="personal secret about karpathy llm",
    )
    db = StateDB.open(tmp_path / ".brain" / "state.sqlite")
    retrieval = BM25VaultIndex(vault_root=vault, db=db)
    retrieval.build(("research",))
    ctx = ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        open_doc_path=None,
        retrieval=retrieval,
        pending_store=None,
        state_db=db,
        source_thread="t.md",
        mode_name="ask",
    )
    yield ctx
    db.close()


def test_returns_in_scope_hits(env: ToolContext) -> None:
    result = SearchVaultTool().run({"query": "karpathy llm"}, env)
    assert result.data is not None
    paths = [h["path"] for h in result.data["hits"]]
    assert "research/notes/llm.md" in paths
    assert not any("personal" in p for p in paths)
    assert result.text.startswith("- research/notes/llm.md")


def test_respects_top_k(env: ToolContext) -> None:
    result = SearchVaultTool().run({"query": "retrieval generation", "top_k": 1}, env)
    assert result.data is not None
    assert len(result.data["hits"]) <= 1
    assert result.data["top_k_used"] == 1


def test_top_k_capped_at_20(env: ToolContext) -> None:
    result = SearchVaultTool().run({"query": "llm", "top_k": 500}, env)
    assert result.data is not None
    assert result.data["top_k_used"] == 20


def test_out_of_scope_domain_raises(env: ToolContext) -> None:
    with pytest.raises(ScopeError):
        SearchVaultTool().run(
            {"query": "karpathy", "domains": ["personal"]},
            env,
        )


def test_empty_query_returns_empty(env: ToolContext) -> None:
    result = SearchVaultTool().run({"query": "   "}, env)
    assert result.data is not None
    assert result.data["hits"] == []
    assert "empty" in result.text.lower()
