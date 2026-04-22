"""brain_mcp_uninstall — remove the ``mcpServers.brain`` entry from Claude Desktop's config.

Delegates to :func:`brain_core.integrations.claude_desktop.uninstall`
which always backs up the prior config before mutating it. No-op when
the entry is already absent (returns ``status='not_installed'``).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from brain_core.integrations.claude_desktop import detect_config_path, uninstall
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_mcp_uninstall"
DESCRIPTION = (
    "Remove the brain MCP entry from Claude Desktop's config. No-op if "
    "the entry is absent. A timestamped backup is written before any mutation."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "config_path": {
            "type": "string",
            "description": "Override the auto-detected Claude Desktop config path.",
        },
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

    result = uninstall(config_path=config_path, server_name=server_name)
    if not result.removed:
        return ToolResult(
            text=f"no brain MCP entry found in {result.config_path}",
            data={
                "status": "not_installed",
                "config_path": str(result.config_path),
                "server_name": server_name,
            },
        )
    return ToolResult(
        text=f"removed brain MCP entry from {result.config_path}",
        data={
            "status": "uninstalled",
            "config_path": str(result.config_path),
            "backup_path": str(result.backup_path) if result.backup_path else None,
            "server_name": server_name,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
