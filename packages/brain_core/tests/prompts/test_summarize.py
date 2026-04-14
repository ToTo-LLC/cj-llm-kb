"""Tests for the summarize prompt — Task 14."""

from __future__ import annotations

import pytest
from brain_core.llm.fake import FakeLLMProvider
from brain_core.llm.types import LLMMessage, LLMRequest
from brain_core.prompts.loader import load_prompt
from brain_core.prompts.schemas import SummarizeOutput

# ---------------------------------------------------------------------------
# Test 1: prompt loads cleanly via default search_dir (strict mode)
# ---------------------------------------------------------------------------


def test_summarize_loads_cleanly() -> None:
    """load_prompt('summarize') works without allow_unregistered_schema."""
    prompt = load_prompt("summarize")

    assert prompt.name == "summarize"
    assert "summary" in prompt.system
    assert "{title}" in prompt.user_template
    assert "{source_type}" in prompt.user_template
    assert "{body}" in prompt.user_template
    assert prompt.output_schema is SummarizeOutput


# ---------------------------------------------------------------------------
# Test 2: user template renders with extracted source fields
# ---------------------------------------------------------------------------


def test_summarize_renders_user_template() -> None:
    """render() substitutes all three placeholders."""
    prompt = load_prompt("summarize")

    rendered = prompt.render(
        title="Test Article",
        source_type="url",
        body="Hello, world.",
    )

    assert "Test Article" in rendered
    assert "url" in rendered
    assert "Hello, world." in rendered


# ---------------------------------------------------------------------------
# Test 3: FakeLLMProvider round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_fake_llm_round_trip() -> None:
    """End-to-end: queue a valid SummarizeOutput JSON, complete, parse back."""
    prompt = load_prompt("summarize")

    # Build a valid instance by hand
    expected = SummarizeOutput(
        title="Test Article",
        summary="Short sentence.",
        key_points=["a", "b", "c"],
        entities=["Alice"],
        concepts=["X"],
        open_questions=[],
    )

    # Serialize and queue
    fake = FakeLLMProvider()
    fake.queue(expected.model_dump_json())

    # Build an LLMRequest with system + user message
    user_message = prompt.render(
        title="Test Article",
        source_type="url",
        body="Hello, world.",
    )
    request = LLMRequest(
        model="claude-3-5-haiku-20241022",
        messages=[LLMMessage(role="user", content=user_message)],
        system=prompt.system,
    )

    # Complete
    response = await fake.complete(request)

    # Parse response
    parsed = SummarizeOutput.model_validate_json(response.content)
    assert parsed == expected

    # Verify requests log
    assert len(fake.requests) == 1
    logged = fake.requests[0]
    assert logged.system == prompt.system
    assert logged.messages[0].content == user_message
