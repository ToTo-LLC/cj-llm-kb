"""LLM-backed domain classifier. Uses the classify prompt + a confidence threshold."""

from __future__ import annotations

from dataclasses import dataclass

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
) -> ClassifyResult:
    """Classify a source by title + snippet. Returns a typed result with a user-pick flag."""
    prompt = load_prompt("classify")
    user_content = prompt.render(title=title, snippet=snippet)
    response = await llm.complete(
        LLMRequest(
            model=model,
            system=prompt.system,
            messages=[LLMMessage(role="user", content=user_content)],
            max_tokens=256,
            temperature=0.0,
        )
    )
    out = ClassifyOutput.model_validate_json(response.content)
    return ClassifyResult(
        source_type=out.source_type,
        domain=out.domain,
        confidence=out.confidence,
        needs_user_pick=out.confidence < confidence_threshold,
    )
