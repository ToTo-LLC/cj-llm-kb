"""Tests for the brain_bulk_import MCP tool.

The tool wraps ``brain_core.ingest.bulk.BulkImporter``. Plan phase calls the
classifier once per candidate file; the apply phase would run the full
IngestPipeline per item. These tests exercise the MCP wiring only — BulkImporter
has its own unit tests in brain_core.

Default is ``dry_run=True`` (per spec §7). The 20-file-without-max_files refusal
is enforced at the MCP layer BEFORE any LLM call, so a refused test doesn't need
to queue any classify responses.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from brain_mcp.tools.base import ToolContext
from brain_mcp.tools.bulk_import import NAME, handle


def _research_vault(tmp_path: Path) -> Path:
    """Build a minimal research-only vault the IngestPipeline + writer accept."""
    vault = tmp_path / "vault"
    (vault / ".brain").mkdir(parents=True)
    for sub in ("sources", "entities", "concepts", "synthesis"):
        (vault / "research" / sub).mkdir(parents=True)
    (vault / "research" / "index.md").write_text(
        "# research — index\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Synthesis\n",
        encoding="utf-8",
    )
    (vault / "research" / "log.md").write_text("# research — log\n", encoding="utf-8")
    for sub in ("inbox", "failed", "archive"):
        (vault / "raw" / sub).mkdir(parents=True)
    (vault / "BRAIN.md").write_text("# BRAIN\n\nDefault schema doc.\n", encoding="utf-8")
    return vault


def test_name() -> None:
    assert NAME == "brain_bulk_import"


async def test_bulk_import_dry_run_returns_plan(
    tmp_path: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """Two text files → plan status, 2 items, vault untouched."""
    vault = _research_vault(tmp_path)
    source_folder = tmp_path / "inbox"
    source_folder.mkdir()
    (source_folder / "a.txt").write_text("first file", encoding="utf-8")
    (source_folder / "b.txt").write_text("second file", encoding="utf-8")

    ctx = make_ctx(vault, allowed_domains=("research",))
    # One classify call per candidate file during plan().
    ctx.llm.queue('{"source_type":"text","domain":"research","confidence":0.9}')
    ctx.llm.queue('{"source_type":"text","domain":"research","confidence":0.9}')

    out = await handle({"folder": str(source_folder), "dry_run": True}, ctx)
    data = json.loads(out[1].text)

    assert data["status"] == "planned"
    assert data["file_count"] == 2
    # No vault writes happened.
    assert not any((vault / "research" / "sources").rglob("*.md"))


async def test_bulk_import_default_is_dry_run(
    tmp_path: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """Omitting dry_run → defaults to planned (no apply)."""
    vault = _research_vault(tmp_path)
    source_folder = tmp_path / "inbox"
    source_folder.mkdir()
    (source_folder / "a.txt").write_text("only file", encoding="utf-8")

    ctx = make_ctx(vault, allowed_domains=("research",))
    ctx.llm.queue('{"source_type":"text","domain":"research","confidence":0.9}')

    out = await handle({"folder": str(source_folder)}, ctx)
    data = json.loads(out[1].text)
    assert data["status"] == "planned"


async def test_bulk_import_refuses_large_folder_without_max_files(
    tmp_path: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """dry_run=False + >20 files + no max_files → refused, no classify calls."""
    vault = _research_vault(tmp_path)
    source_folder = tmp_path / "inbox"
    source_folder.mkdir()
    for i in range(25):
        (source_folder / f"{i}.txt").write_text("x", encoding="utf-8")

    ctx = make_ctx(vault, allowed_domains=("research",))
    # Deliberately queue NO classify responses: the refusal must fire pre-plan()
    # so FakeLLMProvider never has to produce one. If the tool called through,
    # FakeLLMProvider would raise on empty queue and the test would fail loudly.
    out = await handle({"folder": str(source_folder), "dry_run": False}, ctx)
    data = json.loads(out[1].text)
    assert data["status"] == "refused"
    assert "max_files" in data["reason"]
    assert data["file_count"] == 25


async def test_bulk_import_missing_folder_raises(
    tmp_path: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    """Nonexistent folder → FileNotFoundError (plain-English message)."""
    vault = _research_vault(tmp_path)
    ctx = make_ctx(vault, allowed_domains=("research",))
    missing = tmp_path / "definitely-not-here"
    with pytest.raises(FileNotFoundError):
        await handle({"folder": str(missing)}, ctx)
