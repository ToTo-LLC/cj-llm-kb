"""Plan 22 T1 — pin tests for the 4 new frontmatter fields locked in
T0 spec §4.

Fields added:

  * ``source_path: str | None``           — absolute path, sources only
  * ``orphaned: bool = False``            — flipped True when source disappears
  * ``orphaned_at: date | None = None``   — set when ``orphaned`` flips true
  * ``watched_folder_id: str | None``     — links note → ``WatchedFolder.path``

All four are OPTIONAL per the T1 contract: existing notes that predate
Plan 22 MUST continue to parse, validate, and round-trip cleanly. T2 /
T3 / T4 consumers (re-ingest, orphan-mark, scope_guard) construct a
:class:`brain_core.vault.frontmatter.Frontmatter` from the parsed dict
on demand and read these fields through the typed class.

Plan 19 T2 / Plan 20 T1 / Plan 21 T1 pin-pattern: field-set strict
equality + per-field type + default-value pins.
"""

from __future__ import annotations

from datetime import date

import pytest
from brain_core.vault.frontmatter import (
    Frontmatter,
    FrontmatterError,
    parse_frontmatter,
    serialize_with_frontmatter,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Frontmatter — field-set pin
# ---------------------------------------------------------------------------


def test_frontmatter_field_set_includes_plan_22_fields() -> None:
    """The 4 new fields are present on :class:`Frontmatter` alongside
    the canonical pre-Plan-22 fields.

    Adding or removing a canonical frontmatter field requires touching
    this test in lockstep — silent schema drift across the spec, the
    Pydantic class, and downstream consumers is what this pin catches.
    """
    expected = {
        "title",
        "domain",
        "type",
        "created",
        "updated",
        "source_type",
        "source_url",
        "tags",
        "ingested_by",
        "content_hash",
        # Plan 22 T1 / spec §4 additions:
        "source_path",
        "orphaned",
        "orphaned_at",
        "watched_folder_id",
    }
    assert set(Frontmatter.model_fields.keys()) == expected


# ---------------------------------------------------------------------------
# Per-field type + default pins
# ---------------------------------------------------------------------------


def test_source_path_is_optional_str_defaulting_none() -> None:
    """``source_path: str | None = None`` — only set on local-file
    ingestion (watched-folder sync, bulk import, drag-drop). Absent
    for URL / paste / direct-text content.
    """
    field = Frontmatter.model_fields["source_path"]
    assert not field.is_required()
    assert field.default is None


def test_orphaned_defaults_false() -> None:
    """``orphaned: bool = False`` — the canonical "this source still
    exists on disk" state. :meth:`IngestPipeline.mark_orphaned` (T3)
    flips it to ``True``.
    """
    field = Frontmatter.model_fields["orphaned"]
    assert field.annotation is bool
    assert not field.is_required()
    assert field.default is False


def test_orphaned_at_is_optional_date_defaulting_none() -> None:
    """``orphaned_at: date | None = None`` — set when ``orphaned``
    flips true; remains ``None`` while ``orphaned`` is ``False``.
    """
    field = Frontmatter.model_fields["orphaned_at"]
    assert not field.is_required()
    assert field.default is None


def test_watched_folder_id_is_optional_str_defaulting_none() -> None:
    """``watched_folder_id: str | None = None`` — links a note back to
    :attr:`brain_core.config.schema.Config.watched_folders[*].path`.

    The id IS the absolute path — there's no separate uuid because
    ``WatchedFolder.path`` is already unique within a Config (T1's
    cross-field validator pins this).
    """
    field = Frontmatter.model_fields["watched_folder_id"]
    assert not field.is_required()
    assert field.default is None


# ---------------------------------------------------------------------------
# Backward compatibility — legacy notes still parse
# ---------------------------------------------------------------------------


def test_frontmatter_loads_legacy_note_without_new_fields() -> None:
    """A pre-Plan-22 note with no ``source_path`` / ``orphaned`` /
    ``orphaned_at`` / ``watched_folder_id`` fields MUST parse cleanly
    — the schema lock is non-breaking for existing notes.
    """
    legacy = {
        "title": "Example",
        "domain": "research",
        "type": "source",
        "created": date(2026, 1, 1),
        "updated": date(2026, 1, 1),
        "source_type": "url",
        "source_url": "https://example.com/article",
        "tags": ["llm", "kb"],
        "ingested_by": "brain v0.1",
        "content_hash": "abc123",
    }
    fm = Frontmatter.from_dict(legacy)
    # All new fields default to their documented values.
    assert fm.source_path is None
    assert fm.orphaned is False
    assert fm.orphaned_at is None
    assert fm.watched_folder_id is None
    # Existing fields preserve.
    assert fm.title == "Example"
    assert fm.source_url == "https://example.com/article"


def test_frontmatter_loads_watched_folder_note() -> None:
    """A Plan-22-era note from a watched folder carries all four new
    fields populated — the schema accepts the full canonical shape.
    """
    fm = Frontmatter.from_dict(
        {
            "title": "Watched note",
            "domain": "research",
            "type": "source",
            "source_type": "pdf",
            "source_path": "/Users/x/Documents/research/paper.pdf",
            "orphaned": False,
            "orphaned_at": None,
            "watched_folder_id": "/Users/x/Documents/research",
        }
    )
    assert fm.source_path == "/Users/x/Documents/research/paper.pdf"
    assert fm.orphaned is False
    assert fm.orphaned_at is None
    assert fm.watched_folder_id == "/Users/x/Documents/research"


def test_frontmatter_loads_orphaned_note() -> None:
    """An orphan-marked note (T3 mutation) carries ``orphaned: true``
    + ``orphaned_at: <date>``.
    """
    fm = Frontmatter.from_dict(
        {
            "title": "Lost source",
            "domain": "research",
            "type": "source",
            "source_path": "/Users/x/Documents/research/gone.pdf",
            "orphaned": True,
            "orphaned_at": date(2026, 5, 12),
            "watched_folder_id": "/Users/x/Documents/research",
        }
    )
    assert fm.orphaned is True
    assert fm.orphaned_at == date(2026, 5, 12)


# ---------------------------------------------------------------------------
# Type coercion — YAML loader returns ISO strings, schema accepts them
# ---------------------------------------------------------------------------


def test_orphaned_at_accepts_iso_string() -> None:
    """The YAML loader returns ISO date strings for unquoted scalars;
    Pydantic v2 coerces them into :class:`datetime.date` automatically.

    Pin the round-trip so a future YAML-config change can't break
    the parse path.
    """
    fm = Frontmatter.from_dict({"orphaned": True, "orphaned_at": "2026-05-12"})
    assert fm.orphaned_at == date(2026, 5, 12)


def test_orphaned_rejects_non_bool() -> None:
    """``orphaned`` is strictly a bool — Pydantic's loose coercion
    accepts truthy strings ``"true"`` / ``"false"`` for compatibility
    with YAML loaders, but a random string raises.

    Pinned so a future tightening to strict-bool surfaces here.
    """
    with pytest.raises(ValidationError):
        Frontmatter.from_dict({"orphaned": "neither"})


# ---------------------------------------------------------------------------
# parse_frontmatter / serialize_with_frontmatter — dict-level invariants
# ---------------------------------------------------------------------------


def test_parse_frontmatter_preserves_new_fields() -> None:
    """The dict-based parse path (used by every legacy call site)
    preserves the 4 new fields verbatim — no implicit drop.
    """
    raw = (
        "---\n"
        "title: Watched\n"
        "domain: research\n"
        "type: source\n"
        "source_path: /Users/x/Documents/research/paper.pdf\n"
        "orphaned: false\n"
        "watched_folder_id: /Users/x/Documents/research\n"
        "---\n"
        "\n"
        "Body.\n"
    )
    data, body = parse_frontmatter(raw)
    assert data["source_path"] == "/Users/x/Documents/research/paper.pdf"
    assert data["orphaned"] is False
    assert data["watched_folder_id"] == "/Users/x/Documents/research"
    assert body == "Body.\n"


def test_serialize_with_frontmatter_emits_new_fields() -> None:
    """``serialize_with_frontmatter`` round-trips the new fields
    cleanly — the YAML output is parseable by ``parse_frontmatter``
    and the values match.
    """
    payload = {
        "title": "Watched",
        "domain": "research",
        "type": "source",
        "source_path": "/tmp/a.pdf",
        "orphaned": True,
        "orphaned_at": date(2026, 5, 12),
        "watched_folder_id": "/tmp",
    }
    out = serialize_with_frontmatter(payload, body="Body.\n")
    data, body = parse_frontmatter(out)
    assert data["source_path"] == "/tmp/a.pdf"
    assert data["orphaned"] is True
    assert data["orphaned_at"] == date(2026, 5, 12)
    assert data["watched_folder_id"] == "/tmp"
    assert body == "Body.\n"


def test_frontmatter_error_subclass_unchanged() -> None:
    """:class:`FrontmatterError` is a ``ValueError`` subclass (preserved
    from pre-Plan-22 module shape). Downstream callers catch
    ``ValueError`` or ``FrontmatterError``; this pin guards against an
    accidental base-class change.
    """
    assert issubclass(FrontmatterError, ValueError)
