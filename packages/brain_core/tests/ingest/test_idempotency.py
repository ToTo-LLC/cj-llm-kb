"""Regression test: re-ingesting the same source is a no-op — no LLM calls, no duplicate note.

Task 17B's `test_ingest_second_run_is_skipped_duplicate` covers the status path.
This test adds the stronger guarantee that the SECOND run consumes ZERO additional
LLM requests, catching regressions where the idempotency check accidentally moves
AFTER the classify/summarize/integrate stages.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestStatus
from brain_core.llm.fake import FakeLLMProvider
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.vault.types import IndexEntryPatch, PatchSet
from brain_core.vault.writer import VaultWriter


@pytest.mark.asyncio
async def test_second_ingest_of_same_source_is_skipped(
    ephemeral_vault: Path, fixtures_dir: Path
) -> None:
    fake = FakeLLMProvider()
    # First run: classify + summarize + integrate = 3 LLM calls.
    fake.queue('{"source_type":"text","domain":"research","confidence":0.95}')
    fake.queue(
        SummarizeOutput(
            title="hello",
            summary="greeting",
            key_points=["hi"],
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
            log_entry="## [2026-04-14 12:00] ingest | source | [[hello]]",
            reason="initial",
        ).model_dump_json()
    )
    # DELIBERATELY queue NOTHING for the second run. If the pipeline tries to
    # call the LLM on the duplicate path, FakeLLMProvider.complete raises and
    # the test fails loudly.

    p = IngestPipeline(
        vault_root=ephemeral_vault,
        writer=VaultWriter(vault_root=ephemeral_vault),
        llm=fake,
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
    )

    r1 = await p.ingest(fixtures_dir / "hello.txt", allowed_domains=("research",))
    assert r1.status is IngestStatus.OK
    assert r1.note_path is not None
    assert r1.note_path.exists()

    r2 = await p.ingest(fixtures_dir / "hello.txt", allowed_domains=("research",))
    assert r2.status is IngestStatus.SKIPPED_DUPLICATE
    assert r2.note_path is None

    # The key regression assertion: second run made ZERO additional LLM calls.
    # Total across both runs must equal the first run's 3 calls (classify/summarize/integrate).
    assert len(fake.requests) == 3, (
        f"Expected 3 LLM calls total across both runs (all from first run); "
        f"got {len(fake.requests)}. Idempotency check may have moved after the LLM stages."
    )
