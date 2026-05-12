"""brain_unwatch_folder — remove a WatchedFolder entry from Config.

Plan 22 T5 / D2 non-destructive policy. Removes the matching
:class:`brain_core.config.schema.WatchedFolder` entry from
:attr:`Config.watched_folders`. Existing vault notes stay on disk —
no body changes, no orphan-mark flip. Notes already marked
``orphaned: true`` (from prior watcher events) STAY orphaned: the user
adjudicates them via ``brain_restore_orphan`` / ``brain_delete_orphan``.

Persistence routes through :func:`persist_config_or_revert` so the
write is atomic + snapshot-revertible. The ``remaining_notes`` counter
in the response is computed by walking the vault for notes whose
frontmatter ``watched_folder_id`` matches — it's a "you still have N
notes linked to this folder" advisory, not a guard.

Idempotent on a folder that isn't watched: returns
``status: "not_watched"`` rather than raising.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from brain_core.config.writer import persist_config_or_revert
from brain_core.tools._errors import raise_if_no_config
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.vault.frontmatter import (
    Frontmatter,
    FrontmatterError,
    parse_frontmatter,
)

NAME = "brain_unwatch_folder"
DESCRIPTION = (
    "Remove the matching WatchedFolder entry from Config.watched_folders. "
    "Existing notes stay on disk; orphans remain marked. Idempotent: "
    "returns status='not_watched' if the folder isn't in the config."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "folder": {
            "type": "string",
            "description": "Absolute path of the folder to stop watching.",
        },
    },
    "required": ["folder"],
}


def _count_notes_for_folder(
    *, vault_root: Path, domains: list[str], folder_path: str
) -> int:
    """Count vault ``.md`` notes whose ``watched_folder_id == folder_path``."""
    count = 0
    for domain in domains:
        domain_dir = vault_root / domain
        if not domain_dir.exists() or not domain_dir.is_dir():
            continue
        for md_path in domain_dir.rglob("*.md"):
            if not md_path.is_file():
                continue
            try:
                fm_dict, _body = parse_frontmatter(
                    md_path.read_text(encoding="utf-8")
                )
                fm = Frontmatter.from_dict(fm_dict)
            except (OSError, UnicodeDecodeError, FrontmatterError):
                continue
            if fm.watched_folder_id == folder_path:
                count += 1
    return count


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    folder = str(arguments["folder"])
    raise_if_no_config(ctx, "brain_unwatch_folder")
    cfg = ctx.config

    # Locate the matching entry. We compare on the raw ``path`` string so a
    # round-trip from disk (already normalized) lines up exactly. Callers
    # that want loose matching (e.g. ~ expansion) should resolve before
    # invoking.
    match_index: int | None = None
    for i, wf in enumerate(cfg.watched_folders):
        if wf.path == folder:
            match_index = i
            break

    if match_index is None:
        return ToolResult(
            text=f"folder {folder!r} is not watched",
            data={
                "status": "not_watched",
                "folder": folder,
                "remaining_notes": _count_notes_for_folder(
                    vault_root=ctx.vault_root,
                    domains=list(cfg.domains),
                    folder_path=folder,
                ),
            },
        )

    # Mutate inside the snapshot-revert context so the on-disk write is
    # atomic and the in-memory Config rolls back on persistence failure.
    with persist_config_or_revert(cfg, ctx.vault_root):
        del cfg.watched_folders[match_index]

    remaining = _count_notes_for_folder(
        vault_root=ctx.vault_root,
        domains=list(cfg.domains),
        folder_path=folder,
    )
    return ToolResult(
        text=f"unwatched {folder} ({remaining} note(s) still linked)",
        data={
            "status": "unwatched",
            "folder": folder,
            "remaining_notes": remaining,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
