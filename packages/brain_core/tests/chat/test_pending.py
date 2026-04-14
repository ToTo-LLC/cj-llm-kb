"""Tests for brain_core.chat.pending.PendingPatchStore."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from brain_core.chat.pending import PendingPatchStore, PendingStatus
from brain_core.chat.types import ChatMode
from brain_core.vault.types import NewFile, PatchSet


def _sample_patchset(text: str = "body") -> PatchSet:
    return PatchSet(
        new_files=[NewFile(path=Path("research/notes/sample.md"), content=f"# sample\n\n{text}")],
        reason="test fixture",
    )


@pytest.fixture
def store(tmp_path: Path) -> PendingPatchStore:
    return PendingPatchStore(tmp_path / ".brain" / "pending")


class TestPutAndList:
    def test_put_creates_pending_file(self, store: PendingPatchStore) -> None:
        env = store.put(
            patchset=_sample_patchset(),
            source_thread="research/2026-04-14-foo.md",
            mode=ChatMode.BRAINSTORM,
            tool="propose_note",
            target_path=Path("research/notes/sample.md"),
            reason="new note from chat",
        )
        assert env.status == PendingStatus.PENDING
        assert (store.root / f"{env.patch_id}.json").exists()

    def test_list_returns_pending_sorted_by_id(self, store: PendingPatchStore) -> None:
        ids = []
        for i in range(3):
            env = store.put(
                patchset=_sample_patchset(f"v{i}"),
                source_thread="t.md",
                mode=ChatMode.BRAINSTORM,
                tool="propose_note",
                target_path=Path(f"research/n{i}.md"),
                reason="x",
            )
            ids.append(env.patch_id)
            time.sleep(0.002)
        listed = [e.patch_id for e in store.list()]
        assert listed == sorted(ids)

    def test_get_round_trip(self, store: PendingPatchStore) -> None:
        env = store.put(
            patchset=_sample_patchset("hello"),
            source_thread="t.md",
            mode=ChatMode.BRAINSTORM,
            tool="propose_note",
            target_path=Path("research/n.md"),
            reason="x",
        )
        loaded = store.get(env.patch_id)
        assert loaded is not None
        assert loaded.patchset.new_files[0].content.endswith("hello")
        assert loaded.mode == ChatMode.BRAINSTORM


class TestRejectAndApply:
    def test_reject_moves_to_rejected_dir(self, store: PendingPatchStore) -> None:
        env = store.put(
            patchset=_sample_patchset(),
            source_thread="t.md",
            mode=ChatMode.BRAINSTORM,
            tool="propose_note",
            target_path=Path("research/n.md"),
            reason="x",
        )
        store.reject(env.patch_id, reason="user rejected")
        assert not (store.root / f"{env.patch_id}.json").exists()
        assert (store.root / "rejected" / f"{env.patch_id}.json").exists()
        assert store.get(env.patch_id) is None

    def test_mark_applied_moves_to_applied_dir(self, store: PendingPatchStore) -> None:
        env = store.put(
            patchset=_sample_patchset(),
            source_thread="t.md",
            mode=ChatMode.BRAINSTORM,
            tool="propose_note",
            target_path=Path("research/n.md"),
            reason="x",
        )
        store.mark_applied(env.patch_id)
        assert not (store.root / f"{env.patch_id}.json").exists()
        assert (store.root / "applied" / f"{env.patch_id}.json").exists()

    def test_list_ignores_rejected_and_applied(self, store: PendingPatchStore) -> None:
        a = store.put(
            _sample_patchset(), "t.md", ChatMode.BRAINSTORM, "propose_note", Path("r/a.md"), "x"
        )
        time.sleep(0.002)
        b = store.put(
            _sample_patchset(), "t.md", ChatMode.BRAINSTORM, "propose_note", Path("r/b.md"), "x"
        )
        time.sleep(0.002)
        c = store.put(
            _sample_patchset(), "t.md", ChatMode.BRAINSTORM, "propose_note", Path("r/c.md"), "x"
        )
        store.reject(a.patch_id, reason="no")
        store.mark_applied(c.patch_id)
        remaining = [e.patch_id for e in store.list()]
        assert remaining == [b.patch_id]

    def test_reject_unknown_id_raises(self, store: PendingPatchStore) -> None:
        with pytest.raises(KeyError):
            store.reject("nonexistent", reason="x")


class TestCrossPlatform:
    def test_patch_id_is_sortable_lexicographically(self, store: PendingPatchStore) -> None:
        first = store.put(
            _sample_patchset(), "t.md", ChatMode.BRAINSTORM, "propose_note", Path("r/a.md"), "x"
        )
        time.sleep(0.002)
        second = store.put(
            _sample_patchset(), "t.md", ChatMode.BRAINSTORM, "propose_note", Path("r/b.md"), "x"
        )
        assert first.patch_id < second.patch_id

    def test_root_created_lazily(self, tmp_path: Path) -> None:
        root = tmp_path / ".brain" / "pending"
        s = PendingPatchStore(root)
        assert not root.exists()
        s.put(_sample_patchset(), "t.md", ChatMode.BRAINSTORM, "propose_note", Path("r/a.md"), "x")
        assert root.exists()
