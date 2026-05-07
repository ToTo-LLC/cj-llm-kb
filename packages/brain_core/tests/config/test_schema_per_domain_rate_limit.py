"""Plan 16 Task 30 / D27 step 1 of 3 — schema pin tests for
``Config.providers[*].rate_limit_per_domain``.

These tests pin the schema only. Enforcement (Task 31, AnthropicProvider
leaky-bucket) and Settings UI (Task 32) land separately. Cover:

  * Round-trip via JSON: construct → ``model_dump_json`` → ``model_validate_json``.
  * Defaults: ``rate_limit_per_domain`` is an empty dict; ``Config.providers``
    is an empty dict; legacy configs without ``providers`` still load
    (backward compat).
  * Validation: zero / negative ``requests_per_minute`` rejected;
    ``None`` accepted; positive accepted.
  * ``extra="forbid"`` is enforced on both the override and the parent
    ``ProviderConfig`` so typos surface at load time rather than
    silently mis-applying overrides.
  * Multi-domain composition: several domains can carry distinct
    overrides under one provider.
"""

from __future__ import annotations

import pytest
from brain_core.config.schema import Config, ProviderConfig, RateLimitOverride
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_provider_config_rate_limit_roundtrips_through_json() -> None:
    """Construct → JSON → re-parse must be byte-equal in semantics.

    The full ``Config`` round-trip is the realistic path — that's how the
    field hits ``<vault>/.brain/config.json`` on disk, so we exercise the
    whole stack rather than ``ProviderConfig`` in isolation.
    """
    cfg = Config(
        providers={
            "anthropic": ProviderConfig(
                rate_limit_per_domain={
                    "research": RateLimitOverride(requests_per_minute=60),
                }
            )
        }
    )
    blob = cfg.model_dump_json()
    parsed = Config.model_validate_json(blob)
    assert parsed.providers == cfg.providers
    assert (
        parsed.providers["anthropic"]
        .rate_limit_per_domain["research"]
        .requests_per_minute
        == 60
    )


def test_provider_config_rate_limit_roundtrips_at_submodel_level() -> None:
    """Sub-model round-trip: covers tools that serialize ``ProviderConfig``
    on its own (e.g., partial config dumps in admin tooling).
    """
    pc = ProviderConfig(
        rate_limit_per_domain={
            "work": RateLimitOverride(requests_per_minute=120),
            "research": RateLimitOverride(requests_per_minute=30),
        }
    )
    parsed = ProviderConfig.model_validate_json(pc.model_dump_json())
    assert parsed.rate_limit_per_domain == pc.rate_limit_per_domain
    # Sanity: independent caps round-trip correctly.
    assert parsed.rate_limit_per_domain["work"].requests_per_minute == 120
    assert parsed.rate_limit_per_domain["research"].requests_per_minute == 30


def test_rate_limit_override_roundtrips_through_json() -> None:
    """Leaf-model round-trip: ensures the override (the smallest unit
    the UI mutates in T32) serializes cleanly on its own.
    """
    ov = RateLimitOverride(requests_per_minute=42)
    parsed = RateLimitOverride.model_validate_json(ov.model_dump_json())
    assert parsed.requests_per_minute == 42


# ---------------------------------------------------------------------------
# Defaults / backward compat
# ---------------------------------------------------------------------------


def test_provider_config_default_rate_limit_per_domain_is_empty_dict() -> None:
    """Out-of-the-box brain has no per-domain rate-limit overrides."""
    pc = ProviderConfig()
    assert pc.rate_limit_per_domain == {}


def test_config_default_providers_is_empty_dict() -> None:
    """Out-of-the-box brain has no ``providers`` overrides; the
    AnthropicProvider falls back to its built-in defaults until a user
    configures one.
    """
    cfg = Config()
    assert cfg.providers == {}


def test_legacy_config_without_providers_loads_unchanged() -> None:
    """A pre-Plan-16 ``config.json`` blob that lacks ``providers`` MUST
    still parse — adding a new field can never invalidate existing user
    configs. The loader exercises this exact path on every brain
    startup.
    """
    legacy_json = (
        '{"domains": ["research", "work", "personal"], '
        '"active_domain": "research", "autonomous_mode": false}'
    )
    cfg = Config.model_validate_json(legacy_json)
    assert cfg.providers == {}


def test_legacy_provider_config_without_rate_limit_loads_unchanged() -> None:
    """A ``ProviderConfig`` blob that omits ``rate_limit_per_domain``
    parses to an empty-dict default. Mirrors the legacy-config check at
    sub-model granularity.
    """
    pc = ProviderConfig.model_validate_json("{}")
    assert pc.rate_limit_per_domain == {}


def test_rate_limit_override_default_is_none() -> None:
    """An override with no ``requests_per_minute`` set is structurally
    valid (a no-op record); enforcement (Task 31) treats it as "no
    override" and bypasses the leaky-bucket gate.
    """
    ov = RateLimitOverride()
    assert ov.requests_per_minute is None


# ---------------------------------------------------------------------------
# Validation: requests_per_minute sign
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [0, -1, -60, -1000],
)
def test_rate_limit_override_rejects_non_positive_rpm(value: int) -> None:
    """Zero and negative ``requests_per_minute`` are rejected. Wording
    in the error message points users at ``None`` as the documented way
    to disable a limit.
    """
    with pytest.raises(ValidationError) as excinfo:
        RateLimitOverride(requests_per_minute=value)
    assert "positive" in str(excinfo.value)


@pytest.mark.parametrize(
    "value",
    [1, 30, 60, 1000, 100_000],
)
def test_rate_limit_override_accepts_positive_rpm(value: int) -> None:
    """Any strictly-positive integer is accepted regardless of
    magnitude — the leaky-bucket math (T31) handles arbitrary rates.
    """
    ov = RateLimitOverride(requests_per_minute=value)
    assert ov.requests_per_minute == value


def test_rate_limit_override_accepts_explicit_none() -> None:
    """Explicit ``None`` (vs. omitted) is the documented "disable
    limit" form — UI flows in T32 will send ``None`` when the user
    clears an existing override.
    """
    ov = RateLimitOverride(requests_per_minute=None)
    assert ov.requests_per_minute is None


# ---------------------------------------------------------------------------
# Validation: extra="forbid" + nested rejection
# ---------------------------------------------------------------------------


def test_rate_limit_override_rejects_unknown_field() -> None:
    """A typo in ``config.json`` (e.g. ``rpm`` instead of
    ``requests_per_minute``) must fail loud, not silently no-op.
    """
    with pytest.raises(ValidationError):
        RateLimitOverride(rpm=60)  # type: ignore[call-arg]


def test_provider_config_rejects_unknown_field() -> None:
    """``ProviderConfig`` itself is sealed with ``extra="forbid"`` so a
    typo in the per-provider block (e.g. ``rate_limits`` instead of
    ``rate_limit_per_domain``) surfaces at load time.
    """
    with pytest.raises(ValidationError):
        ProviderConfig(rate_limits={"research": {"requests_per_minute": 60}})  # type: ignore[call-arg]


def test_provider_config_rejects_invalid_rate_limit_override() -> None:
    """Validation propagates from the nested ``RateLimitOverride`` up
    through ``ProviderConfig.rate_limit_per_domain``.
    """
    with pytest.raises(ValidationError):
        ProviderConfig(
            rate_limit_per_domain={
                "research": RateLimitOverride(requests_per_minute=-1)
            }
        )


def test_config_rejects_invalid_rate_limit_at_top_level() -> None:
    """End-to-end: validation also fires when constructing the full
    ``Config`` (the path the loader exercises in production).
    """
    with pytest.raises(ValidationError):
        Config(
            providers={
                "anthropic": ProviderConfig(
                    rate_limit_per_domain={
                        "research": RateLimitOverride(requests_per_minute=0)
                    }
                )
            }
        )


# ---------------------------------------------------------------------------
# Multi-domain
# ---------------------------------------------------------------------------


def test_provider_config_supports_multiple_domain_overrides() -> None:
    """Several domains can carry distinct rate-limit overrides
    simultaneously under one provider.
    """
    pc = ProviderConfig(
        rate_limit_per_domain={
            "research": RateLimitOverride(requests_per_minute=30),
            "work": RateLimitOverride(requests_per_minute=120),
            "personal": RateLimitOverride(requests_per_minute=10),
        }
    )
    assert set(pc.rate_limit_per_domain) == {"research", "work", "personal"}
    assert pc.rate_limit_per_domain["research"].requests_per_minute == 30
    assert pc.rate_limit_per_domain["work"].requests_per_minute == 120
    assert pc.rate_limit_per_domain["personal"].requests_per_minute == 10


def test_config_supports_multiple_providers() -> None:
    """``Config.providers`` is a map by provider name — even though
    Anthropic is the only day-one provider, the schema is shaped so
    adding a second provider (T??) doesn't require a schema migration.
    Round-tripping a multi-provider blob today is the cheapest way to
    pin that.
    """
    cfg = Config(
        providers={
            "anthropic": ProviderConfig(
                rate_limit_per_domain={
                    "research": RateLimitOverride(requests_per_minute=60)
                }
            ),
            # Placeholder name; not a Literal so this works today.
            "openai": ProviderConfig(
                rate_limit_per_domain={
                    "work": RateLimitOverride(requests_per_minute=120)
                }
            ),
        }
    )
    parsed = Config.model_validate_json(cfg.model_dump_json())
    assert set(parsed.providers) == {"anthropic", "openai"}
    assert (
        parsed.providers["anthropic"]
        .rate_limit_per_domain["research"]
        .requests_per_minute
        == 60
    )
    assert (
        parsed.providers["openai"]
        .rate_limit_per_domain["work"]
        .requests_per_minute
        == 120
    )


def test_persisted_dict_includes_providers() -> None:
    """``Config.persisted_dict()`` is what hits
    ``<vault>/.brain/config.json`` on every save — ``providers`` must
    appear there or the user's overrides won't survive a restart.
    """
    cfg = Config(
        providers={
            "anthropic": ProviderConfig(
                rate_limit_per_domain={
                    "research": RateLimitOverride(requests_per_minute=60)
                }
            )
        }
    )
    blob = cfg.persisted_dict()
    assert "providers" in blob
    assert (
        blob["providers"]["anthropic"]["rate_limit_per_domain"]["research"][
            "requests_per_minute"
        ]
        == 60
    )
