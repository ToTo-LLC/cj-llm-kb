"""Tests for brain_mcp.tools.base — ToolContext + helpers."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from brain_core.vault.paths import ScopeError
from brain_mcp.tools.base import (
    ToolContext,
    scope_guard_path,
    text_result,
)


def _ctx(vault_root: Path, *, allowed_domains: tuple[str, ...] = ("research",)) -> ToolContext:
    return ToolContext(
        vault_root=vault_root,
        allowed_domains=allowed_domains,
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )


def test_tool_context_frozen(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.allowed_domains = ("personal",)  # type: ignore[misc]


def test_scope_guard_path_happy(tmp_path: Path) -> None:
    (tmp_path / "research" / "notes").mkdir(parents=True)
    (tmp_path / "research" / "notes" / "foo.md").write_text("x", encoding="utf-8")
    ctx = _ctx(tmp_path)
    resolved = scope_guard_path("research/notes/foo.md", ctx)
    assert resolved == (tmp_path / "research" / "notes" / "foo.md").resolve()


def test_scope_guard_path_rejects_out_of_scope(tmp_path: Path) -> None:
    (tmp_path / "personal" / "notes").mkdir(parents=True)
    ctx = _ctx(tmp_path, allowed_domains=("research",))
    with pytest.raises(ScopeError):
        scope_guard_path("personal/notes/secret.md", ctx)


def test_scope_guard_path_rejects_absolute(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    with pytest.raises(ValueError, match="vault-relative"):
        scope_guard_path(str(tmp_path / "research" / "foo.md"), ctx)


def test_text_result_plain() -> None:
    out = text_result("hello world")
    assert len(out) == 1
    assert out[0].type == "text"
    assert out[0].text == "hello world"


def test_text_result_with_data() -> None:
    out = text_result("summary", data={"key": "value", "count": 3})
    assert len(out) == 2
    assert out[0].text == "summary"
    assert out[1].type == "text"
    parsed = json.loads(out[1].text)
    assert parsed == {"key": "value", "count": 3}
