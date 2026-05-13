"""Plan 25 Task 3 — PDFHandler image-mode rendering + page_index OCR plumbing.

Covers:

* PDFHandler's D14 trigger heuristic (text extraction < 200 chars → render
  every page to PNG, collect into ``extras["images"]`` with ``page_index``
  for the Plan 24 T4 pipeline OCR pass).
* Page-index dict shape (1-based ``page_index`` + 0-based overall ``index``;
  NEVER ``slide_index``).
* Pipeline ``_ocr_images`` extension: ``[Page N: <text>]`` blocks distinct
  from ``[Image (slide N): <text>]`` (PPTX) and ``[Image: <text>]`` (DOCX).
* Stage 3.5 content-sniff pre-OCR exception: image-mode PDFs with empty
  body reach the post-classify OCR pass instead of quarantining.
* Stage 5.5 OCR-pass behaviors that already exist for DOCX/PPTX
  (budget-exhausted → FAILED, no-images → no vision call) extended to PDF.

Hermetic — PDFs built at runtime via ``fitz`` (pymupdf). No binary fixtures.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import fitz  # type: ignore[import-untyped]
import pytest
from brain_core.budget import PerDomainBudgetGuard
from brain_core.config.schema import BudgetOverride, Config
from brain_core.cost.ledger import CostEntry, CostLedger
from brain_core.ingest.handlers.pdf import PDFHandler
from brain_core.ingest.pipeline import IngestPipeline
from brain_core.ingest.types import IngestStatus, SourceType
from brain_core.llm.fake import FakeLLMProvider
from brain_core.prompts.schemas import SummarizeOutput
from brain_core.vault.types import IndexEntryPatch, PatchSet
from brain_core.vault.writer import VaultWriter

# ---------------------------------------------------------------------------
# Hermetic PDF fixture builders (built via fitz; no binary files committed)
# ---------------------------------------------------------------------------


def _make_text_pdf(tmp_path: Path, text: str, *, name: str = "text.pdf") -> Path:
    """Build a text-rich PDF fixture at tmp_path.

    Uses ``insert_textbox`` against the full page rect so long prose is
    wrapped + recovered by ``page.get_text()`` rather than truncated at
    the right margin (which ``insert_text`` does silently).
    """
    doc = fitz.open()
    page = doc.new_page()
    rect = fitz.Rect(40, 40, page.rect.width - 40, page.rect.height - 40)
    page.insert_textbox(rect, text, fontsize=10)
    pdf_path = tmp_path / name
    doc.save(pdf_path)
    doc.close()
    return pdf_path


def _make_image_only_pdf(
    tmp_path: Path,
    *,
    num_pages: int = 1,
    name: str = "scanned.pdf",
) -> Path:
    """Build a scanned-style PDF: pages with shape primitives only, zero text.

    ``draw_rect`` adds a filled rectangle to the page — enough to ensure
    rendering produces non-blank pixels, but contributes ZERO characters
    to ``page.get_text()`` so the handler trips the D14 image-mode trigger.
    """
    doc = fitz.open()
    for _ in range(num_pages):
        page = doc.new_page()
        page.draw_rect(
            fitz.Rect(100, 100, 200, 200),
            fill=(0.5, 0.5, 0.5),
        )
    pdf_path = tmp_path / name
    doc.save(pdf_path)
    doc.close()
    return pdf_path


def _make_near_empty_pdf(
    tmp_path: Path,
    *,
    text: str,
    num_pages: int = 1,
    name: str = "near-empty.pdf",
) -> Path:
    """Build a PDF with a small amount of text + image-heavy pages.

    Used to pin the boundary case where SOME text exists but stays below
    the 200-char D14 threshold.
    """
    doc = fitz.open()
    for _ in range(num_pages):
        page = doc.new_page()
        page.insert_text((50, 50), text)
        page.draw_rect(fitz.Rect(100, 100, 400, 400), fill=(0.5, 0.5, 0.5))
    pdf_path = tmp_path / name
    doc.save(pdf_path)
    doc.close()
    return pdf_path


# ---------------------------------------------------------------------------
# Pipeline plumbing — mirrors test_docx_ocr_integration.py
# ---------------------------------------------------------------------------


def _queue_pipeline_responses(fake: FakeLLMProvider, *, title: str) -> None:
    """Queue summarize + integrate (classify skipped via domain_override)."""
    fake.queue(
        SummarizeOutput(
            title=title,
            summary="summary text",
            key_points=["point"],
            entities=[],
            concepts=[],
            open_questions=[],
        ).model_dump_json()
    )
    fake.queue(
        PatchSet(
            index_entries=[
                IndexEntryPatch(
                    section="Sources",
                    line=f"- [[{title}]] — summary text",
                    domain="research",
                )
            ],
            log_entry=f"## [2026-05-13 10:00] ingest | source | [[{title}]]",
            reason="initial",
        ).model_dump_json()
    )


def _make_pipeline(
    fake: FakeLLMProvider,
    *,
    vault: Path,
    cost_ledger: CostLedger,
    config: Config,
) -> IngestPipeline:
    guard = PerDomainBudgetGuard(cost_ledger)
    return IngestPipeline(
        vault_root=vault,
        writer=VaultWriter(vault_root=vault),
        llm=fake,
        summarize_model="claude-sonnet-4-6",
        integrate_model="claude-sonnet-4-6",
        classify_model="claude-haiku-4-5-20251001",
        guard=guard,
        config=config,
        cost_ledger=cost_ledger,
    )


# ---------------------------------------------------------------------------
# Unit tests — PDFHandler image-mode trigger + page_index propagation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_text_rich_pdf_uses_text_path(tmp_path: Path) -> None:
    """Text-rich PDF (>1000 chars) → standard text path, NO image-mode flag,
    NO rendered images in extras."""
    body = (
        "The quick brown fox jumps over the lazy dog. " * 30
    )  # ~1380 chars, well above 200
    pdf_path = _make_text_pdf(tmp_path, body, name="rich.pdf")

    es = await PDFHandler().extract(pdf_path, archive_root=tmp_path / "arch")

    assert es.source_type is SourceType.PDF
    assert "quick brown fox" in es.body_text
    # Image-mode NOT triggered.
    assert es.extras.get("pdf_image_mode") in (None, False)
    assert es.extras.get("images", []) == []


@pytest.mark.asyncio
async def test_image_only_pdf_renders_pages(tmp_path: Path) -> None:
    """Image-only / scanned PDF (3 pages, zero text) → image-mode fires,
    every page rendered as PNG with 1-based ``page_index``."""
    pdf_path = _make_image_only_pdf(tmp_path, num_pages=3, name="scan.pdf")

    es = await PDFHandler().extract(pdf_path, archive_root=tmp_path / "arch")

    assert es.extras.get("pdf_image_mode") is True
    images = es.extras["images"]
    assert len(images) == 3
    for idx, img in enumerate(images, start=1):
        assert img["page_index"] == idx
        assert img["index"] == idx - 1  # 0-based overall counter
        assert img["content_type"] == "image/png"
        assert isinstance(img["blob"], bytes)
        # PNG magic bytes — proves the renderer emitted a real PNG.
        assert img["blob"][:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_near_empty_pdf_triggers_image_mode(tmp_path: Path) -> None:
    """PDF with 50-char text + 2 image-heavy pages → image-mode (50 < 200)."""
    pdf_path = _make_near_empty_pdf(
        tmp_path,
        text="hello world. short.",  # ~20 chars
        num_pages=2,
        name="brief.pdf",
    )

    es = await PDFHandler().extract(pdf_path, archive_root=tmp_path / "arch")

    assert es.extras.get("pdf_image_mode") is True
    assert len(es.extras["images"]) == 2


@pytest.mark.asyncio
async def test_just_above_threshold_uses_text_path(tmp_path: Path) -> None:
    """PDF whose extracted text is >= 200 chars → text path, NO image-mode
    (even when min_chars is default 200)."""
    # 250-char text body, padded with prose so the pymupdf text extractor
    # has clear paragraphs to recover.
    body = (
        "The quick brown fox jumps over the lazy dog. "
        "Adequate filler prose for the text path. "
        "Adequate filler prose for the text path. "
        "Adequate filler prose for the text path. "
        "Adequate filler prose for the text path. "
        "Adequate filler prose to clear the floor."
    )
    assert len(body) >= 200  # verify fixture
    pdf_path = _make_text_pdf(tmp_path, body, name="border.pdf")

    es = await PDFHandler().extract(pdf_path, archive_root=tmp_path / "arch")

    assert es.extras.get("pdf_image_mode") in (None, False)
    assert es.extras.get("images", []) == []


@pytest.mark.asyncio
async def test_image_mode_uses_page_index_not_slide_index(tmp_path: Path) -> None:
    """Every image dict has ``page_index`` + NEVER ``slide_index``.

    Pins the mutual-exclusivity contract that the pipeline OCR pass relies
    on — ``page_index`` takes precedence over ``slide_index`` in the
    inline-block branching.
    """
    pdf_path = _make_image_only_pdf(tmp_path, num_pages=2, name="excl.pdf")

    es = await PDFHandler().extract(pdf_path, archive_root=tmp_path / "arch")

    for img in es.extras["images"]:
        assert "page_index" in img
        assert "slide_index" not in img


@pytest.mark.asyncio
async def test_extras_pdf_image_mode_flag_only_set_in_image_mode(
    tmp_path: Path,
) -> None:
    """``extras["pdf_image_mode"]`` is True for image-mode PDFs and absent
    (or False) for text-path PDFs."""
    # Text-rich → flag absent.
    text_pdf = _make_text_pdf(
        tmp_path,
        "The quick brown fox jumps over the lazy dog. " * 20,
        name="tr.pdf",
    )
    es_text = await PDFHandler().extract(text_pdf, archive_root=tmp_path / "arch_t")
    assert es_text.extras.get("pdf_image_mode") in (None, False)

    # Image-only → flag True.
    img_pdf = _make_image_only_pdf(tmp_path, num_pages=1, name="im.pdf")
    es_img = await PDFHandler().extract(img_pdf, archive_root=tmp_path / "arch_i")
    assert es_img.extras.get("pdf_image_mode") is True


@pytest.mark.asyncio
async def test_pdf_pixmap_rendered_at_dpi_150(tmp_path: Path) -> None:
    """The rasteriser is called with the documented 150-DPI module constant.

    Intercepts ``fitz.Page.get_pixmap`` via patch + reads the keyword args
    so we don't have to inspect PNG metadata.
    """
    pdf_path = _make_image_only_pdf(tmp_path, num_pages=1, name="dpi.pdf")

    captured_dpis: list[int] = []
    real_get_pixmap = fitz.Page.get_pixmap

    def _record_dpi(self: Any, *args: Any, **kwargs: Any) -> Any:
        captured_dpis.append(kwargs.get("dpi", -1))
        return real_get_pixmap(self, *args, **kwargs)

    with patch.object(fitz.Page, "get_pixmap", _record_dpi):
        await PDFHandler().extract(pdf_path, archive_root=tmp_path / "arch")

    assert captured_dpis == [150]


# ---------------------------------------------------------------------------
# Pipeline integration — page_index dict flows through Stage 5.5 OCR
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_image_mode_pdf_pipeline_inlines_page_blocks(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """Image-only PDF (3 pages) end-to-end through IngestPipeline →
    body carries ``[Page 1: ...]`` ... ``[Page 3: ...]`` and NO
    ``[Image (slide`` or bare ``[Image:`` blocks (PDF context dominates)."""
    pdf_path = _make_image_only_pdf(tmp_path, num_pages=3, name="e2e.pdf")
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    config = Config(vault_path=ephemeral_vault)

    fake = FakeLLMProvider()
    # 1 vision call per page, in handler emission order.
    fake.queue_vision("page one ocr text")
    fake.queue_vision("page two ocr text")
    fake.queue_vision("page three ocr text")
    _queue_pipeline_responses(fake, title="scanned-pdf-e2e")

    p = _make_pipeline(fake, vault=ephemeral_vault, cost_ledger=ledger, config=config)

    r = await p.ingest(
        pdf_path,
        allowed_domains=("research",),
        domain_override="research",
    )

    assert r.status is IngestStatus.OK
    assert r.extracted is not None
    body = r.extracted.body_text
    assert "[Page 1: page one ocr text]" in body
    assert "[Page 2: page two ocr text]" in body
    assert "[Page 3: page three ocr text]" in body
    # NO competing block formats — page_index dominates over slide_index
    # and over the no-index fallback.
    assert "[Image (slide" not in body
    assert "[Image:" not in body
    # Three vision calls fired.
    assert len(fake.vision_calls) == 3
    # Ledger booked op="ocr" rows to the research domain.
    today = datetime.now(tz=UTC).date()
    by_domain = ledger.total_by_domain(today)
    assert by_domain.get("research", 0.0) > 0.0


@pytest.mark.asyncio
async def test_image_mode_pdf_passes_content_sniff_pre_ocr(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """Image-mode PDF bypasses Stage 3.5 content sniff because
    ``extras["images"]`` is non-empty — the pre-OCR body is empty / near-empty
    so the sniff WOULD have quarantined without this exception.

    Pins the Plan 25 T3 + T2 coordination: the pre-OCR exception lets
    image-mode PDFs reach Stage 5.5, where the OCR pass fills the body
    with ``[Page N: ...]`` blocks. End-to-end status = OK (not FAILED on
    sniff)."""
    pdf_path = _make_image_only_pdf(tmp_path, num_pages=1, name="single.pdf")
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    config = Config(vault_path=ephemeral_vault)

    fake = FakeLLMProvider()
    # Brief OCR response — total body remains <200 chars but the
    # ``[Page 1:`` marker is present.
    fake.queue_vision("ok")
    _queue_pipeline_responses(fake, title="single-page-pdf")

    p = _make_pipeline(fake, vault=ephemeral_vault, cost_ledger=ledger, config=config)

    r = await p.ingest(
        pdf_path,
        allowed_domains=("research",),
        domain_override="research",
    )

    # NOT quarantined / FAILED on sniff — reached OCR + completed.
    assert r.status is IngestStatus.OK
    assert r.extracted is not None
    assert "[Page 1: ok]" in r.extracted.body_text
    # No "content_sniff" error in the result.
    assert not any("content_sniff" in e for e in r.errors)


@pytest.mark.asyncio
async def test_image_mode_pdf_budget_exhausted_raises_failed(
    ephemeral_vault: Path, tmp_path: Path
) -> None:
    """Per-domain budget exhausted before OCR fires → BudgetCapExceeded
    propagates to the outer pipeline ``try`` and lands as status=FAILED
    + zero vision calls (gate fired before LLM).

    Mirrors Plan 24 T4's docx budget-exhaustion test, extended for PDF
    image-mode."""
    pdf_path = _make_image_only_pdf(tmp_path, num_pages=2, name="budget.pdf")
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    config = Config(vault_path=ephemeral_vault)
    # Pin a $0.001 daily cap on 'research' and seed a 2x-cap row so the
    # next OCR call exceeds it.
    config.budget.per_domain = {"research": BudgetOverride(daily_cap_usd=0.001)}
    ledger.record(
        CostEntry(
            timestamp=datetime.now(tz=UTC) - timedelta(hours=1),
            operation="ingest",
            model="claude-sonnet-4-6",
            input_tokens=200,
            output_tokens=10,
            cost_usd=0.002,
            domain="research",
        )
    )

    fake = FakeLLMProvider()
    # Queue ONLY summarize+integrate so a wrong-direction failure would
    # surface "vision queue is empty" instead of BudgetCapExceeded.
    _queue_pipeline_responses(fake, title="budget-pdf")

    p = _make_pipeline(fake, vault=ephemeral_vault, cost_ledger=ledger, config=config)

    r = await p.ingest(
        pdf_path,
        allowed_domains=("research",),
        domain_override="research",
    )

    assert r.status is IngestStatus.FAILED
    assert any(
        "BudgetCapExceeded" in e or "cap" in e.lower() or "domain=research" in e
        for e in r.errors
    )
    # The vision LLM was never called — the budget gate fired first.
    assert fake.vision_calls == []
