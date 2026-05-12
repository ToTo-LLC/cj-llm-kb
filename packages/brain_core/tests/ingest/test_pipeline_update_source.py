"""Tests for ``IngestPipeline.update_source`` — Plan 22 T2.

Five primary fixtures pin the contract:

1. **No-op**: same content_hash, same resolved source_path → no LLM call,
   no vault mutation, ``update | no_change`` log line emitted.
2. **Overwrite** (D1): different content_hash → vault note replaced;
   ``domain`` + ``created`` + ``watched_folder_id`` preserved; ``updated`` +
   ``content_hash`` + ``source_path`` + ``title`` replaced; ``update |
   overwrite`` log line.
3. **Vault-edit overwrite** (D1 contract): vault note's body hand-edited
   AFTER first ingest; re-ingest BLOWS AWAY the hand edits. Pin so a
   future plan introducing a vault-edit-aware merge path knows what to
   change.
4. **Source-path-change** (move scenario): same content_hash, different
   resolved path → frontmatter ``source_path`` updated, body unchanged,
   no LLM call, ``update | path_only`` log line.
5. **Scope violation**: existing note's domain not in ``allowed_domains``
   → raises ``ScopeError`` clearly; no vault write.

Plus a slug-preservation pin and an orphan-clearing pin to lock the
finer-grained contract (slug/wikilinks remain valid; a successful
re-ingest clears prior ``orphaned: true`` marks per the
:meth:`_rebuild_note` contract).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestStatus
from brain_core.llm.fake import FakeLLMProvider
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.vault.frontmatter import (
    parse_frontmatter,
    serialize_with_frontmatter,
)
from brain_core.vault.log import LogFile
from brain_core.vault.paths import ScopeError
from brain_core.vault.types import IndexEntryPatch, PatchSet
from brain_core.vault.writer import VaultWriter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_pipeline(vault_root: Path, fake: FakeLLMProvider) -> IngestPipeline:
    """Construct a pipeline with stub models — same shape as test_pipeline.py."""
    return IngestPipeline(
        vault_root=vault_root,
        writer=VaultWriter(vault_root=vault_root),
        llm=fake,
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
    )


def _seed_existing_note(
    *,
    vault_root: Path,
    domain: str,
    slug: str,
    source_path: Path,
    body_text: str,
    title: str = "Hello",
    created: str = "2026-04-01",
    extra_fm: dict[str, object] | None = None,
    body_override: str | None = None,
) -> Path:
    """Write an "already-ingested" source note + matching archive copy.

    Mirrors the canonical layout that :meth:`IngestPipeline._build_source_note`
    would produce for the same input. The body defaults to the standard
    template; pass ``body_override`` to simulate a hand-edit.
    """
    from brain_core.ingest.hashing import content_hash

    note_dir = vault_root / domain / "sources"
    note_dir.mkdir(parents=True, exist_ok=True)
    note_path = note_dir / f"{slug}.md"

    chash = content_hash(body_text)
    fm: dict[str, object] = {
        "title": title,
        "domain": domain,
        "type": "source",
        "created": created,
        "updated": created,
        "source_type": "text",
        "source_url": None,
        "content_hash": chash,
        "ingested_by": "brain",
        "source_path": str(source_path.resolve()),
    }
    if extra_fm:
        fm.update(extra_fm)
    body = body_override if body_override is not None else (
        f"# {title}\n\n"
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


def _read_log_lines(vault_root: Path, domain: str) -> list[str]:
    """Return non-blank lines from <domain>/log.md."""
    log_path = vault_root / domain / "log.md"
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _queue_overwrite_responses(fake: FakeLLMProvider) -> None:
    """Queue summarize + integrate responses (no classify — D4)."""
    fake.queue(
        SummarizeOutput(
            title="Hello v2",
            summary="A revised greeting.",
            key_points=["says hi again"],
            entities=["brain"],
            concepts=["greeting"],
            open_questions=[],
        ).model_dump_json()
    )
    fake.queue(
        PatchSet(
            new_files=[],
            edits=[],
            index_entries=[],
            log_entry="integrate-discarded",
            reason="t",
        ).model_dump_json()
    )


# ---------------------------------------------------------------------------
# 1. No-op: same hash + same path → no LLM, no vault mutation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_source_no_op_when_hash_and_path_unchanged(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """No content change + no path change → no LLM call, no vault write.

    The fake's queue is intentionally EMPTY; if `update_source` calls
    summarize/integrate, ``FakeLLMProvider.complete`` raises ``RuntimeError``.
    """
    body = "Hello, brain.\nUnchanged source.\n"
    source_path = tmp_path / "hello.txt"
    source_path.write_text(body, encoding="utf-8")

    note_path = _seed_existing_note(
        vault_root=ephemeral_vault,
        domain="research",
        slug="hello",
        source_path=source_path,
        body_text=body,
    )
    original_note_content = note_path.read_text(encoding="utf-8")

    fake = FakeLLMProvider()  # empty queue → any LLM call raises
    p = _build_pipeline(ephemeral_vault, fake)

    res = await p.update_source(
        note_path,
        source_path,
        allowed_domains=("research",),
    )

    assert res.status is IngestStatus.OK
    assert res.note_path == note_path
    # No LLM call happened
    assert fake.requests == []
    # No file mutation — content byte-for-byte identical
    assert note_path.read_text(encoding="utf-8") == original_note_content
    # Log line was emitted with the no_change sub-verb
    log_lines = _read_log_lines(ephemeral_vault, "research")
    assert any("update" in line and "no_change | hello" in line for line in log_lines), (
        f"expected `update | no_change | hello` line; got {log_lines!r}"
    )


# ---------------------------------------------------------------------------
# 2. Overwrite: content changed → vault note replaced; domain/created preserved
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_source_overwrites_on_content_change(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """Different body bytes → summary + integrate run, vault note replaced.

    Locked invariants:
    - ``domain`` preserved (no re-classify call queued).
    - ``created`` preserved.
    - ``title`` / ``content_hash`` / ``updated`` replaced.
    - ``watched_folder_id`` preserved (round-trips through the dict path).
    - Slug preserved (note path unchanged).
    """
    old_body = "Hello, brain.\nVersion one.\n"
    new_body = "Hello, brain.\nVersion two — totally different content.\n"
    source_path = tmp_path / "hello.txt"
    source_path.write_text(old_body, encoding="utf-8")

    note_path = _seed_existing_note(
        vault_root=ephemeral_vault,
        domain="research",
        slug="hello",
        source_path=source_path,
        body_text=old_body,
        title="Hello",
        created="2026-04-01",
        extra_fm={"watched_folder_id": "/Users/test/watch_a"},
    )

    # Now the source file changes on disk:
    source_path.write_text(new_body, encoding="utf-8")

    fake = FakeLLMProvider()
    _queue_overwrite_responses(fake)
    p = _build_pipeline(ephemeral_vault, fake)

    res = await p.update_source(
        note_path,
        source_path,
        allowed_domains=("research",),
    )

    assert res.status is IngestStatus.OK
    assert res.note_path == note_path
    # No classify call: only summarize + integrate consumed
    assert len(fake.requests) == 2, (
        f"expected 2 LLM calls (summarize + integrate); got {len(fake.requests)}"
    )

    # Frontmatter assertions
    new_content = note_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(new_content)
    assert fm["domain"] == "research", "domain MUST be preserved per D4"
    assert fm["created"] == "2026-04-01" or str(fm["created"]) == "2026-04-01", (
        "created MUST be preserved across re-ingest"
    )
    assert fm["title"] == "Hello v2", "title comes from new summary per D1 overwrite"
    assert fm["watched_folder_id"] == "/Users/test/watch_a", (
        "watched_folder_id MUST be preserved"
    )
    # content_hash refreshed
    from brain_core.ingest.hashing import content_hash

    assert fm["content_hash"] == content_hash(new_body)
    # source_path refreshed to the resolved path
    assert fm["source_path"] == str(source_path.resolve())
    # Body rebuilt from new summary
    assert "# Hello v2" in body
    assert "A revised greeting." in body
    assert "says hi again" in body
    # Slug preserved — note still at the same path
    assert note_path == ephemeral_vault / "research" / "sources" / "hello.md"

    # Log line
    log_lines = _read_log_lines(ephemeral_vault, "research")
    assert any("update" in line and "overwrite | hello" in line for line in log_lines), (
        f"expected `update | overwrite | hello`; got {log_lines!r}"
    )


# ---------------------------------------------------------------------------
# 3. Vault-edit overwrite: vault edits LOST per D1
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_source_overwrites_vault_hand_edits_per_d1(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """D1 (overwrite) contract: vault-side hand-edits are LOST on re-ingest.

    Pin for a future plan that adds vault-edit-aware merge. If/when that
    plan ships, THIS test should be the first to flip — change the
    assertion to "hand-edit preserved" and the production code's overwrite
    branch becomes the merge branch.
    """
    old_body = "Hello, brain.\nVersion one.\n"
    new_body = "Hello, brain.\nVersion two.\n"
    source_path = tmp_path / "hello.txt"
    source_path.write_text(old_body, encoding="utf-8")

    # Seed an existing note whose vault BODY has been hand-edited — note
    # the user-added section + the modified summary line. The frontmatter
    # content_hash still references the ORIGINAL source body (correct —
    # content_hash hashes the source, not the vault body).
    hand_edited_body = (
        "# Hello\n\n"
        "A greeting. USER-EDITED COMMENT.\n\n"
        "## Key points\n\n- says hi\n\n"
        "## My notes\n\n- this section was hand-added by the user\n\n"
        "## Entities\n\n_(none)_\n\n"
        "## Concepts\n\n_(none)_\n\n"
        "## Open questions\n\n_(none)_\n"
    )
    note_path = _seed_existing_note(
        vault_root=ephemeral_vault,
        domain="research",
        slug="hello",
        source_path=source_path,
        body_text=old_body,
        body_override=hand_edited_body,
    )

    # Source file now changes.
    source_path.write_text(new_body, encoding="utf-8")

    fake = FakeLLMProvider()
    _queue_overwrite_responses(fake)
    p = _build_pipeline(ephemeral_vault, fake)

    res = await p.update_source(
        note_path,
        source_path,
        allowed_domains=("research",),
    )

    assert res.status is IngestStatus.OK
    new_content = note_path.read_text(encoding="utf-8")
    _fm, new_body_text = parse_frontmatter(new_content)
    # D1 contract: hand edits ARE lost. If this assertion ever needs to
    # flip, that's the signal a vault-edit-aware merge plan is needed —
    # find me and update.
    assert "USER-EDITED COMMENT" not in new_body_text, (
        "D1 overwrite contract: hand-edited body must NOT survive re-ingest. "
        "If this assertion needs to flip, a vault-edit-aware merge plan is in scope."
    )
    assert "## My notes" not in new_body_text, (
        "D1 overwrite contract: user-added sections must NOT survive re-ingest"
    )
    assert "A revised greeting." in new_body_text, "new summary body landed"


# ---------------------------------------------------------------------------
# 4. Source-path-change: same hash, different path → frontmatter-only update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_source_path_only_on_move_with_same_content(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """Source moved on disk (same body, different path) → frontmatter-only update.

    No LLM call. Body unchanged. ``source_path`` updated to the new
    resolved path. Log line uses the ``path_only`` sub-verb.
    """
    body = "Hello, brain.\nSame body, moved file.\n"
    old_source_dir = tmp_path / "original"
    new_source_dir = tmp_path / "moved"
    old_source_dir.mkdir()
    new_source_dir.mkdir()
    old_source = old_source_dir / "hello.txt"
    new_source = new_source_dir / "hello.txt"
    old_source.write_text(body, encoding="utf-8")

    note_path = _seed_existing_note(
        vault_root=ephemeral_vault,
        domain="research",
        slug="hello",
        source_path=old_source,
        body_text=body,
    )
    # Snapshot the existing body section (post-frontmatter) so we can
    # assert it survives unchanged after the path-only update.
    original_fm, original_body = parse_frontmatter(note_path.read_text(encoding="utf-8"))

    # The file is "moved": same body, different path. The old file may or
    # may not still exist on disk — we point update_source at the new path.
    new_source.write_text(body, encoding="utf-8")

    fake = FakeLLMProvider()  # empty queue → any LLM call raises
    p = _build_pipeline(ephemeral_vault, fake)

    res = await p.update_source(
        note_path,
        new_source,
        allowed_domains=("research",),
    )

    assert res.status is IngestStatus.OK
    assert res.note_path == note_path
    assert fake.requests == [], "path-only update must NOT call LLM"

    new_fm, new_body_text = parse_frontmatter(note_path.read_text(encoding="utf-8"))
    assert new_fm["source_path"] == str(new_source.resolve()), (
        "source_path frontmatter must point at the new location"
    )
    # `updated` re-stamped (the date may equal `created` if both fall on
    # the same calendar day, so just check it's present and string-like).
    assert "updated" in new_fm
    # Body unchanged
    assert new_body_text == original_body, (
        "path-only update must preserve body byte-for-byte"
    )
    # content_hash unchanged
    assert new_fm["content_hash"] == original_fm["content_hash"]

    # Log line
    log_lines = _read_log_lines(ephemeral_vault, "research")
    assert any("update" in line and "path_only | hello" in line for line in log_lines), (
        f"expected `update | path_only | hello`; got {log_lines!r}"
    )


# ---------------------------------------------------------------------------
# 5. Scope violation: note's domain not in allowed_domains → raises clearly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_source_refuses_when_note_domain_outside_scope(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """A watcher in ("research",) scope cannot update a personal-domain note.

    ``scope_guard`` rejects the path at Stage A — before any vault
    mutation, before any LLM call. The raise is the documented "clearly"
    signal: a ``ScopeError`` (a subclass of ``PermissionError``).
    """
    body = "personal text"
    source_path = tmp_path / "secret.txt"
    source_path.write_text(body, encoding="utf-8")

    note_path = _seed_existing_note(
        vault_root=ephemeral_vault,
        domain="personal",
        slug="secret",
        source_path=source_path,
        body_text=body,
    )
    original_content = note_path.read_text(encoding="utf-8")

    fake = FakeLLMProvider()
    p = _build_pipeline(ephemeral_vault, fake)

    with pytest.raises(ScopeError):
        await p.update_source(
            note_path,
            source_path,
            allowed_domains=("research",),  # personal NOT in scope
        )

    # Vault untouched
    assert note_path.read_text(encoding="utf-8") == original_content
    assert fake.requests == []


# ---------------------------------------------------------------------------
# 6. Slug + note path preserved on overwrite (D4 wikilink-stability invariant)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_source_preserves_slug_and_note_path_on_overwrite(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """Even when the new summary title would yield a different slug, the
    note path stays put — wikilinks pointing at the old slug remain valid.

    The new summary title is "Totally Different Title" — slugified to
    ``totally-different-title``. If the production code re-derived the
    slug from the title, the note would move and wikilinks would break.
    D4 forbids this.
    """
    old_body = "v1 body"
    new_body = "v2 body different"
    source_path = tmp_path / "hello.txt"
    source_path.write_text(old_body, encoding="utf-8")

    note_path = _seed_existing_note(
        vault_root=ephemeral_vault,
        domain="research",
        slug="hello",
        source_path=source_path,
        body_text=old_body,
    )
    source_path.write_text(new_body, encoding="utf-8")

    fake = FakeLLMProvider()
    fake.queue(
        SummarizeOutput(
            title="Totally Different Title",
            summary="something else",
            key_points=["x"],
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
            log_entry=None,
            reason="t",
        ).model_dump_json()
    )

    p = _build_pipeline(ephemeral_vault, fake)
    res = await p.update_source(
        note_path,
        source_path,
        allowed_domains=("research",),
    )

    assert res.status is IngestStatus.OK
    # Note path identity preserved — wikilinks stable.
    assert res.note_path == note_path
    assert note_path.exists()
    # No companion file at the would-be slug derived from the new title.
    new_slug_path = ephemeral_vault / "research" / "sources" / "totally-different-title.md"
    assert not new_slug_path.exists(), (
        "D4: slug must be preserved on re-ingest; a new title MUST NOT "
        "spawn a sibling file"
    )


# ---------------------------------------------------------------------------
# 7. Orphan-clearing on successful re-ingest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_source_clears_orphan_mark_on_successful_overwrite(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """A successful re-ingest implies the source is back on disk —
    ``orphaned`` flips to ``False`` and ``orphaned_at`` clears.

    Pin so T3 (``mark_orphaned``) and the watcher's create-after-delete
    flow have a documented inverse.
    """
    old_body = "version one"
    new_body = "version two"
    source_path = tmp_path / "hello.txt"
    source_path.write_text(old_body, encoding="utf-8")

    note_path = _seed_existing_note(
        vault_root=ephemeral_vault,
        domain="research",
        slug="hello",
        source_path=source_path,
        body_text=old_body,
        extra_fm={"orphaned": True, "orphaned_at": "2026-05-01"},
    )
    source_path.write_text(new_body, encoding="utf-8")

    fake = FakeLLMProvider()
    _queue_overwrite_responses(fake)
    p = _build_pipeline(ephemeral_vault, fake)

    res = await p.update_source(
        note_path,
        source_path,
        allowed_domains=("research",),
    )

    assert res.status is IngestStatus.OK
    fm, _body = parse_frontmatter(note_path.read_text(encoding="utf-8"))
    assert fm["orphaned"] is False, "successful re-ingest must clear orphan flag"
    assert fm["orphaned_at"] is None, "successful re-ingest must clear orphaned_at"


# ---------------------------------------------------------------------------
# 8. Log file emits exactly one `update` entry per successful run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_source_log_entry_is_greppable_update_verb(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """Per Plan 22 T2 review criterion (c): the log entry uses the
    ``update`` verb — distinct from ``patch`` (which ``writer.apply``
    stamps for ingest's PatchSet log entries). Pin via ``LogFile.read_all``
    so we round-trip through the same parser the rest of the system uses.
    """
    old_body = "v1"
    new_body = "v2"
    source_path = tmp_path / "hello.txt"
    source_path.write_text(old_body, encoding="utf-8")

    note_path = _seed_existing_note(
        vault_root=ephemeral_vault,
        domain="research",
        slug="hello",
        source_path=source_path,
        body_text=old_body,
    )
    source_path.write_text(new_body, encoding="utf-8")

    fake = FakeLLMProvider()
    _queue_overwrite_responses(fake)
    p = _build_pipeline(ephemeral_vault, fake)

    await p.update_source(note_path, source_path, allowed_domains=("research",))

    log = LogFile(ephemeral_vault / "research" / "log.md")
    entries = log.read_all()
    update_entries = [e for e in entries if e.op == "update"]
    assert len(update_entries) == 1, (
        f"expected exactly one op=update log entry; got {[e.op for e in entries]}"
    )
    assert "overwrite | hello" in update_entries[0].summary


# ---------------------------------------------------------------------------
# 9. Index-entry side effects from integrate land in the same atomic write
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_source_applies_integrate_index_entries(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """When the integrate stage proposes index entries (e.g. a newly-
    mentioned entity), they land in the same atomic VaultWriter call as
    the body replacement. Mirrors :meth:`ingest`'s integrate behavior so
    re-ingest doesn't silently drop the index side effects.
    """
    old_body = "v1 body"
    new_body = "v2 body with new entity"
    source_path = tmp_path / "hello.txt"
    source_path.write_text(old_body, encoding="utf-8")

    note_path = _seed_existing_note(
        vault_root=ephemeral_vault,
        domain="research",
        slug="hello",
        source_path=source_path,
        body_text=old_body,
    )
    source_path.write_text(new_body, encoding="utf-8")

    fake = FakeLLMProvider()
    fake.queue(
        SummarizeOutput(
            title="hello",
            summary="x",
            key_points=["x"],
            entities=["new_entity"],
            concepts=[],
            open_questions=[],
        ).model_dump_json()
    )
    fake.queue(
        PatchSet(
            new_files=[],
            edits=[],
            index_entries=[
                IndexEntryPatch(
                    section="Entities",
                    line="- [[new_entity]] — surfaced on re-ingest",
                    domain="research",
                )
            ],
            log_entry=None,
            reason="t",
        ).model_dump_json()
    )

    p = _build_pipeline(ephemeral_vault, fake)
    res = await p.update_source(
        note_path,
        source_path,
        allowed_domains=("research",),
    )
    assert res.status is IngestStatus.OK

    from brain_core.vault.index import IndexFile

    idx = IndexFile.load(ephemeral_vault / "research" / "index.md")
    assert any(e.target == "new_entity" for e in idx.sections["Entities"]), (
        "integrate stage's index_entries must apply alongside the body replacement"
    )
