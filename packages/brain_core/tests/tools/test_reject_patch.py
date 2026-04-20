"""Smoke test for brain_core.tools.reject_patch — ToolResult shape.

Uses a tiny in-memory store that records reject calls, so we verify the
ToolResult shape + that the store is invoked correctly without needing the
full PendingPatchStore's disk plumbing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.reject_patch import NAME, handle


@dataclass
class _RecordingStore:
    """PendingPatchStore stand-in: record reject calls."""

    rejects: list[tuple[str, str]] = field(default_factory=list)

    def reject(self, patch_id: str, *, reason: str) -> None:
        self.rejects.append((patch_id, reason))


def _mk_ctx(vault: Path, store: _RecordingStore) -> ToolContext:
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


def test_name() -> None:
    assert NAME == "brain_reject_patch"


async def test_reject_invokes_store_and_returns_metadata(tmp_path: Path) -> None:
    store = _RecordingStore()
    result = await handle(
        {"patch_id": "p-123", "reason": "not needed"},
        _mk_ctx(tmp_path, store),
    )

    assert isinstance(result, ToolResult)
    assert store.rejects == [("p-123", "not needed")]
    assert result.data is not None
    assert result.data["status"] == "rejected"
    assert result.data["patch_id"] == "p-123"
    assert result.data["reason"] == "not needed"
