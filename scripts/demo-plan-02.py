"""Plan 02 end-to-end demo.

Runs in a temp directory, ingests 5 source fixtures through the full
IngestPipeline using FakeLLMProvider, proves idempotency, and prints a
success report. This is the Plan 02 demo gate.

Fixture files are read directly from
    packages/brain_core/tests/ingest/fixtures/
rather than copying to a scripts/fixtures/ mirror. Both paths are relative
to the repo root, which is Path(__file__).parent.parent.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import httpx
import respx
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestStatus
from brain_core.llm.fake import FakeLLMProvider
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.vault.frontmatter import parse_frontmatter
from brain_core.vault.index import IndexFile
from brain_core.vault.types import IndexEntryPatch, PatchSet
from brain_core.vault.writer import VaultWriter

_FIXTURES = (
    Path(__file__).parent.parent / "packages" / "brain_core" / "tests" / "ingest" / "fixtures"
)


async def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "brain"
        _scaffold_vault(root)

        fake = FakeLLMProvider()
        pipeline = IngestPipeline(
            vault_root=root,
            writer=VaultWriter(vault_root=root),
            llm=fake,
            summarize_model="claude-sonnet-4-6",
            integrate_model="claude-sonnet-4-6",
            classify_model="claude-haiku-4-5-20251001",
        )

        # Queue (summarize + integrate) responses for 5 ingests.
        # domain_override skips classify, so 2 LLM calls x 5 = 10 total.
        _queue_responses_for(fake, count=5, domain="research")

        async with respx.mock() as mock:
            # URL handler: mock a small HTML page
            html = (
                "<html><head><title>Plan 02 Demo</title></head>"
                "<body><article>"
                "<p>This is the demo article body for Plan 02.</p>"
                "</article></body></html>"
            )
            mock.get("https://example.com/plan-02-demo").mock(
                return_value=httpx.Response(200, text=html)
            )

            # Tweet handler: mock the syndication endpoint
            tweet_payload = {
                "id_str": "1234567890",
                "user": {"name": "Demo User", "screen_name": "demo"},
                "text": "Plan 02 demo tweet body.",
                "created_at": "Thu Apr 14 10:00:00 +0000 2026",
            }
            mock.get(
                "https://cdn.syndication.twimg.com/tweet-result",
                params={"id": "1234567890"},
            ).mock(return_value=httpx.Response(200, json=tweet_payload))

            # ---- 5 ingests ----

            r1 = await pipeline.ingest(
                _FIXTURES / "hello.txt",
                allowed_domains=("research",),
                domain_override="research",
            )
            assert r1.status is IngestStatus.OK, f"text ingest failed: {r1.errors}"
            assert r1.note_path is not None
            print(f"✓ 1/5 text: {r1.note_path.name}")

            r2 = await pipeline.ingest(
                "https://example.com/plan-02-demo",
                allowed_domains=("research",),
                domain_override="research",
            )
            assert r2.status is IngestStatus.OK, f"url ingest failed: {r2.errors}"
            assert r2.note_path is not None
            print(f"✓ 2/5 url: {r2.note_path.name}")

            r3 = await pipeline.ingest(
                _FIXTURES / "sample.pdf",
                allowed_domains=("research",),
                domain_override="research",
            )
            assert r3.status is IngestStatus.OK, f"pdf ingest failed: {r3.errors}"
            assert r3.note_path is not None
            print(f"✓ 3/5 pdf: {r3.note_path.name}")

            r4 = await pipeline.ingest(
                _FIXTURES / "meeting.vtt",
                allowed_domains=("research",),
                domain_override="research",
            )
            assert r4.status is IngestStatus.OK, f"vtt ingest failed: {r4.errors}"
            assert r4.note_path is not None
            print(f"✓ 4/5 vtt: {r4.note_path.name}")

            r5 = await pipeline.ingest(
                "https://x.com/karpathy/status/1234567890",
                allowed_domains=("research",),
                domain_override="research",
            )
            assert r5.status is IngestStatus.OK, f"tweet ingest failed: {r5.errors}"
            assert r5.note_path is not None
            print(f"✓ 5/5 tweet: {r5.note_path.name}")

        # Each source note has content_hash frontmatter
        for r in (r1, r2, r3, r4, r5):
            assert r.note_path is not None
            fm, _body = parse_frontmatter(r.note_path.read_text(encoding="utf-8"))
            assert "content_hash" in fm, f"note {r.note_path} missing content_hash"
        print("✓ every source note has content_hash frontmatter")

        # Index has at least the 5 entries we queued via integrate patches
        idx = IndexFile.load(root / "research" / "index.md")
        source_entries = idx.sections.get("Sources", [])
        assert len(source_entries) >= 5, f"expected ≥5 Sources entries, got {len(source_entries)}"
        print(f"✓ research/index.md has {len(source_entries)} Sources entries")

        # Idempotency: re-ingest hello.txt — no new LLM calls should fire
        calls_before = len(fake.requests)
        r_dup = await pipeline.ingest(
            _FIXTURES / "hello.txt",
            allowed_domains=("research",),
            domain_override="research",
        )
        assert r_dup.status is IngestStatus.SKIPPED_DUPLICATE, f"idempotency failed: {r_dup.status}"
        assert len(fake.requests) == calls_before, "duplicate run made LLM calls"
        print("✓ duplicate ingest of hello.txt is SKIPPED_DUPLICATE with zero LLM calls")

        # Exactly 2 LLM calls per successful ingest (summarize + integrate) x 5 = 10
        assert len(fake.requests) == 10, f"expected 10 LLM calls, got {len(fake.requests)}"
        print(f"✓ LLM call count: {len(fake.requests)}")

        print("\nPLAN 02 DEMO OK")
        return 0


def _queue_responses_for(fake: FakeLLMProvider, *, count: int, domain: str) -> None:
    """Queue (summarize + integrate) responses for `count` successful ingests.

    domain_override is used throughout the demo, so classify is skipped.
    Each ingest consumes exactly two queued responses:
      1. summarize  → SummarizeOutput JSON
      2. integrate  → PatchSet JSON
    """
    for i in range(count):
        fake.queue(
            SummarizeOutput(
                title=f"demo-{i}",
                summary=f"Demo source #{i}.",
                key_points=[f"point {i}"],
                entities=[],
                concepts=[],
                open_questions=[],
            ).model_dump_json()
        )
        fake.queue(
            PatchSet(
                new_files=[],
                index_entries=[
                    IndexEntryPatch(
                        section="Sources",
                        line=f"- [[demo-{i}]] — plan 02 demo source",
                        domain=domain,
                    )
                ],
                log_entry=(f"## [2026-04-14 12:{i:02d}] ingest | source | [[demo-{i}]]"),
                reason=f"demo ingest #{i}",
            ).model_dump_json()
        )


def _scaffold_vault(root: Path) -> None:
    """Mirror the scaffold from demo-plan-01.py, adding raw/ subdirs."""
    root.mkdir(parents=True)
    (root / ".brain").mkdir()
    for domain in ("research", "work", "personal"):
        d = root / domain
        for sub in ("sources", "entities", "concepts", "synthesis"):
            (d / sub).mkdir(parents=True)
        (d / "index.md").write_text(
            f"# {domain} — index\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Synthesis\n",
            encoding="utf-8",
        )
        (d / "log.md").write_text(f"# {domain} — log\n", encoding="utf-8")
    for sub in ("inbox", "failed", "archive"):
        (root / "raw" / sub).mkdir(parents=True)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
