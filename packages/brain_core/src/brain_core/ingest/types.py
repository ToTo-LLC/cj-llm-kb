"""Typed models shared across the ingestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any


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
