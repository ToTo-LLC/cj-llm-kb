"""Tests for the classify prompt — Task 16."""

from __future__ import annotations

import pytest
from brain_core.ingest.types import SourceType
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


# ---------------------------------------------------------------------------
# Plan 26 T1: ClassifyOutput.source_type Literal is derived from SourceType
# ---------------------------------------------------------------------------


def test_classify_output_source_type_literal_matches_source_type_enum() -> None:
    """``ClassifyOutput.source_type`` must include every ``SourceType`` value.

    Plan 24 added ``docx`` + ``pptx`` to the enum but the schema's hardcoded
    Literal lagged — any classify reply with those types failed LLM-reply
    validation. Plan 26 T1 derives the Literal from ``SourceType`` at
    module-import time. This test pins the contract: the Literal's
    ``__args__`` set MUST equal the enum's value set (order independent).
    Any future enum addition that forgets to rebuild the schema (or any
    schema-only edit that strands a value) will fail this test.
    """
    literal_args = set(ClassifyOutput.model_fields["source_type"].annotation.__args__)
    enum_values = {s.value for s in SourceType}
    assert literal_args == enum_values


def test_classify_output_accepts_docx() -> None:
    """A classify reply with ``source_type='docx'`` parses cleanly.

    Plan 24 introduced ``docx`` as a SourceType. Plan 26 T1 makes
    ``ClassifyOutput`` accept it (previously rejected by the hardcoded
    Literal). Regression pin.
    """
    out = ClassifyOutput(source_type="docx", domain="research", confidence=0.9)
    assert out.source_type == "docx"


def test_classify_output_accepts_pptx() -> None:
    """A classify reply with ``source_type='pptx'`` parses cleanly.

    Plan 24 introduced ``pptx`` as a SourceType. Plan 26 T1 regression pin.
    """
    out = ClassifyOutput(source_type="pptx", domain="research", confidence=0.9)
    assert out.source_type == "pptx"


def test_classify_prompt_advertises_all_source_types() -> None:
    """The rendered classify prompt lists every ``SourceType`` value.

    Plan 26 T1 templated the source-type enum line in classify.md. The
    rendered system text MUST advertise every member of ``SourceType``
    as a routing target, backtick-wrapped, so the LLM sees the full set
    (including ``docx`` + ``pptx`` from Plan 24). If a future enum
    addition forgets to rebuild the renderer (or vice versa), this test
    fails.
    """
    prompt = load_prompt("classify")
    source_types_text = ", ".join(f"`{s.value}`" for s in SourceType)
    rendered = prompt.render_system(
        domains="`research`, `personal`", source_types=source_types_text
    )
    for member in SourceType:
        assert f"`{member.value}`" in rendered, (
            f"SourceType member {member.value!r} missing from rendered classify prompt"
        )
    # Both placeholders fully expanded.
    assert "{domains}" not in rendered
    assert "{source_types}" not in rendered
