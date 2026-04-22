"""brain_mcp_selftest — file-layer self-test for the Claude Desktop integration.

Wraps :func:`brain_core.integrations.claude_desktop.selftest`. This is
the non-subprocess slice of ``brain mcp selftest`` — it verifies the
config exists, the entry is present, and the configured executable
resolves. The full subprocess round-trip (spawning ``brain-mcp`` and
calling ``tools/list``) stays in the CLI because it requires the MCP
client SDK, which ``brain_core`` cannot depend on.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from brain_core.integrations.claude_desktop import detect_config_path, selftest
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_mcp_selftest"
DESCRIPTION = (
    "File-layer self-test of the Claude Desktop integration (config exists, "
    "brain entry present, command executable resolves). Does NOT spawn the "
    "MCP server — use the CLI `brain mcp selftest` for the full round-trip."
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

    result = selftest(config_path=config_path, server_name=server_name)
    return ToolResult(
        text=(
            f"selftest {'passed' if result.ok else 'failed'}: "
            f"config_exists={result.config_exists}, "
            f"entry_present={result.entry_present}, "
            f"executable_resolves={result.executable_resolves}"
        ),
        data={
            "status": "passed" if result.ok else "failed",
            "ok": result.ok,
            "config_exists": result.config_exists,
            "entry_present": result.entry_present,
            "executable_resolves": result.executable_resolves,
            "command": result.command,
            "config_path": str(result.config_path),
            "server_name": server_name,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
