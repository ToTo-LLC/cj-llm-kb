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
            time.sleep(0.01)
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
        time.sleep(0.01)
        b = store.put(
            _sample_patchset(), "t.md", ChatMode.BRAINSTORM, "propose_note", Path("r/b.md"), "x"
        )
        time.sleep(0.01)
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

    def test_reject_actually_moves_via_os_replace(self, store: PendingPatchStore) -> None:
        env = store.put(
            patchset=_sample_patchset(),
            source_thread="t.md",
            mode=ChatMode.BRAINSTORM,
            tool="propose_note",
            target_path=Path("research/n.md"),
            reason="x",
        )
        src = store.root / f"{env.patch_id}.json"
        dest = store.root / "rejected" / f"{env.patch_id}.json"
        store.reject(env.patch_id, reason="user rejected")
        assert not src.exists()
        assert dest.exists()
        from brain_core.chat.pending import PendingEnvelope

        loaded = PendingEnvelope.model_validate_json(dest.read_text(encoding="utf-8"))
        assert loaded.status == PendingStatus.REJECTED
        assert loaded.reason == "user rejected"


class TestCrashRecovery:
    def test_list_skips_stale_pending_with_terminal_status(
        self, store: PendingPatchStore
    ) -> None:
        """Simulate a crash between the two os.replace calls in _move(): the pending/
        file has status=REJECTED on disk but hasn't been moved to rejected/ yet.
        list() must filter it out so the rejected patch doesn't resurrect."""
        env = store.put(
            patchset=_sample_patchset(),
            source_thread="t.md",
            mode=ChatMode.BRAINSTORM,
            tool="propose_note",
            target_path=Path("research/n.md"),
            reason="x",
        )
        src = store.root / f"{env.patch_id}.json"
        stale = env.model_copy(update={"status": PendingStatus.REJECTED})
        src.write_text(stale.model_dump_json(indent=2), encoding="utf-8")
        listed = [e.patch_id for e in store.list()]
        assert env.patch_id not in listed


class TestCrossPlatform:
    def test_patch_id_is_sortable_lexicographically(self, store: PendingPatchStore) -> None:
        first = store.put(
            _sample_patchset(), "t.md", ChatMode.BRAINSTORM, "propose_note", Path("r/a.md"), "x"
        )
        time.sleep(0.01)
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
