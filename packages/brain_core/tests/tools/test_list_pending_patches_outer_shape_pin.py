"""Plan 19 T4.3 — pin the outer-shape key set of brain_list_pending_patches.

The Plan 18 T2 audit surfaced a cosmetic-severity DRIFT row on the
``brain_list_pending_patches`` handler: backend emits ``{count, patches}``
but the TS wrapper in ``apps/brain_web/src/lib/api/tools.ts`` declared
``{patches: PendingPatch[]}`` only. Plan 19 T4.3 widened the TS wrapper
to include ``count: number``; this pin locks the backend's outer shape
so a future refactor cannot silently drop / rename / add a key without
the TS side lighting up RED first.

Two cases pinned (empty + populated) so a conditional key-add (e.g.
``count`` only present when patches is non-empty) would also fail the
contract. Mirrors the Plan 18 T3 pin pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.types import ChatMode
from brain_core.tools.base import ToolContext
from brain_core.tools.list_pending_patches import handle
from brain_core.vault.types import NewFile, PatchSet


@dataclass
class _EmptyStore:
    """PendingPatchStore stand-in returning an empty list."""

    envelopes: list[Any] = field(default_factory=list)

    def list(self) -> list[Any]:
        return list(self.envelopes)


def _mk_ctx(vault: Path, store: Any) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=store,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )


async def test_list_pending_patches_outer_data_keys_pin_empty(tmp_path: Path) -> None:
    """Plan 19 T4.3: outer shape stable when the store is empty (count=0)."""
    result = await handle({}, _mk_ctx(tmp_path, _EmptyStore()))

    assert result.data is not None
    assert set(result.data.keys()) == {"count", "patches"}
    assert result.data["count"] == 0
    assert result.data["patches"] == []


async def test_list_pending_patches_outer_data_keys_pin_populated(tmp_path: Path) -> None:
    """Plan 19 T4.3: outer shape stable when the store contains envelopes.

    Defense-in-depth — guards against a refactor that conditionally
    emits ``count`` only on the non-empty branch (or vice versa).
    """
    store = PendingPatchStore(tmp_path / ".brain" / "pending")
    store.put(
        patchset=PatchSet(
            new_files=[NewFile(path=Path("research/notes/a.md"), content="a")],
            reason="r",
        ),
        source_thread="thread-1",
        mode=ChatMode.BRAINSTORM,
        tool="brain_propose_note",
        target_path=Path("research/notes/a.md"),
        reason="because",
    )

    result = await handle({}, _mk_ctx(tmp_path, store))

    assert result.data is not None
    assert set(result.data.keys()) == {"count", "patches"}
    assert result.data["count"] == 1
    assert len(result.data["patches"]) == 1
