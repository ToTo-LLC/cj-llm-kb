from __future__ import annotations

from datetime import date
from pathlib import Path

from brain_core.ingest.types import (
    ExtractedSource,
    IngestResult,
    IngestStatus,
    SourceType,
)


def test_extracted_source_round_trip() -> None:
    es = ExtractedSource(
        title="A Title",
        author="An Author",
        published=date(2026, 4, 13),
        source_url="https://example.com/a",
        source_type=SourceType.URL,
        body_text="Hello body.",
        archive_path=Path("/tmp/archive/a.html"),
        extras={"hash": "abc"},
    )
    assert es.title == "A Title"
    assert es.source_type is SourceType.URL
    assert es.extras["hash"] == "abc"


def test_ingest_result_defaults() -> None:
    r = IngestResult(status=IngestStatus.OK, note_path=None)
    assert r.status is IngestStatus.OK
    assert r.note_path is None
    assert r.errors == []


def test_source_type_values() -> None:
    assert SourceType.URL.value == "url"
    assert SourceType.PDF.value == "pdf"
    assert SourceType.TEXT.value == "text"
