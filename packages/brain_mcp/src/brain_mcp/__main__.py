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
import structlog
from brain_core.config.hot_reload import ConfigWatcher
from brain_core.config.loader import invalidate_cache_for

from brain_mcp.server import create_server

_logger = structlog.get_logger(__name__)


async def _run() -> None:
    vault_root = Path(os.environ.get("BRAIN_VAULT_ROOT", Path.home() / "Documents" / "brain"))
    allowed_domains = tuple(
        d.strip()
        for d in os.environ.get("BRAIN_ALLOWED_DOMAINS", "research,work").split(",")
        if d.strip()
    )
    server = create_server(vault_root=vault_root, allowed_domains=allowed_domains)

    # Plan 16 Task 35 / D28 step 3 of 3: symmetric watchdog. brain_api
    # runs an identical ConfigWatcher; both processes share only the
    # on-disk vault, so each watches independently. Failure to start
    # the watcher must NOT block the MCP server — Claude Desktop is
    # already connected to our stdio at this point and we owe it a
    # response. T34's lazy peek inside ``resolve_config`` is the
    # safety net.
    config_path = vault_root / ".brain" / "config.json"
    config_watcher: ConfigWatcher | None = None
    try:
        config_watcher = ConfigWatcher(
            config_path=config_path,
            on_change=lambda: invalidate_cache_for(config_path),
        )
        config_watcher.start()
    except Exception as exc:  # pragma: no cover — defensive
        _logger.warning(
            "hot_reload_unavailable",
            error=str(exc),
            config_path=str(config_path),
        )
        config_watcher = None

    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )
    finally:
        if config_watcher is not None:
            config_watcher.stop()


def main() -> int:
    asyncio.run(_run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
