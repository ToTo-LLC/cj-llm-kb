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

    ``allowed_domains`` is the call's live domain enum (Plan 10 D6). The
    classify prompt is rendered per-call with this list (D8) and the
    LLM's response is validated against it via pydantic context. The
    default falls back to the v0.1 set so older call sites keep working
    unchanged; Plan 10 Task 4 plumbs the user's runtime ``Config.domains``
    through the ingest pipeline so the default is rarely hit in practice.
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
    # Use ``model_validate`` (with parsed json + context) instead of
    # ``model_validate_json`` so the per-call ``allowed_domains`` flows
    # into ``ClassifyOutput`` 's model_validator (Plan 10 Task 3). This
    # pins the LLM reply to the same enum the prompt advertised.
    parsed = json.loads(response.content)
    out = ClassifyOutput.model_validate(
        parsed,
        context={"allowed_domains": list(allowed_domains)},
    )
    return ClassifyResult(
        source_type=out.source_type,
        domain=out.domain,
        confidence=out.confidence,
        needs_user_pick=out.confidence < confidence_threshold,
    )
