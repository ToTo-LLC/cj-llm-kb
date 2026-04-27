"""Output schemas per prompt. Tasks 14-16 extend this module."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, ValidationInfo, model_validator

from brain_core.vault.types import PatchSet

SCHEMAS: dict[str, type[BaseModel]] = {}


class SummarizeOutput(BaseModel):
    title: str
    summary: str
    key_points: list[str]
    entities: list[str]
    concepts: list[str]
    open_questions: list[str]


class ClassifyOutput(BaseModel):
    """Plan 10 Task 3 — ``domain`` widened from a fixed Literal to ``str``.

    The runtime domain set is user-configurable (``Config.domains``), so a
    Literal can't enumerate it at type-check time. The caller passes the
    live allowed list via pydantic's ``model_validate(..., context=...)``
    hook; if present, the model_validator below pins the LLM's reply to
    that list. If absent (e.g. low-level tests, stand-alone parsing), the
    validator is permissive — the field type still rejects non-strings.
    """

    source_type: Literal["text", "url", "pdf", "email", "transcript", "tweet"]
    domain: str
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_domain_in_context(self, info: ValidationInfo) -> Self:
        # Plan 10 D6: classify prompt's enum is the call's
        # ``allowed_domains``, not the entire configured set. The caller
        # is responsible for providing the same list via
        # ``model_validate(..., context={"allowed_domains": [...]})`` so
        # the validator can pin the LLM reply to that list. If no
        # context is provided, fall back to "any string" — this keeps
        # contract tests, VCR cassettes, and direct ``ClassifyOutput(...)``
        # construction working without mandatory context plumbing.
        ctx = info.context or {}
        allowed = ctx.get("allowed_domains")
        if allowed is None:
            return self
        if self.domain not in allowed:
            raise ValueError(
                f"classify returned domain {self.domain!r}, which is not in the "
                f"allowed set for this call: {sorted(allowed)!r}. The classify "
                "prompt may have been rendered with a different domain list than "
                "the caller's allowed_domains; check the call site."
            )
        return self


class ChatAutotitleOutput(BaseModel):
    title: str
    slug: str


SCHEMAS["SummarizeOutput"] = SummarizeOutput
SCHEMAS["IntegrateOutput"] = PatchSet
SCHEMAS["ClassifyOutput"] = ClassifyOutput
SCHEMAS["ChatAutotitleOutput"] = ChatAutotitleOutput
