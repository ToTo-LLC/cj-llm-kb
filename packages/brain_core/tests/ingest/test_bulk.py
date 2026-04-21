"""Tests for BulkImporter — dry-run plan + apply workflow. Task 19.

Tests:
  1. plan() returns items for claimable files, skips unclaimable
  2. plan() with domain_override skips classify entirely
  3. plan() doesn't write to the vault
  4. apply(plan) runs the pipeline per item and returns results in order
  5. apply() does not stop on failure
  6. Empty folder
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.ingest.bulk import BulkImporter, _is_hidden
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestStatus
from brain_core.llm.fake import FakeLLMProvider
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.vault.types import IndexEntryPatch, PatchSet
from brain_core.vault.writer import VaultWriter

# ---------------------------------------------------------------------------
# Helpers
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


def _summarize_response(title: str = "test") -> str:
    return SummarizeOutput(
        title=title,
        summary="A test document.",
        key_points=["point one"],
        entities=[],
        concepts=[],
        open_questions=[],
    ).model_dump_json()


def _integrate_response(title: str = "test") -> str:
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
        reason="test",
    ).model_dump_json()


def _make_folder(tmp_path: Path) -> Path:
    """Create a standard test fixture folder used across several tests.

    Layout:
        a.txt          — claimable (TextHandler)
        b.md           — claimable (TextHandler)
        .hiddenfile.txt — skipped: file itself is hidden
        hidden/        — directory with hidden name
        hidden/.secret.txt — skipped: parent dir is hidden
        garbage.xyz    — skipped: no handler claims it
        sub/c.txt      — claimable (TextHandler), nested
    """
    folder = tmp_path / "import_folder"
    folder.mkdir()

    (folder / "a.txt").write_text("content of a", encoding="utf-8")
    (folder / "b.md").write_text("content of b", encoding="utf-8")
    (folder / ".hiddenfile.txt").write_text("hidden", encoding="utf-8")
    hidden_dir = folder / "hidden"
    hidden_dir.mkdir()
    (hidden_dir / ".secret.txt").write_text("secret", encoding="utf-8")
    (folder / "garbage.xyz").write_text("unknown format", encoding="utf-8")
    sub = folder / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("content of c", encoding="utf-8")

    return folder


# ---------------------------------------------------------------------------
# Test 1 — plan returns items for claimable files, skips unclaimable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_returns_items_and_skips(ephemeral_vault: Path, tmp_path: Path) -> None:
    folder = _make_folder(tmp_path)
    fake = FakeLLMProvider()
    # 3 claimable files → 3 classify calls
    for _ in range(3):
        fake.queue(CLASSIFY_RESEARCH)

    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(folder, allowed_domains=("research",))

    assert len(plan.items) == 3

    spec_names = {item.spec.name for item in plan.items}
    assert "a.txt" in spec_names
    assert "b.md" in spec_names
    assert "c.txt" in spec_names
    assert ".hiddenfile.txt" not in spec_names
    assert ".secret.txt" not in spec_names

    skipped_names = {p.name for p in plan.skipped}
    assert "garbage.xyz" in skipped_names

    for item in plan.items:
        assert item.classified_domain == "research"
        assert item.confidence == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# Test 2 — plan with domain_override skips classify
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_with_domain_override_skips_classify(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    folder = _make_folder(tmp_path)
    fake = FakeLLMProvider()
    # Queue nothing — if classify is called FakeLLMProvider will raise.

    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(
        folder,
        allowed_domains=("research",),
        domain_override="research",
    )

    assert len(plan.items) == 3
    for item in plan.items:
        assert item.classified_domain == "research"
        assert item.confidence is None

    assert len(fake.requests) == 0


# ---------------------------------------------------------------------------
# Test 3 — plan() doesn't write to the vault
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_does_not_write_to_vault(ephemeral_vault: Path, tmp_path: Path) -> None:
    folder = _make_folder(tmp_path)
    fake = FakeLLMProvider()
    for _ in range(3):
        fake.queue(CLASSIFY_RESEARCH)

    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    await importer.plan(folder, allowed_domains=("research",))

    # No source notes written
    sources_dir = ephemeral_vault / "research" / "sources"
    assert list(sources_dir.glob("*.md")) == []

    # No failure records written
    failed_dir = ephemeral_vault / "raw" / "inbox" / "failed"
    assert list(failed_dir.glob("*.error.json")) == []


# ---------------------------------------------------------------------------
# Test 4 — apply(plan) runs the pipeline per item and returns results in order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_runs_pipeline_per_item_in_order(ephemeral_vault: Path, tmp_path: Path) -> None:
    folder = tmp_path / "two_files"
    folder.mkdir()
    (folder / "first.txt").write_text("first content", encoding="utf-8")
    (folder / "second.txt").write_text("second content", encoding="utf-8")

    fake = FakeLLMProvider()
    # Plan phase: 2 classify calls
    fake.queue(CLASSIFY_RESEARCH)
    fake.queue(CLASSIFY_RESEARCH)
    # Apply phase: 2 items x (summarize + integrate) = 4 calls
    fake.queue(_summarize_response("first"))
    fake.queue(_integrate_response("first"))
    fake.queue(_summarize_response("second"))
    fake.queue(_integrate_response("second"))

    pipeline = _make_pipeline(ephemeral_vault, fake)
    importer = BulkImporter(pipeline)

    plan = await importer.plan(folder, allowed_domains=("research",))
    assert len(plan.items) == 2

    # Pass domain_override so apply does not re-classify (plan already classified).
    results = await importer.apply(plan, allowed_domains=("research",), domain_override="research")

    assert len(results) == 2
    assert results[0].status is IngestStatus.OK
    assert results[1].status is IngestStatus.OK

    # Both source notes exist
    assert results[0].note_path is not None and results[0].note_path.exists()
    assert results[1].note_path is not None and results[1].note_path.exists()

    # Results are in the same order as plan.items (same length, same positions)
    assert len(results) == len(plan.items)


# ---------------------------------------------------------------------------
# Test 5 — apply does not stop on failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_does_not_stop_on_failure(ephemeral_vault: Path, tmp_path: Path) -> None:
    folder = tmp_path / "fail_folder"
    folder.mkdir()
    (folder / "good.txt").write_text("good content", encoding="utf-8")
    (folder / "bad.txt").write_text("bad content", encoding="utf-8")

    fake = FakeLLMProvider()
    # Plan phase: 2 classify calls
    fake.queue(CLASSIFY_RESEARCH)
    fake.queue(CLASSIFY_RESEARCH)

    pipeline = _make_pipeline(ephemeral_vault, fake)
    importer = BulkImporter(pipeline)
    plan = await importer.plan(folder, allowed_domains=("research",))
    assert len(plan.items) == 2

    # Apply phase (domain_override skips classify, so only summarize+integrate per item):
    # First item succeeds (summarize + integrate)
    first_item = plan.items[0]
    fake.queue(_summarize_response(first_item.spec.stem))
    fake.queue(_integrate_response(first_item.spec.stem))
    # Second item: summarize returns invalid JSON → pipeline wraps in FAILED
    fake.queue("not json")  # invalid summarize response

    results = await importer.apply(plan, allowed_domains=("research",), domain_override="research")

    assert len(results) == 2
    assert results[0].status is IngestStatus.OK
    assert results[1].status is IngestStatus.FAILED

    # Failure record written for the second item
    failed_dir = ephemeral_vault / "raw" / "inbox" / "failed"
    assert len(list(failed_dir.glob("*.error.json"))) >= 1


# ---------------------------------------------------------------------------
# Test 6 — Empty folder
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_empty_folder(ephemeral_vault: Path, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    fake = FakeLLMProvider()
    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(empty, allowed_domains=("research",))

    assert len(plan.items) == 0
    assert len(plan.skipped) == 0


# ---------------------------------------------------------------------------
# Unit tests for _is_hidden helper
# ---------------------------------------------------------------------------


def test_is_hidden_file_itself(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    hidden = root / ".hidden.txt"
    assert _is_hidden(hidden, root=root) is True


def test_is_hidden_parent_dir(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / ".secret").mkdir()
    nested = root / ".secret" / "file.txt"
    assert _is_hidden(nested, root=root) is True


def test_is_hidden_normal_file(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "sub").mkdir()
    normal = root / "sub" / "file.txt"
    assert _is_hidden(normal, root=root) is False


def test_is_hidden_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / ".outside.txt"
    # path not relative to root → returns False (no ValueError crash)
    assert _is_hidden(outside, root=root) is False


@pytest.mark.asyncio
async def test_apply_honors_per_item_classified_domain(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """apply() must pass each item's own classified_domain to ingest(), so the
    pipeline does NOT re-classify. Without this, the plan phase's classifier
    work is thrown away and every item burns a second classify call.
    """
    folder = tmp_path / "inbox"
    folder.mkdir()
    (folder / "a.txt").write_text("alpha content", encoding="utf-8")
    (folder / "b.txt").write_text("beta content", encoding="utf-8")

    fake = FakeLLMProvider()
    # Plan phase: 2 classify calls (one per file), each to a DIFFERENT domain.
    fake.queue('{"source_type":"text","domain":"research","confidence":0.9}')
    fake.queue('{"source_type":"text","domain":"work","confidence":0.9}')

    pipeline = _make_pipeline(ephemeral_vault, fake)
    importer = BulkImporter(pipeline)
    plan = await importer.plan(folder, allowed_domains=("research", "work"))
    assert len(plan.items) == 2
    classified_domains = {item.spec.name: item.classified_domain for item in plan.items}
    assert classified_domains == {"a.txt": "research", "b.txt": "work"}

    # At this point the fake queue is empty. Queue ONLY summarize + integrate
    # for each item, giving each summary a distinct title so the slug-from-title
    # re-computation in the pipeline yields distinct source note filenames.
    # NO additional classify responses. If apply() triggers the pipeline to
    # re-classify, the empty queue will make FakeLLMProvider raise loudly.
    for title in ("alpha-note", "beta-note"):
        fake.queue(
            SummarizeOutput(
                title=title,
                summary="y",
                key_points=[],
                entities=[],
                concepts=[],
                open_questions=[],
            ).model_dump_json()
        )
        fake.queue(
            PatchSet(
                index_entries=[],
                log_entry=None,
                reason="t",
            ).model_dump_json()
        )

    results = await importer.apply(plan, allowed_domains=("research", "work"))
    assert len(results) == 2
    for r in results:
        assert r.status is IngestStatus.OK, f"status={r.status} errors={r.errors}"

    # Each item ended up under its OWN classified domain (slug from summary title).
    assert (ephemeral_vault / "research" / "sources" / "alpha-note.md").exists()
    assert (ephemeral_vault / "work" / "sources" / "beta-note.md").exists()
    # And NOT forced into the same domain
    assert not (ephemeral_vault / "research" / "sources" / "beta-note.md").exists()
    assert not (ephemeral_vault / "work" / "sources" / "alpha-note.md").exists()

    # Exactly 6 LLM calls total: 2 classify (plan) + 2 summarize + 2 integrate.
    assert len(fake.requests) == 6


# ---------------------------------------------------------------------------
# Plan 07 Task 4 — BulkPlan.duplicate flag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_marks_already_ingested_files_as_duplicate(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """A folder file whose ``content_hash`` matches an existing source note
    must surface ``duplicate=True`` on the BulkItem so the dry-run UI can
    flag it before the user spends LLM tokens on apply.
    """
    from brain_core.ingest.hashing import content_hash
    from brain_core.vault.frontmatter import serialize_with_frontmatter

    # Seed an existing source note with a known content_hash.
    duplicate_text = "this exact body is already in the vault"
    chash = content_hash(duplicate_text)
    sources_dir = ephemeral_vault / "research" / "sources"
    sources_dir.mkdir(exist_ok=True, parents=True)
    fm = {
        "title": "Existing",
        "domain": "research",
        "type": "source",
        "created": "2026-04-01",
        "updated": "2026-04-01",
        "source_type": "text",
        "source_url": None,
        "content_hash": chash,
        "ingested_by": "brain",
    }
    (sources_dir / "existing.md").write_text(
        serialize_with_frontmatter(fm, body="# Existing\n"),
        encoding="utf-8",
    )

    # Build the inbox folder: one duplicate, one fresh.
    folder = tmp_path / "inbox"
    folder.mkdir()
    (folder / "dup.txt").write_text(duplicate_text, encoding="utf-8")
    (folder / "fresh.txt").write_text("brand new body", encoding="utf-8")

    fake = FakeLLMProvider()
    importer = BulkImporter(_make_pipeline(ephemeral_vault, fake))
    plan = await importer.plan(
        folder,
        allowed_domains=("research",),
        domain_override="research",
    )

    by_name = {item.spec.name: item for item in plan.items}
    assert by_name["dup.txt"].duplicate is True
    assert by_name["fresh.txt"].duplicate is False
