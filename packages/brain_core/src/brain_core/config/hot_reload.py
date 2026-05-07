"""Cross-process config hot-reload via filesystem watcher (Plan 16 Task 35).

Both ``brain_api`` and ``brain_mcp`` start their own
:class:`ConfigWatcher` at lifespan / server-boot. Each watcher
observes ``<vault>/.brain/config.json`` independently and invokes its
``on_change`` callback (typically
:func:`brain_core.config.loader.invalidate_cache_for`) when the file
is modified. There is no IPC, no signal handler, no marker file —
both processes share only the on-disk vault, so symmetric file-watching
is the simplest correct architecture.

**Why symmetric, not "brain_api signals brain_mcp" (the original
plan-doc design):** ``brain_api`` does NOT manage ``brain_mcp``'s
lifecycle. ``brain_api`` is launched by ``brain start`` (the user CLI);
``brain_mcp`` is launched by Claude Desktop as a child process
(installed via ``brain mcp install``). They run independently. There
is no PID handoff, no subprocess management, no signal channel
between the two — verified by grepping the codebase. Sending SIGHUP
across an unmanaged subprocess relationship would require a fragile
out-of-band PID file and a Windows fallback (a marker file the MCP
server polls), neither of which buys anything over each side
watching the file directly.

**Layered invalidation:** This watcher is the EAGER invalidation
path for long-running consumers that hold a ``Config`` reference
between :func:`brain_core.config.loader.resolve_config` calls. T34's
lazy peek (``_peek_config_version``, fired on every ``resolve_config``
call) remains the SAFETY NET — if a watchdog event is dropped (rare,
but FSEvents and inotify have been observed to coalesce events under
load), the next ``resolve_config`` peek catches it.

**Atomic-write debounce.** :func:`brain_core.config.writer.save_config`
writes via temp + ``os.replace`` — one logical save can produce
multiple filesystem events (create-temp, rename, modify-target). The
watcher debounces with a 100ms timer: the first event after a quiet
period schedules ``on_change``; further events within the window
reset the timer. The window is short enough that a real change is
visible well within the 500ms target the pin tests assert.

**Threading model.** ``watchdog.observers.Observer`` runs its event
loop in a dedicated OS thread. Our :class:`FileSystemEventHandler`
subclass receives events on that thread and schedules a
``threading.Timer`` (also on its own thread) to fire ``on_change``.
``on_change`` therefore runs OFF the main thread. The loader's
``invalidate_cache_for`` is safe to call from any thread (dict
``pop`` is atomic in CPython); callers passing more elaborate
``on_change`` callables are responsible for their own thread-safety.

**Cross-platform.** ``watchdog`` selects the native backend per
platform (FSEvents on Mac, ``ReadDirectoryChangesW`` on Windows,
inotify on Linux). Our code stays platform-agnostic: we use
``Observer`` (the auto-selected backend) and ``Path``-based
filtering, never platform-specific event types.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

if TYPE_CHECKING:
    from watchdog.observers.api import BaseObserver

logger = structlog.get_logger(__name__)

# Default debounce window (seconds). Short enough that the 500ms
# target in the pin tests passes comfortably; long enough to coalesce
# the temp+rename burst from :func:`brain_core.config.writer.save_config`
# (typically <50ms apart on Mac/Linux).
_DEFAULT_DEBOUNCE_SECONDS = 0.1


class _DebouncedHandler(FileSystemEventHandler):
    """Filter watchdog events down to ``config.json`` mutations and debounce.

    Watchdog fires events on every change in the watched directory.
    We watch the parent directory of ``config.json`` (watchdog cannot
    watch a single file directly on every backend) and filter
    in-process. The filter accepts any event whose path equals the
    target file or its temp-suffix sibling (``config.json.tmp`` —
    produced by ``save_config``'s atomic rename). The ``.bak`` and
    ``.lock`` siblings are ignored: ``.bak`` is a backup-on-write
    copy that landing does NOT mean the new ``config.json`` has been
    swapped in, and ``.lock`` is filelock's coordination file which
    flickers on every save.

    The debounce timer is a single rolling :class:`threading.Timer`:
    each accepted event cancels the previous (still-pending) timer
    and schedules a fresh one. After the quiet window elapses the
    timer fires ``on_change`` ONCE. This collapses the typical
    create-temp + rename + modify-target burst from one save into a
    single callback.
    """

    def __init__(
        self,
        *,
        target_path: Path,
        on_change: Callable[[], None],
        debounce_seconds: float,
    ) -> None:
        super().__init__()
        # Resolve so canonical comparison works even when watchdog
        # reports the symlink-target form (Mac) vs the literal-path
        # form (Linux).
        self._target_resolved = target_path.resolve()
        self._target_name = target_path.name
        self._target_tmp_name = f"{target_path.name}.tmp"
        self._on_change = on_change
        self._debounce_seconds = debounce_seconds
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def on_any_event(self, event: FileSystemEvent) -> None:
        """Accept any event whose path matches the target or its temp sibling."""
        # Watchdog FileSystemEvent.src_path is `str | bytes` in v6;
        # bytes only happen on Linux when the underlying inotify path
        # is non-utf8. Treat as str — our config.json path is always
        # ASCII-decodable.
        src_raw = event.src_path
        src = src_raw.decode("utf-8", errors="replace") if isinstance(src_raw, bytes) else src_raw
        # Prefer name-matching (cheap, reliable) before the resolve()
        # comparison: every directory that contains a config.json is
        # the only one we'd ever watch, so name match is precise.
        path_name = Path(src).name
        if path_name not in (self._target_name, self._target_tmp_name):
            # Also handle moved events whose dest_path is the target.
            dest_attr = getattr(event, "dest_path", None)
            if dest_attr is None:
                return
            dest = (
                dest_attr.decode("utf-8", errors="replace")
                if isinstance(dest_attr, bytes)
                else dest_attr
            )
            if Path(dest).name not in (self._target_name, self._target_tmp_name):
                return

        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce_seconds, self._fire)
            # Daemon threads die with the process; guards against a
            # leaked timer holding the interpreter open during a
            # crash + atexit teardown.
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        """Invoke ``on_change`` — caller's exceptions are logged, not raised.

        Raising out of a Timer thread would print an uncaught-thread
        traceback and the next debounce cycle would still work, but
        we log a structlog warning so a misbehaving consumer (e.g.
        an ``invalidate_cache_for`` that started raising) is visible
        at the boundary.
        """
        try:
            self._on_change()
        except Exception as exc:  # pragma: no cover — defensive boundary
            logger.warning(
                "config_watcher_callback_failed",
                error=str(exc),
                target=str(self._target_resolved),
            )


class ConfigWatcher:
    """Watch ``<vault>/.brain/config.json`` for changes; invoke a callback.

    Construct with the absolute path to ``config.json`` and a
    callable. Call :meth:`start` at lifespan startup and
    :meth:`stop` at teardown. Both are idempotent.

    The watcher tolerates a missing parent directory at construction
    time — production callers may instantiate during boot before the
    vault has been initialized. :meth:`start` creates the parent
    directory if needed (the same mkdir the writer would do on first
    save) so the watchdog Observer has something to watch. If
    creating the parent fails (permissions, path collision with a
    file), :meth:`start` logs a warning and returns without raising:
    the app must boot regardless, and T34's lazy peek will pick up
    eventual changes.
    """

    def __init__(
        self,
        *,
        config_path: Path,
        on_change: Callable[[], None],
        debounce_seconds: float = _DEFAULT_DEBOUNCE_SECONDS,
    ) -> None:
        self._config_path = config_path
        self._on_change = on_change
        self._debounce_seconds = debounce_seconds
        self._observer: BaseObserver | None = None
        self._started = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """Begin watching. Idempotent — second call is a no-op.

        Failure modes (each emits a structlog warning, returns
        cleanly, leaves ``_started`` ``False`` so a future
        :meth:`stop` is also a no-op):
          * Parent directory cannot be created (permissions, file
            collision).
          * ``Observer.start()`` raises (rare; usually means the OS
            ran out of inotify watches on Linux).
        """
        with self._lock:
            if self._started:
                return

            parent = self._config_path.parent
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                logger.warning(
                    "config_watcher_parent_unavailable",
                    parent=str(parent),
                    error=str(exc),
                )
                return

            handler = _DebouncedHandler(
                target_path=self._config_path,
                on_change=self._on_change,
                debounce_seconds=self._debounce_seconds,
            )
            observer: BaseObserver = Observer()
            observer.schedule(handler, str(parent), recursive=False)
            try:
                observer.start()
            except Exception as exc:  # pragma: no cover — defensive
                logger.warning(
                    "config_watcher_start_failed",
                    target=str(self._config_path),
                    error=str(exc),
                )
                return

            self._observer = observer
            self._started = True

    def stop(self) -> None:
        """Stop watching. Idempotent — safe to call without a prior start."""
        with self._lock:
            if not self._started or self._observer is None:
                return
            try:
                self._observer.stop()
                # join with a short timeout so a stuck observer thread
                # doesn't hang shutdown indefinitely. watchdog's
                # internal threads are well-behaved; a 2s ceiling is
                # enough for a clean stop without dragging tear-down.
                self._observer.join(timeout=2.0)
            except Exception as exc:  # pragma: no cover — defensive
                logger.warning(
                    "config_watcher_stop_failed",
                    target=str(self._config_path),
                    error=str(exc),
                )
            finally:
                self._observer = None
                self._started = False
