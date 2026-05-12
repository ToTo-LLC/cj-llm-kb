"""brain_list_watched_folders — read-only inventory of watched folders.

Plan 22 T5. Returns one entry per :class:`brain_core.config.schema.WatchedFolder`
record in :attr:`Config.watched_folders`, joined with runtime stats walked
from the vault:

* ``file_count`` — number of vault ``.md`` notes whose frontmatter
  ``watched_folder_id`` matches the entry's ``path``.
* ``orphan_count`` — subset of those notes whose ``orphaned == True``.

The walk uses :func:`brain_core.vault.frontmatter.parse_frontmatter` +
:class:`Frontmatter` so the count is consistent with the rest of the
orphan plumbing (T1 schema, T3 mark_orphaned, T4 scope_guard). The walk
restricts itself to ``Config.domains`` directories — a stray file under
``.brain/`` or a non-domain directory can't accidentally count.

Read-only — no vault mutation, no config persistence. Safe to call
without ``typed_confirm`` and without a writer.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from brain_core.tools._errors import raise_if_no_config
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.vault.frontmatter import (
    Frontmatter,
    FrontmatterError,
    parse_frontmatter,
)

NAME = "brain_list_watched_folders"
DESCRIPTION = (
    "List every WatchedFolder in Config.watched_folders with runtime stats "
    "(file_count, orphan_count) computed by walking the vault for notes "
    "whose watched_folder_id matches the entry's path."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
}


def _walk_watched_folder_counts(
    *, vault_root: Path, domains: list[str], folder_path: str
) -> tuple[int, int]:
    """Return ``(file_count, orphan_count)`` for one watched folder.

    Iterates every ``.md`` file under each configured domain directory,
    reads frontmatter, and counts the notes whose ``watched_folder_id``
    matches ``folder_path``. Notes with malformed frontmatter or no
    ``watched_folder_id`` are skipped silently — they cannot be
    attributed to a watched folder.
    """
    file_count = 0
    orphan_count = 0
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
            if fm.watched_folder_id != folder_path:
                continue
            file_count += 1
            if fm.orphaned:
                orphan_count += 1
    return file_count, orphan_count


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    _ = arguments  # no inputs
    raise_if_no_config(ctx, "brain_list_watched_folders")
    cfg = ctx.config

    folders: list[dict[str, Any]] = []
    domains = list(cfg.domains)
    for wf in cfg.watched_folders:
        file_count, orphan_count = _walk_watched_folder_counts(
            vault_root=ctx.vault_root,
            domains=domains,
            folder_path=wf.path,
        )
        folders.append(
            {
                "path": wf.path,
                "domain": wf.domain,
                "enabled": wf.enabled,
                "last_sync": wf.last_sync.isoformat() if wf.last_sync else None,
                "policy": wf.policy,
                "include_subdirs": wf.include_subdirs,
                "file_count": file_count,
                "orphan_count": orphan_count,
            }
        )

    text = (
        "\n".join(
            f"- {f['path']} → {f['domain']} ({f['file_count']} files, "
            f"{f['orphan_count']} orphans)"
            for f in folders
        )
        if folders
        else "(no watched folders)"
    )
    return ToolResult(text=text, data={"folders": folders})


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
