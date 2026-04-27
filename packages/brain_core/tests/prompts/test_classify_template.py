"""Plan 10 Task 3 — classify prompt's templated domain enum.

These tests pin two contracts from the plan-task spec:

1. ``Prompt.render_system(domains=...)`` produces a system prompt that
   mentions every name in the call's ``allowed_domains`` and only those
   names — except for the hardcoded ``personal`` privacy-rail rule
   (D5), which the template includes regardless of whether the slug
   appears in the call's enum.

2. ``ClassifyOutput`` validation rejects a domain returned by the LLM
   that's outside the per-call ``allowed_domains`` (passed via
   pydantic's ``model_validate(..., context={...})`` hook). The error
   message is specific enough for the caller to surface in a UI.
"""

from __future__ import annotations

import pytest
from brain_core.prompts.loader import load_prompt
from brain_core.prompts.schemas import ClassifyOutput
from pydantic import ValidationError


def test_classify_system_renders_listed_domains_only() -> None:
    """``render_system(domains=...)`` puts the listed names in the enum
    and leaves no literal ``{domains}`` placeholder in the output.

    The plan-task spec asks: "classify call with
    ``domains=['research', 'hobby']`` produces a prompt that mentions
    both names and only those names." We assert both slugs appear, and
    that ``work`` (a v0.1 default that's NOT in this call) does NOT
    appear in the rendered text — except inside the privacy-rail rule
    fragment, which mentions ``personal`` regardless of the call's
    enum (D5).
    """
    prompt = load_prompt("classify")
    rendered = prompt.render_system(domains="`research`, `hobby`")

    assert "{domains}" not in rendered
    # The enum line lists each call-allowed slug as a backticked code
    # span; assert each one shows up that way (matches the renderer
    # output `research`, `hobby`).
    assert "`research`" in rendered
    assert "`hobby`" in rendered
    # ``work`` is a v0.1 default but is NOT in this call's enum. The
    # rendered system MUST not advertise it as a routing target. We
    # check the backtick form so the substring "work-like" in the
    # privacy-rail rule's example phrase ("source medium is work-like")
    # doesn't trip a false positive.
    assert "`work`" not in rendered
    # ``personal`` is allowed to appear (and in fact MUST appear) in the
    # privacy-rail rule fragment regardless of the call's enum — D5
    # makes it a hardcoded slug. We don't assert its absence here.


def test_classify_system_unrendered_template_keeps_placeholder() -> None:
    """``Prompt.system`` (the raw template) still contains ``{domains}``.

    This is a sanity check that the template variable is wired in the
    classify.md system section and only collapses when ``render_system``
    is called — proves the per-call render contract (D8).
    """
    prompt = load_prompt("classify")
    assert "{domains}" in prompt.system


def test_classify_output_accepts_domain_in_allowed_set() -> None:
    """Round-trip: a domain in ``allowed_domains`` parses cleanly."""
    payload = {"source_type": "url", "domain": "hobby", "confidence": 0.82}
    out = ClassifyOutput.model_validate(
        payload,
        context={"allowed_domains": ["research", "hobby", "personal"]},
    )
    assert out.domain == "hobby"


def test_classify_output_rejects_domain_outside_allowed_set() -> None:
    """A domain returned by the LLM that's not in the per-call
    ``allowed_domains`` raises ``ValidationError`` with a message that
    names the offending slug AND the allowed set.
    """
    payload = {"source_type": "tweet", "domain": "made-up-domain", "confidence": 0.4}
    with pytest.raises(ValidationError) as exc:
        ClassifyOutput.model_validate(
            payload,
            context={"allowed_domains": ["research", "hobby", "personal"]},
        )
    msg = str(exc.value)
    assert "made-up-domain" in msg
    # The allowed set is shown sorted in the error so callers can
    # display the list to the user without secondary formatting.
    assert "hobby" in msg
    assert "personal" in msg


def test_classify_output_permissive_without_context() -> None:
    """Without a context dict, the model_validator falls back to "any
    string" — preserves contract-test ergonomics where the caller
    doesn't have an allowed_domains list.

    This is the documented escape hatch: ``ClassifyOutput(...)``
    construction (no model_validate) and ``model_validate_json(...)``
    without context both keep working as before. Plan 10 Task 4 will
    flip the pipeline to always pass context, but the loose default
    is intentional for low-level call sites.
    """
    out = ClassifyOutput(
        source_type="pdf",
        domain="some-non-default-slug",
        confidence=0.5,
    )
    assert out.domain == "some-non-default-slug"
