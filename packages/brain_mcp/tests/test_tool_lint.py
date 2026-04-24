"""Tests for the brain_lint stub MCP tool."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from brain_core.tools.base import ToolContext
from brain_mcp.tools.lint import NAME, handle


def test_name() -> None:
    assert NAME == "brain_lint"


async def test_lint_stub_returns_not_implemented(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({}, ctx)
    data = json.loads(out[1].text)
    assert data["status"] == "not_implemented"
    assert "Plan 09" in data["message"]


def test_lint_input_schema_has_no_required() -> None:
    from brain_mcp.tools.lint import INPUT_SCHEMA

    assert INPUT_SCHEMA.get("required", []) == []
