"""brain_list_domains — list top-level domain directories in the vault.

Plan 10 Task 5: returns the *union* of ``Config.domains`` and the on-disk
slug list. The two can diverge (D7 in the plan): the user can edit
``Config.domains`` to remove a slug while the folder stays put — read
paths still work, but the slug is hidden from the UI's allowed-domain
defaults. This tool surfaces both sides so the frontend can render the
divergence (e.g. an "orphan" badge for on-disk-but-not-configured, or
a "missing folder" warning for configured-but-not-on-disk).

Response shape (additive vs. v0.1.0 — ``data.domains`` stays
``list[str]`` for backward compat with existing frontend callers):

    {
      "domains": ["personal", "research", "work"],   # sorted union, slug-only
      "entries": [                                    # detailed view (NEW in 0.2)
        {"slug": "personal",  "configured": True,  "on_disk": True},
        {"slug": "research",  "configured": True,  "on_disk": True},
        {"slug": "work",      "configured": True,  "on_disk": False},
        {"slug": "imported",  "configured": False, "on_disk": True}
      ]
    }
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.config.schema import DEFAULT_DOMAINS
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_list_domains"
DESCRIPTION = (
    "List the top-level domain directories in the vault as the union of "
    "Config.domains (configured) and on-disk folders (discovered). Returns "
    "{domains: [slug], entries: [{slug, configured, on_disk}]} sorted by slug."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
}


def _on_disk_slugs(vault_root: Any) -> set[str]:
    """Walk vault_root for top-level dirs that look like a domain folder.

    Heuristic for "looks like a domain folder" matches the v0.1 list_domains
    behavior: top-level non-hidden dir AND (has an ``index.md`` OR contains
    any ``*.md`` recursively). Empty-but-named directories aren't surfaced
    so a stray ``mkdir`` doesn't pollute the list. Hidden dirs (``.brain``,
    ``.git``) are skipped unconditionally.
    """
    found: set[str] = set()
    if not vault_root.exists():
        return found
    for child in vault_root.iterdir():
        if not child.is_dir():
            continue
        if child.name.startswith("."):
            continue
        if (child / "index.md").exists() or any(child.rglob("*.md")):
            found.add(child.name)
    return found


def _configured_slugs(ctx: ToolContext) -> list[str]:
    """Return ``ctx.config.domains`` if a config is wired in, else the v0.1 default tuple.

    The fallback exists so admin tools work in low-level tests / harness
    contexts where ``ToolContext.config`` is left at ``None`` (the docstring
    on ToolContext explicitly calls this out — 56+ construction sites still
    leave it ``None``). Plan 10 Task 4 / future re-wiring will plumb the
    real config into every brain_api / brain_mcp tool path.
    """
    cfg = ctx.config
    if cfg is not None and getattr(cfg, "domains", None):
        return list(cfg.domains)
    return list(DEFAULT_DOMAINS)


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    _ = arguments  # no inputs

    configured = _configured_slugs(ctx)
    configured_set: set[str] = set(configured)
    on_disk = _on_disk_slugs(ctx.vault_root)

    union = sorted(configured_set | on_disk)
    entries = [
        {
            "slug": slug,
            "configured": slug in configured_set,
            "on_disk": slug in on_disk,
        }
        for slug in union
    ]
    text = "\n".join(f"- {d}" for d in union) if union else "(no domains)"
    return ToolResult(
        text=text,
        data={
            "domains": union,
            "entries": entries,
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
