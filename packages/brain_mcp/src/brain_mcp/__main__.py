"""Entry point: `python -m brain_mcp` runs the stdio MCP server.

Launches the brain MCP server over stdio (the transport Claude Desktop uses).
Configuration flows in via environment variables that ``brain mcp install``
writes into the Claude Desktop config's ``env`` dict:

* ``BRAIN_VAULT_ROOT`` — absolute path to the vault (default
  ``~/Documents/brain``).
* ``BRAIN_ALLOWED_DOMAINS`` — comma-separated allow-list of domains the server
  may read/write (default ``"research,work"``; ``personal`` is deliberately
  excluded from the default).

The Task 1 stub that merely printed the version is replaced here.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import mcp.server.stdio

from brain_mcp.server import create_server


async def _run() -> None:
    vault_root = Path(os.environ.get("BRAIN_VAULT_ROOT", Path.home() / "Documents" / "brain"))
    allowed_domains = tuple(
        d.strip()
        for d in os.environ.get("BRAIN_ALLOWED_DOMAINS", "research,work").split(",")
        if d.strip()
    )
    server = create_server(vault_root=vault_root, allowed_domains=allowed_domains)
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> int:
    asyncio.run(_run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
