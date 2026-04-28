"""Tests for Plan 12 Task 1 — ``Config.cross_domain_warning_acknowledged``
and the matching ``DomainOverride.autonomous_mode`` removal (D1 schema slice).

Pins three contracts that downstream Plan 12 tasks inherit:

  * ``Config.cross_domain_warning_acknowledged`` defaults ``False`` and
    is part of the persisted-field whitelist (D8 + D4).
  * ``Config(cross_domain_warning_acknowledged=True)`` round-trips
    through ``save_config`` / ``load_config`` preserving the bool — so
    Task 9's "remember the dismissal" UX has a stable persistence floor.
  * ``DomainOverride(autonomous_mode=True)`` is rejected by
    ``extra='forbid'`` after the field was removed (D1) — the
    failing-fast construction is the regression guard against anyone
    re-introducing the field without going through a spec amendment.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from brain_core.config.loader import load_config
from brain_core.config.schema import _PERSISTED_FIELDS, Config, DomainOverride
from brain_core.config.writer import save_config
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Config.cross_domain_warning_acknowledged
# ---------------------------------------------------------------------------


def test_cross_domain_ack_defaults_false() -> None:
    """Default for a fresh ``Config()`` is ``False`` — the modal fires
    the next time the D7 trigger condition matches.
    """
    cfg = Config()
    assert cfg.cross_domain_warning_acknowledged is False


def test_cross_domain_ack_true_is_accepted() -> None:
    """Setting the field to ``True`` validates; the value persists on
    the model instance.
    """
    cfg = Config(cross_domain_warning_acknowledged=True)
    assert cfg.cross_domain_warning_acknowledged is True


def test_cross_domain_ack_appears_in_persisted_dict() -> None:
    """D4: ``persisted_dict()`` must include the new field so it lands
    on disk when ``save_config`` runs.
    """
    cfg = Config(cross_domain_warning_acknowledged=True)
    blob = cfg.persisted_dict()
    assert "cross_domain_warning_acknowledged" in blob
    assert blob["cross_domain_warning_acknowledged"] is True


def test_cross_domain_ack_in_persisted_fields_frozenset() -> None:
    """Pin the module-level ``_PERSISTED_FIELDS`` whitelist so anyone
    who later removes / renames the field is forced to update the
    persistence shape in lockstep.
    """
    assert "cross_domain_warning_acknowledged" in _PERSISTED_FIELDS


# ---------------------------------------------------------------------------
# Round-trip through save_config / load_config
# ---------------------------------------------------------------------------


def test_cross_domain_ack_round_trips_through_save_and_load(tmp_path: Path) -> None:
    """End-to-end round-trip: write a Config with the ack flag set, read
    it back through ``load_config``, and assert the bool survived. Uses
    the real Plan 11 writer/loader (no mocks) — catches encoder bugs and
    drift between persisted shape and pydantic input shape.
    """
    original = Config(cross_domain_warning_acknowledged=True)
    target = save_config(original, tmp_path)

    rehydrated = load_config(config_file=target, env={}, cli_overrides={})
    assert rehydrated.cross_domain_warning_acknowledged is True


def test_cross_domain_ack_default_false_round_trips(tmp_path: Path) -> None:
    """Inverse of the above: a fresh-default ``Config`` round-trips
    preserving the ``False`` default. Catches a bug where a coercion
    layer might silently flip the bool, or where the loader's default
    fallback diverges from the writer output.
    """
    original = Config()
    target = save_config(original, tmp_path)

    rehydrated = load_config(config_file=target, env={}, cli_overrides={})
    assert rehydrated.cross_domain_warning_acknowledged is False


def test_cross_domain_ack_lands_in_on_disk_blob(tmp_path: Path) -> None:
    """The on-disk JSON contains the key (not just the rehydrated
    object). Guards against ``persisted_dict()`` regression that would
    silently drop the field from the writer's ``include`` set.
    """
    cfg = Config(cross_domain_warning_acknowledged=True)
    target = save_config(cfg, tmp_path)
    on_disk = json.loads(target.read_text(encoding="utf-8"))
    assert "cross_domain_warning_acknowledged" in on_disk
    assert on_disk["cross_domain_warning_acknowledged"] is True


# ---------------------------------------------------------------------------
# DomainOverride.autonomous_mode removal (D1)
# ---------------------------------------------------------------------------


def test_domain_override_autonomous_mode_kwarg_is_rejected() -> None:
    """D1 regression guard: ``DomainOverride.autonomous_mode`` was
    removed in Plan 12 Task 1. ``extra='forbid'`` (already present on
    the model) means passing the kwarg raises ``ValidationError``.
    Anyone re-introducing the field accidentally trips this test.
    """
    with pytest.raises(ValidationError) as exc:
        DomainOverride(autonomous_mode=True)  # type: ignore[call-arg]
    assert "autonomous_mode" in str(exc.value) or "extra" in str(exc.value).lower()


def test_domain_override_temperature_still_validates() -> None:
    """Sanity: removing ``autonomous_mode`` did not affect the other
    overridable fields. ``DomainOverride(temperature=0.5)`` is the
    canonical "an override is set" smoke check.
    """
    o = DomainOverride(temperature=0.5)
    assert o.temperature == 0.5
    assert o.classify_model is None
    assert o.default_model is None
    assert o.max_output_tokens is None


def test_domain_override_has_no_autonomous_mode_attribute() -> None:
    """Stronger than the kwarg-rejection test: the model_fields metadata
    must not list ``autonomous_mode``. Catches a hypothetical regression
    where the field is silently re-added with an alias / private name.
    """
    assert "autonomous_mode" not in DomainOverride.model_fields
