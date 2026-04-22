"""brain_backup_list — enumerate existing vault snapshots, newest first.

Wraps :func:`brain_core.backup.list_snapshots`. Read-only; opens each
tarball to count member files so the UI can display sizes + file counts
without a separate call.
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.backup import list_snapshots
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_backup_list"
DESCRIPTION = (
    "List existing vault snapshots under <vault>/.brain/backups/ (newest first). "
    "Returns backup_id, path, trigger, created_at, size_bytes, file_count."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    _ = arguments
    snapshots = list_snapshots(ctx.vault_root)
    out: list[dict[str, Any]] = [
        {
            "backup_id": m.backup_id,
            "path": str(m.path),
            "trigger": m.trigger,
            "created_at": m.created_at.isoformat(),
            "size_bytes": m.size_bytes,
            "file_count": m.file_count,
        }
        for m in snapshots
    ]
    if not snapshots:
        text = "(no backups)"
    else:
        text = "\n".join(f"- {m.backup_id} ({m.trigger}, {m.size_bytes} bytes)" for m in snapshots)
    return ToolResult(text=text, data={"backups": out})


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
