"""Per-source failure records written to raw/inbox/failed/."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


def record_failure(
    *,
    vault_root: Path,
    slug: str,
    stage: str,
    exception: BaseException,
) -> Path:
    """Write a JSON failure record and return its path.

    Layout:
        <vault_root>/raw/inbox/failed/<slug>.error.json

    Fields:
        slug, stage, exception_class, message, ts_utc (ISO 8601 with offset)
    """
    failed_dir = vault_root / "raw" / "inbox" / "failed"
    failed_dir.mkdir(parents=True, exist_ok=True)
    path = failed_dir / f"{slug}.error.json"
    path.write_text(
        json.dumps(
            {
                "slug": slug,
                "stage": stage,
                "exception_class": type(exception).__name__,
                "message": str(exception),
                "ts_utc": datetime.now(tz=UTC).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
