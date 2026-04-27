"""Plan 10 Task 4 — classify() routes through the per-call domain set.

These tests pin the two cases from the plan-task spec:

1. "Classify a 'fishing rod' snippet with
   ``domains=['research','work','personal','hobby']`` and a fake LLM
   that returns ``'hobby'``. Assert ``ClassifyResult.domain == 'hobby'``."

2. "Classify with an LLM that returns ``'made-up-domain'`` — assert
   ``ClassifyResult.needs_user_pick is True``."

Together they prove the prompt-render and post-parse contracts
introduced in Tasks 3 + 4: the classify prompt's enum is rendered
from the call's ``allowed_domains``, and an out-of-set reply (whether
the LLM hallucinated or the user removed a domain mid-flight) flips
``needs_user_pick`` so the caller can route to a manual user-pick
or a QUARANTINED record.
"""

from __future__ import annotations

import pytest
from brain_core.ingest.classifier import classify
from brain_core.llm.fake import FakeLLMProvider
from brain_core.prompts.schemas import ClassifyOutput


@pytest.mark.asyncio
async def test_classify_routes_to_user_added_domain() -> None:
    """A 'fishing rod' snippet with a custom 'hobby' domain in the
    call's enum routes to ``hobby`` when the LLM picks it.

    The LLM is mocked, so the test really pins:

      * ``allowed_domains`` flows into the prompt render and the LLM
        sees ``hobby`` as a valid target.
      * The classifier's post-parse in-set check passes (``hobby`` is
        in the call's allowed list), so ``needs_user_pick`` stays
        ``False`` for a high-confidence reply.
      * ``ClassifyResult.domain`` round-trips the LLM's pick.
    """
    fake = FakeLLMProvider()
    fake.queue(
        ClassifyOutput(
            source_type="text",
            domain="hobby",
            confidence=0.88,
        ).model_dump_json(),
    )

    result = await classify(
        llm=fake,
        model="test-model",
        title="My new fishing rod",
        snippet="Bought a 7-foot graphite spinning rod for trout fishing.",
        allowed_domains=("research", "work", "personal", "hobby"),
    )

    assert result.domain == "hobby"
    assert result.needs_user_pick is False
    # The prompt render must have advertised ``hobby`` to the LLM.
    sent = fake.requests[0].system
    assert sent is not None
    assert "`hobby`" in sent
    # Extra-safety check: the placeholder is fully expanded.
    assert "{domains}" not in sent


@pytest.mark.asyncio
async def test_classify_out_of_set_reply_flips_user_pick() -> None:
    """An LLM reply with a domain not in ``allowed_domains`` flips
    ``needs_user_pick`` to True without raising.

    Out-of-set replies happen when (a) the LLM hallucinates a slug,
    or (b) the user removed a domain after the request was queued
    but before the classify call landed. Either way, the classifier
    degrades gracefully — it returns the offending slug verbatim so
    the UI / pipeline can show the user what the LLM picked, and
    flips ``needs_user_pick`` so the caller routes to a user-pick UI
    (or, in the pipeline, to QUARANTINED via the existing Stage 5
    in-set check). It does NOT raise.
    """
    fake = FakeLLMProvider()
    fake.queue(
        ClassifyOutput(
            source_type="text",
            domain="made-up-domain",
            confidence=0.95,  # high-confidence so confidence threshold doesn't trip
        ).model_dump_json(),
    )

    result = await classify(
        llm=fake,
        model="test-model",
        title="Some content",
        snippet="...",
        allowed_domains=("research", "hobby", "personal"),
    )

    assert result.needs_user_pick is True
    # Domain string is preserved so the caller can show the LLM's
    # offending pick to the user instead of swallowing it silently.
    assert result.domain == "made-up-domain"


@pytest.mark.asyncio
async def test_classify_does_not_advertise_unlisted_default_domain() -> None:
    """When the call's allowed_domains EXCLUDES a v0.1 default slug
    (e.g. ``personal``), the rendered prompt must not list it as a
    routing target.

    This is the structural privacy-rail check that was previously
    impossible to enforce because the prompt had ``personal``
    hardcoded in its bullet list. Plan 10 Task 3 templated the enum;
    Task 4 wires the per-call set through. Verifying both at the
    classifier seam pins the contract end-to-end.
    """
    fake = FakeLLMProvider()
    fake.queue(
        ClassifyOutput(
            source_type="text",
            domain="research",
            confidence=0.9,
        ).model_dump_json(),
    )

    await classify(
        llm=fake,
        model="test-model",
        title="A paper",
        snippet="abstract...",
        allowed_domains=("research", "work"),  # personal excluded for this call
    )

    sent = fake.requests[0].system
    assert sent is not None  # mypy + sanity — classify always sends a system
    # ``research`` and ``work`` advertised as enum entries (backticked).
    assert "`research`" in sent
    assert "`work`" in sent
    # Template fully rendered.
    assert "{domains}" not in sent
    # ``personal`` MUST NOT appear as an enum entry. It DOES appear
    # in the privacy-rail rule fragment ("Prefer ``personal`` for
    # anything that looks like private life ...") regardless of the
    # call's enum (D5), so we narrow the check to the first paragraph
    # of the system text — that's the enum sentence in classify.md.
    first_para = sent.split("\n\n", 1)[0]
    assert "`personal`" not in first_para
