# Plan 26 — CRITICAL ClassifyOutput Literal fix + Plan 25 immediate aftermath

**Authored:** 2026-05-13 (same day as Plan 25 close on 2026-05-13, tag
`plan-25-bulk-import-quality` at `5123fd1`).
**Scope:** Four follow-ups surfaced by Plan 25 execution + review:
(0/T1) **CRITICAL** correctness — `ClassifyOutput.source_type` Literal
missing `docx` + `pptx`, blocks classify-routing for the new SourceType
values added by Plan 24 (pre-existing Plan 24 gap surfaced at Plan 25
T2 implementer review); (1/T2) `ScannedPDFError` empty subclass hard-
removal (no internal callers post-Plan-25 T3; the docstring already
flags it deprecated); (2/T3) real walk-phase progress via Server-Sent
Events replacing Plan 25 T4's timer-driven pseudo-progress (the
apply phase already has REAL per-file progress; the walk phase is the
only timer-pseudo surface left); (3/T4) per-file filename display in
the apply-phase progress UI (Plan 25 T4 deferred this; the existing
JS-driven apply loop has the signal but doesn't surface it). Per user
scope locks: **B = critical + Plan-25 immediate aftermath** (4
substantive tasks, smaller bundle than Plan 25's 5); **D1 = runtime-
derived Literal** from `SourceType` enum (single source of truth);
**D2 = hard-remove ScannedPDFError** (no deprecation cycle — no
consumers); **D3 = SSE-based walk progress** at new endpoint
`/api/bulk/walk-progress`; **D4 = bulk-store action `setCurrentFile`**
driven by the existing apply loop (not callback prop).
**Shape:** 4 substantive tasks + 1 foundation/spec annotation + 1
closure = 6 total. Same shape as Plan 25.

## At a glance

- **Theme A — Foundation** (T0): tiny spec annotation in
  `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` §4 (API
  endpoints) noting the new `/api/bulk/walk-progress` SSE endpoint
  shipping in T3. No other spec text changes (T1/T2/T4 align code to
  existing spec; no contract surface changes).
- **Theme B — CRITICAL ClassifyOutput drift closure** (T1):
  `packages/brain_core/src/brain_core/prompts/schemas.py:34`
  `ClassifyOutput.source_type` Literal regenerated at module-load via
  `Literal[*tuple(s.value for s in SourceType)]` (Python 3.12-only
  syntax; project pin is 3.12 per Plan 16). `SourceType` lives at
  `packages/brain_core/src/brain_core/ingest/types.py:19` (pre-flight
  grep verified at plan-doc author time). Classify prompt template
  `classify.md:12` gains `{source_types}` placeholder; loader
  interpolates from the same enum at render time. Net effect: any
  future SourceType addition (e.g. `xlsx`, `csv`) automatically
  propagates to schema + prompt without a separate change.
- **Theme C — ScannedPDFError hard-remove** (T2): delete the empty
  `class ScannedPDFError(HandlerError)` subclass from
  `packages/brain_core/src/brain_core/ingest/handlers/pdf.py:60`, the
  2 docstring references at pdf.py:6 + pdf.py:28 + the lingering
  retained-for-backward-compat comment at pdf.py:48. Delete the 2
  tests in `test_handler_pdf.py` (`test_class_exists` at line 50 +
  the `issubclass` pin at line 55). Add 1 new regression pin: import
  raises `ImportError`. Verifies "no zombie alias" cleanup.
- **Theme D — Real walk progress via SSE** (T3): new endpoint
  `packages/brain_api/src/brain_api/endpoints/bulk_walk_progress.py`
  exposing `GET /api/bulk/walk-progress?path=<folder>` returning a
  `StreamingResponse` with `text/event-stream` media type. Backend:
  `BulkImporter.plan()` keeps its current one-shot signature
  (consumer-stable); a sibling `plan_streaming()` async generator
  yields progress events alongside the same walk implementation.
  Stdlib-only (no `sse-starlette` dep). Frontend:
  `apps/brain_web/src/components/bulk/walk-interstitial.tsx`
  swaps the 1s `setInterval` for a native `EventSource` subscription;
  shows real files-seen count + current path + elapsed-time. Timer-
  pseudo fallback retained for graceful-degradation if SSE connection
  fails (browser CSP, proxy, etc).
- **Theme E — Per-file filename in apply progress** (T4):
  `apps/brain_web/src/lib/state/bulk-store.ts` gains `currentFile:
  string | null` state + `setCurrentFile(name: string | null)` action;
  cleared on `apply-complete` AND `apply-error` (D11 lifecycle).
  `apps/brain_web/src/components/bulk/step-apply.tsx` apply-loop calls
  `setCurrentFile(item.relpath)` before each `await ingest()` and
  `setCurrentFile(null)` in the `finally` block. Renders
  `<p data-testid="apply-current-file">` line below the progress bar
  with leading-ellipsis truncation at 60 chars (reuses Plan 25
  walk-interstitial truncation pattern, inline-duplicate per CLAUDE.md
  "don't introduce abstractions beyond what the task requires").
- **Closure** (T5): `scripts/demo-plan-26.py` 10-gate demo prints
  `PLAN 26 DEMO OK`. Lessons.md Plan 26 closure section. todo.md row
  26 ✅. Tag `plan-26-critical-fix-and-plan-25-aftermath`.

## Why this plan exists (1 paragraph)

Plan 25 closed cleanly on the user-facing items but the
implementer's T2 review surfaced a pre-existing **correctness gap**:
`ClassifyOutput.source_type` is annotated `Literal["text", "url",
"pdf", "email", "transcript", "tweet"]` — Plan 24 added `docx` and
`pptx` SourceType enum values + handlers + frontmatter support, but
didn't extend the classifier's output schema. Production impact:
classify-routing for `.docx` / `.pptx` files without an explicit
`domain_override` would fail Pydantic validation at LLM-reply parse
time. The Plan 25 T2 test fixture worked around this with
`domain_override`, but real bulk-import flows that lean on
classify-routing would have hit this. T1 of Plan 26 closes it
permanently by deriving the Literal from `SourceType` at runtime —
any future SourceType addition is automatically reflected. T2-T4 are
clean-up items surfaced by Plan 25 T3/T4: dead `ScannedPDFError`
class, timer-driven pseudo-progress on walk phase (the apply phase
already has REAL progress), and the deferred per-file filename
display in the apply UI.

## Locked decisions

**D1** *(T1 Literal sync)* — `ClassifyOutput.source_type` becomes
`Literal[*tuple(s.value for s in SourceType)]` at module-import time.
Python 3.12+ unpacked Literal syntax (PEP 646 extension). Single
source of truth: `SourceType` enum in
`packages/brain_core/src/brain_core/models/source.py` (or wherever
the enum lives — pre-flight grep confirms location at T1 start).
Trade-off vs hardcoded list: marginally less explicit at the type-
annotation site; future-proof for any new SourceType addition.

**D2** *(T2 ScannedPDFError cleanup)* — **Hard-remove** the class.
No internal callers (Plan 25 T3 review verified); no known external
consumers. Removing now avoids dead-code drift; if an unknown
external importer surfaces post-removal, they get a clear
`ImportError` at import-time pointing at the rename. **No
deprecation cycle.** Test-deletion: remove the 2 `ScannedPDFError`-
specific tests in `test_handler_pdf.py:50` + `test_handler_pdf.py:55`
(class-exists + subclass-of); add 1 new regression pin that the
import now raises.

**D3** *(T3 streaming protocol)* — **Server-Sent Events** at new
endpoint `GET /api/bulk/walk-progress?path=<folder>`. One-way
streaming matches the use case (no client→server messages needed
beyond initial subscribe); simpler than WebSocket (no protocol
upgrade dance, no Origin checks beyond what the existing
`OriginCheckMiddleware` already enforces on HTTP scope; auth via
existing query-param-token Plan 5 pattern). Native browser
`EventSource` API in frontend; no library dep.

**D4** *(T4 filename signal source)* — **bulk-store action
`setCurrentFile`** invoked by the existing apply loop. Co-locates
state with phase tracking; keeps step-apply.tsx as pure renderer.
Existing `applyIdx`-driven progress stays unchanged.

**D5** *(T1 cross-cut — classify prompt)* — Classify prompt template
`classify.md:12` gains `{source_types}` placeholder; loader's
`Prompt.render_system()` interpolates from `SourceType` enum at
call-time. Same derivation as Literal; same future-proofing.
Without this, the LLM's prompt would still list the stale set
even though Pydantic validates against the new derived Literal —
the LLM would be told "only these 6 values" but expected to
optionally produce 8.

**D6** *(T3 SSE event schema)* — 4 event types:
1. `walk_started` — `{path: string}` — emitted once at stream open.
2. `walk_progress` — `{files_seen: number, current_path: string}` —
   emitted every 50 files seen (NOT every file — flood control).
3. `walk_complete` — `{total_count: number, plan_id: string}` —
   emitted once at walk-end; `plan_id` references the stored plan
   for the wizard's subsequent classify/apply phases.
4. `walk_error` — `{error_message: string, error_code: string}` —
   emitted on walk failure (permission denied, path missing, etc).

**D7** *(T3 cancellation)* — Frontend calls `EventSource.close()`
on wizard close OR error. Backend async generator's outer
`try/except asyncio.CancelledError` catches the disconnect and
cleans up partial state. No abort signal needed beyond the
ASGI request scope close.

**D8** *(T3 SSE auth)* — Token check via query param matching the
chat WebSocket pattern (Plan 5). `OriginCheckMiddleware` already
enforces Origin on HTTP scope — SSE inherits this for free.
**No new auth surface.**

**D9** *(T3 progress event flood control)* — Emit `walk_progress`
every **50 files** seen, NOT every file. A 10,000-file folder
emits 200 events instead of 10,000 — comfortable for the browser
event loop + still smooth UX (the user sees the counter
incrementing every couple hundred ms during a real walk).

**D10** *(T4 filename truncation)* — Leading-ellipsis truncation
at **60 chars** (matches Plan 25 walk-interstitial). Inline-
duplicate the truncation logic in step-apply.tsx for now;
**don't extract a shared helper** until rule-of-three is met (per
CLAUDE.md "don't introduce abstractions beyond what the task
requires"). If Plan 27 surfaces a third caller, extract then.

**D11** *(T4 lifecycle)* — `currentFile` cleared at BOTH
`apply-complete` AND `apply-error` state transitions, AND in the
apply-loop's `finally` block. Three clears prevent the residual
filename from lingering on the "Done!" or error screens.

**D12** *(T0 spec touch scope)* — Only the new SSE endpoint at
`/api/bulk/walk-progress` warrants a spec annotation. T1/T2/T4 are
correctness or polish fixes that align code to existing contract;
no spec text changes there. T3 spec touch is one bullet under §4
(API endpoints) listing the endpoint + media type + brief
description. Avoid spec sprawl.

**D13** *(test-discipline)* — Per-task verification on
`apps/brain_web/` runs BOTH `pnpm vitest run` AND `pnpm tsc --noEmit`
(per `feedback_tsc_vs_vitest.md`). brain_core verification uses the
canonical iCloud-safe recipe (`feedback_uv_uf_hidden.md`):
`find .venv -name "*.pth" | xargs -I{} chflags 0 {} 2>/dev/null;
uv run pytest <args>` on ONE command line.

**D14** *(no new deps)* — Stdlib-only SSE (FastAPI's
`StreamingResponse` + manual `text/event-stream` formatting). No
`sse-starlette`. Native browser `EventSource`. **Zero new pip or
npm packages.**

**D15** *(unified PR shape)* — One plan, 6 commits per task
boundary (matches Plan 25). Closure cuts a lightweight tag per
project convention. Push gated on user authorization.

## Tech stack

**Backend (Python 3.12, brain_core + brain_api):**
- Pydantic v2 — Literal extension via runtime-derived enum unpack
- FastAPI — `StreamingResponse` with `text/event-stream` media type
- asyncio — async generator for walk-progress emission
- structlog — observability for SSE connection lifecycle

**Frontend (Next.js 15, TypeScript, brain_web):**
- Native browser `EventSource` API — no library dep
- Zustand `bulk-store` — gain `currentFile` state + `setCurrentFile`
- React `useEffect` for EventSource lifecycle management

**No new dependencies.** All implementations use existing pinned
packages.

## Demo gate description

`scripts/demo-plan-26.py` runs 10 gates that exit non-zero on
failure and print `PLAN 26 DEMO OK` on success:

1. T1 — `ClassifyOutput.source_type.__args__` contains all 8
   `SourceType` enum values (`text, url, pdf, email, transcript,
   tweet, docx, pptx`) at module-import time.
2. T1 — Classify prompt rendered text contains the full
   source-type list (verifies `{source_types}` placeholder
   interpolation).
3. T1 — Pydantic validation of `ClassifyOutput(source_type="docx",
   domain="research", confidence=0.9)` succeeds.
4. T2 — `from brain_core.ingest.handlers.pdf import
   ScannedPDFError` raises `ImportError`.
5. T2 — Grep of `packages/brain_core/src/brain_core/ingest/handlers/
   pdf.py` returns zero matches for `ScannedPDFError`.
6. T3 — `BulkImporter.plan_streaming()` yields ≥1 `walk_progress`
   event for a fixture folder containing >50 files.
7. T3 — `GET /api/bulk/walk-progress?path=<fixture>` returns
   `Content-Type: text/event-stream` + the 4 expected event types
   in order (`walk_started` → `walk_progress`×N → `walk_complete`).
8. T3 — SSE event-schema JSON shape verified for each event type.
9. T4 — `bulk-store` `setCurrentFile("foo/bar.txt")` updates
   `currentFile`; `setCurrentFile(null)` clears it. Verified via
   Zustand store snapshot.
10. T4 — `step-apply.tsx` test renders `apply-current-file`
    element when `currentFile` is non-null; renders nothing when
    null. Verified via React Testing Library.

## Tasks

### T0 — Plan-doc spec annotation (foundation)

**Owning subagent:** brain-core-engineer (light-touch spec edit; Plans 24-25 precedent for foundation tasks)
**Files touched:**
- `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` — §4 API
  endpoints subsection gains one bullet describing
  `GET /api/bulk/walk-progress` SSE endpoint (media type +
  event schema reference).

**Acceptance:**
- One-bullet addition. No other spec edits.
- Commit subject prefix: `docs(plan-26): T0 — spec §4 SSE walk-progress endpoint annotation`

### T1 — CRITICAL ClassifyOutput Literal runtime-derive + classify prompt placeholder

**Owning subagent:** brain-core-engineer
**Files touched:**
- `packages/brain_core/src/brain_core/prompts/schemas.py` — line 34
  Literal changes from hardcoded 6-value list to
  `Literal[*tuple(s.value for s in SourceType)]`. Imports `SourceType`
  from `brain_core.ingest.types` (pre-flight grep verified at plan-doc
  author time: `packages/brain_core/src/brain_core/ingest/types.py:19`).
- `packages/brain_core/src/brain_core/prompts/classify.md` — line 12
  bullet becomes `**source_type**: one of {source_types}. Infer from
  the content shape if not stated.`
- `packages/brain_core/src/brain_core/prompts/loader.py` OR a new
  callsite in the classify-prompt-builder — interpolate
  `source_types` placeholder via comma-joined backtick-wrapped
  `SourceType` values (e.g. `` `text`, `url`, `pdf`, ... ``).
- `packages/brain_core/tests/prompts/test_classify.py` (or
  equivalent) — add 2 tests: (a) Literal contains all enum values;
  (b) rendered prompt contains all enum values.
- `packages/brain_core/tests/prompts/test_schemas.py` — add 1 pin:
  Pydantic validation accepts `source_type="docx"` and
  `source_type="pptx"`.

**Acceptance:**
- All existing classify tests still pass.
- New tests RED-on-revert.
- Demo gates 1-3 green.
- Commit subject prefix: `fix(plan-26): T1 — ClassifyOutput Literal + classify prompt runtime-derive from SourceType`

### T2 — ScannedPDFError hard-remove

**Owning subagent:** brain-core-engineer
**Files touched:**
- `packages/brain_core/src/brain_core/ingest/handlers/pdf.py` —
  delete class definition at line 60; delete docstring references at
  lines 6 + 28; delete "retained as alias-friendly export" comment
  at line 48.
- `packages/brain_core/tests/ingest/test_handler_pdf.py` — delete the
  import-line reference at line 6 (just remove `, ScannedPDFError`
  from the import); delete the 2 ScannedPDFError-specific test
  blocks; add 1 new regression pin verifying that
  `from brain_core.ingest.handlers.pdf import ScannedPDFError`
  raises `ImportError`.

**Acceptance:**
- `grep -rn "ScannedPDFError" packages/brain_core/` returns ZERO
  matches outside the new `ImportError` regression pin.
- All other pdf-handler tests still pass.
- Demo gates 4-5 green.
- Commit subject prefix: `refactor(plan-26): T2 — hard-remove unused ScannedPDFError empty subclass`

### T3 — SSE walk-progress endpoint + frontend EventSource

**Owning subagent:** brain-core-engineer (backend) → brain-frontend-engineer (frontend)
**Files touched (backend):**
- `packages/brain_core/src/brain_core/ingest/bulk.py` — new method
  `BulkImporter.plan_streaming(...) -> AsyncIterator[WalkProgressEvent]`
  alongside existing `plan()`. Reuses the same walk implementation
  (extract the walk loop into a private helper if needed for DRY).
- `packages/brain_core/src/brain_core/ingest/walk_events.py` (NEW)
  — Pydantic models for the 4 event types (`WalkStarted`,
  `WalkProgress`, `WalkComplete`, `WalkError`). Each derives from a
  shared `WalkEvent` base with a `type: Literal[...]` discriminator.
- `packages/brain_api/src/brain_api/endpoints/bulk_walk_progress.py`
  (NEW) — `GET /api/bulk/walk-progress` endpoint returns
  `StreamingResponse` with `text/event-stream` media type;
  serializes events as `data: <json>\n\n`.
- `packages/brain_api/src/brain_api/app.py` — register new router.
- Tests: `packages/brain_core/tests/ingest/test_bulk_streaming.py`
  (NEW) — 5-6 unit tests for `plan_streaming()`. `packages/brain_api/
  tests/endpoints/test_bulk_walk_progress.py` (NEW) — 4-5
  integration tests for SSE endpoint.

**Files touched (frontend):**
- `apps/brain_web/src/lib/api/bulk-progress.ts` (NEW) — EventSource
  wrapper. Exports `subscribeWalkProgress(path, callbacks)` →
  `() => void` (close handle). Translates SSE event JSON into
  typed event objects mirroring backend Pydantic models.
- `apps/brain_web/src/components/bulk/walk-interstitial.tsx` —
  replace 1s `setInterval` with `useEffect`-managed EventSource
  subscription. On `walk_progress` events update `filesSeen` +
  `currentPath` state. On `walk_complete`/`walk_error` close the
  subscription. Timer-pseudo retained as graceful-degradation
  fallback if EventSource fails to connect within 2s (`onerror`
  before `onopen`).
- Tests: `apps/brain_web/src/components/bulk/walk-interstitial.test.tsx`
  — add 3-4 tests for the EventSource lifecycle (mocked
  EventSource).

**Acceptance:**
- Backend: SSE endpoint serves correctly-formatted event stream;
  4 event types serialize/deserialize round-trip.
- Frontend: walk-interstitial renders real files-seen count; falls
  back to timer-pseudo on connection failure.
- Demo gates 6-8 green.
- Commit subject prefix: `feat(plan-26): T3 — SSE walk-progress endpoint + frontend EventSource wiring`

### T4 — Per-file filename in apply progress UI

**Owning subagent:** brain-frontend-engineer
**Files touched:**
- `apps/brain_web/src/lib/state/bulk-store.ts` — add `currentFile:
  string | null` state field; add `setCurrentFile(name: string |
  null)` action; clear in the existing `complete()` + `error()`
  state-machine transitions.
- `apps/brain_web/src/components/bulk/step-apply.tsx` — in the
  existing apply for-loop, call `setCurrentFile(item.relpath)` before
  `await ingest()`; in the `finally` block, call
  `setCurrentFile(null)`. Render `<p data-testid="apply-current-file"
  className="text-sm text-muted-foreground">Current: {truncated}</p>`
  below the existing progress bar when `currentFile` is non-null.
- Tests: `apps/brain_web/src/components/bulk/step-apply.test.tsx`
  — add 2 tests for the new `apply-current-file` element (renders
  truncated path when set; renders nothing when null);
  `apps/brain_web/src/lib/state/bulk-store.test.ts` — add 2 tests
  for `setCurrentFile` + lifecycle clearing.

**Acceptance:**
- Filename surfaces in apply UI during apply phase.
- Cleared on complete/error/finally.
- Truncation at 60 chars with leading ellipsis (matches Plan 25
  walk-interstitial pattern).
- Demo gates 9-10 green.
- Commit subject prefix: `feat(plan-26): T4 — per-file filename display in apply progress UI`

### T5 — Closure

**Owning subagent:** brain-core-engineer (controller-driven finalization)
**Files touched:**
- `scripts/demo-plan-26.py` (NEW) — 10-gate demo prints
  `PLAN 26 DEMO OK`.
- `tasks/lessons.md` — append Plan 26 closure section.
- `tasks/todo.md` — row 26 marked ✅; Plan 27 candidate scope
  tail block organized (3 NEW Plan-25-surfaced removed; 1 Plan-25
  + 6 Plan-24-surfaced + 16 Plan 22 carry-forwards + 4 preserved
  NOT-DOINGs remain).
- `tasks/plans/26-critical-fix-and-plan-25-aftermath.md` — fill
  `## Review` section.

**Acceptance:**
- Demo runs clean.
- Tag `plan-26-critical-fix-and-plan-25-aftermath` cut locally.
- DO NOT push — controller surfaces push authorization to user.

## Owning subagents

- **brain-core-engineer** — T1, T2, T3 backend, T5 demo
- **brain-frontend-engineer** — T3 frontend, T4
- **brain-installer-engineer** — T0 spec annotation (one bullet)

## Workflow rules

- Per-task: implementer subagent → spec compliance review → code
  quality review → commit. Combined-review pattern per Plan 16 D35.
- Per-task verification: brain_core tests + brain_api tests (where
  touched) + brain_web tests (`pnpm vitest run` + `pnpm tsc --noEmit`
  where touched). RED-on-revert receipt for every new pin.
- Pause cadence: every 2-3 tasks for user check-in. Plan 26 is
  smaller than Plan 25 so 1 pause at T2-T3 boundary should suffice.
- Plan-doc reality-gap discipline: per Plan 25 T4 lesson, if an
  implementer finds the plan-doc spec doesn't match implementation
  reality, surface immediately + adjust the plan-doc inline.

## File inventory (summary)

**New files:**
- `packages/brain_core/src/brain_core/ingest/walk_events.py` (T3)
- `packages/brain_api/src/brain_api/endpoints/bulk_walk_progress.py` (T3)
- `apps/brain_web/src/lib/api/bulk-progress.ts` (T3)
- `packages/brain_core/tests/ingest/test_bulk_streaming.py` (T3)
- `packages/brain_api/tests/endpoints/test_bulk_walk_progress.py` (T3)
- `scripts/demo-plan-26.py` (T5)

**Modified files:**
- `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` (T0)
- `packages/brain_core/src/brain_core/prompts/schemas.py` (T1)
- `packages/brain_core/src/brain_core/prompts/classify.md` (T1)
- `packages/brain_core/src/brain_core/prompts/loader.py` (T1, possibly)
- `packages/brain_core/src/brain_core/ingest/handlers/pdf.py` (T2)
- `packages/brain_core/tests/ingest/test_handler_pdf.py` (T2)
- `packages/brain_core/src/brain_core/ingest/bulk.py` (T3)
- `packages/brain_api/src/brain_api/app.py` (T3)
- `apps/brain_web/src/components/bulk/walk-interstitial.tsx` (T3)
- `apps/brain_web/src/components/bulk/walk-interstitial.test.tsx` (T3)
- `apps/brain_web/src/lib/state/bulk-store.ts` (T4)
- `apps/brain_web/src/lib/state/bulk-store.test.ts` (T4)
- `apps/brain_web/src/components/bulk/step-apply.tsx` (T4)
- `apps/brain_web/src/components/bulk/step-apply.test.tsx` (T4)
- `tasks/lessons.md` (T5)
- `tasks/todo.md` (T5)
- `tasks/plans/26-critical-fix-and-plan-25-aftermath.md` (T5)

**Test growth estimate:**
- brain_core: +6 (T1: +3; T2: -2 + 1 = -1 net; T3: +5)
- brain_api: +5 (T3)
- brain_web: +9 (T3: +3; T4: +4 + 2 store tests)

## T0-T5 outcomes

(Filled at execution time per task.)

## T0 outcome

**Commit:** `61d4f33`. **Anchor deviation caught by implementer:** plan-doc said "§4 API endpoints" but the spec has no such subsection (§4 is "Vault schema"). Implementer routed the annotation to §6 "Streaming events" (line 369) — the spec's actual catalog for `brain_api` streaming surface — alongside the existing WebSocket event list. **2-line diff:** one paragraph + one blank line. **No other spec edits.** Plan-doc reality-gap pattern from Plan 25 T4 fired again — implementer judgment on the right anchor was correct.

## T1 outcome

**Commit:** `f15a243`. **Lines changed:** +103/−6 across 7 files. **Production call sites updated:** `classifier.py:66`, `pipeline.py:1138` (both `render_system()` callers gained `source_types=_SOURCE_TYPES_RENDERED` kwarg). **Test sites updated:** `test_classifier.py:118`, `test_classify_template.py:38` (both pass-through fixtures gained `source_types`). **Schema change pattern:** `_SOURCE_TYPE_VALUES = tuple(s.value for s in SourceType)` module-level constant + `Literal[*_SOURCE_TYPE_VALUES]` with `type: ignore[valid-type]` (mypy doesn't yet understand PEP 646 Literal unpacking; Python 3.12 runtime + Pydantic class-creation both resolve it correctly). **Rendered-list pattern:** `_SOURCE_TYPES_RENDERED = ", ".join(f"`{s.value}`" for s in SourceType)` (backtick-wrapped enum values joined by commas). **Test growth:** brain_core 1274 → 1278 (+4 new in `test_classify.py`); brain_mcp classify-related 5 pass / 1 skip unchanged. **RED-on-revert receipts verified:** stashing `schemas.py` → 3 schema tests fail with `literal_error … input_value='docx'`; stashing `classify.md` → `test_classify_prompt_advertises_all_source_types` fails with `'`docx`' missing from rendered`. **No new deps, no SourceType enum changes, no other Pydantic schema touched.**

## T2 outcome

**Commit:** `7f20b4d`. **Lines changed:** `pdf.py` module docstring (lines 1-31 collapsed to 1-20), stale comment at threshold constant block (former lines 45-49 trimmed), `class ScannedPDFError(HandlerError):` deleted (former lines 60-67). `test_handler_pdf.py` import line 6 narrowed; `test_pdf_handler_low_text_triggers_image_mode` docstring (lines 26-30) cleaned of Pre-Plan-25 narrative; `test_scanned_pdf_error_remains_handler_error_subclass` deleted (1 test, NOT 2 — implementer caught brief's off-by-one); new `test_scanned_pdf_error_no_longer_exported` ImportError pin added. **Grep verification:** zero matches in `src/`; 2 in `tests/` both inside the new regression pin (docstring + import-under-test). **Test count:** −1 net (1 deletion + 1 new pin). All pdf-handler tests green; full brain_core sweep green. **No PDFHandler logic touched; no deprecation cycle (D2 hard-remove).**

## T3 outcome (BACKEND phase complete; FRONTEND phase pending)

**Backend commit:** `f12e357`. **5 new files:** `walk_events.py` (4 Pydantic v2 models + `WalkEvent` discriminated-union alias), `test_walk_events.py`, `test_bulk_streaming.py`, `bulk_walk_progress.py` endpoint, `test_bulk_walk_progress_endpoint.py`. **2 modified files:** `bulk.py` (new `plan_streaming()` async generator), `app.py` (router registration alongside Plan 08 endpoints). **Test growth:** brain_core 1278→1289 (+11: 5 walk_events models + 6 plan_streaming behaviors); brain_api 223→228 (+5 endpoint behavior tests). **Full sweeps green; mypy --strict clean on new code.** **Key implementation calls:**
- **Pre-check `source_root` BEFORE `Path.glob()`** — `glob` swallows `FileNotFoundError` / `PermissionError` and silently returns empty; without the pre-check the error event types would never fire. Implementer caught at exec time.
- **`_check_sse_token` mirrors `check_ws_token`** — FastAPI's required-Query rejects missing token as 422 BEFORE the 403 token-mismatch path; test pins both branches separately.
- **Stream wrapper does NOT re-raise after emitting `WalkError`** — the error frame is already on the wire; re-raising would surface a 500 the client can't consume mid-stream. `CancelledError` IS re-raised (clean request-scope unwind).
- **Stateless `plan_id`** (D6 option a) — UUID4 correlation token only; wizard re-calls `plan()` separately for actual items.
- **No new deps; stdlib-only SSE** (D14 verified).

**FRONTEND phase complete.** **Frontend commit:** `bf3bf5f`. **New files:** `lib/api/bulk-progress.ts` (typed EventSource wrapper exporting `subscribeWalkProgress` + 5-callback shape `onStarted/onProgress/onComplete/onError/onConnectionError` + idempotent close handle that auto-closes on terminal frames). **Modified files:** `walk-interstitial.tsx` (added `useEffect` SSE subscription rendering live `filesSeen` + `currentPath`; elapsed-time `setInterval` kept independent; `data-streaming-mode` attribute tracks `connecting`/`live`/`timer-fallback` mode). **Test growth:** walk-interstitial.test.tsx 0→6 (happy path + walk_error toast + transport-error-before-frame fallback + transport-error-after-frame terminal + unmount cleanup + no-token fallback). Existing Plan 25 T4 `tests/unit/bulk-wizard.test.tsx` (5 tests) still green — they don't seed a token so new `useEffect` short-circuits to timer-fallback before opening EventSource. **Auth pattern:** `getToken()` accessor from `@/lib/state/token-store` (zustand vanilla getter; Plan 08 T2 precedent, mirrors chat WS `?token=<hex>` query-param convention `_check_sse_token` enforces). **3 graceful-degradation paths:**
- `onConnectionError` BEFORE first frame → `setFallbackToTimer(true)` (Plan 25 T4 layout)
- `onConnectionError` AFTER first frame → danger toast + `endWalk(false)` (no fallback; live mode failed mid-stream)
- No token in store → silent fallback (no EventSource opened)

**Verification:** `pnpm vitest run` 88 files / 610+1 skipped passing; `pnpm tsc --noEmit` clean. **No npm deps added.**

**T3 combined backend + frontend totals:** 6 new files, 3 modified files; +11 brain_core tests + +5 brain_api tests + +6 brain_web vitest tests = +22 across the stack.

## T4 outcome

**Commit:** `c74ea6a`. **Modified files:** `bulk-store.ts` (gained `currentFile: string | null` state + `setCurrentFile` action + 3 clear sites), `step-apply.tsx` (gained `currentFile` selector + inline `truncatePath(path, max=60)` helper + `apply-current-file` JSX block below progress bar). **New test files:** `bulk-store.test.ts` (+4 tests), `step-apply.test.tsx` (+3 tests). **Test growth:** brain_web vitest +7 (617 passed / 1 skipped total). `tsc --noEmit` clean. **Truncation helper:** inline at `step-apply.tsx` per D10; signature `function truncatePath(path: string, max = 60): string` returning `path` unchanged when ≤ max, otherwise `"…" + path.slice(-(max-1))`. Mirrors walk-interstitial pattern verbatim (rule-of-three NOT yet met; no shared extraction). **D11 lifecycle 3 clear-sites verified:**
- **Complete transition** — `startApply` outer `finally` block sets `currentFile: null` alongside `phase: "complete"`
- **Error transition** — `endWalk(false)` sets `currentFile: null` alongside `phase: "error"` (and existing walk-marker resets)
- **Apply-loop finally** — same physical site as (1) since the outer `try/finally` wraps the entire for-loop; fires regardless of completion/cancellation/throw

Effectively 2 distinct physical sites collapsing the 3 D11 lifecycle scenarios. **No new deps, no backend touches, no walk-interstitial touches.**

## Plan 27 candidate scope

(Filled at T5 close — will inherit Plan 26's surfaced items + the
remaining 25 carry-forwards from Plan 25's tail block, minus the 4
addressed in Plan 26.)

## Review

(Filled at T5 close.)
