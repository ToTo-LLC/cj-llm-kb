"""Smoke tests for the brain MCP server — empty-tool baseline."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from pathlib import Path

from mcp.client.session import ClientSession

SessionCtx = Callable[[Path], AbstractAsyncContextManager[ClientSession]]


async def test_initialize_succeeds(mcp_session_ctx: SessionCtx, tmp_path: Path) -> None:
    """Session initialization via the in-memory helper should complete cleanly."""
    async with mcp_session_ctx(tmp_path) as session:
        result = await session.list_tools()
        # Task 1 baseline: zero tools registered.
        assert result.tools == []


async def test_unknown_tool_returns_error(mcp_session_ctx: SessionCtx, tmp_path: Path) -> None:
    """Calling a non-existent tool returns a CallToolResult with isError=True.

    The MCP low-level server catches handler exceptions and reports them as
    `CallToolResult(isError=True, content=[TextContent(...)])` rather than
    raising over the wire — so we assert on the result flag, not pytest.raises.
    """
    async with mcp_session_ctx(tmp_path) as session:
        result = await session.call_tool("nonexistent", {})
        assert result.isError is True
        assert any("unknown tool" in getattr(c, "text", "") for c in result.content)
