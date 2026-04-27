"""Plan 11 Task 1 — ``Config.privacy_railed`` runtime validation.

Plan 10's privacy rail was a single hardcoded slug (``personal``). Plan
11 generalises it to an opt-in list with ``personal`` still required. The
six cases below pin the contract from the plan: defaults, slug rules,
required-personal, cross-field membership in ``domains``, and duplicate
detection. Future refactors of the validator pair (field-level slug
rules + model-level cross-field check) cannot silently regress without
flipping one of these tests red.
"""

from __future__ import annotations

import pytest
from brain_core.config.schema import PRIVACY_RAILED_SLUG, Config
from pydantic import ValidationError


def test_default_privacy_railed_is_personal_only() -> None:
    """A fresh Config rails only ``personal`` by default."""
    cfg = Config()
    assert cfg.privacy_railed == ["personal"]
    # Pin the constant so a sneaky rename here can't quietly break the
    # rail elsewhere in the code (see schema.py docstring).
    assert PRIVACY_RAILED_SLUG == "personal"


def test_extended_privacy_rail_validates_when_slug_in_domains() -> None:
    """Adding a second railed slug works as long as it's a known domain."""
    cfg = Config(
        privacy_railed=["personal", "journal"],
        domains=["research", "work", "personal", "journal"],
    )
    assert cfg.privacy_railed == ["personal", "journal"]


def test_missing_personal_in_privacy_railed_is_rejected() -> None:
    """D11: ``personal`` is mandatory in the rail and may not be removed."""
    with pytest.raises(ValidationError) as exc:
        Config(privacy_railed=["journal"], domains=["research", "work", "personal", "journal"])
    msg = str(exc.value)
    assert "personal is required in privacy_railed and may not be removed" in msg


def test_invalid_slug_in_privacy_railed_is_rejected() -> None:
    """D2: per-entry slug rules apply to ``privacy_railed`` too."""
    with pytest.raises(ValidationError) as exc:
        Config(privacy_railed=["personal", "1bad"])
    assert "1bad" in str(exc.value)


def test_railed_slug_not_in_domains_is_rejected() -> None:
    """D11 cross-field: cannot rail a slug that isn't a configured domain."""
    with pytest.raises(ValidationError) as exc:
        Config(
            privacy_railed=["personal", "ghost"],
            domains=["research", "work", "personal"],
        )
    msg = str(exc.value)
    assert "ghost" in msg
    # Error wording names the cross-field rule so the Settings UI can
    # render the right hint (vs. "slug is invalid" which would mislead).
    assert "not in domains" in msg


def test_duplicate_privacy_railed_slug_is_rejected() -> None:
    """A slug may not appear twice in the rail list."""
    with pytest.raises(ValidationError) as exc:
        Config(privacy_railed=["personal", "personal"])
    msg = str(exc.value)
    assert "personal" in msg
    assert "more than once" in msg or "duplicate" in msg.lower()
