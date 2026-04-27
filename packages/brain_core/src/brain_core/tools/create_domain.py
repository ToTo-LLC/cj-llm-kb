"""brain_create_domain — create a new top-level vault domain.

Creates ``<vault>/<slug>/`` plus the canonical ``index.md`` + ``log.md``
seed pair. Plan 10 Task 5 routes slug validation through
``brain_core.config.schema._validate_domain_slug`` (the D2 rules:
``^[a-z][a-z0-9_-]{0,30}$``, no leading digit/``_``/``-``, no trailing
``_``/``-``, no path separators). This means the rules now match
``Config.domains`` validation 1:1 — the slug a user creates here is by
definition acceptable for in-place ``Config.domains.append(slug)``.

The domain folder is created via ``mkdir`` rather than via a PatchSet —
PatchSets are scope-guarded against ``allowed_domains``, and a brand-new
domain is by definition not in that allowlist yet. ``brain_rename_domain``
faces the same chicken-and-egg constraint and is documented as the second
exception in Plan 07 pre-flight D2a; ``brain_create_domain`` is the
companion (D2b in spirit). The atomic-cleanup branch (try/except) ensures
that a partial create (folder + index but no log) leaves the vault as it
was found.

Plan 10 Task 5: after a successful create, the slug is appended to
``ctx.config.domains``. Plan 11 Task 4 wires :func:`persist_config_or_revert`
around the append so the new slug is persisted to
``<vault>/.brain/config.json`` via :func:`save_config`. If the disk
write fails, the in-memory append is reverted and
``ConfigPersistenceError`` propagates so the caller (UI, MCP, CLI) can
surface the failure. The on-disk domain folder created above is left
in place even on persistence failure — the caller can re-run the tool
once the write issue is resolved (the folder-already-exists guard will
then fail-fast and the caller can choose to retry or rip the folder).

The persistence step is skipped when ``ctx.config`` is ``None`` (low-level
tests, harness contexts that don't wire config) — the on-disk folder
still exists, so ``brain_list_domains`` would still surface the slug as
``on_disk=True, configured=False``.
"""

from __future__ import annotations

import shutil
import sys
from datetime import UTC, datetime
from typing import Any

from brain_core.config.schema import _validate_domain_slug
from brain_core.config.writer import persist_config_or_revert
from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_create_domain"
DESCRIPTION = (
    "Create a new top-level vault domain (folder + seed index.md + log.md). "
    "Slug must match the Plan 10 D2 rules (^[a-z][a-z0-9_-]{0,30}$, no "
    "leading digit/_/-, no trailing _/-, no path separators). Fails if the "
    "slug already exists."
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

    # Plan 10 D2: slug rules now live on the schema module so create
    # and Config.domains validation can't drift. ``_validate_domain_slug``
    # raises ValueError with a slug-specific message that the UI can
    # surface verbatim.
    _validate_domain_slug(slug)

    # Reject if the slug is already in Config.domains. The on-disk
    # check below catches the common case (folder exists), but a slug
    # configured-without-folder (D7's allowed divergence) would slip
    # past that check — explicit Config.domains check covers it.
    cfg = ctx.config
    if cfg is not None and slug in (getattr(cfg, "domains", None) or []):
        raise FileExistsError(
            f"domain {slug!r} is already in Config.domains. Remove it from "
            "Settings → Domains first, or pick a different slug."
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

    # Plan 10 Task 5 + Plan 11 Task 4: append to ``Config.domains`` and
    # persist via ``save_config``. The helper snapshots first, mutates
    # in-place, persists, and reverts the in-memory append on disk-write
    # failure (so disk and memory never diverge). Persistence is skipped
    # when ``ctx.config`` is ``None`` — the on-disk folder still exists
    # and ``brain_list_domains`` will surface it as ``on_disk=True,
    # configured=False``.
    if cfg is not None and isinstance(getattr(cfg, "domains", None), list):
        with persist_config_or_revert(cfg, ctx.vault_root):
            cfg.domains.append(slug)

    domain = {"slug": slug, "name": name, "accent_color": accent_color}
    return ToolResult(
        text=f"created domain {slug!r} (name={name!r})",
        data={
            "status": "created",
            "domain": domain,
            "note": (
                "Slug appended to Config.domains and persisted to "
                "<vault>/.brain/config.json via save_config()."
            ),
        },
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
