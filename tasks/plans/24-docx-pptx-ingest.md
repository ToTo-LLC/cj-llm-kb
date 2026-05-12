# Plan 24 — DOCX + PPTX ingest with Claude Vision OCR

**Authored:** 2026-05-12 (post Plan 23 close on 2026-05-12, tag
`plan-23-watched-folders-hotfix-ux` at `8c17290`).
**Scope:** Add ingest support for generic Microsoft Word (.docx) and
PowerPoint (.pptx) files. Both formats get embedded-image OCR via
Claude Vision (always-on per user choice) so chart screenshots,
diagrams, and image-only slides become searchable knowledge. Per
user scope locks: **C = MVP + image OCR**; **2.A = explicit `docx` +
`pptx` SourceType values**; **3.A = keep existing TranscriptDOCXHandler;
new DocxHandler is the fall-through**; **Claude Vision via
LLMProvider.vision_extract abstraction**; **always-OCR embedded
images**.
**Shape:** 6 substantive tasks + 1 closure = 7 total. Mirrors Plan 22
"new-feature" shape, smaller (Plan 22 was 19 + 3 mini-fixes; Plan 24
is bounded to docx/pptx + OCR seam).

## At a glance

- **Theme A — Foundation** (T0): spec update §5 (handlers table +
  OCR rules) + new `docx` + `pptx` SourceType enum values + §10
  safety rail bullet for vision-call budget metering. T1+ implement
  against the locked spec.
- **Theme B — Per-format handlers** (T1, T2):
  - **T1** DocxHandler — generic Word document handler (lower priority
    than TranscriptDOCXHandler per D-locked 3.A). Extract paragraphs
    + headings + tables as markdown; collect `inline_shapes` images
    for T4 OCR wiring. Uses existing `python-docx` dep.
  - **T2** PptxHandler — PowerPoint slide deck handler. Extract slide
    titles + bullet text + speaker notes + per-slide images. Adds
    `python-pptx>=0.6` dep.
- **Theme C — Vision OCR** (T3, T4):
  - **T3** `LLMProvider.vision_extract(image_bytes, prompt)` method
    added to the base abstraction; AnthropicProvider implements via
    existing API image content blocks. New `ocr` operation type in
    cost ledger. `PerDomainBudgetGuard` integration so vision calls
    are metered the same as classify/summarize/integrate. Per
    CLAUDE.md non-negotiable #4 (LLMProvider abstraction) — OCR MUST
    go through LLMProvider, not anthropic SDK directly.
  - **T4** Wire `vision_extract` into DocxHandler + PptxHandler:
    every embedded image is OCR'd; extracted text inlined into the
    note body as `[Image: <ocr-text>]` blocks. Integration tests
    using FakeLLMProvider with canned vision responses.
- **Theme D — Frontend** (T5): drop-zone accept list extension (add
  `.docx` + `.pptx`); Inbox row icon mapping for the new SourceTypes.
  Minimal UI surface — no new screens; no mockup gate.
- **Closure** (T6): demo + lessons + todo + tag.

## Why this plan exists (1 paragraph)

Today's ingest pipeline supports text, URLs, PDF, email, transcripts
(via stem conventions), and tweets. Generic Microsoft Office files —
the dominant document format for work + research — are NOT supported:
non-transcript `.docx` files fail dispatch; `.pptx` files have no
handler at all. Users with research vaults that include conference
slide decks, internal reports, and meeting notes can't ingest them
without first converting to PDF or plain text. Plan 24 closes that
gap directly: add per-format handlers using mature pure-Python
libraries (python-docx already a project dep; python-pptx is a small
new addition). The OCR addition (Claude Vision through the
LLMProvider abstraction) captures content from chart screenshots,
infographics, and image-only slides — content that would otherwise
land in the vault as "[image]" placeholders and become invisible to
search. The cost rail is reused: existing `PerDomainBudgetGuard` +
`costs.sqlite` ledger meter vision calls the same way they meter
classify/summarize/integrate, so a runaway image-heavy slide deck
trips the same budget caps as any other operation.

## Locked decisions

| # | Decision | Status | Why |
|---|---|---|---|
| D1 | **Scope = C MVP + image OCR.** Plan ships per-format handlers AND Claude Vision OCR for embedded images. NOT image-only OCR (option A) — user chose always-OCR-embedded-images (B in the OCR-trigger question). | locked (user C + B) | OCR-on-every-image captures chart screenshots + infographic content in text-rich slide decks. Cost is bounded by existing per-domain budget rail; runaway image-heavy ingests trip the same cap as runaway classify storms. |
| D2 | **SourceType expansion = 2.A explicit `docx` + `pptx` values.** Each gets its own enum entry. Frontmatter `source_type` shows `docx` or `pptx`. | locked (user 2.A) | Matches existing per-format granularity (pdf, email, transcript, tweet are distinct). Enables future per-format queries / per-format prompts. |
| D3 | **TranscriptDOCXHandler interaction = 3.A keep + fall-through.** TranscriptDOCXHandler stays first in dispatcher (claims transcript-stem `.docx`). DocxHandler is registered LATER so it claims all OTHER `.docx` files. | locked (user 3.A) | Backwards-compat with existing transcript workflows. Transcript .docx (e.g., `interview-2024-05.docx`) → `transcript` SourceType + transcript-specific stripping; generic .docx (e.g., `Q4-strategy.docx`) → `docx` SourceType + general extraction. |
| D4 | **OCR provider = Claude Vision via LLMProvider.** Add `vision_extract(image_bytes, prompt)` method to base abstraction; AnthropicProvider implements via Anthropic API's image content blocks. No new deps. | locked (user A) | Per CLAUDE.md non-negotiable #4 — LLM-touching code MUST go through LLMProvider. No native install (vs Tesseract). Cost metered cleanly through existing budget rail. ~$0.003/image. |
| D5 | **OCR trigger = always-OCR embedded images.** Every image in a docx or pptx is sent to vision_extract regardless of how text-rich the doc is. | locked (user B) | Captures chart-screenshot text in slides with both bullets AND infographics. Cost-bounded by existing per-domain budget cap. User explicitly chose this over image-only-OCR. |
| D6 | **New `ocr` operation type in cost ledger.** `costs.sqlite` rows for vision calls carry `op="ocr"` so users can audit OCR spend separately from classify/summarize/integrate. | locked at authoring | Distinguishing OCR from other LLM ops in the cost view is the only way users can answer "how much am I spending on image OCR specifically?" Adds one new operation type to the existing ledger. |
| D7 | **No new UI screens; minimal frontend surface (T5).** Drop-zone accept list extension + Inbox row icons only. NO mockup gate required (per Plan 21/23 small-frontend precedent). | locked at authoring | The new SourceTypes flow through existing UI surfaces. Inbox row + Browse page + chat-context-pill all already handle multiple SourceTypes; adding two more values is a token-driven change, not a new design surface. |
| D8 | **Push at Plan 24 close after user authorization.** Single `git push origin main` covers all Plan 24 commits; explicit `git push origin <tag>` for the lightweight tag. | locked per Plan 20-23 D-precedent | Standard cadence held across five prior plans. |
| D9 | **Combined spec + code-quality review per task.** | locked per Plan 19-23 D-precedent | Held across eight prior plans. |
| D10 | **Sequential subagent dispatch via subagent-driven-development.** | locked per Plan 19-23 D-precedent | T0 (brain-core) → T1 (brain-core) → T2 (brain-core) → T3 (brain-core) → T4 (brain-core) → T5 (brain-frontend) → T6 (brain-core closure). |
| D11 | **Pause cadence: every ~3 tasks.** 7-task plan = pause after T3 (Claude Vision LLMProvider abstraction landed) + T6 plan-close. | locked at authoring | Plan 22 pause cadence (every ~5) was for 18+ tasks. Plan 24 is 7 tasks → pauses at T3 + T6 give one mid-plan + plan-close checkpoint. |
| D12 | **New dependency: `python-pptx>=0.6`.** Pure Python, MIT-licensed, well-maintained. Added to root `pyproject.toml` workspace deps OR `brain_core` pyproject deps (verify at exec time). | locked per user C scope acceptance | First new pip dep since Plan 16 added watchdog. Documented in T2 outcome receipt. |
| D13 | **Plan 25 candidate scope = remaining 16 Plan 22 carry-forwards** (unchanged from Plan 23 closure tail). Plus any Plan 24-surfaced candidates. | locked at authoring | Plan 24 is orthogonal to the Plan 22 carry-forward queue (different subsystem). |

## Tech stack

Same as Plans 16-23 PLUS one new dep:
- Python 3.12, pydantic v2, mypy --strict, ruff, structlog
- `python-docx` (existing — TranscriptDOCXHandler)
- **NEW: `python-pptx>=0.6`** (T2)
- Claude Vision via existing `anthropic` SDK (no new dep — the
  vision API is part of the existing chat API surface)
- vitest, Playwright (frontend unchanged)
- CI runs on macos-14 + windows-2022 per Plan 14's matrix

## Demo gate description

`scripts/demo-plan-24.py` asserts, in sequence (~10-12 gates):

1. **(T0.a)** Spec file `§5 Day-one handlers` table contains rows for
   `docx` + `pptx` (regex match for the format names + library refs).
2. **(T0.b)** Spec §5 contains a new "Image OCR rules" subsection
   describing always-OCR-embedded-images behavior + cost-ledger
   `ocr` operation type.
3. **(T0.c)** Spec §10 has a new bullet for vision-call budget
   metering through `PerDomainBudgetGuard`.
4. **(T0.d)** `SourceType` enum in `brain_core.ingest.types` has new
   values `DOCX = "docx"` + `PPTX = "pptx"` (Pydantic introspection
   check).
5. **(T1)** `packages/brain_core/src/brain_core/ingest/handlers/docx.py`
   exists with `DocxHandler` class (NOT the transcript handler);
   `dispatcher._default_handlers()` registers it AFTER
   TranscriptDOCXHandler.
6. **(T2.a)** `packages/brain_core/src/brain_core/ingest/handlers/pptx.py`
   exists with `PptxHandler` class.
7. **(T2.b)** `python-pptx>=0.6` declared in `pyproject.toml`
   (project root or brain_core — verify at exec time).
8. **(T3.a)** `LLMProvider` base class has `vision_extract` abstract
   method (`inspect.signature` check); `AnthropicProvider` implements
   it.
9. **(T3.b)** `costs.sqlite` schema accepts `op="ocr"` rows
   (introspect the ledger writer or its test).
10. **(T4)** DocxHandler + PptxHandler both call `vision_extract` for
    embedded images during extraction (regex match on the handler
    bodies).
11. **(T5)** `apps/brain_web/src/lib/state/inbox-store.ts` (or
    equivalent — verify at exec time) drop-zone accept list includes
    `.docx` + `.pptx`; Inbox row icon mapping covers both new
    SourceTypes.
12. **(T6)** `tasks/todo.md` row 24 marked ✅; `tasks/lessons.md` has
    Plan 24 closure section; final stdout line `PLAN 24 DEMO OK`.

## Tasks

### Theme A — Foundation

#### T0 — Spec + SourceType + cost-ledger schema

**Files:**
- Modify: `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` —
  §5 handlers table (add 2 rows); §5 new "Image OCR rules"
  subsection; §10 vision-call budget metering bullet.
- Modify: `packages/brain_core/src/brain_core/ingest/types.py` — add
  `DOCX = "docx"` + `PPTX = "pptx"` to `SourceType` enum.
- Create: `packages/brain_core/tests/ingest/test_source_type_pin.py`
  (or extend existing) — Pydantic introspection pin for the
  expanded SourceType enum.

**Goal:** Lock the spec contract + schema before any handler code lands.

**What to do:**
1. **Spec §5 handlers table:** read the existing table around line
   ~230 (it has rows for text/url/pdf/email/transcript/tweet). Add
   two rows:
   ```
   | docx | `python-docx` (existing) | generic Word document; tables → markdown; embedded images OCR'd via Claude Vision; needs_ocr flag if extraction below threshold |
   | pptx | `python-pptx>=0.6` (NEW) | slide deck; titles + bullets + speaker notes; every slide image OCR'd via Claude Vision |
   ```
2. **Spec §5 new subsection:** after the handlers table + before
   "Bulk import", add a new subsection "**Image OCR rules**":
   ```
   For .docx and .pptx ingest, every embedded image is sent through
   `LLMProvider.vision_extract` (Plan 24 D4). Extracted text is
   inlined into the note body as `[Image: <text>]` blocks. The
   vision call is metered through `PerDomainBudgetGuard` with
   `op="ocr"` in the cost ledger. Image-heavy docs that exhaust the
   per-domain budget pause mid-ingest; user raises the cap and
   resumes. OCR provider is Anthropic (Claude Vision) via the
   existing LLMProvider abstraction per CLAUDE.md non-negotiable #4
   — no new SDK dependency; the vision API uses the existing
   anthropic SDK's image content blocks.
   ```
3. **Spec §10 safety rails bullet:** after the watched-folders bullet
   (from Plan 22 T0), add:
   ```
   - **Vision OCR cost metering**: every `LLMProvider.vision_extract`
     call records an `op="ocr"` row in `costs.sqlite`. The same
     `PerDomainBudgetGuard.check_for(domain, config)` gate that
     fires for classify/summarize/integrate also fires for OCR.
     Image-heavy `.docx` or `.pptx` ingests that would exceed the
     per-domain budget cap are paused before vision spend, mirroring
     the bulk_import pre-check pattern.
   ```
4. **SourceType enum:** read `packages/brain_core/src/brain_core/ingest/types.py`
   (Plan 22 T0 already added handler enum); add `DOCX = "docx"` +
   `PPTX = "pptx"`. Order: insert after `TRANSCRIPT` but before
   `TWEET` so the enum reads roughly format-grouped.
5. **Pin test:** field-set strict equality for the SourceType enum
   members:
   ```python
   assert set(SourceType.__members__.keys()) == {
       "TEXT", "URL", "PDF", "EMAIL", "TRANSCRIPT", "TWEET", "DOCX", "PPTX"
   }
   ```

**Per-task review:** combined. Reviewer confirms (a) spec edits land
in the 3 cited locations (regex match on each); (b) no internal
spec contradictions (especially §3 Domain separation + §10 scope_guard
discussion — vision calls go through the same scope-guarded paths);
(c) SourceType pin test fails RED if any enum member is added,
removed, or renamed; (d) no code outside spec + enum touched.

### Theme B — Per-format handlers

#### T1 — DocxHandler (generic Word document)

**Files:**
- Create: `packages/brain_core/src/brain_core/ingest/handlers/docx.py`
  — `DocxHandler` class implementing `SourceHandler` Protocol.
- Modify: `packages/brain_core/src/brain_core/ingest/dispatcher.py` —
  register DocxHandler in `_default_handlers()` AFTER
  TranscriptDOCXHandler (so transcript-stem .docx still routes to
  the transcript handler per D3).
- Create: `packages/brain_core/tests/ingest/handlers/test_docx.py`
  — unit tests with fixture .docx files (use `python-docx` to
  construct test fixtures at runtime; do NOT commit binary .docx
  files to the repo unless needed for a specific shape test).

**Goal:** Generic .docx files (NOT transcript-stem) extract cleanly
via `python-docx` and flow through the existing 9-stage pipeline.

**What to do:**
1. **Read TranscriptDOCXHandler** at
   `packages/brain_core/src/brain_core/ingest/handlers/transcript_docx.py`
   for the pattern. Mirror its shape: `source_type` class attribute,
   `can_handle()` predicate, `extract()` method returning
   `ExtractedSource`.
2. **`can_handle()` for DocxHandler:** claim any `.docx` file that
   does NOT match transcript-stem conventions. The transcript handler
   already claims those; DocxHandler is the fall-through, so
   `can_handle` can simply check the suffix is `.docx` (the
   dispatcher walks handlers in order; TranscriptDOCXHandler claims
   first if applicable).
3. **`extract()`:**
   - Open the `.docx` with `python-docx.Document(path)`.
   - Iterate paragraphs; emit each as a markdown paragraph.
   - Handle headings: `python-docx` paragraph styles (`Heading 1`,
     `Heading 2`, etc.) → markdown `#`, `##`, etc.
   - Handle tables: iterate `doc.tables`; emit as GFM markdown table.
   - Collect images via `doc.inline_shapes`: store as
     `(image_blob, content_type)` tuples in `ExtractedSource.extras`
     under key `images` for T4's OCR pass.
   - `title`: first `Heading 1` content, or first paragraph if no
     heading.
   - `source_type=SourceType.DOCX`.
   - Other ExtractedSource fields: `author=None`, `published=None`,
     `source_url=None`.
4. **Dispatcher registration:** insert DocxHandler after
   TranscriptDOCXHandler in `_default_handlers()`.
5. **Unit tests:**
   - `test_dispatcher_claims_generic_docx_not_transcript_stem` —
     verify dispatcher routes a non-transcript .docx to DocxHandler.
   - `test_dispatcher_routes_transcript_docx_first` — verify
     `interview-2024-05.docx` (or whatever transcript-stem pattern)
     still goes to TranscriptDOCXHandler.
   - `test_extract_headings_to_markdown` — fixture .docx with H1/H2/H3;
     verify output markdown has `#`/`##`/`###`.
   - `test_extract_paragraphs_preserved` — plain paragraphs.
   - `test_extract_tables_to_gfm_markdown` — 2x2 table fixture.
   - `test_extract_collects_inline_images` — fixture with 1 inline
     image; verify `extras["images"]` has 1 entry.
   - `test_extract_empty_docx` — empty doc; verify `body_text == ""`,
     `extras["images"] == []`.

**Per-task review:** combined. Reviewer confirms (a) DocxHandler is
registered AFTER TranscriptDOCXHandler in `_default_handlers()`
(verifying D3); (b) generic .docx dispatched correctly; (c) heading
+ table + image extraction tests pass; (d) extras["images"] structure
matches what T4's OCR wiring will consume.

#### T2 — PptxHandler + python-pptx dep

**Files:**
- Modify: `pyproject.toml` (root workspace OR brain_core's per
  package convention — verify at exec time) — add
  `python-pptx>=0.6` to dependencies.
- Create: `packages/brain_core/src/brain_core/ingest/handlers/pptx.py`
  — `PptxHandler` class.
- Modify: `packages/brain_core/src/brain_core/ingest/dispatcher.py` —
  register PptxHandler (insertion point: after PDFHandler, before
  EmailHandler — pptx is more specific than email/text catch-alls).
- Create: `packages/brain_core/tests/ingest/handlers/test_pptx.py`.

**Goal:** PPTX files extract slide content + speaker notes; embedded
images collected for T4 OCR.

**What to do:**
1. **Add the dep:** `python-pptx>=0.6` in `pyproject.toml`. Run
   `uv lock` if needed.
2. **`can_handle()`:** claim files with suffix `.pptx`. (Don't worry
   about transcript-stem variants — pptx transcripts aren't a
   recognized shape; all .pptx go to PptxHandler.)
3. **`extract()`:**
   - Open the `.pptx` with `pptx.Presentation(path)`.
   - Iterate `pres.slides`:
     - For each slide, emit a markdown section:
       ```
       ## Slide N: <title>
       <bullet points joined as markdown list>

       **Speaker notes:**
       <speaker notes paragraph>
       ```
     - Slide title: `slide.shapes.title.text` (if present).
     - Bullets: walk `slide.placeholders` / `slide.shapes` for
       text-bearing shapes; preserve indent level as nested markdown
       list.
     - Speaker notes: `slide.notes_slide.notes_text_frame.text`.
     - Images: walk `slide.shapes` filtering by `MSO_SHAPE_TYPE.PICTURE`;
       store as `(image_blob, content_type, slide_index)` tuples in
       `ExtractedSource.extras["images"]`.
   - `title`: presentation title from `pres.core_properties.title`
     OR first slide title.
   - `source_type=SourceType.PPTX`.
4. **Dispatcher registration:** insert PptxHandler after PDFHandler
   in `_default_handlers()`.
5. **Unit tests** — similar shape to T1:
   - `test_extract_slides_to_markdown_sections` — 3-slide fixture.
   - `test_extract_speaker_notes` — slide with notes.
   - `test_extract_collects_slide_images` — slide with 1 image.
   - `test_extract_handles_image_only_slide` — slide with no text,
     1 image; verify text body is empty and extras["images"] has the
     image.
   - `test_extract_handles_missing_title` — first slide has no
     title placeholder; verify graceful fallback.

**Per-task review:** combined. Reviewer confirms (a) `python-pptx`
in pyproject; (b) dispatcher registers PptxHandler in the right
position; (c) speaker notes captured; (d) image extras structure
matches T4 consumer.

### Theme C — Vision OCR

#### T3 — `LLMProvider.vision_extract` + AnthropicProvider impl + cost ledger

**Files:**
- Modify: `packages/brain_core/src/brain_core/llm/__init__.py` (or
  the LLMProvider base file — verify location) — add abstract
  method `vision_extract(image_bytes: bytes, prompt: str,
  content_type: str) -> str`.
- Modify: `packages/brain_core/src/brain_core/llm/providers/anthropic.py`
  — implement `vision_extract` using the Anthropic API's image
  content block format.
- Modify: `packages/brain_core/src/brain_core/cost/ledger.py` (or
  equivalent — verify) — accept `op="ocr"` as a valid operation
  type alongside the existing operations.
- Modify: `packages/brain_core/src/brain_core/budget/per_domain.py`
  (or equivalent) — `PerDomainBudgetGuard.check_for` already gates
  by `domain`; T3 just adds a new operation type. If the guard
  tracks per-operation spend separately, extend it; if it tracks
  total domain spend only, no schema change needed.
- Create: `packages/brain_core/tests/llm/test_vision_extract.py` —
  unit tests using `FakeLLMProvider` (extend it with a vision-mock
  implementation).
- Create: `packages/brain_core/tests/cost/test_ocr_op_ledger.py`
  (or extend existing) — pin that `op="ocr"` rows write correctly
  to `costs.sqlite`.

**Goal:** Vision OCR available through LLMProvider abstraction per
CLAUDE.md non-negotiable #4. Cost rail integrated.

**What to do:**
1. **Base class method:**
   ```python
   @abstractmethod
   async def vision_extract(
       self,
       image_bytes: bytes,
       prompt: str,
       *,
       content_type: str = "image/png",
       model: str | None = None,
   ) -> tuple[str, int, int]:  # (extracted_text, input_tokens, output_tokens)
       """Extract text from an image via vision LLM.
       
       Returns (text, input_tokens, output_tokens) so the caller can
       record the cost via the ledger. Default prompt should yield
       text-only output ("Extract any text visible in this image. Return only the text.").
       """
   ```
2. **Anthropic implementation:** uses the existing `anthropic` SDK's
   `Message.create` with content blocks. Image block format:
   `{"type": "image", "source": {"type": "base64", "media_type": content_type, "data": base64_data}}`.
   Followed by text block with the prompt.
   Returns the assistant's response text + the usage object's
   input/output token counts.
3. **Cost ledger:** ensure `op="ocr"` is a valid value (no schema
   change needed if the ledger accepts arbitrary op strings; if it's
   an enum, extend). Each vision call writes a row with the
   token counts + computed cost.
4. **PerDomainBudgetGuard:** existing `check_for(domain, config)`
   gates by total domain spend; vision calls count against the same
   per-domain budget. No new guard needed unless we want per-op caps
   (out of scope for v1; defer).
5. **FakeLLMProvider extension:** add a `vision_extract_responses:
   list[str]` queue + matching consumption logic (mirroring how
   classify/summarize/integrate responses are queued for testing).
6. **Tests:**
   - `test_vision_extract_returns_text` — FakeLLMProvider returns
     queued response.
   - `test_vision_extract_records_cost_row` — verify a `op="ocr"`
     row written to ledger with correct tokens.
   - `test_vision_extract_respects_per_domain_budget` — set tight
     budget; verify vision call refused after budget exhausted.
   - `test_vision_extract_uses_content_type` — base64 encoding +
     media_type plumbing verified.

**Per-task review:** combined. Reviewer confirms (a) `vision_extract`
is on the LLMProvider abstract base (NOT just AnthropicProvider);
(b) AnthropicProvider's implementation uses the existing anthropic
SDK + correct image-content-block format; (c) `op="ocr"` rows write
to costs.sqlite correctly; (d) per-domain budget rail gates vision
calls.

#### T4 — Wire OCR into DocxHandler + PptxHandler

**Files:**
- Modify: `packages/brain_core/src/brain_core/ingest/pipeline.py` (or
  the per-handler post-extract integration point — verify at exec
  time) — after a handler's `extract()` returns `ExtractedSource`,
  if `extras["images"]` is non-empty, run OCR on each via
  `LLMProvider.vision_extract` and inline the extracted text into
  `body_text` as `[Image: <text>]` blocks.
- Modify: T1's `docx.py` and T2's `pptx.py` if changes are needed in
  the handlers themselves (e.g., placeholder markers where OCR text
  goes vs appending at end).
- Create: `packages/brain_core/tests/ingest/handlers/test_docx_ocr_integration.py`
  + `test_pptx_ocr_integration.py` — integration tests using
  FakeLLMProvider with canned vision responses.

**Goal:** OCR'd image text flows into the note body alongside the
extracted document text.

**What to do:**
1. **OCR pass design.** Two options:
   - **A (recommended):** the pipeline (post-extract, pre-summarize
     stage) checks `extras["images"]`; for each image, calls
     `LLMProvider.vision_extract`; appends `[Image: <text>]` blocks
     to `body_text`. Handlers don't know about OCR; the pipeline
     orchestrates.
   - **B:** the handlers themselves call `LLMProvider.vision_extract`
     during `extract()`. Couples handlers to the LLM provider —
     violates SourceHandler's current pure-extraction contract.
   
   **Option A is the right shape** — keeps handlers pure + extraction
   stage-3 separate from OCR stage-3.5.
2. **Insertion point.** Probably between stage-3 (Extract) and
   stage-4 (Archive) — OCR runs AFTER text extraction, BEFORE the
   archive copy is written. The archive should capture the ORIGINAL
   image bytes; the body text gets OCR'd content inlined.
3. **OCR block format.** Each image's OCR text becomes:
   ```
   [Image (slide 3): <extracted text>]
   ```
   for pptx (with slide context), or:
   ```
   [Image: <extracted text>]
   ```
   for docx (no slide concept). The slide index for pptx comes from
   the image tuple's `slide_index` field.
4. **Empty OCR handling.** If `vision_extract` returns empty string
   (no text in image), skip the inline block — don't emit an empty
   `[Image: ]`.
5. **Error handling.** If a vision call fails (transient API error),
   log + skip that image; continue with remaining images. Don't fail
   the whole ingest because one image failed OCR.
6. **Integration tests:**
   - DocxHandler with 1 inline image → after pipeline, body contains
     `[Image: <fake-ocr-text>]`.
   - PptxHandler with images on slides 2 + 5 → body has
     `[Image (slide 2): ...]` + `[Image (slide 5): ...]`.
   - Vision API error → image skipped + structlog warning + ingest
     succeeds.
   - Empty OCR response → no inline block emitted.
   - Per-domain budget exhausted mid-OCR → ingest pauses;
     `IngestResult` status = `failed` with appropriate error message.

**Per-task review:** combined. Reviewer confirms (a) OCR runs at the
pipeline level (not in handlers — pure extraction contract preserved);
(b) inline-block format consistent (with slide context for pptx);
(c) error handling skips bad images but doesn't fail the ingest;
(d) budget exhaustion mid-OCR pauses cleanly.

### Theme D — Frontend

#### T5 — Drop-zone accept list + Inbox icons

**Files:**
- Modify: `apps/brain_web/src/lib/state/inbox-store.ts` (or wherever
  the drop-zone accept list lives — verify via grep for the existing
  list with `.pdf`, `.txt`, `.eml`, etc.) — add `.docx` + `.pptx`.
- Modify: `apps/brain_web/src/components/inbox/source-row.tsx` (or
  the icon-mapping file) — add icon entries for `docx` + `pptx`
  SourceTypes. Use Lucide icons: `FileText` for docx, `Presentation`
  for pptx.
- Modify: `apps/brain_web/tests/unit/source-row.test.tsx` (if exists)
  OR create new test for the icon mapping coverage.

**Goal:** Users can drag-drop .docx/.pptx files into the web app
inbox; the Inbox row renders an appropriate icon.

**What to do:**
1. **Drop-zone accept list:** find the existing list in
   `inbox-store.ts` (Plan 18 T3.9 / Plan 19 T5 work touched this
   area; per Plan 16/19/20/22 lesson, grep before assuming the file
   location). Add the two new extensions + their MIME types:
   - `.docx`: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
   - `.pptx`: `application/vnd.openxmlformats-officedocument.presentationml.presentation`
2. **Icon mapping:** if the inbox row uses an icon-by-source-type
   mapping (likely a dict or switch statement), add:
   - `docx` → `FileText` (Lucide)
   - `pptx` → `Presentation` (Lucide)
3. **Unit tests:** verify the accept list contains both new
   extensions; verify each new SourceType renders the right icon
   (snapshot or shallow-render assertion).

**Per-task review:** combined. Reviewer confirms (a) accept list
includes both new extensions WITH correct MIME types; (b) icon
mapping covers both new SourceTypes; (c) unit tests fail RED if
either is reverted; (d) vitest + tsc clean.

### Closure

#### T6 — Closure: demo + lessons + todo + tag

**Files:**
- Create: `scripts/demo-plan-24.py` — ~12 gates per the demo
  description.
- Modify: `tasks/lessons.md` — Plan 24 closure section.
- Modify: `tasks/todo.md` — row 24 ✅ + Plan 25 candidate scope.
- Tag: `plan-24-docx-pptx-ingest` cut on green demo.

**Goal:** land Plan 24 closure following Plan 22 T17 / Plan 23 T3 shape.

**Lessons to capture:**
1. **First new SourceType expansion since v0.1.0.** Plans 10-23 all
   worked against the fixed text/url/pdf/email/transcript/tweet
   enum. Plan 24's `docx` + `pptx` are the first new entries. The
   path was clean: SourceType enum + handlers + dispatcher
   registration + frontend icon mapping. Mature surface; no
   refactoring of existing handlers needed.
2. **OCR via LLMProvider abstraction.** Per CLAUDE.md non-negotiable
   #4 — required adding `vision_extract` to the base class instead
   of calling anthropic directly. The added method is provider-
   agnostic (any future OpenAI / Google provider implements it the
   same way) + metered through the same budget rail.
3. **`op="ocr"` cost-ledger extension.** New operation type lets
   users audit OCR spend separately from classify/summarize/integrate
   in the cost view. Pattern reusable for future per-feature spend
   metering (e.g., future structured-extract LLM calls).
4. **Pipeline-orchestrated OCR keeps handlers pure.** T4's
   choice-A design (OCR at pipeline level, post-extract) means
   handlers stay LLM-provider-agnostic + the SourceHandler Protocol
   contract is unchanged. Future formats (Excel, RTF, etc.) inherit
   the OCR pass automatically by emitting `extras["images"]`.

**Handoff to Plan 25:**
- 16 Plan 22 carry-forwards unchanged (7 UX + 4 architectural + 1
  dev-loop + 4 preserved NOT-DOING).
- Plan 24-surfaced candidates (if any) appended.

## Owning subagents

- **brain-core-engineer** — T0 (spec + SourceType + ledger), T1
  (DocxHandler), T2 (PptxHandler + dep), T3 (LLMProvider abstraction
  + AnthropicProvider impl), T4 (pipeline OCR wiring), T6 (closure).
- **brain-frontend-engineer** — T5 (drop-zone accept list + Inbox
  icons).
- (No brain-ui-designer; T5 is mockup-free per D7.)

## Workflow rules

Same as Plans 16-23:
- Sequential per-task dispatch via subagent-driven-development.
- Combined spec + code-quality review per task.
- No push without explicit user authorization at Plan 24 close (D8).
- Pause cadence every ~3 tasks (D11): pause after T3 (Vision API
  abstraction landed) + plan-close after T6.
- pytest recipe per `feedback_uv_uf_hidden.md` (chflags 0 .pth OR
  PYTHONPATH bypass).
- Frontend per-task verification: vitest + tsc --noEmit per
  `feedback_tsc_vs_vitest.md`.
- Plan-author drift watch (Plan 16/19/20/22/23 lesson): implementers
  MUST grep before assuming file/symbol locations. Plan-doc cites
  specific files at exec-time-verify cadence; reality may differ.
- LLMProvider non-negotiable: `vision_extract` MUST be on the base
  class, not anthropic-specific. Tests use FakeLLMProvider.

## File inventory (summary)

```
tasks/plans/
└── 24-docx-pptx-ingest.md                  # SELF (this doc)

docs/superpowers/specs/
└── 2026-04-13-cj-llm-kb-design.md          # MODIFY: §5 + §10 (T0)

packages/brain_core/
├── src/brain_core/
│   ├── ingest/
│   │   ├── types.py                        # MODIFY: +DOCX +PPTX SourceType (T0)
│   │   ├── handlers/
│   │   │   ├── docx.py                     # CREATE: DocxHandler (T1)
│   │   │   └── pptx.py                     # CREATE: PptxHandler (T2)
│   │   ├── dispatcher.py                   # MODIFY: register both (T1, T2)
│   │   └── pipeline.py                     # MODIFY: OCR pass (T4)
│   ├── llm/
│   │   ├── __init__.py (or base.py)        # MODIFY: vision_extract abstract (T3)
│   │   └── providers/anthropic.py          # MODIFY: vision_extract impl (T3)
│   └── cost/
│       └── ledger.py                       # MODIFY: accept op="ocr" (T3)
└── tests/
    ├── ingest/
    │   ├── test_source_type_pin.py         # CREATE: enum pin (T0)
    │   ├── handlers/
    │   │   ├── test_docx.py                # CREATE (T1)
    │   │   ├── test_pptx.py                # CREATE (T2)
    │   │   ├── test_docx_ocr_integration.py  # CREATE (T4)
    │   │   └── test_pptx_ocr_integration.py  # CREATE (T4)
    ├── llm/test_vision_extract.py          # CREATE (T3)
    └── cost/test_ocr_op_ledger.py          # CREATE or extend (T3)

pyproject.toml                              # MODIFY: +python-pptx (T2)

apps/brain_web/
├── src/
│   ├── lib/state/inbox-store.ts            # MODIFY: accept list (T5)
│   └── components/inbox/source-row.tsx     # MODIFY: icon mapping (T5)
└── tests/unit/
    └── source-row.test.tsx                 # MODIFY: icon coverage (T5)

scripts/
└── demo-plan-24.py                         # CREATE (T6)

tasks/
├── lessons.md                              # MODIFY: Plan 24 closure (T6)
└── todo.md                                 # MODIFY: row 24 ✅ + Plan 25 (T6)
```

## T0-T6 outcomes

_Filled in at each task close. Standard receipt format mirrors Plan
19-23._

## Plan 25 candidate scope

Filled in at T6 closure. Plan 22's 16 unaddressed carry-forwards
(unchanged through Plan 23) plus any Plan 24-surfaced candidates.

## Review

_Filled in at T6 close. Tag SHA + closure summary + bumps +
verification receipts + backlog forward._

---

**End of Plan 24.**
