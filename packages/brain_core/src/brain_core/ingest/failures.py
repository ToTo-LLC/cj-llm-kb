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
        <vault_root>/raw/inbox/failed/<slug>.<ts>.error.json

    The compact UTC timestamp suffix preserves retry history — re-ingesting
    the same source after a failure no longer overwrites the prior record.

    Fields:
        slug, stage, exception_class, message, ts_utc (ISO 8601 with offset)
    """
    now = datetime.now(tz=UTC)
    failed_dir = vault_root / "raw" / "inbox" / "failed"
    failed_dir.mkdir(parents=True, exist_ok=True)
    ts_compact = now.strftime("%Y%m%dT%H%M%S%f")
    path = failed_dir / f"{slug}.{ts_compact}.error.json"
    path.write_text(
        json.dumps(
            {
                "slug": slug,
                "stage": stage,
                "exception_class": type(exception).__name__,
                "message": str(exception),
                "ts_utc": now.isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
