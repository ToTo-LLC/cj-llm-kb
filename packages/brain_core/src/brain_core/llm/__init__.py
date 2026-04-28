"""brain_core.llm — LLM provider abstraction, types, and per-domain resolvers.

Plan 11 Task 5 adds the per-domain override resolution seam (D8). All
LLM-routing consumers in brain_core MUST pass through
:func:`resolve_llm_config` rather than reading ``config.llm.*`` directly,
so any future override field (provider routing, per-domain temperature,
etc.) lands in one place. Same pattern for autonomy-mode lookups:
:func:`resolve_autonomous_mode` is the single seam.

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


def resolve_autonomous_mode(config: Config, domain: str | None) -> bool:
    """Resolve the effective ``autonomous_mode`` flag for ``domain``.

    Same merge rule as :func:`resolve_llm_config`: override wins when
    set, else fall back to ``config.autonomous_mode``. Returns the
    global when ``domain`` is ``None``, has no override entry, or has an
    override whose ``autonomous_mode`` is ``None``.

    Note: this resolver lands without a consumer in Plan 11. The
    autonomy gate at :mod:`brain_core.autonomy` reads per-category
    flags from ``config.autonomous.<category>`` (a different field), not
    the coarse ``Config.autonomous_mode`` bool. Wiring this seam into
    that gate is Plan 12+ work — landing the resolver now keeps the
    public API of :mod:`brain_core.llm` symmetric with the LLMConfig
    resolver and lets future consumers route through one entry point.
    """
    if domain is None or domain not in config.domain_overrides:
        return config.autonomous_mode
    override = config.domain_overrides[domain]
    if override.autonomous_mode is None:
        return config.autonomous_mode
    return override.autonomous_mode


__all__ = [
    "LLMMessage",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "LLMStreamChunk",
    "TokenUsage",
    "resolve_autonomous_mode",
    "resolve_llm_config",
]
