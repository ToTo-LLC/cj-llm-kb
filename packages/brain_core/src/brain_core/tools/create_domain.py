"""brain_create_domain — create a new top-level vault domain.

Creates ``<vault>/<slug>/`` plus the canonical ``index.md`` + ``log.md``
seed pair. Fails if the slug fails ``^[a-z][a-z0-9-]{1,24}$`` or if a
folder with that slug already exists.

The domain folder is created via ``mkdir`` rather than via a PatchSet —
PatchSets are scope-guarded against ``allowed_domains``, and a brand-new
domain is by definition not in that allowlist yet. ``brain_rename_domain``
faces the same chicken-and-egg constraint and is documented as the second
exception in Plan 07 pre-flight D2a; ``brain_create_domain`` is the
companion (D2b in spirit). The atomic-cleanup branch (try/except) ensures
that a partial create (folder + index but no log) leaves the vault as it
was found.

Slug appendage to ``config.domain_order`` is deferred to Plan 07 Task 5
(real config persistence). For now the returned ``data['domain_order']``
field surfaces the new slug so the frontend can mirror the expected order
client-side.
"""

from __future__ import annotations

import re
import shutil
import sys
from datetime import UTC, datetime
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_create_domain"
DESCRIPTION = (
    "Create a new top-level vault domain (folder + seed index.md + log.md). "
    "Slug must match ^[a-z][a-z0-9-]{1,24}$. Fails if the slug already exists."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "slug": {"type": "string"},
        "name": {"type": "string"},
        "accent_color": {
            "type": "string",
            "default": "#888888",
            "description": "Hex color for the domain pill in the UI.",
        },
    },
    "required": ["slug", "name"],
}

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,24}$")


def _seed_index_md(name: str) -> str:
    today = datetime.now(tz=UTC).date().isoformat()
    fm = f"---\ntitle: {name}\ntype: index\ncreated: {today}\nupdated: {today}\n---\n\n"
    body = (
        f"# {name}\n\n"
        f"Top-level index for the {name} domain. Add wikilinks to the "
        f"key notes in this domain below as the wiki grows.\n"
    )
    return fm + body


def _seed_log_md(name: str) -> str:
    today = datetime.now(tz=UTC).date().isoformat()
    fm = f"---\ntitle: {name} log\ntype: log\ncreated: {today}\n---\n\n"
    body = f"# {name} log\n\n"
    return fm + body


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    slug = str(arguments["slug"])
    name = str(arguments["name"])
    accent_color = str(arguments.get("accent_color", "#888888"))

    if not _SLUG_RE.match(slug):
        raise ValueError(
            f"slug {slug!r} must match ^[a-z][a-z0-9-]{{1,24}}$ "
            "(lowercase letter then up to 24 lowercase alnum/hyphen chars)"
        )

    domain_dir = ctx.vault_root / slug
    if domain_dir.exists():
        raise FileExistsError(f"domain {slug!r} already exists at {domain_dir}")

    # Atomic-ish create: if any step fails, rip the folder out so the vault
    # looks unchanged. ``shutil.rmtree`` is best-effort cleanup; ``ignore_errors``
    # so we never mask the original exception with a teardown failure.
    try:
        domain_dir.mkdir(parents=True, exist_ok=False)
        index_path = domain_dir / "index.md"
        log_path = domain_dir / "log.md"
        index_path.write_text(_seed_index_md(name), encoding="utf-8", newline="\n")
        log_path.write_text(_seed_log_md(name), encoding="utf-8", newline="\n")
    except BaseException:
        if domain_dir.exists():
            shutil.rmtree(domain_dir, ignore_errors=True)
        raise

    domain = {"slug": slug, "name": name, "accent_color": accent_color}
    return ToolResult(
        text=f"created domain {slug!r} (name={name!r})",
        data={
            "status": "created",
            "domain": domain,
            "note": (
                "Plan 07 Task 4: domain_order persistence lands in Task 5. "
                "Append this slug to your client-side domain_order until then."
            ),
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
