"""Path normalization and scope enforcement. The domain firewall lives here.

Plan 22 T4 extends :func:`scope_guard` with an ``include_orphans`` keyword.
When ``False`` (the default), paths that resolve to an existing ``.md``
note whose frontmatter has ``orphaned: true`` raise
:class:`OrphanedNoteError` (a :class:`ScopeError` subclass). The
non-destructive orphan policy from D2 (Plan 22 design doc) requires
orphan notes to be HIDDEN from default discovery (search, list, get),
but the underlying file stays on disk so the user can restore or delete
it via the dedicated tools. Callers that must operate on orphan notes
(``brain_restore_orphan``, ``brain_delete_orphan``, the Orphan
management UI, ``brain_list_orphans``) opt in by passing
``include_orphans=True``.

Backwards compatibility: ``include_orphans`` defaults to ``False``, so
every existing call site (writer pre-validation, search re-verification,
tool handlers) compiles unchanged. In production the writer paths
target NEW notes (orphan flag not yet set) or EDIT-of-existing notes
that the LLM discovered via search (orphans already filtered out at
discovery), so the default-filter does NOT block legitimate workflows.
The two exceptions — restore_orphan and delete_orphan landing in T5 —
will explicitly pass ``include_orphans=True``.

Frontmatter-read caching: a process-local ``(resolved_path, mtime_ns)``
cache memoizes the orphan check. ``os.replace`` (used by
``VaultWriter._atomic_write``) bumps mtime, so concurrent writes
invalidate the cache organically without requiring scope_guard to
listen for VaultWriter mutation events. The cache is bounded by an LRU
trim (1000 entries) so a long-running process scanning a large vault
does not retain stale entries indefinitely.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable
from pathlib import Path
from threading import Lock
from typing import Final

from brain_core.vault.frontmatter import FrontmatterError, parse_frontmatter


class ScopeError(PermissionError):
    """Raised when a path is outside the allowed domain scope."""


class OrphanedNoteError(ScopeError):
    """Raised when a path targets an orphaned note and the caller did not opt in.

    Subclasses :class:`ScopeError` so existing handlers that catch
    ``ScopeError`` (e.g. ``brain_search`` re-verification) treat orphan
    blocks the same as domain-out-of-scope rejections. Callers that
    need to distinguish the two (e.g. UI surfaces wanting to render
    "this note is orphaned — restore?") can catch
    :class:`OrphanedNoteError` specifically.
    """


# Process-local memo of (resolved_path, mtime_ns) -> is_orphaned. The
# OrderedDict + lock gives O(1) lookups, FIFO eviction, and thread-safe
# updates. _MAX_CACHE_ENTRIES caps memory at ~1000 path string + bool
# entries (well under 1 MB for any realistic path-length distribution).
_MAX_CACHE_ENTRIES: Final[int] = 1000
_orphan_cache: OrderedDict[tuple[str, int], bool] = OrderedDict()
_orphan_cache_lock: Final[Lock] = Lock()


def _orphan_cache_clear() -> None:
    """Clear the orphan cache. Test-only hook — call between tests that
    mutate a note's ``orphaned`` flag in place without going through
    VaultWriter (which would otherwise bump mtime). Production code does
    NOT need this — ``os.replace`` updates mtime on every atomic write.
    """
    with _orphan_cache_lock:
        _orphan_cache.clear()


def _is_note_orphaned(resolved: Path) -> bool:
    """Return True if ``resolved`` is an existing ``.md`` file with
    frontmatter ``orphaned: true``. Returns False for directories,
    missing files, non-``.md`` files, files with unparseable
    frontmatter, and notes whose frontmatter lacks the field.

    Cached per (path, mtime_ns) — a write that bumps mtime invalidates
    the entry organically (``os.replace`` updates mtime).
    """
    if resolved.suffix != ".md":
        return False
    try:
        stat = resolved.stat()
    except (OSError, ValueError):
        # Missing file, permission error, or symlink loop — treat as
        # "not an orphan" so the writer can create new files and the
        # caller's downstream code surfaces the real error (FileNotFound,
        # etc.) instead of a misleading OrphanedNoteError.
        return False

    cache_key = (str(resolved), stat.st_mtime_ns)
    with _orphan_cache_lock:
        cached = _orphan_cache.get(cache_key)
        if cached is not None:
            # LRU touch: move to end so frequently-accessed entries
            # don't get evicted first.
            _orphan_cache.move_to_end(cache_key)
            return cached

    # Cache miss — read the file. Done OUTSIDE the lock so concurrent
    # readers don't serialize on disk I/O.
    try:
        raw = resolved.read_text(encoding="utf-8")
        fm, _body = parse_frontmatter(raw)
    except (OSError, UnicodeDecodeError, FrontmatterError):
        result = False
    else:
        result = bool(fm.get("orphaned") is True)

    with _orphan_cache_lock:
        _orphan_cache[cache_key] = result
        _orphan_cache.move_to_end(cache_key)
        while len(_orphan_cache) > _MAX_CACHE_ENTRIES:
            _orphan_cache.popitem(last=False)
    return result


def scope_guard(
    path: Path,
    *,
    vault_root: Path,
    allowed_domains: Iterable[str],
    include_orphans: bool = False,
) -> Path:
    """Return the resolved path if it is inside an allowed domain, else raise ScopeError.

    Enforcement:
    - Resolves symlinks and ``..`` segments.
    - Requires the resolved path to be a descendant of vault_root.
    - Requires the first path component under vault_root to be in allowed_domains.
    - When ``include_orphans=False`` (default): raises
      :class:`OrphanedNoteError` if the resolved path is an existing
      ``.md`` file whose frontmatter has ``orphaned: true``. Skipped for
      directories, missing files (e.g. ``new_files`` patch pre-validation),
      non-``.md`` files, and files without parseable frontmatter.
    - When ``include_orphans=True``: the orphan check is SKIPPED
      entirely — no frontmatter read, no I/O. Use this for the orphan-
      management tools (``brain_list_orphans``, ``brain_restore_orphan``,
      ``brain_delete_orphan``) where the caller is explicitly operating
      on orphaned notes.

    Backwards-compat: every existing call site uses positional / keyword
    domain args and does NOT pass ``include_orphans``; they continue to
    work unchanged because ``include_orphans=False`` is a strict
    superset of the pre-T4 behavior — the only new rejection mode is
    orphaned notes, which by D2 must be hidden from discovery paths.
    """
    vault_root = vault_root.resolve()
    resolved = path.resolve()

    try:
        rel = resolved.relative_to(vault_root)
    except ValueError as exc:
        raise ScopeError(f"{path} is not inside vault {vault_root}") from exc

    if not rel.parts:
        raise ScopeError(f"{path} resolves to vault root, not a domain")

    domain = rel.parts[0]
    allowed = tuple(allowed_domains)
    if domain not in allowed:
        raise ScopeError(f"{path} domain {domain!r} not in allowed {allowed}")

    if not include_orphans and _is_note_orphaned(resolved):
        raise OrphanedNoteError(
            f"{path} is an orphaned note; pass include_orphans=True to access it"
        )

    return resolved
