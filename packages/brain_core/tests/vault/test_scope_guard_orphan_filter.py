"""Plan 22 T4 — pin tests for ``scope_guard(include_orphans=...)``.

Six fixtures cover the orphan-filter axis introduced by D2:

1. Default behavior (``include_orphans=False``) filters orphans →
   :class:`OrphanedNoteError`.
2. Explicit ``include_orphans=True`` returns the orphan path unchanged.
3. Mixed vault: non-orphan notes still pass with default args; orphan
   notes raise. Default filter does not bleed onto neighbors.
4. Cache invalidation: mutating a note's ``orphaned`` field bumps mtime
   (via ``atomic`` write) so the next ``scope_guard`` call reflects the
   new state without manual cache invalidation.
5. Non-note paths (directories, ``index.md`` without ``orphaned``,
   missing files for new-file pre-validation) skip the orphan check.
6. Hot-path no-op: when ``include_orphans=True``, scope_guard performs
   ZERO frontmatter reads — verified by patching ``_is_note_orphaned``
   to a counter.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from brain_core.vault import paths as paths_module
from brain_core.vault.paths import (
    OrphanedNoteError,
    ScopeError,
    _orphan_cache_clear,
    scope_guard,
)


@pytest.fixture(autouse=True)
def _clear_orphan_cache() -> None:
    """Each test starts with an empty orphan cache so memoized state
    from sibling tests can never leak across the fixture boundary."""
    _orphan_cache_clear()


def _write_note(path: Path, *, orphaned: bool, body: str = "body\n") -> None:
    """Write a minimal note with frontmatter including ``orphaned``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = (
        "---\n"
        "title: T4 fixture\n"
        "domain: research\n"
        "type: source\n"
        f"orphaned: {'true' if orphaned else 'false'}\n"
        "---\n\n"
    )
    path.write_text(fm + body, encoding="utf-8")


def test_default_filters_orphaned_note(ephemeral_vault: Path) -> None:
    """``scope_guard(...)`` without ``include_orphans`` raises on an orphan."""
    note = ephemeral_vault / "research" / "sources" / "orphan.md"
    _write_note(note, orphaned=True)
    with pytest.raises(OrphanedNoteError, match="orphaned note"):
        scope_guard(
            note,
            vault_root=ephemeral_vault,
            allowed_domains=("research",),
        )


def test_include_orphans_true_returns_orphan_path(ephemeral_vault: Path) -> None:
    """``include_orphans=True`` lets the orphan path through unchanged."""
    note = ephemeral_vault / "research" / "sources" / "orphan.md"
    _write_note(note, orphaned=True)
    result = scope_guard(
        note,
        vault_root=ephemeral_vault,
        allowed_domains=("research",),
        include_orphans=True,
    )
    assert result == note.resolve()


def test_mixed_vault_filters_only_orphans(ephemeral_vault: Path) -> None:
    """A vault with mixed notes: orphans raise, non-orphans pass.

    Pins that the default-filter does not over-reach onto neighboring
    notes that happen to share a parent directory.
    """
    live = ephemeral_vault / "research" / "sources" / "live.md"
    orphan = ephemeral_vault / "research" / "sources" / "orphan.md"
    _write_note(live, orphaned=False)
    _write_note(orphan, orphaned=True)

    # Live note: passes by default.
    result = scope_guard(
        live,
        vault_root=ephemeral_vault,
        allowed_domains=("research",),
    )
    assert result == live.resolve()

    # Orphan: raises by default.
    with pytest.raises(OrphanedNoteError):
        scope_guard(
            orphan,
            vault_root=ephemeral_vault,
            allowed_domains=("research",),
        )


def test_cache_invalidates_on_mtime_change(ephemeral_vault: Path) -> None:
    """Flipping ``orphaned`` and bumping mtime causes the cache to refresh.

    Mirrors what ``VaultWriter._atomic_write`` does in production —
    ``os.replace`` updates mtime on every write so the cache key
    ``(resolved_path, mtime_ns)`` naturally invalidates.
    """
    note = ephemeral_vault / "research" / "sources" / "n.md"
    _write_note(note, orphaned=False)

    # Default pass.
    result = scope_guard(
        note,
        vault_root=ephemeral_vault,
        allowed_domains=("research",),
    )
    assert result == note.resolve()

    # Flip to orphaned, bump mtime by 2s so the ns clock changes on
    # filesystems with second-level mtime resolution (e.g. ext4 default,
    # HFS+). Linux/macOS APFS and Windows NTFS both update on rewrite,
    # but the explicit os.utime bump makes the test deterministic
    # regardless of FS clock granularity.
    _write_note(note, orphaned=True)
    stat = note.stat()
    os.utime(note, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))

    with pytest.raises(OrphanedNoteError):
        scope_guard(
            note,
            vault_root=ephemeral_vault,
            allowed_domains=("research",),
        )


def test_non_note_paths_skip_orphan_check(ephemeral_vault: Path) -> None:
    """Directories, ``index.md`` (no orphan field), and missing files all
    pass scope_guard with default args — orphan check is gated on
    existing ``.md`` files with parseable frontmatter and
    ``orphaned: true``.
    """
    # Directory: domain-root resolves as a path with the domain as
    # first component. scope_guard accepts it (vault_root/domain is a
    # directory) and the orphan check skips because suffix != ".md".
    domain_dir = ephemeral_vault / "research"
    result = scope_guard(
        domain_dir,
        vault_root=ephemeral_vault,
        allowed_domains=("research",),
    )
    assert result == domain_dir.resolve()

    # index.md exists with frontmatter-less body — the ephemeral_vault
    # fixture writes a heading-only index.md. parse_frontmatter raises;
    # _is_note_orphaned catches and returns False.
    index = ephemeral_vault / "research" / "index.md"
    result = scope_guard(
        index,
        vault_root=ephemeral_vault,
        allowed_domains=("research",),
    )
    assert result == index.resolve()

    # Missing file (e.g. writer.apply new_files pre-validation): scope_guard
    # passes; orphan check no-ops on stat failure.
    missing = ephemeral_vault / "research" / "sources" / "not-yet.md"
    result = scope_guard(
        missing,
        vault_root=ephemeral_vault,
        allowed_domains=("research",),
    )
    assert result == missing.resolve()


def test_include_orphans_true_skips_frontmatter_read(
    ephemeral_vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``include_orphans=True`` MUST NOT read frontmatter.

    The orphan-listing path (``brain_list_orphans``) iterates over many
    notes per request. Forcing it through ``_is_note_orphaned`` would
    re-read each note's frontmatter on every call. Pin this by patching
    ``_is_note_orphaned`` to a counter and verifying it stays at zero.
    """
    note = ephemeral_vault / "research" / "sources" / "orphan.md"
    _write_note(note, orphaned=True)

    call_count = {"n": 0}

    def _counting_check(resolved: Path) -> bool:
        call_count["n"] += 1
        return False

    monkeypatch.setattr(paths_module, "_is_note_orphaned", _counting_check)

    # include_orphans=True: zero calls.
    scope_guard(
        note,
        vault_root=ephemeral_vault,
        allowed_domains=("research",),
        include_orphans=True,
    )
    assert call_count["n"] == 0

    # include_orphans=False (default): exactly one call.
    scope_guard(
        note,
        vault_root=ephemeral_vault,
        allowed_domains=("research",),
    )
    assert call_count["n"] == 1


def test_orphaned_note_error_is_scope_error(ephemeral_vault: Path) -> None:
    """:class:`OrphanedNoteError` is a :class:`ScopeError` subclass.

    Existing handlers (e.g. ``brain_search`` re-verification) catch
    ``ScopeError`` to drop disallowed hits. That same catch must also
    drop orphans without code changes — pins the inheritance chain.
    """
    note = ephemeral_vault / "research" / "sources" / "orphan.md"
    _write_note(note, orphaned=True)

    with pytest.raises(ScopeError):
        scope_guard(
            note,
            vault_root=ephemeral_vault,
            allowed_domains=("research",),
        )
