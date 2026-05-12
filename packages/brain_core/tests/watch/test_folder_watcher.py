"""Plan 22 T6 — pin tests for :class:`WatchedFolderWatcher`.

Pinned coverage:

* (1) start / stop lifecycle: observer thread starts + stops cleanly,
  no hanging threads.
* (2) ``FileCreatedEvent`` → ``pipeline.ingest`` with the folder's
  domain_override.
* (3) ``FileModifiedEvent`` on a mapped path → ``pipeline.update_source``.
* (4) ``FileModifiedEvent`` on an UNMAPPED path → fall through to
  ``pipeline.ingest`` (cache miss = treat as new).
* (5) ``FileDeletedEvent`` on a mapped path → ``pipeline.mark_orphaned``.
* (6) ``FileDeletedEvent`` on an unmapped path → no pipeline call.
* (7) ``FileMovedEvent`` → synthetic delete + create (v1 behavior, no
  content-hash-aware move detection per Plan 22 §T6).
* (8) Debounce: two rapid events on the same path within the window
  collapse to ONE pipeline call.
* (9) Hidden / unclaimed files are filtered out before pipeline routing.
* (10) Pipeline exception in dispatch does not kill the observer
  thread.

All tests use :class:`PollingObserver` for deterministic event
delivery (FSEvents / ReadDirectoryChangesW behavior varies in CI).
The pipeline is replaced with a typed :class:`_FakePipeline` so we
never run a real LLM round-trip. The watcher is constructed inside
an ``asyncio`` event loop (via :func:`pytest.mark.asyncio` /
``asyncio.run``) so the ``run_coroutine_threadsafe`` bridge has a
target loop to schedule onto — matching the production lifespan
seam.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from brain_core.config.schema import WatchedFolder
from brain_core.ingest.types import IngestResult, IngestStatus
from brain_core.watch.folder_watcher import (
    WatchedFolderWatcher,
    _index_vault_for_folder,
)
from watchdog.observers.polling import PollingObserver


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------
@dataclass
class _IngestCall:
    spec: Path | str
    domain_override: str | None
    allowed_domains: tuple[str, ...]


@dataclass
class _UpdateCall:
    existing_note_path: Path
    new_source_path: Path
    allowed_domains: tuple[str, ...]


@dataclass
class _OrphanCall:
    existing_note_path: Path
    allowed_domains: tuple[str, ...]


class _FakePipeline:
    """Minimal stand-in for :class:`IngestPipeline` exposing the 3 routed methods.

    The watcher only calls ``ingest`` / ``update_source`` (both async)
    and ``mark_orphaned`` (sync). Everything else from the real
    pipeline (``_classify_with_cost``, etc.) is irrelevant here, so
    we don't model it.
    """

    def __init__(self, vault_root: Path) -> None:
        self.vault_root = vault_root
        self.ingest_calls: list[_IngestCall] = []
        self.update_calls: list[_UpdateCall] = []
        self.orphan_calls: list[_OrphanCall] = []
        self._lock = threading.Lock()
        self._ingest_event = threading.Event()
        self._update_event = threading.Event()
        self._orphan_event = threading.Event()
        # When set, the next call to the named method raises this
        # exception. Lets us pin the "observer survives a failing
        # dispatch" branch deterministically.
        self.next_raise_ingest: Exception | None = None

    async def ingest(
        self,
        spec: Path | str,
        *,
        allowed_domains: tuple[str, ...],
        domain_override: str | None = None,
        apply: bool = True,
    ) -> IngestResult:
        with self._lock:
            self.ingest_calls.append(
                _IngestCall(
                    spec=spec,
                    domain_override=domain_override,
                    allowed_domains=allowed_domains,
                )
            )
            self._ingest_event.set()
            if self.next_raise_ingest is not None:
                exc = self.next_raise_ingest
                self.next_raise_ingest = None
                raise exc
        return IngestResult(status=IngestStatus.OK, note_path=None)

    async def update_source(
        self,
        existing_note_path: Path,
        new_source_path: Path,
        *,
        allowed_domains: tuple[str, ...],
    ) -> IngestResult:
        with self._lock:
            self.update_calls.append(
                _UpdateCall(
                    existing_note_path=existing_note_path,
                    new_source_path=new_source_path,
                    allowed_domains=allowed_domains,
                )
            )
            self._update_event.set()
        return IngestResult(
            status=IngestStatus.OK, note_path=existing_note_path
        )

    def mark_orphaned(
        self,
        existing_note_path: Path,
        *,
        allowed_domains: tuple[str, ...],
    ) -> IngestResult:
        with self._lock:
            self.orphan_calls.append(
                _OrphanCall(
                    existing_note_path=existing_note_path,
                    allowed_domains=allowed_domains,
                )
            )
            self._orphan_event.set()
        return IngestResult(status=IngestStatus.OK, note_path=existing_note_path)


@dataclass
class _StubHandler:
    """``can_handle``-only stub. ``extract`` is never called by the watcher."""

    accept_suffixes: tuple[str, ...] = (".txt", ".md")
    accept_paths: bool = True

    def can_handle(self, spec: object) -> bool:
        if isinstance(spec, Path):
            return self.accept_paths and spec.suffix in self.accept_suffixes
        return False

    async def extract(self, *_: Any, **__: Any) -> Any:  # pragma: no cover
        raise NotImplementedError("watcher should never reach extract()")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_note(
    *,
    vault: Path,
    domain: str,
    slug: str,
    source_path: Path,
    folder_path: str,
    orphaned: bool = False,
) -> Path:
    """Write a minimal source note with the frontmatter fields the watcher reads.

    Body is irrelevant — the watcher only reads frontmatter to build
    its source-path → note-path cache.
    """
    note = vault / domain / "sources" / f"{slug}.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "---\n"
        f"title: {slug}\n"
        f"domain: {domain}\n"
        "type: source\n"
        "created: 2025-01-01\n"
        "updated: 2025-01-01\n"
        f"source_path: {source_path}\n"
        f"watched_folder_id: {folder_path}\n"
        f"orphaned: {'true' if orphaned else 'false'}\n"
        "content_hash: deadbeef\n"
        "---\n\n"
        f"# {slug}\n\nbody.\n"
    )
    note.write_text(body, encoding="utf-8")
    return note


def _scaffold_vault(tmp_path: Path) -> Path:
    """Minimal vault that ``_index_vault_for_folder`` can walk."""
    vault = tmp_path / "brain"
    vault.mkdir()
    for domain in ("research",):
        d = vault / domain
        d.mkdir()
        (d / "sources").mkdir()
    return vault


async def _wait_async(
    predicate: Callable[[], bool],
    *,
    timeout: float = 5.0,
    poll: float = 0.05,
) -> bool:
    """Async poll — sleeps via ``asyncio.sleep`` so the event loop stays live.

    The watcher schedules pipeline coroutines onto the loop via
    ``run_coroutine_threadsafe``; if we blocked the loop with
    ``time.sleep`` those coroutines would never get a chance to run
    and every test would time out. Using ``asyncio.sleep`` lets the
    loop service the watchdog → loop bridge.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(poll)
    return False


def _build_watcher(
    *,
    folders: list[WatchedFolder],
    pipeline: _FakePipeline,
    debounce_ms: int = 100,
) -> WatchedFolderWatcher:
    """Construct a watcher with PollingObserver + the stub handler list.

    The polling observer's default polling interval is 1 second, which
    is too coarse for tight test runs. We use the factory closure to
    pass ``timeout=0.1`` so events surface inside the ~5s test budget.
    """
    return WatchedFolderWatcher(
        observers=folders,
        pipeline=pipeline,  # type: ignore[arg-type]
        debounce_ms=debounce_ms,
        handlers=[_StubHandler()],
        observer_factory=lambda: PollingObserver(timeout=0.1),
    )


# ---------------------------------------------------------------------------
# (1) Lifecycle
# ---------------------------------------------------------------------------
async def test_start_stop_lifecycle_clean(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched"
    folder.mkdir()
    pipe = _FakePipeline(vault)
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipe,
    )

    # Before start: stop is a no-op (idempotent guarantee).
    watcher.stop()

    watcher.start()
    # Idempotent: second start is a no-op.
    watcher.start()
    assert watcher._started is True  # type: ignore[attr-defined]

    watcher.stop()
    # Idempotent stop after a real stop.
    watcher.stop()
    assert watcher._started is False  # type: ignore[attr-defined]
    # Observer thread must have joined — no rogue daemon left running.
    if watcher._observer is not None:  # type: ignore[attr-defined]
        # _observer is cleared in stop(); if a defensive branch left
        # it populated the join must still have succeeded.
        assert not watcher._observer.is_alive()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# (2) FileCreatedEvent → ingest
# ---------------------------------------------------------------------------
async def test_on_created_routes_to_ingest(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched"
    folder.mkdir()
    pipe = _FakePipeline(vault)
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipe,
    )
    watcher.start()
    try:
        src = folder / "hello.txt"
        src.write_text("hi there", encoding="utf-8")

        assert await _wait_async(lambda: len(pipe.ingest_calls) >= 1)
        call = pipe.ingest_calls[0]
        assert Path(str(call.spec)).resolve() == src.resolve()
        assert call.domain_override == "research"
    finally:
        watcher.stop()


# ---------------------------------------------------------------------------
# (3) FileModifiedEvent on mapped path → update_source
# ---------------------------------------------------------------------------
async def test_on_modified_mapped_routes_to_update_source(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched"
    folder.mkdir()
    src = folder / "doc.txt"
    src.write_text("v1", encoding="utf-8")
    # Pre-seed a vault note that frontmatter-points at this source.
    note = _make_note(
        vault=vault,
        domain="research",
        slug="doc",
        source_path=src.resolve(),
        folder_path=str(folder),
    )
    pipe = _FakePipeline(vault)
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipe,
    )
    watcher.start()
    try:
        # Modify the existing file. The watcher's lazy cache walk
        # should map src → note; the event lands in update_source.
        src.write_text("v2", encoding="utf-8")
        assert await _wait_async(lambda: len(pipe.update_calls) >= 1)
        call = pipe.update_calls[0]
        assert call.existing_note_path == note
        assert call.new_source_path.resolve() == src.resolve()
        # And NOT in ingest — modify on a mapped path is update only.
        assert pipe.ingest_calls == []
    finally:
        watcher.stop()


# ---------------------------------------------------------------------------
# (4) FileModifiedEvent on UNMAPPED path → fall through to ingest
# ---------------------------------------------------------------------------
async def test_on_modified_unmapped_falls_through_to_ingest(tmp_path: Path) -> None:
    """A modify event whose source has no vault counterpart yet must
    fall through to ingest — covers the watcher-started-after-file-
    appeared gap without needing a manual resync."""
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched"
    folder.mkdir()
    # Pre-create the file BEFORE the watcher starts → no FileCreatedEvent
    # will fire for it. A subsequent modify is the first event the
    # watcher sees.
    src = folder / "stray.txt"
    src.write_text("v1", encoding="utf-8")

    pipe = _FakePipeline(vault)
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipe,
    )
    watcher.start()
    try:
        # Mutate the file → triggers a modify event with no cache hit.
        src.write_text("v2 (newer)", encoding="utf-8")
        assert await _wait_async(lambda: len(pipe.ingest_calls) >= 1)
        call = pipe.ingest_calls[0]
        assert Path(str(call.spec)).resolve() == src.resolve()
        assert call.domain_override == "research"
        assert pipe.update_calls == []
    finally:
        watcher.stop()


# ---------------------------------------------------------------------------
# (5) FileDeletedEvent on mapped path → mark_orphaned
# ---------------------------------------------------------------------------
async def test_on_deleted_mapped_routes_to_mark_orphaned(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched"
    folder.mkdir()
    src = folder / "gone.txt"
    src.write_text("here today", encoding="utf-8")
    note = _make_note(
        vault=vault,
        domain="research",
        slug="gone",
        source_path=src.resolve(),
        folder_path=str(folder),
    )
    pipe = _FakePipeline(vault)
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipe,
    )
    watcher.start()
    try:
        src.unlink()
        assert await _wait_async(lambda: len(pipe.orphan_calls) >= 1)
        call = pipe.orphan_calls[0]
        assert call.existing_note_path == note
        assert call.allowed_domains == ("research",)
    finally:
        watcher.stop()


# ---------------------------------------------------------------------------
# (6) FileDeletedEvent on unmapped path → no pipeline call
# ---------------------------------------------------------------------------
async def test_on_deleted_unmapped_is_dropped(tmp_path: Path) -> None:
    """No matching vault note → mark_orphaned is NOT called.

    D2 non-destructive: the watcher must not synthesize state for a
    file it never tracked. The drop is intentional, not a bug.
    """
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched"
    folder.mkdir()
    src = folder / "unknown.txt"
    src.write_text("never ingested", encoding="utf-8")
    pipe = _FakePipeline(vault)
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipe,
    )
    watcher.start()
    try:
        src.unlink()
        # Give the debounce window 5x its setting to fire.
        await asyncio.sleep(0.6)
        assert pipe.orphan_calls == []
        assert pipe.ingest_calls == []
        assert pipe.update_calls == []
    finally:
        watcher.stop()


# ---------------------------------------------------------------------------
# (7) FileMovedEvent → synthetic delete + create
# ---------------------------------------------------------------------------
async def test_on_moved_fires_synthetic_delete_and_create(tmp_path: Path) -> None:
    """v1: move = orphan-old + ingest-new. Content-hash move-detection
    is out of scope per Plan 22 §T6."""
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched"
    folder.mkdir()
    src = folder / "before.txt"
    src.write_text("renaming target", encoding="utf-8")
    note = _make_note(
        vault=vault,
        domain="research",
        slug="before",
        source_path=src.resolve(),
        folder_path=str(folder),
    )
    pipe = _FakePipeline(vault)
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipe,
    )
    watcher.start()
    try:
        dest = folder / "after.txt"
        src.rename(dest)

        # Both the orphan (old path) and the ingest (new path) should
        # land. PollingObserver may surface moves as create+delete
        # rather than a FileMovedEvent — either way the user-visible
        # effect from the watcher's perspective is the same.
        assert await _wait_async(
            lambda: len(pipe.orphan_calls) >= 1 and len(pipe.ingest_calls) >= 1,
            timeout=8.0,
        )
        # Orphan call points at the OLD note.
        assert pipe.orphan_calls[0].existing_note_path == note
        # Ingest call points at the NEW path.
        spec = pipe.ingest_calls[0].spec
        assert Path(str(spec)).resolve() == dest.resolve()
    finally:
        watcher.stop()


# ---------------------------------------------------------------------------
# (8) Debounce: rapid-fire on same path → one call
# ---------------------------------------------------------------------------
async def test_debounce_collapses_rapid_events(tmp_path: Path) -> None:
    """Two writes within the debounce window collapse to ONE
    pipeline call. Without debounce the typical editor save burst
    (write temp + rename + modify) would amplify into 2-3 ingests
    per logical user action."""
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched"
    folder.mkdir()
    pipe = _FakePipeline(vault)
    # Generous debounce window so the test isn't racing the polling
    # observer's own 100ms tick.
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipe,
        debounce_ms=300,
    )
    watcher.start()
    try:
        # File pre-exists so both events are MODIFY (deterministic
        # across PollingObserver implementations — create-on-pre-
        # existing-file is sometimes coalesced and we want this test
        # to pin the modify-burst case explicitly).
        src = folder / "burst.txt"
        src.write_text("v1", encoding="utf-8")
        # Wait past one polling tick so the file is "known" to the
        # observer, then fire two rapid modifies inside the debounce
        # window.
        await asyncio.sleep(0.3)
        src.write_text("v2", encoding="utf-8")
        await asyncio.sleep(0.05)
        src.write_text("v3", encoding="utf-8")

        # Allow debounce window + polling tick to elapse.
        await asyncio.sleep(1.0)

        # The pre-existing modify could route to ingest (file existed
        # before the watcher captured the cache, so it's unmapped) —
        # what matters is that the BURST collapsed into exactly one
        # call, not two.
        total = len(pipe.ingest_calls) + len(pipe.update_calls)
        assert total == 1, (
            f"expected 1 pipeline call after rapid burst, got {total} "
            f"(ingest={len(pipe.ingest_calls)}, update={len(pipe.update_calls)})"
        )
    finally:
        watcher.stop()


# ---------------------------------------------------------------------------
# (9) Hidden / unclaimed files are filtered out
# ---------------------------------------------------------------------------
async def test_hidden_file_skipped(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched"
    folder.mkdir()
    pipe = _FakePipeline(vault)
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipe,
    )
    watcher.start()
    try:
        # Dot-prefixed file → must be skipped at the filter seam, no
        # pipeline call ever.
        (folder / ".hidden.txt").write_text("ignore me", encoding="utf-8")
        await asyncio.sleep(0.6)
        assert pipe.ingest_calls == []
    finally:
        watcher.stop()


async def test_unclaimed_file_skipped(tmp_path: Path) -> None:
    """A file no handler claims (here: .xyz) → no pipeline call."""
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched"
    folder.mkdir()
    pipe = _FakePipeline(vault)
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipe,
    )
    watcher.start()
    try:
        # The stub handler accepts .txt / .md only.
        (folder / "binary.xyz").write_text("opaque", encoding="utf-8")
        await asyncio.sleep(0.6)
        assert pipe.ingest_calls == []
        assert pipe.update_calls == []
    finally:
        watcher.stop()


# ---------------------------------------------------------------------------
# (10) Pipeline exception in dispatch does not crash observer
# ---------------------------------------------------------------------------
async def test_pipeline_exception_keeps_observer_running(tmp_path: Path) -> None:
    """An ingest that raises must NOT take down the observer thread.
    The next event on a different path still routes successfully."""
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched"
    folder.mkdir()
    pipe = _FakePipeline(vault)
    pipe.next_raise_ingest = RuntimeError("simulated handler crash")
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipe,
    )
    watcher.start()
    try:
        (folder / "first.txt").write_text("kaboom", encoding="utf-8")
        # Wait for the failing call to be recorded (event was routed,
        # then raised) before queuing the next file.
        assert await _wait_async(lambda: len(pipe.ingest_calls) >= 1)
        # Observer thread must still be alive.
        observer = watcher._observer  # type: ignore[attr-defined]
        assert observer is not None and observer.is_alive()

        # Second file lands cleanly through the same observer.
        (folder / "second.txt").write_text("ok now", encoding="utf-8")
        assert await _wait_async(lambda: len(pipe.ingest_calls) >= 2)
    finally:
        watcher.stop()


# ---------------------------------------------------------------------------
# Lookup helper unit coverage
# ---------------------------------------------------------------------------
def test_index_vault_for_folder_indexes_matching_notes(tmp_path: Path) -> None:
    """``_index_vault_for_folder`` builds {source_path: note} for the
    watched folder; notes from other folders / domains are excluded."""
    vault = _scaffold_vault(tmp_path)
    folder_a = tmp_path / "folder-a"
    folder_a.mkdir()
    folder_b = tmp_path / "folder-b"
    folder_b.mkdir()

    src_a = folder_a / "alpha.txt"
    src_a.write_text("a", encoding="utf-8")
    src_b = folder_b / "beta.txt"
    src_b.write_text("b", encoding="utf-8")

    note_a = _make_note(
        vault=vault,
        domain="research",
        slug="alpha",
        source_path=src_a.resolve(),
        folder_path=str(folder_a),
    )
    # Note for folder-b — must NOT appear in folder-a's index.
    _make_note(
        vault=vault,
        domain="research",
        slug="beta",
        source_path=src_b.resolve(),
        folder_path=str(folder_b),
    )
    # Note with no source_path — skipped silently.
    skip_note = vault / "research" / "sources" / "no-source.md"
    skip_note.write_text(
        "---\ntitle: x\ndomain: research\ntype: source\n"
        f"watched_folder_id: {folder_a}\n---\n\n# x\n",
        encoding="utf-8",
    )

    idx = _index_vault_for_folder(
        vault_root=vault,
        domains=["research"],
        folder_path=str(folder_a),
    )
    assert idx == {str(src_a.resolve()): note_a}
