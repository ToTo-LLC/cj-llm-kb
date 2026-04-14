"""Email handler — pasted .eml-style text. Uses stdlib email.parser."""

from __future__ import annotations

from email import message_from_string
from email.utils import parseaddr
from pathlib import Path

from brain_core.ingest.handlers.base import HandlerError
from brain_core.ingest.hashing import content_hash
from brain_core.ingest.types import ExtractedSource, SourceType

_REQUIRED_HEADERS = {"from", "to", "subject"}


class EmailHandler:
    source_type: SourceType = SourceType.EMAIL

    def can_handle(self, spec: str | Path) -> bool:
        if not isinstance(spec, str):
            return False
        head = spec.splitlines()[:10]
        headers: dict[str, str] = {}
        for line in head:
            if ":" in line:
                key, _, value = line.partition(":")
                headers[key.strip().lower()] = value.strip()
        if not _REQUIRED_HEADERS.issubset(headers):
            return False
        return "@" in headers.get("from", "")

    async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource:
        if not isinstance(spec, str):
            raise HandlerError(f"email handler cannot read {spec!r}")
        msg = message_from_string(spec)
        subject = msg.get("Subject", "").strip() or None
        from_raw = msg.get("From", "")
        _, from_addr = parseaddr(from_raw)
        body_text = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        body_text += payload.decode("utf-8", errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                body_text = payload.decode("utf-8", errors="replace")
        if not body_text:
            # Final safety net: if every branch above left body_text empty (e.g. edge-case
            # multipart with no text/plain parts), fall back to splitting on the blank-line
            # boundary.
            body_text = spec.split("\n\n", 1)[-1] if "\n\n" in spec else spec

        archive_root.mkdir(parents=True, exist_ok=True)
        h = content_hash(spec)[:16]
        archive_path = archive_root / f"{h}.eml"
        archive_path.write_text(spec, encoding="utf-8")

        return ExtractedSource(
            title=subject,
            author=from_addr or None,
            published=None,
            source_url=None,
            source_type=SourceType.EMAIL,
            body_text=body_text.strip(),
            archive_path=archive_path,
        )
