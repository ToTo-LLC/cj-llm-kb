"""PDF handler — text extraction via pymupdf with Plan 25 T3 image-mode fallback.

Plan 25 T3 changes the pre-existing scanned-PDF behavior:

* Pre-Plan-25: when ``len(extracted_text) < min_chars``, the handler raised
  :class:`ScannedPDFError` (a :class:`HandlerError` subclass) — the pipeline
  surfaced a FAILED ingest and the user was told to OCR the file themselves.

* Plan 25 T3 (D14): when ``len(extracted_text) < min_chars``, the handler
  RENDERS every page to a PNG at 150 DPI and returns those bytes in
  ``extras["images"]`` for the Plan 24 T4 pipeline OCR pass (each image dict
  carries ``page_index`` 1-based + ``index`` 0-based overall counter). The
  pipeline's :meth:`_ocr_images` calls :func:`brain_core.ingest.ocr.ocr_image`
  per page and inlines ``[Page N: <text>]`` blocks into the body. ``body_text``
  on the returned :class:`ExtractedSource` stays whatever native text
  extraction produced (typically empty / near-empty); the pipeline pass adds
  the OCR text downstream.

* ``extras["pdf_image_mode"] = True`` is set as a diagnostic flag so the
  operator can see in logs / downstream introspection which extraction path
  fired.

* Handlers stay pure (Plan 24 T4 architecture): the handler NEVER calls
  :meth:`LLMProvider.vision_extract` directly. It only collects bytes for
  the pipeline to OCR. That keeps budget / cost rails + per-domain guards
  centralised at the pipeline seam.

* :class:`ScannedPDFError` is retained as an alias-friendly export for
  backward compatibility with any caller still importing the symbol; it's
  no longer raised by :meth:`PDFHandler.extract`.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import fitz  # type: ignore[import-untyped]

from brain_core.ingest.handlers.base import HandlerError
from brain_core.ingest.types import ExtractedSource, SourceType


# Plan 25 T3 D14: image-mode trigger threshold. When native text extraction
# returns fewer than this many characters, render every page to a PNG for
# the pipeline OCR pass. Mirrors the pre-Plan-25 ``min_chars`` default that
# previously raised :class:`ScannedPDFError`; behavior at the threshold
# changed (raise → render), the value did not.
_PDF_IMAGE_MODE_FALLBACK_THRESHOLD: int = 200

# Plan 25 T3: render DPI for image-mode page rasterisation. 150 DPI balances
# OCR fidelity (Claude Vision wants > 72 to read body text reliably) against
# token cost (300 DPI quadruples pixel count + image bytes). Hardcoded
# module constant rather than a Config field — promote to ``vision_dpi``
# only when a real use case demands it.
_PDF_RENDER_DPI: int = 150


class ScannedPDFError(HandlerError):
    """Retained for backward-compat imports.

    Plan 25 T3: :meth:`PDFHandler.extract` no longer raises this — it
    renders pages for OCR instead. The class remains a subclass of
    :class:`HandlerError` so any external caller still catching this
    exception name doesn't break at import time.
    """


class PDFHandler:
    source_type: SourceType = SourceType.PDF

    def __init__(self, *, min_chars: int = _PDF_IMAGE_MODE_FALLBACK_THRESHOLD) -> None:
        self._min_chars = min_chars

    def can_handle(self, spec: str | Path) -> bool:
        if not isinstance(spec, Path):
            return False
        return spec.suffix.lower() == ".pdf" and spec.exists()

    async def extract(self, spec: str | Path, *, archive_root: Path) -> ExtractedSource:
        if not isinstance(spec, Path) or not spec.exists():
            raise HandlerError(f"pdf handler cannot read {spec!r}")
        try:
            doc_ctx = fitz.open(spec)
        except fitz.FileDataError as exc:
            raise HandlerError(
                f"Could not open PDF {spec.name!r}: {exc}. "
                "The file may be corrupt, password-protected, or not a PDF."
            ) from exc
        with doc_ctx as doc:
            parts: list[str] = []
            title: str | None = None
            try:
                meta = doc.metadata or {}
                title = meta.get("title") or None
            except Exception:
                title = None
            for page in doc:
                parts.append(page.get_text())
            body = "\n\n".join(p.strip() for p in parts if p.strip())

            # Plan 25 T3 D14: image-mode trigger. When native text extraction
            # falls below ``min_chars``, render every page to PNG so the
            # pipeline OCR pass can recover text via Claude Vision. We do
            # this INSIDE the ``with doc_ctx`` block because pymupdf
            # invalidates page handles once the document context exits.
            images: list[dict[str, Any]] = []
            pdf_image_mode = False
            if self._min_chars > 0 and len(body) < self._min_chars:
                pdf_image_mode = True
                for page_num, page in enumerate(doc, start=1):
                    pix = page.get_pixmap(dpi=_PDF_RENDER_DPI)
                    png_bytes = pix.tobytes("png")
                    images.append(
                        {
                            "blob": png_bytes,
                            "content_type": "image/png",
                            # 1-based for human-readable inline markers
                            # ``[Page N: ...]``. Mutually exclusive with
                            # ``slide_index`` (only PptxHandler sets that).
                            "page_index": page_num,
                            # 0-based overall image counter; matches the
                            # convention DocxHandler + PptxHandler use.
                            "index": page_num - 1,
                        }
                    )
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_path = archive_root / spec.name
        shutil.copy2(spec, archive_path)

        extras: dict[str, Any] = {}
        if images:
            extras["images"] = images
        if pdf_image_mode:
            # Diagnostic flag — lets downstream code (logs, debug tooling)
            # distinguish "PDF that needed OCR" from "PDF with both text
            # and embedded images". Not currently consumed by the
            # pipeline, but cheap to emit and useful in failure analysis.
            extras["pdf_image_mode"] = True

        return ExtractedSource(
            title=title or spec.stem,
            author=None,
            published=None,
            source_url=None,
            source_type=SourceType.PDF,
            body_text=body,
            archive_path=archive_path,
            extras=extras,
        )
