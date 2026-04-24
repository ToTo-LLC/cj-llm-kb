"""Tests for brain_core.tools.base — ToolContext, ToolResult, scope_guard_path."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from brain_core.tools.base import ToolContext, ToolResult, scope_guard_path
from brain_core.vault.paths import ScopeError


def _ctx(tmp_path: Path, *, allowed_domains: tuple[str, ...] = ("research",)) -> ToolContext:
    return ToolContext(
        vault_root=tmp_path,
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


def test_tool_result_frozen_with_optional_data() -> None:
    result = ToolResult(text="hello")
    assert result.text == "hello"
    assert result.data is None

    result2 = ToolResult(text="hi", data={"k": "v"})
    assert result2.data == {"k": "v"}

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.text = "mutated"  # type: ignore[misc]


def test_tool_context_frozen(tmp_path: Path) -> None:
    """``ToolContext`` is a frozen dataclass — every field is immutable once
    constructed. Previously covered in brain_mcp/tests/test_tools_base.py via
    the re-export; moved here as part of issue #39 when the re-export shim
    was deleted (ToolContext now lives only in brain_core).
    """
    ctx = _ctx(tmp_path)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.allowed_domains = ("personal",)  # type: ignore[misc]


def test_scope_guard_path_happy(tmp_path: Path) -> None:
    """Happy-path smoke for ``scope_guard_path``. Previously in
    brain_mcp/tests/test_tools_base.py via re-export; moved here with #39."""
    (tmp_path / "research" / "notes").mkdir(parents=True)
    (tmp_path / "research" / "notes" / "foo.md").write_text("x", encoding="utf-8")
    ctx = _ctx(tmp_path)
    resolved = scope_guard_path("research/notes/foo.md", ctx)
    assert resolved == (tmp_path / "research" / "notes" / "foo.md").resolve()


def test_tool_context_field_set(tmp_path: Path) -> None:
    """The field set must match the Plan 04 + Plan 09 contract — brain_mcp
    tests depend on it. ``config`` was added in issue #31 as an optional
    field (default None) so existing call sites stay source-compatible.
    """
    names = {f.name for f in dataclasses.fields(ToolContext)}
    assert names == {
        "vault_root",
        "allowed_domains",
        "retrieval",
        "pending_store",
        "state_db",
        "writer",
        "llm",
        "cost_ledger",
        "rate_limiter",
        "undo_log",
        "config",
    }


def test_scope_guard_path_rejects_absolute(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    with pytest.raises(ValueError, match="vault-relative"):
        scope_guard_path(str(tmp_path / "research" / "notes" / "x.md"), ctx)


def test_scope_guard_path_rejects_out_of_scope(tmp_path: Path) -> None:
    (tmp_path / "personal" / "notes").mkdir(parents=True)
    ctx = _ctx(tmp_path, allowed_domains=("research",))
    with pytest.raises(ScopeError):
        scope_guard_path("personal/notes/secret.md", ctx)
