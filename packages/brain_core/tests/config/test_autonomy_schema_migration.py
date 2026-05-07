"""Plan 16 Task 38 — per-domain autonomy schema + migration helper.

Pin tests covering:

  * :class:`AutonomyCategoryFlags` field defaults (all-False) and
    ``extra="forbid"`` rejection of unknown category keys.
  * The cross-field validator on ``Config.autonomous`` that rejects
    orphan slugs (entries keyed on a slug that isn't in
    ``Config.domains``). Mirrors the existing
    ``_check_domain_overrides_keys_in_domains`` validator (Plan 11 D8).
  * ``Config().autonomous`` defaults to an empty dict (T37 §4 D-4 lock —
    fresh installs and missing-field configs land on ``{}``; the gate
    treats missing slugs as all-False).
  * The :func:`brain_core.config.loader._migrate_legacy_autonomous` helper
    that rewrites the pre-T38 flat ``AutonomousConfig`` shape into the
    new per-domain nested shape. The helper is locked in T37 §3 with
    user sign-offs:
      * D-2 = CONSERVATIVE: ``entities=True`` is DROPPED on migration
        (NOT mapped to ``{new_files, edits}``); a ``structlog.warning``
        with event ``"legacy_autonomy_entities_dropped"`` fires so a
        future ``brain doctor`` / Settings UI surface can prompt the
        user to re-enable specific categories.
      * D-3: ``index_rewrites=True`` is renamed to ``index_entries=True``
        (1:1 by name) — no content change, just a name normalization
        toward the PatchSet member-field naming.
      * D-1 / D-4: defaults / shape choices that fall out of these
        decisions.
    The helper must be IDEMPOTENT — running it on already-nested input
    is a no-op so a hot-reload cycle doesn't corrupt the persisted
    shape.

T39 owns the gate rewrite (``should_auto_apply``) and the call-site
plumbing in ``apply_patch._resolve_config``; T40 lands the new Settings
UI panel. T38 only lands the schema shape and the migration helper.
"""

from __future__ import annotations

import pytest
from brain_core.config.loader import _migrate_legacy_autonomous
from brain_core.config.schema import AutonomyCategoryFlags, Config
from pydantic import ValidationError
from structlog.testing import capture_logs

# ---------------------------------------------------------------------------
# AutonomyCategoryFlags — defaults + extra-forbid
# ---------------------------------------------------------------------------


def test_autonomy_category_flags_defaults_all_false() -> None:
    """All five member-field / category flags default to ``False`` —
    the safe baseline that matches CLAUDE.md principle #3 (LLM writes
    are staged, never direct) until the user explicitly opts in.
    """
    flags = AutonomyCategoryFlags()
    assert flags.new_files is False
    assert flags.edits is False
    assert flags.index_entries is False
    assert flags.concepts is False
    assert flags.draft is False


def test_autonomy_category_flags_rejects_unknown_field() -> None:
    """``extra="forbid"`` mirrors every other config sub-model — a
    typo (e.g. ``new_filez``) raises at construction time instead of
    being silently dropped.
    """
    with pytest.raises(ValidationError) as exc:
        AutonomyCategoryFlags(new_filez=True)  # type: ignore[call-arg]
    assert "extra" in str(exc.value).lower() or "new_filez" in str(exc.value)


# ---------------------------------------------------------------------------
# Config.autonomous — default + cross-field validator
# ---------------------------------------------------------------------------


def test_config_autonomous_default_is_empty_dict() -> None:
    """T37 §4 D-4: fresh installs land on ``{}`` (the gate treats
    missing slugs as all-False — equivalent semantics to an explicit
    all-False entry, but smaller on-disk footprint and clearer "user
    has not touched this" UI signal).
    """
    cfg = Config()
    assert cfg.autonomous == {}


def test_config_autonomous_orphan_slug_is_rejected() -> None:
    """T37 §1 cross-field validator: every key in ``autonomous`` must
    reference a live domain. Mirrors the equivalent
    ``_check_domain_overrides_keys_in_domains`` validator (Plan 11 D8).
    Without this guard, deleting a domain would leave a stale autonomy
    entry that silently comes back if the slug is re-added.
    """
    with pytest.raises(ValidationError) as exc:
        Config(
            domains=["research", "work", "personal"],
            autonomous={"ghost": AutonomyCategoryFlags(new_files=True)},
        )
    msg = str(exc.value)
    assert "ghost" in msg
    assert "not in domains" in msg


def test_config_autonomous_known_slug_round_trips() -> None:
    """Sanity: an entry keyed on a live domain validates and round-trips
    via ``model_dump`` / ``model_validate``.
    """
    cfg = Config(
        domains=["research", "work", "personal"],
        autonomous={"research": AutonomyCategoryFlags(new_files=True, concepts=True)},
    )
    dumped = cfg.model_dump()
    rebuilt = Config.model_validate(dumped)
    assert rebuilt.autonomous["research"].new_files is True
    assert rebuilt.autonomous["research"].concepts is True
    assert rebuilt.autonomous["research"].edits is False


# ---------------------------------------------------------------------------
# _migrate_legacy_autonomous — the migration helper
# ---------------------------------------------------------------------------


def _legacy_flags(**flags: bool) -> dict[str, bool]:
    """Build a flat-shape ``AutonomousConfig`` dict with the requested
    flags overridden — every other flag stays ``False`` (the schema's
    out-of-the-box default).
    """
    base = {
        "ingest": False,
        "entities": False,
        "concepts": False,
        "index_rewrites": False,
        "draft": False,
    }
    base.update(flags)
    return base


def test_migrate_ingest_true_expands_to_new_files_and_index_entries() -> None:
    """``ingest=True`` ⇒ ``{new_files: True, index_entries: True}`` for
    every slug in ``domains``. T37 §3 mapping table — an INGEST patch
    is typically ``new_files`` + ``index_entries``, so preserving prior
    intent under the new member-field gate requires both.
    """
    raw = {
        "domains": ["research", "personal"],
        "autonomous": _legacy_flags(ingest=True),
    }
    migrated = _migrate_legacy_autonomous(raw)
    assert migrated["autonomous"] == {
        "research": {
            "new_files": True,
            "edits": False,
            "index_entries": True,
            "concepts": False,
            "draft": False,
        },
        "personal": {
            "new_files": True,
            "edits": False,
            "index_entries": True,
            "concepts": False,
            "draft": False,
        },
    }


def test_migrate_entities_true_drops_with_warning() -> None:
    """T37 §3 D-2 = CONSERVATIVE: ``entities=True`` does NOT map to
    any new flag (would silently grant edit-autonomy to a domain that
    didn't previously have it). Instead we emit a structured warning
    so a future ``brain doctor`` / UI surface can prompt the user to
    re-enable specific categories.

    The event name ``legacy_autonomy_entities_dropped`` is stable
    contract — downstream tooling may grep it.
    """
    raw = {
        "domains": ["research", "personal"],
        "autonomous": _legacy_flags(entities=True),
    }
    with capture_logs() as cap_logs:
        migrated = _migrate_legacy_autonomous(raw)
    # Every flag stays False — entities silently drops.
    for slug in ("research", "personal"):
        assert migrated["autonomous"][slug] == {
            "new_files": False,
            "edits": False,
            "index_entries": False,
            "concepts": False,
            "draft": False,
        }
    # Warning event fired with the locked event name + the domain list.
    matching = [e for e in cap_logs if e.get("event") == "legacy_autonomy_entities_dropped"]
    assert len(matching) == 1, f"expected exactly one warning event, got {cap_logs!r}"
    event = matching[0]
    assert event["log_level"] == "warning"
    assert list(event["domains"]) == ["research", "personal"]


def test_migrate_index_rewrites_renames_to_index_entries() -> None:
    """T37 §3 D-3: ``index_rewrites=True`` ⇒ ``index_entries=True`` per
    slug. The new shape's Literal must use the member-field name; the
    old category-bucket name is normalized away. No content change,
    just a name normalization.
    """
    raw = {
        "domains": ["research"],
        "autonomous": _legacy_flags(index_rewrites=True),
    }
    migrated = _migrate_legacy_autonomous(raw)
    assert migrated["autonomous"]["research"]["index_entries"] is True
    # Sanity: the unrelated flags stay False.
    assert migrated["autonomous"]["research"]["new_files"] is False
    assert migrated["autonomous"]["research"]["edits"] is False


def test_migrate_concepts_and_draft_pass_through() -> None:
    """``concepts`` and ``draft`` are 1:1 by name — they pass through
    untouched per slug.
    """
    raw = {
        "domains": ["research", "personal"],
        "autonomous": _legacy_flags(concepts=True, draft=True),
    }
    migrated = _migrate_legacy_autonomous(raw)
    for slug in ("research", "personal"):
        assert migrated["autonomous"][slug]["concepts"] is True
        assert migrated["autonomous"][slug]["draft"] is True
        # The other three flags stay False.
        assert migrated["autonomous"][slug]["new_files"] is False
        assert migrated["autonomous"][slug]["edits"] is False
        assert migrated["autonomous"][slug]["index_entries"] is False


def test_migrate_composes_multiple_true_flags() -> None:
    """Multiple True flags compose with logical OR per cell.
    ``ingest=True, concepts=True`` ⇒ ``new_files=True``,
    ``index_entries=True`` (from ingest), ``concepts=True`` (from
    concepts).
    """
    raw = {
        "domains": ["research"],
        "autonomous": _legacy_flags(ingest=True, concepts=True),
    }
    migrated = _migrate_legacy_autonomous(raw)
    assert migrated["autonomous"]["research"] == {
        "new_files": True,
        "edits": False,
        "index_entries": True,
        "concepts": True,
        "draft": False,
    }


def test_migrate_empty_dict_is_no_op() -> None:
    """An empty ``autonomous: {}`` payload passes through unchanged —
    the shape is already compatible with the new nested form (just no
    entries).
    """
    raw = {
        "domains": ["research"],
        "autonomous": {},
    }
    migrated = _migrate_legacy_autonomous(raw)
    assert migrated["autonomous"] == {}


def test_migrate_already_nested_shape_is_no_op() -> None:
    """An already-migrated ``{slug: {flag: bool, ...}}`` payload passes
    through unchanged. This is the IDEMPOTENCY contract — re-running
    the helper on its own output (the typical hot-reload case) must
    not corrupt the shape.
    """
    nested = {
        "research": {
            "new_files": True,
            "edits": False,
            "index_entries": False,
            "concepts": False,
            "draft": False,
        }
    }
    raw = {
        "domains": ["research"],
        "autonomous": nested,
    }
    migrated = _migrate_legacy_autonomous(raw)
    assert migrated["autonomous"] == nested


def test_migrate_legacy_bool_true_expands_to_all_true() -> None:
    """T37 §3 shape (3): a hypothetical ``autonomous: true`` (the spec
    brief's pre-existing-on-disk-shape narrative covers this defensive
    case even though it never shipped). ``True`` ⇒ all-True for every
    slug; the user effectively asked for "auto-apply everything".
    """
    raw = {
        "domains": ["research", "personal"],
        "autonomous": True,
    }
    migrated = _migrate_legacy_autonomous(raw)
    for slug in ("research", "personal"):
        assert migrated["autonomous"][slug] == {
            "new_files": True,
            "edits": True,
            "index_entries": True,
            "concepts": True,
            "draft": True,
        }


def test_migrate_legacy_bool_false_collapses_to_empty_dict() -> None:
    """``autonomous: false`` ⇒ ``{}`` (no entries — the gate evaluates
    every slug as all-False, which matches the user's prior intent).
    """
    raw = {
        "domains": ["research", "personal"],
        "autonomous": False,
    }
    migrated = _migrate_legacy_autonomous(raw)
    assert migrated["autonomous"] == {}


def test_migrate_missing_autonomous_key_is_no_op() -> None:
    """A config blob that lacks the ``autonomous`` key entirely (legacy
    pre-Plan-07 ``config.json``) passes through unchanged — the
    Pydantic ``Field(default_factory=dict)`` default lands at
    ``Config.model_validate`` time.
    """
    raw = {"domains": ["research"]}
    migrated = _migrate_legacy_autonomous(raw)
    assert "autonomous" not in migrated


# ---------------------------------------------------------------------------
# Round-trip: migrated raw + Config.model_validate
# ---------------------------------------------------------------------------


def test_migrate_then_construct_config_round_trips() -> None:
    """End-to-end: a flat-shape blob round-trips through the migration
    helper, lands on a real ``Config`` via ``model_validate``, and
    re-running the helper on the dumped blob is a no-op (the IDEMPOTENCY
    contract).
    """
    raw = {
        "domains": ["research", "personal"],
        "autonomous": _legacy_flags(ingest=True, draft=True),
    }
    migrated = _migrate_legacy_autonomous(raw)
    cfg = Config(**migrated)
    # Pydantic round-trip via model_dump → model_validate.
    dumped = cfg.model_dump()
    re_migrated = _migrate_legacy_autonomous(
        {"domains": list(cfg.domains), "autonomous": dumped["autonomous"]}
    )
    assert re_migrated["autonomous"] == dumped["autonomous"]
