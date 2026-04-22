"""brain_backup_create — create a point-in-time snapshot of the vault.

Wraps :func:`brain_core.backup.create_snapshot`. Writes a gzip tarball
to ``<vault>/.brain/backups/``; the tarball excludes ephemeral paths
(``.brain/run/``, ``.brain/logs/``) and ``.brain/secrets.env`` so a
snapshot never leaks the user's API key.

Triggers surface in the filename so the Settings page can group them
("manual backups" vs. "daily cron" vs. "pre-bulk-import auto-safety").
"""

from __future__ import annotations

import sys
from typing import Any, cast

from brain_core.backup import BackupTrigger, create_snapshot
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_backup_create"
DESCRIPTION = (
    "Create a tarball snapshot of the vault (excludes .brain/run, .brain/logs, "
    "secrets.env). Writes to <vault>/.brain/backups/. Returns the backup metadata."
)

_VALID_TRIGGERS: tuple[str, ...] = ("manual", "daily", "pre_bulk_import")

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "trigger": {
            "type": "string",
            "enum": list(_VALID_TRIGGERS),
            "default": "manual",
        },
    },
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    trigger_str = str(arguments.get("trigger", "manual"))
    if trigger_str not in _VALID_TRIGGERS:
        raise ValueError(
            f"trigger {trigger_str!r} must be one of {list(_VALID_TRIGGERS)}"
        )
    trigger = cast(BackupTrigger, trigger_str)
    meta = create_snapshot(ctx.vault_root, trigger=trigger)

    return ToolResult(
        text=(
            f"created backup {meta.backup_id} "
            f"({meta.file_count} files, {meta.size_bytes} bytes)"
        ),
        data={
            "status": "created",
            "backup_id": meta.backup_id,
            "path": str(meta.path),
            "trigger": meta.trigger,
            "created_at": meta.created_at.isoformat(),
            "size_bytes": meta.size_bytes,
            "file_count": meta.file_count,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
