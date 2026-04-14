"""Tests for brain_core.chat.modes."""

from __future__ import annotations

from typing import Any

from brain_core.chat.modes import MODES, tool_to_tooldef
from brain_core.chat.tools.base import ToolContext, ToolResult
from brain_core.chat.types import ChatMode
from brain_core.llm.types import ToolDef


def test_all_modes_present() -> None:
    assert set(MODES.keys()) == {ChatMode.ASK, ChatMode.BRAINSTORM, ChatMode.DRAFT}


def test_ask_policy() -> None:
    p = MODES[ChatMode.ASK]
    assert p.temperature == 0.2
    assert "propose_note" not in p.tool_allowlist
    assert "edit_open_doc" not in p.tool_allowlist
    assert "search_vault" in p.tool_allowlist
    assert "read_note" in p.tool_allowlist
    assert "citation" in p.prompt_text.lower() or "cite" in p.prompt_text.lower()


def test_brainstorm_adds_propose_note() -> None:
    p = MODES[ChatMode.BRAINSTORM]
    assert p.temperature == 0.8
    assert "propose_note" in p.tool_allowlist
    assert "edit_open_doc" not in p.tool_allowlist
    text = p.prompt_text.lower()
    assert "push back" in text or "alternatives" in text or "socratic" in text


def test_draft_adds_edit_open_doc() -> None:
    p = MODES[ChatMode.DRAFT]
    assert p.temperature == 0.4
    assert "propose_note" in p.tool_allowlist
    assert "edit_open_doc" in p.tool_allowlist
    assert "open document" in p.prompt_text.lower() or "open doc" in p.prompt_text.lower()


def test_tool_to_tooldef() -> None:
    class _Stub:
        name = "search_vault"
        description = "BM25 search"
        input_schema: dict[str, Any] = {  # noqa: RUF012
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }

        def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
            return ToolResult(text="")

    td = tool_to_tooldef(_Stub())
    assert isinstance(td, ToolDef)
    assert td.name == "search_vault"
    assert td.description == "BM25 search"
    assert td.input_schema == {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }


def test_prompts_are_non_trivial() -> None:
    """Every mode prompt should be substantive (>200 chars), not a placeholder stub."""
    for mode in ChatMode:
        assert len(MODES[mode].prompt_text) > 200, (
            f"mode {mode} prompt is too short — did you seed it with a real prompt?"
        )
