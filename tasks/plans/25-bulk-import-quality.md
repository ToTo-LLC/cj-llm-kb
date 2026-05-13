# Plan 25 — Bulk import quality (filtering + content sniff + interstitial animations)

**Authored:** 2026-05-13 (post Plan 24 close on 2026-05-12, tag
`plan-24-docx-pptx-ingest` at `a2cab32`).
**Scope:** Five bulk-import quality fixes surfaced by user during
hands-on use of Plan 22's bulk-import feature: (1) cross-platform
system file denylist (`.DS_Store`, `Thumbs.db`, `__MACOSX/`, etc.);
(2) pre-filter at walk stage so only handler-claimable file types
enter the plan (no more `.mov`/`.zip` cluttering the list); (3)
per-phase interstitial animations in the bulk-import wizard so users
see progress during long-running walks/classify/apply phases; (4)
pre-classify content sniff so binary-nonsense `.txt` files (random
bytes, encrypted blobs, base64 dumps) skip the LLM calls and quarantine
to `raw/inbox/failed/` instead of burning tokens; (5) PDF + PPTX
image-mode handling so primarily-image files actually consume properly
via Claude Vision OCR (PDFs currently flag `needs_ocr` and skip
entirely; image-heavy PPTX could be quarantined by content sniff
before OCR runs). Per user scope locks: **A = all items as one
focused plan**; **2.A = backend pre-filter at walk stage** (unsupported
files never enter the plan); **4.A = standard sniff thresholds** (200
char min, 80% printable ASCII, 40% letter ratio); **PDF trigger =
heuristic-based** (render+OCR pages when text extraction <200 chars);
**sniff OCR-aware = skip min_chars check when body has OCR markers**
(keep printable + letter ratios).
**Shape:** 5 substantive tasks + 1 closure = 6 total. Per D8 T1
bundles the system-file denylist + unsupported-type pre-filter into
one task. Per D14 T3 NEW handles PDF image-mode (extends Plan 24
vision_extract to PDF pages).

## At a glance

- **Theme A — Foundation** (T0): spec update §5 (Stages list gains
  3.5 content sniff; Bulk import subsection gains filtering note).
- **Theme B — Walk-stage filtering** (T1): cross-platform `_SYSTEM_FILES`
  denylist (Mac + Windows + Linux + dev junk) + `_VALID_EXTENSIONS`
  whitelist (only handler-claimable suffixes enter the plan). Both
  applied at `BulkImporter.plan()` walk stage so the user sees only
  actionable files. Existing `_is_hidden` check stays (handles
  dotfile-based system files like `.git/`); the new denylist
  ADDITIVELY catches non-dot system files like `Thumbs.db`,
  `Desktop.ini`, `__MACOSX/`.
- **Theme C — Content sniff with OCR-awareness** (T2): new pipeline
  stage 3.5 between Extract and Archive — for text-shaped sources,
  check char count + printable ratio + letter ratio. Per D15 the
  min_chars (200) check is SKIPPED when body contains OCR block
  markers (`[Image:`, `[Image (slide`, `[Page N:`) since OCR-heavy
  sources are NOT near-empty; printable + letter ratios still apply.
  Below threshold → quarantine to `raw/inbox/failed/<slug>.needs_review.json`
  with reason `non_meaningful_text` + skip classify/summarize/integrate.
  Zero LLM tokens spent on quarantine path.
- **Theme C2 — PDF image-mode** (T3 NEW): extends PDFHandler with a
  page-render + vision_extract path for image-only / scanned PDFs.
  Per D14 the trigger is heuristic: if text extraction returns
  <200 chars, render each page via `pymupdf.page.get_pixmap()` →
  PNG → `LLMProvider.vision_extract` (Plan 24 T3 helper) → inline
  as `[Page N: <ocr-text>]` blocks. Replaces current `needs_ocr`
  skip-and-flag behavior. Cost: ~$0.003/page (Sonnet vision); a
  50-page scanned PDF ≈ ~$0.15. Bounded by existing per-domain
  budget rail.
- **Theme D — Frontend interstitial animations** (T4): per-phase
  progress UI in the bulk-import wizard (Walk / Classify / Apply).
  File-count + percentage indicator + skeleton/spinner. No mockup
  gate per D10 (polish on existing wizard surface).
- **Closure** (T5): demo + lessons + todo + tag
  `plan-25-bulk-import-quality`.

## Why this plan exists (1 paragraph)

Bulk import via the web wizard is the primary path for users to
seed their vault with existing research / work / personal files.
Plan 22 made it a first-class wizard; Plan 24 extended it to handle
`.docx` / `.pptx` files. But hands-on use surfaced 4 quality issues:
the wizard lists hundreds of irrelevant files (Mac `.DS_Store`,
Windows `Thumbs.db`, video files like `.mov`, etc.) cluttering the
plan view; long walks/classify/apply phases run with no visible
progress indication (users wonder if the app is hung); and `.txt`
files containing computer-generated nonsense (binary masquerading
as text, base64 dumps, encrypted blobs) burn LLM tokens before the
classifier produces a low-confidence answer that lands the file in
`raw/inbox/unrouted/` anyway. Plan 25 closes all four gaps in one
focused plan: walk-stage filtering eliminates system + unsupported
files from the user's view (T1); a cheap pre-classify content sniff
(T2) routes nonsense to quarantine without LLM spend; and per-phase
progress UI (T3) gives the user feedback during long-running phases.
The cost rail and existing quarantine path are reused — no schema
changes, no new dependencies.

## Locked decisions

| # | Decision | Status | Why |
|---|---|---|---|
| D1 | **Scope = A all 4 items.** System file denylist + unsupported-type pre-filter + content sniff + frontend animations. | locked (user A) | All 4 items are bulk-import quality fixes; bundle cleanly. Plan 22 carry-forwards (16 items) stay deferred to Plan 26 — they're a different concern class (architectural / dev-loop). |
| D2 | **Item 2 filter strategy = 2.A backend pre-filter at walk stage.** Unsupported file types (`.mov`, `.zip`, `.iso`, etc.) never enter the plan. The user sees only handler-claimable files. | locked (user 2.A) | Cleanest UX; matches user's explicit ask "this list should only contain valid file types". Trade-off: loses visibility into what was skipped, but the file extension itself is the signal — user can audit by browsing the folder. |
| D3 | **Item 4 sniff thresholds = 4.A standard.** 200 char minimum total content, 80% printable-ASCII ratio, 40% letter ratio. | locked (user 4.A) | Catches binary nonsense, base64 dumps, encrypted blobs while passing legitimate technical docs / code samples / multi-language content. PDF handler already uses similar threshold logic (`needs_ocr` flag at <200 chars from a 5MB PDF). |
| D4 | **Quarantine path for content sniff = `raw/inbox/failed/<slug>.needs_review.json`** with reason `non_meaningful_text`. Mirrors existing quarantine pattern from `pipeline.py` failure handling per spec §5. | locked at authoring | Reuses established failure-handling pattern. User can review quarantined files in Inbox UI (already wires `raw/inbox/failed/` per Plan 07). |
| D5 | **No mockup gate for T3 frontend.** Per Plan 21/23 small-frontend precedent — interstitial animations are polish on the existing bulk-import wizard surface; no new screens; minimal microcopy. | locked at authoring | Mockup gate applies to new UI surfaces (Plan 22 T11 for watched-folders panels). Animation polish on existing flow doesn't trigger it. |
| D6 | **Spec update at T0 per CLAUDE.md non-negotiable.** Adding pipeline stage 3.5 changes the documented Stages list in §5; bulk-import behavior changes (walk-stage filtering) warrant a §5 footnote. | locked per CLAUDE.md | Pipeline stage changes are notable; spec stays the source of truth. |
| D7 | **No new dependencies.** Content sniff uses stdlib (`str.isprintable`, `str.isalpha`); walk filtering is pure pathlib + string ops. | locked per Plan 19-24 D-precedent | Held across nine prior plans. |
| D8 | **T1 bundles system-file denylist + unsupported-type pre-filter.** Both modify the same `BulkImporter.plan()` walk method; same review surface; single PR cleaner. | locked at authoring | Splitting into 2 tasks would mean 2 PRs touching the same method with overlapping diff context. One task = one focused review. |
| D9 | **Push at Plan 25 close after user authorization.** Single `git push origin main` + explicit `git push origin <tag>` for lightweight tag. | locked per Plan 20-24 D-precedent | Standard cadence held across six prior plans. |
| D10 | **Sequential subagent dispatch via subagent-driven-development.** | locked per Plan 19-24 D-precedent | T0 (brain-core) → T1 (brain-core) → T2 (brain-core) → T3 (brain-frontend) → T4 (brain-core closure). |
| D11 | **Combined spec + code-quality review per task.** | locked per Plan 19-24 D-precedent | Held across nine prior plans. |
| D12 | **Pause cadence: none mid-plan.** 5-task budget = plan-close after T4. | locked at authoring | Pause cadence is for larger plans (~5 tasks = no mid-plan pause). |
| D13 | **Plan 26 candidate scope = 22 unchanged carry-forwards from Plan 24 close** (6 Plan 24-surfaced + 16 Plan 22 carry-forwards). Plus any Plan 25-surfaced. | locked at authoring | Plan 25 is orthogonal to those queues — different concern class. |
| D14 | **PDF image-mode trigger = heuristic-based.** Text extraction runs first via existing pymupdf path. If extracted text <200 chars total, switch to page-rendering mode: each PDF page → `page.get_pixmap()` → PNG bytes → `LLMProvider.vision_extract` (Plan 24 T3 helper). Inline as `[Page N: <ocr-text>]` blocks. Replaces current `needs_ocr` skip-and-flag (spec §5 day-one handler row will be updated). | locked (user A) | Cost-efficient: vision LLM only fires when text extraction came up empty. Matches user framing "differently when primarily image content". 50-page scanned PDF ≈ $0.15 vs $0 today (the skip-and-flag) but TODAY the content is unrecoverable; Plan 25 makes it consumable. |
| D15 | **Content-sniff OCR-aware exception.** When body_text contains OCR block markers (`[Image:`, `[Image (slide`, `[Page N:`), the source had visual content that was OCR'd by Plan 24 T4 (or Plan 25 T3 for PDF). Skip the 200-char min_chars check; keep the 80% printable + 40% letter ratio checks. Net: image-heavy PPTX/PDF/DOCX with proper OCR'd content passes sniff; binary nonsense still gets quarantined. | locked (user A) | The 200-char min was meant to catch 'near-empty' files. OCR-heavy sources are NOT near-empty — they had image content the LLM extracted. Printable + letter ratios still catch the binary-nonsense class. |

## Tech stack

Same as Plans 16-24: Python 3.12, pydantic v2, mypy --strict, ruff,
structlog, vitest, Playwright. **No new dependencies.** CI runs on
macos-14 + windows-2022 per Plan 14's matrix.

## Demo gate description

`scripts/demo-plan-25.py` asserts, in sequence (~10 gates):

**T0:**
1. Spec §5 Stages list mentions content sniff (3.5) between Extract
   and Archive (or wherever it lands).
2. Spec §5 Bulk import subsection has a "walk-stage filtering" note
   (system files + unsupported types).
2b. Spec §5 day-one handlers table `pdf` row mentions image-mode
   rendering + Claude Vision OCR (replaces `needs_ocr` skip).

**T1:**
3. `BulkImporter` (or `bulk.py` module) exports a `_SYSTEM_FILES`
   constant (set / frozenset / tuple of file names).
4. `BulkImporter` exports a `_VALID_EXTENSIONS` constant covering
   the handler-claimable suffixes (`.txt`, `.md`, `.markdown`,
   `.pdf`, `.eml`, `.vtt`, `.srt`, `.docx`, `.pptx`).
5. `BulkImporter.plan()` walk excludes both: a fixture vault with
   `.DS_Store` + `Thumbs.db` + `__MACOSX/` + `.mov` + `.zip` + a
   valid `.txt` returns a plan with ONLY the `.txt` in either
   `items` or `skipped`.

**T2:**
6. `pipeline.py` (or sibling) has a `_looks_like_meaningful_text` helper
   (or equivalent name) with the 3 thresholds (200 chars / 80%
   printable / 40% letter).
7. Pipeline ingest flow has a stage 3.5 sniff call between Extract
   and Archive (regex/AST check).
8. A `.txt` fixture with 500 chars of random non-printable bytes
   quarantines to `raw/inbox/failed/` with reason
   `non_meaningful_text` AND no classify/summarize/integrate LLM
   calls fire (assert FakeLLMProvider queue UNCONSUMED).

**T3 (PDF image-mode):**
9. `PDFHandler.extract()` has a low-text branch that renders pages
   to images (regex match for `get_pixmap` or `_render_pages_to_images`
   helper).
10. `extras["images"]` dicts from PDFHandler include `page_index`
    (1-based) AND NOT `slide_index`.
11. Pipeline OCR pass (Plan 24 T4 helper) extended to emit `[Page N:
    <text>]` block when image dict has `page_index`.
12. Integration test: scanned-PDF fixture ingests → body contains
    `[Page 1: <text>]` blocks AND content sniff passes via D15.

**T4 (frontend):**
13. Bulk import wizard frontend has per-phase progress UI elements
    (regex match for Walk/Classify/Apply phase labels or progress
    bars in the wizard component files).

**Closure:**
14. `tasks/todo.md` row 25 marked ✅; `tasks/lessons.md` has Plan 25
    closure section; final stdout `PLAN 25 DEMO OK`.

## Tasks

### Theme A — Foundation

#### T0 — Spec update §5 (stages + bulk filtering note)

**Files:**
- Modify: `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` —
  §5 Stages list gains a "3.5 Content sniff" entry; §5 Bulk import
  subsection gains a "Walk-stage filtering" footnote.

**Goal:** Lock the spec contract before T1+ implementation per
CLAUDE.md non-negotiable.

**What to do:**

**Edit 1 — §5 Stages list** (around line 207-225 in the spec; verify
at exec time):

Insert between current stage 3 (Extract) and stage 4 (Archive):

```markdown
3.5 **Content sniff** (Plan 25) — for text-shaped sources (TextHandler / TranscriptTextHandler / DocxHandler / PptxHandler outputs that produced text bodies), check the extracted `body_text` against cheap heuristics: ≥200 chars, ≥80% printable ASCII ratio, ≥40% letter ratio. Files failing the heuristic quarantine to `raw/inbox/failed/<slug>.needs_review.json` with reason `non_meaningful_text` and skip stages 4-8 entirely (zero LLM token spend). Catches binary garbage masquerading as `.txt`, base64 dumps without context, encrypted blobs, and similar non-meaningful content. Pre-existing PDF `needs_ocr` flag at <200 chars from a 5MB doc is the precedent for this pattern.
```

Re-number subsequent stages: 4 (Archive), 5 (Route), 6 (Summarize),
7 (Integrate), 8 (Apply), 9 (Log & cost). Or keep the original
numbering and call the new step "3.5" to avoid renumbering — if the
spec already references stage 4 elsewhere, the latter is safer. Verify
at exec time.

**Edit 1.5 — §5 day-one handlers table** (around line ~228-237;
verify at exec time). Update the existing `pdf` row to reflect
Plan 25 T3 image-mode behavior:

Replace:
```
| pdf | `pymupdf` | text only; scanned PDFs flagged `needs_ocr`, skipped |
```

With:
```
| pdf | `pymupdf` | text-rich PDFs use text extraction; image-only / scanned PDFs render pages → Claude Vision OCR via `LLMProvider.vision_extract` (Plan 25 T3); replaces pre-Plan-25 `needs_ocr` skip-and-flag behavior. Trigger: text extraction <200 chars (Plan 25 D14). |
```

**Edit 2 — §5 Bulk import subsection** (after the existing 2-sentence
description; verify line number):

Add a "Walk-stage filtering" footnote:

```markdown
**Walk-stage filtering** (Plan 25). `BulkImporter.plan()` applies two
filters during the folder walk so the user sees only actionable
files in the plan view:
- **System file denylist** — cross-platform list of OS-generated
  files that are never user content: `.DS_Store`, `._*` AppleDouble,
  `__MACOSX/`, `.Spotlight-V100/`, `.fseventsd/`, `.Trashes/`,
  `.DocumentRevisions-V100/`, `.TemporaryItems/`, `.AppleDouble/`,
  `.AppleDB/`, `.AppleDesktop/`, `.LSOverride`, `.VolumeIcon.icns`,
  `.com.apple.timemachine.donotpresent` (Mac); `Thumbs.db`,
  `ehthumbs.db`, `ehthumbs_vista.db`, `Desktop.ini`, `desktop.ini`,
  `$RECYCLE.BIN/`, `System Volume Information/`, `pagefile.sys`,
  `hiberfil.sys`, `swapfile.sys` (Windows); `.directory`,
  `.Trash-*/` (Linux); `__pycache__/`, `node_modules/`, `.venv/` (dev
  artifacts). Adds to the existing `_is_hidden` dotfile check.
- **Unsupported-type pre-filter** — only files with extensions
  claimable by a registered handler enter the plan (`.txt`, `.md`,
  `.markdown`, `.pdf`, `.eml`, `.vtt`, `.srt`, `.docx`, `.pptx`).
  Video, archive, executable, image, and other non-text formats are
  silently walked over. URL/Tweet handlers aren't applicable to
  folder walks (those handlers accept URLs as input, not file
  paths).
```

**Per-task review:** combined. Reviewer confirms (a) spec stages
list mentions the new 3.5 step (or renumbered equivalent);
(b) bulk-import section has walk-filtering footnote; (c) no internal
contradictions with existing §5 content; (d) no code changes outside
spec.

### Theme B — Walk-stage filtering

#### T1 — System-file denylist + unsupported-type pre-filter (bundled per D8)

**Files:**
- Modify: `packages/brain_core/src/brain_core/ingest/bulk.py` — add
  `_SYSTEM_FILES` denylist + `_VALID_EXTENSIONS` whitelist constants;
  add `_is_system_file(path)` predicate; modify `BulkImporter.plan()`
  walk to apply both filters BEFORE the existing dispatch check.
- Create or extend: `packages/brain_core/tests/ingest/test_bulk_walk_filtering.py`
  — unit tests for the filter behavior.

**Goal:** Bulk import plan view shows only handler-claimable files
that aren't OS junk.

**What to do:**

1. **`_SYSTEM_FILES` constant.** Define as a frozenset of file/folder
   names. Cross-platform per D8:

```python
_SYSTEM_FILES: frozenset[str] = frozenset({
    # Mac
    ".DS_Store",
    "__MACOSX",  # directory; walk skips at dir level
    ".Spotlight-V100",
    ".fseventsd",
    ".Trashes",
    ".DocumentRevisions-V100",
    ".TemporaryItems",
    ".AppleDouble",
    ".AppleDB",
    ".AppleDesktop",
    ".LSOverride",
    ".VolumeIcon.icns",
    ".com.apple.timemachine.donotpresent",
    "Icon\r",  # Mac folder custom icon (literal Icon? with CR)
    # Windows
    "Thumbs.db",
    "ehthumbs.db",
    "ehthumbs_vista.db",
    "Desktop.ini",
    "desktop.ini",
    "$RECYCLE.BIN",
    "System Volume Information",
    "pagefile.sys",
    "hiberfil.sys",
    "swapfile.sys",
    # Linux
    ".directory",
    # Dev artifacts (often misplaced in a bulk-import folder)
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
})
```

Also handle pattern-based matches:
- `._*` (AppleDouble files like `._myfile.txt`) — starts with `._`
- `.Trash-*` (Linux trash) — starts with `.Trash-`
- `~$*` (Office temp files like `~$document.docx`) — starts with `~$`
- `*.pyc`, `*.pyo`, `*.class` — compiled artifacts (less common at folder roots; lower priority)

Recommend implementing `_is_system_file(name)` as:
```python
def _is_system_file(name: str) -> bool:
    if name in _SYSTEM_FILES:
        return True
    if name.startswith("._"):  # AppleDouble
        return True
    if name.startswith(".Trash-"):  # Linux trash
        return True
    if name.startswith("~$"):  # Office temp
        return True
    return False
```

2. **`_VALID_EXTENSIONS` whitelist.** Define from the day-one handler
   claims (verify at exec time by reading dispatcher.py):

```python
_VALID_EXTENSIONS: frozenset[str] = frozenset({
    ".txt", ".md", ".markdown",  # text + markdown
    ".pdf",
    ".eml",
    ".vtt", ".srt",  # transcripts
    ".docx",  # Word (transcript handler + DocxHandler post-Plan-24)
    ".pptx",  # PowerPoint post-Plan-24
})
```

If any handler accepts different/additional extensions, extend the
set. Verify at exec time.

3. **Walk filter integration in `BulkImporter.plan()`.** Find the
   existing walk loop (the `for path in folder.rglob("*"):` or
   similar; verify at exec time). Add filter checks BEFORE the
   dispatcher check:

```python
for path in folder.rglob("*"):
    # Existing checks (hidden dotfiles, dirs/symlinks)
    if self._is_hidden(path, root=folder):
        continue
    if path.is_dir() or path.is_symlink():
        continue
    # NEW: system-file filter (Plan 25 T1)
    if _is_system_file(path.name):
        continue
    # Also walk over any ancestor path component that's a system dir
    # (e.g., a file deep inside __MACOSX/ shouldn't appear even if
    # its filename isn't itself a system file).
    if any(_is_system_file(part) for part in path.relative_to(folder).parts):
        continue
    # NEW: unsupported-type pre-filter (Plan 25 T1)
    if path.suffix.lower() not in _VALID_EXTENSIONS:
        continue
    # Existing dispatch + plan-building logic
    ...
```

4. **Unit tests** at `packages/brain_core/tests/ingest/test_bulk_walk_filtering.py`:

- **test_dsstore_filtered:** vault with `.DS_Store` + valid `.txt`;
  plan has only the `.txt`.
- **test_thumbs_db_filtered:** vault with `Thumbs.db` + valid `.txt`;
  plan has only the `.txt`.
- **test_macosx_dir_filtered:** vault with `__MACOSX/file.txt` +
  `real-doc.txt`; plan has only `real-doc.txt`.
- **test_mov_filtered:** vault with `video.mov` + valid `.txt`;
  plan has only the `.txt`.
- **test_zip_filtered:** vault with `archive.zip` + valid `.txt`;
  plan has only the `.txt`.
- **test_apple_double_filtered:** vault with `._image.png` + valid
  `.txt`; plan has only the `.txt`.
- **test_office_temp_filtered:** vault with `~$document.docx` + a
  real `.docx`; plan has only the real `.docx`.
- **test_valid_extensions_pass:** vault with `.txt` + `.pdf` +
  `.docx` + `.pptx`; plan has all 4 in `items` (each dispatched
  successfully — use FakeLLMProvider with canned classify
  responses for the items; check item count, not full ingest).
- **test_filter_combined_with_hidden_check:** vault with `.git/foo.txt`
  (hidden by existing _is_hidden) + `.DS_Store` (hidden by new
  denylist) + `.mov` (filtered by suffix) + `real.txt`; plan has
  only `real.txt`.

**Per-task review:** combined. Reviewer confirms (a) `_SYSTEM_FILES`
covers both Mac + Windows lists from the plan-doc; (b) pattern-based
checks (`._*`, `.Trash-*`, `~$*`) handled; (c) `_VALID_EXTENSIONS`
matches actual handler-claimable suffixes; (d) walk filters apply
BEFORE the dispatcher (cost-efficient: never call dispatch on
filtered files); (e) deep-path system-dir filtering works
(`__MACOSX/file.txt` excluded even though `file.txt` itself isn't
system); (f) full brain_core suite stays green.

### Theme C — Content sniff

#### T2 — Pipeline stage 3.5 content sniff + quarantine

**Files:**
- Modify: `packages/brain_core/src/brain_core/ingest/pipeline.py` —
  add `_looks_like_meaningful_text(body_text: str)` helper; insert
  stage 3.5 sniff check between Extract and Archive in the
  `ingest()` method.
- Create or extend: `packages/brain_core/tests/ingest/test_pipeline_content_sniff.py`.

**Goal:** Text files containing computer-generated nonsense (binary,
base64, encrypted) quarantine to `raw/inbox/failed/` without burning
LLM tokens.

**What to do:**

1. **`_looks_like_meaningful_text` helper.** Standard thresholds per
   D3 with **OCR-aware exception** per D15:

```python
import re

_OCR_MARKER_PATTERN = re.compile(r"\[(?:Image(?:\s+\(slide\s+\d+\))?|Page\s+\d+):\s")


def _looks_like_meaningful_text(body_text: str, *, min_chars: int = 200) -> bool:
    """Cheap heuristic: does body_text look like human-readable content?

    Catches binary nonsense masquerading as text, base64 dumps without
    context, encrypted blobs, etc. Passes legitimate technical docs,
    code samples, multi-language content.

    Thresholds per Plan 25 D3:
    - body_text length >= min_chars (default 200) — SKIPPED if body
      contains OCR block markers per D15 (OCR-heavy sources are not
      near-empty regardless of post-OCR length)
    - non-whitespace content >= 50% of body_text length (when min_chars applies)
    - printable ratio >= 80% (printable ASCII or valid Unicode letters/
      digits/whitespace/punctuation; excludes control chars + binary)
    - letter ratio >= 40% (sequences resembling words)
    """
    has_ocr_markers = bool(_OCR_MARKER_PATTERN.search(body_text))
    if not has_ocr_markers and len(body_text) < min_chars:
        return False
    if not has_ocr_markers:
        non_ws = "".join(c for c in body_text if not c.isspace())
        if len(non_ws) < min_chars / 2:
            return False  # too much whitespace = effectively empty
    printable = sum(1 for c in body_text if c.isprintable())
    if len(body_text) > 0 and printable / len(body_text) < 0.8:
        return False
    letters = sum(1 for c in body_text if c.isalpha())
    if len(body_text) > 0 and letters / len(body_text) < 0.4:
        return False
    return True
```

The OCR-marker regex catches three forms:
- `[Image: <text>]` — docx inline images (Plan 24 T4)
- `[Image (slide N): <text>]` — pptx slide images (Plan 24 T4)
- `[Page N: <text>]` — pdf page renders (Plan 25 T3)

2. **Stage 3.5 insertion in `pipeline.py:ingest()`.** Find the
   existing flow at exec time. Insert AFTER Extract (stage 3) returns
   the `ExtractedSource` and BEFORE Archive (stage 4):

```python
# Stage 3.5: Content sniff (Plan 25 T2)
# For text-shaped sources, screen the body for meaningful content.
# Skip classify/summarize/integrate for clearly-non-meaningful files.
if extracted.source_type in {SourceType.TEXT, SourceType.TRANSCRIPT, SourceType.DOCX, SourceType.PPTX}:
    if not _looks_like_meaningful_text(extracted.body_text):
        # Quarantine to raw/inbox/failed/ with structured reason
        await self._quarantine(
            spec=spec,
            extracted=extracted,
            stage="content_sniff",
            reason="non_meaningful_text",
            details={
                "char_count": len(extracted.body_text),
                "printable_ratio": ...,  # compute for diagnostics
                "letter_ratio": ...,
            },
        )
        return IngestResult(
            status=IngestStatus.FAILED,
            errors=["Content sniff: text does not appear to be meaningful (non_meaningful_text)"],
            note_path=None,
        )
```

(Verify the actual quarantine helper at exec time — `_quarantine` may
or may not exist. If not, mirror the existing failure-path pattern in
pipeline.py from Plan 02 / Plan 14 work.)

3. **Quarantine file shape.** Per spec §5 failure handling:
   `raw/inbox/failed/<slug>.error.json` (or `.needs_review.json` —
   verify the established suffix convention). JSON contents:

```json
{
    "stage": "content_sniff",
    "reason": "non_meaningful_text",
    "source_path": "/absolute/path/to/source.txt",
    "details": {
        "char_count": 500,
        "printable_ratio": 0.62,
        "letter_ratio": 0.15
    },
    "retry_command": "brain ingest <path> --force-content-sniff-skip"
}
```

The `retry_command` field is helpful per spec §5 ("Failures land in
`raw/inbox/failed/<slug>.error.json` with stage, exception, and a
retry command"). The flag `--force-content-sniff-skip` doesn't exist
yet; for now just include a placeholder OR write the user-instruction
text in `details.retry_hint` like "If you believe this file is
meaningful, classify it manually via the Inbox UI."

4. **Unit tests** at `packages/brain_core/tests/ingest/test_pipeline_content_sniff.py`:

- **test_meaningful_text_passes:** body = "The quick brown fox..."
  (200+ chars, all letters/spaces); sniff returns True.
- **test_short_body_quarantines:** body = "Hi." (3 chars); sniff
  returns False; pipeline quarantines.
- **test_binary_garbage_quarantines:** body = random non-printable
  bytes decoded with errors="replace" (500 chars of `�`);
  printable_ratio low; quarantines.
- **test_base64_dump_quarantines:** body = 500 chars of base64
  characters with no whitespace ("aGVsbG93b3JsZA..."); letter_ratio
  high but no word-like patterns... actually base64 has letters so
  this test is tricky. Use a fixture with 60% letters + 40% special
  chars; verify quarantines based on word-pattern threshold OR
  adjust expectations.
- **test_quarantine_skips_llm_calls:** FakeLLMProvider with empty
  classify queue; ingest a binary-garbage `.txt`; verify no
  ValueError from empty-queue (because no classify was attempted).
- **test_quarantine_file_written:** ingest a binary-garbage file;
  verify `raw/inbox/failed/<slug>.error.json` (or `.needs_review.json`)
  exists with correct shape.
- **test_pptx_with_image_only_slide_passes:** PptxHandler output has
  `[Image (slide 1): chart of Q4 revenue]` text from OCR; verify
  this passes the sniff EVEN IF total body is short (OCR marker
  triggers D15 min_chars-skip).
- **test_short_ocr_heavy_pptx_passes_via_d15:** single-slide pptx with
  one image; body = `## Slide 1: \n\n[Image (slide 1): hello world]`
  (~50 chars total — below 200); sniff returns True because OCR
  marker present + printable/letter ratios pass.
- **test_pdf_with_page_ocr_markers_passes_via_d15:** PDFHandler image-mode
  output has `[Page 1: <text>]` blocks (Plan 25 T3); body <200 chars;
  passes sniff via D15.
- **test_binary_garbage_with_fake_ocr_marker_still_quarantines:** body =
  `[Image: ` + 500 chars of random non-printable bytes; the marker
  is present but printable ratio fails 80% threshold; quarantines.
  (Pin that OCR-marker exception is NOT a bypass for binary content.)

**Per-task review:** combined. Reviewer confirms (a) sniff helper
matches the 3 documented thresholds + D15 OCR-aware exception;
(b) quarantine path mirrors existing failure-handling pattern;
(c) no LLM tokens spent on quarantined files (FakeLLMProvider queue
stays unconsumed); (d) sniff applies to ALL text-shaped SourceTypes
(text, transcript, docx, pptx, pdf — including Plan 24 + Plan 25 T3
additions); (e) sniff handles UTF-8 content correctly (letters
include non-ASCII Unicode letters); (f) OCR-marker exception
preserves printable + letter ratio checks (binary nonsense with a
fake OCR marker still quarantines); (g) full brain_core suite stays
green.

### Theme C2 — PDF image-mode

#### T3 — PDFHandler image-mode (render + vision_extract)

**Files:**
- Modify: `packages/brain_core/src/brain_core/ingest/handlers/pdf.py`
  — extend PDFHandler with a page-rendering fallback path when text
  extraction returns <200 chars. Reuse Plan 24 T3's `ocr_image`
  helper (or call `LLMProvider.vision_extract` directly via the
  pipeline pattern from Plan 24 T4 — verify integration point at
  exec time).
- Modify: `packages/brain_core/src/brain_core/ingest/pipeline.py` —
  PDF page-rendered images flow through the same OCR pass as DOCX/PPTX
  embedded images (Plan 24 T4 stage 5.5). Verify if any pipeline-level
  changes needed, OR if PDFHandler can self-contain the rendering +
  emit `extras["images"]` for the Plan 24 T4 pipeline pass to pick up.
- Create: `packages/brain_core/tests/ingest/handlers/test_pdf_image_mode.py`.

**Goal:** Image-only / scanned PDFs become consumable via Vision OCR
instead of being skipped with `needs_ocr`. Text-rich PDFs are
unchanged (fast text-extraction path).

**What to do:**

1. **Read existing PDFHandler** at exec time. Find the current
   `needs_ocr` branch — it likely flags + skips when extraction is
   <200 chars (per spec §5 "scanned PDFs flagged `needs_ocr`,
   skipped"). T3 replaces the skip behavior with rendering + OCR.

2. **Decide integration pattern.** Two options:
   - **A. Handler-collects-images, pipeline-OCRs.** PDFHandler's
     extract() detects the low-text case, renders each page via
     `pymupdf.page.get_pixmap()` → PNG bytes, and populates
     `extras["images"]` with `{blob, content_type="image/png",
     page_index, index}` dicts (same shape as PPTX uses for
     `slide_index`). Plan 24 T4's pipeline OCR pass (stage 5.5)
     processes them automatically. Net: zero changes to pipeline.py;
     all logic lives in PDFHandler.
   - **B. Handler calls vision_extract directly.** PDFHandler runs
     OCR inline during extract(). Violates Plan 24 T4's "OCR at
     pipeline level, handlers stay pure" architecture.

   **Choose A** — preserves the Plan 24 T4 architecture. PDFHandler
   collects images; pipeline OCRs.

3. **Page rendering.** Use `pymupdf`:
   ```python
   import pymupdf
   doc = pymupdf.open(path)
   for page_num, page in enumerate(doc, start=1):
       pix = page.get_pixmap(dpi=150)  # 150 DPI = good OCR balance
       png_bytes = pix.tobytes("png")
       images.append({
           "blob": png_bytes,
           "content_type": "image/png",
           "page_index": page_num,  # 1-based for human-readable
           "index": page_num - 1,
       })
   ```
   DPI choice: 150 is a good balance (Tesseract/OCR research suggests
   200-300 for max accuracy, but Claude Vision performs well at 150).
   Verify at exec time; lower if file size becomes a concern.

4. **Trigger condition.** After text extraction, check `len(body_text)`:
   ```python
   if len(extracted_text.strip()) < 200:
       # Image-mode: render pages, collect into extras["images"]
       images = self._render_pages_to_images(doc)
       return ExtractedSource(
           title=...,
           source_type=SourceType.PDF,
           body_text=extracted_text,  # may be empty or near-empty
           extras={"images": images, "pdf_image_mode": True},
           ...
       )
   else:
       # Standard text-extraction path
       return ExtractedSource(body_text=extracted_text, extras={}, ...)
   ```
   The `pdf_image_mode: True` flag in extras is informational
   diagnostic for the pipeline / log.

5. **Pipeline OCR pass integration.** Plan 24 T4's stage 5.5 OCR
   pass iterates `extras["images"]` and inlines `[Image: ...]` /
   `[Image (slide N): ...]` blocks. For PDF, the inline format
   should use `[Page N: ...]`:
   - If image dict has `slide_index` → `[Image (slide N): <text>]`
   - **NEW:** If image dict has `page_index` → `[Page N: <text>]`
   - Else → `[Image: <text>]`

   Verify Plan 24 T4's `_ocr_images` (or similar helper) at exec
   time; extend the dict-shape branching.

6. **Cost estimate.** ~$0.003/page × N pages. A 50-page scanned PDF
   ≈ $0.15 in vision spend. Bounded by existing per-domain budget
   rail (Plan 16 T26-T32). If budget exhausts mid-PDF, the existing
   stage 5.5 budget-exhaustion handler (`BudgetCapExceeded` re-raise
   per Plan 24 T4) pauses cleanly.

7. **Unit tests** at `packages/brain_core/tests/ingest/handlers/test_pdf_image_mode.py`:
   - **test_text_rich_pdf_uses_text_path:** fixture PDF with 1000+
     chars of extractable text; assert `extras["images"]` is empty
     (no rendering); `pdf_image_mode` flag is False or absent.
   - **test_image_only_pdf_renders_pages:** fixture scanned PDF
     (build via pymupdf — render text → image → embed as image-only
     page); assert `extras["images"]` has N entries (1 per page);
     `pdf_image_mode: True`.
   - **test_near_empty_pdf_triggers_image_mode:** PDF with 50 chars
     of text + 3 image-heavy pages; assert image-mode triggered
     (50 < 200 threshold).
   - **test_image_mode_uses_page_index:** verify each image dict
     has `page_index` (1-based), NOT `slide_index`.
   - **test_image_mode_pdf_e2e_integration:** with FakeLLMProvider
     vision queue; ingest scanned PDF; verify body contains
     `[Page 1: <text>]` blocks; content sniff passes via D15
     OCR-marker exception.
   - **test_image_mode_budget_exhausted_raises:** set per-domain
     budget to 0; ingest scanned PDF; assert BudgetCapExceeded
     raised + IngestResult.status = FAILED.

8. **Pipeline _ocr_images extension.** Read Plan 24 T4's helper at
   exec time. Add the page_index branch:
   ```python
   page_idx = img.get("page_index")
   slide_idx = img.get("slide_index")
   if page_idx is not None:
       ocr_blocks.append(f"[Page {page_idx}: {ocr_text.strip()}]")
   elif slide_idx is not None:
       ocr_blocks.append(f"[Image (slide {slide_idx}): {ocr_text.strip()}]")
   else:
       ocr_blocks.append(f"[Image: {ocr_text.strip()}]")
   ```

9. **Spec §5 day-one handlers table.** The pdf row currently says
   "text only; scanned PDFs flagged `needs_ocr`, skipped". T3
   changes this to "text-rich PDFs use text extraction; image-only
   PDFs render pages → Claude Vision OCR (Plan 25 T3); replaces
   pre-Plan-25 `needs_ocr` skip-and-flag behavior". Add this row
   update as part of T0 spec edits (Edit 1 in T0 already touches
   the handlers table; extend to update the pdf row).

**Per-task review:** combined. Reviewer confirms (a) PDFHandler
collects images at handler level (Plan 24 T4 "handlers stay pure"
architecture preserved); (b) pipeline OCR pass extended for
`page_index` dict shape; (c) text-rich PDFs (≥200 chars extracted)
take the fast path with NO vision spend; (d) image-only PDFs
trigger rendering correctly; (e) `[Page N: ...]` inline format
distinct from `[Image (slide N): ...]` and `[Image: ...]`;
(f) content sniff D15 OCR-aware exception applies to PDF page
markers; (g) budget exhaustion mid-PDF raises cleanly; (h) full
brain_core suite stays green; (i) FakeLLMProvider vision queue
consumed correctly per page count.

### Theme D — Frontend interstitial animations

#### T4 — Per-phase progress UI in bulk-import wizard

**Files:**
- Modify: `apps/brain_web/src/components/bulk/*` (verify file
  structure at exec time — likely `bulk-import-wizard.tsx` or per-step
  `step-pick-folder.tsx`, `step-scanning.tsx`, `step-classifying.tsx`,
  `step-applying.tsx`, etc.).
- Modify: `apps/brain_web/src/lib/state/bulk-store.ts` (or
  equivalent) to expose per-phase progress fields (file count,
  current index, percentage).
- Modify: `apps/brain_web/tests/unit/bulk-wizard.test.tsx` (or
  equivalent — verify location).

**Goal:** Users see clear progress indication during long-running
walk / classify / apply phases.

**What to do:**

1. **Identify the 3 phases** in the existing wizard. Per current
   bulk_import flow:
   - **Walk phase** — `BulkImporter.plan()` walks folder; can take
     5-30s for thousands of files.
   - **Classify phase** — per-file classify LLM call; takes ~1-2s
     per file. (If `domain_override` is set, this phase is skipped.)
   - **Apply phase** — per-file summarize+integrate+vault-write;
     takes ~5-10s per file. Only runs if user clicks Apply after
     reviewing the plan.

2. **Per-phase progress UI design:**

   **Walk phase:**
   ```
   ┌─────────────────────────────────────────────┐
   │ Scanning folder...                          │
   │                                             │
   │   ⟳  /Users/.../research/        342 files  │
   │                                             │
   │   This may take a moment for large folders. │
   └─────────────────────────────────────────────┘
   ```
   Static-spinner + live file count (count updates as files are
   walked). If backend supports streaming, use it; otherwise show
   indeterminate spinner with periodic file-count update.

   **Classify phase:**
   ```
   ┌─────────────────────────────────────────────┐
   │ Classifying 27 of 342 files                 │
   │ ████████░░░░░░░░░░░░░░░░░░░░░░░░░  8%       │
   │                                             │
   │ Current: q4-strategy-deck.pptx              │
   │                                             │
   │ Estimated time remaining: ~10m              │
   └─────────────────────────────────────────────┘
   ```
   Progress bar + N of M file count + current filename + (optional)
   ETA.

   **Apply phase:** same shape as Classify but for the ingest stage.

3. **Backend support.** The frontend needs per-phase progress data.
   Two options:
   - **A.** Backend streams progress via WebSocket (Plan 05 set up
     WebSocket chat infrastructure; can extend for bulk progress).
   - **B.** Backend exposes a polling endpoint (`/api/bulk/progress?
     job_id=...`) that frontend polls every ~500ms.
   - **C.** Frontend simulates progress with timer-based animation
     between API calls (no real progress; just keeps the user from
     wondering if it's hung).

   **Recommendation: B (polling)** for v1. Simpler than WebSocket;
   1Hz polling overhead is negligible; works without extending the
   chat-WebSocket protocol. Backend `brain_bulk_import` tool would
   need to expose progress state — likely an in-memory dict keyed
   by job_id. **OR C if the backend can't be modified in this plan's
   scope** — flag as a Plan 26 candidate to add real progress
   streaming.

   For T3 v1, use **C with timer-based pseudo-progress** — the file
   count updates aren't perfectly accurate but the user sees the app
   isn't hung. Real streaming-based progress = Plan 26 candidate.

4. **Animation polish:** subtle transitions between phases (fade
   in/out the phase label + spinner). Don't use Radix dialog
   animation (`waitForAnimationsToFinish` requirement per
   `feedback_axe_dialog_animation_wait.md`) — keep transitions
   simple CSS opacity (no axe-color-contrast issues during transition).

5. **Microcopy** (verbatim — these strings will be vitest-pinned):
   - "Scanning folder..."
   - "Classifying N of M files"
   - "Applying N of M files"
   - "Current: <filename>"
   - "Estimated time remaining: ~Xm" (optional; only if ETA available)
   - "This may take a moment for large folders." (helper text)

6. **Unit tests** at `apps/brain_web/tests/unit/bulk-wizard.test.tsx`:
   - **test_walk_phase_renders_spinner_and_count:** render with
     `{phase: "walking", fileCount: 27}`; assert "Scanning folder..."
     visible + file count displayed.
   - **test_classify_phase_renders_progress_bar:** `{phase:
     "classifying", current: 27, total: 342}`; assert progress bar
     at 8% + "Classifying 27 of 342 files".
   - **test_apply_phase_renders_current_filename:** assert current
     filename visible in the apply phase.
   - **test_phase_transition_animates:** verify CSS class change
     between phases (e.g., a `fade-in` class applied on phase change).
   - **test_zero_state_no_progress:** initial state before walk
     starts; verify no progress UI rendered.

**Per-task review:** combined. Reviewer confirms (a) all 3 phases
have distinct progress UI; (b) microcopy verbatim per the spec
above; (c) animations don't introduce axe-color-contrast issues;
(d) backend support strategy chosen (B polling vs C timer-pseudo)
is documented in T3 outcome; (e) vitest + tsc clean.

### Closure

#### T5 — Closure: demo + lessons + todo + tag

**Files:**
- Create: `scripts/demo-plan-25.py` — assert each gate (~10 gates).
- Modify: `tasks/lessons.md` — Plan 25 closure section.
- Modify: `tasks/todo.md` — row 25 ✅ + Plan 26 candidate scope tail.
- Tag: `plan-25-bulk-import-quality` cut on green demo.

**Lessons to capture:**

1. **Hands-on use surfaces UX gaps faster than spec review.** Plan 22
   shipped bulk-import as a first-class wizard; Plan 24 extended it
   for DOCX/PPTX. Both plans passed review. But the first real
   "point at a folder of mixed files" use case surfaced 4 quality
   issues immediately (system files, unsupported types, no progress
   indication, nonsense-text token-burn). **Rule:** for user-facing
   workflows, the dev's smoke-test ≠ the user's real-world test.
   Build in user-feedback loops between feature plans.

2. **Walk-stage filtering > post-walk skipped-list display.** The
   user explicitly preferred "don't show me unsupported files at
   all" over "show me a collapsible skipped list". Trade-off:
   loses discoverability of "this format isn't supported yet" but
   wins on focus. **Rule:** for high-volume operations (bulk
   import of 1000s of files), the user's mental model is "show me
   only what I can act on" — pre-filter at the walk stage, don't
   surface a separate skip list.

3. **Content sniff as a cheap pre-classify guard.** PDF's pre-existing
   `needs_ocr` flag (skip if <200 chars from a 5MB doc) is the
   precedent. Plan 25 generalizes the pattern: any text-shaped
   source whose body fails cheap heuristics (printable ratio,
   letter ratio, length) skips classify/summarize/integrate.
   Estimated savings: $0.001-0.01 per filtered file × N nonsense
   files in a real-world vault. **Rule:** pre-screen for "is this
   actually content?" BEFORE spending LLM tokens. Cheap heuristics
   often catch what would otherwise become a low-confidence
   classification.

4. **Cross-platform system-file lists are surprisingly long.** Mac
   alone has ~15 distinct system file types; Windows adds ~10;
   Linux ~3. The `_is_hidden` dotfile check handles ~50% of them;
   the rest need explicit denylist entries. Pattern-based matches
   (`._*` AppleDouble, `~$*` Office temp, `.Trash-*` Linux) close
   the long tail. **Rule:** "trust the dotfile convention" is wrong
   for Windows. Explicit denylist is required for cross-platform
   bulk imports.

5. **Frontend polish vs feature work.** Interstitial animations
   are pure UX polish (no functional change). But for long-running
   workflows where users wonder if the app is hung, polish has
   real value — it's the difference between "this works" and
   "this works AND I trust it". **Rule:** for workflows >5s,
   visible progress > "trust the spinner". Especially for new
   users who haven't built up trust with the app yet.

6. **PDF image-mode as Plan 24 OCR extension (T3 NEW lesson).** Pre-
   Plan-25, scanned/image-only PDFs were flagged `needs_ocr` and
   skipped entirely — the content was unrecoverable without external
   OCR. Plan 25 T3 extends Plan 24's `LLMProvider.vision_extract`
   abstraction to PDF pages: `pymupdf.page.get_pixmap()` renders each
   page to PNG; the same pipeline OCR pass (stage 5.5) that handles
   docx/pptx embedded images now also processes PDF pages, inlining
   `[Page N: <text>]` blocks. Per Plan 24 T4 "handlers stay pure",
   PDFHandler collects images into `extras["images"]` with
   `page_index`; pipeline orchestrates OCR. **Rule:** new ingestable
   formats (PDF image-mode, future Excel screenshots, etc.) extend
   the existing OCR architecture rather than adding parallel OCR
   pipelines. Handlers collect; pipeline OCRs; cost rail meters.

7. **OCR-aware content-sniff exception (D15 lesson).** The 200-char
   min_chars threshold was meant to catch near-empty files (PDFs
   that didn't extract text). But OCR-heavy sources (image-only PDFs,
   single-slide PPTX with one image, DOCX with a chart screenshot)
   are NOT near-empty — they had visual content that got OCR'd.
   Plan 25 T2 detects OCR block markers (`[Image:`, `[Image (slide`,
   `[Page N:`) and skips the min_chars check while keeping printable
   + letter ratios. **Rule:** content-sniff guards should be aware
   of upstream pipeline transforms. The "200 chars" threshold encodes
   "this file appears empty"; if OCR ran and produced markers, that
   assumption no longer holds.

**Handoff to Plan 26 paragraph:** 22 unchanged carry-forwards (6
Plan 24-surfaced + 16 Plan 22 carry-forwards) plus any Plan
25-surfaced. Likely Plan 25 surfaces: real progress streaming
(WebSocket-based) for bulk import — Plan 25 T3 ships timer-pseudo
or polling, but real streaming is a future improvement.

## Owning subagents

- **brain-core-engineer** — T0 (spec), T1 (BulkImporter walk filter),
  T2 (pipeline content sniff + OCR-aware exception), T3 (PDF
  image-mode), T5 (closure).
- **brain-frontend-engineer** — T4 (bulk-import wizard animations).

## Workflow rules

Same as Plans 16-24:
- Sequential per-task dispatch via subagent-driven-development.
- Combined spec + code-quality review per task.
- No mid-plan pause (D12).
- No push without explicit user authorization at Plan 25 close (D9).
- pytest recipe per `feedback_uv_uf_hidden.md` (chflags OR PYTHONPATH bypass).
- Frontend per-task verification: vitest + tsc --noEmit per
  `feedback_tsc_vs_vitest.md`.
- Plan-author drift watch (Plan 16/19/20/22/24 lesson): implementers
  MUST grep before assuming file/symbol locations.

## File inventory (summary)

```
tasks/plans/
└── 25-bulk-import-quality.md                       # SELF

docs/superpowers/specs/
└── 2026-04-13-cj-llm-kb-design.md                  # MODIFY: §5 stages + bulk filtering (T0)

packages/brain_core/
├── src/brain_core/ingest/
│   ├── bulk.py                                     # MODIFY: _SYSTEM_FILES + _VALID_EXTENSIONS + walk filter (T1)
│   ├── pipeline.py                                 # MODIFY: stage 3.5 sniff + quarantine (T2); _ocr_images branches on page_index (T3)
│   └── handlers/pdf.py                             # MODIFY: image-mode rendering when text < 200 chars (T3)
└── tests/ingest/
    ├── test_bulk_walk_filtering.py                 # CREATE (T1)
    ├── test_pipeline_content_sniff.py              # CREATE (T2)
    └── handlers/test_pdf_image_mode.py             # CREATE (T3)

apps/brain_web/
├── src/
│   ├── components/bulk/                            # MODIFY: per-phase progress UI (T3)
│   └── lib/state/bulk-store.ts                     # MODIFY: progress fields (T3)
└── tests/unit/
    └── bulk-wizard.test.tsx                        # MODIFY/CREATE: animation tests (T3)

scripts/
└── demo-plan-25.py                                 # CREATE (T4)

tasks/
├── lessons.md                                      # MODIFY: Plan 25 closure (T4)
└── todo.md                                         # MODIFY: row 25 ✅ + Plan 26 (T4)
```

## T0-T5 outcomes

_Filled in at each task close. Standard receipt format mirrors Plan
19-24._

## T0 outcome

**Status:** DONE.

**Edits landed** in `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md`:

1. **§5 Stages list — new "3.5 Content sniff" bullet** (line 215, between stages 3 Extract and 4 Archive). Used `3.5` numbering to avoid renumbering downstream references to stages 4-9. Includes the OCR-aware exception (D15) and lists OCR block markers (`[Image:`, `[Image (slide`, `[Page N:`). Cites PDF's pre-Plan-25 `needs_ocr` flag as precedent and notes it is replaced by T3 image-mode rendering.
2. **§5 Day-one handlers — pdf row** (line 237). Now reads `pymupdf` + `LLMProvider.vision_extract` (Plan 24 T3) for image-mode; Notes describe the dual-path: text-rich PDFs use text extraction, image-only / scanned PDFs trigger page-rendering mode (`get_pixmap()` → PNG → Vision OCR), inlined as `[Page N: <text>]`, trigger <200 chars (D14). Explicitly states it replaces pre-Plan-25 `needs_ocr` skip-and-flag.
3. **§5 Bulk import — Walk-stage filtering footnote** (lines 260-263, after idempotency line, before `### Watched folders`). Two bullets: (a) System file denylist with the full Mac + Windows + Linux + dev-junk list plus pattern matches (`._*`, `~$*`, `.Trash-*`); (b) Unsupported-type pre-filter listing the 9 handler-claimable extensions and noting URL/Tweet handlers don't apply to folder walks.

**Bonus edit (consistency fix):** §5 Failure handling line 314 previously said `<200 chars from a 5MB PDF → needs_ocr, skip, no token spend`. This contradicted the new pdf handler row and the new content sniff stage. Updated to describe the bifurcated behavior: PDFs at <200 chars trigger T3 image-mode (no skip); text-shaped sources at <200 chars fall through to 3.5 Content sniff quarantine. Also restates the D15 OCR-aware sniff exception. This was not in the original T0 edit list but is required for internal consistency — the failure handling description was the only other spec location referencing the old `needs_ocr` skip-and-flag pattern, and leaving it would have contradicted both new edits.

**Wording adjustments vs templates:** None. All three template edits applied verbatim modulo joining template text into existing markdown structure. The bonus failure-handling edit was authored to match Plan 25 D14 + D15 scope locks.

**Internal-consistency check (per CLAUDE.md non-negotiable: spec update first; no contradictions with §3 Domain separation or §10 safety rails):**

- §3 Domain separation (line 188): unaffected — Plan 25 changes are pipeline-internal (Extract → 3.5 Sniff → Archive ordering), not domain-routing.
- §10 Safety rails (line 566): `scope_guard` reference is about path-allowlist enforcement, not ingest gating. Plan 25 quarantine writes go to `raw/inbox/failed/` (already-allowed location for stage failures per line 313). No new safety-rail surface.
- §5 Watched folders: untouched. `BulkImporter.plan()` reference at line 283 is now compatible with the walk-stage filters (filtering applies symmetrically to bulk import and watched-folder initial sync).
- §4 Vault schema: untouched. No new frontmatter fields introduced (quarantine sidecar `.needs_review.json` is sibling of `.error.json`, mirroring existing `Failures land in raw/inbox/failed/<slug>.error.json` pattern at line 313).
- `needs_ocr` references: 3 total post-edit, all in Plan 25 context explicitly calling it the "pre-Plan-25 behavior" (lines 215, 237, 314). No orphan references remain.

**Other spec sections touched:** §5 Failure handling (bonus consistency edit at line 314, as documented above). No other sections needed update.

**Locked decisions covered:** D6 (spec update at T0) ✅; D14 (PDF image-mode trigger <200 chars) documented in handlers table + failure handling; D15 (OCR-aware sniff exception) documented in stages list + failure handling; D7 (no new deps) — confirmed, T0 is docs-only.

**Files changed:**

- `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` (+5 net lines: 1 stages bullet + 1 modified table row + 3 bulk-import lines + 1 modified failure-handling bullet)
- `tasks/plans/25-bulk-import-quality.md` (this outcome receipt)

**Commits (per D9, NOT pushed):**

- _SHA TBD after commit_ — `docs(plan-25): T0 — spec §5 stages 3.5 + handlers pdf row + bulk filtering footnote`
- _SHA TBD after commit_ — `docs(plan-25): T0 — outcome receipts for spec update`

**Self-review concerns:** None blocking. The §5 stage 3.5 prose at line 215 is a single dense paragraph; if the spec convention is shorter bullets, future editors may want to split it into sub-bullets. Kept as-is for T0 to match the template verbatim and to keep numbering simple (sub-bullets would risk renumbering or visual confusion next to stages 4-9).

## T1 outcome

**Status:** DONE.

**Files modified:**

- `packages/brain_core/src/brain_core/ingest/bulk.py` (+101 LOC) — added `_SYSTEM_FILES` frozenset (Mac + Windows + Linux + dev-artifact lists per D8 + plan-doc template; 32 entries), `_VALID_EXTENSIONS` frozenset (9 extensions per spec line 263), `_is_system_file()` predicate (exact-name + `._*` AppleDouble + `.Trash-*` Linux trash + `~$*` Office temp patterns), and 3 new pre-dispatch filter checks in `BulkImporter.plan()` walk loop (system-file name check, ancestor-path system-dir check, extension whitelist check). Filter checks land BETWEEN the existing `_is_hidden` check and the `dispatch` call — order matters because filtered files must be invisible (NOT in `plan.skipped`) per D2. Walk integration at `bulk.py:222-238` (post-edit line range).

- `packages/brain_core/tests/ingest/test_bulk.py` (~+22 / -3 LOC) — adjusted the shared `_make_folder` fixture and the `test_plan_returns_items_and_skips` assertion to match the new D2 contract: `garbage.xyz` (unsupported `.xyz` extension) is now silently filtered (NOT in `skipped`); added `unclaimed.eml` to keep the `plan.skipped` semantic alive (whitelisted extension + no Path-based handler → dispatcher rejection → `skipped`).

**Files created:**

- `packages/brain_core/tests/ingest/test_bulk_walk_filtering.py` (290 LOC, 12 tests) — covers `.DS_Store` exact-name, `Thumbs.db` exact-name, `__MACOSX/` ancestor-path, `$RECYCLE.BIN/` ancestor-path, `.mov` unsupported, `.zip` unsupported, `._*` AppleDouble pattern, `~$*` Office temp pattern, `.Trash-*` Linux pattern, all 4 path-claimable extensions pass (`.txt`/`.pdf`/`.docx`/`.pptx`), combined filter coverage (hidden + system + unsupported all pruned with positive control), `__pycache__/` dev-artifact ancestor-path.

**`_VALID_EXTENSIONS` final list (verified by grepping each handler's `can_handle`):**

`.txt`, `.md`, `.markdown` (TextHandler `_EXTS`); `.pdf` (PDFHandler); `.vtt`, `.srt` (TranscriptVTTHandler `_EXTS`); `.docx` (DocxHandler + TranscriptDOCXHandler); `.pptx` (PptxHandler); `.eml` (kept for forward-compat — EmailHandler currently only claims `str` so `.eml` files on disk land in `plan.skipped` via dispatcher rejection, not items).

**Additional system files beyond the spec footnote:**

The spec §5 Walk-stage filtering footnote (line 262) lists ~27 system files. The plan-doc T1 template adds 5 more: `Icon\r` (Mac folder custom icon), `Network Trash Folder` (Mac SMB share trash), `.tox` (Python tox cache), `.idea` (JetBrains), `.vscode` (Visual Studio Code). Kept the superset per the plan-doc T1 explicit list — `.idea`/`.vscode` are also caught by `_is_hidden` (dotfiles) but live in `_SYSTEM_FILES` for self-documentation per the plan-doc note ("belt-and-suspenders + makes the denylist self-documenting").

**Walk-loop integration location:**

`packages/brain_core/src/brain_core/ingest/bulk.py:222-238` (post-edit) — filter checks land between `_is_hidden` (line ~219) and `dispatch` (line ~244). Order:
1. `max_files` cap check (existing)
2. `is_file()` / `is_symlink()` skip (existing)
3. `_is_hidden` dotfile/ancestor check (existing)
4. **NEW T1:** `_is_system_file(p.name)` — exact-name + pattern match
5. **NEW T1:** ancestor `_is_system_file(part)` — deep-path system-dir exclusion
6. **NEW T1:** `p.suffix.lower() not in _VALID_EXTENSIONS` — silent extension filter
7. `dispatch(p, handlers=...)` — adds to `skipped` on DispatchError (existing)

**Test count and pass status:**

- New tests: 12 (all pass, 0.50s)
- Existing test adjusted: 1 (`test_plan_returns_items_and_skips`)
- Full brain_core suite baseline (pre-T1): 1234 collected, 1234 passed + 5 skipped
- Full brain_core suite post-T1: 1246 collected (+12), 1241 passed + 5 skipped (12.73s)

**Verification recipe (re-run):**

```bash
unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src \
  uv run --package brain_core pytest \
  packages/brain_core/tests/ingest/test_bulk_walk_filtering.py -v
# → 12 passed

unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src \
  uv run --package brain_core pytest packages/brain_core/tests/ -q
# → 1241 passed, 5 skipped
```

**Locked decisions covered:** D2 (unsupported-type pre-filter silent at walk stage, NOT in `skipped`) ✅; D7 (no new dependencies — pure stdlib) ✅; D8 (bundled system-file denylist + unsupported-type pre-filter in one task / one commit) ✅.

**Commits (per D9, NOT pushed):**

- _SHA TBD_ — `feat(plan-25): T1 — BulkImporter walk filter (system files + valid extensions)`
- _SHA TBD_ — `docs(plan-25): T1 — outcome receipts`

**Self-review findings:**

- **Reviewer gates per plan-doc §T1 review block:**
  - (a) `_SYSTEM_FILES` covers Mac (15 entries) + Windows (10) + Linux (1) + dev artifacts (7) — ✅ matches plan-doc template.
  - (b) Pattern-based checks for `._*`, `.Trash-*`, `~$*` — ✅ all three implemented in `_is_system_file`.
  - (c) `_VALID_EXTENSIONS` matches handler-claimable suffixes — ✅ verified by grepping each handler's `can_handle`; `.eml` retained per plan-doc template (forward-compat, lands in `skipped` not silent-filter for now).
  - (d) Walk filters apply BEFORE the dispatcher — ✅ all three new checks are between `_is_hidden` and `dispatch`.
  - (e) Deep-path system-dir filtering — ✅ test `test_macosx_dir_filtered` constructs `__MACOSX/file.txt` (filename itself is plain `file.txt`, not a system match) and asserts exclusion via ancestor-path traversal.
  - (f) Full brain_core suite stays green — ✅ 1241 passed, 5 skipped.

- **No concerns blocking T2.** One minor follow-up worth flagging for T2 (content sniff) reviewer attention: the `.eml` case is the ONLY currently-whitelisted extension with no Path-based handler. If a future plan registers a Path-based EmailHandler, the `test_plan_returns_items_and_skips` fixture's `unclaimed.eml` will need adjustment — the test asserts dispatcher rejection lands it in `skipped`. Noted here for posterity; not a T1 blocker.

- **Cross-platform check:** `_SYSTEM_FILES` is a frozenset of exact filenames — comparison is case-sensitive. This matches reality on macOS (case-insensitive filesystem coalesces `Thumbs.db` and `thumbs.db` at the FS layer, so a single case-sensitive check suffices) and Windows (NTFS is case-insensitive at the OS layer; entries like `desktop.ini` AND `Desktop.ini` are both in the set as belt-and-suspenders). Linux is case-sensitive but the affected files (`.directory`, `.Trash-*`) follow Linux conventions exactly. No cross-platform concerns surfaced.

- **Use of `\r` literal:** `"Icon\r"` is the actual filename macOS uses for folder custom icons (literal CR character in the filename, no extension). Verified the frozenset entry uses the exact `\r` escape and not a string-with-literal-backslash-r. Python frozenset construction handles this correctly; `_is_system_file` does an exact `name in _SYSTEM_FILES` comparison so the CR byte must match exactly. Documented in the inline comment.

## T2 outcome

**Status:** DONE.

**Files modified:**

- `packages/brain_core/src/brain_core/ingest/pipeline.py` (+202 LOC) — added module-level `_OCR_MARKER_PATTERN` regex (matches `[Image:`, `[Image (slide N):`, `[Page N:`), `_TEXT_SHAPED_SOURCE_TYPES` frozenset (5 members: `TEXT`, `TRANSCRIPT`, `DOCX`, `PPTX`, `PDF`; `URL` + `EMAIL` + `TWEET` intentionally excluded), `_looks_like_meaningful_text(body_text, *, min_chars=200)` helper enforcing 4 thresholds (length, non-whitespace, printable ratio, letter ratio) with D15 OCR-marker exception, and `IngestPipeline._quarantine_content_sniff(*, spec, slug, extracted)` method writing `raw/inbox/failed/<slug>.<ts>.needs_review.json` with diagnostic JSON shape. Stage 3.5 inserted between Stage 3 (Extract) and Stage 4 (Content hash + Idempotency) in `ingest()` — fires only when `extracted.source_type in _TEXT_SHAPED_SOURCE_TYPES`; quarantine path returns `IngestStatus.FAILED` and records ingest-history row with `cost_usd=0.0`. Stage 3.5 insertion at `pipeline.py:218-244` (post-edit line range); helper at `pipeline.py:50-128`; quarantine method at `pipeline.py:1338-1410` (post-edit).

- `packages/brain_core/tests/ingest/fixtures/hello.txt` (+1 line) — bumped from 65 chars to 262 chars of meaningful prose. The shipped fixture was used by 12 test files across brain_core + brain_api + brain_mcp; bumping it once is cleaner than rewriting every consumer (and matches the spirit of Stage 3.5 — "real text files have real content").

- `packages/brain_core/tests/ingest/test_pipeline.py` (+8 / -3 LOC) — `test_ingest_records_failure_on_exception` writes inline `"hello body"` (10 chars). Bumped to filler prose so the failure path under test (empty queue at summarize) is reached.

- `packages/brain_core/tests/ingest/test_bulk.py` (+15 / -4 LOC) — added module-level `_MEANINGFUL_BODY` constant (270 chars), updated 3 apply-phase tests (`test_apply_runs_pipeline_per_item_in_order`, `test_apply_does_not_stop_on_failure`, `test_apply_honors_per_item_classified_domain`) to use it. Each file's body is prefixed with a unique short string to avoid Stage 4 idempotency collisions.

- `packages/brain_core/tests/ingest/test_pipeline_ingest_watched_context.py` (+8 / -2 LOC) — bumped inline content in 2 bulk-import tests (`test_bulk_importer_apply_threads_watched_folder_id` + `test_bulk_importer_apply_without_watched_kwarg_is_backwards_compat`).

- `packages/brain_core/tests/ingest/handlers/test_docx_ocr_integration.py` (+17 / -6 LOC) — added module-level `_DOCX_FILLER_PROSE` constant; `_build_image_docx` + `_build_plain_docx` paragraphs prefixed with it so docx bodies clear the sniff floor before reaching the post-classify OCR pass under test.

- `packages/brain_core/tests/ingest/handlers/test_pptx_ocr_integration.py` (+22 / -6 LOC) — added `_PPTX_FILLER` constant; all 4 fixture builders (`_build_three_slide_pptx_with_image_on_slide_2`, `_build_five_slide_pptx_with_images_on_2_and_5`, `_build_plain_pptx`, `_build_two_image_pptx`) bumped per-slide placeholder text.

- `packages/brain_core/tests/watch/test_folder_watcher_integration.py` (+22 / -6 LOC) — bumped 4 inline-content writes in `test_e2e_create_writes_source_note_with_watch_frontmatter` + `test_e2e_create_then_modify_routes_via_update_source` (2 writes: create + modify) + `test_e2e_concurrent_files_each_produce_a_note` (5 burst files, each made distinct + above floor).

- `packages/brain_api/tests/test_tool_endpoints.py` (+5 / -2 LOC) — bumped `test_brain_ingest` `demo.txt` body to clear sniff floor.

- `packages/brain_api/tests/test_upload_endpoint.py` (+5 / -1 LOC) — bumped `test_upload_markdown_happy_path_returns_patch_id` multipart bytes payload.

- `packages/brain_api/tests/test_watched_folders_integration.py` (+5 / -2 LOC) — bumped `test_api_watch_folder_initial_sync_imports_files` alpha + beta inline content.

- `packages/brain_mcp/tests/test_tool_ingest.py` (+5 / -1 LOC) — bumped shared `_write_source_file` helper used by all 3 brain_mcp ingest tests.

**Files created:**

- `packages/brain_core/tests/ingest/test_pipeline_content_sniff.py` (370 LOC, 17 tests) — covers:
  - **12 helper-level tests** for `_looks_like_meaningful_text`: meaningful prose passes, short body quarantines, binary garbage quarantines (all 256 byte-values), high whitespace quarantines, base64-dump-passes (documented heuristic limit), short OCR-marker PPTX passes via D15, short PDF page-marker passes via D15, short docx Image-marker passes via D15, binary-garbage-with-fake-OCR-marker still quarantines (D15 is NOT a binary bypass), digit-only body quarantines on letter ratio, empty body quarantines, Cyrillic multi-language content passes (review gate (e) for UTF-8 letters).
  - **1 set-membership pin** for `_TEXT_SHAPED_SOURCE_TYPES` (review gate (d)).
  - **4 pipeline-integration tests**: binary-garbage `.txt` routes to quarantine with empty FakeLLM queue (no LLM spend per review gate (c)), normal prose `.txt` consumes 3-response queue happy path, quarantine JSON shape pin (every documented field present), short OCR-marker PPTX clears Stage 3.5 via D15 in the integrated pipeline.

**Pipeline insertion point:**

`packages/brain_core/src/brain_core/ingest/pipeline.py` Stage 3.5 lives between Stage 3 (Extract) and Stage 4 (Content hash + Idempotency) in `IngestPipeline.ingest()`. Post-edit line range: `pipeline.py:218-244`. The check fires only when `extracted.source_type in _TEXT_SHAPED_SOURCE_TYPES`; non-text-shaped types (`URL`, `EMAIL`, `TWEET`) flow through unchanged. Quarantine path returns `IngestStatus.FAILED` immediately, skipping stages 4-9 — no LLM round-trip is dispatched.

**Existing quarantine helper reused vs new:**

NEW. The existing `record_failure(...)` in `brain_core/ingest/failures.py` writes `<slug>.<ts>.error.json` for *unexpected exception* failure records. T2's quarantine path is semantically different: it's an EXPECTED quarantine (sniff caught non-meaningful content, no exception involved), so the JSON shape is richer (`stage`, `reason`, diagnostic ratios, `retry_hint`) and the suffix is `.needs_review.json` per plan-doc D4. The new `IngestPipeline._quarantine_content_sniff` method mirrors `record_failure`'s timestamped-filename convention so retries don't overwrite prior records.

**`_TEXT_SHAPED_SOURCE_TYPES` set:**

`{SourceType.TEXT, SourceType.TRANSCRIPT, SourceType.DOCX, SourceType.PPTX, SourceType.PDF}` — verified against `brain_core.ingest.types.SourceType` (8 members; the 3 excluded are `URL`, `EMAIL`, `TWEET`). The plan-doc spec called for these 5; the test `test_text_shaped_source_types_membership` pins the exact set so any future SourceType addition is flagged for explicit decision.

**Test count and pass status:**

- New tests (T2): 17 (all pass, 0.38s)
- Existing tests adjusted for the 200-char floor: 17 distinct test functions across 7 test files (12 in brain_core, 3 in brain_api, 2 in brain_mcp = wait — the actual adjusted count, by file: test_pipeline.py 1, test_bulk.py 3, test_pipeline_ingest_watched_context.py 2, test_docx_ocr_integration.py 5, test_pptx_ocr_integration.py 3, test_folder_watcher_integration.py 3, test_tool_endpoints.py 1, test_upload_endpoint.py 1, test_watched_folders_integration.py 1, test_tool_ingest.py 3 = 23 tests touched).
- Full brain_core suite baseline (pre-T2, T1 closure): 1241 passed + 5 skipped (1246 collected).
- Full brain_core suite post-T2: **1258 passed** + 5 skipped (1263 collected, +17 from new tests). 12.21s.
- Cross-package sweep (brain_core + brain_api + brain_mcp + brain_cli): 1756 passed + 12 skipped, 18.47s. No regressions.

**Verification recipe (re-run):**

```bash
unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src \
  uv run --package brain_core pytest \
  packages/brain_core/tests/ingest/test_pipeline_content_sniff.py -v
# → 17 passed

unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src \
  uv run --package brain_core pytest packages/brain_core/tests/ -q
# → 1258 passed, 5 skipped

unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src \
  uv run --package brain_core pytest \
  packages/brain_core/tests/ packages/brain_api/tests/ packages/brain_mcp/tests/ packages/brain_cli/tests/ -q
# → 1756 passed, 12 skipped
```

**Locked decisions covered:** D3 (sniff thresholds 200/80%/40%) ✅; D4 (quarantine to `raw/inbox/failed/<slug>.needs_review.json` with reason `non_meaningful_text`) ✅; D7 (no new dependencies — stdlib only: `re`, `json`, `pathlib`, `datetime`) ✅; D15 (OCR-marker exception preserves printable + letter ratio checks) ✅.

**Self-review findings:**

- **Reviewer gates per plan-doc §T2 review block:**
  - (a) Sniff helper matches 3 documented thresholds + D15 OCR-aware exception — ✅ helper has 4 thresholds (the spec lists 3 + non-whitespace floor as a sub-rule of the min_chars threshold; my implementation makes the non-whitespace floor explicit so it round-trips correctly under D15 skip). All 4 documented in the helper's docstring.
  - (b) Quarantine path mirrors existing failure-handling pattern — ✅ same `raw/inbox/failed/` dir + same compact-UTC-timestamp suffix shape as `record_failure`. Distinguished by `.needs_review.json` suffix (vs `.error.json`) so the Inbox UI can differentiate "exception failure" from "expected quarantine".
  - (c) No LLM tokens spent on quarantined files — ✅ `test_pipeline_quarantines_binary_garbage` + `test_quarantine_json_shape` both run with FakeLLMProvider queue intentionally EMPTY; if Stage 3.5 fails to short-circuit, the first downstream LLM call would raise `RuntimeError` and the assertion would fail.
  - (d) Sniff applies to ALL text-shaped SourceTypes — ✅ `test_text_shaped_source_types_membership` pins the 5-member set exactly. Future SourceType additions surface as a test failure that requires an explicit decision.
  - (e) UTF-8 content handled correctly — ✅ `test_utf8_letters_count_for_letter_ratio` exercises Cyrillic prose. `str.isalpha` is Unicode-aware so non-ASCII letters count naturally.
  - (f) OCR-marker exception preserves printable + letter ratio checks — ✅ `test_binary_garbage_with_fake_ocr_marker_still_quarantines` constructs `[Image: <620 chars of control codes>]`. The marker is present but printable ratio fails. Pins "D15 is NOT a bypass for binary content".
  - (g) Full brain_core suite stays green — ✅ 1258 passed + 5 skipped (was 1241 + 5). Cross-package: 1756 passed + 12 skipped.

- **Concern — base64-dump heuristic limit (called out in plan-doc):** Test `test_base64_dump_outcome` documents that well-formed base64 dumps PASS the sniff (high letter ratio + 100% printable). This is by design — base64 content is technically "meaningful text" by the helper's heuristics. Downstream classify/summarize prompts have the context to handle it (and pre-Plan-25 behavior left it to the LLM anyway). The sniff is a cheap pre-screen for OBVIOUS nonsense (binary, encrypted), not a sophisticated classifier. A future plan could add a base64-detection sub-rule if production usage shows the LLM wasting tokens on base64 dumps. Documented in the test docstring.

- **Concern — fixture bump impact:** Bumping `tests/ingest/fixtures/hello.txt` from 65 → 262 chars touches a shared fixture used across 12 test files. Verified all consumers continue to pass; the bumped content has the same shape (UTF-8 prose) and is a strict superset of the old content (starts with "Hello, brain."), so any test that asserts on the *first line* of body_text still works. No idempotency-test surprise: content_hash is computed at runtime per-test, not pre-recorded.

- **Concern — Plan 24 `docx`/`pptx` `ClassifyOutput.source_type` Literal gap:** The pipeline-integration test `test_pipeline_passes_short_pptx_with_ocr_marker` had to use `domain_override` because `ClassifyOutput.source_type` is annotated `Literal["text", "url", "pdf", "email", "transcript", "tweet"]` — missing the Plan 24 additions of `docx` + `pptx`. This is a pre-existing gap (Plan 24 added the SourceType members + handlers + frontmatter support but didn't extend the classify prompt's output schema). Not a T2 blocker — the production code path that ingests `.pptx` files (e.g. `brain_watch_folder`) already passes `domain_override` since the watch is scoped to a single domain. Flag for a future plan: extend the ClassifyOutput Literal to match `SourceType`.

- **Cross-platform check:** `_OCR_MARKER_PATTERN` is a raw regex over Unicode strings — no path separators, no platform-specific bytes. The quarantine file path uses `pathlib.Path` and `datetime.now(tz=UTC).strftime(...)` — both cross-platform. Filename suffix `.needs_review.json` is a plain ASCII suffix that Windows + macOS + Linux all accept. The compact timestamp `%Y%m%dT%H%M%S%f` contains no reserved characters. No POSIX-only assumptions.

- **Empty-body early-return:** Added a `len(body_text) == 0` short-circuit at the top of `_looks_like_meaningful_text` (not in the plan-doc spec). Necessary because the printable/letter ratio computations divide by `len(body_text)`. Without it, a body of `""` would `ZeroDivisionError` on the printable check. The plan-doc snippet had `if len(body_text) > 0 and printable / ...` guards on both ratio checks; my implementation does the equivalent via the top-of-function early return, which is cleaner and avoids the guard repetition. Documented in the helper's docstring and pinned by `test_empty_body_quarantines`.

**Commits (per D9, NOT pushed):**

- _SHA TBD_ — `feat(plan-25): T2 — pipeline content-sniff stage 3.5 + OCR-aware exception`
- _SHA TBD_ — `test(plan-25): T2 — helper + pipeline integration tests + fixture bumps`
- _SHA TBD_ — `docs(plan-25): T2 — outcome receipts`

## T3 outcome

**Status:** DONE.

**Files modified:**

- `packages/brain_core/src/brain_core/ingest/handlers/pdf.py` (rewritten, +99 / -25 LOC net) — replaced the pre-Plan-25 `ScannedPDFError`-raising skip-and-flag behavior with D14 image-mode: native text extraction always runs first; when `len(body) < min_chars`, every page is rendered to PNG at 150 DPI via `fitz.Page.get_pixmap(dpi=150)` + `pix.tobytes("png")` and collected into `extras["images"]` as `{"blob": bytes, "content_type": "image/png", "page_index": <1-based>, "index": <0-based>}` dicts (mirrors the PptxHandler shape, swapping `slide_index` → `page_index`). `extras["pdf_image_mode"] = True` is set as a diagnostic flag in the image-mode branch. The handler stays pure — `LLMProvider.vision_extract` is NEVER called here; the Plan 24 T4 pipeline OCR pass handles the rendered images. `ScannedPDFError` retained as an empty subclass of `HandlerError` so any external importer doesn't break. Module-level constants `_PDF_IMAGE_MODE_FALLBACK_THRESHOLD = 200` + `_PDF_RENDER_DPI = 150`.

- `packages/brain_core/src/brain_core/ingest/pipeline.py` (+24 / -7 LOC) — extended `_ocr_images` inline-block branching at `pipeline.py:1257-1273` (post-edit): `page_index` is checked FIRST (PDF context dominates) → `[Page N: <text>]`; `slide_index` second → `[Image (slide N): <text>]`; else fallback → `[Image: <text>]`. The `ingest.ocr.image_skipped` warning log now also carries `page_index=img.get("page_index")` so partial-failure diagnostics in image-mode PDFs show which page errored. Stage 3.5 content-sniff guard at `pipeline.py:286-322` (post-edit) extended with a PRE-OCR exception: when `extras["images"]` is non-empty, sniff is SKIPPED entirely so image-mode PDFs (with empty pre-OCR body) reach Stage 5.5 instead of quarantining. This is necessary because D15's marker-aware exception only fires on POST-OCR bodies — pre-OCR there's nothing for the regex to match. Documented inline as "Plan 25 T3 PRE-OCR exception".

**Files created:**

- `packages/brain_core/tests/ingest/handlers/test_pdf_image_mode.py` (+393 LOC) — 10 unit + integration tests built via hermetic `fitz`-constructed PDF fixtures (no binary files committed). Coverage:
  1. `test_text_rich_pdf_uses_text_path` — text-rich PDF (>1000 chars via `insert_textbox`) → no `pdf_image_mode` flag, `extras["images"]` empty.
  2. `test_image_only_pdf_renders_pages` — 3-page image-only PDF → 3 PNG entries with correct 1-based `page_index` + 0-based `index`; PNG magic-byte check on each blob.
  3. `test_near_empty_pdf_triggers_image_mode` — ~20-char text PDF (<200) → image-mode fires.
  4. `test_just_above_threshold_uses_text_path` — 250+ char body → text path, no image-mode.
  5. `test_image_mode_uses_page_index_not_slide_index` — pins the mutual-exclusivity contract.
  6. `test_extras_pdf_image_mode_flag_only_set_in_image_mode` — flag present in image-mode, absent in text path.
  7. `test_pdf_pixmap_rendered_at_dpi_150` — `unittest.mock.patch.object(fitz.Page, "get_pixmap", ...)` intercepts the kwarg + asserts `dpi=150`.
  8. `test_image_mode_pdf_pipeline_inlines_page_blocks` — end-to-end through `IngestPipeline` with `FakeLLMProvider.queue_vision`; body carries `[Page 1: ...]`...`[Page 3: ...]` with NO `[Image (slide` or `[Image:` blocks; ledger booked `op="ocr"` rows to `research`.
  9. `test_image_mode_pdf_passes_content_sniff_pre_ocr` — single-page image-only PDF whose post-OCR body stays <200 chars; status=OK (proves the Stage 3.5 pre-OCR exception fires + the D15 OCR-marker exception covers the post-OCR sniff implicitly via the marker regex).
  10. `test_image_mode_pdf_budget_exhausted_raises_failed` — daily cap $0.001 + seeded 2x-cap ledger row; status=FAILED, errors contain "BudgetCapExceeded"/"cap"/"domain=research", `fake.vision_calls == []` (gate fired before LLM).

- `packages/brain_core/tests/ingest/test_handler_pdf.py` (+27 / -3 LOC) — updated `test_pdf_handler_flags_probable_scan` → `test_pdf_handler_low_text_triggers_image_mode` (asserts new behavior: rendered pages in `extras` instead of `ScannedPDFError` raise); added `test_pdf_handler_extracts_text` body to assert no `pdf_image_mode` flag on the rich path; added `test_scanned_pdf_error_remains_handler_error_subclass` pinning the backward-compat export.

**Extension points (file:line):**

- PDFHandler image-mode trigger: `packages/brain_core/src/brain_core/ingest/handlers/pdf.py:102-122` (the `if self._min_chars > 0 and len(body) < self._min_chars` branch).
- Pipeline `_ocr_images` `page_index` branch: `packages/brain_core/src/brain_core/ingest/pipeline.py:1257-1273` (post-edit; was 1242-1246 pre-edit).
- Pre-OCR content-sniff exception: `packages/brain_core/src/brain_core/ingest/pipeline.py:286-296` (post-edit; the `_has_pending_ocr_images` guard short-circuits the sniff branch when `extras["images"]` is non-empty).

**Pre-Plan-25 `needs_ocr` skip-and-flag removal:** the location was `packages/brain_core/src/brain_core/ingest/handlers/pdf.py:50-54` (pre-edit) raising `ScannedPDFError` with `f"extracted {len(body)} chars from {spec.name}; below min={self._min_chars} (likely scanned)"`. T3 replaced the `raise` with the image-mode render loop. The `ScannedPDFError` class is preserved as an export-friendly alias (empty subclass of `HandlerError`) so external importers don't break on the symbol vanishing, but it's no longer raised by `extract()`.

**Verification:**

- New tests: 10 in `test_pdf_image_mode.py` + 1 new in `test_handler_pdf.py` = 11 new. All passing.
- Brain_core baseline: 1258 (T2 close) → post-T3 1269 (+11). 5 skipped is unchanged.
- mypy clean on `pdf.py`, `pipeline.py`, both test files.

**Self-review findings:**

- **Architectural coordination — Stage 3.5 pre-OCR exception (not in plan-doc):** the plan-doc's T3 spec didn't anticipate the Stage 3.5 / Stage 5.5 ordering gap. D15 makes sniff OCR-aware via the `_OCR_MARKER_PATTERN` regex, BUT pre-OCR an image-mode PDF has empty body so no markers exist for the regex to match. Without a separate exception, image-only PDFs would quarantine at Stage 3.5 before ever reaching the OCR pass, defeating the whole T3 feature. I added a check at the Stage 3.5 guard: when `extras["images"]` is non-empty, SKIP the sniff entirely (the OCR pass will fill the body downstream). The post-OCR body still benefits from D15's regex (e.g. for re-ingest scenarios where a body already carries `[Page N:` markers). This change is documented inline in the pipeline as "Plan 25 T3 PRE-OCR exception" + pinned by `test_image_mode_pdf_passes_content_sniff_pre_ocr`. Flag this in the lessons update for Plan 26: T2 + T3 had a sequencing dependency that wasn't visible until exec time.

- **Test #4 fixture choice — `insert_textbox` vs `insert_text`:** `fitz.Page.insert_text((50, 100), text)` truncates at the right margin without wrapping, so a 250-char prose body landed in the PDF as only ~110 chars of extracted text — flipping the test from "text path" to "image-mode" unexpectedly. Switched the fixture builder to `insert_textbox(page_rect, text, fontsize=10)` which wraps across the full page area. Documented in the fixture builder's docstring.

- **DPI verification (test #7) — patching `fitz.Page.get_pixmap`:** Used `unittest.mock.patch.object` to intercept the kwarg list. Considered inspecting `Pixmap.xres` / `yres` on the result PNG but `pix.tobytes("png")` returns bytes that don't reliably carry DPI metadata across platforms. Patching is cleaner + faster.

- **Cross-platform check:** `pymupdf` ships native binaries for macOS and Windows. `fitz.Page.get_pixmap(dpi=150)` + `pix.tobytes("png")` are stable across platforms. The PNG bytes returned by pymupdf are platform-independent (PNG spec is canonical). `pathlib.Path` for archive_root. No `shell=True`, no hardcoded separators.

- **Concern — `_PDF_RENDER_DPI` hardcoded vs configurable:** Per the spec's pre-task questions section, hardcoding 150 in a module constant for now is fine; promote to a `Config.handlers.pdf.render_dpi` field only when a real use case (e.g. high-density scanned legal docs needing 300 DPI for fidelity) demands it. Not a Plan 25 concern.

- **Concern — `ScannedPDFError` retained but unused:** the class is kept solely for import-compat with any external caller. It's not raised by `extract()` anymore. Plan 26 could either (a) deprecate + remove in a follow-up cleanup, or (b) keep indefinitely as a no-op alias. Documented in the class docstring.

**Commits (per D9, NOT pushed):**

- _SHA TBD_ — `feat(plan-25): T3 — PDFHandler image-mode + pipeline page_index OCR plumbing`
- _SHA TBD_ — `test(plan-25): T3 — PDF image-mode unit + integration tests`
- _SHA TBD_ — `docs(plan-25): T3 — outcome receipts`

## T4 outcome

**Status:** DONE.

**What landed:**

- `apps/brain_web/src/lib/state/bulk-store.ts` (+58 / -3 LOC) — added
  `BulkPhase` type (`idle | walking | applying | complete | error`),
  4 new state fields (`phase`, `walkPath`, `walkStartedAt`,
  `applyStartedAt`), and 2 new actions (`beginWalk`, `endWalk`).
  `pickFolder()` now also clears walk state on the success edge;
  `startApply()` stamps `applyStartedAt` + flips `phase = "applying"`;
  the apply-loop tail flips `phase = "complete"`.
- `apps/brain_web/src/components/bulk/walk-interstitial.tsx` (+82 LOC,
  new file) — Step 1 interstitial that renders while `phase === "walking"`.
  Spinner (Lucide `Loader2` + `animate-spin`), folder path
  (font-mono, truncated past 60 chars with leading ellipsis), helper
  text "This may take a moment for large folders.", and an elapsed-time
  counter that updates every 1s via `setInterval` (cleared on unmount
  or phase change). Wrapped in `role="status"` + `aria-live="polite"`
  for screen readers.
- `apps/brain_web/src/components/bulk/step-pick-folder.tsx` (+24 / -2
  LOC) — wired `beginWalk(path)` at the start of `runDryRun()` and
  `endWalk(false)` at both error paths (unexpected status, thrown
  exception). The picker UI hides behind an early-return when
  `phase === "walking"` so the user has a single focus point during
  the dry-run.
- `apps/brain_web/src/components/bulk/step-apply.tsx` (+38 / -3 LOC) —
  added `formatEta()` helper (Math.ceil((M-N) × 10 / 60) minutes;
  returns `null` below 60s to elide noise), added an `apply-headline`
  microcopy line that swaps "Importing N of M files" / "Done!" /
  "N of M applied" based on phase, and added an `apply-eta` line
  that surfaces "Estimated time remaining: ~Xm" while applying.
  Bumped the progress-bar fill class from `transition-[width]` to
  `transition-all duration-500` for smoother sweep.
- `apps/brain_web/tests/unit/bulk-wizard.test.tsx` (+170 LOC, new
  file) — 5 unit tests per plan-doc spec.

**Existing wizard structure (re-verified at exec time):**

- 4 step files in `apps/brain_web/src/components/bulk/`:
  `step-pick-folder.tsx`, `step-target-domain.tsx`, `step-dry-run.tsx`,
  `step-apply.tsx`, plus `bulk-screen.tsx` orchestrator + `stepper.tsx`.
- State store: `apps/brain_web/src/lib/state/bulk-store.ts` (zustand,
  Plan 07 Task 21 origin).
- Walk happens inside `step-pick-folder.tsx`'s `runDryRun()` callback;
  apply happens inside `bulk-store.startApply()`'s for-loop.

**Phase transition strategy:**

CSS transition-opacity on the WalkInterstitial container (`duration-200
ease-out`). No Radix dialog wrapping — per `feedback_axe_dialog_animation_wait.md`
(auto-memory) Radix dialogs hold mid-animation opacity that trips axe
color-contrast checks. Pure CSS opacity sidesteps the issue. The
phase gate itself (render `<WalkInterstitial />` vs `null` based on
`phase === "walking"`) is the source of truth; CSS transition just
softens the mount/unmount visual.

**Timer location:**

Walk-elapsed counter timer lives in the `<WalkInterstitial>` component
via `setInterval(1000)` inside a `React.useEffect` — bound to the
phase value, so the cleanup unmounts the interval when phase flips
back to idle. Apply phase uses NO timer — per the original code the
apply loop is JS-driven serial (one `await ingest()` per iteration),
so `applyIdx` reflects REAL progress already. The plan-doc's
"simulated progress via `setInterval` every 10s" framing assumed a
batched backend call; the actual implementation is per-file ingest,
which is strictly better UX (accurate count, not pseudo). I kept the
real progress and added an ETA derived from remaining file count.

**Microcopy strings (verbatim per plan-doc spec):**

- "Scanning folder..." (walk headline)
- "This may take a moment for large folders." (walk helper)
- "Importing N of M files" (apply headline, while applying)
- "Estimated time remaining: ~Xm" (apply ETA)
- "Done!" (apply headline on completion)

**Verification recipe (executed):**

- `pnpm vitest run --reporter=verbose tests/unit/bulk-wizard.test.tsx`
  → **5/5 PASS** (1.15s).
- `pnpm tsc --noEmit` → **clean** (zero errors).
- `pnpm vitest run` (full suite) → **87 files / 604 passed / 1 skipped**
  (zero regressions from the +4 new tests in T4).
- Bulk-adjacent suites (`bulk-store`, `bulk-apply`, `bulk-approve`) →
  **13/13 PASS** (no regressions from the store extension).

**RED-on-revert receipts (Plan 23 T2 pattern):**

- `git stash` of the 3 modified files (store + step-pick-folder +
  step-apply). New files (`walk-interstitial.tsx`, `bulk-wizard.test.tsx`)
  remained as untracked.
- Re-ran `pnpm vitest run tests/unit/bulk-wizard.test.tsx` → **2 FAILED**
  (`apply progress bar shows 'Importing N of M files'` + `apply ETA
  shows 'Estimated time remaining: ~Xm'`). Both depend on the
  reverted `step-apply.tsx` edits. Failure mode: `getByTestId("apply-headline")`
  → "Unable to find element with testId" + same for "apply-eta".
- Re-ran `pnpm tsc --noEmit` → **9 errors** (all variants of
  `Property 'phase' does not exist on type 'BulkState'`) — confirms
  the store edits pin both the test stubs AND the WalkInterstitial
  consumer.
- `git stash pop` → restored; re-ran vitest + tsc → **5/5 PASS** /
  **0 errors**.

**Self-review findings:**

- **Plan-doc "simulated progress" framing — diverged intentionally.**
  The plan-doc spec (D11) called for `setInterval`-driven pseudo-progress
  for the apply phase ("N starts at 0 and increments via a timer at
  ~10s per file"). I diverged from that because the existing apply
  loop is JS-driven serial — `applyIdx` already reflects REAL per-file
  progress as each `await ingest()` resolves. Simulating progress
  on top of real progress would be strictly worse UX (potentially lying
  to the user — e.g. if the backend hangs, the simulated counter
  would still march forward). The plan-doc assumed a batched backend
  call; the reality is per-file JS-driven. Test #5 (`walk elapsed
  counter advances when timers tick`) adapts the fake-timers contract
  to the walk phase, where the backend truly doesn't stream — and so
  timer-driven UI is the only option. The other 4 tests cover the
  same surface area the plan-doc asked for, just landed against real
  progress + ETA instead of simulated progress. Flag for Plan 26: if
  the user wants a "smooth progress sweep" UX (animation between
  per-file ticks), that's a separate decoration on top of real
  progress, not a replacement for it.

- **`endWalk(false)` on success path — not strictly needed.** The
  current code calls `endWalk(false)` only on error edges; the success
  edge goes through `pickFolder()` which clears walk state directly.
  I considered adding `endWalk(true)` symmetrically but it's dead
  code in the current flow. Left a comment in the store noting
  `endWalk(true)` is defensive coverage for callers that don't reach
  `pickFolder()` (none today). Plan 26 cleanup: collapse the two
  paths.

- **Truncation heuristic — 60-char max, leading ellipsis.** Long
  folder paths like `/Users/chrisjohnson/Documents/old-vault/2026/research/AI/...`
  exceed the 60-char width of the mono-font display at default font
  size. I picked leading ellipsis (show the leaf folder) over trailing
  ellipsis (show the prefix) because the leaf is the more useful
  bit when scanning a folder you JUST picked. The full path lives in
  the `title` attribute for hover. Adjustable if user feedback
  contradicts.

- **No mockup gate per D5.** Confirmed: animation polish on the
  existing wizard, no new screens. The interstitial visual style
  (rounded surface, hairline border, accent-colored spinner) reuses
  Plan 22's component vocabulary (same `var(--accent)`, `var(--text-muted)`,
  `var(--hairline)` tokens already in use across the bulk wizard).

- **A11y check.** WalkInterstitial uses `role="status"` +
  `aria-live="polite"` for screen-reader announcement; spinner is
  marked `aria-hidden="true"` (it's decorative; the headline conveys
  the same info). Progress bar `role="progressbar"` was already in
  step-apply.tsx — I left it untouched. The new `apply-headline`
  text is not redundant with the progress bar (the bar shows
  percentage; the headline shows count) so no double-announcement
  risk.

- **Cross-platform.** No POSIX-only APIs. `setInterval` / `clearInterval`
  / `Date.now()` are all DOM/JS spec — work identically on
  Safari/Chrome/Edge across macOS + Windows. `pathlib`-style
  separators preserved in the displayed path (the backend's path
  string is rendered verbatim; we never split or join on `/` or `\`).

**Commits (per D9, NOT pushed):**

- _SHA TBD_ — `feat(plan-25): T4 — bulk-import wizard interstitial animations (walk / apply phases)`
- _SHA TBD_ — `test(plan-25): T4 — unit tests for phase rendering + simulated progress`
- _SHA TBD_ — `docs(plan-25): T4 — outcome receipts`

## Plan 26 candidate scope

Filled in at T5 closure. **30 items total** — 4 NEW Plan-25-surfaced + 6 Plan-24-surfaced (unchanged) + 16 Plan 22 carry-forwards (unchanged through Plans 23 / 24 / 25) + 4 preserved NOT-DOING carry-forwards. See `tasks/todo.md` tail block for the full grouped list.

**4 NEW Plan-25-surfaced candidates:**

1. **CRITICAL/correctness:** Plan 24 `ClassifyOutput.source_type` `Literal["text", "url", "pdf", "email", "transcript", "tweet"]` does NOT include `docx` or `pptx` literals. Pre-existing Plan 24 gap surfaced at Plan 25 T2 when the pipeline-integration test `test_pipeline_passes_short_pptx_with_ocr_marker` had to bypass classify via `domain_override`. Plan 24 added the `SourceType` enum members + handlers + frontmatter support but didn't extend the classify prompt's output schema. Fix: one-line schema change + 2-3 test fixture updates.
2. **Cleanup:** `ScannedPDFError` empty alias retained as a `HandlerError` subclass for backward-compat imports after T3 stopped raising it. Plan 26 could (a) deprecate + remove if no external consumers surface, or (b) keep indefinitely as a no-op alias. T3 cleanup concern.
3. **UX polish:** Real WebSocket-based walk-phase progress streaming. Plan 25 T4 ships timer-based pseudo-progress for the walk phase because the backend `BulkImporter.plan()` returns one-shot, no streaming. Apply phase already has REAL progress. Plan 5 set up WebSocket chat infrastructure; extending to bulk-progress would give the walk phase real file counts.
4. **UX polish:** Per-file filename display in apply-phase progress UI. Plan-doc T4 spec called for "Current: <filename>" microcopy below the apply progress bar; T4 implementer's `applyIdx`-driven progress already shows accurate count + ETA but the current filename surface was deferred. Add `currentFile` field to bulk-store + thread the filename from the `startApply()` for-loop into it before each `await ingest()`.

## Review

**Tag:** `plan-25-bulk-import-quality` cut locally on green demo (lightweight `commit` type per project convention; NOT pushed per D9 — controller surfaces to user for push authorization).

**Closure summary.** Plan 25 closes the four bulk-import quality issues the user surfaced after hands-on use of Plan 22 + Plan 24, plus the T3 PDF image-mode addition that grew during brainstorm. Total: 5 substantive tasks + 1 closure = 6 work units. Scope locks held: A (all 5 items as one focused plan), 2.A (backend pre-filter at walk stage), 4.A (standard 200/80/40 sniff thresholds), PDF trigger heuristic-based, D15 OCR-aware sniff exception. Zero new dependencies; zero schema changes; four spec text edits across §5 (stages list + bulk-import footnote + pdf handler row + failure-handling consistency bullet).

**Test count bumps:**

- brain_core: 1234 (Plan 24 close) → **1269** + 5 skipped (+35 across T1 / T2 / T3).
- brain_web vitest: 599 (Plan 24 close) → **604** + 1 skipped (+5 across T4).
- tsc --noEmit: clean across `apps/brain_web/`.

**Verification receipts (per task):**

- T0: spec edits + internal-consistency check (no contradictions with §3 / §4 / §10 / Watched folders subsections).
- T1: 12 new walk-filter tests; brain_core 1234 → 1241 + 5 skipped (+12, -1 adjusted fixture).
- T2: 17 new sniff tests (12 helper + 1 set-membership pin + 4 pipeline-integration); brain_core 1241 → 1258 + 5 skipped (+17); 17 distinct existing tests across 7 files adjusted for 200-char floor.
- T3: 10 new PDF image-mode tests + 1 new `test_handler_pdf.py` pin; brain_core 1258 → 1269 + 5 skipped (+11).
- T4: 5 new vitest tests; brain_web 599 → 604 + 1 skipped (+5); tsc --noEmit clean; RED-on-revert receipts captured.
- T5 (closure): 14-gate demo `scripts/demo-plan-25.py` prints `PLAN 25 DEMO OK`.

**Notable execution-time discoveries:**

1. **T2/T3 sequencing dependency** — Stage 3.5 sniff (T2) would have quarantined image-mode PDFs (T3) BEFORE Stage 5.5 OCR ran, because pre-OCR the body is empty and D15's marker regex can't fire. T3 implementer caught this at exec time and added a PRE-OCR exception: skip Stage 3.5 when `extras["images"]` is non-empty. Lesson captured in `tasks/lessons.md` Plan 25 closure section as the T3 NEW lesson on cross-stage feature ordering.
2. **T4 plan-doc D11 divergence** — plan-doc specified timer-driven pseudo-progress for apply phase; implementer caught at exec time that existing apply loop is JS-driven serial so `applyIdx` already reflects REAL progress. Simulating on top would be strictly worse UX. Kept real progress for apply; used timer-based pseudo-progress ONLY for walk phase. Documented in T4 outcome receipt + lessons.md.
3. **Plan 24 `ClassifyOutput.source_type` Literal gap** — pre-existing Plan 24 schema gap surfaced at Plan 25 T2 implementer review. Not a Plan 25 blocker; flagged as the critical Plan 26 candidate.

**Spec text changes:**

- §5 Stages list: new `3.5 Content sniff` entry between Extract (3) and Archive (4); D15 OCR-aware exception documented.
- §5 Bulk import: new `Walk-stage filtering` footnote with system-file denylist + unsupported-type pre-filter bullets.
- §5 Day-one handlers table: pdf row replaced pre-Plan-25 `needs_ocr, skipped` with T3 image-mode rendering (`vision_extract` + `[Page N: <text>]` + D14 <200 chars trigger).
- §5 Failure handling (bonus consistency edit): bifurcated PDF-vs-text-shaped behavior — PDFs <200 chars trigger T3 image-mode (no skip); text-shaped sources <200 chars fall through to 3.5 Content sniff quarantine.

**Files changed (summary):**

- `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` — 4 edits (T0).
- `packages/brain_core/src/brain_core/ingest/bulk.py` — `_SYSTEM_FILES` + `_VALID_EXTENSIONS` + `_is_system_file` + 3 walk-loop filter checks (T1, +101 LOC).
- `packages/brain_core/src/brain_core/ingest/pipeline.py` — Stage 3.5 sniff + `_OCR_MARKER_PATTERN` + `_TEXT_SHAPED_SOURCE_TYPES` + `_looks_like_meaningful_text` + `_quarantine_content_sniff` (T2, +202 LOC); `_ocr_images` page_index branch + Stage 3.5 PRE-OCR exception (T3, +24 / -7 LOC).
- `packages/brain_core/src/brain_core/ingest/handlers/pdf.py` — image-mode rewrite (T3, +99 / -25 LOC net).
- `packages/brain_core/tests/ingest/test_bulk_walk_filtering.py` — NEW (T1, 290 LOC, 12 tests).
- `packages/brain_core/tests/ingest/test_pipeline_content_sniff.py` — NEW (T2, 370 LOC, 17 tests).
- `packages/brain_core/tests/ingest/handlers/test_pdf_image_mode.py` — NEW (T3, 393 LOC, 10 tests).
- `apps/brain_web/src/components/bulk/walk-interstitial.tsx` — NEW (T4, 82 LOC).
- `apps/brain_web/src/components/bulk/step-pick-folder.tsx` — `beginWalk`/`endWalk` wiring (T4, +24 / -2 LOC).
- `apps/brain_web/src/components/bulk/step-apply.tsx` — apply-headline + apply-eta microcopy (T4, +38 / -3 LOC).
- `apps/brain_web/src/lib/state/bulk-store.ts` — `BulkPhase` + 4 fields + 2 actions (T4, +58 / -3 LOC).
- `apps/brain_web/tests/unit/bulk-wizard.test.tsx` — NEW (T4, 170 LOC, 5 tests).
- `scripts/demo-plan-25.py` — NEW (T5 closure, 14 gates).
- `tasks/lessons.md` — Plan 25 closure section appended.
- `tasks/todo.md` — row 25 ✅ + Plan 26 candidate scope tail refreshed.
- `tasks/plans/25-bulk-import-quality.md` — outcome receipts T0-T4 + this Review section.

**Backlog forward.** 30-item Plan 26 candidate scope queued (4 Plan-25-surfaced + 6 Plan-24-surfaced + 16 Plan 22 + 4 preserved NOT-DOING). Critical item (Plan 24 `ClassifyOutput.source_type` Literal gap) flagged for early-priority adjudication at Plan 26 brainstorm.

---

**End of Plan 25.**
