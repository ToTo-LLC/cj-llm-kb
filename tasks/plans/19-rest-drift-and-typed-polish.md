# Plan 19 — REST-endpoint drift + typed-surface polish closure

**Authored:** 2026-05-11 (post Plan 18 close on 2026-05-11, tag
`plan-18-typed-surface-drift-closure` at `609f1aa`).
**Scope:** Close the Track A REST-endpoint drift (`/api/upload`
`UploadResult` parallel to Plan 18 T2's MCP-tool audit, plus an audit
of the rest of `brain_api/endpoints/*`), the Track B `cost === 0`
ingest-row badge UX, the Track C 4 informational extra-in-backend
DRIFTs deferred from Plan 18 T2 (`recent` outer / `proposeNote` /
`listPendingPatches` outer / `configSet` + 7 downstream), and the
Track D `planToFiles` type-tighten that eliminates the T3.9 consumer
cast. All four tracks are typed-surface or UX-fallout work from
Plan 18 closure.
**Shape:** 6 substantive tasks across 4 themes + 1 closure task.
Mirrors Plan 18 D5 / Plan 17 D2 / Plan 16 D35: per-task ~20-100 LOC
PR budget; combined spec + code-quality review per task.

## At a glance

- **Theme A — REST-endpoint drift closure** (T1, T2): audit all 3
  REST endpoint files in `packages/brain_api/src/brain_api/endpoints/`
  against their TS consumers; fix every DRIFT-class finding.
- **Theme B — Cost-badge UX fallout from Plan 18** (T3): suppress the
  ingest-row cost badge when `cost === 0` per locked direction.
- **Theme C — Informational extra-in-backend DRIFTs** (T4): bundle the
  4 cosmetic DRIFTs from Plan 18 T2 audit (no live consumers) — TS
  narrow + Python key-set pin per sub-fix; `configSet` is a single
  root that propagates to 7 wrappers.
- **Theme D — Type-tighten** (T5): `planToFiles` accepts
  `BulkImportPlannedItem[]` directly; eliminate the `as unknown` cast
  the T3.9 consumer needed.
- **Closure** (T6): demo + lessons + todo.md + tag
  `plan-19-rest-drift-and-typed-polish`.

## Why this plan exists (1 paragraph)

Plan 18 closed the typed-wrapper-vs-runtime drift class on the
MCP-tool surface (`tools.ts`'s 38 wrappers; 11 T1-class DRIFTs fixed
inline + 4 informational extras deferred). Three live consumer bugs
surfaced inline (Inbox silently empty / undo toast always 0 /
budget-override toast from prop default). The Plan 18 T3.5 review
surfaced that `apps/brain_web/src/lib/ingest/upload.ts:24-30` declares
an `UploadResult` interface for the `/api/upload` HTTP endpoint that
doesn't match `packages/brain_api/src/brain_api/endpoints/upload.py:91-95`'s
actual `UploadResponse = {patch_id: str}` — the same T1-class drift
shape Plan 18 closed, but on the REST transport. The Plan 18 closure
lesson "typed-wrapper-vs-runtime drift IS a *class*, not an *instance*
— when one drifts, audit ALL siblings" applies analogously: the REST
endpoint surface needs its own audit pass. Plan 19 does that audit
(small surface: 3 endpoint files), fixes every finding, and bundles
the remaining typed-surface / UX polish carry-forwards (Tracks B, C,
D) in one comprehensive plan rather than splitting them across
multiple smaller plans (the polish items are individually tiny and
share the same review style).

## Locked decisions

| # | Decision | Status | Why |
|---|---|---|---|
| D1 | **Track A scope: audit ALL 3 REST endpoint files in `packages/brain_api/src/brain_api/endpoints/`** (`setup_status.py`, `token.py`, `upload.py`), not just fix the known `/api/upload` drift. Append findings inline to this plan doc as `## T1 audit findings`. | locked (user 1.A) | Mirrors Plan 18 T2 pattern. The REST surface is small (3 files, < 400 LOC total) — audit time is minutes; catches the class, not just the instance. Plan 18 lesson "sample size of one is misleading; when one drifts, audit the rest" applies. |
| D2 | **Plan 19 covers Tracks A+B+C+D in ONE comprehensive plan**, not split across multiple smaller plans. ~5-7 substantive tasks + closure. | locked (user 2.A) | All 7 actionable candidates are typed-surface or UX-fallout work from Plan 18 — same review style, same mental model. Plan 18 successfully shipped 11 sub-fixes inline (T3.1-T3.11); pattern proven at this scale. Splitting introduces plan-doc / demo / closure overhead per slice without proportional benefit. |
| D3 | **Track C (4 informational extras) bundled into ONE task (T4) with 4 sub-fixes** (T4.1-T4.4). Same TS-narrow + Python key-set pin pattern per item; `configSet` is a single root fix propagating to 7 downstream wrappers. | locked (user 3.A) | All 4 sub-fixes are cosmetic severity (no live consumers), same pattern (TS narrow + Python key-set pin), ~30-50 LOC each. Bundling keeps per-task review focused. Plan 18 T3.1-T3.11 were split because 3 of them closed LIVE consumer bugs needing different regression tests — Track C has no live consumers so finer splitting adds overhead without proportional value. |
| D4 | **Track B (`cost === 0` UX): suppress badge when `cost === 0`.** Single conditional change in `apps/brain_web/src/components/inbox/source-row.tsx:109`. | locked (user B.A) | Cleaner visually; sidesteps the `$0.000` semantic ambiguity (free? unknown? not-billed?). Plan 18 lesson "when a typed-surface fix exposes a previously-hidden field, the immediate UX question is what the default value means to the user" — suppression is the most decisive resolution. |
| D5 | **Preserved Plan 17 / earlier carry-forwards (items 8-11) stay NOT-DOING in Plan 20 candidate tail block at Plan 19 closure.** | locked (user C.A) | All four have explicit not-yet-actionable criteria: `seedBrainMd`/`seedScope` at 3/5 callers (rule-of-three threshold); per-thread cross-domain confirmation = architectural NO per spec §3 + Plan 16 D36 (re-litigating requires spec amendment); topbar scope chip drift = lesson-only per Plan 12; PEP 703 `_cached_ctx` = 3.14 timeline trigger. Preserve the rationale-per-item to avoid future plan authors re-proposing without context. |
| D6 | **Audit deliverable shape: append findings inline to THIS plan doc as `## T1 audit findings`.** Markdown table with one row per REST endpoint + verdict (OK / MINOR / DRIFT) + notes. Plan 18 D2 / Plan 17 T9 precedent. | locked per Plan 18 D2 | Audit findings are point-in-time observations against current handler shapes; the plan doc is their natural home. Separate report files sprawl; JSON manifests are an awkward shape for prose. |
| D7 | **Demo gate: per-item closure assertion, no gate-count target.** | locked per Plan 18 D4 / Plan 17 D7 | Gate count is not pinned; closure shape branches on T1 findings (T2 demo branches per-finding). |
| D8 | **Per-task review: combined spec + code-quality** held across 47 tasks in Plan 16; 18 in Plan 17; 5 in Plan 18. | locked per Plan 16 D35 / Plan 17 D2 / Plan 18 D5 | No reason to re-litigate at the Plan-15+ polish-pass scale. |
| D9 | **No new dependencies.** Plan 19 ships zero new pip / npm packages. | locked per Plan 18 D6 / Plan 17 D6 | All Plan 19 work is closure / audit / docs / narrow / fix. |
| D10 | **Push at Plan 19 close, after user authorization.** Single `git push` covers all Plan 19 commits. | locked per Plan 18 D7 | Standard cadence — local work is tagged and visible via `git log`; CI surfaces residuals at one synchronization point. |
| D11 | **Sequential subagent dispatch via `superpowers:subagent-driven-development`.** | locked per Plan 16 D2 / Plan 17 D3 / Plan 18 D8 | Combined review per task plus sequential dispatch held across three prior polish-scale plans. |

## Tech stack

Same as Plans 16 + 17 + 18: Python 3.12, pydantic v2, mypy --strict,
ruff, vitest, Playwright. No new tools. No new dependencies. CI runs
on macos-14 + windows-2022 per Plan 14's matrix.

## Demo gate description

`scripts/demo-plan-19.py` asserts, in sequence:

1. **(T1.a)** `tasks/plans/19-rest-drift-and-typed-polish.md` contains
   a non-empty `## T1 audit findings` section (markdown table with
   ≥3 rows — one per REST endpoint file).
2. **(T1.b)** The audit findings table includes at minimum the
   `/api/upload` row marked **DRIFT** (the known finding from
   Plan 18 T3.5 review).
3. **(T2)** Branch on T1 findings:
   - For each row marked **DRIFT** in T1: assert the TS interface at
     the cited line has been narrowed to match the backend shape
     (regex match on the narrowed interface body in `upload.ts` and
     any other affected TS file).
   - Assert a Python pin test exists for each REST endpoint with a
     fixed `BaseModel` response (mirrors Plan 18 T3's key-set pin
     pattern but adapted to FastAPI's response_model — assert the
     response_model class has exactly the declared field set).
4. **(T3)** `apps/brain_web/src/components/inbox/source-row.tsx`
   contains a conditional that suppresses the cost badge when
   `cost === 0` — regex match on the suppression pattern (e.g.,
   `cost > 0 ? ...` or `cost === 0 ? null : ...`). Inline breadcrumb
   comment at `inbox-store.ts:159` updated to point at Plan 19
   closure (or removed entirely as resolved).
5. **(T4)** Four Track C narrows landed:
   - **(T4.1)** `tools.ts` `recent()` return type widened to include
     `limit_used: number` (outer-shape extra).
   - **(T4.2)** `tools.ts` `proposeNote()` return type widened to
     include `status: string`.
   - **(T4.3)** `tools.ts` `listPendingPatches()` return type widened
     to include `count: number` (outer-shape extra).
   - **(T4.4)** `tools.ts` `configSet()` return type widened to
     include `status`, `persisted: boolean`, `note: string`. Same
     widening propagates to 7 `configSet`-routed wrappers
     (`setDomainOverride` / `setPrivacyRailed` / `setDomainBudget` /
     `setDomainRateLimit` / `setDomainAutonomy` / `setActiveDomain` /
     `setCrossDomainWarningAcknowledged`) via the single root.
   - Four Python key-set pins in
     `packages/brain_core/tests/tools/` matching the 4 backend
     handlers (`recent.py`, `propose_note.py`,
     `list_pending_patches.py`, `config_set.py`).
6. **(T5)** `tools.ts` `planToFiles()` signature accepts
   `BulkImportPlannedItem[]` directly (regex match on the parameter
   type). The consumer cast at
   `apps/brain_web/src/components/bulk/step-pick-folder.tsx` is
   removed (grep for the `as unknown as Array<Record<string, unknown>>`
   pattern returns zero hits at the planToFiles caller site).
7. **(T6)** `tasks/todo.md` row 19 marked ✅; `tasks/lessons.md` has
   a Plan 19 closure section; final stdout line is `PLAN 19 DEMO OK`.

## Tasks

### Theme A — REST-endpoint drift closure

#### T1 — `brain_api/endpoints/*` audit + findings table

**Files:**
- Modify (findings only): `tasks/plans/19-rest-drift-and-typed-polish.md`
  — append a `## T1 audit findings` section with one row per REST
  endpoint file + TS consumer + verdict (OK / MINOR / DRIFT) + notes.

**Goal:** Mirror Plan 18 T2's audit shape on the REST surface. Plan
18 T2 audited the 38 typed wrappers in `tools.ts` (MCP-tool transport)
and surfaced 15 DRIFT rows. Plan 19 T1 audits the REST endpoint
surface (`packages/brain_api/src/brain_api/endpoints/*`) against
their TS consumers in `apps/brain_web/src/`. The REST surface is
small (3 endpoint files, < 400 LOC total).

**What to do:**
1. **Enumerate.** List every endpoint file in
   `packages/brain_api/src/brain_api/endpoints/` and its declared
   `response_model` (Pydantic `BaseModel`):
   - `upload.py` — `POST /api/upload` → `UploadResponse = {patch_id: str}`
   - `setup_status.py` — `GET /api/setup-status` → `SetupStatusResponse = {has_token, is_first_run, vault_exists, vault_path}`
   - `token.py` — `GET /api/token` → `TokenResponse = {token: str}`
2. **Locate TS consumers.** For each endpoint, find the TS-side caller
   that consumes the response (grep `/api/upload`, `/api/setup-status`,
   `/api/token` across `apps/brain_web/src/`). Specifically:
   - `/api/upload` → `apps/brain_web/src/lib/ingest/upload.ts:66-95`
     declares `UploadResult` for the response body.
   - `/api/setup-status` → likely `apps/brain_web/src/lib/setup/` or
     `lib/api/` somewhere; verify shape against backend.
   - `/api/token` → likely `apps/brain_web/src/lib/state/token-store.ts`
     or similar; verify shape against backend.
3. **Verify.** For each, compare the TS-declared shape (interface,
   type alias, or inline `as` cast) against the backend's
   `BaseModel` field set. Compare key sets + types:
   - TS-declared required keys present in backend? ✓ or ✗
   - Backend-emitted keys present in TS (or `[extra]` index sig)? ✓ or ✗
   - Type compatibility (string vs nullable etc.)?
4. **Categorize verdicts** (Plan 18 T2 legend):
   - **OK** — TS and backend agree exactly on key set + types.
   - **MINOR** — TS uses optional fields (`?:`) or
     `[extra: string]: unknown` index sig that absorbs the
     discrepancy; runtime reads degrade gracefully.
   - **DRIFT** — TS declares required fields backend doesn't emit
     (T1-class — silently `undefined` at runtime) OR backend emits
     keys not declared in TS AND TS has no index-sig escape hatch
     (TS callers can't read those fields without an `as`-cast).
     T2 fix candidates.
5. **File findings** as a markdown table appended to this plan doc
   under `## T1 audit findings`. Columns: REST endpoint | Backend
   model (file:line) | TS consumer (file:line) | Verdict | Notes.

**Known seed:** `/api/upload` is already known to be **DRIFT**
(backend `UploadResponse = {patch_id: str}`; TS `UploadResult = {patch_id: string | null; applied: boolean; domain: string | null; [extra]}` —
TS-required `applied` and `domain` NEVER emitted by backend; backend
`patch_id` is non-nullable, TS nullable — TS is more permissive there
which is fine; the runtime issue is `applied`/`domain` silently
`undefined`). Auditor should re-derive this finding plus surface any
others.

**Per-task review:** combined spec + code-quality. Reviewer
spot-checks 2-3 random rows by re-reading the backend code (Plan 18
T2 precedent — sample 3-4 rows and re-derive verdict). Reviewer
confirms the table covers all 3 endpoint files.

#### T2 — Fix REST-endpoint drift findings

**Files (branches on T1 verdict):**

**For each DRIFT-class row in T1:**
- Modify: the relevant TS file (`upload.ts` for `/api/upload`; other
  TS consumer files for any other findings) — narrow the TS interface
  to match the backend's `BaseModel` shape. Backend remains source
  of truth (same direction as Plan 18 T3's D1).
- Verify the consumer code path. For `/api/upload` specifically:
  - The fallback at `upload.ts:91-95` currently fills `applied: false,
    domain: null` for the empty-data path. Post-narrow, this fallback
    should reduce to `{patch_id: null}` (or drop entirely if the
    backend response_model guarantees `patch_id: str` non-null —
    which it does per `UploadResponse(BaseModel) { patch_id: str }`).
  - Grep `result.applied` / `result.domain` / `uploadResult.applied`
    etc. across `apps/brain_web/src/` to check for live consumers
    reading the about-to-be-removed fields. If any exist, that's a
    live consumer bug analogous to Plan 18 T3.1 / T3.7 / T3.11 —
    flag inline + close in this task.
- Create or modify a Python pin test for the affected endpoint:
  `packages/brain_api/tests/test_endpoint_<name>_shape.py` (or
  extend the existing file if one exists). Assert the response_model's
  `model_fields.keys()` matches the expected key set exactly. Pattern:
  ```python
  from brain_api.endpoints.upload import UploadResponse
  def test_upload_response_field_set():
      assert set(UploadResponse.model_fields.keys()) == {"patch_id"}
  ```
  This mirrors Plan 18 T3's key-set pin pattern but adapted to
  FastAPI's response_model surface (no need to invoke the handler —
  the model field set is the contract).

**Goal:** close the audit cleanly. Every DRIFT row produces a TS
narrow + Python pin + (if applicable) a fixed live consumer.

**What to do:**
1. **Read T1 findings.** Enumerate DRIFT rows.
2. **Per-finding:**
   a. Narrow the TS interface.
   b. Audit the TS fallback / consumer chain for the field set;
      adjust as needed; close any live consumer bugs surfaced.
   c. Add a Python pin test asserting the response_model's field
      set is exact.
3. **Append `## T2 outcome`** to this plan doc explaining the
   per-finding receipts. If T1 surfaces zero DRIFT (unlikely given
   the `/api/upload` known seed), T2 closes as zero-fix with a
   pointer to T1's findings table.

**Per-task review:** combined spec + code-quality. Reviewer confirms
(a) each narrowed TS interface compiles cleanly against the backend
shape (no orphaned `as`-cast leftovers); (b) each Python pin test
fails RED if a key is added/removed from the response_model;
(c) any live consumer bugs are closed with the same care as Plan 18
T3.1 / T3.7 / T3.11 (regression test against the bug's actual
symptom, not just the type narrowing).

### Theme B — Cost-badge UX fallout

#### T3 — Suppress ingest-row cost badge when `cost === 0`

**Files:**
- Modify: `apps/brain_web/src/components/inbox/source-row.tsx`
  — line 109 conditional: render the cost badge only when
  `cost > 0`. Locked direction per D4: suppress for cached /
  zero-token rows.
- Modify: `apps/brain_web/src/lib/state/inbox-store.ts:159` —
  update the inline "Plan 19 candidate" breadcrumb comment to
  point at Plan 19 closure resolution (or remove the comment
  entirely as resolved).
- Create or modify: `apps/brain_web/tests/unit/source-row.test.tsx`
  (or wherever the existing source-row tests live) — add a unit
  test asserting (a) badge renders when `cost > 0`; (b) badge
  does NOT render when `cost === 0`; (c) badge does NOT render
  when `cost` is undefined (defensive — same suppression path).

**Goal:** Close Track B per locked D4. The `$0.000` rendering for
cached / zero-token rows is visually noisy and semantically
ambiguous (free? unknown? not-billed?); suppression is decisive.

**What to do:**
1. **Apply suppression.** Change the conditional render at
   `source-row.tsx:109` from `cost ? <Badge>${cost.toFixed(3)}</Badge> : ...`
   (or current shape) to `cost > 0 ? <Badge>${cost.toFixed(3)}</Badge> : null`.
   Verify the exact current code at execution time; the line
   number is point-in-time.
2. **Update the breadcrumb.** `inbox-store.ts:159` has an inline
   comment from Plan 18 closure flagging "Plan 19 candidate."
   Either update to reference Plan 19's resolution OR remove the
   comment as resolved.
3. **Unit test.** Add the 3-case suppression test. Existing
   source-row tests should not break.
4. **Verify visually.** Per CLAUDE.md "Always validate fixes via
   the UI in the browser before declaring done" — start the dev
   server, ingest a small file (or use a seed fixture), confirm
   no badge renders for the resulting `cost === 0` row.

**Per-task review:** combined spec + code-quality. Reviewer
confirms (a) the suppression is on `cost === 0` specifically, not
`cost == 0` (would coerce); (b) `cost = undefined` also suppresses
(defensive); (c) the inline breadcrumb is updated/removed; (d) the
unit test fails RED if the suppression is reverted.

### Theme C — Informational extra-in-backend DRIFTs

#### T4 — Track C 4 informational DRIFTs bundled

**Files:**
- Modify: `apps/brain_web/src/lib/api/tools.ts` — narrow 4
  wrapper return types (sub-fixes T4.1-T4.4 below).
- Create: 4 Python key-set pin tests under
  `packages/brain_core/tests/tools/`:
  - `test_recent_outer_shape_pin.py` (or extend existing)
  - `test_propose_note_data_shape_pin.py` (or extend existing)
  - `test_list_pending_patches_outer_shape_pin.py` (or extend existing)
  - `test_config_set_data_shape_pin.py` (or extend existing)
- The 7 `configSet`-routed wrappers (`setDomainOverride`,
  `setPrivacyRailed`, `setDomainBudget`, `setDomainRateLimit`,
  `setDomainAutonomy`, `setActiveDomain`,
  `setCrossDomainWarningAcknowledged`) inherit the narrowed
  `configSet` return type automatically — single root fix.

**Goal:** Close the 4 informational extra-in-backend DRIFTs Plan 18
T2 audit surfaced and deferred per user adjudication. All four are
cosmetic severity (no live consumers read the extras), so the fix
is pure TS-widen-to-match-backend + Python pin. Per locked D3, all
four bundle into one task with sub-fixes.

**Sub-fixes:**

**T4.1 — `recent()` outer-shape extra (`limit_used`)**
- Plan 18 T2 row: backend emits `{items, limit_used}`; TS declares
  `{items: RecentEntry[]}` only.
- Widen TS at `tools.ts:129-132` (or current location) to
  `Promise<ToolResponse<{items: RecentEntry[]; limit_used: number}>>`.
- Python pin: `packages/brain_core/tests/tools/` — strict assertion
  `set(result.data.keys()) == {"items", "limit_used"}` against the
  `brain_recent` handler.

**T4.2 — `proposeNote()` extra-in-backend (`status`)**
- Plan 18 T2 row: backend emits `{status, patch_id, target_path}`;
  TS declares `{patch_id, target_path}` only.
- Widen TS at `tools.ts:242-250` (or current location) to include
  `status: string`.
- Python pin: strict assertion
  `set(result.data.keys()) == {"status", "patch_id", "target_path"}`
  against the `brain_propose_note` handler.

**T4.3 — `listPendingPatches()` outer-shape extra (`count`)**
- Plan 18 T2 row: backend emits `{count, patches}`; TS declares
  `{patches: PendingPatch[]}` only.
- Widen TS at `tools.ts:253-256` (or current location) to
  `Promise<ToolResponse<{count: number; patches: PendingPatch[]}>>`.
- Python pin: strict assertion
  `set(result.data.keys()) == {"count", "patches"}` against the
  `brain_list_pending_patches` handler.

**T4.4 — `configSet()` extra-in-backend (`status`/`persisted`/`note`)**
- Plan 18 T2 row: backend emits `{status, key, value, persisted, note}`;
  TS declares `{key, value}` only. Same drift propagates to 7
  `configSet`-routed wrappers.
- Widen TS at `tools.ts:422-426` (or current location) to include
  `status: string; persisted: boolean; note: string`. The 7
  downstream wrappers inherit the type automatically (they all
  return `Promise<ToolResponse<...>>` via the central `configSet`
  helper).
- Python pin: strict assertion
  `set(result.data.keys()) == {"status", "key", "value", "persisted", "note"}`
  against the `brain_config_set` handler. (Note: Plan 18 audit found
  the same keys emitted across both branches in `config_set.py:832-845, 901-910` —
  a single pin is sufficient if both branches share the same key
  set; otherwise add a per-branch variant.)

**Goal:** close all 4 Track C DRIFTs with TS-widen + Python pin per
sub-fix. Locked direction is **widen TS to backend reality**, not
narrow backend (which would change the backend's public API for
zero benefit — no consumers need the extras hidden).

**What to do:**
1. **Per sub-fix:** widen the TS wrapper return type to include the
   backend-emitted extra fields; add the Python key-set pin test.
2. **Verify the 7 configSet-routed wrappers.** Spot-check 1-2 of
   them (`setActiveDomain`, `setDomainBudget`) compile cleanly
   against the widened `configSet` type. No source change should
   be needed in the wrappers themselves — they inherit via type
   propagation.
3. **Append `## T4 outcome`** to this plan doc summarizing the 4
   sub-fix receipts.

**Per-task review:** combined spec + code-quality. Reviewer confirms
(a) each TS widening matches the backend shape exactly; (b) each
Python pin fails RED on a key add/remove/rename; (c) the 7
downstream `configSet` wrappers don't need source changes (single
root fix verified via spot-check); (d) no orphaned `as`-cast remnants
in TS callers of the 4 affected wrappers.

### Theme D — Type-tighten

#### T5 — `planToFiles` accepts `BulkImportPlannedItem[]` directly

**Files:**
- Modify: `apps/brain_web/src/lib/api/tools.ts` — `planToFiles`'s
  signature accepts `BulkImportPlannedItem[]` directly instead of
  the looser `Array<Record<string, unknown>>` shape.
- Modify: `apps/brain_web/src/components/bulk/step-pick-folder.tsx`
  — remove the `as unknown as Array<Record<string, unknown>>` cast
  Plan 18 T3.9 had to leave in place.

**Goal:** Close Track D. Plan 18 T3.9 narrowed `bulkImport`'s
`planned` branch to use `BulkImportPlannedItem[]`, but the consumer
at `step-pick-folder.tsx` had to cast away to the `planToFiles`
caller's old looser parameter type. Tightening `planToFiles`'s
signature eliminates the consumer cast — the type system enforces
end-to-end shape correctness from `bulkImport` → `planToFiles`.

**What to do:**
1. **Read current `planToFiles` signature.** Grep `planToFiles` in
   `tools.ts` to find its current parameter type. Confirm the
   looser shape exists.
2. **Tighten to `BulkImportPlannedItem[]`.** If the function body
   reads fields the looser type doesn't declare (unlikely — the
   `BulkImportPlannedItem` shape was defined to cover them), no
   body change needed.
3. **Remove consumer cast.** `step-pick-folder.tsx` passes the
   `planned` items directly without the `as unknown as ...` cast.
4. **Verify type-check.** `tsc --noEmit` (or whatever the brain_web
   type-check recipe is) passes cleanly on both files. Existing
   bulk-import unit tests should not break.
5. **Append `## T5 outcome`** to this plan doc.

**Per-task review:** combined spec + code-quality. Reviewer confirms
(a) the cast is removed at the named call site; (b) no other call
sites of `planToFiles` regress (grep all callers); (c) type-check
clean.

### Closure

#### T6 — Closure: demo + lessons + todo + tag

**Files:**
- Create: `scripts/demo-plan-19.py` — assert each gate per the demo
  description above.
- Modify: `tasks/lessons.md` — append a "Plan 19 closure" section.
- Modify: `tasks/todo.md` — row 19 marked ✅ Complete; tail block
  refreshed as "Plan 20 candidate scope" preserving the 4
  NOT-DOING carry-forwards (items 8-11 from Plan 18 closure) per D5.
- Tag: `plan-19-rest-drift-and-typed-polish` cut on green demo.

**Goal:** land Plan 19 closure following Plan 18 T5's shape.

**What to do:**
1. **`demo-plan-19.py`.** Per D7, the demo asserts each carry-forward
   is CLOSED with per-item structural assertions (file existence,
   regex match, AST shape, response_model field-set). No live LLM,
   no network. Final stdout line on a clean run: `PLAN 19 DEMO OK`.
2. **Lessons.** Plan 19 closure section in `tasks/lessons.md`:
   - "REST-endpoint drift class lesson" — extend Plan 18's
     typed-wrapper-vs-runtime drift class lesson to the REST
     transport. Future implementers must audit BOTH MCP-tool
     wrappers (`tools.ts`) AND REST endpoints (`brain_api/endpoints/*`)
     when one drifts.
   - "FastAPI response_model as drift-pin source" — the response_model
     field-set is itself a contract that key-set pins can read
     without invoking the handler. Lighter than the MCP-tool pin
     pattern (which needs a fixture + handler invocation).
   - "T4 4-sub-fix bundle precedent" — bundling cosmetic-severity
     drifts under one task with sub-fixes is the right cadence when
     no live consumers exist. Plan 18's split (T3.1-T3.11) was
     correct for live-consumer-bug closure; Plan 19 T4's bundle is
     correct for cosmetic-only closure.
   - Anything else surfaced during T1-T5 review.
3. **todo.md update.** Row 19 marked ✅; tail block becomes
   "Plan 20 candidate scope" with the 4 preserved NOT-DOING
   carry-forwards per D5:
   - `seedBrainMd` / `seedScope` rule-of-three (threshold not met;
     re-check at execution if Plan 19 added callers).
   - Per-thread cross-domain confirmation (architectural NO per
     spec §3, Plan 16 D36).
   - "Topbar scope chip" drift watch (lesson-only per Plan 12).
   - Free-threaded Python PEP 703 for `_cached_ctx` (3.14 trigger).
4. **Tag.** `plan-19-rest-drift-and-typed-polish` cut on green
   `scripts/demo-plan-19.py` + green pytest + green vitest +
   green Playwright + green CI on macos-14 + windows-2022.
5. **Push.** Per D10, after closure tag: single `git push` covers
   Plan 19's commits. User authorization required.

**Per-task review:** combined spec + code-quality. Demo gate count
is not pinned per D7; closure shape mirrors Plan 18 T5.

## Owning subagents

- **brain-frontend-engineer** — T1 (TS-side audit of REST consumer
  shapes), T2 (TS narrows + live consumer fixes if surfaced), T3
  (Track B suppression conditional + unit test), T4 (TS narrows for
  Track C 4 sub-fixes), T5 (planToFiles signature tighten + consumer
  cast removal). May bounce a follow-up to brain-mcp-engineer if a
  backend endpoint's response_model shape needs adjudication.
- **brain-mcp-engineer (role-overloaded as brain-api-engineer)** — T1
  (Python-side enumeration of REST endpoint response_models), T2
  (Python pin tests for REST endpoints; possible response_model
  adjustments if T1 surfaces a backend-side fix). The CLAUDE.md
  subagent list does NOT include a dedicated `brain-api-engineer`
  type — `brain-mcp-engineer` has handled brain_api work across
  Plans 11 + 13 + 14 + 15 + 17.
- **brain-core-engineer** — T4 (Python key-set pin tests for the
  4 backend handlers `brain_recent` / `brain_propose_note` /
  `brain_list_pending_patches` / `brain_config_set`), T6 (demo +
  lessons + closure).
- **brain-test-engineer** — may collaborate on T3 unit test if
  needed; T1-T5 implementers are empowered to land tests inline per
  Plan 18 D5's "combined review" practice.
- (No new tasks for brain-prompt-engineer, brain-ui-designer, or
  brain-installer-engineer in Plan 19. T3 UX direction is already
  locked per D4 — designer adjudication not required.)

## Workflow rules

Same as Plans 16 + 17 + 18:
- Sequential per-task dispatch via `superpowers:subagent-driven-development`.
- Combined spec + code-quality review per task.
- Implementer routes back to plan author on any unrecognized rule
  edge case (e.g., T1 audit edge cases, T2 live-consumer-bug
  adjudication, T4 sub-fix verdict edge cases).
- Pause every ~3 tasks for user check-in (Plan 18 paused every 3;
  Plan 16/17 paused every ~5).
- No push without explicit user authorization at Plan 19 close
  (D10).
- pytest recipe on this iCloud-synced repo:
  `find .venv -name "*.pth" | xargs -I{} chflags 0 {} 2>/dev/null; uv run pytest <args>`
  on ONE command line. Or PYTHONPATH bypass:
  `unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src uv run --package <pkg> pytest packages/<pkg>/tests -q`.
- Radix dialogs + axe need `waitForAnimationsToFinish` from
  `apps/brain_web/tests/e2e/_helpers.ts` (auto-memory:
  `feedback_axe_dialog_animation_wait.md`). Unlikely relevant for
  Plan 19 (no new dialogs).
- Monkeypatching internal helper calls: patch BOTH the helper's
  resolved-at-call-time namespace AND the caller's namespace
  (latter `raising=False`) per Plan 17 T17 lesson. Unlikely
  relevant for Plan 19 (key-set pins read model fields directly,
  no helper interception needed).
- Pydantic v2 `model_validator(mode="after")` does NOT roll back
  the triggering field mutation on raise (CLAUDE.md "What NOT to
  do"). Unlikely relevant for Plan 19 (no schema mutations).

## File inventory (summary)

```
tasks/plans/
└── 19-rest-drift-and-typed-polish.md   # SELF (this doc);
                                        # T1/T2/T4/T5 outcomes
                                        # appended at exec time

apps/brain_web/
├── src/
│   ├── lib/
│   │   ├── ingest/upload.ts             # MODIFY: narrow UploadResult
│   │   │                                 # per T1's /api/upload finding (T2)
│   │   ├── api/tools.ts                 # MODIFY: 4 Track C widens (T4);
│   │   │                                 # planToFiles signature tighten (T5)
│   │   ├── state/inbox-store.ts         # MODIFY: line 159 breadcrumb
│   │   │                                 # update/remove (T3)
│   │   └── (possibly setup/token        # MODIFY: per T1 findings (T2)
│   │     consumer files)                 # if drift surfaces
│   ├── components/
│   │   ├── inbox/source-row.tsx         # MODIFY: cost === 0 suppression (T3)
│   │   └── bulk/step-pick-folder.tsx    # MODIFY: remove planToFiles cast (T5)
└── tests/unit/
    └── source-row.test.tsx              # CREATE or MODIFY: cost suppression
                                        # unit test (T3)

packages/brain_api/
├── src/brain_api/endpoints/
│   ├── upload.py                        # AUDIT (T1); possibly MODIFY (T2)
│   ├── setup_status.py                  # AUDIT (T1); possibly MODIFY (T2)
│   └── token.py                         # AUDIT (T1); possibly MODIFY (T2)
└── tests/
    └── test_endpoint_<name>_shape.py   # CREATE: response_model field-set
                                        # pin per DRIFT row (T2)

packages/brain_core/
└── tests/tools/
    ├── test_recent_outer_shape_pin.py   # CREATE: T4.1 pin
    ├── test_propose_note_data_shape_pin.py  # CREATE: T4.2 pin
    ├── test_list_pending_patches_outer_shape_pin.py  # CREATE: T4.3 pin
    └── test_config_set_data_shape_pin.py    # CREATE: T4.4 pin

scripts/
└── demo-plan-19.py                      # CREATE (T6)

tasks/
├── lessons.md                           # MODIFY: Plan 19 closure
│                                        # section (T6)
└── todo.md                              # MODIFY: row 19 ✅ + Plan 20
                                         # candidate scope tail (T6)
```

## T1 audit findings

Audited 2026-05-11 against backend `response_model` Pydantic
`BaseModel` declarations in
`packages/brain_api/src/brain_api/endpoints/*.py`. One row per
endpoint file (3 total) matched to its TS-side consumer in
`apps/brain_web/src/`.

**Scope note:** D1 locks the audit surface to
`packages/brain_api/src/brain_api/endpoints/*` (3 files). Other
FastAPI routers under `packages/brain_api/src/brain_api/routes/`
(`health.py`, `tools.py`, `chat.py`) host the tool dispatcher +
chat WebSocket + health probe — those surfaces are covered by Plan
18's `tools.ts` audit (`/api/tools/<name>` POST dispatcher) and by
the WebSocket envelope contract tests respectively, so they are
intentionally excluded from this REST-endpoint audit. The
`/api/healthz` route emits a free-form `dict[str, Any]` (no
`response_model`) and has no TS consumer in `apps/brain_web/src/`.

Verdict legend (mirrors Plan 18 T2):
- **OK** — TS and backend agree exactly on key set + types.
- **MINOR** — TS uses optional fields (`?:`) or `[extra]` index
  sig that absorbs the discrepancy; runtime reads degrade
  gracefully.
- **DRIFT** — TS declares required fields backend doesn't emit
  (T1-class — silently `undefined` at runtime) OR backend emits
  keys not declared in TS AND TS has no index-sig escape hatch.
  T2 fix candidates.

| REST endpoint | Backend model (file:line) | TS consumer (file:line) | Verdict | Notes |
|---|---|---|---|---|
| `POST /api/upload` | `UploadResponse` @ `packages/brain_api/src/brain_api/endpoints/upload.py:91-94` — `{patch_id: str}` | `UploadResult` @ `apps/brain_web/src/lib/ingest/upload.ts:25-30` — `{patch_id: string \| null; applied: boolean; domain: string \| null; [extra: string]: unknown}` | **DRIFT** | TS declares 3 required keys; backend emits only 1 (`patch_id`). **TS-required `applied: boolean` and `domain: string \| null` are NEVER emitted by the backend** — both silently `undefined` at runtime. TS `patch_id: string \| null` is more permissive than backend `patch_id: str` (non-null) — TS-permissive direction is safe. Index sig absorbs the absence on read, but TS callers reading `res.applied`/`res.domain` get `undefined`. **Live consumer impact: HIGH.** Two callers read `res.domain` without questioning (Plan 18 T1-class shape exactly): `apps/brain_web/src/components/inbox/drop-zone.tsx:64` (`updateStatus(id, { ..., domain: res.domain })`) and `apps/brain_web/src/components/shell/app-shell.tsx:178` (`updateStatus(id, { ..., domain: res.domain ?? null })`). Both unconditionally write `undefined` (drop-zone) or `null` (app-shell, via `??`) into the inbox row's `domain` field — meaning every successful drag-drop / file-picker upload records the row with `domain: undefined`/`null` regardless of the classify result the backend actually produced. The backend's ingest dispatch DOES produce a domain on the staged patch (see `upload.py:167` `module.handle({"source": str(staged)}, ctx.tool_ctx)`), but the response_model drops it. The `res.patch_id` read at `app-shell.tsx:180` works correctly because the backend does emit it. The empty-data fallback at `upload.ts:91-95` (`patch_id: null, applied: false, domain: null`) is dead code under the current backend (which always returns a UTF-8 body with `patch_id`); T2 should narrow `UploadResult` to `{patch_id: string}` and drop the fallback, and the live consumers at drop-zone.tsx + app-shell.tsx must be reworked to either drop the inbox `domain` write entirely (T2 design choice) or change the response_model to include it (backend-side fix). **T2 candidate (highest-impact in this audit).** |
| `GET /api/setup-status` | `SetupStatusResponse` @ `packages/brain_api/src/brain_api/endpoints/setup_status.py:39-45` — `{has_token: bool; is_first_run: bool; vault_exists: bool; vault_path: str}` | `SetupStatusBody` @ `apps/brain_web/src/lib/bootstrap/bootstrap-context.tsx:75-80` — `{has_token: boolean; is_first_run: boolean; vault_exists: boolean; vault_path: string}` | **OK** | Exact key-set + type agreement (4 keys both sides, no extras either direction, no index sig needed). Cast is `(await statusRes.json()) as SetupStatusBody` at `bootstrap-context.tsx:128`. Consumer reads `statusBody.is_first_run` (`:137`, `:140`) and `statusBody.vault_path` (`:138`) — both keys present in backend. Bootstrap effect's branch on `is_first_run` routes the user to `/setup/` correctly. No drift. |
| `GET /api/token` | `TokenResponse` @ `packages/brain_api/src/brain_api/endpoints/token.py:33-36` — `{token: str}` | `TokenBody` @ `apps/brain_web/src/lib/bootstrap/bootstrap-context.tsx:82-84` — `{token: string}` | **OK** | Exact key-set + type agreement (single `token: string` field both sides). Cast at `bootstrap-context.tsx:162` reads `tokenBody.token` and writes to the local + Zustand token store (`:164-165`). The endpoint additionally emits a `Cache-Control: no-store` response header (`token.py:57`) which is a transport-layer concern, not part of the body shape — no TS-side drift implication. Note the backend explicitly carries a 503 `{"error": "setup_required"}` branch for the missing-token-file path (`token.py:52-56`) which is handled in the consumer at `bootstrap-context.tsx:154-160` via the `!tokenRes.ok` check (no body parse on the error path) — the error envelope shape is consumed via the shared `ApiError` flow, not via `TokenBody`. No drift. |

**Summary:** 2 OK, 0 MINOR, 1 DRIFT (1 row is a T2 fix candidate).

**Drift-class breakdown:**
- **T1-class — TS-required fields missing in backend** (silently
  `undefined` at runtime; breaks live consumers): `/api/upload`
  (`applied`, `domain`). **1 row.**
- **Extra-in-backend, no TS index-sig escape hatch:** 0 rows.

**Live-consumer-impact heat map** (consumers in
`apps/brain_web/src/` that consume drifted fields):
- `/api/upload` — `components/inbox/drop-zone.tsx:64` and
  `components/shell/app-shell.tsx:178` both write `res.domain`
  (which is always `undefined` from the backend) into the inbox
  row. The app-shell caller uses `res.domain ?? null` so the row
  always lands with `domain: null`; the drop-zone caller does NOT
  coalesce, so the row's `domain` field receives the literal
  `undefined` (whether that round-trips through the inbox-store's
  Zustand merge depends on the store contract — worth checking in
  T2). **HIGH** — every successful upload records a wrong/missing
  domain in the inbox row. Same Plan 18 T1-class shape as
  `recentIngests` (silently-empty Inbox), `undoLast` (toast always
  0), `budgetOverride` (toast reads stale prop default).
- `/api/setup-status`, `/api/token` — no drift, no consumer
  impact.

Spot-check pass (3 of 3 rows re-derived from backend after writing
verdicts — small surface, so we re-check every row):
- `/api/upload` row → re-read `endpoints/upload.py:91-94`:
  confirms `class UploadResponse(BaseModel): patch_id: str` —
  single non-nullable string field, no `applied`, no `domain`. TS
  declares 3 required fields. Confirmed **DRIFT**.
- `/api/setup-status` row → re-read
  `endpoints/setup_status.py:39-45`: confirms
  `{has_token, is_first_run, vault_exists, vault_path}` with
  `bool/bool/bool/str`. TS `SetupStatusBody` declares the same 4
  keys with `boolean/boolean/boolean/string`. Confirmed **OK**.
- `/api/token` row → re-read `endpoints/token.py:33-36`: confirms
  `{token: str}`. TS `TokenBody` declares `{token: string}`.
  Confirmed **OK**.

**Comparison to Plan 18 T2 audit:** Plan 18 T2 audited the
MCP-tool transport surface (`tools.ts`, 38 wrapper rows) and
surfaced 15 DRIFTs (39% drift rate, 11 T1-class + 4 extras). Plan
19 T1 audits the REST-endpoint surface (3 endpoint rows) and
surfaces 1 DRIFT (33% drift rate, 1 T1-class + 0 extras). Drift
rate is roughly similar across the two transports, but the
REST-endpoint surface is small enough that one DRIFT covers the
entire fix budget for T2. The Plan 18 lesson — "when one drifts,
audit ALL siblings" — paid off: the audit ruled out drift on the
other 2 endpoints quickly (Pydantic-typed responses tend to be
shape-faithful when the TS-side caller also declares a closed
interface that hand-matches the backend, which is the case for
`SetupStatusBody` and `TokenBody`).

## T2 outcome

Closed 2026-05-11. The 1 DRIFT row from T1 (`/api/upload`,
`UploadResult`) is fixed end-to-end: TS narrowed to backend reality,
both live consumers stopped writing the never-emitted `res.domain`
field into the inbox row, and the dead-code envelope fallback at
`upload.ts:91-95` is replaced with a defensive contract-violation
guard.

### Per-finding receipts

**`/api/upload` — `UploadResult` narrow**

- **TS narrow site:** `apps/brain_web/src/lib/ingest/upload.ts:25-42`.
  - Before: `{patch_id: string | null; applied: boolean; domain: string | null; [extra: string]: unknown}`.
  - After: `{patch_id: string}` (single non-nullable field, mirrors
    backend `UploadResponse(BaseModel) {patch_id: str}` at
    `packages/brain_api/src/brain_api/endpoints/upload.py:91-94`
    exactly).
  - The previous `[extra]` index sig is gone — backend's
    `response_model=UploadResponse` enforces a closed shape, so the
    escape hatch was buying nothing and hiding the drift.

- **Dead-code fallback removed:**
  `apps/brain_web/src/lib/ingest/upload.ts:91-107` (post-narrow line
  range). The previous fallback at lines 91-95 filled
  `{patch_id: null, applied: false, domain: null}` when the envelope
  was empty — under the current backend contract (response_model
  guarantees a non-empty `patch_id`), this path was provably dead. T2
  replaces it with a defensive runtime guard: if `envelope.data` is
  missing or `data.patch_id` is non-string / empty, throw an
  `ApiError` with code `upload_envelope_invalid` so the consumer's
  error-toast surface catches it. Surprise / minor scope creep:
  documented inline at the throw site so the next reader sees why
  this isn't dead code (it's a contract-violation tripwire).

- **Live consumer 1: `apps/brain_web/src/components/inbox/drop-zone.tsx:60-76`** (post-edit line range). The
  `uploadFile(file).then((res) => updateStatus(id, { ..., domain: res.domain }))` call (line 64 pre-fix) is now
  `uploadFile(file).then(() => updateStatus(id, { status: "done", progress: 100 }))` — the broken `domain: res.domain` write (always `undefined` at runtime; the row in the Zustand store stayed at its optimistic `null` placeholder OR took on `undefined` depending on the store's merge contract) is gone. Plain-English comment in source explains the reasoning so a future reader doesn't re-add it. Inline regression test at `apps/brain_web/tests/unit/drop-zone.test.tsx:78-110` exercises the post-fix
  state: it asserts that after a successful `uploadFile` mock returns
  `{patch_id: "p-narrow"}`, the inbox-store row's `domain` field
  stays `null` (the placeholder), NOT `"WRONG"` or `undefined` (the
  pre-fix bug shapes). Sanity-checked via RED-then-GREEN: temporarily
  reverting the consumer to read `res.domain` yields
  `AssertionError: expected 'WRONG' to be null`. GREEN restored.

- **Live consumer 2: `apps/brain_web/src/components/shell/app-shell.tsx:173-194`** (post-edit line range). The
  `uploadFile(file).then((res) => inbox.updateStatus(id, { ..., domain: res.domain ?? null }))` call (line 178 pre-fix) is now
  `uploadFile(file).then((res) => inbox.updateStatus(id, { status: "done", progress: 100 }))` — the broken `domain: res.domain ?? null` write
  (always `null`, silently clobbering whatever the optimistic row
  held) is gone. `res.patch_id` read at the chat-attach branch
  (`if (onChatRoute && res.patch_id)`) is preserved — backend DOES
  emit `patch_id`, so that read is correct. Same plain-English
  comment shape as drop-zone for symmetry.

- **Python pin test:**
  `packages/brain_api/tests/test_endpoint_upload_shape.py` (newly
  created). Two tests:
  1. `test_upload_response_field_set` — `set(UploadResponse.model_fields.keys()) == {"patch_id"}`.
     Sanity-checked via RED-then-GREEN: deliberately adding a
     `stray: str = "TEMP_RED_CHECK"` field on the backend yields
     `AssertionError: {'patch_id', 'stray'} != {'patch_id'}`. GREEN
     restored.
  2. `test_upload_response_patch_id_is_non_nullable_str` —
     `field.annotation is str` and `field.is_required()`. Pins the
     non-null direction; the TS narrow assumes this stays true.

### Verification receipts

- `tsc --noEmit` on `apps/brain_web/` — clean (no output).
- `pnpm vitest run` on `apps/brain_web/` — 81 test files, 493
  passed + 1 skipped (the new regression test in drop-zone slot 78-110 is the
  additional test). RED-then-GREEN demonstrated on the new regression
  test in isolation.
- `pytest packages/brain_api/tests/test_endpoint_upload_shape.py` — 2 passed.
  RED-then-GREEN demonstrated on the field-set pin test in isolation.
- `pytest packages/brain_api/tests/test_upload_endpoint.py` — 4
  passed (no regressions; happy-path body shape unchanged).
- `pnpm lint` on `apps/brain_web/` — 0 ESLint warnings or errors.
- **Visual UI verification** per CLAUDE.md "always validate fixes
  via the UI in the browser before declaring done": started backend
  via `.venv/bin/python -m uvicorn brain_cli.runtime.backend_factory:build_app --factory`
  with `BRAIN_VAULT_ROOT=~/Documents/brain` and explicit
  `BRAIN_WEB_OUT_DIR=apps/brain_web/out` (the resolver's `parents[4]`
  fallback was unable to locate the out-dir in the iCloud-synced
  workspace — minor surprise; documented for future visual-QA
  invocations). Navigated to `http://localhost:4317/inbox/` and
  triggered the drop-zone `drop` handler via a synthetic
  `DragEvent` with a real `File` payload. Observed: (a) optimistic
  row appears in the in-progress tab immediately (drop-zone's
  `addOptimistic` fires), (b) backend returns
  `{error: "ingest_failed", ...}` (no Anthropic API key in this
  workspace, so classify step fails — environment limitation, not a
  fix regression), (c) consumer's error branch surfaces the
  "Upload failed." toast with the backend's message verbatim, (d)
  row flips to `failed` status and shows up in the "Needs
  attention" tab with badge `unclassified` (which is
  `source.domain ?? "unclassified"` rendering when `row.domain ===
  null` — exactly the post-fix shape). The happy-path consumer
  branch (success → `updateStatus(id, {status: "done", progress:
  100})`) is identical structure to the error branch and is covered
  by the vitest regression test that asserts `row.domain` stays
  `null` post-success.

### Surprises captured

1. The dead-code fallback at `upload.ts:91-95` IS provably dead under
   the current backend contract (response_model is closed; envelope
   middleware guarantees a `data` field on 2xx). T2 replaces it with
   a defensive `ApiError` throw rather than removing it entirely —
   this protects against a future backend regression that drops the
   envelope wrap or returns a 2xx with no body. Tradeoff considered:
   could have removed the check entirely + relied on the typed read
   throwing at the destructure site (`return { patch_id: data.patch_id }`
   would throw `TypeError: Cannot read properties of undefined`),
   but a typed `ApiError` produces a friendlier toast and a clear
   error code (`upload_envelope_invalid`) for future debugging.
   Chose defensive guard.
2. `resolve_out_dir()` at `packages/brain_api/src/brain_api/static_ui.py:95-97`
   uses `parents[4]` as a dev-fallback for `<repo_root>/apps/brain_web/out`. Under uv's editable install + iCloud's `.pth` masking, the resolved `Path(__file__).parents[4]` did not land on the repo root and the SPA mount silently degraded to API-only mode. Setting `BRAIN_WEB_OUT_DIR` explicitly worked. **Not a Plan 19 fix candidate** (Plan 13 + Plan 15 cross-platform sweeps own this seam), but worth a lessons.md row at Plan 19 closure (T6) so future visual-QA invocations skip the diagnosis. Documented here for the closure pass.
3. The TestClient happy-path assertion in `test_upload_endpoint.py:103-104` reads `body["patch_id"]` directly (not `body["data"]["patch_id"]`) — this works because the envelope middleware only wraps responses that aren't already a `BaseModel`-typed response_model on a JSON-accept path under specific conditions. Worth double-checking the envelope-shape parity tests at `test_envelope_shape_parity.py` if a future plan touches the envelope middleware — no action needed at T2.

### Commit boundaries

Per Plan 19 workflow note: atomic commits preferred. T2 produces 3
commits:
- **(a)** Frontend: TS narrow + 2 consumer fixes + drop-zone
  regression test.
- **(b)** Backend: Python pin test (new file).
- **(c)** Plan doc: this `## T2 outcome` section.

(Or a single combined commit if the user prefers; commits stay
~150 LOC total.)

## T3 outcome

**Status:** DONE on 2026-05-12.

Track B closure: the ingest-row cost badge is suppressed when `cost
=== 0` (cached / zero-token rows the backend emits as `cost_usd: 0.0`).
The strict `cost > 0` form also suppresses `undefined` / `null` / `NaN`
by JS coercion — defensive against bad data and matches D4's locked
"suppression is decisive" direction.

### Per-finding receipts

**(a) Suppression at `apps/brain_web/src/components/inbox/source-row.tsx`
(lines 109-115 post-fix).** The pre-fix conditional was `typeof
source.cost === "number" && ( ... )` — a type-guard that accepted `0`
and rendered `· $0.000`. Post-fix: `typeof source.cost === "number" &&
source.cost > 0 && ( ... )`. Strict `> 0` was chosen over `cost ? ...`
loose-truthy per the plan doc's "explicit over clever" preference: `>
0` is decisive about which values mean "no badge", and the inline
comment cites D4 + the defensive-against-NaN rationale.

**(b) Breadcrumb resolved at `apps/brain_web/src/lib/state/inbox-store.ts`
(lines 160-164 post-fix).** The Plan 18-era comment flagged "Plan 19
candidate" — updated to "Plan 19 T3 (D4) resolved the UX question
downstream in <SourceRow>" so future readers see the closure cross-
reference without having to git-blame to find it.

**(c) Unit tests at `apps/brain_web/tests/unit/source-row.test.tsx`
(lines 78-122, 3 new cases).** Names:
- `"done status renders the cost badge when cost > 0"` (positive case)
- `"done status suppresses the cost badge when cost === 0"` (the live
  bug case)
- `"done status suppresses the cost badge when cost is undefined"`
  (defensive — same suppression path)

RED-then-GREEN sanity check: I temporarily reverted the `source.cost
> 0` guard back to the pre-fix `typeof source.cost === "number"`
shape and re-ran the test file. The `cost === 0` case failed with
`expected document not to contain element, found <span>... · $0.000
</span>` — confirms the test fails RED if the suppression is reverted.
Restored the fix; re-ran; 7/7 GREEN.

### Smoke + verification

- `pnpm vitest run tests/unit/source-row.test.tsx` → 7/7 pass.
- `pnpm vitest run tests/unit/inbox-store.test.ts tests/unit/inbox-store-loadRecent.test.ts`
  → 9/9 pass (related store tests unaffected by the breadcrumb change).
- `pnpm tsc --noEmit` → exit 0 (no type regressions; mirrors the T2
  follow-up commit `0ac02a9` lesson about vitest leniency vs tsc).
- **Visual verification (per CLAUDE.md):** started `pnpm dev` on
  `:4316`, stubbed `/api/setup-status` / `/api/token` /
  `/api/tools/brain_recent_ingests` to feed 3 synthetic done-rows
  (`cost_usd: 0`, `cost_usd: 0.123`, `cost_usd` omitted). Clicked the
  "Recent" inbox tab. Verified sublines:
  - `cost=0` row → `"Filed to research"` (badge suppressed) ✅
  - `cost=0.123` row → `"Filed to research · $0.123"` (badge renders) ✅
  - `cost=undefined` row → `"Filed to research"` (badge suppressed) ✅

### Commit

Single atomic commit (per D8 review style and the ~20-40 LOC scope).
Commit SHA recorded after `git commit`. No push per D10.

## T4 outcome

To be filled in at T4 execution. Per-sub-fix receipts (T4.1 / T4.2 /
T4.3 / T4.4) — TS widen + Python pin path per sub-fix.

## T5 outcome

To be filled in at T5 execution. `planToFiles` signature tighten +
consumer cast removal receipts.

## Plan 20 candidate scope

Filled in at T6 closure. The canonical record is the tail block of
`tasks/todo.md`; this section is a brief pointer. Preserved Plan 17
/ earlier carry-forwards per D5 (4 NOT-DOING items):

- `seedBrainMd` / `seedScope` rule-of-three (threshold not met).
- Per-thread cross-domain confirmation (architectural NO per spec
  §3 + Plan 16 D36).
- Topbar scope chip drift watch (lesson-only per Plan 12).
- Free-threaded Python PEP 703 for `_cached_ctx` (3.14 timeline
  trigger).

Plus any new candidates surfacing from Plan 19 execution.

## Review

- **Tag:** `plan-19-rest-drift-and-typed-polish` (cut on green demo
  by the user after final approval).
- **Closes:** the Plan 18 candidate scope tail block (preserved here
  for traceability): Track A REST-endpoint drift (T1 audit + T2
  fixes); Track B cost-badge UX (T3 suppression); Track C 4
  informational extras (T4 bundled with sub-fixes); Track D
  `planToFiles` type-tighten (T5).
- **Bumps:** to be filled in at closure.
- **Verification:** `scripts/demo-plan-19.py` → `PLAN 19 DEMO OK`
  (gate count not pinned per D7); pytest + vitest + Playwright
  green on the implementer's local Mac (Windows CI cut at user-tag
  + push time per D10).
- **Backlog forward:** Plan 20 candidate scope per the tail block
  of `tasks/todo.md` (preserved Plan 17 carry-forwards + any new
  candidates surfacing from Plan 19 execution).

---

**End of Plan 19 (draft, awaiting approval).**
