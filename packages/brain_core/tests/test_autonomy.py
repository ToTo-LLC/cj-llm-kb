"""Tests for brain_core.autonomy.should_auto_apply.

The autonomy gate is the ONLY exception to non-negotiable principle #3 in
CLAUDE.md (LLM writes always staged). Plan 16 Task 39 reshaped it to a
per-domain x per-category gate with the HYBRID member-field/category
algorithm locked in T37 §5:

* OTHER short-circuits to False (preserved invariant).
* Member-field flags (``new_files`` / ``edits`` / ``index_entries``)
  must be True for every populated PatchSet member field.
* Categories CONCEPTS / DRAFT additionally require their same-named
  category flag.
* Categories INGEST / ENTITIES / INDEX_REWRITES have NO category-level
  requirement — member-field flags govern alone (HYBRID D-1).
* ANY-False ⇒ stage the WHOLE patch (intersection across all required
  flags; no partial apply).
* Per-domain isolation: ``flags["work"]`` does not affect autonomy for
  ``"research"`` (and a missing-domain entry is the same as all-False).
"""

from __future__ import annotations

from pathlib import Path

from brain_core.autonomy import should_auto_apply
from brain_core.config.schema import AutonomyCategoryFlags, Config
from brain_core.vault.types import (
    Edit,
    IndexEntryPatch,
    NewFile,
    PatchCategory,
    PatchSet,
)


def _new_files_patch(category: PatchCategory) -> PatchSet:
    return PatchSet(
        new_files=[NewFile(path=Path("research/notes/x.md"), content="x")],
        reason="test",
        category=category,
    )


def _edits_patch(category: PatchCategory) -> PatchSet:
    return PatchSet(
        edits=[Edit(path=Path("research/notes/x.md"), old="a", new="b")],
        reason="test",
        category=category,
    )


def _index_entries_patch(category: PatchCategory) -> PatchSet:
    return PatchSet(
        index_entries=[
            IndexEntryPatch(section="Sources", line="- [[slug]] — sum", domain="research")
        ],
        reason="test",
        category=category,
    )


def _multi_member_patch(category: PatchCategory) -> PatchSet:
    return PatchSet(
        new_files=[NewFile(path=Path("research/notes/x.md"), content="x")],
        edits=[Edit(path=Path("research/notes/y.md"), old="a", new="b")],
        reason="test",
        category=category,
    )


def _empty_patch(category: PatchCategory) -> PatchSet:
    return PatchSet(reason="test", category=category)


def _config_with_flags(
    domain: str = "research", **overrides: bool
) -> Config:
    """Construct a Config whose ``autonomous`` map has one entry for ``domain``.

    Member-field flags (``new_files`` / ``edits`` / ``index_entries``) and
    category flags (``concepts`` / ``draft``) default to ``False``; pass
    them as kwargs to flip individual leaves.
    """
    return Config(
        vault_path=Path("/tmp/vault"),
        autonomous={domain: AutonomyCategoryFlags(**overrides)},
    )


# ----------------------------------------------------------------------
# (a) baseline — all-true autonomy + matching member fields auto-applies.
# ----------------------------------------------------------------------
def test_all_true_autonomy_auto_applies() -> None:
    """Every flag True + a matching member-field-shaped patch ⇒ auto-apply."""
    cfg = _config_with_flags(
        new_files=True,
        edits=True,
        index_entries=True,
        concepts=True,
        draft=True,
    )
    assert (
        should_auto_apply(_new_files_patch(PatchCategory.INGEST), cfg, domain="research")
        is True
    )


# ----------------------------------------------------------------------
# (b) new_files=False + patch contains new_files ⇒ stage.
# ----------------------------------------------------------------------
def test_new_files_disabled_stages_new_files_patch() -> None:
    cfg = _config_with_flags(new_files=False, edits=True, index_entries=True)
    assert (
        should_auto_apply(_new_files_patch(PatchCategory.INGEST), cfg, domain="research")
        is False
    )


# ----------------------------------------------------------------------
# (c) edits=False + edits-only patch ⇒ stage.
# ----------------------------------------------------------------------
def test_edits_disabled_stages_edits_only_patch() -> None:
    cfg = _config_with_flags(new_files=True, edits=False, index_entries=True)
    assert (
        should_auto_apply(_edits_patch(PatchCategory.INGEST), cfg, domain="research")
        is False
    )


# ----------------------------------------------------------------------
# (d) all-false ⇒ stage every patch.
# ----------------------------------------------------------------------
def test_all_false_stages_every_patch() -> None:
    cfg = _config_with_flags()  # every flag defaults to False
    for patchset in (
        _new_files_patch(PatchCategory.INGEST),
        _edits_patch(PatchCategory.ENTITIES),
        _index_entries_patch(PatchCategory.INDEX_REWRITES),
        _multi_member_patch(PatchCategory.CONCEPTS),
    ):
        assert should_auto_apply(patchset, cfg, domain="research") is False


# ----------------------------------------------------------------------
# (e) CONCEPTS + concepts=True + member-field flags True ⇒ auto-apply.
# ----------------------------------------------------------------------
def test_concepts_with_full_intersection_auto_applies() -> None:
    cfg = _config_with_flags(new_files=True, concepts=True)
    assert (
        should_auto_apply(_new_files_patch(PatchCategory.CONCEPTS), cfg, domain="research")
        is True
    )


# ----------------------------------------------------------------------
# (f) CONCEPTS + concepts=True BUT new_files=False ⇒ stage (intersection).
# ----------------------------------------------------------------------
def test_concepts_intersection_member_field_false_stages() -> None:
    cfg = _config_with_flags(new_files=False, concepts=True)
    assert (
        should_auto_apply(_new_files_patch(PatchCategory.CONCEPTS), cfg, domain="research")
        is False
    )


# ----------------------------------------------------------------------
# (g) CONCEPTS + member-field flags True BUT concepts=False ⇒ stage.
# ----------------------------------------------------------------------
def test_concepts_category_flag_false_stages() -> None:
    cfg = _config_with_flags(
        new_files=True, edits=True, index_entries=True, concepts=False
    )
    assert (
        should_auto_apply(_new_files_patch(PatchCategory.CONCEPTS), cfg, domain="research")
        is False
    )


# ----------------------------------------------------------------------
# (h) INGEST + all required member fields True ⇒ auto-apply (no
#     category-flag requirement under D-1 HYBRID).
# ----------------------------------------------------------------------
def test_ingest_no_category_flag_required_under_hybrid() -> None:
    """INGEST/ENTITIES/INDEX_REWRITES patches with member fields covered by
    flags auto-apply even though there's no ``flags.ingest`` / ``flags.entities``
    / ``flags.index_rewrites`` (those keys don't exist on AutonomyCategoryFlags
    under HYBRID — by design)."""
    cfg = _config_with_flags(new_files=True)
    assert (
        should_auto_apply(_new_files_patch(PatchCategory.INGEST), cfg, domain="research")
        is True
    )
    cfg = _config_with_flags(edits=True)
    assert (
        should_auto_apply(_edits_patch(PatchCategory.ENTITIES), cfg, domain="research")
        is True
    )
    cfg = _config_with_flags(index_entries=True)
    assert (
        should_auto_apply(
            _index_entries_patch(PatchCategory.INDEX_REWRITES),
            cfg,
            domain="research",
        )
        is True
    )


# ----------------------------------------------------------------------
# (i) INGEST missing any required member-field flag ⇒ stage.
# ----------------------------------------------------------------------
def test_ingest_member_field_false_stages() -> None:
    cfg = _config_with_flags(new_files=False)
    assert (
        should_auto_apply(_new_files_patch(PatchCategory.INGEST), cfg, domain="research")
        is False
    )


# ----------------------------------------------------------------------
# (j) Empty patchset (no member fields) with concepts=True ⇒ auto-apply
#     (concepts gate satisfied; no member fields to gate against).
# ----------------------------------------------------------------------
def test_empty_concepts_patch_auto_applies_when_concepts_true() -> None:
    cfg = _config_with_flags(concepts=True)
    assert (
        should_auto_apply(_empty_patch(PatchCategory.CONCEPTS), cfg, domain="research")
        is True
    )


# ----------------------------------------------------------------------
# (k) OTHER short-circuits to False even if every flag is True.
# ----------------------------------------------------------------------
def test_other_category_never_auto_applies() -> None:
    cfg = _config_with_flags(
        new_files=True,
        edits=True,
        index_entries=True,
        concepts=True,
        draft=True,
    )
    assert (
        should_auto_apply(_new_files_patch(PatchCategory.OTHER), cfg, domain="research")
        is False
    )


# ----------------------------------------------------------------------
# (l) Missing domain entry ⇒ stage every patch.
# ----------------------------------------------------------------------
def test_missing_domain_entry_stages() -> None:
    """Domain not in ``config.autonomous`` ⇒ all-False semantics ⇒ stage."""
    cfg = Config(vault_path=Path("/tmp/vault"))
    assert cfg.autonomous == {}
    for cat in (
        PatchCategory.INGEST,
        PatchCategory.ENTITIES,
        PatchCategory.CONCEPTS,
        PatchCategory.INDEX_REWRITES,
        PatchCategory.DRAFT,
        PatchCategory.OTHER,
    ):
        assert (
            should_auto_apply(_new_files_patch(cat), cfg, domain="research") is False
        )


def test_default_config_everything_false() -> None:
    """Out-of-the-box Config auto-applies nothing for any category."""
    cfg = Config(vault_path=Path("/tmp/vault"))
    for cat in PatchCategory:
        assert (
            should_auto_apply(_new_files_patch(cat), cfg, domain="research") is False
        )


# ----------------------------------------------------------------------
# (m) Multi-member patch with mixed flags ⇒ stage (any-False).
# ----------------------------------------------------------------------
def test_multi_member_any_false_stages() -> None:
    """A patch touching new_files AND edits requires BOTH flags True."""
    cfg = _config_with_flags(new_files=True, edits=False)
    assert (
        should_auto_apply(_multi_member_patch(PatchCategory.INGEST), cfg, domain="research")
        is False
    )
    # Flip: edits=True but new_files=False ⇒ also stages.
    cfg = _config_with_flags(new_files=False, edits=True)
    assert (
        should_auto_apply(_multi_member_patch(PatchCategory.INGEST), cfg, domain="research")
        is False
    )
    # Both True ⇒ auto-applies.
    cfg = _config_with_flags(new_files=True, edits=True)
    assert (
        should_auto_apply(_multi_member_patch(PatchCategory.INGEST), cfg, domain="research")
        is True
    )


# ----------------------------------------------------------------------
# (n) Per-domain isolation: enabling work doesn't grant autonomy to research.
# ----------------------------------------------------------------------
def test_per_domain_isolation() -> None:
    """``flags["work"]={...all True}`` does not affect ``"research"``."""
    cfg = Config(
        vault_path=Path("/tmp/vault"),
        domains=["research", "work", "personal"],
        autonomous={
            "work": AutonomyCategoryFlags(
                new_files=True, edits=True, index_entries=True, concepts=True, draft=True
            )
        },
    )
    # work auto-applies.
    assert (
        should_auto_apply(_new_files_patch(PatchCategory.INGEST), cfg, domain="work")
        is True
    )
    # research stages — no entry under that key.
    assert (
        should_auto_apply(_new_files_patch(PatchCategory.INGEST), cfg, domain="research")
        is False
    )


# ----------------------------------------------------------------------
# Bonus: DRAFT mirrors CONCEPTS for category-flag semantics.
# ----------------------------------------------------------------------
def test_draft_category_flag_required() -> None:
    """DRAFT works like CONCEPTS — needs both member-field AND draft=True."""
    # Member-field True, draft False ⇒ stage.
    cfg = _config_with_flags(new_files=True, draft=False)
    assert (
        should_auto_apply(_new_files_patch(PatchCategory.DRAFT), cfg, domain="research")
        is False
    )
    # Both True ⇒ auto-apply.
    cfg = _config_with_flags(new_files=True, draft=True)
    assert (
        should_auto_apply(_new_files_patch(PatchCategory.DRAFT), cfg, domain="research")
        is True
    )


# ----------------------------------------------------------------------
# Bonus: empty-string domain hits the missing-entry path ⇒ False.
# ----------------------------------------------------------------------
def test_empty_string_domain_stages() -> None:
    cfg = _config_with_flags("research", new_files=True, edits=True, index_entries=True)
    assert (
        should_auto_apply(_new_files_patch(PatchCategory.INGEST), cfg, domain="")
        is False
    )
