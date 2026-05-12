"""Pin tests for the SourceType enum.

These guard against silent drift in `SourceType` members. Any future change
(add, remove, rename, or string-value mutation) must update the assertions
here alongside the enum — making the contract change explicit in review.

Plan 24 added DOCX + PPTX. Any future SourceType addition (e.g., xlsx, rtf)
must update this pin alongside the enum.
"""

from __future__ import annotations

from brain_core.ingest.types import SourceType


def test_source_type_enum_field_set() -> None:
    """Pin SourceType members so future drift fails RED.

    Plan 24 added DOCX + PPTX. Any future SourceType addition (e.g.,
    xlsx, rtf) must update this pin alongside the enum.
    """
    assert set(SourceType.__members__.keys()) == {
        "TEXT",
        "URL",
        "PDF",
        "EMAIL",
        "TRANSCRIPT",
        "DOCX",
        "PPTX",
        "TWEET",
    }


def test_source_type_string_values_match() -> None:
    """Pin string values (since SourceType is a StrEnum used in frontmatter)."""
    assert SourceType.TEXT.value == "text"
    assert SourceType.URL.value == "url"
    assert SourceType.PDF.value == "pdf"
    assert SourceType.EMAIL.value == "email"
    assert SourceType.TRANSCRIPT.value == "transcript"
    assert SourceType.DOCX.value == "docx"
    assert SourceType.PPTX.value == "pptx"
    assert SourceType.TWEET.value == "tweet"
