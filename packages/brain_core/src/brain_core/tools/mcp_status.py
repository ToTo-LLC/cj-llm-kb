"""brain_mcp_status — report the current Claude Desktop installation state.

Read-only; no file writes. Wraps
:func:`brain_core.integrations.claude_desktop.verify`. The returned
``data`` dict carries enough to power the Settings → MCP Integration
panel (config path, whether the entry is present, whether the configured
executable resolves on disk).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from brain_core.integrations.claude_desktop import detect_config_path, verify
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_mcp_status"
DESCRIPTION = (
    "Return the current Claude Desktop integration status for the brain MCP "
    "server (config path, entry presence, executable resolution)."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "config_path": {"type": "string"},
        "server_name": {"type": "string", "default": "brain"},
    },
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    _ = ctx
    server_name = str(arguments.get("server_name", "brain"))
    config_path = (
        Path(str(arguments["config_path"]))
        if arguments.get("config_path")
        else detect_config_path()
    )

    result = verify(config_path=config_path, server_name=server_name)
    ok = result.config_exists and result.entry_present and result.executable_resolves
    text = (
        f"brain MCP status: {'ok' if ok else 'not installed'} "
        f"(config_exists={result.config_exists}, entry_present={result.entry_present}, "
        f"executable_resolves={result.executable_resolves})"
    )
    return ToolResult(
        text=text,
        data={
            "status": "ok" if ok else "not_installed",
            "config_path": str(config_path),
            "config_exists": result.config_exists,
            "entry_present": result.entry_present,
            "executable_resolves": result.executable_resolves,
            "command": result.command,
            "server_name": server_name,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
