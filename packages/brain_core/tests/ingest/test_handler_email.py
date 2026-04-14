from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.ingest.handlers.email import EmailHandler
from brain_core.ingest.types import SourceType


@pytest.mark.asyncio
async def test_email_handler_parses_header_and_body(fixtures_dir: Path, tmp_path: Path) -> None:
    text = (fixtures_dir / "email.txt").read_text(encoding="utf-8")
    h = EmailHandler()
    assert await h.can_handle(text) is True
    es = await h.extract(text, archive_root=tmp_path)
    assert es.source_type is SourceType.EMAIL
    assert es.title == "Q2 planning"
    assert es.author and "alice@example.com" in es.author
    assert "Budget review" in es.body_text
    assert es.archive_path.exists()


@pytest.mark.asyncio
async def test_email_handler_rejects_non_email_text() -> None:
    assert await EmailHandler().can_handle("just a random paragraph") is False
