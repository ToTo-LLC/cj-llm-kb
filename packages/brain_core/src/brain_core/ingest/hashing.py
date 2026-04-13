"""Content hashing for idempotent ingest."""

from __future__ import annotations

import hashlib


def content_hash(data: str | bytes) -> str:
    """Return a stable SHA-256 hex digest of the input content."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()
