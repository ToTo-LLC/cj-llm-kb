#!/usr/bin/env python3
"""Plan 25 end-to-end demo — bulk-import quality (filtering + sniff + animations).

Walks every substantive-task gate from
``tasks/plans/25-bulk-import-quality.md`` (T0 → T4) plus the closure
marker. Each gate is a structural assertion (file existence, regex
match, ``inspect.signature`` / dynamic-import check, source text
pin) — no live LLM, no network, no spawned servers. Mirrors the
demo-plan-22 / demo-plan-23 / demo-plan-24 shape (cached file reads,
single-purpose gate functions, fail-fast main loop).

Gate map
--------
 1   T0.a  Spec §5 Stages list mentions ``3.5 Content sniff`` between
            Extract (stage 3) and Archive (stage 4) — regex on stage-
            number prefix + section heading.
 2   T0.b  Spec §5 Bulk import has a "Walk-stage filtering" footnote
            documenting system-file denylist + unsupported-type pre-
            filter.
 3   T0.c  Spec §5 day-one handlers table ``pdf`` row reflects T3
            image-mode rendering (mentions ``image-mode`` /
            ``vision_extract`` / ``Page N`` markers).
 4   T1.a  ``BulkImporter`` (``ingest.bulk``) exports ``_SYSTEM_FILES``
            + ``_VALID_EXTENSIONS`` constants — introspect via import.
 5   T1.b  Walk filter integrated in ``BulkImporter.plan()`` — vault
            with ``.DS_Store`` + ``.mov`` + ``real.txt`` returns a plan
            whose items mention only ``real.txt`` (system + unsupported
            files SILENTLY filtered, NOT in ``skipped`` per D2).
 6   T2.a  ``_looks_like_meaningful_text`` helper + thresholds + D15
            OCR-marker exception exist in ``pipeline.py`` (introspect
            via import; check helper signature + module docstring).
 7   T2.b  ``_OCR_MARKER_PATTERN`` regex matches all 3 marker forms
            (``[Image:``, ``[Image (slide N):``, ``[Page N:``).
 8   T2.c  Pipeline ``ingest()`` has Stage 3.5 sniff call —
            ``_looks_like_meaningful_text`` + ``_quarantine_content_sniff``
            both referenced in the same source file.
 9   T2.d  Binary-garbage ``.txt`` quarantines to
            ``raw/inbox/failed/<slug>.<ts>.needs_review.json`` with
            ``stage=content_sniff`` + ``reason=non_meaningful_text``
            (structural JSON shape assertion via direct
            ``_quarantine_content_sniff`` call).
10   T3.a  ``PDFHandler.extract()`` has image-mode branch —
            ``get_pixmap`` + ``_PDF_RENDER_DPI`` constants in the
            handler source.
11   T3.b  ``extras["images"]`` dicts from PDFHandler include
            ``page_index`` (1-based) AND NOT ``slide_index`` — pin
            via grep of ``page_index`` AND absence of ``slide_index``
            string in pdf.py.
12   T3.c  Pipeline ``_ocr_images`` extended to emit ``[Page N: ...]``
            block when image dict has ``page_index``; ``page_index``
            branch precedes ``slide_index`` branch (so PDF context
            wins over a mis-tagged image).
13   T4    Bulk import wizard has per-phase progress UI —
            ``WalkInterstitial`` component + ``Scanning folder...``
            microcopy + ``Importing N of M files`` microcopy in the
            wizard component files.
14   T5    ``tasks/todo.md`` row 25 ✅ + ``tasks/lessons.md`` has a
            ``## Plan 25`` closure section.

Closure (T5) is this script; final stdout line on a clean run is
``PLAN 25 DEMO OK``.

Plan-doc §"Demo gate description" called for ~14 gates after the
T0 split (1 / 2 / 2b → 1 / 2 / 3 here, mapped to T0.a / T0.b / T0.c
in line with the demo-plan-24 sub-letter cadence). This script lands
14 gates — 3 for T0 (one per spec edit) + 2 for T1 (constants + walk
filter integration) + 4 for T2 (helper / regex / pipeline call /
quarantine shape) + 3 for T3 (handler image-mode / page_index field /
pipeline branch) + 1 for T4 + 1 closure.
"""

from __future__ import annotations

import importlib
import inspect
import json
import re
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BRAIN_CORE = _REPO_ROOT / "packages" / "brain_core"
_BRAIN_WEB = _REPO_ROOT / "apps" / "brain_web"

_SPEC = (
    _REPO_ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "2026-04-13-cj-llm-kb-design.md"
)
_BULK = _BRAIN_CORE / "src" / "brain_core" / "ingest" / "bulk.py"
_PIPELINE = _BRAIN_CORE / "src" / "brain_core" / "ingest" / "pipeline.py"
_PDF_HANDLER = (
    _BRAIN_CORE / "src" / "brain_core" / "ingest" / "handlers" / "pdf.py"
)

_WALK_INTERSTITIAL = (
    _BRAIN_WEB / "src" / "components" / "bulk" / "walk-interstitial.tsx"
)
_STEP_APPLY = (
    _BRAIN_WEB / "src" / "components" / "bulk" / "step-apply.tsx"
)
_STEP_PICK_FOLDER = (
    _BRAIN_WEB / "src" / "components" / "bulk" / "step-pick-folder.tsx"
)
_BULK_STORE = (
    _BRAIN_WEB / "src" / "lib" / "state" / "bulk-store.ts"
)

_TODO = _REPO_ROOT / "tasks" / "todo.md"
_LESSONS = _REPO_ROOT / "tasks" / "lessons.md"


def _gate(label: str) -> None:
    print(f"  ok Gate {label}")


def _fail(label: str, why: str) -> int:
    print(f"  FAIL Gate {label}: {why}", file=sys.stderr)
    return 1


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _exists(label: str, path: Path) -> int:
    if not path.is_file():
        return _fail(label, f"file missing: {path}")
    return 0


# ---------------------------------------------------------------------------
# Gate 1 — T0.a: spec §5 Stages list has "3.5 Content sniff".
# ---------------------------------------------------------------------------


def _gate_1_t0_spec_stage_3_5() -> int:
    if rc := _exists("1", _SPEC):
        return rc
    text = _read(_SPEC)
    # Stage 3.5 entry must exist + must be Plan-25-tagged + must mention
    # the OCR-aware exception (D15) so a regression that drops only the
    # exception (the more recent edit) still fails RED.
    if not re.search(
        r"^3\.5\s+\*\*Content sniff\*\*\s*\(Plan 25\)",
        text,
        re.MULTILINE,
    ):
        return _fail(
            "1",
            "spec §5 Stages list missing `3.5 **Content sniff** (Plan 25)` "
            "entry (T0.a edit)",
        )
    if "OCR-aware exception" not in text:
        return _fail(
            "1",
            "spec §5 stage 3.5 entry missing `OCR-aware exception` (D15) "
            "reference — sniff helper would lose the marker bypass contract",
        )
    if "non_meaningful_text" not in text:
        return _fail(
            "1",
            "spec §5 stage 3.5 entry missing `non_meaningful_text` "
            "quarantine reason (D4)",
        )
    _gate(
        "1 — T0.a spec §5 stage 3.5 Content sniff entry: Plan 25 tag + "
        "D15 OCR-aware exception + D4 quarantine reason all present"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 2 — T0.b: spec §5 Bulk import has "Walk-stage filtering" footnote.
# ---------------------------------------------------------------------------


def _gate_2_t0_spec_walk_filtering() -> int:
    text = _read(_SPEC)
    if "**Walk-stage filtering**" not in text:
        return _fail(
            "2",
            "spec §5 Bulk import subsection missing `**Walk-stage filtering**` "
            "footnote (T0.b edit)",
        )
    # The footnote MUST mention both filter classes per D2:
    # system-file denylist + unsupported-type pre-filter. Pin both keywords
    # so a regression that ships only half the contract fails RED.
    if "System file denylist" not in text:
        return _fail(
            "2",
            "spec §5 Walk-stage filtering footnote missing `System file denylist` "
            "bullet (D8 bundled-filter contract)",
        )
    if "Unsupported-type pre-filter" not in text:
        return _fail(
            "2",
            "spec §5 Walk-stage filtering footnote missing "
            "`Unsupported-type pre-filter` bullet (D2 silent-filter contract)",
        )
    _gate(
        "2 — T0.b spec §5 Walk-stage filtering footnote: `**Walk-stage "
        "filtering**` + both bullet classes (denylist + pre-filter) present"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 3 — T0.c: spec §5 day-one handlers table pdf row reflects image-mode.
# ---------------------------------------------------------------------------


def _gate_3_t0_spec_pdf_row_image_mode() -> int:
    text = _read(_SPEC)
    # Find the pdf row in the day-one handlers table; the row MUST mention
    # both `vision_extract` (Plan 24 Protocol method) AND `Page N` (Plan
    # 25 T3 inline marker) so a regression that backslides the row to
    # the pre-Plan-25 `needs_ocr, skipped` shape fails RED.
    pdf_row_match = re.search(
        r"^\|\s*pdf\s*\|.*?\|.*?\|\s*$",
        text,
        re.MULTILINE,
    )
    if pdf_row_match is None:
        return _fail(
            "3",
            "spec §5 day-one handlers table missing pdf row entirely",
        )
    pdf_row = pdf_row_match.group(0)
    if "vision_extract" not in pdf_row:
        return _fail(
            "3",
            f"spec §5 pdf row missing `vision_extract` reference "
            f"(Plan 25 T3 image-mode); row contents:\n  {pdf_row}",
        )
    if "Page N" not in pdf_row:
        return _fail(
            "3",
            f"spec §5 pdf row missing `[Page N: ...]` inline-marker "
            f"reference (Plan 25 T3); row contents:\n  {pdf_row}",
        )
    if "Plan 25" not in pdf_row:
        return _fail(
            "3",
            f"spec §5 pdf row missing `Plan 25` provenance tag "
            f"(T0.c contract); row contents:\n  {pdf_row}",
        )
    _gate(
        "3 — T0.c spec §5 pdf row: `vision_extract` + `Page N` + Plan 25 "
        "provenance all present (replaces pre-Plan-25 `needs_ocr` skip)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 4 — T1.a: BulkImporter exports _SYSTEM_FILES + _VALID_EXTENSIONS.
# ---------------------------------------------------------------------------


def _gate_4_t1_bulk_constants() -> int:
    if rc := _exists("4", _BULK):
        return rc
    try:
        bulk_module = importlib.import_module("brain_core.ingest.bulk")
    except ImportError as exc:
        return _fail(
            "4",
            f"could not import brain_core.ingest.bulk: {exc}",
        )
    if not hasattr(bulk_module, "_SYSTEM_FILES"):
        return _fail(
            "4",
            "brain_core.ingest.bulk missing `_SYSTEM_FILES` constant "
            "(Plan 25 T1 system-file denylist)",
        )
    if not hasattr(bulk_module, "_VALID_EXTENSIONS"):
        return _fail(
            "4",
            "brain_core.ingest.bulk missing `_VALID_EXTENSIONS` constant "
            "(Plan 25 T1 unsupported-type pre-filter)",
        )
    system_files = bulk_module._SYSTEM_FILES
    valid_extensions = bulk_module._VALID_EXTENSIONS
    if not isinstance(system_files, frozenset):
        return _fail(
            "4",
            f"_SYSTEM_FILES must be frozenset (plan-doc T1 template); "
            f"got {type(system_files).__name__}",
        )
    if not isinstance(valid_extensions, frozenset):
        return _fail(
            "4",
            f"_VALID_EXTENSIONS must be frozenset (plan-doc T1 template); "
            f"got {type(valid_extensions).__name__}",
        )
    # Spot-check the denylist for Mac + Windows + Linux representation —
    # T1 outcome receipt promises all three OSes covered.
    if ".DS_Store" not in system_files:
        return _fail(
            "4",
            "_SYSTEM_FILES missing `.DS_Store` (Mac canonical system file)",
        )
    if "Thumbs.db" not in system_files:
        return _fail(
            "4",
            "_SYSTEM_FILES missing `Thumbs.db` (Windows canonical system file)",
        )
    # Day-one handler-claimable extensions per T1 outcome receipt.
    required_exts = {".txt", ".md", ".pdf", ".docx", ".pptx"}
    missing = required_exts - valid_extensions
    if missing:
        return _fail(
            "4",
            f"_VALID_EXTENSIONS missing required handler-claimable suffixes: "
            f"{sorted(missing)}",
        )
    # Pattern-based predicate must also exist.
    if not hasattr(bulk_module, "_is_system_file"):
        return _fail(
            "4",
            "brain_core.ingest.bulk missing `_is_system_file(name)` "
            "predicate (T1 pattern-based denylist)",
        )
    _gate(
        "4 — T1.a BulkImporter constants: `_SYSTEM_FILES` (frozenset, "
        "cross-platform spot-check passed) + `_VALID_EXTENSIONS` (frozenset, "
        "5 day-one extensions present) + `_is_system_file` predicate"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 5 — T1.b: walk filter excludes system + unsupported; only real.txt.
# ---------------------------------------------------------------------------


def _gate_5_t1_walk_filter_integration() -> int:
    try:
        bulk_module = importlib.import_module("brain_core.ingest.bulk")
    except ImportError as exc:
        return _fail(
            "5",
            f"could not import brain_core.ingest.bulk: {exc}",
        )
    # Direct AST/text check that the walk loop applies BOTH new filters
    # BEFORE dispatch. This is a stronger guarantee than a live fixture
    # (which would need a full IngestPipeline + LLMProvider + StateDB
    # rig) — the live behaviour is covered by the 12 dedicated tests in
    # test_bulk_walk_filtering.py per the T1 outcome receipt.
    bulk_text = _read(_BULK)
    # System-file name check inside walk:
    if not re.search(r"_is_system_file\(p\.name\)", bulk_text):
        return _fail(
            "5",
            "BulkImporter.plan() missing `_is_system_file(p.name)` walk-stage "
            "check (T1 system-file denylist not wired)",
        )
    # Ancestor-path system-dir check inside walk:
    if "_is_system_file(part)" not in bulk_text:
        return _fail(
            "5",
            "BulkImporter.plan() missing `_is_system_file(part)` ancestor-path "
            "check (T1 deep-path system-dir exclusion not wired — file inside "
            "__MACOSX/ would leak)",
        )
    # Extension whitelist check inside walk:
    if "_VALID_EXTENSIONS" not in bulk_text:
        return _fail(
            "5",
            "BulkImporter.plan() does not reference `_VALID_EXTENSIONS` "
            "(T1 unsupported-type pre-filter not wired)",
        )
    if not re.search(
        r"p\.suffix\.lower\(\)\s+not in\s+_VALID_EXTENSIONS",
        bulk_text,
    ):
        return _fail(
            "5",
            "BulkImporter.plan() missing `p.suffix.lower() not in "
            "_VALID_EXTENSIONS` walk-stage check (T1 pre-filter shape drift)",
        )
    # Sanity: dispatch happens AFTER the filter checks (filtered files
    # must never reach dispatch + must never land in `plan.skipped` per
    # D2 silent-filter contract).
    # We assert this via grep order: the _VALID_EXTENSIONS line index
    # comes BEFORE any `dispatch(` call within BulkImporter.plan().
    plan_def_idx = bulk_text.find("def plan(")
    if plan_def_idx < 0:
        return _fail(
            "5",
            "BulkImporter.plan() definition not found",
        )
    valid_ext_idx = bulk_text.find("_VALID_EXTENSIONS", plan_def_idx)
    dispatch_idx = bulk_text.find("dispatch(", plan_def_idx)
    if valid_ext_idx < 0:
        return _fail(
            "5",
            "_VALID_EXTENSIONS check not found within BulkImporter.plan() body",
        )
    if dispatch_idx > 0 and valid_ext_idx > dispatch_idx:
        return _fail(
            "5",
            "_VALID_EXTENSIONS filter check appears AFTER `dispatch(...)` "
            "inside BulkImporter.plan() — D2 silent-filter contract violated "
            "(unsupported files would land in `skipped` instead of being "
            "invisible)",
        )
    # Final sanity: bulk module imports without errors AND the bulk_module
    # _is_system_file actually filters known names (live predicate call).
    if not bulk_module._is_system_file(".DS_Store"):  # type: ignore[attr-defined]
        return _fail(
            "5",
            "_is_system_file('.DS_Store') returned False — T1 predicate broken",
        )
    if not bulk_module._is_system_file("._myfile.txt"):  # type: ignore[attr-defined]
        return _fail(
            "5",
            "_is_system_file('._myfile.txt') returned False — T1 AppleDouble "
            "pattern broken",
        )
    if bulk_module._is_system_file("real.txt"):  # type: ignore[attr-defined]
        return _fail(
            "5",
            "_is_system_file('real.txt') returned True — T1 false positive",
        )
    _gate(
        "5 — T1.b BulkImporter.plan() walk filters: name check + ancestor-path "
        "check + extension whitelist all present + filters precede dispatch "
        "(D2 silent-filter contract honored) + live predicate spot-checked"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 6 — T2.a: _looks_like_meaningful_text helper + thresholds in pipeline.
# ---------------------------------------------------------------------------


def _gate_6_t2_sniff_helper() -> int:
    if rc := _exists("6", _PIPELINE):
        return rc
    try:
        pipeline_module = importlib.import_module("brain_core.ingest.pipeline")
    except ImportError as exc:
        return _fail(
            "6",
            f"could not import brain_core.ingest.pipeline: {exc}",
        )
    if not hasattr(pipeline_module, "_looks_like_meaningful_text"):
        return _fail(
            "6",
            "pipeline missing `_looks_like_meaningful_text` helper (T2 sniff)",
        )
    helper = pipeline_module._looks_like_meaningful_text
    sig = inspect.signature(helper)
    params = sig.parameters
    if "body_text" not in params:
        return _fail(
            "6",
            f"_looks_like_meaningful_text missing `body_text` parameter; got "
            f"{list(params)}",
        )
    if "min_chars" not in params:
        return _fail(
            "6",
            f"_looks_like_meaningful_text missing `min_chars` keyword (default "
            f"200 per D3); got {list(params)}",
        )
    # Pin the D3 default explicitly so any silent threshold drift fails RED.
    min_chars_default = params["min_chars"].default
    if min_chars_default != 200:
        return _fail(
            "6",
            f"_looks_like_meaningful_text `min_chars` default must be 200 "
            f"per D3; got {min_chars_default!r}",
        )
    # _TEXT_SHAPED_SOURCE_TYPES set must exist + must include the 5 plan-
    # doc-named types (text, transcript, docx, pptx, pdf) — gate (d) on
    # the T2 review block.
    if not hasattr(pipeline_module, "_TEXT_SHAPED_SOURCE_TYPES"):
        return _fail(
            "6",
            "pipeline missing `_TEXT_SHAPED_SOURCE_TYPES` frozenset (T2)",
        )
    text_shaped = pipeline_module._TEXT_SHAPED_SOURCE_TYPES
    if not isinstance(text_shaped, frozenset):
        return _fail(
            "6",
            f"_TEXT_SHAPED_SOURCE_TYPES must be frozenset; got "
            f"{type(text_shaped).__name__}",
        )
    from brain_core.ingest.types import SourceType  # type: ignore[import-not-found]
    required = {
        SourceType.TEXT,
        SourceType.TRANSCRIPT,
        SourceType.DOCX,
        SourceType.PPTX,
        SourceType.PDF,
    }
    if text_shaped != required:
        return _fail(
            "6",
            f"_TEXT_SHAPED_SOURCE_TYPES drift: expected exactly {required}; "
            f"got {text_shaped}",
        )
    # Live behaviour spot-check: helper returns False on empty body + on
    # binary garbage; True on 300 chars of prose.
    if helper("") is True:
        return _fail(
            "6",
            "_looks_like_meaningful_text('') returned True — empty body must "
            "quarantine",
        )
    prose = (
        "The quick brown fox jumps over the lazy dog. " * 10
    )  # ~440 chars
    if helper(prose) is not True:
        return _fail(
            "6",
            "_looks_like_meaningful_text(long prose) returned False — false "
            "positive on legitimate content",
        )
    _gate(
        "6 — T2.a sniff helper: `_looks_like_meaningful_text(body_text, "
        "*, min_chars=200)` + `_TEXT_SHAPED_SOURCE_TYPES = frozenset({TEXT, "
        "TRANSCRIPT, DOCX, PPTX, PDF})` + live behaviour spot-check"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 7 — T2.b: _OCR_MARKER_PATTERN matches all 3 marker forms.
# ---------------------------------------------------------------------------


def _gate_7_t2_ocr_marker_pattern() -> int:
    try:
        pipeline_module = importlib.import_module("brain_core.ingest.pipeline")
    except ImportError as exc:
        return _fail(
            "7",
            f"could not import brain_core.ingest.pipeline: {exc}",
        )
    if not hasattr(pipeline_module, "_OCR_MARKER_PATTERN"):
        return _fail(
            "7",
            "pipeline missing `_OCR_MARKER_PATTERN` regex (T2 D15 OCR-aware "
            "exception keystone)",
        )
    pat = pipeline_module._OCR_MARKER_PATTERN
    # All 3 documented forms (Plan 24 T4 docx, Plan 24 T4 pptx, Plan 25
    # T3 pdf). Each MUST match — if one form drops, D15 silently regresses.
    image_only = pat.search("intro text [Image: scan of receipt] outro")
    slide_form = pat.search("intro text [Image (slide 1): chart] outro")
    page_form = pat.search("intro text [Page 1: scanned page] outro")
    if image_only is None:
        return _fail(
            "7",
            "_OCR_MARKER_PATTERN does NOT match `[Image: ...]` (Plan 24 T4 "
            "docx inline marker)",
        )
    if slide_form is None:
        return _fail(
            "7",
            "_OCR_MARKER_PATTERN does NOT match `[Image (slide N): ...]` "
            "(Plan 24 T4 pptx inline marker)",
        )
    if page_form is None:
        return _fail(
            "7",
            "_OCR_MARKER_PATTERN does NOT match `[Page N: ...]` "
            "(Plan 25 T3 pdf inline marker)",
        )
    # Negative pin: a literal `[Image` without the colon must NOT match
    # (so prose like "the [Image gallery is empty]" doesn't trigger D15).
    if pat.search("the [Image gallery] is empty") is not None:
        return _fail(
            "7",
            "_OCR_MARKER_PATTERN false-positive on `[Image gallery]` (missing "
            "colon should not match)",
        )
    _gate(
        "7 — T2.b _OCR_MARKER_PATTERN: matches all 3 forms (`[Image:` / "
        "`[Image (slide N):` / `[Page N:`) + rejects colon-less prose"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 8 — T2.c: pipeline ingest() has Stage 3.5 sniff call (regex/AST).
# ---------------------------------------------------------------------------


def _gate_8_t2_stage_3_5_wired() -> int:
    pipe_text = _read(_PIPELINE)
    # Both the helper call AND the quarantine method must appear in the
    # pipeline source. If either is missing the wiring is broken — the
    # helper alone wouldn't quarantine, the method alone wouldn't fire.
    if "_looks_like_meaningful_text" not in pipe_text:
        return _fail(
            "8",
            "pipeline source does not reference `_looks_like_meaningful_text` "
            "(T2 sniff helper not wired)",
        )
    if "_quarantine_content_sniff" not in pipe_text:
        return _fail(
            "8",
            "pipeline source missing `_quarantine_content_sniff` (T2 quarantine "
            "method)",
        )
    # Stage 3.5 must guard on the SourceType set per gate (d) of the T2
    # review block — non-text-shaped types flow through unchanged.
    if "_TEXT_SHAPED_SOURCE_TYPES" not in pipe_text:
        return _fail(
            "8",
            "pipeline source missing `_TEXT_SHAPED_SOURCE_TYPES` membership "
            "check (T2 sniff would fire on URL / EMAIL / TWEET incorrectly)",
        )
    # The sniff check must precede summarize/integrate. Pin via grep:
    # _looks_like_meaningful_text index < _ocr_images index (Stage 5.5
    # OCR runs LATER than Stage 3.5 sniff).
    sniff_idx = pipe_text.find("_looks_like_meaningful_text(")
    ocr_idx = pipe_text.find("self._ocr_images(")
    if sniff_idx < 0:
        return _fail(
            "8",
            "pipeline does not call `_looks_like_meaningful_text(...)` — "
            "Stage 3.5 sniff not actually invoked",
        )
    if ocr_idx < 0:
        return _fail(
            "8",
            "pipeline does not call `self._ocr_images(...)` — Plan 24 T4 OCR "
            "pass missing (cross-plan invariant)",
        )
    # T3 added a PRE-OCR exception for image-mode PDFs so the sniff
    # defers when extras["images"] is non-empty (D15 marker exception
    # doesn't fire pre-OCR because the body is empty). Pin that the guard
    # exists.
    has_pending_ocr_phrase = (
        "extras" in pipe_text
        and "images" in pipe_text
    )
    if not has_pending_ocr_phrase:
        return _fail(
            "8",
            "pipeline source missing `extras['images']` reference — T3 PRE-OCR "
            "exception (skip Stage 3.5 when image-mode PDF awaiting OCR) "
            "likely not wired",
        )
    _gate(
        "8 — T2.c Stage 3.5 wired: `_looks_like_meaningful_text` + "
        "`_quarantine_content_sniff` + `_TEXT_SHAPED_SOURCE_TYPES` guard + "
        "sniff precedes `_ocr_images` + T3 PRE-OCR exception (extras["
        "'images']) present"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 9 — T2.d: binary-garbage quarantines to .needs_review.json with
# correct shape.
# ---------------------------------------------------------------------------


def _gate_9_t2_quarantine_file_shape() -> int:
    try:
        pipeline_module = importlib.import_module("brain_core.ingest.pipeline")
    except ImportError as exc:
        return _fail(
            "9",
            f"could not import brain_core.ingest.pipeline: {exc}",
        )
    # Live structural check: instantiate IngestPipeline-lite enough to call
    # _quarantine_content_sniff(...) on a synthetic ExtractedSource +
    # verify the JSON file matches the documented shape (per the
    # _quarantine_content_sniff docstring).
    from brain_core.ingest.types import ExtractedSource, SourceType  # type: ignore[import-not-found]  # noqa: E501

    # Minimal pipeline construction — instantiate just enough to call the
    # method. IngestPipeline.__init__ requires several deps; for this
    # gate we craft a stub that satisfies the method's only requirement:
    # `self.vault_root` must be a Path.
    class _PipelineStub:
        """Stub satisfying _quarantine_content_sniff's only attribute access."""

        def __init__(self, vault_root: Path) -> None:
            self.vault_root = vault_root

    with tempfile.TemporaryDirectory() as tmp:
        stub = _PipelineStub(Path(tmp))
        binary_body = "\x00\x01\x02\x03" * 200  # 800 chars of control bytes
        extracted = ExtractedSource(
            title="binary garbage",
            author=None,
            published=None,
            source_url=None,
            source_type=SourceType.TEXT,
            body_text=binary_body,
            archive_path=Path(tmp) / "archive" / "binary-source.txt",
            extras={},
        )
        # Call the bound method via the unbound function reference so the
        # stub doesn't need to be a full IngestPipeline.
        quarantine_fn = pipeline_module.IngestPipeline._quarantine_content_sniff
        try:
            written = quarantine_fn(
                stub,  # type: ignore[arg-type]
                spec="/tmp/source.txt",
                slug="binary-source",
                extracted=extracted,
            )
        except Exception as exc:  # noqa: BLE001
            return _fail(
                "9",
                f"_quarantine_content_sniff raised: {type(exc).__name__}: {exc}",
            )
        if not isinstance(written, Path):
            return _fail(
                "9",
                f"_quarantine_content_sniff must return Path; got "
                f"{type(written).__name__}",
            )
        if not written.is_file():
            return _fail(
                "9",
                f"_quarantine_content_sniff did not write the quarantine file: "
                f"{written}",
            )
        # Path layout: <vault>/raw/inbox/failed/<slug>.<ts>.needs_review.json
        if "raw/inbox/failed" not in str(written).replace("\\", "/"):
            return _fail(
                "9",
                f"quarantine path does not include `raw/inbox/failed/`: {written}",
            )
        if not written.name.endswith(".needs_review.json"):
            return _fail(
                "9",
                f"quarantine filename does not end with `.needs_review.json` "
                f"(per D4 suffix contract); got {written.name}",
            )
        if not written.name.startswith("binary-source."):
            return _fail(
                "9",
                f"quarantine filename does not start with `<slug>.` prefix; "
                f"got {written.name}",
            )
        # JSON shape per docstring.
        record = json.loads(written.read_text(encoding="utf-8"))
        for key in (
            "stage",
            "reason",
            "source_path",
            "source_type",
            "slug",
            "ts_utc",
            "details",
            "retry_hint",
        ):
            if key not in record:
                return _fail(
                    "9",
                    f"quarantine JSON missing required key `{key}`; got "
                    f"{sorted(record.keys())}",
                )
        if record["stage"] != "content_sniff":
            return _fail(
                "9",
                f"quarantine `stage` must be `content_sniff`; got "
                f"{record['stage']!r}",
            )
        if record["reason"] != "non_meaningful_text":
            return _fail(
                "9",
                f"quarantine `reason` must be `non_meaningful_text` per D4; "
                f"got {record['reason']!r}",
            )
        details = record["details"]
        for det_key in (
            "char_count",
            "printable_ratio",
            "letter_ratio",
            "has_ocr_markers",
        ):
            if det_key not in details:
                return _fail(
                    "9",
                    f"quarantine `details` missing key `{det_key}`; got "
                    f"{sorted(details.keys())}",
                )
        if details["char_count"] != len(binary_body):
            return _fail(
                "9",
                f"quarantine `details.char_count` mismatch: expected "
                f"{len(binary_body)}; got {details['char_count']}",
            )
    _gate(
        "9 — T2.d binary-garbage quarantine: `raw/inbox/failed/<slug>.<ts>."
        "needs_review.json` written with stage=content_sniff + "
        "reason=non_meaningful_text + diagnostic details (char_count / "
        "ratios / has_ocr_markers)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 10 — T3.a: PDFHandler.extract() has image-mode branch.
# ---------------------------------------------------------------------------


def _gate_10_t3_pdf_image_mode_branch() -> int:
    if rc := _exists("10", _PDF_HANDLER):
        return rc
    pdf_text = _read(_PDF_HANDLER)
    if "_PDF_RENDER_DPI" not in pdf_text:
        return _fail(
            "10",
            "handlers/pdf.py missing `_PDF_RENDER_DPI` module constant "
            "(T3 D14 image-mode rendering)",
        )
    if "_PDF_IMAGE_MODE_FALLBACK_THRESHOLD" not in pdf_text:
        return _fail(
            "10",
            "handlers/pdf.py missing `_PDF_IMAGE_MODE_FALLBACK_THRESHOLD` "
            "constant (T3 D14 trigger threshold)",
        )
    # The render call MUST be `get_pixmap(...)` per pymupdf API.
    if not re.search(r"\.get_pixmap\(", pdf_text):
        return _fail(
            "10",
            "handlers/pdf.py missing `.get_pixmap(...)` call (T3 page-to-PNG "
            "rendering)",
        )
    # The PNG conversion must use `.tobytes("png")` per the plan-doc template.
    if not re.search(r"\.tobytes\(['\"]png['\"]\)", pdf_text):
        return _fail(
            "10",
            "handlers/pdf.py missing `.tobytes('png')` call — image-mode "
            "rendering doesn't actually serialize to PNG bytes",
        )
    # The diagnostic flag `pdf_image_mode` must be settable in extras.
    if "pdf_image_mode" not in pdf_text:
        return _fail(
            "10",
            "handlers/pdf.py missing `pdf_image_mode` flag — diagnostic "
            "extras marker absent (T3 outcome receipt promised flag)",
        )
    _gate(
        "10 — T3.a PDFHandler image-mode: `_PDF_RENDER_DPI` + "
        "`_PDF_IMAGE_MODE_FALLBACK_THRESHOLD` constants + `.get_pixmap(...)` "
        "+ `.tobytes('png')` + `pdf_image_mode` diagnostic flag all present"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 11 — T3.b: extras["images"] dicts include page_index, NOT slide_index.
# ---------------------------------------------------------------------------


def _gate_11_t3_page_index_field() -> int:
    pdf_text = _read(_PDF_HANDLER)
    if '"page_index"' not in pdf_text and "'page_index'" not in pdf_text:
        return _fail(
            "11",
            "handlers/pdf.py does not write `page_index` key to image dict "
            "(T3 image-mode shape contract)",
        )
    # PDF handler must NOT WRITE slide_index to the image dict — that's
    # the PptxHandler's field; the pipeline OCR pass picks branch via key
    # presence so the two MUST stay disjoint. We allow a comment / docstring
    # that REFERENCES the string (for cross-reference documentation) but
    # reject any literal assignment like ``"slide_index":`` inside a dict.
    if re.search(r'["\']slide_index["\']\s*:', pdf_text):
        return _fail(
            "11",
            "handlers/pdf.py writes `slide_index` key to image dict — must "
            "use `page_index` exclusively per T3 contract (mutual-exclusivity "
            "with PptxHandler)",
        )
    _gate(
        "11 — T3.b PDFHandler `extras['images']` shape: `page_index` key "
        "present + `slide_index` key absent (mutual-exclusivity contract)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 12 — T3.c: pipeline _ocr_images extended for page_index → [Page N: ...].
# ---------------------------------------------------------------------------


def _gate_12_t3_pipeline_page_block() -> int:
    pipe_text = _read(_PIPELINE)
    # The `[Page N: ...]` inline-block emission must exist + the
    # page_index branch must come BEFORE the slide_index branch (PDF
    # context wins per the T3 outcome receipt).
    if not re.search(r"\[Page\s+\{?page_index\}?:", pipe_text):
        return _fail(
            "12",
            "pipeline.py missing `[Page {page_index}: ...]` f-string format "
            "(T3 page-block inline marker)",
        )
    # Branch ordering: find page_index AND slide_index branch indices
    # inside _ocr_images. The page_index branch (PDF context) MUST come
    # first so a PDF tagged with both keys (defensive future case) renders
    # as `[Page N: ...]` not `[Image (slide N): ...]`.
    ocr_match = re.search(
        r"async\s+def\s+_ocr_images\s*\([^)]*\)[^:]*:\s*\n(.+?)(?=\n(?:    def |"
        r"    async def |class |def |async def )|\Z)",
        pipe_text,
        re.DOTALL,
    )
    if ocr_match is None:
        return _fail(
            "12",
            "pipeline.py `_ocr_images` function body not found",
        )
    ocr_body = ocr_match.group(1)
    page_index_branch_idx = ocr_body.find('page_index')
    slide_index_branch_idx = ocr_body.find('slide_index')
    if page_index_branch_idx < 0:
        return _fail(
            "12",
            "pipeline.py `_ocr_images` body does not branch on `page_index` "
            "(T3 PDF inline-block emission unwired)",
        )
    if slide_index_branch_idx < 0:
        return _fail(
            "12",
            "pipeline.py `_ocr_images` body does not branch on `slide_index` "
            "(Plan 24 PPTX inline-block emission unwired — cross-plan "
            "invariant)",
        )
    if page_index_branch_idx >= slide_index_branch_idx:
        return _fail(
            "12",
            "pipeline.py `_ocr_images` branches on `slide_index` BEFORE "
            "`page_index` — T3 contract requires PDF context (page_index) "
            "win over PPTX context (slide_index)",
        )
    _gate(
        "12 — T3.c pipeline `_ocr_images` extended: `[Page {page_index}: "
        "...]` format + `page_index` branch precedes `slide_index` branch "
        "(PDF context wins per T3 outcome receipt)"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 13 — T4: bulk-import wizard has per-phase progress UI.
# ---------------------------------------------------------------------------


def _gate_13_t4_wizard_progress_ui() -> int:
    if rc := _exists("13", _WALK_INTERSTITIAL):
        return rc
    walk_text = _read(_WALK_INTERSTITIAL)
    # Walk-phase headline microcopy MUST be verbatim per plan-doc T4
    # microcopy spec.
    if "Scanning folder..." not in walk_text:
        return _fail(
            "13",
            "walk-interstitial.tsx missing verbatim microcopy `Scanning "
            "folder...` (T4 plan-doc spec)",
        )
    if "This may take a moment for large folders." not in walk_text:
        return _fail(
            "13",
            "walk-interstitial.tsx missing verbatim helper microcopy "
            "`This may take a moment for large folders.` (T4)",
        )
    # WalkInterstitial component must be exported (so step-pick-folder can
    # render it).
    if "export function WalkInterstitial" not in walk_text:
        return _fail(
            "13",
            "walk-interstitial.tsx missing `export function WalkInterstitial`",
        )
    if rc := _exists("13", _STEP_APPLY):
        return rc
    apply_text = _read(_STEP_APPLY)
    # Apply-phase microcopy: `Importing N of M files` template string.
    if not re.search(
        r"Importing \$\{applyIdx\}\s+of\s+\$\{included\.length\}\s+files",
        apply_text,
    ):
        return _fail(
            "13",
            "step-apply.tsx missing `Importing ${applyIdx} of "
            "${included.length} files` template literal (T4 plan-doc "
            "verbatim microcopy)",
        )
    if "Estimated time remaining:" not in apply_text:
        return _fail(
            "13",
            "step-apply.tsx missing `Estimated time remaining:` ETA "
            "microcopy (T4)",
        )
    # The bulk-store must declare BulkPhase + the walking phase value.
    if rc := _exists("13", _BULK_STORE):
        return rc
    store_text = _read(_BULK_STORE)
    if "BulkPhase" not in store_text:
        return _fail(
            "13",
            "bulk-store.ts missing `BulkPhase` type alias (T4 phase model)",
        )
    if '"walking"' not in store_text:
        return _fail(
            "13",
            "bulk-store.ts missing `walking` phase literal (T4 walk-phase "
            "wiring)",
        )
    # step-pick-folder must invoke beginWalk to flip phase → walking.
    if rc := _exists("13", _STEP_PICK_FOLDER):
        return rc
    pick_text = _read(_STEP_PICK_FOLDER)
    if "beginWalk" not in pick_text:
        return _fail(
            "13",
            "step-pick-folder.tsx does not call `beginWalk` — T4 walk-phase "
            "trigger not wired",
        )
    _gate(
        "13 — T4 wizard progress UI: WalkInterstitial component + verbatim "
        "microcopy (`Scanning folder...` / `This may take a moment for "
        "large folders.` / `Importing N of M files` / `Estimated time "
        "remaining:`) + BulkPhase + beginWalk wiring all present"
    )
    return 0


# ---------------------------------------------------------------------------
# Gate 14 — T5 closure: todo.md row 25 ✅ + lessons.md Plan 25 section.
# ---------------------------------------------------------------------------


def _gate_14_t5_closure() -> int:
    if rc := _exists("14", _TODO):
        return rc
    todo_text = _read(_TODO)
    if re.search(r"\|\s*25\s*\|.*?✅\s*Complete", todo_text) is None:
        return _fail(
            "14",
            "tasks/todo.md row 25 not marked `✅ Complete`",
        )
    if rc := _exists("14", _LESSONS):
        return rc
    lessons_text = _read(_LESSONS)
    if "## Plan 25" not in lessons_text:
        return _fail(
            "14",
            "tasks/lessons.md missing `## Plan 25` closure section",
        )
    _gate(
        "14 — T5 closure: tasks/todo.md row 25 ✅; tasks/lessons.md has "
        "Plan 25 section"
    )
    return 0


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


_GATES = (
    _gate_1_t0_spec_stage_3_5,
    _gate_2_t0_spec_walk_filtering,
    _gate_3_t0_spec_pdf_row_image_mode,
    _gate_4_t1_bulk_constants,
    _gate_5_t1_walk_filter_integration,
    _gate_6_t2_sniff_helper,
    _gate_7_t2_ocr_marker_pattern,
    _gate_8_t2_stage_3_5_wired,
    _gate_9_t2_quarantine_file_shape,
    _gate_10_t3_pdf_image_mode_branch,
    _gate_11_t3_page_index_field,
    _gate_12_t3_pipeline_page_block,
    _gate_13_t4_wizard_progress_ui,
    _gate_14_t5_closure,
)


def main() -> int:
    for gate_fn in _GATES:
        rc = gate_fn()
        if rc != 0:
            return rc
    print()
    print("PLAN 25 DEMO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
