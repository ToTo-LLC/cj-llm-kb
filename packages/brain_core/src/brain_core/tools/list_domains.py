"""brain_list_domains — list top-level domain directories in the vault.

Plan 10 Task 5: returns the *union* of ``Config.domains`` and the on-disk
slug list. The two can diverge (D7 in the plan): the user can edit
``Config.domains`` to remove a slug while the folder stays put — read
paths still work, but the slug is hidden from the UI's allowed-domain
defaults. This tool surfaces both sides so the frontend can render the
divergence (e.g. an "orphan" badge for on-disk-but-not-configured, or
a "missing folder" warning for configured-but-not-on-disk).

Plan 11 Task 6: response gained ``active_domain`` so the frontend
``useDomains()`` hook can hydrate scope state on first mount without a
second round trip (D8 in plan 11). The field is read live from
``ctx.config.active_domain`` (Plan 11 Task 4 guarantees that any mutation
to ``Config.active_domain`` is durable + in-process visible — rename
follows, delete refuses if the slug is active — so the field is always
a member of the response's ``domains`` list).

Response shape (additive vs. v0.1.0 — ``data.domains`` stays
``list[str]`` for backward compat with existing frontend callers):

    {
      "domains": ["personal", "research", "work"],   # sorted union, slug-only
      "entries": [                                    # detailed view (NEW in 0.2)
        {"slug": "personal",  "configured": True,  "on_disk": True},
        {"slug": "research",  "configured": True,  "on_disk": True},
        {"slug": "work",      "configured": True,  "on_disk": False},
        {"slug": "imported",  "configured": False, "on_disk": True}
      ],
      "active_domain": "research"                     # NEW in plan 11 — live from Config
    }
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_list_domains"
DESCRIPTION = (
    "List the top-level domain directories in the vault as the union of "
    "Config.domains (configured) and on-disk folders (discovered). Returns "
    "{domains: [slug], entries: [{slug, configured, on_disk}], active_domain: slug} "
    "sorted by slug."
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


_NO_CONFIG_MESSAGE = (
    "brain_list_domains requires ctx.config to be a Config instance, but "
    "got None. The brain_api lifespan (build_app_context) and brain_mcp "
    "_build_ctx are responsible for threading the loaded Config through "
    "ToolContext; a None config here means the wrapper hasn't wired it in. "
    "Falling back to Config() defaults would make Settings reads lie about "
    "the resolved configuration."
)


def _configured_slugs(ctx: ToolContext) -> list[str]:
    """Return ``ctx.config.domains`` live.

    Plan 13 Task 1 / D1: a ``None`` config is a lifecycle violation, not a
    fallback case. The brain_api lifespan (Plan 11 Task 7) and the brain_mcp
    ``_build_ctx`` (Plan 12 Task 4) are responsible for threading a real
    Config through; raise ``RuntimeError`` if they haven't, mirroring
    ``brain_config_get`` (Plan 12 Task 3 / D5). Silently falling back to
    ``DEFAULT_DOMAINS`` made the response lie about the resolved configuration
    in production-shape paths (Plan 11 lesson 343).
    """
    cfg = ctx.config
    if cfg is None:
        raise RuntimeError(_NO_CONFIG_MESSAGE)
    return list(cfg.domains)


def _active_domain(ctx: ToolContext) -> str:
    """Return ``ctx.config.active_domain`` live.

    Plan 13 Task 1 / D1: same strict policy as ``_configured_slugs``. Plan 11
    Task 6 / D8 added this field so the frontend ``useDomains()`` hook
    hydrates scope on first mount; the Config validator guarantees
    ``active_domain in domains`` so the field always references a slug
    present in the response's ``domains`` list.
    """
    cfg = ctx.config
    if cfg is None:
        raise RuntimeError(_NO_CONFIG_MESSAGE)
    return str(cfg.active_domain)


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
            "active_domain": _active_domain(ctx),
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
