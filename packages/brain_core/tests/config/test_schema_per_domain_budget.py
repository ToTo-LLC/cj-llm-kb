"""Plan 16 Task 26 / D26 step 1 of 4 — schema pin tests for
``BudgetConfig.per_domain``.

These tests pin the schema only. Enforcement (Task 28) and Settings UI
(Task 29) land separately. Cover:

  * Round-trip via JSON: construct → ``model_dump_json`` → ``model_validate_json``.
  * Defaults: ``per_domain`` is an empty dict; missing field on legacy
    configs still loads (backward compat).
  * Validation: zero / negative rejected; ``None`` accepted; positive
    accepted; either cap can be ``None`` independently.
  * ``extra="forbid"`` is enforced on the override sub-model so typos
    surface at load time rather than silently mis-applying overrides.
"""

from __future__ import annotations

import pytest
from brain_core.config.schema import BudgetConfig, BudgetOverride, Config
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_budget_config_per_domain_roundtrips_through_json() -> None:
    """Construct → JSON → re-parse must be byte-equal in semantics.

    The full ``Config`` round-trip is the realistic path — that's how the
    field hits ``<vault>/.brain/config.json`` on disk, so we exercise the
    whole stack rather than ``BudgetConfig`` in isolation.
    """
    cfg = Config(
        budget=BudgetConfig(
            per_domain={
                "research": BudgetOverride(monthly_cap_usd=10.0, daily_cap_usd=1.0),
            }
        )
    )
    blob = cfg.model_dump_json()
    parsed = Config.model_validate_json(blob)
    assert parsed.budget.per_domain == cfg.budget.per_domain
    assert parsed.budget.per_domain["research"].monthly_cap_usd == 10.0
    assert parsed.budget.per_domain["research"].daily_cap_usd == 1.0


def test_budget_config_per_domain_roundtrips_at_submodel_level() -> None:
    """Sub-model round-trip: covers tools that serialize ``BudgetConfig``
    on its own (e.g., partial config dumps in admin tooling).
    """
    bc = BudgetConfig(
        per_domain={
            "work": BudgetOverride(monthly_cap_usd=25.0),
            "research": BudgetOverride(daily_cap_usd=0.5),
        }
    )
    parsed = BudgetConfig.model_validate_json(bc.model_dump_json())
    assert parsed.per_domain == bc.per_domain
    # Sanity: independent caps round-trip correctly.
    assert parsed.per_domain["work"].monthly_cap_usd == 25.0
    assert parsed.per_domain["work"].daily_cap_usd is None
    assert parsed.per_domain["research"].monthly_cap_usd is None
    assert parsed.per_domain["research"].daily_cap_usd == 0.5


# ---------------------------------------------------------------------------
# Defaults / backward compat
# ---------------------------------------------------------------------------


def test_budget_config_default_per_domain_is_empty_dict() -> None:
    """Out-of-the-box brain has no per-domain overrides."""
    bc = BudgetConfig()
    assert bc.per_domain == {}


def test_legacy_config_without_per_domain_loads_unchanged() -> None:
    """A pre-Plan-16 ``config.json`` blob that lacks ``per_domain`` MUST
    still parse — adding a new field can never invalidate existing
    user configs.
    """
    legacy_json = (
        '{"daily_usd": 5.0, "monthly_usd": 80.0, "alert_threshold_pct": 80, '
        '"override_until": null, "override_delta_usd": 0.0}'
    )
    bc = BudgetConfig.model_validate_json(legacy_json)
    assert bc.per_domain == {}


def test_budget_override_defaults_are_none() -> None:
    """An override with no caps set is structurally valid (a no-op
    record); enforcement (Task 28) treats it as "no override".
    """
    ov = BudgetOverride()
    assert ov.monthly_cap_usd is None
    assert ov.daily_cap_usd is None


# ---------------------------------------------------------------------------
# Validation: cap signs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("monthly_cap_usd", 0.0),
        ("monthly_cap_usd", -1.0),
        ("monthly_cap_usd", -0.01),
        ("daily_cap_usd", 0.0),
        ("daily_cap_usd", -1.0),
        ("daily_cap_usd", -0.01),
    ],
)
def test_budget_override_rejects_non_positive_caps(
    field: str, value: float
) -> None:
    """Zero and negative caps are rejected. Wording in the error message
    points users at ``None`` as the documented way to disable a cap.
    """
    with pytest.raises(ValidationError) as excinfo:
        BudgetOverride(**{field: value})
    assert "positive" in str(excinfo.value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("monthly_cap_usd", 0.01),
        ("monthly_cap_usd", 1.0),
        ("monthly_cap_usd", 1000.0),
        ("daily_cap_usd", 0.01),
        ("daily_cap_usd", 1.0),
        ("daily_cap_usd", 1000.0),
    ],
)
def test_budget_override_accepts_positive_caps(field: str, value: float) -> None:
    """Any strictly-positive cap is accepted regardless of magnitude."""
    ov = BudgetOverride(**{field: value})
    assert getattr(ov, field) == value


def test_budget_override_accepts_none_for_both_caps() -> None:
    """Explicit ``None`` (vs. omitted) is the documented "disable cap" form."""
    ov = BudgetOverride(monthly_cap_usd=None, daily_cap_usd=None)
    assert ov.monthly_cap_usd is None
    assert ov.daily_cap_usd is None


def test_budget_override_accepts_one_cap_set_other_none() -> None:
    """The two caps are independent — setting one and leaving the other
    ``None`` is a common UI flow ("monthly cap with no daily limit").
    """
    ov_monthly = BudgetOverride(monthly_cap_usd=20.0)
    assert ov_monthly.monthly_cap_usd == 20.0
    assert ov_monthly.daily_cap_usd is None

    ov_daily = BudgetOverride(daily_cap_usd=2.0)
    assert ov_daily.monthly_cap_usd is None
    assert ov_daily.daily_cap_usd == 2.0


# ---------------------------------------------------------------------------
# Validation: extra="forbid" + nested rejection
# ---------------------------------------------------------------------------


def test_budget_override_rejects_unknown_field() -> None:
    """A typo in ``config.json`` (e.g. ``monthly_cap`` instead of
    ``monthly_cap_usd``) must fail loud, not silently no-op.
    """
    with pytest.raises(ValidationError):
        BudgetOverride(monthly_cap=10.0)  # type: ignore[call-arg]


def test_budget_config_rejects_invalid_per_domain_override() -> None:
    """Validation propagates from the nested ``BudgetOverride`` up
    through ``BudgetConfig.per_domain``.
    """
    with pytest.raises(ValidationError):
        BudgetConfig(per_domain={"research": BudgetOverride(monthly_cap_usd=-1.0)})


def test_config_rejects_invalid_per_domain_override_at_top_level() -> None:
    """End-to-end: validation also fires when constructing the full
    ``Config`` (the path the loader exercises in production).
    """
    with pytest.raises(ValidationError):
        Config(
            budget=BudgetConfig(
                per_domain={"research": BudgetOverride(daily_cap_usd=0.0)}
            )
        )


# ---------------------------------------------------------------------------
# Multi-domain
# ---------------------------------------------------------------------------


def test_budget_config_supports_multiple_domain_overrides() -> None:
    """Several domains can carry distinct overrides simultaneously."""
    bc = BudgetConfig(
        per_domain={
            "research": BudgetOverride(monthly_cap_usd=10.0, daily_cap_usd=1.0),
            "work": BudgetOverride(monthly_cap_usd=50.0),
            "personal": BudgetOverride(daily_cap_usd=0.5),
        }
    )
    assert set(bc.per_domain) == {"research", "work", "personal"}
    assert bc.per_domain["research"].monthly_cap_usd == 10.0
    assert bc.per_domain["research"].daily_cap_usd == 1.0
    assert bc.per_domain["work"].monthly_cap_usd == 50.0
    assert bc.per_domain["work"].daily_cap_usd is None
    assert bc.per_domain["personal"].monthly_cap_usd is None
    assert bc.per_domain["personal"].daily_cap_usd == 0.5
