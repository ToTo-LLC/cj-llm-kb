"""SourceHandler Protocol and the handler registry."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from brain_core.ingest.types import ExtractedSource, SourceType


class HandlerError(RuntimeError):
    """Raised when a handler cannot fetch or extract a source."""


@runtime_checkable
class SourceHandler(Protocol):
    """Contract every per-type handler satisfies.

    `can_handle` must be a pure, synchronous routing check — no I/O, no
    side effects, no network. `extract` does the actual work and may do I/O.
    """

    source_type: SourceType

    def can_handle(self, spec: str | Path) -> bool: ...

    async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource: ...
