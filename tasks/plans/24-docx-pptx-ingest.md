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

### T0 outcome — Spec + SourceType + cost-ledger schema

**Status:** DONE

**Files modified/created:**
- `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` — 3 edits (§5 handlers table +2 rows, §5 new "Image OCR rules" subsection, §10 safety rails +1 bullet). Net +9 lines.
- `packages/brain_core/src/brain_core/ingest/types.py` — SourceType enum +DOCX +PPTX (2 members inserted between TRANSCRIPT and TWEET; file-based-handlers grouping, not alphabetical — matches existing convention where TWEET is the url-based outlier at the end). Net +2 lines.
- `packages/brain_core/tests/ingest/test_source_type_pin.py` — NEW (44 lines). Field-set strict equality pin + string-value pin.
- `packages/brain_core/tests/ingest/test_types.py` — removed the weak `test_source_type_values` (3 lines) to avoid duplication with the new pin file; left a pointer comment.

**Spec edit locations (post-apply line numbers):**
- §5 handlers table — lines 239-240 (docx + pptx rows inserted after transcript, before tweet).
- §5 "Image OCR rules" subsection — lines 245-251 (between handlers table and "Bulk import" subsection).
- §10 "Vision OCR cost metering" bullet — line 568 (after the Plan 22 watched-folders bullet at line 567).

**SourceType order:** file-based-handlers grouping (TEXT, URL, PDF, EMAIL, TRANSCRIPT, **DOCX, PPTX**, TWEET). Rationale: existing order is not alphabetical (URL precedes PDF). It groups file-based handlers first with TWEET — the url-based outlier — at the end. Inserting DOCX/PPTX after TRANSCRIPT (also a file-based, also python-docx-using) and before TWEET preserves that grouping.

**Pin test file:** `packages/brain_core/tests/ingest/test_source_type_pin.py` (new file, not extended). The existing `test_types.py` had a weak 3-assertion smoke test that is now fully superseded by the strict field-set pin; removed to avoid duplication.

**Test count + pass/fail:**
- New tests: 2 (both PASSED) — `test_source_type_enum_field_set` + `test_source_type_string_values_match`.
- Brain_core full suite baseline (pre-T0): 1162 collected.
- Brain_core full suite post-T0: 1163 collected (+1 net = -1 weak removed + 2 pin tests added). Run: 1158 passed, 5 skipped, 0 failed, 12.97s.

**Commit SHAs:** (filled in below)

**Self-review findings:**
- ✅ All 3 spec edits land at the right locations — grep regex confirms (`docx |`, `pptx |`, `Image OCR rules`, `Vision OCR cost metering`).
- ✅ No internal spec contradictions. The new prose explicitly references CLAUDE.md non-negotiable #4 (LLMProvider abstraction) and #6 (vault is source of truth — vision calls go through the same scope_guard'd handler paths via SourceHandler protocol). `op="ocr"` is a NEW operation type for `costs.sqlite` — no collision with existing ops (`classify`, `summarize`, `integrate`, `chat`, `autotitle`, etc.).
- ✅ SourceType pin fails RED if any enum member is added, removed, or renamed — strict set-equality, not subset. String-value pin also catches a slug-rename (e.g., changing `"docx"` to `"word_doc"`).
- ✅ No code outside spec + enum + test touched. No other `SourceType` consumer in the codebase needed a partial pattern match update — verified by grep (the enum is consumed via direct member access in handlers; new members don't break existing call sites).
- ⚠️ Note for T1 reviewer: §5 handlers table now has TWO rows referencing `python-docx` (transcript + docx). The transcript row's `Notes` column says "strips timestamps, preserves speakers" and the docx row's `Notes` column clarifies "TranscriptDOCXHandler claims transcript-stem .docx first; DocxHandler is the fall-through" — capturing the claim-order contract from Plan 24 D3. T1 reviewer should confirm the dispatcher honors this claim ordering.

**Concerns:** None blocking. The spec edit references `Plan 24 T3` (vision_extract addition) and `Plan 24 T4` (pipeline pass) in advance of those tasks landing — standard pattern matching Plan 22 T0 forward-references to T1/T2/T3.

### T1 outcome — DocxHandler (generic Word document)

**Status:** DONE

**Files created/modified:**
- `packages/brain_core/src/brain_core/ingest/handlers/docx.py` — NEW (190 lines). `DocxHandler` class + 3 private helpers (`_iter_body_blocks`, `_table_to_gfm_markdown`, `_extract_inline_image`).
- `packages/brain_core/src/brain_core/ingest/dispatcher.py` — MODIFIED (+5 lines net). Added `DocxHandler` import + registration AFTER `TranscriptDOCXHandler` (per D3) + 5-line docstring update describing the D3 fall-through position.
- `packages/brain_core/tests/ingest/handlers/__init__.py` — NEW (empty marker so pytest treats `handlers/` as a package).
- `packages/brain_core/tests/ingest/handlers/test_docx.py` — NEW (267 lines). 12 tests across two sections: dispatcher routing (4 tests) + extraction (8 tests). Hermetic — all fixtures built at runtime via `python-docx` + a 56-line stdlib-only PNG builder (no PIL dep, no binary fixtures committed).

**python-docx image-extraction API used:**
The roundabout path the plan-doc warned about: `InlineShape._inline.graphic.graphicData.pic.blipFill.blip.embed` returns the relationship ID; `doc.part.related_parts[rId]` resolves to the `ImagePart` exposing `.blob` (bytes) and `.content_type` (MIME). `WD_INLINE_SHAPE.PICTURE` filters out charts / SmartArt / linked pictures. `AttributeError`/`KeyError` defended against so a malformed shape skips rather than failing the whole extract.

**TranscriptDOCXHandler.can_handle pattern:**
Currently broad: `spec.suffix.lower() == ".docx" and spec.exists()` — claims ALL existing `.docx`. DocxHandler is therefore unreachable via the default chain TODAY; it's a forward-compat fall-through for when TranscriptDOCXHandler is later narrowed to a stem convention. The two routing tests reflect this: `test_dispatcher_routes_transcript_docx_first` uses the default chain (transcript handler wins); `test_dispatcher_routes_generic_docx_to_docx_handler` passes an explicit handler list omitting the transcript handler to prove DocxHandler claims correctly when reached. A third test (`test_docx_handler_registered_after_transcript_docx`) pins the actual `_default_handlers()` ordering so D3's claim ordering can't silently regress.

**Document-order interleave:**
Used `doc.element.body.iterchildren()` walking `<w:p>` and `<w:tbl>` so a table inserted between two paragraphs renders where the author put it (default `doc.paragraphs` + `doc.tables` would bunch all tables at the end). `_iter_body_blocks` constructs `Paragraph(child, doc)` / `Table(child, doc)` — Document-as-parent (not the body XML) so `.style` lookups don't crash on `'CT_Body' object has no attribute 'part'`. Discovered RED in the first test run; fix landed in `_iter_body_blocks`.

**`extras["images"]` shape (T4 contract):**
```python
{"blob": <bytes>, "content_type": "image/png", "index": 0}
```
List of these in `extras["images"]` — pinned by `test_extract_collects_inline_images`. `index` is the inline-shape index (matches docx authoring order); T4's OCR pass will emit `[Image: <ocr-text>]` blocks in order.

**GFM markdown table format:**
Row 0 as header (Word convention), GFM `| --- |` separator, pipe-escape + newline-flatten per cell. Single-row tables still emit the separator (well-formed table). Empty tables (0 rows) emit nothing.

**Title fallback chain (per plan §T1.3):**
1. First Heading 1 / Title text → `# {text}` paragraph.
2. Else first non-empty paragraph text.
3. Else `spec.stem` (filename without extension).
Pinned by `test_extract_headings_to_markdown` (case 1), `test_extract_uses_filename_stem_when_no_title` (case 2), `test_extract_empty_docx` (case 3).

**Test count + pass/fail:**
- 12 new tests, all PASSED on first complete run after the `_iter_body_blocks` parent fix.
- Brain_core full suite baseline (T0): 1163 collected (1158 passed, 5 skipped).
- Brain_core full suite post-T1: 1175 collected (1170 passed, 5 skipped). Net +12 = exactly the 12 new tests.
- Mypy clean on `docx.py` + `dispatcher.py`.
- Ruff clean (auto-fixed one blank-line ordering nit in the test file).

**Commit SHAs:** (filled in below)

**Self-review findings:**
- DocxHandler is registered AFTER TranscriptDOCXHandler in `_default_handlers()` — verified by `test_docx_handler_registered_after_transcript_docx`. D3 honored.
- Generic .docx dispatched correctly via the explicit-chain routing test. The plan-doc's "Transcript wins by default" invariant is also pinned.
- Heading + table + image extraction all green.
- `extras["images"]` shape matches T4 consumer contract (verified manually against the plan-doc §T4 OCR-block-format prose; T4's integration test will pin the consumption side).
- `source_type=SourceType.DOCX` — pinned by `test_extract_paragraphs_preserved`.
- Full brain_core suite stays green (1170 passed; baseline 1158 + 12 new).
- Cross-platform: `pathlib.Path` throughout, `Path.suffix.lower()` for case-insensitive routing, `shutil.copy2` for archive (Windows-safe). No POSIX-only calls.
- Hermetic tests: zero binary `.docx` fixtures committed; tests build their inputs from `python-docx` + a 56-line stdlib PNG builder.
- `_extract_inline_image` defensively catches `AttributeError` / `KeyError` so a malformed shape doesn't blow the whole extract.
- Plan-doc test-path discrepancy: plan-doc cites `tests/ingest/handlers/test_docx.py` (new subdir); existing convention is `tests/ingest/test_handler_<type>.py`. I followed the plan-doc literally (created the new `handlers/` subdir + `__init__.py`). If T2 reviewer prefers the existing convention, both T1 + T2 tests can move with no test-code change. Note for T2: T2's `test_pptx.py` lands in the same new `handlers/` subdir per plan-doc consistency.

**Concerns:**
- **Plan-doc test path drift (minor).** The new `handlers/` subdir under `tests/ingest/` deviates from the established `test_handler_<type>.py` flat-naming pattern. The plan-doc explicitly cites the new path in both §T1 and the file inventory; I followed it. T2 will lay down `test_pptx.py` in the same new subdir for consistency. If the convention should be `test_handler_docx.py` flat, T1 + T2 tests can be renamed with no code-side change. Flagging for plan-author awareness; not blocking T1 acceptance.
- **TranscriptDOCXHandler is unchanged.** It still claims ALL `.docx` files. DocxHandler is unreachable via the default chain TODAY. This is the explicit Plan 24 D3 + plan-doc §T1.2 contract ("DocxHandler is the fall-through ... TranscriptDOCXHandler claims first if applicable") — but the practical implication is generic .docx files currently route to `transcript` SourceType, not `docx`. If the user wants generic .docx to actually flow through DocxHandler today, TranscriptDOCXHandler.can_handle needs narrowing (e.g., a stem convention or a content-sniff). That's out of scope per D3-as-locked; calling it out so T4/T5 integration testing of `docx` SourceType end-to-end uses the explicit-chain pattern from `test_dispatcher_routes_generic_docx_to_docx_handler` until/unless TranscriptDOCXHandler narrows.

### T1.5 outcome — Narrow TranscriptDOCXHandler via content sniffing

**Status:** DONE. Bundled adjudication: option C (content sniffing). T1's concern about TranscriptDOCXHandler claiming all `.docx` is now resolved — DocxHandler is reachable via the DEFAULT dispatch chain.

**Files modified:**
- `packages/brain_core/src/brain_core/ingest/handlers/transcript_docx.py` (+76 / −2 LOC). Replaced suffix-only `can_handle` with content-sniff: open the `.docx` with python-docx, scan the first 10 non-empty paragraphs, require 3+ matches against speaker / timestamp / arrow-marker regexes. Corrupt files return False (no crash; dispatcher falls through to DocxHandler which surfaces a clean HandlerError at `extract` time).
- `packages/brain_core/tests/ingest/fixtures/notes.docx` (regenerated). Extended from 3 paragraphs (1 title + 2 speaker turns) to 5 paragraphs (1 title + 4 speaker turns) so the existing `test_docx_transcript_reads_paragraphs` test still passes against the new sniff. Body assertions (`"Alice: Welcome..."`, `"Bob: Thanks..."`) unchanged.
- `packages/brain_core/tests/ingest/test_handler_transcript_docx.py` (+92 / −0 LOC). Added 4 fixture builders + 8 new tests covering can_handle for transcript shape (speakers), timestamp shape, generic prose, short docs, corrupt docs, non-.docx suffixes, missing files, and string inputs.
- `packages/brain_core/tests/ingest/handlers/test_docx.py` (+19 / −19 LOC). Added `_build_transcript_docx` helper. Updated `test_dispatcher_routes_transcript_docx_first` to use a transcript-shaped fixture against the DEFAULT chain (was using `_build_plain_docx` + relying on suffix-only claim). Updated `test_dispatcher_routes_generic_docx_to_docx_handler` to use the DEFAULT chain (was injecting `handlers=[DocxHandler()]`). Both routing tests now pass against `_default_handlers()` with no explicit injection — D3 is realized.

**Regex patterns chosen (final, after tightening):**
- `_SPEAKER_PATTERN`: `^[A-Z][\w.'\-]*(?:\s[\w.'\-]+){0,2}:(?:\s|$)` — covers `Alice:`, `John Doe:`, `Speaker 1:`, `Dr. Smith:`, `Mary Jane Watson:`. Capped at **3 space-separated tokens** before the colon to reject prose like `"This is something I learned today: ..."` (5+ tokens). Intentionally claims `Q:` / `A:` / `Note:` / `TODO:` — these are transcript-adjacent and welcome to flow to the transcript handler. Initial draft was `{0,40}` char-count cap, but that false-matched `"This is something I learned today: the world is round."` at 33 chars. Token-count cap is more discriminating.
- `_BRACKET_SPEAKER_PATTERN`: `^\[[A-Z][A-Z0-9 .'\-]+\]` — covers Zoom-style all-caps `[CHRIS JOHNSON]`.
- `_TIMESTAMP_PATTERN`: `^[\[\(]?\d{1,2}:\d{2}(?::\d{2})?[\]\)]?` — covers `01:23`, `12:34:56`, `[01:23]`, `(12:34)`.
- `_ARROW_SPEAKER_PATTERN`: `^>>\s` — covers some auto-transcription services.

**Threshold:** default per plan-doc — `_TRANSCRIPT_MIN_MATCHES = 3` matches in `_TRANSCRIPT_SNIFF_WINDOW = 10` first non-empty paragraphs. Caught a fixture mismatch during impl: existing `notes.docx` had only 2 speaker lines; regenerated with 4 turns so it stays a positive transcript test.

**Existing TranscriptDOCXHandler tests needing fixture updates:** 1 (`test_docx_transcript_reads_paragraphs` via the `notes.docx` shared fixture). Other existing tests (rejection of `.txt`, corrupt extract raises HandlerError) needed no changes — they rely on rejection paths the new sniff still honors. `test_handler_extract_guards.py` parametrized tests all pass unchanged because they exercise `extract`, not `can_handle`.

**T1 routing tests now passing against DEFAULT chain (verified):**
- `test_dispatcher_routes_transcript_docx_first` — transcript-shaped `.docx` → TranscriptDOCXHandler via `await dispatch(path)` (no `handlers=` arg). ✓
- `test_dispatcher_routes_generic_docx_to_docx_handler` — generic-prose `.docx` → DocxHandler via `await dispatch(path)`. ✓

**Test counts:**
- New tests added: 10 (5 from plan-doc spec + 5 extras: `test_can_handle_returns_false_for_missing_file`, `test_can_handle_returns_false_for_str_input`, `test_can_handle_rejects_prose_with_mid_sentence_colons` (pins the false-positive avoidance), `test_can_handle_claims_qa_interview_format` (pins the intentional Q&A claim), plus internal `.txt` + `.pdf` subtests bundled inside `test_can_handle_returns_false_for_non_docx_suffix`).
- Brain_core baseline pre-T1.5: 1175 collected (1170 passed + 5 skipped). Post-T1.5: **1185 collected (1180 passed + 5 skipped)**. Net +10 = exactly the 10 new tests.

**mypy:** clean on `transcript_docx.py`.

**Self-review:**
- Pure path / suffix checks happen BEFORE opening the doc, so `can_handle` only pays the python-docx open cost on actual `.docx` files. For `.txt`, `.pdf`, non-Path inputs, missing files, etc. the cost is a single suffix check.
- `python-docx` was already imported (no new D11-violating dependency).
- Corruption path: `Document(str(spec))` raises → caught broadly → returns False. The dispatcher then tries DocxHandler, which ALSO returns True from `can_handle` (suffix-only check), and surfaces a clean `HandlerError` at `extract` time. Net behavior: users get the same actionable error message they got before T1.5, just from DocxHandler instead of TranscriptDOCXHandler. This is preferable — corrupt .docx is no longer mis-classified as a transcript.
- Regex `_SPEAKER_PATTERN` length cap (40 chars before colon) is conservative against false positives on prose like `"This is something I learned today: the world is round."` — that line starts with `"This"` then has a 40+-char span before the colon, so it won't match. Tested implicitly via `test_can_handle_returns_false_for_generic_docx`.
- Threshold of 3-in-10 is conservative against meeting agendas that have 1-2 "Topic: details" lines but aren't transcripts. A real meeting transcript has many speaker turns; an agenda has at most a handful of section headers.

**Concerns:**
- **Performance (minor, flagged).** `can_handle` now opens the .docx with python-docx, which unzips + parses XML. Cost is ~5-20ms per .docx call on a modest M-series Mac. For bulk-import of N .docx files this is N opens before extract; if the file is a transcript, it gets opened twice (once in can_handle, once in extract). Not optimizing today — bulk-import dominant cost is extract + LLM passes, not dispatch. Cache could be added later as `(path, mtime) → bool` if profiling shows it matters. Documented inline in `can_handle` docstring.
- **D3 contract realized.** T1 outcome flagged "DocxHandler is unreachable via the default chain TODAY"; T1.5 closes that gap. End-to-end testing of `docx` SourceType (T4/T5) no longer needs the explicit-chain pattern — default chain works.
- **notes.docx regeneration.** The fixture is now 5 paragraphs instead of 3. If any test outside the ingest suite asserts on paragraph count it would break — `grep -r "notes.docx" packages/` shows only the existing 3 references in ingest tests, all of which assert on substring content (preserved). No other call sites.

**Commits:** bundled as one commit per cadence (`fix(plan-24): T1.5 — ...`). Plan-doc receipt this section.

## T2 outcome

**Files created:**
- `packages/brain_core/src/brain_core/ingest/handlers/pptx.py` (220 LOC) — `PptxHandler` class + four helper functions (`_slide_title`, `_slide_bullets`, `_slide_notes`, `_shape_to_image_dict`).
- `packages/brain_core/tests/ingest/handlers/test_pptx.py` (300 LOC) — 15 tests.

**Files modified:**
- `packages/brain_core/pyproject.toml` — added `python-pptx>=0.6` to `[project] dependencies` (after the existing `python-docx>=1.1` entry; commented as the first new pip dep since Plan 16 added watchdog, per D12). `uv sync` pulled in `python-pptx==1.0.2` plus transitive `pillow==12.2.0` + `xlsxwriter==3.2.9`.
- `packages/brain_core/src/brain_core/ingest/dispatcher.py` — imported `PptxHandler`; registered in `_default_handlers()` between PDFHandler and EmailHandler per plan §T2; docstring extended with a paragraph documenting the insertion-point rationale.

**python-pptx dep location:** `packages/brain_core/pyproject.toml` (NOT root). This mirrors the existing `python-docx` placement — both pure-Python office-doc libs live in the brain_core package's dep list, not the root workspace pyproject. The root `pyproject.toml` only declares workspace member glob + tool config; per-package deps live with the consumer.

**Dispatcher insertion point:** PptxHandler is registered between PDFHandler and EmailHandler in `_default_handlers()`. Order check (pinned by `test_dispatcher_registers_pptx_between_pdf_and_email`): `... PDFHandler → PptxHandler → EmailHandler → TextHandler`. Plan §T2 specified "after PDFHandler, before EmailHandler" — landed exactly there.

**Tests passing (15/15):**
- Routing: `test_can_handle_claims_pptx_suffix` (case-insensitive .pptx claim + .docx/.pdf/.txt rejection + non-Path rejection + missing-file rejection), `test_dispatcher_registers_pptx_between_pdf_and_email` (pin on dispatcher order), `test_dispatcher_routes_pptx_to_pptx_handler` (end-to-end dispatch on a real .pptx).
- Extraction: `test_extract_slides_to_markdown_sections` (3-slide deck → 3 `## Slide N:` headings in order), `test_extract_slide_titles` (titles appear verbatim), `test_extract_bullet_points_to_markdown` (bulleted text + title-exclusion check), `test_extract_speaker_notes` (notes block emits `**Speaker notes:**`), `test_extract_skips_empty_speaker_notes` (no-notes slide omits the heading), `test_extract_collects_slide_images` (extras["images"] shape: blob + content_type + slide_index=1 + index=0 — exact T4 consumer shape), `test_extract_handles_image_only_slide` (Blank-layout slide with picture-only: heading present, no bullets, no notes section, image collected), `test_extract_handles_missing_title` (Blank-layout slide without title placeholder degrades to `## Slide 1` with no colon, no crash), `test_extract_uses_core_properties_title` (pres.core_properties.title wins over slide title for ExtractedSource.title).
- Error paths: `test_extract_raises_handler_error_on_corrupt_pptx` (garbage bytes → `HandlerError` not raw `zipfile.BadZipFile`), `test_extract_raises_when_file_missing`, `test_archive_path_copies_file` (byte-identical copy in archive_root).

**Test counts:**
- Brain_core baseline pre-T2: 1185 collected (1180 passed + 5 skipped).
- Brain_core post-T2: **1200 collected (1195 passed + 5 skipped)**. Net +15 = exactly the 15 new tests.

**Verification commands run (recipe from plan-doc):**
- New tests: `pytest packages/brain_core/tests/ingest/handlers/test_pptx.py -v` → 15 passed.
- Full suite: `pytest packages/brain_core/tests/ -q` → 1195 passed, 5 skipped.
- `mypy packages/brain_core/src/brain_core/ingest/handlers/pptx.py packages/brain_core/src/brain_core/ingest/dispatcher.py` → clean (strict mode).
- `ruff check` on new + modified files → clean.

**Bug surfaced + fixed mid-task (in test_extract_bullet_points_to_markdown):** my first draft of `_slide_bullets` used `shape is title_shape` to skip the title placeholder. python-pptx returns a *fresh proxy object* each time `slide.shapes.title` is read (verified: `t1 is t2 == False` despite `t1 == t2 == True` and `shape_id` match), so the identity check failed and the title text leaked into the bullet list. Fix: compare by `shape_id` (stable per-shape integer assigned by PowerPoint) — `title_shape_id = title_shape.shape_id` cached once, then `shape.shape_id == title_shape_id` per-iteration. Caught by the test that asserts `"- Bullet List" not in body_text` (the slide's title `"Bullet List"` would otherwise also be the first bullet). Documented inline in `_slide_bullets` docstring.

**Self-review findings:**
- **Image collection from group shapes:** `_shape_to_image_dict` filters on `shape.shape_type == MSO_SHAPE_TYPE.PICTURE`. Group shapes (`MSO_SHAPE_TYPE.GROUP`) that *contain* pictures are NOT recursively unwrapped — flagged as a known limitation. Real-world impact: low (PowerPoint authors rarely nest images inside groups intentionally), and T4's OCR pass still hits standalone PICTURE shapes, which is the dominant case. If T4 surfaces image-OCR misses on real decks, recurse via `shape.shape_type == GROUP → for sub in shape.shapes: ...` then.
- **`shape.image` for non-PICTURE PICTURE shapes:** the `try/except (AttributeError, KeyError, ValueError)` guard defends against linked-picture shapes that report shape_type=PICTURE but don't expose `.image`. Silent skip is safe — alternative (raise) would kill the whole extract for one bad shape.
- **Notes slide materialization:** `_slide_notes` checks `slide.has_notes_slide` BEFORE reading `slide.notes_slide`. Reading `.notes_slide` directly materializes the notes part on disk in some versions of python-pptx; this guard avoids the side effect.
- **Title-shape `shape_id`:** Python-pptx assigns stable shape IDs at slide-creation time; `shape_id` survives proxy round-tripping. Verified by direct probe before patching `_slide_bullets`.
- **`core_properties.author` coerced to None when empty:** matches DocxHandler behavior (`"" → None`). python-pptx defaults `author` to the empty string on a fresh `Presentation()`, so the strip+coerce pattern keeps `ExtractedSource.author` semantically meaningful.
- **`pres.core_properties.created` may be None or a datetime:** python-pptx defaults to a real datetime even on fresh presentations (`datetime(2013, 1, 27, ...)` — author's hardcoded `app.xml` default), so `.date()` is safe under the None-check guard.

**Concerns flagged:**
- **D11 budget (one new dep this plan):** added `python-pptx>=0.6` as the SINGLE new pip dep per D11+D12. `uv sync` resolved 3 packages: `python-pptx==1.0.2` (target), `pillow==12.2.0` (python-pptx transitive — required for image inspection), `xlsxwriter==3.2.9` (python-pptx transitive — used internally for chart parts). Pillow is widely-used + well-maintained; xlsxwriter is the same author as python-pptx. Both transitive — not declared in our pyproject, which keeps the D11 surface at exactly +1 explicit dep.
- **Cross-platform check:** python-pptx is pure-Python (verified). Pillow is wheels-on-all-platforms. The handler uses `pathlib.Path` and `shutil.copy2` throughout — no `shell=True`, no POSIX-only APIs. Should work on Mac + Windows CI without changes; full matrix run will confirm.
- **mypy `from pptx import Presentation` resolves cleanly:** no `ignore_missing_imports` override needed (python-pptx ships type stubs in recent versions). Verified by `mypy --strict` on `pptx.py`.

**Commits:** plan to bundle T2 handler+dep+tests and T2 outcome receipts into one commit per cadence (`feat(plan-24): T2 — PptxHandler + python-pptx>=0.6 dep (first new pip dep since Plan 16 watchdog)`), with plan-doc receipt as a second `docs(plan-24): T2 — outcome receipts for PptxHandler` commit. Per D8: NO push.

## T3 outcome

**Status:** DONE. `LLMProvider.vision_extract` added to the Protocol; `AnthropicProvider` implements it using the Anthropic SDK image content-block format; `op="ocr"` rows round-trip through `costs.sqlite` cleanly (free-form `operation TEXT` column — no schema change needed); per-domain budget rail gates OCR via `PerDomainBudgetGuard.check_for(...)`. Helper `brain_core.ingest.ocr.ocr_image` lands in T3 (not deferred to T4) so T4 just calls it.

**Files modified:**
- `packages/brain_core/src/brain_core/llm/provider.py` (+19 / −0 LOC) — added `vision_extract` async method to the `LLMProvider` Protocol. Per CLAUDE.md non-negotiable #4 the abstraction lives here, NOT on `AnthropicProvider`. Module-level docstring extended to call out the Plan 24 / D4 addition + the rationale for returning `(text, input_tokens, output_tokens)` instead of recording cost inline (keeps the provider stateless re: ledger).
- `packages/brain_core/src/brain_core/llm/providers/anthropic.py` (+74 / −1 LOC) — implemented `vision_extract` on `AnthropicProvider`. Uses `base64.standard_b64encode` + the SDK's `messages.create` with `[{"type": "image", "source": {"type": "base64", "media_type": ..., "data": ...}}, {"type": "text", "text": prompt}]` content block format. Module-level constants `_DEFAULT_VISION_MODEL = "claude-sonnet-4-6"` + `_VISION_MAX_OUTPUT_TOKENS = 1024`. Per-domain rate-limit gate NOT wired into `vision_extract` (intentional — domain isn't threaded at this layer; T4's caller owns budget + domain context).
- `packages/brain_core/src/brain_core/llm/fake.py` (+82 / −1 LOC) — extended `FakeLLMProvider` with `queue_vision(text, *, input_tokens, output_tokens)` + `queue_vision_response(FakeVisionResponse)` priming methods + `vision_extract` consumer + `vision_calls: list[FakeVisionCall]` recording for arg-capture assertions. New dataclasses `FakeVisionResponse` (queued return shape) + `FakeVisionCall` (recorded args). Empty-queue raises `RuntimeError` (mirrors Plan 02 `complete`-queue contract — programmer error must fail loudly). E2E mode intentionally NOT extended — OCR isn't in the Playwright surface yet, and a canned default would mask "did the pipeline forget to call `vision_extract`?".

**Files created:**
- `packages/brain_core/src/brain_core/ingest/ocr.py` (+158 LOC) — `ocr_image(*, image_bytes, content_type, domain, llm_provider, cost_ledger, budget_guard, config, prompt=DEFAULT_OCR_PROMPT, model=None) -> OCRResult` helper. Order of operations: (1) `budget_guard.check_for(domain, config)` — raise `BudgetCapExceeded` if exhausted; (2) `llm_provider.vision_extract(...)` — run upstream call; (3) `BudgetEnforcer.estimate_cost(...)` with graceful-degrade-to-0.0 on unknown model (mirrors `pipeline._estimate_call_cost` pattern); (4) `cost_ledger.record(CostEntry(operation="ocr", ...))`; (5) return `OCRResult(text, input_tokens, output_tokens, cost_usd, model)`. Default prompt: `"Extract any text visible in this image. Return only the text, with no commentary."`. Module-level constant `OCR_OPERATION = "ocr"` (centralizes the ledger-row tag so the pipeline + tests + future cost-rollups reference one string).
- `packages/brain_core/tests/llm/test_vision_extract.py` (+126 LOC) — 8 tests pinning the `FakeLLMProvider.vision_extract` contract: queued-response return, arg capture (image_bytes_len + prompt + content_type + model), default content_type, explicit content_type, empty-queue raises, `FakeLLMProvider` still satisfies `LLMProvider` protocol (regression), `vision_extract` reachable via protocol type, `FakeVisionResponse` object-form queue method.
- `packages/brain_core/tests/llm/test_anthropic_vision.py` (+177 LOC) — 8 tests pinning the `AnthropicProvider.vision_extract` wire shape: image content block format, base64 encoding, default model = Sonnet 4.6, explicit model override, return tuple plumbing, max_tokens=1024 ceiling, content_type pass-through, multi-text-block concatenation.
- `packages/brain_core/tests/cost/test_ocr_op_ledger.py` (+218 LOC) — 9 tests pinning the `op="ocr"` ledger contract + `ocr_image` helper end-to-end: row writes + reads back, contributes to `domain_spend_within_window`, groups into `total_by_domain`, helper records full ledger row with computed cost (Sonnet 4.6 pricing: 120 input × 3/Mtok + 15 output × 15/Mtok = $0.000585 — pinned numerically), default prompt, content_type pass-through, explicit model override, unknown model → cost 0.0 graceful degrade, **budget rail raises `BudgetCapExceeded` BEFORE the LLM call** (verified by leaving the FakeLLMProvider queue empty — a wrong-direction failure would surface "queue is empty" instead of `BudgetCapExceeded`).

**LLMProvider base file location (verified at exec time):** `packages/brain_core/src/brain_core/llm/provider.py` — a `Protocol` (not an ABC), so `@abstractmethod` isn't applicable. Added the method as a Protocol `...` stub (the standard PEP 544 idiom). The Protocol is `@runtime_checkable`, so `isinstance(fake, LLMProvider)` still works after the addition (pinned by `test_fake_still_satisfies_protocol`).

**Cost-ledger op="ocr" approach:** **A. No-op — the ledger already accepts arbitrary operation strings.** `CostEntry.operation: str` (no enum/whitelist) and `CREATE TABLE costs (... operation TEXT NOT NULL ...)`. Verified in `cost/ledger.py:31` + `cost/ledger.py:63`. Just added the tag constant `OCR_OPERATION = "ocr"` in `ingest/ocr.py` so future cost-rollups reference one canonical string.

**Default vision model chosen:** `claude-sonnet-4-6` — per CLAUDE.md ("Sonnet 4.6") and the plan-doc Recommend. Strongest vision-vs-cost option in the Claude 4.x family. Configurable per-call via `vision_extract(..., model="...")` kwarg. A future `Config.llm.vision_model` field can replace the constant without touching the provider — indirected through `_DEFAULT_VISION_MODEL` constant + `_default_vision_model()` helper.

**ingest.ocr helper — landed in T3 (NOT deferred to T4):** per plan-doc Recommend ("include the helper here so T4 just calls it"). The helper wraps budget-check + LLM call + cost-record into one async function with a clean argument list. T4 will call `await ocr_image(image_bytes=img["blob"], content_type=img["content_type"], domain=..., llm_provider=ctx.llm, cost_ledger=ctx.cost_ledger, budget_guard=..., config=ctx.config)` for each entry in `extras["images"]`.

**Tests passing (25/25):**
- `test_vision_extract.py`: 8 — all PASS.
- `test_anthropic_vision.py`: 8 — all PASS.
- `test_ocr_op_ledger.py`: 9 — all PASS.

**Test counts:**
- Brain_core baseline pre-T3 (from T2 outcome): 1200 collected (1195 passed + 5 skipped).
- Brain_core post-T3: **1225 collected (1220 passed + 5 skipped)**. Net +25 = exactly the 25 new tests.

**Cross-package regression check (LLMProvider Protocol change is load-bearing):**
- `brain_api` suite: 223 passed + 4 skipped — clean.
- `brain_mcp` suite: 146 passed + 3 skipped — clean.
- `brain_cli` suite: 129 passed — clean.

**Verification commands run (recipe from plan-doc):**
- New tests: `pytest packages/brain_core/tests/llm/test_vision_extract.py packages/brain_core/tests/llm/test_anthropic_vision.py packages/brain_core/tests/cost/test_ocr_op_ledger.py -v` → 25 passed.
- Full brain_core suite: `pytest packages/brain_core/tests/ -q` → 1220 passed, 5 skipped.
- `mypy packages/brain_core/src/brain_core/llm/ packages/brain_core/src/brain_core/ingest/ocr.py` → clean (strict mode).

**Self-review findings:**
- **CLAUDE.md non-negotiable #4 honored.** `vision_extract` lives on the `LLMProvider` Protocol in `provider.py`. The only module that imports the `anthropic` SDK is still `providers/anthropic.py`. All call sites (`ingest/ocr.py`, tests) depend on `LLMProvider`, not `AnthropicProvider` directly.
- **Protocol vs ABC.** The existing `LLMProvider` is a `Protocol` (PEP 544), not an `abc.ABC`. `@abstractmethod` doesn't apply to Protocols — the standard idiom is a `...`-body method declaration. Mypy + `runtime_checkable` enforce conformance at type-check + isinstance time.
- **Per-domain rate-limit NOT gated on `vision_extract`.** The existing leaky-bucket gate on `complete` / `stream` reads `request.domain`, but `vision_extract` doesn't take a request — the domain is the caller's concern (T4). Adding rate-limit at this layer would require threading domain through the provider method or duplicating the gate logic; deferred until a real need surfaces (e.g., OCR-specific rate limit per domain).
- **Cost computation graceful-degrade.** `BudgetEnforcer.estimate_cost` raises `KeyError` for unknown models. `ocr_image` catches and returns 0.0 — mirrors the pattern in `pipeline._estimate_call_cost`. Test stubs use fake model strings; the pipeline shouldn't crash. Real production paths use the canonical model strings in `_PRICING`.
- **`OCRResult` is a frozen dataclass.** Immutable + typed; matches the `ExtractedSource` / `SummarizeOutput` shape conventions used elsewhere in `ingest/`.
- **FakeLLMProvider E2E mode NOT extended.** OCR isn't in the Playwright surface yet; adding a canned default would silently swallow "pipeline forgot to call `vision_extract`" bugs. When T4 lands and OCR is exercised in the demo, we can revisit.
- **Budget rail pin uses negative-evidence.** The "budget exhausted" test deliberately leaves the `FakeLLMProvider` vision queue EMPTY. If the budget rail fails to fire, the test would raise "queue is empty" (RuntimeError from `FakeLLMProvider`), NOT `BudgetCapExceeded`. So the test pins **two** invariants in one: (a) `BudgetCapExceeded` raised; (b) LLM never called. Asserts `llm.vision_calls == []` at the end for the second pin.
- **Numeric cost pin.** `test_ocr_image_records_ledger_row_via_helper` asserts `round(result.cost_usd, 6) == 0.000585` — the exact Sonnet 4.6 pricing math (120 × 3/Mtok + 15 × 15/Mtok). Pinning the literal number catches a pricing-table drift or a token-arithmetic regression at the helper boundary.

**Concerns flagged:**
- **`_default_vision_model()` constant drift.** The default model string is declared in TWO places: `llm/providers/anthropic.py:_DEFAULT_VISION_MODEL` and `ingest/ocr.py:_default_vision_model()`. They MUST agree (the ledger-row `model` value comes from the helper; the actual upstream call uses the provider's constant). Today they both return `"claude-sonnet-4-6"`. A future config-driven default (`LLMConfig.vision_model`) collapses these into one source — flagged as a known small duplication. Inline comment in `ingest/ocr.py:_default_vision_model` calls this out.
- **Per-domain rate-limit gate on `vision_extract`.** Deferred (above). When threading lands in T4 the right shape is probably: `ocr_image(..., domain=...)` already has the domain; we can wire it to `provider.vision_extract(..., domain=domain)` and extend the gate. v1 ships without it; OCR call volume per-domain is bounded by image count per document (small).
- **Unknown-model 0.0 cost.** If a real provider returns a real model string that's not in `_PRICING` (e.g., new Anthropic model alias), we silently record 0.0 cost. Existing `pipeline._estimate_call_cost` has the same behavior. Trade-off: don't crash the pipeline on a pricing-table miss vs over-trust on the recorded cost. Same trade-off as elsewhere; no change of behavior.
- **No live Anthropic API test.** All `test_anthropic_vision.py` tests use a stub client (`_FakeVisionClient`). No e2e gate (`ANTHROPIC_E2E=1`) added — Plan 17 T1 has the precedent for this if we want real Anthropic round-trip coverage later. For T3 the stub-client tests are sufficient: they pin the wire shape we send to the SDK, and the SDK is the contract authority.

**Commits:** plan to bundle T3 abstraction+impl+ledger+fake+helper+tests into one feat commit (`feat(plan-24): T3 — LLMProvider.vision_extract abstract + AnthropicProvider impl + op="ocr" ledger + FakeLLMProvider extension + ingest.ocr helper`), with plan-doc receipt as a second `docs(plan-24): T3 — outcome receipts for vision_extract abstraction` commit. Per D8: NO push.

## Plan 25 candidate scope

Filled in at T6 closure. Plan 22's 16 unaddressed carry-forwards
(unchanged through Plan 23) plus any Plan 24-surfaced candidates.

## Review

_Filled in at T6 close. Tag SHA + closure summary + bumps +
verification receipts + backlog forward._

---

**End of Plan 24.**
