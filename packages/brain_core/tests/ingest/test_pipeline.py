"""End-to-end tests for IngestPipeline.ingest() — Task 17B.

Tests:
  1. Happy-path text ingestion (full 9-stage run)
  2. Idempotency: second ingest of same file returns SKIPPED_DUPLICATE with no LLM calls
  3. Domain mismatch: classify returns domain not in allowed_domains → QUARANTINED
  4. domain_override: skips classify entirely
  5. Stage exception: pipeline returns FAILED and writes a .error.json record
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestStatus
from brain_core.llm.fake import FakeLLMProvider
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.vault.frontmatter import parse_frontmatter
from brain_core.vault.index import IndexFile
from brain_core.vault.types import IndexEntryPatch, PatchSet
from brain_core.vault.writer import VaultWriter

# ---------------------------------------------------------------------------
# Test 1 — End-to-end text ingestion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_text_end_to_end(ephemeral_vault: Path, fixtures_dir: Path) -> None:
    fake = FakeLLMProvider()
    # classify returns research
    fake.queue('{"source_type":"text","domain":"research","confidence":0.95}')
    # summarize returns a well-formed SummarizeOutput
    fake.queue(
        SummarizeOutput(
            title="hello",
            summary="A greeting.",
            key_points=["says hi"],
            entities=[],
            concepts=[],
            open_questions=[],
        ).model_dump_json()
    )
    # integrate returns a PatchSet with one index entry
    patch = PatchSet(
        new_files=[],
        index_entries=[
            IndexEntryPatch(
                section="Sources",
                line="- [[hello]] — greeting",
                domain="research",
            )
        ],
        log_entry="## [2026-04-14 12:00] ingest | source | [[hello]]",
        reason="test",
    )
    fake.queue(patch.model_dump_json())

    writer = VaultWriter(vault_root=ephemeral_vault)
    p = IngestPipeline(
        vault_root=ephemeral_vault,
        writer=writer,
        llm=fake,
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
    )
    res = await p.ingest(fixtures_dir / "hello.txt", allowed_domains=("research",))
    assert res.status is IngestStatus.OK
    assert res.note_path is not None
    assert res.note_path.exists()

    # Index got the entry
    idx = IndexFile.load(ephemeral_vault / "research" / "index.md")
    assert any(e.target == "hello" for e in idx.sections["Sources"])

    # Source note frontmatter has the right fields
    fm, _body = parse_frontmatter(res.note_path.read_text(encoding="utf-8"))
    assert fm["title"] == "hello"
    assert fm["domain"] == "research"
    assert fm["type"] == "source"
    assert "content_hash" in fm


# ---------------------------------------------------------------------------
# Test 2 — Idempotency: second run with same input is a no-op
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_second_run_is_skipped_duplicate(
    ephemeral_vault: Path, fixtures_dir: Path
) -> None:
    """A second ingest of the same file detects the duplicate via content_hash and skips."""
    fake = FakeLLMProvider()
    # First run: 3 LLM calls (classify + summarize + integrate)
    fake.queue('{"source_type":"text","domain":"research","confidence":0.95}')
    fake.queue(
        SummarizeOutput(
            title="hello",
            summary="x",
            key_points=["x"],
            entities=[],
            concepts=[],
            open_questions=[],
        ).model_dump_json()
    )
    fake.queue(
        PatchSet(
            index_entries=[
                IndexEntryPatch(section="Sources", line="- [[hello]] — x", domain="research")
            ],
            log_entry="ingest",
            reason="t",
        ).model_dump_json()
    )

    writer = VaultWriter(vault_root=ephemeral_vault)
    p = IngestPipeline(
        vault_root=ephemeral_vault,
        writer=writer,
        llm=fake,
        summarize_model="s",
        integrate_model="s",
        classify_model="c",
    )
    r1 = await p.ingest(fixtures_dir / "hello.txt", allowed_domains=("research",))
    assert r1.status is IngestStatus.OK

    # Second run: queue NO additional LLM responses.  If the pipeline tries to call
    # the LLM again, FakeLLMProvider.complete will raise RuntimeError (empty queue).
    r2 = await p.ingest(fixtures_dir / "hello.txt", allowed_domains=("research",))
    assert r2.status is IngestStatus.SKIPPED_DUPLICATE
    assert r2.note_path is None


# ---------------------------------------------------------------------------
# Test 3 — Domain mismatch → quarantined
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_domain_mismatch_quarantined(
    ephemeral_vault: Path, fixtures_dir: Path
) -> None:
    fake = FakeLLMProvider()
    # Classify returns "personal" but allowed_domains excludes it
    fake.queue('{"source_type":"text","domain":"personal","confidence":0.9}')

    p = IngestPipeline(
        vault_root=ephemeral_vault,
        writer=VaultWriter(vault_root=ephemeral_vault),
        llm=fake,
        summarize_model="s",
        integrate_model="s",
        classify_model="c",
    )
    res = await p.ingest(fixtures_dir / "hello.txt", allowed_domains=("research", "work"))
    assert res.status is IngestStatus.QUARANTINED
    assert res.note_path is None
    assert res.errors and "personal" in res.errors[0]


# ---------------------------------------------------------------------------
# Test 4 — domain_override skips classify
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_with_domain_override_skips_classify(
    ephemeral_vault: Path, fixtures_dir: Path
) -> None:
    fake = FakeLLMProvider()
    # NO classify response queued — if the pipeline calls classify, FakeLLMProvider raises.
    fake.queue(
        SummarizeOutput(
            title="hello",
            summary="x",
            key_points=["x"],
            entities=[],
            concepts=[],
            open_questions=[],
        ).model_dump_json()
    )
    fake.queue(PatchSet(index_entries=[], log_entry=None, reason="t").model_dump_json())

    p = IngestPipeline(
        vault_root=ephemeral_vault,
        writer=VaultWriter(vault_root=ephemeral_vault),
        llm=fake,
        summarize_model="s",
        integrate_model="s",
        classify_model="c",
    )
    res = await p.ingest(
        fixtures_dir / "hello.txt",
        allowed_domains=("research",),
        domain_override="research",
    )
    assert res.status is IngestStatus.OK


# ---------------------------------------------------------------------------
# Test 5 — Failure records a JSON error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_records_failure_on_exception(ephemeral_vault: Path, tmp_path: Path) -> None:
    """If a stage raises, the pipeline returns FAILED and writes a .error.json record."""
    fake = FakeLLMProvider()
    # Queue classify but nothing for summarize — summarize will raise RuntimeError.
    fake.queue('{"source_type":"text","domain":"research","confidence":0.95}')

    p = IngestPipeline(
        vault_root=ephemeral_vault,
        writer=VaultWriter(vault_root=ephemeral_vault),
        llm=fake,
        summarize_model="s",
        integrate_model="s",
        classify_model="c",
    )
    # Use a dummy text file in tmp_path so the failure is triggered by the empty queue,
    # not a missing file.
    src = tmp_path / "hello.txt"
    src.write_text("hello body", encoding="utf-8")
    res = await p.ingest(src, allowed_domains=("research",))
    assert res.status is IngestStatus.FAILED
    assert res.errors
    # Failure record written
    failed_files = list((ephemeral_vault / "raw" / "inbox" / "failed").glob("*.error.json"))
    assert len(failed_files) == 1


# ---------------------------------------------------------------------------
# Tests 6-8 — `apply` kwarg (staged-mode extension for Plan 04 brain_ingest)
# ---------------------------------------------------------------------------


def _queue_happy_path_responses(fake: FakeLLMProvider) -> None:
    """Queue classify + summarize + integrate responses for a successful run."""
    fake.queue('{"source_type":"text","domain":"research","confidence":0.95}')
    fake.queue(
        SummarizeOutput(
            title="hello",
            summary="A greeting.",
            key_points=["says hi"],
            entities=[],
            concepts=[],
            open_questions=[],
        ).model_dump_json()
    )
    fake.queue(
        PatchSet(
            index_entries=[
                IndexEntryPatch(section="Sources", line="- [[hello]] — greeting", domain="research")
            ],
            log_entry="## [2026-04-16 12:00] ingest | source | [[hello]]",
            reason="test",
        ).model_dump_json()
    )


@pytest.mark.asyncio
async def test_ingest_default_still_applies(ephemeral_vault: Path, fixtures_dir: Path) -> None:
    """Regression: the default call (no apply kwarg) still writes to the vault.

    Guards against a breakage where `apply=True` default ever flips or the
    pre-extension behavior changes.
    """
    fake = FakeLLMProvider()
    _queue_happy_path_responses(fake)

    p = IngestPipeline(
        vault_root=ephemeral_vault,
        writer=VaultWriter(vault_root=ephemeral_vault),
        llm=fake,
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
    )
    res = await p.ingest(fixtures_dir / "hello.txt", allowed_domains=("research",))
    assert res.status is IngestStatus.OK
    assert res.note_path is not None
    assert res.note_path.exists(), "default apply=True must still write vault file"
    assert res.patchset is None, "default run returns no patchset"


@pytest.mark.asyncio
async def test_ingest_apply_false_returns_patchset(
    ephemeral_vault: Path, fixtures_dir: Path
) -> None:
    """apply=False: pipeline returns PatchSet, vault is untouched."""
    fake = FakeLLMProvider()
    _queue_happy_path_responses(fake)

    p = IngestPipeline(
        vault_root=ephemeral_vault,
        writer=VaultWriter(vault_root=ephemeral_vault),
        llm=fake,
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
    )
    res = await p.ingest(
        fixtures_dir / "hello.txt",
        allowed_domains=("research",),
        apply=False,
    )
    assert res.status is IngestStatus.OK
    assert res.note_path is not None
    assert not res.note_path.exists(), "apply=False must NOT write vault file"
    assert res.patchset is not None, "apply=False must populate patchset"
    # Stage 8 prepends the source note as the first new_file.
    assert res.patchset.new_files, "patchset should contain at least the source note"
    assert res.patchset.new_files[0].path == res.note_path


@pytest.mark.asyncio
async def test_ingest_apply_false_preserves_failure_handling(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """Pipeline failures still return FAILED (no patchset) with apply=False.

    Matches the `apply=True` failure contract: the try/except wraps stages 2-9,
    so raising mid-stage yields FAILED regardless of the flag.
    """
    fake = FakeLLMProvider()
    # Queue classify but nothing for summarize — summarize call will raise.
    fake.queue('{"source_type":"text","domain":"research","confidence":0.95}')

    p = IngestPipeline(
        vault_root=ephemeral_vault,
        writer=VaultWriter(vault_root=ephemeral_vault),
        llm=fake,
        summarize_model="s",
        integrate_model="s",
        classify_model="c",
    )
    src = tmp_path / "hello.txt"
    src.write_text("hello body", encoding="utf-8")
    res = await p.ingest(src, allowed_domains=("research",), apply=False)
    assert res.status is IngestStatus.FAILED
    assert res.errors
    assert res.patchset is None, "FAILED results never carry a patchset"
