"""Plan 22 T10 — end-to-end integration tests for :class:`WatchedFolderWatcher`.

T6's pin tests in :mod:`test_folder_watcher` mock the pipeline with a
:class:`_FakePipeline` so the watcher's event-routing semantics can be
asserted without the cost of real LLM round-trips. T10 climbs one rung
up the stack: REAL :class:`IngestPipeline` + REAL
:class:`WatchedFolderWatcher` + a :class:`FakeLLMProvider` queue prims
the only seam that needs to stay deterministic.

The six scenarios pin the integration boundary:

* **e2e_create** — drop a `.txt` into a watched folder → the pipeline's
  full 9-stage run writes a source note with the watched-folder
  frontmatter fields populated (``source_path`` + ``watched_folder_id``
  + classified domain).
* **e2e_modify** — pre-seed an ingested source + its vault note; modify
  the source file → pipeline's ``update_source`` path overwrites body
  + refreshes ``content_hash`` + ``updated`` while preserving slug.
* **e2e_delete** — pre-seed the same setup; delete the source file →
  pipeline's ``mark_orphaned`` flips ``orphaned: true`` +
  ``orphaned_at`` while leaving body byte-identical.
* **e2e_hidden** — drop a dotfile → no pipeline call, no note (the
  watcher's hidden-file filter fires before dispatch).
* **e2e_unclaimed** — drop a `.xyz` no handler claims → no pipeline
  call, no note (``_any_handler_claims`` gate).
* **e2e_concurrent** — drop 5 `.txt` files in rapid succession →
  debounce coalesces per-path, but every file produces a note.

All tests use :class:`PollingObserver` for deterministic event
delivery (FSEvents / ReadDirectoryChangesW are flaky in CI sandboxes
per Plan 22 D-watch). The observer timeout is 100ms; tests poll for
state with an async wait-loop bounded at 10s so a real CI cold-start
has slack without a fixed sleep that pads every run.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from pathlib import Path

import pytest
from brain_core.config.schema import WatchedFolder
from brain_core.ingest.hashing import content_hash
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.llm.fake import FakeLLMProvider
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.vault.frontmatter import (
    parse_frontmatter,
    serialize_with_frontmatter,
)
from brain_core.vault.types import PatchSet
from brain_core.vault.writer import VaultWriter
from brain_core.watch.folder_watcher import WatchedFolderWatcher
from watchdog.observers.polling import PollingObserver


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_pipeline(vault_root: Path, fake: FakeLLMProvider) -> IngestPipeline:
    """Real :class:`IngestPipeline` wired against the fake LLM.

    Mirrors :func:`brain_core.tests.ingest.test_pipeline._build_pipeline` —
    a thin construction with the model strings the dispatcher cares
    about. ``state_db=None`` keeps ``_record_history`` a no-op so we
    don't need a SQLite fixture; the integration goal is the
    filesystem + frontmatter contract, not the history ledger.
    """
    return IngestPipeline(
        vault_root=vault_root,
        writer=VaultWriter(vault_root=vault_root),
        llm=fake,
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
    )


def _build_watcher(
    *,
    folders: list[WatchedFolder],
    pipeline: IngestPipeline,
    debounce_ms: int = 100,
) -> WatchedFolderWatcher:
    """Watcher backed by :class:`PollingObserver`.

    The polling observer's default polling interval is 1 second, which
    is too coarse for a test budget — we set 100ms via the factory
    closure. ``debounce_ms`` defaults to 100ms (production default);
    the concurrent test bumps it slightly to keep the burst inside a
    single debounce window.
    """
    return WatchedFolderWatcher(
        observers=folders,
        pipeline=pipeline,
        debounce_ms=debounce_ms,
        observer_factory=lambda: PollingObserver(timeout=0.1),
    )


def _queue_ingest_responses(
    fake: FakeLLMProvider,
    *,
    domain: str,
    title: str,
    summary: str = "An end-to-end test source.",
) -> None:
    """Queue the LLM responses an ``ingest`` round-trip consumes.

    The watcher always passes ``domain_override`` (from the
    ``WatchedFolder.domain`` field), which makes Stage 5 (classify) a
    no-op — the pipeline synthesizes a :class:`ClassifyResult` from
    the override without calling the LLM. So only 2 responses are
    queued: summarize + integrate. The ``domain`` arg is retained on
    the signature for symmetry with the FakeLLM E2E-mode canned
    response shape (which inspects the prompt to choose).
    """
    del domain  # unused on the override path — see docstring.
    fake.queue(
        SummarizeOutput(
            title=title,
            summary=summary,
            key_points=["watched-folder source"],
            entities=[],
            concepts=["watch"],
            open_questions=[],
        ).model_dump_json()
    )
    fake.queue(
        PatchSet(
            new_files=[],
            edits=[],
            index_entries=[],
            log_entry=f"## ingest | source | [[{title}]]",
            reason="watched folder e2e",
        ).model_dump_json()
    )


def _queue_update_responses(
    fake: FakeLLMProvider,
    *,
    title: str = "Updated",
    summary: str = "Revised body via watcher.",
) -> None:
    """Queue the 2 LLM responses ``update_source``'s overwrite branch consumes.

    update_source preserves the domain (D4) so there is no classify
    call — only summarize + integrate.
    """
    fake.queue(
        SummarizeOutput(
            title=title,
            summary=summary,
            key_points=["modified"],
            entities=[],
            concepts=[],
            open_questions=[],
        ).model_dump_json()
    )
    fake.queue(
        PatchSet(
            new_files=[],
            edits=[],
            index_entries=[],
            log_entry="integrate-discarded",
            reason="re-ingest after watcher modify",
        ).model_dump_json()
    )


def _seed_source_note(
    *,
    vault_root: Path,
    domain: str,
    slug: str,
    source_path: Path,
    watched_folder_path: str,
) -> Path:
    """Plant an already-ingested source note pointing at ``source_path``.

    Mirrors the canonical frontmatter the pipeline's
    :meth:`_build_source_note` produces — minus the body sections the
    overwrite branch will rebuild from the summary anyway. The
    ``content_hash`` is the hash of ``source_path``'s CURRENT content
    so the no-op branch can fire on an unchanged source.
    """
    note_dir = vault_root / domain / "sources"
    note_dir.mkdir(parents=True, exist_ok=True)
    note_path = note_dir / f"{slug}.md"

    body_bytes = source_path.read_text(encoding="utf-8")
    chash = content_hash(body_bytes)
    fm: dict[str, object] = {
        "title": slug,
        "domain": domain,
        "type": "source",
        "created": "2026-04-01",
        "updated": "2026-04-01",
        "source_type": "text",
        "source_url": None,
        "content_hash": chash,
        "ingested_by": "brain",
        "source_path": str(source_path.resolve()),
        "watched_folder_id": watched_folder_path,
        "orphaned": False,
    }
    body = (
        f"# {slug}\n\n"
        f"A greeting.\n\n"
        f"## Key points\n\n- says hi\n\n"
        f"## Entities\n\n_(none)_\n\n"
        f"## Concepts\n\n_(none)_\n\n"
        f"## Open questions\n\n_(none)_\n"
    )
    note_path.write_text(
        serialize_with_frontmatter(fm, body=body), encoding="utf-8"
    )
    return note_path


async def _wait_async(
    predicate: Callable[[], bool],
    *,
    timeout: float = 10.0,
    poll: float = 0.05,
) -> bool:
    """Async poll — sleeps via ``asyncio.sleep`` so the event loop stays live.

    The watcher schedules pipeline coroutines onto the running loop via
    ``run_coroutine_threadsafe``; if we blocked the loop with
    ``time.sleep`` those coroutines would never run and every test
    would time out. Borrowed verbatim from :mod:`test_folder_watcher`.
    A 10s budget is generous — most calls complete in <500ms locally —
    but CI cold-start needs the slack and the wait short-circuits the
    moment the predicate is true.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(poll)
    return False


def _find_note(vault_root: Path, domain: str, slug_substring: str) -> Path | None:
    """Locate the source note matching ``slug_substring`` (case-insensitive).

    The pipeline's slug derivation is title-aware — the seeded source
    file's name may NOT be the final slug. We search the sources
    directory and return the first match.
    """
    sources = vault_root / domain / "sources"
    if not sources.exists():
        return None
    for md in sources.glob("*.md"):
        if slug_substring.lower() in md.stem.lower():
            return md
    return None


def _scaffold_vault(tmp_path: Path) -> Path:
    """Minimal vault layout the IngestPipeline writes into.

    Matches :func:`brain_core.tests.conftest.ephemeral_vault` shape for
    the ``research`` domain — the only domain we need for this test
    file. Trimmed to that one domain to keep each test's setup tight.
    """
    vault = tmp_path / "brain"
    vault.mkdir()
    (vault / ".brain").mkdir()
    research = vault / "research"
    research.mkdir()
    for sub in ("sources", "entities", "concepts", "synthesis"):
        (research / sub).mkdir()
    (research / "index.md").write_text(
        "# research — index\n\n"
        "## Sources\n\n"
        "## Entities\n\n"
        "## Concepts\n\n"
        "## Synthesis\n",
        encoding="utf-8",
    )
    (research / "log.md").write_text("# research — log\n", encoding="utf-8")
    for sub in ("inbox", "failed", "archive"):
        (vault / "raw" / sub).mkdir(parents=True)
    (vault / "BRAIN.md").write_text(
        "# BRAIN\n\nDefault schema doc.\n", encoding="utf-8"
    )
    return vault


# ---------------------------------------------------------------------------
# (1) e2e_create — file dropped → full ingest → note exists w/ frontmatter
# ---------------------------------------------------------------------------
async def test_e2e_create_writes_source_note_with_watch_frontmatter(
    tmp_path: Path,
) -> None:
    """Drop a `.txt` into a watched folder → vault note created.

    Asserts the integration boundary: the pipeline's full 9-stage run
    fires end-to-end on a real filesystem event and writes the source
    note with the classified domain.

    **Plan 22 T10.5 (was a v1 gap)**: the pipeline now populates
    ``source_path`` + ``watched_folder_id`` on watcher-triggered
    ingests. T10.5 wired the optional kwargs through
    :meth:`IngestPipeline.ingest` and
    :meth:`WatchedFolderWatcher._handle_create` passes them. Pre-T10.5
    this test pinned the ABSENCE of those fields (documenting the gap);
    post-T10.5 we flip to PRESENCE assertions so the lookup-cache T6
    depends on is grep-locked at the integration seam. The flip is the
    correctness gate for the modify + delete e2e tests below — without
    these fields, the watcher's :meth:`_find_note_by_source_path` walks
    return ``None`` and the test relies on a fallback that masks the
    real bug.
    """
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched_create"
    folder.mkdir()

    fake = FakeLLMProvider()
    _queue_ingest_responses(fake, domain="research", title="My Source")
    pipeline = _build_pipeline(vault, fake)
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipeline,
    )
    watcher.start()
    try:
        src = folder / "my-source.txt"
        # Plan 25 T2: Stage 3.5 content sniff needs >=200 chars.
        src.write_text(
            "Hello from the watched folder. " + "The quick brown fox jumps over the lazy dog. " * 6,
            encoding="utf-8",
        )

        # Wait for the watcher to dispatch + the pipeline to write the
        # note. We poll for the note's existence rather than the
        # request count so we know the ENTIRE pipeline (not just the
        # first LLM call) has completed. The slug derivation in
        # ``_build_source_note`` runs the summary title through the
        # kebab-case helper ("My Source" → "my-source"), so we search
        # for any *.md created under the sources/ directory rather
        # than guessing the slug — the per-file frontmatter assertion
        # below catches a wrong-source-path note.
        sources_dir = vault / "research" / "sources"

        def _note_landed() -> bool:
            return any(sources_dir.glob("*.md"))

        assert await _wait_async(_note_landed), (
            "watched-folder ingest did not produce a vault note in time; "
            f"requests={len(fake.requests)}, "
            f"sources_dir contents={list(sources_dir.glob('*'))!r}"
        )

        notes = list(sources_dir.glob("*.md"))
        assert len(notes) == 1, f"expected exactly 1 note, got {notes!r}"
        note = notes[0]
        fm, body = parse_frontmatter(note.read_text(encoding="utf-8"))
        assert fm["domain"] == "research"
        assert fm["type"] == "source"
        assert fm["title"] == "My Source"
        # Plan 22 T10.5: watcher-triggered ingest now writes
        # ``source_path`` + ``watched_folder_id`` on the source note's
        # frontmatter. ``source_path`` is the resolved path of the
        # source file (T2 :meth:`update_source` convention).
        # ``watched_folder_id`` is the verbatim ``WatchedFolder.path``
        # string (Plan 22 D1).
        assert fm["source_path"] == str(src.resolve())
        assert fm["watched_folder_id"] == str(folder)
        # Both LLM responses (summarize + integrate) were consumed.
        # Classify is skipped because the watcher passes
        # ``domain_override`` derived from ``WatchedFolder.domain``.
        assert len(fake.requests) == 2
    finally:
        watcher.stop()


# ---------------------------------------------------------------------------
# (2) e2e_modify — modify an ingested source → update_source overwrites
# ---------------------------------------------------------------------------
async def test_e2e_modify_overwrites_existing_note(tmp_path: Path) -> None:
    """Modify a tracked source → vault note body overwritten in place.

    Pre-seeds the source + its vault note (matching the post-ingest
    state) so the watcher's lazy cache walk finds the mapping on the
    first modify event. The pipeline's ``update_source`` overwrite
    branch fires: summary + integrate run, content_hash refreshes,
    slug is preserved (the note path is unchanged).
    """
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched_modify"
    folder.mkdir()
    src = folder / "doc.txt"
    src.write_text("Version one — original.\n", encoding="utf-8")

    seeded_note = _seed_source_note(
        vault_root=vault,
        domain="research",
        slug="doc",
        source_path=src,
        watched_folder_path=str(folder),
    )

    fake = FakeLLMProvider()
    # Modify path: update_source's overwrite branch — 2 LLM calls
    # (summarize + integrate). Domain is read from existing
    # frontmatter (D4); no classify.
    _queue_update_responses(fake, title="Doc", summary="Revised body.")
    pipeline = _build_pipeline(vault, fake)
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipeline,
    )
    watcher.start()
    try:
        # Mutate the source file. New body → new content_hash → the
        # overwrite branch fires.
        new_body = "Version two — totally different bytes for sure.\n"
        src.write_text(new_body, encoding="utf-8")

        new_hash = content_hash(new_body)
        assert await _wait_async(
            lambda: (
                seeded_note.exists()
                and parse_frontmatter(seeded_note.read_text(encoding="utf-8"))[0].get(
                    "content_hash"
                )
                == new_hash
            )
        ), "modify event did not refresh the vault note's content_hash"

        fm, body = parse_frontmatter(seeded_note.read_text(encoding="utf-8"))
        # Slug preserved — same note path.
        assert seeded_note == vault / "research" / "sources" / "doc.md"
        # Domain preserved per D4.
        assert fm["domain"] == "research"
        # source_path refreshed.
        assert fm["source_path"] == str(src.resolve())
        # Updated body reflects the revised summary.
        assert "Revised body." in body
        # Exactly 2 LLM calls — no classify, no second pass.
        assert len(fake.requests) == 2
    finally:
        watcher.stop()


# ---------------------------------------------------------------------------
# (3) e2e_delete — source file deleted → mark_orphaned flips frontmatter
# ---------------------------------------------------------------------------
async def test_e2e_delete_orphans_existing_note(tmp_path: Path) -> None:
    """Delete a tracked source → vault note frontmatter flipped to orphaned.

    Pre-seeds the source + its vault note; deletes the source on
    disk; asserts the watcher routes the FileDeletedEvent to
    ``mark_orphaned`` and the note's frontmatter reflects the orphan
    state (body byte-identical per T3's invariant — only frontmatter
    changes).
    """
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched_delete"
    folder.mkdir()
    src = folder / "gone.txt"
    src.write_text("Here today, gone tomorrow.\n", encoding="utf-8")

    seeded_note = _seed_source_note(
        vault_root=vault,
        domain="research",
        slug="gone",
        source_path=src,
        watched_folder_path=str(folder),
    )
    pre_fm, pre_body = parse_frontmatter(seeded_note.read_text(encoding="utf-8"))

    fake = FakeLLMProvider()  # mark_orphaned is LLM-free — queue stays empty.
    pipeline = _build_pipeline(vault, fake)
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipeline,
    )
    watcher.start()
    try:
        src.unlink()

        assert await _wait_async(
            lambda: (
                seeded_note.exists()
                and bool(
                    parse_frontmatter(
                        seeded_note.read_text(encoding="utf-8")
                    )[0].get("orphaned")
                )
            )
        ), "delete event did not flip the vault note's orphaned frontmatter"

        post_fm, post_body = parse_frontmatter(
            seeded_note.read_text(encoding="utf-8")
        )
        assert post_fm["orphaned"] is True
        assert post_fm["orphaned_at"] is not None
        # Body byte-identical — only frontmatter changes per T3.
        assert post_body == pre_body
        # No LLM calls — orphan path is sync, LLM-free.
        assert len(fake.requests) == 0
    finally:
        watcher.stop()


# ---------------------------------------------------------------------------
# (4) e2e_hidden — dotfile dropped → filter fires, no pipeline call
# ---------------------------------------------------------------------------
async def test_e2e_hidden_file_does_not_ingest(tmp_path: Path) -> None:
    """Dot-prefixed file → no vault note, no LLM call.

    The watcher's :func:`_is_hidden_relative_to` filter drops the
    event before it reaches the pipeline. We use an empty FakeLLM
    queue so any pipeline dispatch would surface a RuntimeError
    inside the watcher's exception handler — the test asserts the
    no-call path explicitly.
    """
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched_hidden"
    folder.mkdir()

    fake = FakeLLMProvider()
    pipeline = _build_pipeline(vault, fake)
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipeline,
    )
    watcher.start()
    try:
        (folder / ".hidden.txt").write_text("ignore me", encoding="utf-8")
        # Give the polling observer + debounce window a generous
        # slack — 5x the debounce default — to fire if it ever would.
        # If the filter is in place, no dispatch ever happens.
        await asyncio.sleep(0.6)
        # No LLM call.
        assert fake.requests == []
        # No source note materialized.
        sources = vault / "research" / "sources"
        assert list(sources.glob("*.md")) == []
    finally:
        watcher.stop()


# ---------------------------------------------------------------------------
# (5) e2e_unclaimed — unclaimed suffix → handler gate fires, no pipeline call
# ---------------------------------------------------------------------------
async def test_e2e_unclaimed_file_does_not_ingest(tmp_path: Path) -> None:
    """A file no handler claims (here: `.xyz`) → no pipeline call.

    The watcher's :func:`_any_handler_claims` gate runs against the
    configured handler list (default set when ``handlers=None``).
    `.xyz` is not claimed by any handler, so the event is filtered.
    Without this gate, a 200-byte opaque file would push the
    dispatcher into ``DispatchError`` — noise we keep out of
    ``ingest_history``.
    """
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched_unclaimed"
    folder.mkdir()

    fake = FakeLLMProvider()
    pipeline = _build_pipeline(vault, fake)
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipeline,
    )
    watcher.start()
    try:
        (folder / "binary.xyz").write_text("opaque payload", encoding="utf-8")
        await asyncio.sleep(0.6)
        assert fake.requests == []
        sources = vault / "research" / "sources"
        assert list(sources.glob("*.md")) == []
    finally:
        watcher.stop()


# ---------------------------------------------------------------------------
# (5.5) e2e_create_then_modify — Plan 22 T10.5 lifecycle pin
# ---------------------------------------------------------------------------
async def test_e2e_create_then_modify_routes_via_update_source(
    tmp_path: Path,
) -> None:
    """Plan 22 T10.5 regression: create → modify on the SAME path
    must route through ``update_source`` (not duplicate ingest).

    The original T10 modify/delete tests pre-seed a note with the
    correct watched-context frontmatter, so they pass even when the
    bug is present. This lifecycle test does NOT pre-seed: it lets
    the watcher write the note via its own create-event handler,
    THEN modifies the same source file. If T10.5 wired the watched-
    context kwargs correctly, the modify event finds the note via
    :meth:`_find_note_by_source_path` and overwrites it in place
    (1 note in sources/, refreshed content_hash). Pre-T10.5 the
    lookup returns ``None``, the modify falls through to a fresh
    ingest, and we'd end up with 2 notes in sources/ — the
    duplicate-on-modify gap the task closes.
    """
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched_lifecycle"
    folder.mkdir()

    fake = FakeLLMProvider()
    # Create event consumes summarize + integrate (classify skipped via
    # ``domain_override``).
    _queue_ingest_responses(
        fake, domain="research", title="lifecycle", summary="v1 body."
    )
    # Modify event consumes summarize + integrate (no classify, no
    # duplicate ingest if T10.5 is wired correctly).
    _queue_update_responses(fake, title="lifecycle", summary="v2 body.")

    pipeline = _build_pipeline(vault, fake)
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipeline,
    )
    watcher.start()
    try:
        # Step 1: create
        src = folder / "lifecycle.txt"
        # Plan 25 T2: Stage 3.5 content sniff needs >=200 chars.
        src.write_text(
            "Version one. " + "The quick brown fox jumps over the lazy dog. " * 6,
            encoding="utf-8",
        )
        sources_dir = vault / "research" / "sources"

        def _initial_note_landed() -> bool:
            notes = list(sources_dir.glob("*.md"))
            if len(notes) != 1:
                return False
            fm, _ = parse_frontmatter(notes[0].read_text(encoding="utf-8"))
            return fm.get("source_path") == str(src.resolve())

        assert await _wait_async(_initial_note_landed), (
            "create event did not produce the watched-context note in time; "
            f"requests={len(fake.requests)}"
        )
        notes_after_create = list(sources_dir.glob("*.md"))
        assert len(notes_after_create) == 1
        created_note = notes_after_create[0]
        fm_create, _ = parse_frontmatter(created_note.read_text(encoding="utf-8"))
        original_hash = fm_create["content_hash"]

        # Step 2: modify the SAME source file. The watcher's modify
        # handler must find the existing note via
        # :meth:`_find_note_by_source_path` and route to
        # :meth:`update_source` — NOT a duplicate ingest.
        new_body = (
            "Version two — completely different content for hashing. "
            + "The quick brown fox jumps over the lazy dog. " * 6
        )
        src.write_text(new_body, encoding="utf-8")

        new_hash = content_hash(new_body)

        def _modify_landed() -> bool:
            if not created_note.exists():
                return False
            fm, _ = parse_frontmatter(created_note.read_text(encoding="utf-8"))
            return fm.get("content_hash") == new_hash

        assert await _wait_async(_modify_landed), (
            "modify event did not refresh the existing note's content_hash; "
            f"requests={len(fake.requests)}, "
            f"sources={list(sources_dir.glob('*.md'))!r}"
        )

        # Critical T10.5 invariant: sources/ still holds EXACTLY 1
        # note — modify routed to update_source, not duplicate ingest.
        notes_after_modify = list(sources_dir.glob("*.md"))
        assert len(notes_after_modify) == 1, (
            f"modify event produced a duplicate note (T10.5 regression!): "
            f"{notes_after_modify!r}"
        )

        # The single note's hash refreshed; the slug / path is unchanged.
        fm_modify, _ = parse_frontmatter(
            created_note.read_text(encoding="utf-8")
        )
        assert fm_modify["content_hash"] == new_hash
        assert fm_modify["content_hash"] != original_hash
        # source_path + watched_folder_id preserved by update_source.
        assert fm_modify["source_path"] == str(src.resolve())
        assert fm_modify["watched_folder_id"] == str(folder)

        # 4 total LLM calls = 2 for create (summarize + integrate)
        # + 2 for modify (summarize + integrate). If fallback ingest
        # had fired on modify, we'd still see 4 calls (no classify
        # because domain_override is set), but the duplicate-note
        # check above would have caught it.
        assert len(fake.requests) == 4
    finally:
        watcher.stop()


# ---------------------------------------------------------------------------
# (6) e2e_concurrent — 5 rapid files → 5 notes (per-path debounce isolates)
# ---------------------------------------------------------------------------
async def test_e2e_concurrent_files_each_produce_a_note(tmp_path: Path) -> None:
    """Drop 5 distinct `.txt` files in rapid succession → 5 vault notes.

    Per-path debounce coalesces a BURST on the same path, but events
    on DIFFERENT paths are independent — the watcher tracks a timer
    per source path. This test pins the multi-file fan-out: 5 distinct
    file events must produce 5 distinct ingest calls, even when their
    timestamps overlap inside the polling-observer's tick window.
    """
    vault = _scaffold_vault(tmp_path)
    folder = tmp_path / "watched_concurrent"
    folder.mkdir()

    fake = FakeLLMProvider()
    # Each file consumes 2 LLM responses (summarize + integrate;
    # classify is skipped via ``domain_override``). With 5 files = 10
    # queued responses. We give each file a distinct title so the
    # slug-derivation produces 5 distinct note paths and we can
    # assert per-file frontmatter independently.
    for i in range(5):
        _queue_ingest_responses(
            fake, domain="research", title=f"Burst File {i}"
        )

    pipeline = _build_pipeline(vault, fake)
    watcher = _build_watcher(
        folders=[WatchedFolder(path=str(folder), domain="research")],
        pipeline=pipeline,
        debounce_ms=150,
    )
    watcher.start()
    try:
        # Drop 5 files inside ~50ms — well under the polling-observer
        # tick (100ms), so all 5 surface in the same poll batch. Each
        # body is >=200 chars + DISTINCT so Stage 3.5 passes (Plan 25
        # T2) and Stage 4 idempotency does NOT skip later files as
        # duplicates.
        burst_filler = "The quick brown fox jumps over the lazy dog. " * 6
        for i in range(5):
            (folder / f"burst-{i}.txt").write_text(
                f"Burst body {i} — uniquely distinct. " + burst_filler,
                encoding="utf-8",
            )

        # Wait until all 5 notes land. We're checking the sources
        # directory rather than the LLM-request count so we know the
        # full pipeline ran for every file (not just classify).
        def _all_notes_landed() -> bool:
            sources = vault / "research" / "sources"
            return len(list(sources.glob("*.md"))) >= 5

        assert await _wait_async(_all_notes_landed, timeout=15.0), (
            "watcher did not produce 5 notes for 5 rapid file drops; "
            f"got {len(list((vault / 'research' / 'sources').glob('*.md')))}"
        )

        notes = sorted(
            (vault / "research" / "sources").glob("*.md")
        )
        assert len(notes) == 5

        # Each note must have a DISTINCT title (and therefore a
        # distinct slug / note path) — proves the debounce didn't
        # coalesce across paths. We assert on BOTH ``title`` AND
        # ``source_path``: post-Plan 22 T10.5, every watcher-
        # triggered note carries ``source_path`` frontmatter, so we
        # can also pin the per-file source-path mapping (each file's
        # note must reference its own source path, not some sibling's).
        titles = {
            parse_frontmatter(n.read_text(encoding="utf-8"))[0]["title"]
            for n in notes
        }
        assert len(titles) == 5, (
            "expected 5 distinct title frontmatter values, got: "
            f"{titles!r}"
        )
        # All 5 titles match the queued "Burst File N" pattern.
        assert titles == {f"Burst File {i}" for i in range(5)}, (
            f"unexpected titles: {titles!r}"
        )
        # Per-file source_path pin (T10.5). The set of recorded
        # ``source_path`` values must equal the set of source files we
        # dropped — proves the watcher threads the per-event path
        # through correctly, not just a single shared value.
        recorded_source_paths = {
            parse_frontmatter(n.read_text(encoding="utf-8"))[0]["source_path"]
            for n in notes
        }
        expected_source_paths = {
            str((folder / f"burst-{i}.txt").resolve()) for i in range(5)
        }
        assert recorded_source_paths == expected_source_paths, (
            f"unexpected source_paths: {recorded_source_paths!r}"
        )
        # All 5 notes are in the research domain. Also pin that the
        # shared watched_folder_id rode every note.
        for n in notes:
            fm, _ = parse_frontmatter(n.read_text(encoding="utf-8"))
            assert fm["domain"] == "research"
            assert fm["watched_folder_id"] == str(folder)
        # 10 LLM calls = 2 per file × 5 files (classify is skipped via
        # ``domain_override``).
        assert len(fake.requests) == 10
    finally:
        watcher.stop()
