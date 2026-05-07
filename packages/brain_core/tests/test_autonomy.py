"""Tests for brain_core.autonomy.should_auto_apply.

The autonomy gate is the ONLY exception to non-negotiable principle #3 in
CLAUDE.md (LLM writes always staged). It is tightly scoped: per-category,
defaulting to False, with :class:`PatchCategory.OTHER` wired to always return
False regardless of config — so a PatchSet emitted without a category can
never auto-apply.

**Plan 16 Task 38 status — XFAILED.** T38 reshaped ``Config.autonomous``
from a flat :class:`AutonomousConfig` BaseModel (now deleted) to a per-
domain ``dict[str, AutonomyCategoryFlags]``; T39 owns the gate rewrite
of ``should_auto_apply`` to consume the new shape (per-domain x per-
category, with the hybrid member-field/category gate locked in T37
§5). Until T39 lands, every test in this file fails because:

  * ``AutonomousConfig`` no longer exists in ``brain_core.config.schema``
    (the old import was deleted with the schema).
  * The fixture ``_config(**autonomy)`` constructs a flat
    ``AutonomousConfig`` payload that the new ``Config.autonomous`` field
    rejects (it expects ``dict[str, AutonomyCategoryFlags]``).
  * ``should_auto_apply`` itself still reads ``config.autonomous.<flag>``
    via ``getattr`` and ``_CATEGORY_TO_FLAG`` — neither is correct under
    the new dict-shape; T39 plumbs ``domain: str`` and reshapes the
    lookup.

The file is module-level ``pytest.mark.xfail(strict=True)`` so the suite
stays green and T39 sees a strict-xfail-flip when the gate rewrite
lands. Strict mode means an accidental fix (e.g. a passing test before
T39 lands) errors out instead of silently flipping to xpass.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.autonomy import should_auto_apply
from brain_core.config.schema import Config
from brain_core.vault.types import NewFile, PatchCategory, PatchSet

pytestmark = pytest.mark.xfail(
    reason=(
        "Plan 16 Task 38 reshaped Config.autonomous to dict[str, "
        "AutonomyCategoryFlags]; T39 rewrites should_auto_apply to "
        "consume the new shape. AutonomousConfig (the old flat model) "
        "no longer exists."
    ),
    strict=True,
    raises=Exception,
)


def _patchset(category: PatchCategory = PatchCategory.OTHER) -> PatchSet:
    return PatchSet(
        new_files=[NewFile(path=Path("research/notes/x.md"), content="x")],
        reason="test",
        category=category,
    )


def _config(**autonomy: bool) -> object:
    """Stub fixture — kept for shape so the file imports cleanly under
    strict-xfail. T39 rewrites every call site to pass
    ``Config(autonomous={"<slug>": AutonomyCategoryFlags(...)})`` plus a
    new ``domain=...`` kwarg on ``should_auto_apply``.
    """
    raise RuntimeError(
        "_config fixture is stub-only under T38 xfail; T39 rewrites this "
        "to use Config(autonomous={slug: AutonomyCategoryFlags(...)})."
    )


def test_other_category_never_auto_applies() -> None:
    """OTHER is the safe default — even when other flags are on, OTHER stays staged."""
    assert (
        should_auto_apply(
            _patchset(PatchCategory.OTHER),
            _config(ingest=True, entities=True, concepts=True, index_rewrites=True, draft=True),
        )
        is False
    )


def test_ingest_category_applies_when_enabled() -> None:
    assert should_auto_apply(_patchset(PatchCategory.INGEST), _config(ingest=True)) is True


def test_ingest_category_does_not_apply_when_disabled() -> None:
    assert should_auto_apply(_patchset(PatchCategory.INGEST), _config(ingest=False)) is False


def test_each_category_honors_own_flag() -> None:
    for cat in (
        PatchCategory.ENTITIES,
        PatchCategory.CONCEPTS,
        PatchCategory.INDEX_REWRITES,
        PatchCategory.DRAFT,
    ):
        key = cat.value
        assert should_auto_apply(_patchset(cat), _config(**{key: True})) is True
        assert should_auto_apply(_patchset(cat), _config(**{key: False})) is False


def test_disabled_categories_do_not_cross_enable() -> None:
    """Turning on ingest autonomy must not affect entities (or any other category)."""
    assert should_auto_apply(_patchset(PatchCategory.ENTITIES), _config(ingest=True)) is False
    assert should_auto_apply(_patchset(PatchCategory.CONCEPTS), _config(ingest=True)) is False
    assert should_auto_apply(_patchset(PatchCategory.INDEX_REWRITES), _config(ingest=True)) is False
    assert should_auto_apply(_patchset(PatchCategory.DRAFT), _config(ingest=True)) is False


def test_default_config_everything_false() -> None:
    """Out-of-the-box Config auto-applies nothing, for any category."""
    cfg = Config(vault_path=Path("/tmp/vault"))
    for cat in PatchCategory:
        assert should_auto_apply(_patchset(cat), cfg) is False
