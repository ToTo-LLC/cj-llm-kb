"""Plan 11 Task 1 — ``DomainOverride`` model + ``Config.domain_overrides``.

These tests pin three contracts that everything else in Plan 11
inherits:

  * ``DomainOverride`` is all-optional with bounds matching
    :class:`LLMConfig` 1:1 (so an override can never carry a value the
    global config wouldn't accept).
  * ``Config.domain_overrides`` keys must reference live domains
    (no orphan entries for deleted slugs).
  * ``Config.persisted_dict()`` returns the D4 whitelist exactly —
    ``vault_path`` is excluded by design.
"""

from __future__ import annotations

import pytest
from brain_core.config.schema import Config, DomainOverride
from pydantic import ValidationError


def test_default_domain_overrides_is_empty() -> None:
    """A fresh Config carries no per-domain overrides."""
    cfg = Config()
    assert cfg.domain_overrides == {}


def test_domain_override_all_default_validates() -> None:
    """``DomainOverride()`` with no fields set is the "fall back to
    global for everything" case — must validate cleanly."""
    o = DomainOverride()
    assert o.classify_model is None
    assert o.default_model is None
    assert o.temperature is None
    assert o.max_output_tokens is None


def test_domain_override_temperature_above_ceiling_is_rejected() -> None:
    """Bound ``le=1.5`` mirrors :class:`LLMConfig.temperature` — anything
    higher would let an override carry a value the global config
    wouldn't accept."""
    with pytest.raises(ValidationError) as exc:
        DomainOverride(temperature=2.0)
    assert "temperature" in str(exc.value).lower()


def test_domain_override_temperature_below_floor_is_rejected() -> None:
    """Bound ``ge=0.0`` — same reasoning as the ceiling test."""
    with pytest.raises(ValidationError) as exc:
        DomainOverride(temperature=-0.1)
    assert "temperature" in str(exc.value).lower()


def test_domain_override_max_output_tokens_zero_is_rejected() -> None:
    """``gt=0`` — zero output tokens would be a silent no-op LLM call."""
    with pytest.raises(ValidationError) as exc:
        DomainOverride(max_output_tokens=0)
    assert "max_output_tokens" in str(exc.value)


def test_domain_override_extra_field_is_rejected() -> None:
    """``extra='forbid'`` — typos must fail loudly, not silently
    pollute the override blob."""
    with pytest.raises(ValidationError) as exc:
        DomainOverride(extra_field="x")  # type: ignore[call-arg]
    assert "extra" in str(exc.value).lower() or "extra_field" in str(exc.value)


def test_config_domain_overrides_for_known_slug_validates() -> None:
    """Override keyed on a domain in ``domains`` round-trips."""
    cfg = Config(
        domain_overrides={"hobby": DomainOverride(classify_model="haiku")},
        domains=["research", "work", "personal", "hobby"],
    )
    assert "hobby" in cfg.domain_overrides
    assert cfg.domain_overrides["hobby"].classify_model == "haiku"


def test_config_domain_overrides_for_unknown_slug_is_rejected() -> None:
    """D8 cross-field: every override key must reference a live domain."""
    with pytest.raises(ValidationError) as exc:
        Config(
            domain_overrides={"ghost": DomainOverride()},
            domains=["research", "work", "personal"],
        )
    msg = str(exc.value)
    assert "ghost" in msg
    assert "not in domains" in msg


def test_persisted_dict_returns_exactly_the_d4_keys() -> None:
    """D4: ``persisted_dict()`` must drop ``vault_path`` and return only
    the documented persistence whitelist. Pinning the exact key set here
    so any future field addition that's meant to be persisted is forced
    to update both the whitelist and this test together."""
    cfg = Config()
    keys = set(cfg.persisted_dict().keys())
    expected = {
        "domains",
        "active_domain",
        "autonomous_mode",
        "web_port",
        "log_llm_payloads",
        "llm",
        "budget",
        "autonomous",
        "handlers",
        "domain_overrides",
        "privacy_railed",
        "cross_domain_warning_acknowledged",
    }
    assert keys == expected
    # ``vault_path`` is the canonical excluded field — guard it
    # explicitly so an accidental whitelist edit can't quietly leak it.
    assert "vault_path" not in keys
