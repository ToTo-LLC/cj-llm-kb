from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from brain_core.ingest.archive import archive_dir_for


def test_archive_dir_for_default(tmp_path: Path) -> None:
    when = datetime(2026, 4, 14, 9, 30, tzinfo=UTC)
    got = archive_dir_for(vault_root=tmp_path, domain="default", when=when)
    assert got == tmp_path / "raw" / "archive" / "default" / "2026" / "04"


def test_archive_dir_for_pads_single_digit_month(tmp_path: Path) -> None:
    when = datetime(2026, 1, 5, tzinfo=UTC)
    got = archive_dir_for(vault_root=tmp_path, domain="personal", when=when)
    assert got == tmp_path / "raw" / "archive" / "personal" / "2026" / "01"


def test_archive_dir_for_does_not_create_dir(tmp_path: Path) -> None:
    """archive_dir_for is a pure computation — caller is responsible for mkdir."""
    when = datetime(2026, 4, 14, tzinfo=UTC)
    got = archive_dir_for(vault_root=tmp_path, domain="work", when=when)
    assert not got.exists()
