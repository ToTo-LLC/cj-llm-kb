"""brain_delete_domain — move a top-level vault domain into trash.

Wraps :func:`brain_core.vault.domain.delete_domain`. Three hard rails
enforced at the tool boundary:

1. ``typed_confirm=True`` is mandatory — the frontend collects a typed
   ``"delete"`` string from the user before forwarding the call.
2. The ``personal`` slug is refused unconditionally — the privacy rail
   from ``CLAUDE.md`` means a one-click destroy for personal notes must
   not exist on the default UI path.
3. The last non-``personal`` domain is refused (Plan 10 Task 5) — the
   user cannot accidentally end up with only ``personal`` configured,
   which would leave them no scope for ingest / classify routing.

The folder is ``shutil.move``'d to ``<vault>/.brain/trash/<slug>-<ts>/``
and a ``KIND\tdelete_domain`` undo record is written so
``brain_undo_last`` fully reverses the operation.
"""

from __future__ import annotations

import sys
from typing import Any

from brain_core.config.schema import PRIVACY_RAILED_SLUG
from brain_core.config.writer import persist_config_or_revert
from brain_core.tools.base import ToolContext, ToolResult
from brain_core.vault.domain import delete_domain

NAME = "brain_delete_domain"
DESCRIPTION = (
    "Move a vault domain to <vault>/.brain/trash/ (reversible via brain_undo_last). "
    "Requires typed_confirm=True. Refuses the reserved 'personal' slug unconditionally."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "slug": {"type": "string"},
        "typed_confirm": {
            "type": "boolean",
            "default": False,
            "description": (
                "Must be true. The frontend sets this after the user types the confirmation string."
            ),
        },
    },
    "required": ["slug"],
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    slug = str(arguments["slug"])
    typed_confirm = bool(arguments.get("typed_confirm", False))

    # Plan 10 Task 5 rail 3: refuse to delete the last non-personal
    # configured domain. Without this guard the user could end up with
    # only ``personal`` in Config.domains, which leaves no valid scope
    # for ingest / classify routing (the privacy rail keeps personal
    # excluded from default queries). Counting from Config.domains
    # when present, falling back to on-disk discovery otherwise.
    if slug != PRIVACY_RAILED_SLUG:
        non_personal_count = _count_non_personal_domains(ctx)
        if non_personal_count <= 1:
            raise PermissionError(
                f"refusing to delete {slug!r} — it is the last non-"
                f"{PRIVACY_RAILED_SLUG!r} domain. Removing it would leave "
                f"only {PRIVACY_RAILED_SLUG!r} configured, which has no "
                "valid ingest/classify scope. Add another domain first, "
                "then re-run delete."
            )

    # Plan 11 Task 4: refuse to delete the active domain. Without this
    # guard the persisted Config would carry ``active_domain == slug``
    # but ``domains`` no longer contains it, and the next ``load_config``
    # would reject the file via ``_check_active_domain_in_domains``.
    # The user should switch active_domain first (Settings → Domains).
    cfg = ctx.config
    if cfg is not None and getattr(cfg, "active_domain", None) == slug:
        raise PermissionError(
            f"refusing to delete {slug!r} — it is the active domain. "
            "Switch the active domain first (Settings → Domains), then re-run delete."
        )

    result = delete_domain(ctx.vault_root, slug, typed_confirm=typed_confirm)

    # Plan 10 Task 5 + Plan 11 Task 4: drop the slug from
    # ``Config.domains`` and persist via ``save_config``. The helper
    # reverts the in-memory removal on disk-write failure so the live
    # Config never diverges from disk. The folder is already in trash
    # at this point — even if persistence fails, the data isn't lost
    # (``brain_undo_last`` reverses the move) so the worst case is the
    # caller re-runs ``brain_delete_domain`` after fixing the disk
    # write issue.
    # ``slug`` may not be in cfg.domains (e.g. on-disk-only / D7
    # divergence); skip persistence in that case so we don't write a
    # no-op config update on every divergent delete.
    if cfg is not None and isinstance(getattr(cfg, "domains", None), list) and slug in cfg.domains:
        with persist_config_or_revert(cfg, ctx.vault_root):
            cfg.domains.remove(slug)

    return ToolResult(
        text=(
            f"deleted domain {slug!r} → moved to {result.trash_path} "
            f"(files_moved={result.files_moved}, undo_id={result.undo_id})"
        ),
        data={
            "status": "deleted",
            "slug": result.slug,
            "trash_path": str(result.trash_path),
            "files_moved": result.files_moved,
            "undo_id": result.undo_id,
        },
    )


def _count_non_personal_domains(ctx: ToolContext) -> int:
    """Count configured-or-on-disk domains other than ``personal``.

    Used by the "last non-personal" guard. Reads ``Config.domains``
    when wired in, falls back to a vault-root scan otherwise. The
    fallback exists so admin tools work in test contexts where
    ``ToolContext.config`` is left at ``None``.
    """
    cfg = ctx.config
    if cfg is not None:
        configured = getattr(cfg, "domains", None) or []
        if configured:
            return sum(1 for s in configured if s != PRIVACY_RAILED_SLUG)
    # Fallback: count top-level non-hidden dirs other than ``personal``.
    if not ctx.vault_root.exists():
        return 0
    return sum(
        1
        for child in ctx.vault_root.iterdir()
        if child.is_dir() and not child.name.startswith(".") and child.name != PRIVACY_RAILED_SLUG
    )


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
