"""YAML frontmatter parse + serialize. Stable key order for diff-friendliness.

The canonical frontmatter on a vault note is a YAML mapping; the
parse/serialize functions in this module work on a plain ``dict`` for
maximum compatibility with hand-edited Obsidian notes (extra keys are
preserved, missing keys are tolerated). :class:`Frontmatter` is a
typed Pydantic schema that documents the canonical field set per
``docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md`` §4. The
serialize/parse path is intentionally NOT wired through this class so
that legacy notes lacking newer fields continue to round-trip
unchanged; downstream code that needs validated typing
(:mod:`brain_core.vault.scope_guard` orphan filter, T2
``IngestPipeline.update_source``, T3 ``IngestPipeline.mark_orphaned``)
constructs a :class:`Frontmatter` from the parsed dict on demand.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any, Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict


class FrontmatterError(ValueError):
    """Raised for any frontmatter parsing failure."""


class Frontmatter(BaseModel):
    """Typed canonical frontmatter schema for vault notes (spec §4).

    Every field is OPTIONAL with a default — this matches the spec where
    the four "sources only" / "watched-folder only" fields appear under
    conditional comments and where hand-edited Obsidian notes routinely
    omit fields that the LLM would otherwise populate. ``extra="allow"``
    keeps unknown keys around so a user-added field (e.g. ``aliases``,
    ``cssclass``) survives a parse → validate → re-serialize round-trip.

    Plan 22 T1 adds the last four fields below — they are all OPTIONAL
    so loading an existing pre-Plan-22 note never raises:

    * ``source_path`` — absolute path on disk; only set when ingestion
      came from a local file (watched-folder sync, bulk import,
      drag-drop of a file). Absent for URL / paste / direct-text
      content.
    * ``orphaned`` — defaults to ``False``. Flipped to ``True`` by
      :meth:`brain_core.ingest.pipeline.IngestPipeline.mark_orphaned`
      (T3) when a watched source disappears from disk.
    * ``orphaned_at`` — UTC date the note's ``orphaned`` flag last
      flipped to ``True``. ``None`` while ``orphaned`` is ``False``.
    * ``watched_folder_id`` — the ``WatchedFolder.path`` from
      :attr:`brain_core.config.schema.Config.watched_folders` that
      sourced this note. Links the note back to its watched-folder
      record so :meth:`brain_core.vault.scope_guard.scope_guard` and
      the Orphan-management UI can resolve the originating folder.

    The fields are typed loosely (``str | None`` rather than richer
    types) because the YAML loader returns strings for unquoted scalars
    and we want the schema to round-trip a raw ``parse_frontmatter``
    dict without coercion failures. Stricter typing happens at the
    consumer call sites (e.g. :class:`pathlib.Path` for ``source_path``
    inside the ingest pipeline).
    """

    model_config = ConfigDict(extra="allow")
    title: str | None = None
    domain: str | None = None
    type: Literal["source", "entity", "concept", "synthesis", "chat"] | None = None
    created: date | None = None
    updated: date | None = None
    source_type: (
        Literal["text", "url", "pdf", "email", "transcript", "tweet"] | None
    ) = None
    source_url: str | None = None
    tags: list[str] | None = None
    ingested_by: str | None = None
    content_hash: str | None = None
    # Plan 22 T1 / spec §4: new optional fields for watched-folders + orphan management.
    source_path: str | None = None
    orphaned: bool = False
    orphaned_at: date | None = None
    watched_folder_id: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Frontmatter:
        """Convenience constructor over a ``parse_frontmatter``-shaped dict.

        Equivalent to ``Frontmatter.model_validate(dict(data))`` but
        spelled out so the call sites in T2 / T3 / T4 read clearly.
        Unknown keys are preserved (``extra="allow"``); known fields
        coerce per their type (e.g. ISO date string → ``date``).
        """
        return cls.model_validate(dict(data))


_FENCE = "---"


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Split frontmatter from body. Raises if no frontmatter or malformed."""
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != _FENCE:
        raise FrontmatterError("missing frontmatter fence at top of file")

    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == _FENCE:
            end_idx = i
            break
    if end_idx is None:
        raise FrontmatterError("unterminated frontmatter - no closing ---")

    yaml_src = "".join(lines[1:end_idx])
    try:
        loaded = yaml.safe_load(yaml_src)
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"invalid YAML in frontmatter: {exc}") from exc
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise FrontmatterError("frontmatter must be a YAML mapping")
    data = cast(dict[str, Any], loaded)

    body = "".join(lines[end_idx + 1 :])
    if body.startswith("\n"):
        body = body[1:]
    return data, body


def serialize_with_frontmatter(data: Mapping[str, Any], *, body: str) -> str:
    """Serialize a note with frontmatter. Key order is preserved from the input mapping."""
    yaml_text = yaml.safe_dump(dict(data), sort_keys=False, allow_unicode=True).rstrip("\n")
    return f"{_FENCE}\n{yaml_text}\n{_FENCE}\n\n{body}"
