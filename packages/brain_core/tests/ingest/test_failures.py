from __future__ import annotations

import json
from pathlib import Path

from brain_core.ingest.failures import record_failure


def test_record_failure_writes_json_with_required_fields(tmp_path: Path) -> None:
    try:
        raise ValueError("trafilatura extracted nothing")
    except ValueError as exc:
        path = record_failure(
            vault_root=tmp_path,
            slug="example-com-a",
            stage="extract",
            exception=exc,
        )

    assert path == tmp_path / "raw" / "inbox" / "failed" / "example-com-a.error.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["slug"] == "example-com-a"
    assert data["stage"] == "extract"
    assert data["exception_class"] == "ValueError"
    assert "trafilatura extracted nothing" in data["message"]
    assert "ts_utc" in data
    assert data["ts_utc"].endswith("+00:00") or data["ts_utc"].endswith("Z")


def test_record_failure_creates_parent_dirs(tmp_path: Path) -> None:
    """record_failure creates raw/inbox/failed/ if it doesn't already exist."""
    assert not (tmp_path / "raw").exists()
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        record_failure(
            vault_root=tmp_path,
            slug="b",
            stage="fetch",
            exception=exc,
        )
    assert (tmp_path / "raw" / "inbox" / "failed").is_dir()


def test_record_failure_overwrites_existing(tmp_path: Path) -> None:
    """A second failure for the same slug replaces the previous record."""
    try:
        raise ValueError("first")
    except ValueError as exc:
        record_failure(vault_root=tmp_path, slug="c", stage="fetch", exception=exc)
    try:
        raise RuntimeError("second")
    except RuntimeError as exc:
        path = record_failure(vault_root=tmp_path, slug="c", stage="extract", exception=exc)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["stage"] == "extract"
    assert data["exception_class"] == "RuntimeError"
