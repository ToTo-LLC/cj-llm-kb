"""Typed models shared across the ingestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Deferred to dodge any import-cycle risk — vault.types is ultimately a leaf,
    # but pipeline imports from ingest.types at module load, and a runtime import
    # of vault.types here would force the order. The forward-ref string below
    # keeps Pydantic/dataclasses happy without forcing load order.
    from brain_core.vault.types import PatchSet


class SourceType(StrEnum):
    TEXT = "text"
    URL = "url"
    PDF = "pdf"
    EMAIL = "email"
    TRANSCRIPT = "transcript"
    TWEET = "tweet"


class IngestStatus(StrEnum):
    OK = "ok"
    QUARANTINED = "quarantined"
    FAILED = "failed"
    SKIPPED_DUPLICATE = "skipped_duplicate"


@dataclass(frozen=True)
class ExtractedSource:
    title: str | None
    author: str | None
    published: date | None
    source_url: str | None
    source_type: SourceType
    body_text: str
    archive_path: Path
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestResult:
    status: IngestStatus
    note_path: Path | None
    cost_usd: float = 0.0
    errors: list[str] = field(default_factory=list)
    extracted: ExtractedSource | None = None
    # Populated only when the pipeline is called with ``apply=False`` — in that
    # mode Stage 9 skips the VaultWriter.apply() call and returns the built
    # PatchSet (source note prepended) to the caller so they can stage it for
    # human approval. ``note_path`` is the *intended* vault path; nothing has
    # been written yet. When ``apply=True`` (default), this is ``None``.
    patchset: PatchSet | None = None
