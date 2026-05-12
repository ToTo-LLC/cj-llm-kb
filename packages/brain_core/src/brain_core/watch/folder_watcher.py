"""Watched-folder filesystem observer (Plan 22 T6).

Bridges watchdog filesystem events into :class:`IngestPipeline` calls.
Symmetric per D7: one observer per process, started at lifespan /
server-boot, stopped at shutdown. ``brain_api`` and ``brain_mcp``
each instantiate their own watcher (T7 / T8); there is no IPC.

**Event routing** mirrors the Plan 22 §T6 plan-doc:

* :class:`FileCreatedEvent` → :meth:`IngestPipeline.ingest` with
  ``domain_override`` from the matching :class:`WatchedFolder`.
* :class:`FileModifiedEvent` → :meth:`IngestPipeline.update_source`
  when the file maps to an existing vault note (frontmatter
  ``source_path`` match). When no note exists yet (the file pre-dates
  the watcher, or was created during a watcher outage), the event
  falls through to :meth:`ingest` — i.e. a modified file with no
  vault counterpart is treated as a new ingestion. This is the
  "best-effort reconcile" behavior; for an explicit reconciliation
  pass the caller should run :func:`brain_resync_folder` (Plan 22 T5).
* :class:`FileDeletedEvent` → :meth:`IngestPipeline.mark_orphaned`
  on the matching vault note. If no matching note exists the event
  is logged and dropped (D2 non-destructive policy: never remove
  state we didn't author).
* :class:`FileMovedEvent` → fan out to a synthetic delete on the old
  path + a synthetic create on the new path. Out-of-scope per Plan
  22 §T6: ``content_hash``-aware move detection (recognizing the
  moved-to file as the same source) lives in a later plan.

**Threading model.** Watchdog runs its observer in a dedicated OS
thread; our :class:`FileSystemEventHandler` subclass receives events
on that thread. The pipeline methods are async, so we capture the
loop reference at :meth:`WatchedFolderWatcher.start` and bridge each
event via :func:`asyncio.run_coroutine_threadsafe`. Pipeline
exceptions in the resulting coroutine are caught + logged so a bad
ingest cannot kill the observer thread. The synchronous
:meth:`IngestPipeline.mark_orphaned` is called on the watchdog
thread directly (wrapped in ``run_in_executor`` would buy nothing —
the writer's filelock already handles cross-thread concurrency).

**Debounce.** Filesystem editors routinely produce a burst of events
for a single user action (atomic save → create temp + rename + modify
target). The handler holds a rolling :class:`threading.Timer` per
source path; events within the debounce window (default 100ms,
matching :mod:`brain_core.config.hot_reload`) cancel + reschedule the
timer rather than each firing the pipeline. This is per-path
coalescing — events on different files are independent.

**Note lookup.** ``_find_note_by_source_path`` keeps an in-memory
``dict[str, Path]`` mapping the resolved source path to the matching
vault note. The dict is populated lazily on first lookup (one walk
per startup) and updated in-place by event handlers as they observe
create / update / orphan transitions. A process restart rebuilds it
on the next lookup; if perf becomes an issue we can migrate to
``state.sqlite`` in a later plan (D7 considered + deferred).

**Cross-platform.** Default ``Observer`` selects the per-platform
backend (FSEvents on Mac, ``ReadDirectoryChangesW`` on Windows,
inotify on Linux). Tests inject :class:`PollingObserver` via
``observer_factory`` for deterministic event delivery in CI.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from brain_core.ingest.dispatcher import _default_handlers
from brain_core.ingest.handlers.base import SourceHandler
from brain_core.vault.frontmatter import (
    Frontmatter,
    FrontmatterError,
    parse_frontmatter,
)

if TYPE_CHECKING:
    from watchdog.observers.api import BaseObserver

    from brain_core.config.schema import WatchedFolder
    from brain_core.ingest.pipeline import IngestPipeline

logger = structlog.get_logger(__name__)

# Default debounce window — matches :mod:`brain_core.config.hot_reload`
# for consistency. Long enough to absorb the typical editor save burst,
# short enough to feel responsive.
_DEFAULT_DEBOUNCE_SECONDS = 0.1


ObserverFactory = Callable[[], "BaseObserver"]


def _is_hidden_relative_to(path: Path, root: Path) -> bool:
    """Return True if ``path`` (relative to ``root``) has any dot-prefixed component.

    Mirror of :func:`brain_core.ingest.bulk._is_hidden`. Duplicated here
    rather than imported to keep the watch module's dependency surface
    tight (bulk imports the pipeline, which would inflate the import
    graph for a one-liner).
    """
    try:
        rel = path.relative_to(root)
    except ValueError:
        # path is outside root — defensive; events on watched roots
        # always live under the root, but the resolver path may differ
        # on macOS where /var is symlinked to /private/var.
        return False
    return any(part.startswith(".") for part in rel.parts)


def _any_handler_claims(
    spec: Path, *, handlers: list[SourceHandler] | None
) -> bool:
    """Return True if any registered :class:`SourceHandler` claims ``spec``.

    The watcher only forwards events for files that at least one
    handler recognizes. Without this gate, dropping a 200-page
    ``.xlsx`` into a watched folder would push the pipeline through
    its FAILED branch (the dispatcher would raise ``DispatchError``);
    the gate keeps that noise out of ``ingest_history``.

    ``handlers=None`` falls back to the configured default set so the
    decision is consistent with :func:`brain_core.ingest.dispatcher.dispatch`.
    """
    candidates = handlers if handlers is not None else _default_handlers()
    return any(h.can_handle(spec) for h in candidates)


class _FolderEventHandler(FileSystemEventHandler):
    """Per-folder watchdog handler that funnels events to the watcher.

    One instance per :class:`WatchedFolder` — the handler captures
    the originating folder's ``path`` + ``domain`` so the watcher's
    dispatcher always knows which scope to forward against.
    """

    def __init__(
        self,
        *,
        folder: WatchedFolder,
        on_event: Callable[[FileSystemEvent, WatchedFolder], None],
    ) -> None:
        super().__init__()
        self._folder = folder
        self._on_event = on_event

    def on_any_event(self, event: FileSystemEvent) -> None:
        # Skip directory events outright — we only care about file
        # mutations. Watchdog fires both a directory event and a
        # contained-file event on most backends; the file event is
        # the actionable one.
        if event.is_directory:
            return
        try:
            self._on_event(event, self._folder)
        except Exception as exc:  # pragma: no cover — defensive boundary
            logger.warning(
                "watched_folder_handler_error",
                error=str(exc),
                folder=self._folder.path,
            )


class WatchedFolderWatcher:
    """Watch a set of :class:`WatchedFolder` paths; bridge events into the pipeline.

    Construct with the list of folders, the configured
    :class:`IngestPipeline`, and (optionally) a non-default
    ``observer_factory`` for tests. Call :meth:`start` at lifespan
    startup and :meth:`stop` at teardown. Both are idempotent.

    Lifecycle is single-threaded from the caller's perspective: the
    watchdog observer thread is an internal detail. The watcher
    captures ``asyncio.get_running_loop()`` at :meth:`start` time so
    async pipeline calls can be scheduled back onto the caller's
    event loop.

    A folder whose path is missing on :meth:`start` is skipped with a
    warning — the watcher must not refuse to boot just because one
    folder vanished between config save and server start. The user
    can call ``brain_resync_folder`` (Plan 22 T5) once the path
    reappears, or simply restart the server.
    """

    def __init__(
        self,
        observers: list[WatchedFolder],
        pipeline: IngestPipeline,
        *,
        allowed_domains: tuple[str, ...] | None = None,
        debounce_ms: int = 100,
        handlers: list[SourceHandler] | None = None,
        observer_factory: ObserverFactory = Observer,
    ) -> None:
        # ``observers`` is the Plan-22 name from the §T6 plan-doc; we
        # keep that param name even though internally we store them as
        # ``_folders`` for clarity (an Observer is a watchdog thing).
        self._folders: list[WatchedFolder] = list(observers)
        self._pipeline = pipeline
        # ``allowed_domains`` defaults to the union of every folder's
        # domain — the watcher should be able to write to any folder
        # it's configured for. Callers (T7 / T8) may pass a narrower
        # tuple to enforce stricter scoping at the lifespan seam.
        if allowed_domains is None:
            allowed_domains = tuple(
                sorted({wf.domain for wf in self._folders})
            )
        self._allowed_domains = allowed_domains
        self._debounce_seconds = debounce_ms / 1000.0
        self._handlers = handlers
        self._observer_factory = observer_factory

        self._observer: BaseObserver | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._started = False
        self._lock = threading.Lock()

        # Per-path rolling timers for debounce. Keyed by resolved
        # source path string so different files don't share a timer.
        self._timers: dict[str, threading.Timer] = {}
        self._timers_lock = threading.Lock()

        # In-memory lookup: resolved-source-path → vault note path.
        # Lazy-populated on first event so a fresh server start with
        # an empty watched folder doesn't walk the vault for nothing.
        self._source_to_note: dict[str, Path] | None = None
        self._source_lookup_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Begin watching every enabled folder. Idempotent.

        Captures the running asyncio loop reference so the watchdog
        thread can schedule pipeline coroutines back onto it. Folders
        marked ``enabled=False`` are silently skipped — the user
        toggled them off in Settings. Folders whose path does not
        exist are skipped with a warning but do not raise: a missing
        path mid-boot must not prevent the rest of the watcher from
        running.
        """
        with self._lock:
            if self._started:
                return

            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop — caller is constructing the watcher
                # outside an async context (e.g. a synchronous test).
                # We allow it: async events will be scheduled via a
                # background loop helper inside _dispatch (raising
                # cleanly if no loop ever shows up). The realistic
                # production caller (FastAPI lifespan / MCP boot) is
                # always inside a running loop.
                self._loop = None

            observer = self._observer_factory()
            scheduled_any = False
            for folder in self._folders:
                if not folder.enabled:
                    continue
                folder_path = Path(folder.path)
                if not folder_path.exists() or not folder_path.is_dir():
                    logger.warning(
                        "watched_folder_missing",
                        folder=folder.path,
                        domain=folder.domain,
                    )
                    continue
                handler = _FolderEventHandler(
                    folder=folder, on_event=self._on_event
                )
                try:
                    observer.schedule(
                        handler,
                        str(folder_path),
                        recursive=folder.include_subdirs,
                    )
                    scheduled_any = True
                except Exception as exc:  # pragma: no cover — defensive
                    logger.warning(
                        "watched_folder_schedule_failed",
                        folder=folder.path,
                        error=str(exc),
                    )

            if not scheduled_any:
                # Nothing to watch — don't start the observer thread
                # at all. ``stop`` remains a no-op.
                return

            try:
                observer.start()
            except Exception as exc:  # pragma: no cover — defensive
                logger.warning(
                    "watched_folder_observer_start_failed",
                    error=str(exc),
                )
                return

            self._observer = observer
            self._started = True

    def stop(self) -> None:
        """Stop watching. Idempotent — safe to call without a prior start.

        Cancels any pending debounce timers + joins the observer
        thread with a short timeout. The in-memory source-path cache
        is cleared so a subsequent :meth:`start` rebuilds it from a
        clean slate (avoids serving stale entries after a config
        change between stop and restart).
        """
        with self._lock:
            if not self._started or self._observer is None:
                # Cancel any pending timers even on the no-op path —
                # a caller may have called start() then stop() without
                # any folders being scheduled, in which case timers
                # could exist from an earlier successful start cycle.
                self._cancel_pending_timers()
                self._source_to_note = None
                return
            try:
                self._observer.stop()
                self._observer.join(timeout=2.0)
            except Exception as exc:  # pragma: no cover — defensive
                logger.warning(
                    "watched_folder_observer_stop_failed",
                    error=str(exc),
                )
            finally:
                self._cancel_pending_timers()
                self._observer = None
                self._started = False
                self._source_to_note = None

    # ------------------------------------------------------------------
    # Event routing
    # ------------------------------------------------------------------
    def _on_event(
        self, event: FileSystemEvent, folder: WatchedFolder
    ) -> None:
        """Top-level event router. Filters + debounces + dispatches.

        Called on the watchdog observer thread. Per-path debounce
        coalesces a burst of events on the same file into a single
        dispatch after the quiet window elapses.
        """
        # Resolve the event's path(s) to canonical form so the cache
        # keys + filter checks behave consistently across symlinks
        # (Mac's /tmp → /private/tmp is the common offender).
        src_raw = event.src_path
        src_str = (
            src_raw.decode("utf-8", errors="replace")
            if isinstance(src_raw, bytes)
            else src_raw
        )
        src_path = Path(src_str)

        folder_root = Path(folder.path)
        # Hidden-file filter — also dot-prefixed parent dirs
        # (e.g. ``.obsidian/``). Matches BulkImporter semantics.
        if _is_hidden_relative_to(src_path, folder_root):
            return

        # Per-path debounce: cancel any pending timer for this path
        # and schedule a fresh one. The schedule call is keyed on the
        # SOURCE path string — for FileMovedEvent we'll also key on
        # dest_path so a move debounces against itself.
        key = self._debounce_key(event)
        with self._timers_lock:
            pending = self._timers.get(key)
            if pending is not None:
                pending.cancel()
            timer = threading.Timer(
                self._debounce_seconds,
                self._dispatch,
                args=(event, folder),
            )
            timer.daemon = True
            self._timers[key] = timer
            timer.start()

    @staticmethod
    def _debounce_key(event: FileSystemEvent) -> str:
        """Build a unique-per-path string key for the debounce timer table.

        For moves the key includes BOTH paths so a move event doesn't
        merge with an unrelated modify on the same source path that
        fires in the same window.
        """
        src_raw = event.src_path
        src_str = (
            src_raw.decode("utf-8", errors="replace")
            if isinstance(src_raw, bytes)
            else src_raw
        )
        dest_attr = getattr(event, "dest_path", None)
        if dest_attr is None:
            return src_str
        dest_str = (
            dest_attr.decode("utf-8", errors="replace")
            if isinstance(dest_attr, bytes)
            else dest_attr
        )
        return f"{src_str}::{dest_str}"

    def _dispatch(
        self, event: FileSystemEvent, folder: WatchedFolder
    ) -> None:
        """Per-event dispatch — invoked by the debounce timer.

        Runs on a timer thread (NOT the original watchdog thread).
        Wraps every pipeline call in a try/except so a single bad
        event cannot crash the observer.
        """
        # Drop the timer from the table now that it has fired. New
        # events on the same key will allocate a fresh timer.
        key = self._debounce_key(event)
        with self._timers_lock:
            self._timers.pop(key, None)

        try:
            if isinstance(event, FileMovedEvent):
                self._handle_move(event, folder)
                return
            if isinstance(event, FileCreatedEvent):
                self._handle_create(event, folder)
                return
            if isinstance(event, FileModifiedEvent):
                self._handle_modify(event, folder)
                return
            if isinstance(event, FileDeletedEvent):
                self._handle_delete(event, folder)
                return
            # Unknown event class — log + drop.
            logger.debug(
                "watched_folder_unhandled_event",
                event_type=type(event).__name__,
                src_path=str(event.src_path),
            )
        except Exception as exc:  # pragma: no cover — defensive boundary
            # ``run_coroutine_threadsafe`` returns a Future that
            # captures coroutine exceptions silently; sync calls fall
            # through this catch. Either way we want the observer to
            # keep running.
            logger.warning(
                "watched_folder_dispatch_failed",
                event_type=type(event).__name__,
                error=str(exc),
                folder=folder.path,
            )

    # ------------------------------------------------------------------
    # Individual handlers
    # ------------------------------------------------------------------
    def _handle_create(
        self, event: FileCreatedEvent, folder: WatchedFolder
    ) -> None:
        """Create event → :meth:`IngestPipeline.ingest` with domain override."""
        src = Path(str(event.src_path))
        if not _any_handler_claims(src, handlers=self._handlers):
            return
        self._schedule_async(
            self._pipeline.ingest(
                spec=src,
                allowed_domains=self._allowed_domains,
                domain_override=folder.domain,
            )
        )

    def _handle_modify(
        self, event: FileModifiedEvent, folder: WatchedFolder
    ) -> None:
        """Modify event → :meth:`update_source` when mapped, else fall to ingest.

        The fall-through is important: if the watcher started AFTER
        the file already existed but BEFORE any ingest of it (or the
        first event we saw was a modify, not a create), there is no
        matching vault note yet. Treating it as an ingest covers that
        gap without requiring the user to manually re-trigger.
        """
        src = Path(str(event.src_path))
        if not _any_handler_claims(src, handlers=self._handlers):
            return
        note_path = self._find_note_by_source_path(src, folder=folder)
        if note_path is None:
            # No vault counterpart — treat as a new ingest.
            self._schedule_async(
                self._pipeline.ingest(
                    spec=src,
                    allowed_domains=self._allowed_domains,
                    domain_override=folder.domain,
                )
            )
            return
        self._schedule_async(
            self._pipeline.update_source(
                existing_note_path=note_path,
                new_source_path=src,
                allowed_domains=self._allowed_domains,
            )
        )

    def _handle_delete(
        self, event: FileDeletedEvent, folder: WatchedFolder
    ) -> None:
        """Delete event → :meth:`mark_orphaned` on the mapped note.

        ``mark_orphaned`` is synchronous, so we call it directly on
        the timer thread. The pipeline's writer holds a filelock for
        concurrency safety, so a parallel async ingest cannot collide
        with the sync orphan-mark.
        """
        src = Path(str(event.src_path))
        note_path = self._find_note_by_source_path(src, folder=folder)
        if note_path is None:
            logger.debug(
                "watched_folder_delete_unmapped",
                src=str(src),
                folder=folder.path,
            )
            return
        try:
            self._pipeline.mark_orphaned(
                note_path,
                allowed_domains=self._allowed_domains,
            )
            # On successful mark, drop the cache entry so a subsequent
            # create on the same source path re-walks (the note is now
            # orphan-flagged; a re-ingest must hit update_source's
            # orphan-restore path, not be hidden by a stale cache).
            self._invalidate_source(src)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "watched_folder_mark_orphaned_failed",
                src=str(src),
                error=str(exc),
            )

    def _handle_move(
        self, event: FileMovedEvent, folder: WatchedFolder
    ) -> None:
        """Move event → synthetic delete + create per Plan 22 §T6.

        Content-hash-aware move detection (treating "same content, new
        path" as a path-only update rather than orphan-then-reingest)
        is explicitly out of v1 scope. The user-visible effect: a
        rename produces an orphan-marked vault note for the old path
        plus a freshly-ingested note for the new path. A subsequent
        ``brain_resync_folder`` would clean up the orphan if the user
        wants to deduplicate.
        """
        src = Path(str(event.src_path))
        dest_raw = event.dest_path
        dest_str = (
            dest_raw.decode("utf-8", errors="replace")
            if isinstance(dest_raw, bytes)
            else dest_raw
        )
        dest = Path(dest_str)
        # Synthetic delete on the old path — only if hidden filter +
        # any-handler-claims would have admitted the original event.
        if not _is_hidden_relative_to(src, Path(folder.path)):
            self._handle_delete(FileDeletedEvent(str(src)), folder)
        # Synthetic create on the new path.
        if not _is_hidden_relative_to(dest, Path(folder.path)):
            self._handle_create(FileCreatedEvent(str(dest)), folder)

    # ------------------------------------------------------------------
    # Source → note lookup
    # ------------------------------------------------------------------
    def _find_note_by_source_path(
        self, src: Path, *, folder: WatchedFolder
    ) -> Path | None:
        """Return the vault note path whose ``source_path`` matches ``src``.

        Resolved via an in-memory ``dict[str, Path]`` keyed on
        resolved source path strings. The cache is populated lazily
        on first call (one walk per :meth:`start` lifecycle); a
        successful walk caches the full mapping, after which event
        handlers update the cache in-place. A miss returns ``None``.

        The walk uses :func:`_index_vault_for_folder` to enumerate
        every vault note whose frontmatter ``watched_folder_id``
        matches ``folder.path``. Notes whose frontmatter is malformed
        or whose ``source_path`` is absent are skipped silently —
        they cannot be safely linked to a source file.
        """
        cache = self._ensure_source_cache(folder=folder)
        try:
            resolved = str(src.resolve())
        except OSError:
            # ``resolve(strict=False)`` won't raise on a missing path,
            # but a permission error on a parent might. Fall back to
            # the raw string in that case.
            resolved = str(src)
        return cache.get(resolved)

    def _ensure_source_cache(
        self, *, folder: WatchedFolder
    ) -> dict[str, Path]:
        """Return the lazily-initialized source → note cache.

        Threading note: the lazy init happens under
        ``_source_lookup_lock`` so two concurrent events from the
        watchdog thread can't both kick off a vault walk. The walk
        itself is bounded to the configured domains, not the full
        filesystem, so the worst case is a few hundred ``.md`` files
        on a healthy vault.
        """
        with self._source_lookup_lock:
            if self._source_to_note is None:
                self._source_to_note = _index_vault_for_folder(
                    vault_root=self._pipeline.vault_root,
                    domains=self._domain_set(),
                    folder_path=folder.path,
                )
            return self._source_to_note

    def _domain_set(self) -> list[str]:
        """Return the deduplicated list of domains across watched folders.

        Used by the lazy vault walk so we only enumerate notes from
        scopes the watcher actually cares about. Falls back to the
        constructor's ``allowed_domains`` when the folder list is
        empty (defensive — a watcher with no folders is a no-op, but
        a domain set may still be useful for future-proofed callers).
        """
        domains = {wf.domain for wf in self._folders}
        if not domains:
            return list(self._allowed_domains)
        return sorted(domains)

    def _invalidate_source(self, src: Path) -> None:
        """Drop the cache entry for ``src``. Called on delete completion."""
        with self._source_lookup_lock:
            if self._source_to_note is None:
                return
            try:
                resolved = str(src.resolve())
            except OSError:
                resolved = str(src)
            self._source_to_note.pop(resolved, None)

    # ------------------------------------------------------------------
    # Async bridge
    # ------------------------------------------------------------------
    def _schedule_async(self, coro: object) -> None:
        """Submit ``coro`` (an awaitable) onto the captured asyncio loop.

        The watchdog event handler runs on a non-asyncio thread. We
        cannot ``await`` from there, so we hand the coroutine off via
        :func:`asyncio.run_coroutine_threadsafe`. The returned
        :class:`concurrent.futures.Future` is intentionally not
        awaited: events are fire-and-forget per watchdog conventions.
        We DO attach a callback that logs coroutine exceptions so a
        bad ingest doesn't disappear silently into the void.
        """
        loop = self._loop
        if loop is None:
            # No loop captured at start — either the test is
            # synchronous (in which case it should pass its own loop
            # via a fixture) or the production caller forgot to call
            # start inside an async context. Log + drop rather than
            # raise: the observer thread MUST stay alive.
            logger.warning(
                "watched_folder_no_event_loop",
                msg="event dispatched without a running loop; dropping",
            )
            # ``coro`` is a coroutine object; closing it suppresses
            # the "coroutine was never awaited" warning that would
            # otherwise leak to the user.
            close = getattr(coro, "close", None)
            if callable(close):
                close()
            return

        future: concurrent.futures.Future[Any] = (
            asyncio.run_coroutine_threadsafe(coro, loop)  # type: ignore[arg-type]
        )

        def _log_exception(fut: object) -> None:
            # ``fut`` is a concurrent.futures.Future.
            try:
                exc = fut.exception(timeout=0)  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover — defensive
                return
            if exc is not None:
                logger.warning(
                    "watched_folder_async_dispatch_error",
                    error=str(exc),
                )

        future.add_done_callback(_log_exception)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _cancel_pending_timers(self) -> None:
        """Cancel + drop every pending debounce timer."""
        with self._timers_lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()


def _index_vault_for_folder(
    *,
    vault_root: Path,
    domains: list[str],
    folder_path: str,
) -> dict[str, Path]:
    """Walk configured domains and return ``{resolved_source_path: note_path}``.

    Mirrors :func:`brain_core.tools.resync_folder._index_vault_by_watched_folder`
    but returns a dict keyed on resolved source path — the shape the
    watcher's debouncer needs for O(1) lookup. Duplicated rather than
    imported because the resync tool's helper returns a list of
    ``(note_path, Frontmatter)`` tuples and the watcher needs the
    inverted shape; the duplication keeps both consumers' code
    straightforward.

    Notes with malformed frontmatter, no ``source_path``, or no
    ``watched_folder_id`` matching ``folder_path`` are skipped.
    """
    out: dict[str, Path] = {}
    for domain in domains:
        domain_dir = vault_root / domain
        if not domain_dir.exists() or not domain_dir.is_dir():
            continue
        for md_path in domain_dir.rglob("*.md"):
            if not md_path.is_file():
                continue
            try:
                fm_dict, _body = parse_frontmatter(
                    md_path.read_text(encoding="utf-8")
                )
                fm = Frontmatter.from_dict(fm_dict)
            except (OSError, UnicodeDecodeError, FrontmatterError):
                continue
            if fm.watched_folder_id != folder_path:
                continue
            if not fm.source_path:
                continue
            try:
                resolved = str(Path(fm.source_path).resolve())
            except OSError:
                resolved = fm.source_path
            out[resolved] = md_path
    return out
