"""VTT/SRT transcript handler — strips timestamps, preserves speakers."""

from __future__ import annotations

import shutil
from pathlib import Path

import webvtt

from brain_core.ingest.handlers.base import HandlerError
from brain_core.ingest.types import ExtractedSource, SourceType

_EXTS = {".vtt", ".srt"}


class TranscriptVTTHandler:
    source_type: SourceType = SourceType.TRANSCRIPT

    async def can_handle(self, spec: str | Path) -> bool:
        return isinstance(spec, Path) and spec.suffix.lower() in _EXTS and spec.exists()

    async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource:
        if not isinstance(spec, Path) or not spec.exists():
            raise HandlerError(f"transcript_vtt cannot read {spec!r}")
        if spec.suffix.lower() == ".srt":
            captions = webvtt.from_srt(str(spec))
        else:
            captions = webvtt.read(str(spec))
        lines = [c.text.strip() for c in captions if c.text.strip()]
        body = "\n".join(lines)
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_path = archive_root / spec.name
        shutil.copy2(spec, archive_path)
        return ExtractedSource(
            title=spec.stem,
            author=None,
            published=None,
            source_url=None,
            source_type=SourceType.TRANSCRIPT,
            body_text=body,
            archive_path=archive_path,
        )
