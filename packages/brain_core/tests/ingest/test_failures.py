from __future__ import annotations

import json
import re
import time
from pathlib import Path

from brain_core.ingest.failures import record_failure

_FILENAME_RE = re.compile(r"^(?P<slug>.+)\.(?P<ts>\d{8}T\d{6}\d{6})\.error\.json$")


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

    assert path.parent == tmp_path / "raw" / "inbox" / "failed"
    match = _FILENAME_RE.match(path.name)
    assert match is not None, f"unexpected filename: {path.name}"
    assert match.group("slug") == "example-com-a"
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


def test_record_failure_preserves_history_on_collision(tmp_path: Path) -> None:
    """Two failures for the same slug each persist as their own file (item #22).

    Prior behavior overwrote the previous record on slug collision, losing
    retry history. The compact-timestamp suffix preserves both records.
    """
    try:
        raise ValueError("first")
    except ValueError as exc:
        first = record_failure(vault_root=tmp_path, slug="c", stage="fetch", exception=exc)
    # Sleep enough to guarantee a different microsecond-precision timestamp
    # even on coarse-grained Windows clocks.
    time.sleep(0.001)
    try:
        raise RuntimeError("second")
    except RuntimeError as exc:
        second = record_failure(vault_root=tmp_path, slug="c", stage="extract", exception=exc)

    assert first.exists(), "first failure record should still exist"
    assert second.exists(), "second failure record should also exist"
    assert first != second, "second record should not overwrite the first"

    failed_dir = tmp_path / "raw" / "inbox" / "failed"
    files = sorted(failed_dir.glob("c.*.error.json"))
    assert len(files) == 2, f"expected 2 records, found {[f.name for f in files]}"

    # Sanity: each file's content matches the failure it recorded.
    first_data = json.loads(first.read_text(encoding="utf-8"))
    second_data = json.loads(second.read_text(encoding="utf-8"))
    assert first_data["stage"] == "fetch"
    assert first_data["exception_class"] == "ValueError"
    assert second_data["stage"] == "extract"
    assert second_data["exception_class"] == "RuntimeError"
