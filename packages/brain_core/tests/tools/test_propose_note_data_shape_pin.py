"""Plan 19 T4.2 — pin the data-shape key set of brain_propose_note's ToolResult.

The Plan 18 T2 audit surfaced a cosmetic-severity DRIFT row on the
``brain_propose_note`` handler: backend emits
``{status, patch_id, target_path}`` but the TS wrapper in
``apps/brain_web/src/lib/api/tools.ts`` declared
``{patch_id, target_path}`` only. Plan 19 T4.2 widened the TS wrapper to
include ``status: string``; this pin locks the backend's data shape so
a future refactor cannot silently drop / rename / add a key without the
TS side lighting up RED first.

Pin shape: strict set-equality (``set(...) == {...}``). Mirrors the
Plan 18 T3 pin pattern.
"""

from __future__ import annotations

from pathlib import Path

from brain_core.chat.pending import PendingPatchStore
from brain_core.rate_limit import RateLimitConfig, RateLimiter
from brain_core.tools.base import ToolContext
from brain_core.tools.propose_note import handle


def _mk_ctx(vault: Path, store: PendingPatchStore) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=store,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        # Generous bucket — we only stage one patch.
        rate_limiter=RateLimiter(RateLimitConfig(patches_per_minute=60)),
        undo_log=None,
    )


async def test_propose_note_data_keys_pin(tmp_path: Path) -> None:
    """Plan 19 T4.2: brain_propose_note ToolResult.data must be exactly
    ``{status, patch_id, target_path}``.
    """
    store = PendingPatchStore(tmp_path / ".brain" / "pending")
    ctx = _mk_ctx(tmp_path, store)

    result = await handle(
        {
            "path": "research/notes/pin-shape.md",
            "content": "body text",
            "reason": "T4.2 pin",
        },
        ctx,
    )

    assert result.data is not None
    assert set(result.data.keys()) == {"status", "patch_id", "target_path"}
    # Sanity-check value types — pin shape is keys-only but a wrong
    # type at a known key would be a worse drift than a missing key.
    assert result.data["status"] == "pending"
    assert isinstance(result.data["patch_id"], str)
    assert result.data["target_path"] == "research/notes/pin-shape.md"
