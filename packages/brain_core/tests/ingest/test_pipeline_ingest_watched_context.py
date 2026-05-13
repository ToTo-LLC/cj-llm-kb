"""Plan 22 T10.5 — pin watched-context kwargs on ``IngestPipeline.ingest``.

T1 added ``source_path`` + ``watched_folder_id`` to
:class:`brain_core.vault.frontmatter.Frontmatter`. T10 surfaced that the
9-stage ingest pipeline didn't populate them, so the T6
:class:`brain_core.watch.folder_watcher.WatchedFolderWatcher` lookup
(:func:`brain_core.watch.folder_watcher._index_vault_for_folder`)
returned ``None`` for every event → modify fell through to duplicate
ingest, delete silently no-opped.

T10.5 wires the two optional kwargs through the pipeline + bulk path:

* :meth:`IngestPipeline.ingest` takes ``source_path`` and
  ``watched_folder_id`` kwargs. Default ``None`` preserves the pre-T10.5
  contract for drag-drop / MCP ingest / paste-text call sites.
* When either kwarg is set, the source note's frontmatter carries the
  field. ``source_path`` is round-tripped as the resolved absolute-path
  string (mirrors T2's :meth:`update_source` convention so the watcher's
  lookup compares apples-to-apples).
* :meth:`BulkImporter.apply` adds a single ``watched_folder_id`` kwarg.
  When set, every per-item ``pipeline.ingest`` call receives both
  ``watched_folder_id`` AND a per-item ``source_path=item.spec``. When
  ``None`` (the default — drag-drop / standalone bulk-import), neither
  kwarg is threaded and notes keep the pre-T10.5 frontmatter shape.

The five tests pin the public contract:

1. Default kwargs → no watched-context fields on the note (backwards-compat).
2. ``source_path`` set → field on the note with the resolved path string.
3. ``watched_folder_id`` set → field on the note with the verbatim string.
4. Both set → both fields populated, both with the correct values.
5. :meth:`BulkImporter.apply` with ``watched_folder_id`` → every per-item
   pipeline call lands the kwargs through correctly.

These tests use the real :class:`IngestPipeline` against a
:class:`FakeLLMProvider` (no live LLM calls) — same shape as
``test_pipeline.py`` / ``test_bulk.py`` for consistency across the
ingest test suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.ingest.bulk import BulkImporter
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestStatus
from brain_core.llm.fake import FakeLLMProvider
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.vault.frontmatter import parse_frontmatter
from brain_core.vault.types import IndexEntryPatch, PatchSet
from brain_core.vault.writer import VaultWriter

# ---------------------------------------------------------------------------
# Helpers (mirror test_bulk.py / test_pipeline.py)
# ---------------------------------------------------------------------------

CLASSIFY_RESEARCH = '{"source_type":"text","domain":"research","confidence":0.9}'


def _make_pipeline(vault_root: Path, fake: FakeLLMProvider) -> IngestPipeline:
    return IngestPipeline(
        vault_root=vault_root,
        writer=VaultWriter(vault_root=vault_root),
        llm=fake,
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
    )


def _summarize_response(title: str = "hello") -> str:
    return SummarizeOutput(
        title=title,
        summary="A test source.",
        key_points=["pt"],
        entities=[],
        concepts=[],
        open_questions=[],
    ).model_dump_json()


def _integrate_response(title: str = "hello") -> str:
    return PatchSet(
        new_files=[],
        index_entries=[
            IndexEntryPatch(
                section="Sources",
                line=f"- [[{title}]] — test",
                domain="research",
            )
        ],
        log_entry=f"## ingest | [[{title}]]",
        reason="t",
    ).model_dump_json()


def _queue_classify_summarize_integrate(
    fake: FakeLLMProvider, *, title: str = "hello"
) -> None:
    """Queue the 3-LLM-call sequence the auto-classify path consumes."""
    fake.queue(CLASSIFY_RESEARCH)
    fake.queue(_summarize_response(title))
    fake.queue(_integrate_response(title))


def _queue_override_summarize_integrate(
    fake: FakeLLMProvider, *, title: str = "hello"
) -> None:
    """Queue the 2-LLM-call sequence the ``domain_override`` path consumes.

    With ``domain_override`` set, Stage 5 (classify) is skipped — only
    summarize + integrate fire.
    """
    fake.queue(_summarize_response(title))
    fake.queue(_integrate_response(title))


# ---------------------------------------------------------------------------
# (1) Default kwargs → no source_path / watched_folder_id on the note
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_without_watched_kwargs_omits_fields(
    ephemeral_vault: Path, fixtures_dir: Path
) -> None:
    """Default ``ingest()`` call → backwards-compat frontmatter shape.

    The note must NOT carry ``source_path`` or ``watched_folder_id``
    when the caller leaves both kwargs at their default ``None``.
    Pre-T10.5 ingest call sites (drag-drop, MCP ingest tool, paste-text)
    rely on this — surfacing a path the user didn't trigger via watch
    would be a privacy regression.
    """
    fake = FakeLLMProvider()
    _queue_classify_summarize_integrate(fake, title="hello")

    pipeline = _make_pipeline(ephemeral_vault, fake)
    res = await pipeline.ingest(
        fixtures_dir / "hello.txt",
        allowed_domains=("research",),
    )
    assert res.status is IngestStatus.OK
    assert res.note_path is not None

    fm, _body = parse_frontmatter(res.note_path.read_text(encoding="utf-8"))
    # Either the keys are absent OR they're explicitly None — both shapes
    # parse to ``None`` via :meth:`Frontmatter.from_dict`. We accept either
    # so a future YAML library tweak doesn't break the pin.
    assert fm.get("source_path") is None
    assert fm.get("watched_folder_id") is None


# ---------------------------------------------------------------------------
# (2) source_path set → frontmatter has the resolved string
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_with_source_path_populates_frontmatter(
    ephemeral_vault: Path, fixtures_dir: Path
) -> None:
    """Pipeline with ``source_path=<path>`` → frontmatter carries that path.

    The value is the resolved absolute-path STRING — mirrors T2's
    :meth:`update_source` convention so the watcher's lookup compares
    apples-to-apples between the original ingest and a subsequent
    modify event.
    """
    fake = FakeLLMProvider()
    _queue_classify_summarize_integrate(fake, title="hello")

    spec = fixtures_dir / "hello.txt"
    pipeline = _make_pipeline(ephemeral_vault, fake)
    res = await pipeline.ingest(
        spec,
        allowed_domains=("research",),
        source_path=spec,
    )
    assert res.status is IngestStatus.OK
    assert res.note_path is not None

    fm, _body = parse_frontmatter(res.note_path.read_text(encoding="utf-8"))
    assert fm["source_path"] == str(spec.resolve())
    # watched_folder_id NOT set — the other kwarg defaulted to None.
    assert fm.get("watched_folder_id") is None


# ---------------------------------------------------------------------------
# (3) watched_folder_id set → frontmatter has the verbatim string
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_with_watched_folder_id_populates_frontmatter(
    ephemeral_vault: Path, fixtures_dir: Path, tmp_path: Path
) -> None:
    """Pipeline with ``watched_folder_id=<str>`` → frontmatter carries it.

    The value is round-tripped verbatim (no path-resolve) — by Plan 22
    D1, ``watched_folder_id`` IS the ``WatchedFolder.path`` string and
    the watcher's :func:`_index_vault_for_folder` does an exact string
    match on it. A surprise resolve here would break that filter.
    """
    fake = FakeLLMProvider()
    _queue_classify_summarize_integrate(fake, title="hello")

    folder_id = str(tmp_path / "my_watched_folder")
    pipeline = _make_pipeline(ephemeral_vault, fake)
    res = await pipeline.ingest(
        fixtures_dir / "hello.txt",
        allowed_domains=("research",),
        watched_folder_id=folder_id,
    )
    assert res.status is IngestStatus.OK
    assert res.note_path is not None

    fm, _body = parse_frontmatter(res.note_path.read_text(encoding="utf-8"))
    assert fm["watched_folder_id"] == folder_id
    # source_path NOT set — the other kwarg defaulted to None.
    assert fm.get("source_path") is None


# ---------------------------------------------------------------------------
# (4) Both kwargs → both fields populated correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_with_both_kwargs_populates_both(
    ephemeral_vault: Path, fixtures_dir: Path, tmp_path: Path
) -> None:
    """Both kwargs set → both fields on frontmatter with correct values.

    This is the production-path shape T6's
    :meth:`WatchedFolderWatcher._handle_create` produces. Without
    BOTH fields, the watcher's lookup
    (:func:`_index_vault_for_folder`) returns ``None`` (it filters on
    ``watched_folder_id`` AND requires ``source_path`` to be non-empty),
    so the gap T10.5 closes only closes when BOTH kwargs are threaded.
    """
    fake = FakeLLMProvider()
    _queue_classify_summarize_integrate(fake, title="hello")

    spec = fixtures_dir / "hello.txt"
    folder_id = str(tmp_path / "watched_root")
    pipeline = _make_pipeline(ephemeral_vault, fake)
    res = await pipeline.ingest(
        spec,
        allowed_domains=("research",),
        source_path=spec,
        watched_folder_id=folder_id,
    )
    assert res.status is IngestStatus.OK
    assert res.note_path is not None

    fm, _body = parse_frontmatter(res.note_path.read_text(encoding="utf-8"))
    assert fm["source_path"] == str(spec.resolve())
    assert fm["watched_folder_id"] == folder_id


# ---------------------------------------------------------------------------
# (5) BulkImporter.apply threads watched_folder_id + per-item source_path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_importer_apply_threads_watched_folder_id(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """``BulkImporter.apply(watched_folder_id=...)`` threads per-item kwargs.

    For each plan item, the resulting source note's frontmatter must
    carry BOTH the shared ``watched_folder_id`` (the caller's argument)
    AND the per-item ``source_path`` (derived from ``item.spec``). This
    is the T5 ``brain_watch_folder`` initial-sync code path — the gap
    T10.5 closes.

    Two files in the folder → two notes → both must have the watched-
    context frontmatter.
    """
    folder = tmp_path / "bulk_watch"
    folder.mkdir()
    # Plan 25 T2: Stage 3.5 content sniff needs >=200 chars per file.
    filler = "The quick brown fox jumps over the lazy dog. " * 6
    (folder / "alpha.txt").write_text("Alpha. " + filler, encoding="utf-8")
    (folder / "beta.txt").write_text("Beta. " + filler, encoding="utf-8")
    watched_folder_path = str(folder)

    fake = FakeLLMProvider()
    # domain_override is supplied at apply-time, so plan() does NOT
    # classify either file — every classify call is skipped. Each
    # file consumes 2 LLM calls (summarize + integrate). 2 files = 4
    # queued responses.
    for title in ("alpha", "beta"):
        _queue_override_summarize_integrate(fake, title=title)

    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(
        folder,
        allowed_domains=("research",),
        domain_override="research",
    )
    assert len(plan.items) == 2

    results = await importer.apply(
        plan,
        allowed_domains=("research",),
        domain_override="research",
        watched_folder_id=watched_folder_path,
    )
    assert all(r.status is IngestStatus.OK for r in results), (
        f"unexpected statuses: {[r.status for r in results]}"
    )

    # Each per-item note must carry both fields.
    sources_dir = ephemeral_vault / "research" / "sources"
    notes = sorted(sources_dir.glob("*.md"))
    assert len(notes) == 2

    for r in results:
        assert r.note_path is not None
        fm, _body = parse_frontmatter(
            r.note_path.read_text(encoding="utf-8")
        )
        # The shared watched_folder_id rides on every note.
        assert fm["watched_folder_id"] == watched_folder_path
        # The per-item source_path is the ITEM's spec — different per note.
        assert fm["source_path"] is not None
        sp = Path(str(fm["source_path"]))
        # Resolves under the watched folder we just created.
        assert sp.parent.resolve() == folder.resolve()
        assert sp.name in {"alpha.txt", "beta.txt"}


# ---------------------------------------------------------------------------
# (6) BulkImporter.apply without watched_folder_id → backwards-compat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_importer_apply_without_watched_kwarg_is_backwards_compat(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """Calling ``apply()`` with no ``watched_folder_id`` → no watched fields.

    The standalone ``brain_bulk_import`` tool (drag-drop) does NOT pass
    ``watched_folder_id`` — its notes must NOT carry the watched-context
    frontmatter. A drift here would surface a folder ID on
    every bulk-imported note even when the user never set up a watch.
    """
    folder = tmp_path / "bulk_plain"
    folder.mkdir()
    # Plan 25 T2: Stage 3.5 content sniff needs >=200 chars.
    filler = "The quick brown fox jumps over the lazy dog. " * 6
    (folder / "alpha.txt").write_text("Alpha. " + filler, encoding="utf-8")

    fake = FakeLLMProvider()
    _queue_override_summarize_integrate(fake, title="alpha")

    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(
        folder,
        allowed_domains=("research",),
        domain_override="research",
    )
    results = await importer.apply(
        plan,
        allowed_domains=("research",),
        domain_override="research",
        # NO watched_folder_id kwarg — backwards-compat path.
    )
    assert len(results) == 1
    assert results[0].note_path is not None
    fm, _body = parse_frontmatter(
        results[0].note_path.read_text(encoding="utf-8")
    )
    assert fm.get("source_path") is None
    assert fm.get("watched_folder_id") is None
