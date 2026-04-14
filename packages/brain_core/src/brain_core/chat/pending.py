"""PendingPatchStore — file-per-patch staging queue for chat-proposed vault mutations.

Per Plan 03 D3a, each pending patch is one JSON file at .brain/pending/<patch_id>.json.
Rejected patches move to .brain/pending/rejected/. Applied patches move to .brain/pending/applied/.
Patch IDs are {epoch_ms:013d}-{uuid4hex[:8]} — sortable lexicographically by creation time.

Note: `.brain/` is scratch state, not vault content. Writes here deliberately bypass VaultWriter
(which owns vault content). The `_atomic_write_text` helper provides the same temp+rename
atomicity guarantees inline, cross-platform safe via os.replace.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from brain_core.chat.types import ChatMode
from brain_core.vault.types import PatchSet


class PendingStatus(StrEnum):
    PENDING = "pending"
    REJECTED = "rejected"
    APPLIED = "applied"


class PendingEnvelope(BaseModel):
    patch_id: str
    created_at: datetime
    source_thread: str
    mode: ChatMode
    tool: str
    target_path: Path
    reason: str
    status: PendingStatus = PendingStatus.PENDING
    patchset: PatchSet = Field(...)


def _new_patch_id() -> str:
    ms = int(time.time() * 1000)
    suffix = uuid.uuid4().hex[:8]
    return f"{ms:013d}-{suffix}"


def _atomic_write_text(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


class PendingPatchStore:
    """File-per-patch staging queue rooted at `<vault>/.brain/pending/`."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def put(
        self,
        patchset: PatchSet,
        source_thread: str,
        mode: ChatMode,
        tool: str,
        target_path: Path,
        reason: str,
    ) -> PendingEnvelope:
        """Stage a patchset; returns the envelope with assigned patch_id."""
        env = PendingEnvelope(
            patch_id=_new_patch_id(),
            created_at=datetime.now(UTC),
            source_thread=source_thread,
            mode=mode,
            tool=tool,
            target_path=target_path,
            reason=reason,
            patchset=patchset,
        )
        _atomic_write_text(
            self.root / f"{env.patch_id}.json",
            env.model_dump_json(indent=2),
        )
        return env

    def list(self) -> list[PendingEnvelope]:
        """Return pending envelopes (excludes rejected/applied), sorted by patch_id."""
        if not self.root.exists():
            return []
        out: list[PendingEnvelope] = []
        for f in sorted(self.root.glob("*.json")):
            if f.parent != self.root:
                continue
            out.append(PendingEnvelope.model_validate_json(f.read_text(encoding="utf-8")))
        return out

    def get(self, patch_id: str) -> PendingEnvelope | None:
        """Return a pending envelope by id, or None if absent (rejected/applied count as absent)."""
        f = self.root / f"{patch_id}.json"
        if not f.exists():
            return None
        return PendingEnvelope.model_validate_json(f.read_text(encoding="utf-8"))

    def reject(self, patch_id: str, reason: str) -> None:
        """Move a pending patch to the rejected/ subdir with an updated reason."""
        self._move(patch_id, PendingStatus.REJECTED, reason=reason)

    def mark_applied(self, patch_id: str) -> None:
        """Move a pending patch to the applied/ subdir."""
        self._move(patch_id, PendingStatus.APPLIED, reason=None)

    def _move(self, patch_id: str, new_status: PendingStatus, reason: str | None) -> None:
        src = self.root / f"{patch_id}.json"
        if not src.exists():
            raise KeyError(patch_id)
        env = PendingEnvelope.model_validate_json(src.read_text(encoding="utf-8"))
        env = env.model_copy(
            update={"status": new_status, "reason": reason if reason is not None else env.reason}
        )
        dest_dir = self.root / new_status.value
        dest_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(dest_dir / f"{patch_id}.json", env.model_dump_json(indent=2))
        src.unlink()
