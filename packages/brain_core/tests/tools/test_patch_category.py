"""Verify tool handlers stamp the right PatchCategory on emitted PatchSets.

Currently covers the ``brain_propose_note`` path-derivation helper. The
``brain_ingest`` handler stamps ``PatchCategory.INGEST`` unconditionally;
that contract is pinned by the apply_patch auto-apply regression tests.
"""

from __future__ import annotations

from pathlib import Path

from brain_core.tools.propose_note import _category_for_path
from brain_core.vault.types import PatchCategory


def test_propose_note_entities_path() -> None:
    assert _category_for_path(Path("research/entities/person.md")) == PatchCategory.ENTITIES


def test_propose_note_concepts_path() -> None:
    assert (
        _category_for_path(Path("research/concepts/tactical-empathy.md")) == PatchCategory.CONCEPTS
    )


def test_propose_note_index_rewrites() -> None:
    assert _category_for_path(Path("research/index.md")) == PatchCategory.INDEX_REWRITES


def test_propose_note_synthesis_is_other() -> None:
    assert _category_for_path(Path("research/synthesis/foo.md")) == PatchCategory.OTHER


def test_propose_note_notes_is_other() -> None:
    assert _category_for_path(Path("research/notes/foo.md")) == PatchCategory.OTHER
