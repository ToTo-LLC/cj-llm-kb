from __future__ import annotations

import json

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


# ---------------------------------------------------------------------------
# Plan 07 Task 25C — BRAIN_E2E_MODE backdoor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_mode_chat_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """With BRAIN_E2E_MODE=1, an empty queue returns the canned chat reply."""
    monkeypatch.setenv("BRAIN_E2E_MODE", "1")
    fake = FakeLLMProvider()
    req = LLMRequest(
        model="claude-sonnet-4-6",
        messages=[LLMMessage(role="user", content="hi")],
    )
    resp = await fake.complete(req)
    assert "Hello from FakeLLM" in resp.content
    assert resp.stop_reason == "end_turn"


@pytest.mark.asyncio
async def test_e2e_mode_classify_returns_valid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Classify-style prompts resolve to ClassifyOutput-parseable JSON."""
    monkeypatch.setenv("BRAIN_E2E_MODE", "1")
    fake = FakeLLMProvider()
    req = LLMRequest(
        model="claude-haiku-4-5",
        system="Classify the provided source into a single domain.",
        messages=[LLMMessage(role="user", content="title + snippet...")],
    )
    resp = await fake.complete(req)
    parsed = json.loads(resp.content)
    assert parsed["domain"] == "work"
    assert 0.0 <= parsed["confidence"] <= 1.0
    assert parsed["source_type"] == "text"


@pytest.mark.asyncio
async def test_e2e_mode_summarize_returns_valid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Summarize-style prompts resolve to SummarizeOutput-parseable JSON."""
    monkeypatch.setenv("BRAIN_E2E_MODE", "1")
    fake = FakeLLMProvider()
    req = LLMRequest(
        model="claude-sonnet-4-6",
        system="Summarize the following source into a structured JSON object.",
        messages=[LLMMessage(role="user", content="source body...")],
    )
    resp = await fake.complete(req)
    parsed = json.loads(resp.content)
    assert "title" in parsed
    assert "summary" in parsed
    assert isinstance(parsed["key_points"], list)


@pytest.mark.asyncio
async def test_e2e_mode_still_prefers_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    """Queued responses take precedence over the E2E canned fallback."""
    monkeypatch.setenv("BRAIN_E2E_MODE", "1")
    fake = FakeLLMProvider()
    fake.queue("exact-response")
    req = LLMRequest(
        model="claude-sonnet-4-6",
        messages=[LLMMessage(role="user", content="hi")],
    )
    resp = await fake.complete(req)
    assert resp.content == "exact-response"


@pytest.mark.asyncio
async def test_e2e_mode_off_still_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """BRAIN_E2E_MODE unset (or =0) keeps the raise-on-empty contract."""
    monkeypatch.delenv("BRAIN_E2E_MODE", raising=False)
    fake = FakeLLMProvider()
    req = LLMRequest(
        model="claude-sonnet-4-6",
        messages=[LLMMessage(role="user", content="hi")],
    )
    with pytest.raises(RuntimeError, match="queue is empty"):
        await fake.complete(req)


@pytest.mark.asyncio
async def test_e2e_mode_stream_yields_canned_deltas(monkeypatch: pytest.MonkeyPatch) -> None:
    """The stream path falls back to canned deltas + done chunk in E2E mode."""
    monkeypatch.setenv("BRAIN_E2E_MODE", "1")
    fake = FakeLLMProvider()
    req = LLMRequest(
        model="claude-sonnet-4-6",
        messages=[LLMMessage(role="user", content="hi")],
    )
    chunks = [chunk async for chunk in fake.stream(req)]
    deltas = [c.delta for c in chunks if c.delta]
    assert "".join(deltas) == "Hello from FakeLLM. (E2E mode default reply.)"
    assert chunks[-1].done is True
