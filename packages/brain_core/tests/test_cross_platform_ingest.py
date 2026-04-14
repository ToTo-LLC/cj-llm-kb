"""Cross-platform ingest smoke tests — Plan 02 Task 23.

Extends the Plan 01 `test_cross_platform.py` vault-write smoke with
ingest-specific coverage: unicode filenames through text + pdf handlers
and archive directory computation cross-platform.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import pytest
from brain_core.ingest.archive import archive_dir_for
from brain_core.ingest.handlers.pdf import PDFHandler
from brain_core.ingest.handlers.text import TextHandler
from brain_core.ingest.types import SourceType


@pytest.mark.asyncio
async def test_text_handler_unicode_filename(tmp_path: Path) -> None:
    """Text handler reads a file whose name contains unicode + spaces + em-dash."""
    src = tmp_path / "héllo — ✓.txt"
    src.write_text("Hello, brain. Unicode body: café ✨\n", encoding="utf-8")

    h = TextHandler()
    assert h.can_handle(src) is True

    archive_root = tmp_path / "archive"
    extracted = await h.extract(src, archive_root=archive_root)

    assert extracted.source_type is SourceType.TEXT
    assert "café" in extracted.body_text
    assert extracted.archive_path.exists()
    assert extracted.archive_path.name == "héllo — ✓.txt"
    assert extracted.title == "héllo — ✓"


@pytest.mark.asyncio
async def test_pdf_handler_unicode_filename(tmp_path: Path) -> None:
    """PDF handler opens and extracts from a file whose name contains unicode."""
    src = tmp_path / "café — résumé ✓.pdf"
    doc = fitz.open()
    page = doc.new_page()
    # Long enough body text to clear the default min_chars=200 threshold.
    page.insert_text(
        (50, 100),
        "Unicode PDF smoke fixture.\n"
        "Paragraph one with enough text to pass the scanned-PDF guard.\n"
        "Paragraph two continues with more filler content for the threshold.\n"
        "Paragraph three keeps going so extraction produces a non-trivial body.\n",
    )
    doc.save(src)
    doc.close()

    h = PDFHandler()
    assert h.can_handle(src) is True

    archive_root = tmp_path / "archive"
    extracted = await h.extract(src, archive_root=archive_root)

    assert extracted.source_type is SourceType.PDF
    assert "Unicode PDF smoke fixture" in extracted.body_text
    assert extracted.archive_path.exists()
    assert extracted.archive_path.name == "café — résumé ✓.pdf"


def test_archive_dir_for_is_pathlib_cross_platform(tmp_path: Path) -> None:
    """archive_dir_for uses pathlib and produces separators native to the OS."""
    when = datetime(2026, 4, 14, 9, 30, tzinfo=UTC)
    got = archive_dir_for(vault_root=tmp_path, domain="research", when=when)

    # Structural assertions — independent of OS separator.
    assert got.parts[-5:] == ("raw", "archive", "research", "2026", "04")
    assert got.name == "04"
    assert got.parent.name == "2026"
    # Does NOT contain hardcoded forward-slash segments
    assert "/" not in got.name
    assert "\\" not in got.name
    # Is a valid pathlib Path rooted under the tmp vault
    assert got.is_relative_to(tmp_path)
    # Not yet created — archive_dir_for is pure
    assert not got.exists()


def test_archive_dir_for_unicode_domain(tmp_path: Path) -> None:
    """archive_dir_for accepts a unicode domain string without mangling."""
    when = datetime(2026, 1, 5, tzinfo=UTC)
    got = archive_dir_for(vault_root=tmp_path, domain="rëcherche", when=when)
    assert "rëcherche" in got.parts
    assert got.name == "01"
