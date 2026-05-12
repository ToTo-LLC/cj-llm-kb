"""brain_list_orphans — read-only inventory of orphaned vault notes.

Plan 22 T5 / D2 non-destructive orphan policy. Walks the vault under
``Config.domains`` and returns every ``.md`` note whose frontmatter has
``orphaned: true``. Optional ``folder`` filter restricts the response
to notes whose ``watched_folder_id`` matches.

This tool is one of the three explicit ``include_orphans=True`` callers
(per T4): it's literally a tool for inspecting orphan notes. The
scope_guard call below opts in so the default orphan filter doesn't
hide the very rows the user is asking to see.

Read-only — no vault mutation. Safe to call without a writer.
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
from brain_core.vault.paths import scope_guard

NAME = "brain_list_orphans"
DESCRIPTION = (
    "List every vault note marked orphaned: true. Optional folder filter "
    "restricts to notes whose watched_folder_id matches. Returns "
    "{orphans: [{note_path, domain, source_path, orphaned_at, watched_folder_id}]}."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "folder": {
            "type": ["string", "null"],
            "description": (
                "Optional watched-folder path filter. When set, only orphans "
                "whose frontmatter watched_folder_id matches this value are returned."
            ),
        },
    },
}


def _collect_orphans(
    *,
    vault_root: Path,
    domains: list[str],
    allowed_domains: tuple[str, ...],
    folder_filter: str | None,
) -> list[dict[str, Any]]:
    """Walk configured domains and return one entry per orphaned note.

    Notes outside ``allowed_domains`` are skipped (scope_guard would
    raise) — the list reflects what the caller is permitted to see.
    Notes with malformed frontmatter or no domain are skipped silently;
    they cannot be safely attributed.
    """
    orphans: list[dict[str, Any]] = []
    for domain in domains:
        if domain not in allowed_domains:
            continue
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
            if not fm.orphaned:
                continue
            if folder_filter is not None and fm.watched_folder_id != folder_filter:
                continue
            # Belt-and-braces: re-validate the path with include_orphans=True
            # so a caller that scoped allowed_domains tightly still sees a
            # consistent error voice (rather than silent omission).
            scope_guard(
                md_path,
                vault_root=vault_root,
                allowed_domains=allowed_domains,
                include_orphans=True,
            )
            orphans.append(
                {
                    "note_path": str(md_path),
                    "domain": fm.domain,
                    "source_path": fm.source_path,
                    "orphaned_at": (
                        fm.orphaned_at.isoformat() if fm.orphaned_at else None
                    ),
                    "watched_folder_id": fm.watched_folder_id,
                }
            )
    return orphans


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    raise_if_no_config(ctx, "brain_list_orphans")
    folder_filter = arguments.get("folder")
    folder_filter_str: str | None = (
        str(folder_filter) if folder_filter is not None else None
    )
    orphans = _collect_orphans(
        vault_root=ctx.vault_root,
        domains=list(ctx.config.domains),
        allowed_domains=ctx.allowed_domains,
        folder_filter=folder_filter_str,
    )
    text = (
        "\n".join(f"- {o['note_path']} (domain={o['domain']})" for o in orphans)
        if orphans
        else "(no orphans)"
    )
    return ToolResult(text=text, data={"orphans": orphans})


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
