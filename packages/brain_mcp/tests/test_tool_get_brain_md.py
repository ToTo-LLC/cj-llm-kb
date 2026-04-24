"""Tests for the brain_get_brain_md MCP tool."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from brain_core.tools.base import ToolContext
from brain_mcp.tools.get_brain_md import INPUT_SCHEMA, NAME, handle


def test_name() -> None:
    assert NAME == "brain_get_brain_md"


def test_input_schema_no_args() -> None:
    assert INPUT_SCHEMA["type"] == "object"
    assert INPUT_SCHEMA["properties"] == {}


async def test_reads_brain_md(seeded_vault: Path, make_ctx: Callable[..., ToolContext]) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({}, ctx)
    assert "You are brain" in out[0].text
    data = json.loads(out[1].text)
    assert data["exists"] is True
    assert "You are brain" in data["body"]


async def test_missing_returns_friendly(
    tmp_path: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    vault = tmp_path / "empty"
    (vault / "research").mkdir(parents=True)
    ctx = make_ctx(vault, allowed_domains=("research",))
    out = await handle({}, ctx)
    assert "no BRAIN.md" in out[0].text
    data = json.loads(out[1].text)
    assert data["exists"] is False
    assert data["body"] == ""
