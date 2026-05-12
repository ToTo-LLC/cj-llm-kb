"""Plan 22 T6 — watched-folder filesystem observer package.

Public surface:

* :class:`WatchedFolderWatcher` — bridges watchdog events into
  :class:`brain_core.ingest.pipeline.IngestPipeline` calls
  (``ingest`` / ``update_source`` / ``mark_orphaned``). Symmetric per
  D7: one observer per process, started at lifespan / server-boot,
  stopped at shutdown. Mirrors the shape of
  :class:`brain_core.config.hot_reload.ConfigWatcher`.
"""

from brain_core.watch.folder_watcher import WatchedFolderWatcher

__all__ = ["WatchedFolderWatcher"]
