"""Plan 10 Task 1 — ``Config.domains`` runtime validation.

The v0.1 ``Domain = Literal["research","work","personal"]`` constraint is
replaced with a runtime-validated ``list[str]`` field. These tests pin
the six cases prescribed in ``tasks/plans/10-configurable-domains.md``
(Task 1, "Spec for the new test file") so future refactors can't
silently regress the slug rules or the ``personal``-required privacy
rail.
"""

from __future__ import annotations

import pytest
from brain_core.config.schema import PRIVACY_RAILED_SLUG, Config
from pydantic import ValidationError


def test_default_domains_is_research_work_personal() -> None:
    """A fresh Config carries the v0.1 default domain set."""
    cfg = Config()
    assert cfg.domains == ["research", "work", "personal"]
    # Privacy-rail slug constant is pinned to "personal"; if this ever
    # flips, the Settings → Domains UI must be revisited (see D5).
    assert PRIVACY_RAILED_SLUG == "personal"


def test_custom_domains_list_validates() -> None:
    """Adding a fourth, well-formed slug round-trips."""
    cfg = Config(domains=["research", "work", "personal", "hobby"])
    assert cfg.domains == ["research", "work", "personal", "hobby"]
    # active_domain default ("research") still resolves against the
    # extended set — model_validator runs after field validators.
    assert cfg.active_domain == "research"


def test_missing_personal_is_rejected() -> None:
    """D5: removing the privacy rail raises with the spec error wording."""
    with pytest.raises(ValidationError) as exc:
        Config(domains=["research", "work"])
    msg = str(exc.value)
    assert "personal is required and may not be removed" in msg
    assert "Settings → Domains" in msg or "Settings → Domains" in msg


def test_slug_starting_with_digit_is_rejected() -> None:
    """D2: leading digit fails the ``[a-z]…`` rule."""
    with pytest.raises(ValidationError) as exc:
        Config(domains=["research", "1bad", "personal"])
    assert "1bad" in str(exc.value)


def test_uppercase_slug_is_rejected() -> None:
    """D2: uppercase is rejected — we want lower-cased dir names on disk."""
    with pytest.raises(ValidationError) as exc:
        Config(domains=["research", "Work", "personal"])
    assert "Work" in str(exc.value)


def test_duplicate_slug_is_rejected() -> None:
    """D2: a slug may not appear twice in the list."""
    with pytest.raises(ValidationError) as exc:
        Config(domains=["research", "work", "personal", "research"])
    assert "research" in str(exc.value)
    # Error message names duplication explicitly so the UI can surface
    # the right hint (vs. "slug is invalid" which would mislead).
    assert "more than once" in str(exc.value) or "duplicate" in str(exc.value).lower()
