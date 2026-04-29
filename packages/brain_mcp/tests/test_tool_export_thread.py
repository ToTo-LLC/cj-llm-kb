"""Tests for the brain_export_thread MCP tool (issue #17)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from brain_core.tools.base import ToolContext
from brain_mcp.tools.export_thread import NAME, handle


def test_name() -> None:
    assert NAME == "brain_export_thread"


async def test_returns_text_content_envelope_with_markdown(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """Standard 2-element TextContent shape — first element is the
    summary string, second the JSON payload that includes ``markdown``."""
    chats_dir = seeded_vault / "research" / "chats"
    chats_dir.mkdir(parents=True, exist_ok=True)
    body = "---\nmode: ask\n---\n\n## User\n\nhello\n\n## Assistant\n\nhi\n"
    (chats_dir / "t-export.md").write_text(body, encoding="utf-8")

    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({"thread_id": "t-export"}, ctx)

    assert len(out) == 2
    assert "exported" in out[0].text
    payload = json.loads(out[1].text)
    assert payload["thread_id"] == "t-export"
    assert payload["domain"] == "research"
    assert payload["filename"] == "t-export.md"
    assert payload["markdown"] == body


async def test_missing_thread_propagates_file_not_found(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """The shim doesn't trap FileNotFoundError — the global error
    handler in brain_api translates it into a 404 envelope. Pin that
    the exception still bubbles."""
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    with pytest.raises(FileNotFoundError):
        await handle({"thread_id": "t-missing"}, ctx)
