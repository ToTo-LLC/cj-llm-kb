"""Additive tool_use support on LLM types."""

from __future__ import annotations

import pytest
from brain_core.llm.types import (
    ContentBlock,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    TextBlock,
    TokenUsage,
    ToolDef,
    ToolResultBlock,
    ToolUse,
    ToolUseStart,
)
from pydantic import ValidationError


def test_request_defaults_tools_empty() -> None:
    req = LLMRequest(
        model="claude-sonnet-4-6",
        messages=[LLMMessage(role="user", content="hi")],
    )
    assert req.tools == []


def test_request_accepts_tool_defs() -> None:
    td = ToolDef(
        name="search_vault",
        description="x",
        input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
    )
    req = LLMRequest(
        model="m",
        messages=[LLMMessage(role="user", content="hi")],
        tools=[td],
    )
    assert req.tools[0].name == "search_vault"


def test_response_defaults_tool_uses_empty() -> None:
    resp = LLMResponse(
        model="m",
        content="hi",
        usage=TokenUsage(input_tokens=1, output_tokens=1),
    )
    assert resp.tool_uses == []
    assert resp.content == "hi"  # existing Plan 02 shape unchanged


def test_response_with_tool_uses() -> None:
    resp = LLMResponse(
        model="m",
        content="",
        usage=TokenUsage(input_tokens=5, output_tokens=3),
        stop_reason="tool_use",
        tool_uses=[ToolUse(id="tu_1", name="search_vault", input={"query": "x"})],
    )
    assert resp.stop_reason == "tool_use"
    assert resp.tool_uses[0].input == {"query": "x"}


def test_message_accepts_string_content_plan02_shape() -> None:
    m = LLMMessage(role="user", content="plain text")
    assert m.content == "plain text"


def test_message_accepts_content_block_list() -> None:
    blocks: list[ContentBlock] = [
        TextBlock(text="hello"),
        ToolResultBlock(tool_use_id="tu_1", content="- a.md\n- b.md"),
    ]
    m = LLMMessage(role="user", content=blocks)
    assert isinstance(m.content, list)
    assert m.content[0].kind == "text"
    assert m.content[1].kind == "tool_result"


def test_content_block_discriminator_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        LLMMessage.model_validate({"role": "user", "content": [{"kind": "nope", "x": 1}]})


def test_stream_chunk_tool_use_events() -> None:
    chunk = LLMStreamChunk(tool_use_start=ToolUseStart(id="tu_1", name="search_vault"))
    assert chunk.tool_use_start is not None
    assert chunk.tool_use_start.name == "search_vault"

    chunk2 = LLMStreamChunk(tool_use_input_delta='{"query": "x"}')
    assert chunk2.tool_use_input_delta == '{"query": "x"}'

    chunk3 = LLMStreamChunk(tool_use_stop_id="tu_1", done=False)
    assert chunk3.tool_use_stop_id == "tu_1"
