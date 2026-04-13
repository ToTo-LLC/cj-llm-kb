from __future__ import annotations

import pytest
from brain_core.llm.fake import FakeLLMProvider
from brain_core.llm.types import LLMMessage, LLMRequest


@pytest.mark.asyncio
async def test_fake_returns_queued_response() -> None:
    fake = FakeLLMProvider()
    fake.queue("hello world", input_tokens=10, output_tokens=2)
    req = LLMRequest(model="claude-sonnet-4-6", messages=[LLMMessage(role="user", content="hi")])
    resp = await fake.complete(req)
    assert resp.content == "hello world"
    assert resp.usage.input_tokens == 10
    assert resp.usage.output_tokens == 2


@pytest.mark.asyncio
async def test_fake_raises_when_queue_empty() -> None:
    fake = FakeLLMProvider()
    req = LLMRequest(model="claude-sonnet-4-6", messages=[LLMMessage(role="user", content="hi")])
    with pytest.raises(RuntimeError, match="queue is empty"):
        await fake.complete(req)


@pytest.mark.asyncio
async def test_fake_records_requests() -> None:
    fake = FakeLLMProvider()
    fake.queue("x")
    req = LLMRequest(model="claude-sonnet-4-6", messages=[LLMMessage(role="user", content="q")])
    await fake.complete(req)
    assert len(fake.requests) == 1
    assert fake.requests[0].messages[0].content == "q"
