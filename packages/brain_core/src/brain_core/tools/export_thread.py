"""brain_export_thread — return a chat thread's markdown for client-side download.

Thread files live at ``<domain>/chats/<thread_id>.md`` (see
:class:`brain_core.chat.persistence.ThreadPersistence`); they're already
markdown, with YAML frontmatter (``mode``, ``scope``, ``model``,
``created``, ``updated``, ``turns``, ``cost_usd``) and one ``## User``
/ ``## Assistant`` / ``## System`` section per turn. This tool reads
the file and returns it as ``data.markdown`` so the frontend can save
it as a download.

The tool searches for the thread file across ``ctx.allowed_domains``
(scope-guarded — a thread in ``personal`` won't surface in a research-
scoped session). Returns 404 (FileNotFoundError) when the thread isn't
found in any allowed domain.

Issue #17 in ``docs/v0.1.0-known-issues.md``.
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_export_thread"
DESCRIPTION = (
    "Read a chat thread's markdown file from the vault and return its "
    "contents (frontmatter + per-turn sections). The frontend turns "
    "the response into a downloadable .md file. Searches across "
    "allowed_domains; raises FileNotFoundError when the thread is "
    "absent or out-of-scope."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "thread_id": {
            "type": "string",
            "description": (
                "The thread identifier (without ``.md``). Resolves to "
                "``<domain>/chats/<thread_id>.md`` for some domain in "
                "``ctx.allowed_domains``."
            ),
        },
    },
    "required": ["thread_id"],
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    thread_id_arg = arguments.get("thread_id")
    if not isinstance(thread_id_arg, str) or not thread_id_arg:
        raise ValueError("thread_id must be a non-empty string")

    # Defense in depth: refuse path-segment characters so a malicious
    # caller can't traverse out of the chats directory. Slugs from
    # ChatSession are URL-safe; this just pins the contract.
    if "/" in thread_id_arg or "\\" in thread_id_arg or thread_id_arg.startswith("."):
        raise ValueError(
            f"thread_id must be a plain slug, got {thread_id_arg!r}"
        )

    for domain in ctx.allowed_domains:
        candidate = ctx.vault_root / domain / "chats" / f"{thread_id_arg}.md"
        if candidate.exists():
            markdown = candidate.read_text(encoding="utf-8")
            rel_path = candidate.relative_to(ctx.vault_root).as_posix()
            return ToolResult(
                text=f"exported {rel_path} ({len(markdown)} chars)",
                data={
                    "thread_id": thread_id_arg,
                    "path": rel_path,
                    "domain": domain,
                    "markdown": markdown,
                    "filename": f"{thread_id_arg}.md",
                    "byte_length": len(markdown.encode("utf-8")),
                },
            )

    raise FileNotFoundError(
        f"thread {thread_id_arg!r} not found in any allowed domain "
        f"({', '.join(ctx.allowed_domains)})"
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
