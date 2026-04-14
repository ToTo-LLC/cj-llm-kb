"""Archive path computation for the raw/archive/ tree.

Pure function — caller is responsible for creating the directory. This module
computes the canonical layout defined in the vault schema:
    <vault_root>/raw/archive/<domain>/<YYYY>/<MM>/
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def archive_dir_for(
    *,
    vault_root: Path,
    domain: str,
    when: datetime,
) -> Path:
    """Return the archive directory for a source ingested at `when` under `domain`.

    Does NOT create the directory — the pipeline's archive-writer owns mkdir.
    """
    return vault_root / "raw" / "archive" / domain / f"{when.year:04d}" / f"{when.month:02d}"
