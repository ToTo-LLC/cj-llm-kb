"""brain_mcp_install — write the ``mcpServers.brain`` entry into Claude Desktop's config.

Pure file-layer operation: delegates to
:func:`brain_core.integrations.claude_desktop.install`, which handles the
atomic write and timestamped backup of any prior config. The caller
(frontend / MCP client) is responsible for confirming the destructive
nature of this action with the user — the tool itself does not prompt.

Cross-platform config-path resolution happens in ``detect_config_path()``
(Mac / Windows / Linux); the caller may override via the explicit
``config_path`` argument for testing.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from brain_core.integrations.claude_desktop import detect_config_path, install
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_mcp_install"
DESCRIPTION = (
    "Install the brain MCP server into Claude Desktop's config file. "
    "Writes mcpServers.brain with a timestamped backup of any prior config. "
    "command + args describe how Claude Desktop should spawn brain-mcp."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "command": {"type": "string"},
        "args": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
        },
        "env": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "default": {},
        },
        "config_path": {
            "type": "string",
            "description": "Override the auto-detected Claude Desktop config path.",
        },
        "server_name": {"type": "string", "default": "brain"},
    },
    "required": ["command"],
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    _ = ctx  # no vault interaction
    command = str(arguments["command"])
    args_raw = arguments.get("args", [])
    args: list[str] = [str(a) for a in args_raw] if args_raw else []
    env_raw = arguments.get("env", {})
    env: dict[str, str] = (
        {str(k): str(v) for k, v in env_raw.items()} if env_raw else {}
    )
    server_name = str(arguments.get("server_name", "brain"))
    config_path = (
        Path(str(arguments["config_path"]))
        if arguments.get("config_path")
        else detect_config_path()
    )

    result = install(
        config_path=config_path,
        server_name=server_name,
        command=command,
        args=args,
        env=env,
    )

    return ToolResult(
        text=f"installed brain MCP entry into {result.config_path}",
        data={
            "status": "installed",
            "config_path": str(result.config_path),
            "backup_path": str(result.backup_path) if result.backup_path else None,
            "server_name": server_name,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
