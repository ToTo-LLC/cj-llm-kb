"""Entry point: `python -m brain_mcp` runs the stdio MCP server.

Task 1 lands a stub that prints the version and exits. Task 21 wires the
real stdio transport via `mcp.server.stdio.stdio_server`.
"""

from __future__ import annotations

import sys

from brain_mcp import __version__


def main() -> int:
    print(f"brain_mcp {__version__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
