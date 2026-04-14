"""Tests for the list_index tool."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from brain_core.chat.tools.base import ToolContext
from brain_core.chat.tools.list_index import ListIndexTool
from brain_core.vault.paths import ScopeError


@pytest.fixture
def ctx_with_index(tmp_path: Path) -> Iterator[ToolContext]:
    vault = tmp_path / "vault"
    (vault / "research").mkdir(parents=True)
    (vault / "research" / "index.md").write_text(
        "---\ntitle: research index\n---\n# research index\n- [[karpathy]]\n- [[rag]]\n",
        encoding="utf-8",
    )
    (vault / "personal").mkdir(parents=True)
    (vault / "personal" / "index.md").write_text("---\n---\npersonal only", encoding="utf-8")
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


@pytest.fixture
def ctx_no_index(tmp_path: Path) -> Iterator[ToolContext]:
    vault = tmp_path / "vault"
    (vault / "research").mkdir(parents=True)
    # intentionally no index.md
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


def test_default_domain_uses_first_allowed(ctx_with_index: ToolContext) -> None:
    result = ListIndexTool().run({}, ctx_with_index)
    assert "karpathy" in result.text
    assert "rag" in result.text
    assert result.data is not None
    assert result.data["domain"] == "research"


def test_explicit_domain(ctx_with_index: ToolContext) -> None:
    result = ListIndexTool().run({"domain": "research"}, ctx_with_index)
    assert "karpathy" in result.text


def test_out_of_scope_domain_raises(ctx_with_index: ToolContext) -> None:
    with pytest.raises(ScopeError):
        ListIndexTool().run({"domain": "personal"}, ctx_with_index)


def test_missing_index_returns_friendly_empty(ctx_no_index: ToolContext) -> None:
    result = ListIndexTool().run({}, ctx_no_index)
    assert result.text == "(no index yet)"
    assert result.data is not None
    assert result.data["domain"] == "research"
    assert result.data["body"] == ""
