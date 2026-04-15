"""brain MCP server factory.

Task 1 lands the skeleton — empty tool list, rejecting call_tool handler.
Task 4+ populate via brain_mcp.tools.* modules registered at factory time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import mcp.types as types
from mcp.server.lowlevel import Server


def create_server(
    *,
    vault_root: Path,
    allowed_domains: tuple[str, ...] = ("research",),
) -> Server:
    """Build a fresh `mcp.server.lowlevel.Server` instance with handlers registered.

    Does NOT start the stdio transport. Callers (brain_mcp.__main__, test
    harnesses) are responsible for running the server against their chosen
    transport.
    """
    _ = vault_root  # Task 4+ will wire this into _build_ctx
    _ = allowed_domains  # Task 4+ will wire this
    server: Server = Server("brain")

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return []

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        raise ValueError(f"unknown tool: {name}")

    return server
