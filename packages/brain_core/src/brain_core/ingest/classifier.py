"""LLM-backed domain classifier. Uses the classify prompt + a confidence threshold."""

from __future__ import annotations

import json
from dataclasses import dataclass

from brain_core.config.schema import DEFAULT_DOMAINS
from brain_core.llm.provider import LLMProvider
from brain_core.llm.types import LLMMessage, LLMRequest
from brain_core.prompts.loader import load_prompt
from brain_core.prompts.schemas import ClassifyOutput


@dataclass(frozen=True)
class ClassifyResult:
    source_type: str
    domain: str
    confidence: float
    needs_user_pick: bool


async def classify(
    *,
    llm: LLMProvider,
    model: str,
    title: str,
    snippet: str,
    confidence_threshold: float = 0.7,
    allowed_domains: tuple[str, ...] = DEFAULT_DOMAINS,
) -> ClassifyResult:
    """Classify a source by title + snippet. Returns a typed result with a user-pick flag.

    ``allowed_domains`` is the call's live domain enum (Plan 10 D6).
    The classify prompt is rendered per-call with this list (D8) and
    the response is parsed permissively — out-of-set replies don't
    raise; the post-parse check below flips ``needs_user_pick`` so
    the caller can route to a manual user-pick UI or a QUARANTINED
    record (matching the v0.1 pipeline's existing
    ``if domain not in allowed_domains`` semantics in
    :class:`brain_core.ingest.pipeline.IngestPipeline.ingest`).
    Strict context-based validation is still available to direct
    callers via ``ClassifyOutput.model_validate(payload, context={...})``
    — see ``brain_core.prompts.schemas.ClassifyOutput`` for the
    contract.

    The default falls back to ``DEFAULT_DOMAINS`` so legacy call sites
    keep working; Plan 10 Task 4 wires the user's runtime
    ``Config.domains`` through the ingest pipeline so the default is
    rarely hit in practice.
    """
    prompt = load_prompt("classify")
    domains_text = ", ".join(f"`{d}`" for d in allowed_domains)
    system = prompt.render_system(domains=domains_text)
    user_content = prompt.render(title=title, snippet=snippet)
    response = await llm.complete(
        LLMRequest(
            model=model,
            system=system,
            messages=[LLMMessage(role="user", content=user_content)],
            max_tokens=256,
            temperature=0.0,
        )
    )
    # Permissive parse — the model_validator on ClassifyOutput is a
    # contract for callers that want strict context-driven rejection
    # (see Task 3). The classifier itself prefers graceful degradation
    # over raising, so it parses without context and applies the
    # in-set check explicitly below. ``json.loads`` first so a
    # non-JSON response surfaces as a parse error (handled by the
    # caller's broad except) rather than a pydantic ValidationError
    # — same behavior as v0.1 ``model_validate_json``.
    parsed = json.loads(response.content)
    out = ClassifyOutput.model_validate(parsed)
    out_of_scope = out.domain not in allowed_domains
    return ClassifyResult(
        source_type=out.source_type,
        domain=out.domain,
        confidence=out.confidence,
        # ``needs_user_pick`` flips True when EITHER the LLM was unsure
        # (confidence below threshold) OR the LLM returned a domain
        # outside the per-call enum. The caller (Plan 10 D6) treats
        # both as "ask the user" — the pipeline maps it to QUARANTINED,
        # the standalone classify tool surfaces it via the
        # ``needs_user_pick`` flag in its return data.
        needs_user_pick=out.confidence < confidence_threshold or out_of_scope,
    )
