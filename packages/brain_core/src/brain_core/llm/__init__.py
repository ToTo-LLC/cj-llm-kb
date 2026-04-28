"""brain_core.llm — LLM provider abstraction, types, and per-domain resolvers.

Plan 11 Task 5 adds the per-domain override resolution seam (D8). All
LLM-routing consumers in brain_core MUST pass through
:func:`resolve_llm_config` rather than reading ``config.llm.*`` directly,
so any future override field (provider routing, per-domain temperature,
etc.) lands in one place.

Plan 12 Task 2 deleted the sibling ``resolve_autonomous_mode`` resolver:
Plan 11 lesson 351 confirmed it shipped without a consumer (autonomy is
governed by per-category flags on :class:`AutonomousConfig`, not the
coarse ``Config.autonomous_mode`` bool). D1 chose DELETE over WIRE; if a
future plan needs per-domain autonomy it should reintroduce the seam
alongside its first real consumer rather than land speculative dead code.

Chicken-and-egg around classify (documented per-call site too):
``classify_model`` is a per-domain overridable field, but classification
is what *determines* the domain. Auto-detection paths (no pre-specified
domain) MUST call the resolver with ``domain=None`` so the global
``classify_model`` is used. Pre-specified-domain paths (e.g., the user
explicitly targets a domain via ``domain_override``) call with the
specified slug so the override applies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from brain_core.config.schema import LLMConfig
from brain_core.llm.provider import LLMProvider
from brain_core.llm.types import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    TokenUsage,
)

if TYPE_CHECKING:
    from brain_core.config.schema import Config


def resolve_llm_config(config: Config, domain: str | None) -> LLMConfig:
    """Resolve the effective :class:`LLMConfig` for ``domain``.

    Returns the global ``config.llm`` unchanged when ``domain`` is ``None``
    or has no entry in ``config.domain_overrides``. Otherwise builds a new
    :class:`LLMConfig` by merging field-by-field: the override wins on any
    field that is set (non-``None``) on
    ``config.domain_overrides[domain]``; every other field falls back to
    ``config.llm``.

    Fields that exist on :class:`LLMConfig` but NOT on
    :class:`brain_core.config.schema.DomainOverride` (today: ``provider``)
    cannot be overridden — they always come from the global. The
    ``hasattr`` check below handles this transparently, so adding fields
    to either schema in the future requires no resolver change.

    Defensive: if ``domain`` is some legacy / unknown slug not present in
    ``config.domain_overrides``, the resolver returns the global rather
    than raising. Validators on :class:`Config` already prevent orphan
    overrides, but the resolver is the last line of defence and stays
    permissive so live-reload edge cases don't crash callers.
    """
    if domain is None or domain not in config.domain_overrides:
        return config.llm

    override = config.domain_overrides[domain]
    # Field-by-field merge so any new ``LLMConfig`` field automatically
    # picks up the override pattern via ``model_fields`` introspection.
    merged: dict[str, Any] = config.llm.model_dump()
    for field_name in LLMConfig.model_fields:
        if hasattr(override, field_name):
            value = getattr(override, field_name)
            if value is not None:
                merged[field_name] = value
    return LLMConfig(**merged)


__all__ = [
    "LLMMessage",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "LLMStreamChunk",
    "TokenUsage",
    "resolve_llm_config",
]
