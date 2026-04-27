"""Tests for the LLM-backed domain classifier — Task 16."""

from __future__ import annotations

import pytest
from brain_core.ingest.classifier import classify
from brain_core.llm.fake import FakeLLMProvider
from brain_core.prompts.loader import load_prompt
from brain_core.prompts.schemas import ClassifyOutput

# ---------------------------------------------------------------------------
# Test 1: high-confidence path — needs_user_pick is False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_high_confidence() -> None:
    """confidence=0.85 with default threshold 0.7 → needs_user_pick is False."""
    fake = FakeLLMProvider()
    output = ClassifyOutput(source_type="url", domain="research", confidence=0.85)
    fake.queue(output.model_dump_json())

    result = await classify(
        llm=fake,
        model="test-model",
        title="Attention Is All You Need",
        snippet="We propose a new simple network architecture, the Transformer.",
    )

    assert result.confidence == 0.85
    assert result.domain == "research"
    assert result.source_type == "url"
    assert result.needs_user_pick is False


# ---------------------------------------------------------------------------
# Test 2: low-confidence path — needs_user_pick is True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_low_confidence_flips_needs_user_pick() -> None:
    """confidence=0.5 with default threshold 0.7 → needs_user_pick is True."""
    fake = FakeLLMProvider()
    output = ClassifyOutput(source_type="tweet", domain="personal", confidence=0.5)
    fake.queue(output.model_dump_json())

    result = await classify(
        llm=fake,
        model="test-model",
        title="Quick tweet",
        snippet="Had a client call AND a family dinner today...",
    )

    assert result.confidence == 0.5
    assert result.needs_user_pick is True


# ---------------------------------------------------------------------------
# Test 3: custom threshold
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_custom_threshold() -> None:
    """confidence=0.75 with threshold=0.9 → needs_user_pick is True."""
    fake = FakeLLMProvider()
    output = ClassifyOutput(source_type="text", domain="work", confidence=0.75)
    fake.queue(output.model_dump_json())

    result = await classify(
        llm=fake,
        model="test-model",
        title="Q3 Roadmap",
        snippet="This quarter we will focus on delivery of the new platform.",
        confidence_threshold=0.9,
    )

    assert result.confidence == 0.75
    assert result.needs_user_pick is True


# ---------------------------------------------------------------------------
# Test 4: request shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_request_shape() -> None:
    """Verify the LLMRequest built by classify() has the expected fields.

    Plan 10 Task 3 routes the system text through ``Prompt.render_system``
    so the ``{domains}`` template variable is replaced with the call's
    ``allowed_domains``. The default fallback is the v0.1 set, so the
    rendered system MUST equal the v0.1-default render — not the raw
    template (which still contains ``{domains}`` literally).
    """
    from brain_core.config.schema import DEFAULT_DOMAINS

    fake = FakeLLMProvider()
    output = ClassifyOutput(source_type="pdf", domain="research", confidence=0.9)
    fake.queue(output.model_dump_json())

    await classify(
        llm=fake,
        model="test-model",
        title="A Survey of NLP",
        snippet="This survey covers recent advances in natural language processing.",
    )

    assert len(fake.requests) == 1
    request = fake.requests[0]

    prompt = load_prompt("classify")
    expected_domains_text = ", ".join(f"`{d}`" for d in DEFAULT_DOMAINS)
    expected_system = prompt.render_system(domains=expected_domains_text)
    assert request.system == expected_system
    assert "{domains}" not in request.system  # template was rendered
    assert request.temperature == 0.0
    assert request.max_tokens == 256
    assert request.messages[0].role == "user"
