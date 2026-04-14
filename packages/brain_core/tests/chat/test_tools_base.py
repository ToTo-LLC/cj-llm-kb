"""Tests for ChatTool Protocol + ToolRegistry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from brain_core.chat.tools.base import (
    ChatTool,
    ToolContext,
    ToolRegistry,
    ToolResult,
)


class _EchoTool:
    name = "echo"
    description = "echo back the args"
    input_schema: dict[str, Any] = {  # noqa: RUF012
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        return ToolResult(text=args["text"])


def _ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(
        vault_root=tmp_path,
        allowed_domains=("research",),
        open_doc_path=None,
        retrieval=None,
        pending_store=None,
        state_db=None,
        source_thread="t.md",
        mode_name="ask",
    )


def test_echo_tool_satisfies_protocol() -> None:
    tool: ChatTool = _EchoTool()
    assert tool.name == "echo"
    assert isinstance(tool, ChatTool)  # runtime_checkable


def test_run_returns_tool_result(tmp_path: Path) -> None:
    tool = _EchoTool()
    result = tool.run({"text": "hi"}, _ctx(tmp_path))
    assert result.text == "hi"
    assert result.data is None
    assert result.proposed_patch is None


def test_register_and_get() -> None:
    reg = ToolRegistry()
    reg.register(_EchoTool())
    assert reg.get("echo").name == "echo"


def test_get_unknown_raises() -> None:
    with pytest.raises(KeyError):
        ToolRegistry().get("nope")


def test_all_returns_registration_order() -> None:
    class _A:
        name = "a"
        description = "a"
        input_schema: dict[str, Any] = {}  # noqa: RUF012

        def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
            return ToolResult(text="")

    class _B:
        name = "b"
        description = "b"
        input_schema: dict[str, Any] = {}  # noqa: RUF012

        def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
            return ToolResult(text="")

    reg = ToolRegistry()
    reg.register(_A())
    reg.register(_B())
    assert [t.name for t in reg.all()] == ["a", "b"]


def test_double_register_raises() -> None:
    reg = ToolRegistry()
    reg.register(_EchoTool())
    with pytest.raises(ValueError, match="already registered"):
        reg.register(_EchoTool())


def test_subset_filters_by_allowlist() -> None:
    class _A:
        name = "a"
        description = "a"
        input_schema: dict[str, Any] = {}  # noqa: RUF012

        def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
            return ToolResult(text="")

    class _B:
        name = "b"
        description = "b"
        input_schema: dict[str, Any] = {}  # noqa: RUF012

        def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
            return ToolResult(text="")

    reg = ToolRegistry()
    reg.register(_A())
    reg.register(_B())

    filtered = reg.subset(allowlist=("a",))
    assert [t.name for t in filtered.all()] == ["a"]

    assert reg.subset(allowlist=()).all() == []

    # Unknown names in allowlist are silently ignored.
    assert [t.name for t in reg.subset(allowlist=("a", "nonexistent")).all()] == ["a"]
