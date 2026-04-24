"""Tests for the brain_list_domains MCP tool."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any

from brain_core.tools.base import ToolContext
from brain_mcp.tools.list_domains import INPUT_SCHEMA, NAME, handle
from mcp.client.session import ClientSession


def test_input_schema_shape() -> None:
    assert NAME == "brain_list_domains"
    assert INPUT_SCHEMA["type"] == "object"
    assert INPUT_SCHEMA.get("properties") == {}


async def test_handle_returns_sorted_domains(
    seeded_vault: Path, make_ctx: Callable[..., ToolContext]
) -> None:
    ctx = make_ctx(seeded_vault, allowed_domains=("research",))
    out = await handle({}, ctx)
    assert len(out) >= 2  # text + JSON data
    data = json.loads(out[1].text)
    assert data["domains"] == ["personal", "research", "work"]


async def test_mcp_session_list_domains(
    mcp_session_ctx_with_vault: Callable[[], AbstractAsyncContextManager[ClientSession]],
) -> None:
    """End-to-end via the in-memory MCP client."""
    async with mcp_session_ctx_with_vault() as session:
        result = await session.call_tool("brain_list_domains", {})
        assert result.isError is False
        parsed: dict[str, Any] | None = None
        for block in result.content:
            try:
                candidate = json.loads(getattr(block, "text", ""))
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(candidate, dict) and "domains" in candidate:
                parsed = candidate
                break
        assert parsed is not None, "no JSON content block found"
        assert "research" in parsed["domains"]
