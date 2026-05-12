"""Tests for ``IngestPipeline.mark_orphaned`` — Plan 22 T3.

Six primary fixtures pin the D2 non-destructive orphan-mark contract:

1. **Normal-mark**: not-yet-orphaned note → frontmatter flipped to
   ``orphaned: true`` + ``orphaned_at: <today>``; body BYTE-IDENTICAL;
   ``orphan | mark | <slug>`` log line; undo record persisted.
2. **Idempotent no-op**: already-orphaned note → no vault write;
   ``orphaned_at`` PRESERVED (audit invariant — original mark date
   survives a re-call); ``orphan | no_change | <slug>`` log line.
3. **Body-unchanged pin**: explicit byte-level assertion on the body
   after :meth:`parse_frontmatter` round-trip — only frontmatter changes.
4. **Undo round-trip**: ``mark_orphaned`` → ``UndoLog.revert`` → note
   restored to its pre-mark frontmatter (orphaned absent / false again).
5. **Scope-violation**: existing note's domain not in ``allowed_domains``
   → raises ``ScopeError``; no vault write.
6. **Missing-note**: nonexistent path → status ``FAILED``, no raise to
   the caller (matches :meth:`update_source` shape so T5 / T6 callers
   branch on status uniformly).

Plus an LLM-not-called pin (the orphan path must not touch the model)
and a no-other-frontmatter-mutation pin (only ``orphaned`` +
``orphaned_at`` differ).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestStatus
from brain_core.llm.fake import FakeLLMProvider
from brain_core.vault.frontmatter import (
    parse_frontmatter,
    serialize_with_frontmatter,
)
from brain_core.vault.log import LogFile
from brain_core.vault.paths import ScopeError
from brain_core.vault.undo import UndoLog
from brain_core.vault.writer import VaultWriter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_pipeline(vault_root: Path, fake: FakeLLMProvider) -> IngestPipeline:
    """Construct a pipeline with stub models — same shape as T2's helpers."""
    return IngestPipeline(
        vault_root=vault_root,
        writer=VaultWriter(vault_root=vault_root),
        llm=fake,
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
    )


_DEFAULT_BODY = (
    "# Hello\n\n"
    "A greeting.\n\n"
    "## Key points\n\n- says hi\n\n"
    "## Entities\n\n_(none)_\n\n"
    "## Concepts\n\n_(none)_\n\n"
    "## Open questions\n\n_(none)_\n"
)


def _seed_existing_note(
    *,
    vault_root: Path,
    domain: str,
    slug: str,
    title: str = "Hello",
    created: str = "2026-04-01",
    extra_fm: dict[str, object] | None = None,
    body_override: str | None = None,
) -> Path:
    """Write an "already-ingested" source note. Mirrors T2's helper.

    A ``source_path`` frontmatter field is included by default so the
    fixture resembles a watched-folder-ingested note (the primary
    real-world :meth:`mark_orphaned` caller). Callers can override via
    ``extra_fm``.
    """
    note_dir = vault_root / domain / "sources"
    note_dir.mkdir(parents=True, exist_ok=True)
    note_path = note_dir / f"{slug}.md"
    fm: dict[str, object] = {
        "title": title,
        "domain": domain,
        "type": "source",
        "created": created,
        "updated": created,
        "source_type": "text",
        "source_url": None,
        "content_hash": "deadbeef" * 8,
        "ingested_by": "brain",
        "source_path": "/Users/test/watched/hello.txt",
    }
    if extra_fm:
        fm.update(extra_fm)
    body = body_override if body_override is not None else _DEFAULT_BODY
    note_path.write_text(
        serialize_with_frontmatter(fm, body=body), encoding="utf-8"
    )
    return note_path


def _read_log_lines(vault_root: Path, domain: str) -> list[str]:
    """Return non-blank lines from <domain>/log.md."""
    log_path = vault_root / domain / "log.md"
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# 1. Normal mark: not-yet-orphaned note → frontmatter flipped, body unchanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_orphaned_flips_frontmatter_and_preserves_body(
    ephemeral_vault: Path,
) -> None:
    """Default path: ``orphaned: true`` + ``orphaned_at: <today>``; body intact.

    Locked invariants:
    - ``orphaned`` frontmatter flips ``False`` → ``True``.
    - ``orphaned_at`` set to today's date (ISO 8601 string per project convention).
    - Note body BYTE-IDENTICAL to the pre-mark version (T3 review criterion c).
    - Other frontmatter fields (``title``, ``domain``, ``created``,
      ``content_hash``, ``source_path``) unchanged.
    - ``orphan | mark | <slug>`` log line landed via the ``orphan`` verb
      (greppable distinctly from ``patch`` / ``update``).
    - LLM not called (the fake's queue is empty; any call would raise).
    """
    note_path = _seed_existing_note(
        vault_root=ephemeral_vault,
        domain="research",
        slug="hello",
    )
    original_content = note_path.read_text(encoding="utf-8")
    original_fm, original_body = parse_frontmatter(original_content)

    fake = FakeLLMProvider()  # empty queue → any LLM call raises
    p = _build_pipeline(ephemeral_vault, fake)

    res = p.mark_orphaned(
        note_path,
        allowed_domains=("research",),
    )

    assert res.status is IngestStatus.OK
    assert res.note_path == note_path
    assert fake.requests == [], "mark_orphaned must NOT call the LLM"

    new_fm, new_body = parse_frontmatter(note_path.read_text(encoding="utf-8"))

    # orphaned flag flipped
    assert new_fm["orphaned"] is True
    # orphaned_at = today's ISO date
    today_iso = date.today().isoformat()
    # YAML serializes a `date` scalar — round-trip can come back as
    # either str or date depending on the loader. Accept both.
    assert (
        new_fm["orphaned_at"] == today_iso
        or str(new_fm["orphaned_at"]) == today_iso
    ), f"expected orphaned_at == {today_iso!r}; got {new_fm['orphaned_at']!r}"

    # Other frontmatter preserved verbatim
    assert new_fm["title"] == original_fm["title"]
    assert new_fm["domain"] == original_fm["domain"]
    assert new_fm["created"] == original_fm["created"]
    assert new_fm["content_hash"] == original_fm["content_hash"]
    assert new_fm["source_path"] == original_fm["source_path"]
    # No `updated` re-stamp — orphan-mark is metadata only, not a content
    # update. (If a future plan wants to track "last mutation date" via
    # `updated`, flip this assertion and update the helper.)
    assert new_fm.get("updated") == original_fm.get("updated")

    # Body BYTE-IDENTICAL
    assert new_body == original_body, (
        "T3 review criterion (c): body must not change on orphan mark"
    )

    # Log line via ``orphan`` verb
    log_lines = _read_log_lines(ephemeral_vault, "research")
    assert any("orphan" in line and "mark | hello" in line for line in log_lines), (
        f"expected `orphan | mark | hello` line; got {log_lines!r}"
    )

    # Log entry round-trips through LogFile parser with op="orphan"
    log = LogFile(ephemeral_vault / "research" / "log.md")
    entries = log.read_all()
    orphan_entries = [e for e in entries if e.op == "orphan"]
    assert len(orphan_entries) == 1
    assert "mark | hello" in orphan_entries[0].summary


# ---------------------------------------------------------------------------
# 2. Idempotent no-op: already-orphaned → no write, orphaned_at preserved
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_orphaned_is_idempotent_when_already_orphaned(
    ephemeral_vault: Path,
) -> None:
    """Re-marking an orphan is a no-op: no vault write, no orphaned_at refresh.

    The original ``orphaned_at`` is the audit record of WHEN the source
    disappeared. A re-call (e.g. watcher fires twice on the same delete
    event) must preserve that timestamp — not refresh it to today.
    """
    original_orphan_date = "2026-05-01"  # past date — predates "today"
    note_path = _seed_existing_note(
        vault_root=ephemeral_vault,
        domain="research",
        slug="hello",
        extra_fm={"orphaned": True, "orphaned_at": original_orphan_date},
    )
    original_content = note_path.read_text(encoding="utf-8")

    fake = FakeLLMProvider()
    p = _build_pipeline(ephemeral_vault, fake)

    res = p.mark_orphaned(
        note_path,
        allowed_domains=("research",),
    )

    assert res.status is IngestStatus.OK
    assert res.note_path == note_path

    # No vault write — content byte-for-byte identical
    assert note_path.read_text(encoding="utf-8") == original_content, (
        "idempotent re-mark must NOT rewrite the vault note"
    )

    # Frontmatter still carries the ORIGINAL orphaned_at, not today's date
    fm, _body = parse_frontmatter(note_path.read_text(encoding="utf-8"))
    assert fm["orphaned"] is True
    assert (
        fm["orphaned_at"] == original_orphan_date
        or str(fm["orphaned_at"]) == original_orphan_date
    ), (
        "idempotent re-mark must preserve original orphaned_at — it's the "
        "audit record of the original disappearance"
    )

    # Log line with the no_change sub-verb is still emitted (greppability)
    log_lines = _read_log_lines(ephemeral_vault, "research")
    assert any("orphan" in line and "no_change | hello" in line for line in log_lines), (
        f"expected `orphan | no_change | hello` line; got {log_lines!r}"
    )


# ---------------------------------------------------------------------------
# 3. Body unchanged pin (explicit) — paranoid byte-level check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_orphaned_body_is_byte_identical(
    ephemeral_vault: Path,
) -> None:
    """Belt-and-braces pin: body bytes are identical pre- and post-mark.

    Even a stray reformatting in :meth:`_rewrite_frontmatter_for_orphan`
    (e.g. an extra trailing newline injected during serialize) is caught
    here. T3 review criterion (c) explicit.
    """
    distinctive_body = (
        "# Distinctive Title\n\n"
        "Body with TRAILING WHITESPACE   \n"
        "Special chars: — • → ←\n\n"
        "## Section A\n\n- one\n- two\n\n"
        "## Section B\n\nMulti-line\nparagraph here.\n"
    )
    note_path = _seed_existing_note(
        vault_root=ephemeral_vault,
        domain="research",
        slug="distinctive",
        body_override=distinctive_body,
    )
    _original_fm, original_body = parse_frontmatter(
        note_path.read_text(encoding="utf-8")
    )

    fake = FakeLLMProvider()
    p = _build_pipeline(ephemeral_vault, fake)

    res = p.mark_orphaned(note_path, allowed_domains=("research",))
    assert res.status is IngestStatus.OK

    _new_fm, new_body = parse_frontmatter(note_path.read_text(encoding="utf-8"))
    assert new_body == original_body, (
        "body must be byte-identical; the orphan path mutates frontmatter only"
    )


# ---------------------------------------------------------------------------
# 4. Undo round-trip: mark → revert → frontmatter back to pre-mark state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_orphaned_undo_round_trip_restores_pre_mark_frontmatter(
    ephemeral_vault: Path,
) -> None:
    """``brain_undo_last`` must reverse a ``mark_orphaned`` cleanly.

    T3 review criterion (b): undo log entry landed so the orphan mark is
    revertible. Specifically, after revert the note's content is BYTE-
    IDENTICAL to its pre-mark state (frontmatter back to ``orphaned:
    false`` from the typed-class default, or absent depending on whether
    the field was in the original).
    """
    note_path = _seed_existing_note(
        vault_root=ephemeral_vault,
        domain="research",
        slug="hello",
        # Deliberately DON'T include an `orphaned` key — match the common
        # pre-Plan-22 note shape so we can pin that revert restores the
        # absence, not a False stamping.
    )
    pre_mark_content = note_path.read_text(encoding="utf-8")
    pre_mark_fm, _pre_mark_body = parse_frontmatter(pre_mark_content)
    assert "orphaned" not in pre_mark_fm, (
        "test premise: pre-mark note does NOT carry the orphaned key"
    )

    fake = FakeLLMProvider()
    p = _build_pipeline(ephemeral_vault, fake)

    res = p.mark_orphaned(note_path, allowed_domains=("research",))
    assert res.status is IngestStatus.OK

    # Confirm the mark landed
    marked_fm, _body = parse_frontmatter(note_path.read_text(encoding="utf-8"))
    assert marked_fm["orphaned"] is True

    # Locate the undo record. The writer doesn't surface the undo_id
    # through mark_orphaned's result (D2: keep the surface minimal), so
    # we read the most-recent file in .brain/undo/ — the same shape
    # `brain_undo_last` would invoke via UndoLog.revert(latest_undo_id).
    undo_dir = ephemeral_vault / ".brain" / "undo"
    records = sorted(undo_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime)
    assert records, "mark_orphaned must persist an undo record"
    latest_undo_id = records[-1].stem

    log = UndoLog(vault_root=ephemeral_vault)
    log.revert(latest_undo_id)

    # Note content restored to pre-mark bytes
    restored_content = note_path.read_text(encoding="utf-8")
    assert restored_content == pre_mark_content, (
        "after brain_undo_last revert, note must match pre-mark bytes"
    )
    restored_fm, _restored_body = parse_frontmatter(restored_content)
    assert "orphaned" not in restored_fm, (
        "revert must restore the original frontmatter (no orphaned key)"
    )


# ---------------------------------------------------------------------------
# 5. Scope violation: note's domain outside allowed_domains → ScopeError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_orphaned_refuses_when_note_domain_outside_scope(
    ephemeral_vault: Path,
) -> None:
    """A watcher in ("research",) scope cannot orphan a personal-domain note.

    ``scope_guard`` rejects the path at Stage A — before any vault
    mutation. The raise is the documented "clearly" signal: a
    ``ScopeError`` (subclass of ``PermissionError``).
    """
    note_path = _seed_existing_note(
        vault_root=ephemeral_vault,
        domain="personal",
        slug="secret",
    )
    original_content = note_path.read_text(encoding="utf-8")

    fake = FakeLLMProvider()
    p = _build_pipeline(ephemeral_vault, fake)

    with pytest.raises(ScopeError):
        p.mark_orphaned(
            note_path,
            allowed_domains=("research",),  # personal NOT in scope
        )

    # Vault untouched
    assert note_path.read_text(encoding="utf-8") == original_content
    assert fake.requests == []


# ---------------------------------------------------------------------------
# 6. Missing note: path doesn't exist → status FAILED, no vault mutation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_orphaned_returns_failed_when_note_path_missing(
    ephemeral_vault: Path,
) -> None:
    """Nonexistent vault path → status ``FAILED`` (mirrors update_source).

    The path-level ``scope_guard`` accepts an absent file (it only checks
    the path is inside the vault under an allowed domain), so the
    FileNotFoundError surfaces from the subsequent ``read_text`` and
    flows to the FAILED branch. Callers see a clear status code; no
    surprise raise to the watcher's main loop.
    """
    missing_path = ephemeral_vault / "research" / "sources" / "does-not-exist.md"
    assert not missing_path.exists()

    fake = FakeLLMProvider()
    p = _build_pipeline(ephemeral_vault, fake)

    res = p.mark_orphaned(missing_path, allowed_domains=("research",))

    assert res.status is IngestStatus.FAILED
    assert res.errors, "FAILED status must include an error message"
    # No log entry, no vault write — the failure happens before stage E.
    log_lines = _read_log_lines(ephemeral_vault, "research")
    assert not any(
        "orphan" in line and "does-not-exist" in line for line in log_lines
    ), "missing-note path must NOT emit an orphan log entry"


# ---------------------------------------------------------------------------
# 7. Other frontmatter not mutated — explicit field-by-field pin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_orphaned_does_not_mutate_other_frontmatter_fields(
    ephemeral_vault: Path,
) -> None:
    """Only ``orphaned`` and ``orphaned_at`` may change.

    Pin every other field in the seeded frontmatter. Catches a future
    refactor that "helpfully" re-stamps ``updated`` or normalizes
    ``source_path`` casing on the orphan path — both would be wrong (the
    orphan path is metadata only, not a content update).
    """
    note_path = _seed_existing_note(
        vault_root=ephemeral_vault,
        domain="research",
        slug="hello",
        extra_fm={
            "watched_folder_id": "/Users/test/watch_a",
            # User-added extras (Frontmatter extra="allow")
            "aliases": ["hi", "hello-doc"],
            "cssclass": "important",
        },
    )
    original_fm, _body = parse_frontmatter(note_path.read_text(encoding="utf-8"))

    fake = FakeLLMProvider()
    p = _build_pipeline(ephemeral_vault, fake)

    p.mark_orphaned(note_path, allowed_domains=("research",))

    new_fm, _new_body = parse_frontmatter(note_path.read_text(encoding="utf-8"))

    mutable_keys = {"orphaned", "orphaned_at"}
    for key, original_value in original_fm.items():
        if key in mutable_keys:
            continue
        assert new_fm.get(key) == original_value, (
            f"frontmatter key {key!r} must not be mutated by mark_orphaned; "
            f"was {original_value!r}, now {new_fm.get(key)!r}"
        )
    # And the user-added extras survived
    assert new_fm["aliases"] == ["hi", "hello-doc"]
    assert new_fm["cssclass"] == "important"
    assert new_fm["watched_folder_id"] == "/Users/test/watch_a"
