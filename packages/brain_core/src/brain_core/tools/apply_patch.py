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

Plan 07 Task 1: the autonomy gate (:func:`brain_core.autonomy.should_auto_apply`)
is consulted AFTER the scope check. A patch whose category is opted into
auto-apply in :class:`~brain_core.config.schema.AutonomousConfig` returns
``status="auto_applied"`` instead of ``"applied"`` so the UI can distinguish
policy-applied patches from human-approved ones. Both paths call
``writer.apply`` and ``mark_applied`` identically and record to the undo log,
so ``brain_undo_last`` can revert either. ``PatchCategory.OTHER`` — the
default for any PatchSet that doesn't explicitly opt in — never auto-applies.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from brain_core.autonomy import should_auto_apply
from brain_core.config.schema import Config
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

    # Autonomy gate — consult config BEFORE the apply so a non-auto patch
    # still follows the same approval-gated flow (Plan 04 semantics). The
    # session has no in-flight Config object; ``_resolve_config`` snapshots
    # defaults and overlays the session vault_root (mirrors
    # ``brain_config_get``). Plan 07 Task 5 wires persisted config here;
    # until then, ``_resolve_config`` is the extension point for tests to
    # monkeypatch a specific ``AutonomousConfig``.
    config = _resolve_config(ctx)
    auto_applied = should_auto_apply(envelope.patchset, config)

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
    status = "auto_applied" if auto_applied else "applied"
    prefix = "auto-applied" if auto_applied else "applied"
    return ToolResult(
        text=f"{prefix} patch {patch_id} → {len(receipt.applied_files)} file(s)",
        data={
            "status": status,
            "patch_id": patch_id,
            "undo_id": receipt.undo_id,
            "applied_files": applied_rel,
        },
    )


def _resolve_config(ctx: ToolContext) -> Config:
    """Snapshot a defaults-backed Config with the session vault_root overlaid.

    Mirrors the ``brain_config_get`` approach — no env / config-file read here
    to keep the handler deterministic under test. Plan 07 Task 5 replaces the
    body with a real loader call; Task 1 tests monkeypatch this function to
    supply a custom :class:`AutonomousConfig`.
    """
    return Config(vault_path=ctx.vault_root)


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
