"""Stage 3.5 content-sniff tests (Plan 25 T2).

Two layers:

* **Helper-level tests** (11): exercise ``_looks_like_meaningful_text``
  directly against synthetic bodies covering each threshold + the D15
  OCR-marker exception. No pipeline machinery, no LLM queue.

* **Pipeline-integration tests** (4): construct an :class:`IngestPipeline`
  with a :class:`FakeLLMProvider` whose queue is intentionally EMPTY for
  the classify slot. If Stage 3.5 fails to short-circuit, the empty queue
  raises ``RuntimeError`` and the test fails loudly — pinning that no LLM
  tokens are spent on quarantined files. Pipelining is exercised for both
  the quarantine path (binary garbage) and the happy path (normal prose).

The 15 tests cover (per plan-doc §T2 review block):
    (a) sniff helper matches 3 thresholds + D15 exception,
    (b) quarantine path mirrors existing failure-handling shape,
    (c) no LLM spend on quarantined files (empty FakeLLM queue stays empty),
    (d) sniff applies to ALL text-shaped SourceTypes,
    (e) UTF-8 / non-ASCII letters count toward letter ratio,
    (f) OCR-marker exception is NOT a binary-content bypass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from brain_core.ingest.pipeline import (
    _OCR_MARKER_PATTERN,
    _TEXT_SHAPED_SOURCE_TYPES,
    IngestPipeline,
    _looks_like_meaningful_text,
)
from brain_core.ingest.types import (
    ExtractedSource,
    IngestStatus,
    SourceType,
)
from brain_core.llm.fake import FakeLLMProvider
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.vault.types import IndexEntryPatch, PatchSet
from brain_core.vault.writer import VaultWriter

# ---------------------------------------------------------------------------
# Helper-level tests — exercise _looks_like_meaningful_text directly.
# ---------------------------------------------------------------------------


def test_meaningful_text_passes() -> None:
    """Normal English prose >200 chars with high letter ratio passes."""
    body = "The quick brown fox jumps over the lazy dog. " * 10  # 450 chars
    assert _looks_like_meaningful_text(body) is True


def test_short_body_quarantines() -> None:
    """Body shorter than 200 chars with no OCR markers fails the min_chars floor."""
    assert _looks_like_meaningful_text("Hi.") is False


def test_binary_garbage_quarantines() -> None:
    """A string of all 256 byte-values has too many non-printable chars."""
    # chr(0..256) — ~50% printable; D3 threshold is 80%. Repeat to clear the
    # 200-char floor so the printable-ratio check is the actual rejecter.
    body = "".join(chr(i) for i in range(256)) * 5  # 1280 chars
    assert _looks_like_meaningful_text(body) is False


def test_high_whitespace_quarantines() -> None:
    """A body that's mostly whitespace fails the non-whitespace half-floor."""
    body = "a" + " " * 500  # 501 chars, 1 letter, 500 spaces
    # min_chars=200 applies (no OCR markers), so non-ws < 100 → fail.
    assert _looks_like_meaningful_text(body) is False


def test_base64_dump_outcome() -> None:
    """A base64-only body (no whitespace, ~60-70% letters) passes the helper.

    Documents the heuristic's known limit: well-formed base64 with mostly
    alphabetical content (uppercase + lowercase + digits + ``/``/``+``)
    clears printable (100%) + letter (>40%) thresholds and is NOT
    quarantined. This is by design — base64 content is technically
    "meaningful text" by the helper's heuristic. Downstream classify /
    summarize prompts have the contextual knowledge to handle it (and
    pre-Plan-25 behavior left it to the LLM anyway). The sniff is a
    cheap pre-screen for OBVIOUS nonsense (binary, encrypted blobs),
    not a sophisticated content classifier.
    """
    # 500 chars of typical base64 alphabet — ~60% letters.
    body = "aGVsbG93b3JsZGFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6" * 11  # 528 chars
    # Document: passes the helper (high letters + 100% printable + no ws issue).
    assert _looks_like_meaningful_text(body) is True


def test_short_ocr_heavy_pptx_passes_via_d15() -> None:
    """A pptx body shorter than 200 chars passes IF it carries an OCR marker."""
    body = "## Slide 1: \n\n[Image (slide 1): hello world]"
    assert len(body) < 200
    assert _OCR_MARKER_PATTERN.search(body) is not None
    assert _looks_like_meaningful_text(body) is True


def test_pdf_with_page_ocr_markers_passes_via_d15() -> None:
    """A pdf body shorter than 200 chars with a Page N marker passes via D15."""
    body = "[Page 1: extracted text]"
    assert len(body) < 200
    assert _looks_like_meaningful_text(body) is True


def test_docx_inline_image_marker_passes_via_d15() -> None:
    """A docx body shorter than 200 chars with a bare ``[Image: `` marker passes."""
    body = "[Image: hello]"
    assert len(body) < 200
    assert _looks_like_meaningful_text(body) is True


def test_binary_garbage_with_fake_ocr_marker_still_quarantines() -> None:
    """OCR-marker exception is NOT a bypass for non-printable binary content.

    The marker skips the 200-char floor, but printable + letter ratios
    STILL apply. A body that's mostly raw binary bytes wrapped in
    ``[Image: ... ]`` still rejects.
    """
    binary_chars = "".join(chr(i) for i in range(1, 32)) * 20  # 620 chars of control codes
    body = "[Image: " + binary_chars + "]"
    assert _OCR_MARKER_PATTERN.search(body) is not None  # marker is there
    assert _looks_like_meaningful_text(body) is False  # but still rejects


def test_letter_ratio_threshold() -> None:
    """A 500-char digit-only body has 0% letters and fails the 40% floor."""
    body = "1234567890" * 50  # 500 chars, 100% printable, 0% letters
    assert _looks_like_meaningful_text(body) is False


def test_empty_body_quarantines() -> None:
    """An empty body is never meaningful — short-circuit at the top."""
    assert _looks_like_meaningful_text("") is False


def test_utf8_letters_count_for_letter_ratio() -> None:
    """``str.isalpha`` includes non-ASCII Unicode letters (multi-language)."""
    # Russian text — Cyrillic letters count as alpha. ~250 chars.
    body = (
        "Это длинный текст на русском языке, который должен пройти проверку "
        "содержимого. Кириллические буквы являются буквами по определению "
        "Unicode, поэтому коэффициент букв превышает требуемые сорок процентов. "
        "Простой тест многоязычного содержимого."
    )
    assert len(body) >= 200
    assert _looks_like_meaningful_text(body) is True


# ---------------------------------------------------------------------------
# Source-type set pin — covers review gate (d).
# ---------------------------------------------------------------------------


def test_text_shaped_source_types_membership() -> None:
    """Pin the set of source types Stage 3.5 applies to.

    URL + EMAIL + TWEET are intentionally excluded (their handlers
    produce structured output that may legitimately be short).
    """
    assert _TEXT_SHAPED_SOURCE_TYPES == frozenset({
        SourceType.TEXT,
        SourceType.TRANSCRIPT,
        SourceType.DOCX,
        SourceType.PPTX,
        SourceType.PDF,
    })


# ---------------------------------------------------------------------------
# Pipeline-integration tests — Stage 3.5 quarantine + happy path.
# ---------------------------------------------------------------------------


def _make_pipeline(vault_root: Path, fake: FakeLLMProvider) -> IngestPipeline:
    """Build a minimal IngestPipeline for Stage-3.5 integration tests."""
    writer = VaultWriter(vault_root=vault_root)
    return IngestPipeline(
        vault_root=vault_root,
        writer=writer,
        llm=fake,
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
    )


@pytest.mark.asyncio
async def test_pipeline_quarantines_binary_garbage(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """A ``.txt`` of binary garbage routes to Stage 3.5 quarantine.

    Pins review gates (b) quarantine path mirrors failure-handling pattern,
    (c) no LLM tokens spent — the FakeLLMProvider queue stays empty so any
    classify/summarize call would raise ``RuntimeError`` and surface here.
    """
    # 1280 chars of control codes — printable ratio fails.
    garbage = "".join(chr(i) for i in range(256)) * 5
    src = tmp_path / "garbage.txt"
    src.write_text(garbage, encoding="utf-8")

    fake = FakeLLMProvider()  # queue intentionally EMPTY
    pipeline = _make_pipeline(ephemeral_vault, fake)
    res = await pipeline.ingest(src, allowed_domains=("research",))

    assert res.status is IngestStatus.FAILED
    assert res.note_path is None
    assert res.errors
    assert "content_sniff" in res.errors[0]
    assert "non_meaningful_text" in res.errors[0]

    # Quarantine record written to raw/inbox/failed/<slug>.<ts>.needs_review.json.
    failed_dir = ephemeral_vault / "raw" / "inbox" / "failed"
    records = list(failed_dir.glob("*.needs_review.json"))
    assert len(records) == 1, f"expected exactly one quarantine record, got {records}"
    assert records[0].stem.startswith("garbage")


@pytest.mark.asyncio
async def test_pipeline_passes_meaningful_text(
    ephemeral_vault: Path, fixtures_dir: Path
) -> None:
    """Normal-prose ``hello.txt`` clears Stage 3.5 and completes the 9 stages.

    The plan-doc says "ingest a .txt file with normal prose" and asserts
    classify+summarize+integrate run. The shipped ``hello.txt`` fixture is
    only ~64 chars, which would FAIL Stage 3.5's 200-char floor. So we write
    a fresh prose file in tmp_path that comfortably clears the floor.

    Pins review gate (c): on the happy path the queue IS consumed — we
    enqueue exactly three responses and verify all three are popped.
    """
    fake = FakeLLMProvider()
    fake.queue('{"source_type":"text","domain":"research","confidence":0.95}')
    fake.queue(
        SummarizeOutput(
            title="hello",
            summary="A friendly greeting expanded into prose.",
            key_points=["says hi"],
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
                    line="- [[hello]] — greeting",
                    domain="research",
                )
            ],
            log_entry="ingest",
            reason="t",
        ).model_dump_json()
    )

    # Write a prose file that comfortably clears Stage 3.5.
    body = (
        "Hello, brain. This is a plain-text fixture for the text handler. "
        "The quick brown fox jumps over the lazy dog several times so the "
        "body comfortably exceeds the two-hundred-character content-sniff "
        "floor. Every word here is real English prose — letter ratio well "
        "above forty percent, printable ratio one hundred percent."
    )
    src = ephemeral_vault.parent / "hello-prose.txt"
    src.write_text(body, encoding="utf-8")

    pipeline = _make_pipeline(ephemeral_vault, fake)
    res = await pipeline.ingest(src, allowed_domains=("research",))

    assert res.status is IngestStatus.OK
    assert res.note_path is not None
    assert res.note_path.exists()

    # No quarantine record — Stage 3.5 passed.
    failed_dir = ephemeral_vault / "raw" / "inbox" / "failed"
    assert not list(failed_dir.glob("*.needs_review.json"))

    # FakeLLMProvider queue was fully consumed.
    # ``_queue`` is the private attr — exposed for queue-length assertions in
    # other brain_core tests too. Three responses popped → 0 remaining.
    assert fake._queue == []  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_quarantine_json_shape(ephemeral_vault: Path, tmp_path: Path) -> None:
    """Quarantine JSON carries every documented field with correct shapes."""
    garbage = "".join(chr(i) for i in range(256)) * 5
    src = tmp_path / "shape-check.txt"
    src.write_text(garbage, encoding="utf-8")

    fake = FakeLLMProvider()  # empty queue
    pipeline = _make_pipeline(ephemeral_vault, fake)
    await pipeline.ingest(src, allowed_domains=("research",))

    failed_dir = ephemeral_vault / "raw" / "inbox" / "failed"
    records = list(failed_dir.glob("*.needs_review.json"))
    assert len(records) == 1
    data = json.loads(records[0].read_text(encoding="utf-8"))

    # Top-level fields.
    assert data["stage"] == "content_sniff"
    assert data["reason"] == "non_meaningful_text"
    assert data["source_path"] == str(src)
    assert data["source_type"] == "text"
    assert data["slug"].startswith("shape-check")
    assert "ts_utc" in data
    assert "retry_hint" in data

    # Details block.
    details = data["details"]
    assert details["char_count"] == 1280
    assert 0.0 <= details["printable_ratio"] <= 1.0
    assert details["printable_ratio"] < 0.8  # the sniff rejected on this axis
    assert 0.0 <= details["letter_ratio"] <= 1.0
    assert details["has_ocr_markers"] is False


@pytest.mark.asyncio
async def test_pipeline_passes_short_pptx_with_ocr_marker(
    ephemeral_vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A short pptx body with an OCR marker clears Stage 3.5 via D15.

    PptxHandler dispatch requires a real ``.pptx`` on disk; we shortcut by
    stubbing ``dispatch`` to return a hand-built handler that yields an
    :class:`ExtractedSource` with ``source_type=pptx`` + an OCR-marker body
    of <200 chars. Without the D15 exception, Stage 3.5 would quarantine
    on the min_chars floor — verifying the helper integration through the
    pipeline boundary.
    """
    from brain_core.ingest.handlers.base import SourceHandler

    # Hand-built handler whose extract returns an OCR-marker short body.
    class _PptxStub:
        async def extract(
            self, spec: object, *, archive_root: Path
        ) -> ExtractedSource:
            archive_root.mkdir(parents=True, exist_ok=True)
            archive_path = archive_root / "stub.pptx"
            archive_path.write_bytes(b"")  # placeholder archived copy
            return ExtractedSource(
                title="Stub Deck",
                author=None,
                published=None,
                source_url=None,
                source_type=SourceType.PPTX,
                body_text="## Slide 1: \n\n[Image (slide 1): hello world]",
                archive_path=archive_path,
            )

        def can_handle(self, spec: object) -> bool:
            return True

    async def _fake_dispatch(
        spec: object, *, handlers: list[SourceHandler] | None = None
    ) -> _PptxStub:
        return _PptxStub()

    monkeypatch.setattr("brain_core.ingest.pipeline.dispatch", _fake_dispatch)

    fake = FakeLLMProvider()
    # ``domain_override`` skips the classify round-trip — the ClassifyOutput
    # ``source_type`` Literal is stale wrt Plan 24's DOCX/PPTX additions
    # (separate pre-existing gap), so queuing a classify response with
    # ``"pptx"`` would fail pydantic validation. Using the override is the
    # idiomatic path for non-text-handler ingests anyway (e.g. brain_watch_folder
    # passes ``domain_override`` for every watched-folder source).
    fake.queue(
        SummarizeOutput(
            title="Stub Deck",
            summary="An OCR-heavy deck.",
            key_points=["hello world"],
            entities=[],
            concepts=[],
            open_questions=[],
        ).model_dump_json()
    )
    fake.queue(
        PatchSet(
            new_files=[],
            index_entries=[],
            log_entry="ingest",
            reason="t",
        ).model_dump_json()
    )

    pipeline = _make_pipeline(ephemeral_vault, fake)
    # ``spec`` doesn't need to point at a real file — the stubbed dispatch
    # ignores it and returns our hand-built handler directly. Path is used
    # only by ``_slug_for`` to derive the preliminary slug.
    res = await pipeline.ingest(
        Path("stub-deck.pptx"),
        allowed_domains=("research",),
        domain_override="research",
    )

    assert res.status is IngestStatus.OK
    # No quarantine record — D15 OCR-marker exception held.
    failed_dir = ephemeral_vault / "raw" / "inbox" / "failed"
    assert not list(failed_dir.glob("*.needs_review.json"))
    # All three LLM responses consumed.
    assert fake._queue == []  # type: ignore[attr-defined]
