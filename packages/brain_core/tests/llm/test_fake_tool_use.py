"""FakeLLMProvider tool_use scripting."""

from __future__ import annotations

from brain_core.llm.fake import FakeLLMProvider
from brain_core.llm.types import (
    ContentBlock,
    LLMMessage,
    LLMRequest,
    TextBlock,
    ToolDef,
    ToolResultBlock,
    ToolUse,
)


async def test_queue_tool_use_non_streaming() -> None:
    fake = FakeLLMProvider()
    fake.queue_tool_use(
        tool_uses=[ToolUse(id="tu_1", name="search_vault", input={"query": "x"})],
        text="",
    )
    req = LLMRequest(
        model="m",
        messages=[LLMMessage(role="user", content="hi")],
        tools=[ToolDef(name="search_vault", description="x", input_schema={})],
    )
    resp = await fake.complete(req)
    assert resp.stop_reason == "tool_use"
    assert len(resp.tool_uses) == 1
    assert resp.tool_uses[0].name == "search_vault"
    assert resp.tool_uses[0].input == {"query": "x"}


async def test_plain_queue_still_works_for_plan02_callers() -> None:
    """Regression gate: existing Plan 02 callers use .queue(text) and read .content as str."""
    fake = FakeLLMProvider()
    fake.queue("plain summary")
    req = LLMRequest(
        model="m",
        messages=[LLMMessage(role="user", content="hi")],
    )
    resp = await fake.complete(req)
    assert resp.content == "plain summary"
    assert resp.tool_uses == []
    assert resp.stop_reason == "end_turn"


async def test_tool_result_round_trip_shape() -> None:
    fake = FakeLLMProvider()
    fake.queue("acknowledged")
    blocks: list[ContentBlock] = [ToolResultBlock(tool_use_id="tu_1", content="a.md, b.md")]
    req = LLMRequest(
        model="m",
        messages=[
            LLMMessage(role="user", content="first"),
            LLMMessage(role="assistant", content=[TextBlock(text="calling tool")]),
            LLMMessage(role="user", content=blocks),
        ],
    )
    resp = await fake.complete(req)
    assert resp.content == "acknowledged"


async def test_stream_emits_tool_use_events() -> None:
    fake = FakeLLMProvider()
    fake.queue_tool_use(
        tool_uses=[ToolUse(id="tu_1", name="search_vault", input={"query": "x"})],
    )
    req = LLMRequest(
        model="m",
        messages=[LLMMessage(role="user", content="hi")],
    )
    chunks = []
    async for chunk in fake.stream(req):
        chunks.append(chunk)
    # Expect: a tool_use_start, at least one input_delta, then a done chunk
    assert any(c.tool_use_start is not None for c in chunks)
    assert any(c.tool_use_input_delta is not None for c in chunks)
    assert chunks[-1].done
