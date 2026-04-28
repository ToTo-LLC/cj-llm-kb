"""Tests for :func:`brain_core.llm.resolve_llm_config` /
:func:`brain_core.llm.resolve_autonomous_mode` (Plan 11 D8).

Covers:
  * domain=None → global config returned unchanged
  * domain not in overrides → global config returned (defensive: legacy
    slugs do NOT crash, even though Config validators already reject them)
  * full and partial overrides → field-by-field merge
  * fields on ``LLMConfig`` but NOT on ``DomainOverride`` (today:
    ``provider``) stay from the global even when an override is present
  * ``resolve_autonomous_mode`` flips both directions (True→False,
    False→True) when the override is set, otherwise falls back to global
"""

from __future__ import annotations

from typing import Any

from brain_core.config.schema import Config, DomainOverride, LLMConfig
from brain_core.llm import resolve_autonomous_mode, resolve_llm_config


def _mk_config(**kwargs: Any) -> Config:
    """Build a Config with ``domains`` already containing ``hobby`` so
    ``domain_overrides`` keyed on ``hobby`` passes the cross-field check.
    """
    kwargs.setdefault("domains", ["research", "work", "personal", "hobby"])
    return Config(**kwargs)


# ---------------------------------------------------------------------------
# resolve_llm_config
# ---------------------------------------------------------------------------


def test_domain_none_returns_global_unchanged() -> None:
    cfg = _mk_config()
    out = resolve_llm_config(cfg, None)
    # Spec allows live-ref OR copy; check field-value identity.
    assert out.classify_model == cfg.llm.classify_model
    assert out.default_model == cfg.llm.default_model
    assert out.temperature == cfg.llm.temperature
    assert out.max_output_tokens == cfg.llm.max_output_tokens
    assert out.provider == cfg.llm.provider


def test_domain_not_in_overrides_returns_global() -> None:
    """No override entry for ``research`` → global comes back."""
    cfg = _mk_config()
    out = resolve_llm_config(cfg, "research")
    assert out.classify_model == cfg.llm.classify_model
    assert out.default_model == cfg.llm.default_model


def test_unknown_domain_does_not_crash() -> None:
    """Defensive: a slug not in ``Config.domains`` (and therefore not in
    ``domain_overrides``) returns the global rather than raising. Config
    validators prevent orphan override KEYS, but the resolver must stay
    permissive for live-reload edge cases.
    """
    cfg = _mk_config()
    out = resolve_llm_config(cfg, "this-slug-does-not-exist")
    assert out.classify_model == cfg.llm.classify_model


def test_full_override_replaces_every_overridable_field() -> None:
    cfg = _mk_config(
        domain_overrides={
            "hobby": DomainOverride(
                classify_model="haiku-OVERRIDE",
                default_model="sonnet-OVERRIDE",
                temperature=0.7,
                max_output_tokens=8192,
            )
        }
    )
    out = resolve_llm_config(cfg, "hobby")
    assert out.classify_model == "haiku-OVERRIDE"
    assert out.default_model == "sonnet-OVERRIDE"
    assert out.temperature == 0.7
    assert out.max_output_tokens == 8192


def test_partial_override_only_replaces_set_fields() -> None:
    cfg = _mk_config(
        llm=LLMConfig(
            classify_model="global-haiku",
            default_model="global-sonnet",
            temperature=0.2,
            max_output_tokens=4096,
        ),
        domain_overrides={"hobby": DomainOverride(temperature=0.9)},
    )
    out = resolve_llm_config(cfg, "hobby")
    # Overridden:
    assert out.temperature == 0.9
    # Inherited from global:
    assert out.classify_model == "global-haiku"
    assert out.default_model == "global-sonnet"
    assert out.max_output_tokens == 4096


def test_provider_field_stays_from_global_even_with_override() -> None:
    """``provider`` exists on :class:`LLMConfig` but NOT on
    :class:`DomainOverride`. The merge MUST keep the global value
    regardless of what other override fields are set. Future-proofs
    against any LLMConfig field that doesn't have an override sibling.
    """
    cfg = _mk_config(
        llm=LLMConfig(provider="anthropic"),
        domain_overrides={"hobby": DomainOverride(classify_model="haiku-OVERRIDE")},
    )
    out = resolve_llm_config(cfg, "hobby")
    assert out.provider == "anthropic"
    # And the override DID land on the field that supports it:
    assert out.classify_model == "haiku-OVERRIDE"


def test_override_is_not_a_mutation_of_global() -> None:
    """Resolving with an override must not mutate the underlying global
    ``config.llm``. The merge constructs a fresh ``LLMConfig``.
    """
    cfg = _mk_config(
        llm=LLMConfig(temperature=0.2),
        domain_overrides={"hobby": DomainOverride(temperature=0.9)},
    )
    _ = resolve_llm_config(cfg, "hobby")
    assert cfg.llm.temperature == 0.2  # global untouched


# ---------------------------------------------------------------------------
# resolve_autonomous_mode
# ---------------------------------------------------------------------------


def test_autonomous_domain_none_returns_global() -> None:
    cfg_on = _mk_config(autonomous_mode=True)
    cfg_off = _mk_config(autonomous_mode=False)
    assert resolve_autonomous_mode(cfg_on, None) is True
    assert resolve_autonomous_mode(cfg_off, None) is False


def test_autonomous_domain_without_override_returns_global() -> None:
    cfg = _mk_config(autonomous_mode=True)
    assert resolve_autonomous_mode(cfg, "research") is True


def test_autonomous_override_none_falls_back_to_global() -> None:
    """An override entry exists for the slug but ``autonomous_mode`` is
    ``None`` (only other LLM fields are set) → global wins.
    """
    cfg = _mk_config(
        autonomous_mode=True,
        domain_overrides={"hobby": DomainOverride(temperature=0.9)},
    )
    assert resolve_autonomous_mode(cfg, "hobby") is True


def test_autonomous_unknown_domain_returns_global() -> None:
    cfg = _mk_config(autonomous_mode=False)
    assert resolve_autonomous_mode(cfg, "this-slug-does-not-exist") is False


# ---------------------------------------------------------------------------
# Schema divergence pin
# ---------------------------------------------------------------------------


def test_llm_config_and_domain_override_field_divergence_is_intentional() -> None:
    """The resolver's hasattr-driven merge silently drops LLMConfig fields
    not present on DomainOverride. That's intended for ``provider`` (per
    Plan 11 D12 — overriding the LLM provider per-domain is out of scope).
    Any other divergence is a sign that someone added a field to LLMConfig
    without deciding whether it should be overridable per-domain.

    If this test fails, EITHER add the new field to DomainOverride (with
    appropriate field validation) OR add it to the expected difference set
    below with a comment explaining why it's intentionally not overridable.
    """
    llm_fields = set(LLMConfig.model_fields)
    override_fields = set(DomainOverride.model_fields)

    # LLMConfig has fields DomainOverride doesn't override:
    only_on_llm_config = llm_fields - override_fields
    assert only_on_llm_config == {"provider"}, (
        f"Unexpected divergence: {only_on_llm_config - {'provider'}} on "
        "LLMConfig but not DomainOverride. Either add to DomainOverride or "
        "extend the expected set with a justification comment."
    )

    # DomainOverride has no fields LLMConfig doesn't — Plan 12 D1 dropped
    # ``autonomous_mode`` from the override (autonomy is governed by
    # :class:`AutonomousConfig` per-category flags). Any future override-only
    # field needs review: either add a corresponding field to LLMConfig or
    # extend this expected set with a justification comment.
    only_on_override = override_fields - llm_fields
    assert only_on_override == set(), (
        f"Unexpected divergence: {only_on_override} on DomainOverride but "
        "not LLMConfig. Override-only fields need explicit justification."
    )
