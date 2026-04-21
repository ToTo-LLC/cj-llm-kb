"""Tests for brain_core.autonomy.should_auto_apply.

The autonomy gate is the ONLY exception to non-negotiable principle #3 in
CLAUDE.md (LLM writes always staged). It is tightly scoped: per-category,
defaulting to False, with :class:`PatchCategory.OTHER` wired to always return
False regardless of config — so a PatchSet emitted without a category can
never auto-apply.
"""

from __future__ import annotations

from pathlib import Path

from brain_core.autonomy import should_auto_apply
from brain_core.config.schema import AutonomousConfig, Config
from brain_core.vault.types import NewFile, PatchCategory, PatchSet


def _patchset(category: PatchCategory = PatchCategory.OTHER) -> PatchSet:
    return PatchSet(
        new_files=[NewFile(path=Path("research/notes/x.md"), content="x")],
        reason="test",
        category=category,
    )


def _config(**autonomy: bool) -> Config:
    return Config(
        vault_path=Path("/tmp/vault"),
        autonomous=AutonomousConfig(**autonomy),
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
