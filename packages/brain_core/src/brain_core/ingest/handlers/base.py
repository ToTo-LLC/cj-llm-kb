"""SourceHandler Protocol and the handler registry."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from brain_core.ingest.types import ExtractedSource, SourceType


class HandlerError(RuntimeError):
    """Raised when a handler cannot fetch or extract a source."""


@runtime_checkable
class SourceHandler(Protocol):
    """Contract every per-type handler satisfies."""

    source_type: SourceType

    async def can_handle(self, spec: str | Path) -> bool: ...

    async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource: ...


# Populated at import time by each handler module via register().
HANDLERS: list[SourceHandler] = []


def register(handler: SourceHandler) -> None:
    HANDLERS.append(handler)
