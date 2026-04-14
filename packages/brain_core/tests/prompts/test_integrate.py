"""Tests for the integrate prompt — Task 15."""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.llm.fake import FakeLLMProvider
from brain_core.llm.types import LLMMessage, LLMRequest
from brain_core.prompts.loader import load_prompt
from brain_core.vault.types import Edit, IndexEntryPatch, NewFile, PatchSet

# ---------------------------------------------------------------------------
# Test 1: prompt loads cleanly via default search_dir (strict mode)
# ---------------------------------------------------------------------------


def test_integrate_loads_cleanly() -> None:
    """load_prompt('integrate') works without allow_unregistered_schema."""
    prompt = load_prompt("integrate")

    assert prompt.name == "integrate"
    assert prompt.output_schema_name == "IntegrateOutput"
    assert prompt.output_schema is PatchSet
    assert "{source_note}" in prompt.user_template
    assert "{index_md}" in prompt.user_template
    assert "{domain}" in prompt.user_template
    assert "{related_notes}" in prompt.user_template


# ---------------------------------------------------------------------------
# Test 2: user template renders with all placeholders
# ---------------------------------------------------------------------------


def test_integrate_renders_user_template() -> None:
    """render() substitutes all four placeholders."""
    prompt = load_prompt("integrate")

    rendered = prompt.render(
        source_note="note body",
        index_md="# index",
        domain="research",
        related_notes="none",
    )

    assert "note body" in rendered
    assert "# index" in rendered
    assert "research" in rendered
    assert "none" in rendered


# ---------------------------------------------------------------------------
# Test 3: FakeLLMProvider round-trip with PatchSet
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_integrate_fake_llm_round_trip() -> None:
    """End-to-end: queue a valid PatchSet JSON, complete, parse back."""
    prompt = load_prompt("integrate")

    # Build a valid PatchSet by hand exercising multiple fields
    patch = PatchSet(
        new_files=[
            NewFile(
                path=Path("research/notes/attention.md"),
                content="# Attention\n\nSeminal paper.",
            )
        ],
        edits=[
            Edit(
                path=Path("research/notes/transformers.md"),
                old="## See also\n",
                new="## See also\n\n- [[attention]]\n",
            )
        ],
        index_entries=[
            IndexEntryPatch(
                section="Sources",
                line="- [[attention]] — Vaswani 2017",
                domain="research",
            ),
            IndexEntryPatch(
                section="Concepts",
                line="- attention mechanism",
                domain="research",
            ),
        ],
        log_entry="add attention.md note + backlinks",
        reason="Weave new attention paper into the transformers hub.",
    )

    # Serialize and queue
    fake = FakeLLMProvider()
    fake.queue(patch.model_dump_json())

    # Build an LLMRequest with system + user message
    user_message = prompt.render(
        source_note="Attention Is All You Need — Vaswani et al. 2017.",
        index_md="# Research Index\n\n## Sources\n",
        domain="research",
        related_notes="transformers.md — Overview of transformer architectures.",
    )
    request = LLMRequest(
        model="claude-3-5-haiku-20241022",
        messages=[LLMMessage(role="user", content=user_message)],
        system=prompt.system,
    )

    # Complete
    response = await fake.complete(request)

    # Parse response and compare
    parsed = PatchSet.model_validate_json(response.content)
    assert parsed == patch

    # Verify requests log
    assert len(fake.requests) == 1
    logged = fake.requests[0]
    assert logged.system == prompt.system
