"""Tests for the classify prompt — Task 16."""

from __future__ import annotations

import pytest
from brain_core.llm.fake import FakeLLMProvider
from brain_core.llm.types import LLMMessage, LLMRequest
from brain_core.prompts.loader import load_prompt
from brain_core.prompts.schemas import ClassifyOutput

# ---------------------------------------------------------------------------
# Test 1: prompt loads cleanly via default search_dir (strict mode)
# ---------------------------------------------------------------------------


def test_classify_loads_cleanly() -> None:
    """load_prompt('classify') works without allow_unregistered_schema."""
    prompt = load_prompt("classify")

    assert prompt.name == "classify"
    assert prompt.output_schema_name == "ClassifyOutput"
    assert prompt.output_schema is ClassifyOutput
    assert "{title}" in prompt.user_template
    assert "{snippet}" in prompt.user_template


# ---------------------------------------------------------------------------
# Test 2: user template renders with title + snippet
# ---------------------------------------------------------------------------


def test_classify_renders_user_template() -> None:
    """render() substitutes both placeholders."""
    prompt = load_prompt("classify")

    rendered = prompt.render(title="My Article", snippet="First paragraph here.")

    assert "My Article" in rendered
    assert "First paragraph here." in rendered


# ---------------------------------------------------------------------------
# Test 3: FakeLLMProvider round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_fake_llm_round_trip() -> None:
    """End-to-end: queue a valid ClassifyOutput JSON, complete, parse back."""
    prompt = load_prompt("classify")

    # Build a valid instance by hand
    expected = ClassifyOutput(source_type="url", domain="research", confidence=0.85)

    # Serialize and queue
    fake = FakeLLMProvider()
    fake.queue(expected.model_dump_json())

    # Build an LLMRequest with system + user message
    user_message = prompt.render(
        title="Deep Learning Paper",
        snippet="This paper introduces a novel architecture for transformers.",
    )
    request = LLMRequest(
        model="claude-3-5-haiku-20241022",
        messages=[LLMMessage(role="user", content=user_message)],
        system=prompt.system,
    )

    # Complete
    response = await fake.complete(request)

    # Parse response
    parsed = ClassifyOutput.model_validate_json(response.content)
    assert parsed == expected

    # Verify requests log
    assert len(fake.requests) == 1
    logged = fake.requests[0]
    assert logged.system == prompt.system
    assert logged.messages[0].content == user_message
