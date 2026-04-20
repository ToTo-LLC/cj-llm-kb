"""brain_apply_patch — apply a staged patch to the vault via VaultWriter.

The only tool entry point that actually mutates the vault. Looks up the
envelope in ``ctx.pending_store``, derives the target domain from the
envelope's ``target_path.parts[0]``, and refuses if that derived domain is
not in ``ctx.allowed_domains``. On success, ``ctx.writer.apply(...)`` runs
the atomic apply and ``ctx.pending_store.mark_applied(patch_id)`` moves the
envelope to ``pending/applied/``.

Belt-and-braces scope check: :class:`VaultWriter` also scope-guards every
path internally, but we do the domain check up front to give a cleaner error
message and avoid starting (then rolling back) an atomic apply. If
``writer.apply`` raises, ``mark_applied`` is never called — the envelope
stays in ``pending/`` so the user can retry or reject it.

Rate limiter consumes from the ``patches`` bucket (cost=1) BEFORE any other
work so a refused call is cheap and deterministic (matches the pattern in
``brain_propose_note``).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.vault.paths import ScopeError

NAME = "brain_apply_patch"
DESCRIPTION = (
    "Apply a staged patch to the vault. Routes through VaultWriter; "
    "moves the envelope to pending/applied/ on success."
)
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "patch_id": {
            "type": "string",
            "description": "The patch_id returned by a prior staging tool (e.g. brain_propose_note).",
        },
    },
    "required": ["patch_id"],
}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    # Rate-limit check FIRST — a refused call must not read the envelope
    # or touch the writer. Raises RateLimitError on drain; transport/caller
    # converts to the response shape.
    ctx.rate_limiter.check("patches", cost=1)

    patch_id = str(arguments["patch_id"])
    envelope = ctx.pending_store.get(patch_id)
    if envelope is None:
        raise KeyError(f"patch {patch_id!r} not found")

    # Derive domain from the target path; must be in allowed_domains. This is
    # a defensive check above and beyond VaultWriter.apply's internal
    # scope_guard — it gives the caller a cleaner error message and avoids
    # partial work.
    target_parts = envelope.target_path.parts
    if not target_parts:
        raise ValueError(f"cannot derive domain from target_path {envelope.target_path!r}")
    domain = target_parts[0]
    if domain not in ctx.allowed_domains:
        raise ScopeError(f"patch targets domain {domain!r} not in allowed {ctx.allowed_domains}")

    # Staging tools (brain_propose_note) record vault-relative paths in the
    # envelope for portability. Plan 04 Task 25 fix: VaultWriter.apply now
    # absolutizes vault-relative paths against vault_root before scope_guard,
    # so we can pass the envelope's patchset through unchanged.
    receipt = ctx.writer.apply(envelope.patchset, allowed_domains=(domain,))
    # Only mark applied after a successful writer.apply. If apply raised, the
    # envelope stays in pending/ — correct, because the patch did not land.
    ctx.pending_store.mark_applied(patch_id)

    # Re-express applied_files as vault-relative POSIX strings so the caller
    # sees a stable, cross-platform representation.
    applied_rel = [_rel_to_vault(p, ctx.vault_root).as_posix() for p in receipt.applied_files]
    return ToolResult(
        text=f"applied patch {patch_id} → {len(receipt.applied_files)} file(s)",
        data={
            "status": "applied",
            "patch_id": patch_id,
            "undo_id": receipt.undo_id,
            "applied_files": applied_rel,
        },
    )


def _rel_to_vault(p: Path, vault_root: Path) -> Path:
    """Return `p` as vault-relative. If p is already relative, return as-is."""
    if not p.is_absolute():
        return p
    try:
        return p.resolve().relative_to(vault_root.resolve())
    except ValueError:
        # Defensive: writer only emits in-vault paths, but if something is
        # outside, fall back to the absolute path so we don't crash the tool
        # response.
        return p


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402

_tools.register(sys.modules[__name__])
