# Plan 20 — `response_model` pin adoption + `tools.ts` wrapper-shape audit

**Authored:** 2026-05-12 (post Plan 19 close on 2026-05-12, tag
`plan-19-rest-drift-and-typed-polish` at `c50b29f`).
**Scope:** Adopt the Plan 19 T2.b lightweight FastAPI `response_model`
field-set pin pattern across the two Plan 19 T1 audit-OK-but-unpinned
endpoints (`endpoints/setup_status.py:SetupStatusResponse` and
`endpoints/token.py:TokenResponse`), plus the two foundational shared
envelopes (`responses.py:ToolResponse` and `responses.py:ErrorResponse`)
that every tool call and every error path routes through. Then run a
parallel audit on the TS `tools.ts` wrapper surface for the
hardcoded-return-type-vs-propagation drift class Plan 19 T4 surfaced
(7 `configSet`-routed wrappers had hardcoded `Promise<ToolResponse<{key,
value}>>` instead of propagating via `ReturnType<typeof configSet>`).
The audit defines its surface-of-interest before counting findings, per
Plan 19 T1 lesson, then surfaces the count via `AskUserQuestion` for a
tiered fix decision (mirrors Plan 18 T2 / Plan 19 T1 precedent).
**Shape:** 3 substantive tasks across 2 themes + 1 closure task.
Mirrors Plan 19 D5 / Plan 18 D5 / Plan 17 D2 / Plan 16 D35: per-task
~20-100 LOC PR budget; combined spec + code-quality review per task.

## At a glance

- **Theme A — `response_model` pin adoption** (T1): bundled
  field-set pin tests for 4 stable BaseModels —
  `SetupStatusResponse` + `TokenResponse` (Plan 19 T1 audit-OK,
  unpinned) plus shared envelopes `ToolResponse` + `ErrorResponse`
  (foundational shapes every response routes through). Mirrors
  Plan 19 T2.b's lightweight `set(Model.model_fields.keys()) ==
  {...}` pattern (~10-15 LOC per pin via Pydantic introspection,
  no handler invocation).
- **Theme B — `tools.ts` wrapper-shape audit + tiered fix** (T2,
  T3): audit `apps/brain_web/src/lib/api/tools.ts` for the
  hardcoded-return-type-vs-propagation drift class Plan 19 T4
  surfaced. Tiered fix at exec time via `AskUserQuestion` once the
  finding count is known (per Plan 18 T2 / Plan 19 T1 precedent
  — plans size work, not the inverse).
- **Closure** (T4): demo + lessons + todo.md + tag
  `plan-20-response-model-pins-and-wrapper-audit`.

## Why this plan exists (1 paragraph)

Plan 19 T2.b shipped the lightweight FastAPI `response_model`
field-set pin pattern — `set(UploadResponse.model_fields.keys()) ==
{"patch_id"}` via Pydantic introspection, ~10-15 LOC, no fixture, no
handler call — and validated it as drift-protection at the wire
boundary. Plan 19 T1 audited 3 REST endpoints (`upload.py`,
`setup_status.py`, `token.py`); only `upload.py` got a pin because
it was the DRIFT row. The other 2 were audit-OK and remain unpinned
— future drift on either fails silently because there's no
regression-pin gate. Plan 20 closes that gap with bundled pin tests
covering the 2 unpinned endpoints PLUS the 2 foundational shared
envelopes (`ToolResponse` and `ErrorResponse`) that every tool call
and every 4xx/5xx response routes through. Separately, Plan 19 T4's
"7 `configSet`-routed wrappers had hardcoded return types, not
propagation" surprise is the surface-level instance of a broader
drift class: any wrapper-fanout helper in `tools.ts` where the
wrappers should propagate via `ReturnType<typeof root>` but
hardcoded narrow return types instead. TS covariance hides the
drift at compile time; only IDE hover/auto-complete reveals it.
Plan 20 T2 audits the surface; T3 fixes findings at a tiered scope
locked at exec time once the count is known.

## Locked decisions

| # | Decision | Status | Why |
|---|---|---|---|
| D1 | **#6 (response_model pin adoption) scope = 6B corrected.** Pin 4 BaseModels: `endpoints/setup_status.py:SetupStatusResponse` + `endpoints/token.py:TokenResponse` (Plan 19 T1 audit-OK, unpinned) plus `responses.py:ToolResponse` (outer envelope; `{text, data}`) and `responses.py:ErrorResponse` (error envelope; `{error, message, detail}`). | locked (user 6B) | Plan-author drift correction: pre-execution grep revealed `routes/*` had no Pydantic response_model surface (`chat.py` = WebSocket; `health.py` = `dict[str, str]` literal; `tools.py` = generic `ToolResponse` envelope already covered by Plan 18 T2's per-tool data-shape audit). The actual adoption surface is `endpoints/*` unpinned BaseModels plus the shared envelopes. Captures Plan 16/Plan 19 T5 "grep before assuming file/symbol locations" lesson at the plan-doc level. |
| D2 | **#7 (wrapper-shape audit) scope = 3.A audit-then-size.** T2 enumerates `tools.ts` wrapper functions, classifies hardcoded-vs-propagation patterns, and appends findings inline as `## T2 audit findings`. T3 fixes per-finding at a tiered scope locked at exec time via `AskUserQuestion` once the count is known. | locked (user 3.A) | Mirrors Plan 18 T2 ("audit returned 15 DRIFTs vs predicted 0 → user adjudicated tiered fix scope") and Plan 19 T1 ("define audit surface-of-interest before counting findings"). Plans size work, not the inverse — pre-locking T3's fix count would silently expand or contract the plan based on the audit verdict. |
| D3 | **T1 bundled with 4 sub-fixes (T1.1-T1.4).** Same Plan 19 T4 cosmetic-bundle precedent: same TS-narrow-equivalent pattern (Pydantic key-set assertion), no live consumers per shape (all 4 are stable BaseModels with established field sets), total LOC ~50-60. | locked per Plan 19 D3 | Bundling keeps per-task review focused. Split is the right cadence when sub-fixes need different regression tests against live-consumer bugs (Plan 18 T3.1-T3.11); bundle is correct when all sub-fixes share one pattern with no live-bug-fix work. |
| D4 | **T1 known shapes are point-in-time observations.** Plan-doc cites the shapes Pydantic introspection should expect (`SetupStatusResponse: {has_token, is_first_run, vault_exists, vault_path}`; `TokenResponse: {token}`; `ToolResponse: {text, data}`; `ErrorResponse: {error, message, detail}`) but the implementer MUST verify the exact field set at exec time by reading `model_fields.keys()` against current main HEAD. If a shape has drifted since the audit, the pin codifies whatever the actual current shape is (Plan 19 T1 audit-rederive precedent). | locked per Plan 19 T1 | Plan-doc shape claims are snapshots; implementation must re-derive against current main. Plan 16/19 T5 lesson — plan-author drift at file/symbol/shape level is normal across multi-week gaps. |
| D5 | **Preserved Plan 17/earlier carry-forwards (4 NOT-DOING items)** stay NOT-DOING in Plan 21 candidate tail block at Plan 20 closure. | locked (user 4.A) | All four have explicit not-yet-actionable criteria unchanged since Plan 19 closure (no triggers have fired): `seedBrainMd`/`seedScope` rule-of-three at 3/5 callers (threshold not met); per-thread cross-domain confirmation = architectural NO per spec §3 + Plan 16 D36 (re-litigation requires spec amendment); topbar scope chip drift watch = lesson-only per Plan 12 closure; PEP 703 `_cached_ctx` 3.14+ default trigger. Preserve rationale-per-item to avoid future plan authors re-proposing without context. |
| D6 | **Audit deliverable shape: append findings inline to THIS plan doc as `## T2 audit findings`.** Markdown table with one row per `tools.ts` wrapper-fanout helper inspected + verdict (OK-PROPAGATES / OK-NARROW-INTENTIONAL / DRIFT-HARDCODED) + notes. Plan 19 D6 / Plan 18 D2 / Plan 17 T9 precedent. | locked per Plan 19 D6 | Audit findings are point-in-time observations against current `tools.ts` shape; the plan doc is their natural home. Separate report files sprawl; JSON manifests are an awkward shape for prose verdict columns. |
| D7 | **Demo gate: per-item closure assertion, no gate-count target.** Gate count branches on T2 findings (T3 demo gates depend on what T2 surfaces and how the user tiers the fix scope). | locked per Plan 19 D7 / Plan 18 D4 | Gate count is not pinned — closure shape adapts to audit outcomes. |
| D8 | **Per-task review: combined spec + code-quality** held across 47 tasks in Plan 16; 18 in Plan 17; 5 in Plan 18; 5 in Plan 19. | locked per Plan 16 D35 / Plan 17 D2 / Plan 18 D5 / Plan 19 D8 | No reason to re-litigate at the Plan-15+ polish-pass scale. |
| D9 | **No new dependencies.** Plan 20 ships zero new pip / npm packages. | locked per Plan 19 D9 / Plan 18 D6 / Plan 17 D6 | All Plan 20 work is pin tests + audit + targeted typed-surface fixes. |
| D10 | **Push at Plan 20 close, after user authorization.** Single `git push` covers all Plan 20 commits. | locked per Plan 19 D10 / Plan 18 D7 | Standard cadence — local work is tagged and visible via `git log`; CI surfaces residuals at one synchronization point. |
| D11 | **Sequential subagent dispatch via `superpowers:subagent-driven-development`.** | locked per Plan 19 D11 / Plan 18 D8 / Plan 17 D3 / Plan 16 D2 | Combined review per task plus sequential dispatch held across four prior polish-scale plans. |
| D12 | **Plan-author drift acknowledgement (NEW).** Plan 20's #6 scope was REVISED before T1 dispatch after pre-execution grep showed `routes/*` had no `response_model` surface to pin; corrected to `endpoints/*` + shared envelopes via the user's 6B selection. The plan-doc records the revision so future readers see the Plan 16/Plan 19 T5 "grep-before-assuming" lesson applied at plan-author time, not just at implementer time. | locked at authoring time | The drift watch should fire at both layers: implementers MUST grep before assuming, AND plan authors should grep before recommending. Plan 20 caught it at authoring, not at execution — the cheaper outcome. |

## Tech stack

Same as Plans 16 + 17 + 18 + 19: Python 3.12, pydantic v2, mypy
--strict, ruff, vitest, Playwright. No new tools. No new
dependencies. CI runs on macos-14 + windows-2022 per Plan 14's
matrix.

## Demo gate description

`scripts/demo-plan-20.py` asserts, in sequence:

1. **(T1.1)** `packages/brain_api/tests/test_endpoint_setup_status_shape.py`
   exists and asserts `set(SetupStatusResponse.model_fields.keys())`
   equals the implementer-verified expected set (cited shape per D4:
   `{has_token, is_first_run, vault_exists, vault_path}`, but exec
   time re-derive trumps plan-doc claim if drift surfaced).
2. **(T1.2)** `packages/brain_api/tests/test_endpoint_token_shape.py`
   exists and asserts `set(TokenResponse.model_fields.keys())` equals
   the verified expected set (cited: `{token}`).
3. **(T1.3)** `packages/brain_api/tests/test_response_envelope_shapes.py`
   (or a name the implementer chooses for the shared-envelope pins)
   exists and asserts `set(ToolResponse.model_fields.keys())` equals
   the verified expected set (cited: `{text, data}`).
4. **(T1.4)** Same test file (or sibling) asserts
   `set(ErrorResponse.model_fields.keys())` equals the verified
   expected set (cited: `{error, message, detail}`).
5. **(T2)** `tasks/plans/20-response-model-pins-and-wrapper-audit.md`
   contains a non-empty `## T2 audit findings` section (markdown
   table with ≥N rows where N is the count of `tools.ts`
   wrapper-fanout helpers inspected — implementer determines N at
   exec time).
6. **(T3)** Branch on T2 findings:
   - For each row marked **DRIFT-HARDCODED** in T2 that the user
     adjudicated as "fix": assert the named wrapper's return type
     in `tools.ts` has been retyped per the tier (propagation via
     `ReturnType<typeof <root>>` OR explicit type-alias OR
     consistent hardcoded shape — choice locked at T3 exec-time
     `AskUserQuestion`).
   - If T2 surfaces zero DRIFT (Plan 19 T4's 7-wrapper surprise was
     point-in-time at Plan 19 close; some may have been re-fixed
     since): T3 closes as zero-fix with a pointer to T2's findings
     table.
7. **(T4)** `tasks/todo.md` row 20 marked ✅; `tasks/lessons.md` has
   a Plan 20 closure section; final stdout line is `PLAN 20 DEMO OK`.

## Tasks

### Theme A — `response_model` pin adoption

#### T1 — Bundled field-set pins for 4 BaseModels

**Files:**
- Create: `packages/brain_api/tests/test_endpoint_setup_status_shape.py`
  — Pydantic introspection pin for `SetupStatusResponse.model_fields`.
- Create: `packages/brain_api/tests/test_endpoint_token_shape.py`
  — Pydantic introspection pin for `TokenResponse.model_fields`.
- Create: `packages/brain_api/tests/test_response_envelope_shapes.py`
  (or equivalent name at implementer's discretion) — Pydantic
  introspection pins for `ToolResponse.model_fields` and
  `ErrorResponse.model_fields` (one test function per envelope).

**Goal:** Close the Plan 19 T1 audit-OK-but-unpinned gap. The 2
unpinned `endpoints/*` BaseModels (`SetupStatusResponse`,
`TokenResponse`) plus the 2 foundational shared envelopes
(`ToolResponse`, `ErrorResponse`) become drift-protected via the
Plan 19 T2.b lightweight pattern. Each pin is ~10-15 LOC — import
the model, assert the field set is exactly what current main HEAD
emits. Future field add/remove/rename fails RED.

**What to do:**
1. **Re-derive shapes at exec time.** For each of the 4 BaseModels,
   open the source file (`packages/brain_api/src/brain_api/endpoints/setup_status.py`,
   `endpoints/token.py`, `responses.py`) and enumerate the
   declared field names. Cited shapes per D4 (point-in-time as of
   authoring):
   - `SetupStatusResponse: {has_token, is_first_run, vault_exists, vault_path}`
   - `TokenResponse: {token}`
   - `ToolResponse: {text, data}`
   - `ErrorResponse: {error, message, detail}`
   - If any shape has drifted, the pin codifies the NEW shape (the
     pin's job is to prevent FUTURE drift, not to retroactively
     enforce yesterday's shape).
2. **Write the pin tests.** Pattern (Plan 19 T2.b precedent):
   ```python
   from brain_api.endpoints.setup_status import SetupStatusResponse

   def test_setup_status_response_field_set() -> None:
       """Pin SetupStatusResponse field set so future drift fails RED."""
       assert set(SetupStatusResponse.model_fields.keys()) == {
           "has_token",
           "is_first_run",
           "vault_exists",
           "vault_path",
       }
   ```
   Mirror for the other 3 BaseModels. Each test ~10-15 LOC. No
   fixture, no handler invocation.
3. **Per-field type + required-direction pins (MANDATORY for
   single-typed fields).** Plan 19 T2's
   `test_endpoint_upload_shape.py` is the canonical precedent:
   one `test_*_field_set` test (strict key-set equality) PLUS
   one `test_*_<field>_is_non_nullable_<type>` test per
   single-typed field (`field.annotation is str` +
   `field.is_required()`). Mirror that two-tier pattern for Plan
   20:
   - **`SetupStatusResponse`** — field-set pin + per-field
     type+required pin for each field (all 4 are single-typed
     primitives — likely `bool`/`bool`/`bool`/`str` or similar;
     re-derive the annotations at exec time per D4).
   - **`TokenResponse`** — field-set pin + `token: str` required
     pin.
   - **`ToolResponse`** — field-set pin + `text: str` required
     pin. SKIP type-annotation pin on `data: dict[str, Any] |
     None` (heterogeneity is intentional per the responses.py
     module docstring — pinning the dict type would lock out
     per-tool data shape variation). Pin only that `data` is
     `not field.is_required()` (i.e., defaults to None).
   - **`ErrorResponse`** — field-set pin + `error: str` + `message:
     str` required pins. SKIP type-annotation pin on `detail:
     dict[str, Any] | None` (same heterogeneity rationale as
     `data`); pin only `not field.is_required()` for `detail`.
4. **Verify locally.** Run the new tests:
   ```bash
   find .venv -name "*.pth" | xargs -I{} chflags 0 {} 2>/dev/null; \
     uv run --package brain_api pytest packages/brain_api/tests/test_endpoint_setup_status_shape.py \
     packages/brain_api/tests/test_endpoint_token_shape.py \
     packages/brain_api/tests/test_response_envelope_shapes.py -v
   ```
   Or the PYTHONPATH-bypass recipe per auto-memory `feedback_uv_uf_hidden.md`
   if `.pth` masking re-asserts mid-test-run.
5. **Append `## T1 outcome`** to this plan doc with per-pin receipts
   (4 pin test files + pass/fail confirmation).

**Per-task review:** combined spec + code-quality. Reviewer
confirms (a) each field-set pin uses `set(...keys()) == {...}`
strict equality (not subset); (b) cited field sets match current
main HEAD at exec time (re-derive if drift surfaced); (c) each
single-typed field across all 4 BaseModels has a per-field
`field.annotation` + `field.is_required()` pin (matches Plan 19
T2's `test_endpoint_upload_shape.py` two-tier shape); (d) envelope
BaseModels' heterogeneous fields (`ToolResponse.data` /
`ErrorResponse.detail`, both `dict[str, Any] | None`) pin only
`not field.is_required()` and skip the type-annotation pin
(heterogeneity intentional per responses.py module docstring);
(e) tests pass on the local recipe + would fail RED on a key
add/remove/rename OR a single-typed field's type-annotation
change in the source BaseModel.

### Theme B — `tools.ts` wrapper-shape audit + tiered fix

#### T2 — `tools.ts` wrapper-fanout audit + findings table

**Files:**
- Modify (findings only): `tasks/plans/20-response-model-pins-and-wrapper-audit.md`
  — append a `## T2 audit findings` section with one row per
  wrapper-fanout helper inspected + verdict (OK-PROPAGATES /
  OK-NARROW-INTENTIONAL / DRIFT-HARDCODED) + notes.

**Goal:** Mirror Plan 19 T1's audit shape on the `tools.ts`
wrapper-shape surface. Plan 19 T4 surfaced 7 `configSet`-routed
wrappers (`setDomainOverride`, `setPrivacyRailed`,
`setDomainBudget`, `setDomainRateLimit`, `setDomainAutonomy`,
`setActiveDomain`, `setCrossDomainWarningAcknowledged`) that all
had hardcoded narrow return types instead of propagating via
`ReturnType<typeof configSet>` or a shared alias. TS covariance
let them compile against the widened `configSet` (the narrower
`{key, value}` is assignable from the wider `ConfigSetData`), but
IDE hover/auto-complete at each wrapper still showed the OLD
shape. Plan 20 T2 audits the rest of the wrapper surface for the
same drift class.

**Surface-of-interest (audit boundary, per Plan 19 T1 lesson):**
- File: `apps/brain_web/src/lib/api/tools.ts` (only).
- Subject: any function declaration with a return type containing
  `Promise<ToolResponse<...>>` — count snapshot at authoring time
  is 21 hardcoded declarations across 47 total exports.
- **Wrapper-fanout helper** definition: a function that calls
  another `tools.ts` function (the "root"), forwards/transforms
  its arguments, and returns the root's response. The drift class
  fires when the wrapper hardcodes a narrower-than-root return
  type that TS covariance silently accepts.
- **Out of scope:** root-level wrappers (functions that call
  `callTool(...)` directly with no intermediate wrapping); these
  ARE the typed surface and explicit hardcoded shapes there are
  intentional design (the wrapper IS the contract).

**What to do:**
1. **Enumerate.** List every function in `tools.ts` whose return
   type contains `Promise<ToolResponse<` (grep recipe:
   `grep -nE "Promise<ToolResponse<" apps/brain_web/src/lib/api/tools.ts`).
   Authoring-time count: 21. Verify at exec time.
2. **Classify each.** For each function, determine:
   - Does it call another `tools.ts` function (wrapper-fanout)
     OR does it call `callTool(...)` directly (root)?
   - If wrapper-fanout: does its return type match the root's
     return type exactly (OK-PROPAGATES — wrapper inherits via
     `ReturnType<typeof <root>>` OR matches the same explicit
     `ToolResponse<Foo>` alias)? OR is it narrower (DRIFT-HARDCODED
     — the Plan 19 T4 shape)?
   - If root: OK-NARROW-INTENTIONAL (the wrapper IS the typed
     surface; explicit return type is the design).
3. **File findings** as a markdown table appended to this plan doc
   under `## T2 audit findings`. Columns: Wrapper | Line | Root
   call (or `callTool`) | Wrapper return type | Root return type
   (if applicable) | Verdict | Notes.
4. **Surface count to user.** At end of T2, count
   DRIFT-HARDCODED rows. Plan 19 T4 found 7 (all routed through
   `configSet`). Plan 20 T2 may find more, fewer, or zero across
   the broader 21-wrapper surface. The count drives T3's tiered
   scope decision.

**Known seed:** the Plan 19 T4 fix landed explicit retyping for
the 7 `configSet`-routed wrappers in commit `7cd2b72` (per Plan 19
closure summary). Auditor should re-verify those 7 are now
**OK-NARROW-INTENTIONAL** (explicit-retype is now consistent with
the root's `ConfigSetData` shape) AND audit the remaining ~14
hardcoded-return-type wrappers for the same drift class.

**Per-task review:** combined spec + code-quality. Reviewer
spot-checks 2-3 random rows by re-reading the wrapper + its root
function (Plan 18 T2 / Plan 19 T1 precedent — sample 3-4 rows and
re-derive verdict). Reviewer confirms the table covers all 21
hardcoded-return-type wrappers OR (if the count changed since
authoring) the current count, and the surface-of-interest
definition is honored.

#### T3 — Fix per-finding (branches on T2 verdicts)

**Files (branches on T2 findings):**

**For each DRIFT-HARDCODED row in T2 that the user adjudicates as
"fix":**
- Modify: `apps/brain_web/src/lib/api/tools.ts` — retype the
  named wrapper to match its root's return shape. Choice of
  retyping mechanism is locked at T3 exec-time `AskUserQuestion`
  (see "What to do" step 2).
- (No backend changes expected — this is pure TS-side
  alignment; if T2 surfaces a wrapper that masks a backend
  drift, treat as a live-consumer bug analogous to Plan 19 T2's
  drop-zone/app-shell fixes and close with the same care.)

**Goal:** close the audit cleanly. Every DRIFT-HARDCODED row the
user opts to fix gets explicit retyping that prevents future
covariance-masked drift.

**What to do:**
1. **Read T2 findings + surface count.** Enumerate
   DRIFT-HARDCODED rows. Plan 19 T4 found 7 (all closed by Plan
   19 T4's commit `7cd2b72`); Plan 20 T2 may find additional ones
   across the broader surface.
2. **Tiered scope decision via `AskUserQuestion`.** Mirrors Plan
   18 T2 / Plan 19 T1 precedent. Surface count + options:
   - **A. Fix all DRIFT-HARDCODED rows inline.** Bundle as a
     single sub-task per Plan 19 T4 cosmetic-bundle precedent
     (no live consumer bugs; same retype pattern; total LOC
     scales with finding count).
   - **B. Fix the N highest-risk inline; defer remainder to
     Plan 21.** If count is large (>10), tier by which wrappers
     have live IDE/auto-complete consumers vs which are purely
     hypothetical drift surfaces.
   - **C. Defer all to Plan 21.** Valid if count is large enough
     to materially balloon Plan 20 OR if the user prefers a
     dedicated wrapper-shape audit plan.
   - **D. Retype mechanism:** (a) explicit shared `type` alias
     (e.g., `type ConfigSetReturn = Promise<ToolResponse<ConfigSetData>>`
     and route the 7 wrappers + root through it); (b)
     `ReturnType<typeof <root>>` propagation; (c) keep explicit
     hardcoded shapes but add an ESLint rule pinning consistency.
     User picks one (or hybrid) at exec time.
3. **Implement chosen fix.** Per the user's tier and retype
   mechanism, modify `tools.ts`. Each fix is ~5-15 LOC per
   wrapper.
4. **Verify.** Run `pnpm vitest run` AND `pnpm tsc --noEmit`
   per auto-memory `feedback_tsc_vs_vitest.md` discipline
   (vitest passing ≠ type correctness; Plan 19 T2 caught
   `activeTab: "all"` slipping past vitest because tsc rejected
   it). Both must be green.
5. **Append `## T3 outcome`** to this plan doc summarizing the
   per-finding receipts + tier locked + retype mechanism chosen.

**Per-task review:** combined spec + code-quality. Reviewer
confirms (a) every DRIFT-HARDCODED row the user opted to fix is
retyped per the locked mechanism; (b) `pnpm tsc --noEmit`
clean (not just vitest); (c) any rows the user opted to defer
are explicitly carried forward to Plan 21 candidate scope in
T4's `todo.md` tail block update; (d) the retype mechanism
choice is recorded in T3 outcome for future plans to follow
the same convention.

### Closure

#### T4 — Closure: demo + lessons + todo + tag

**Files:**
- Create: `scripts/demo-plan-20.py` — assert each gate per the
  demo description above.
- Modify: `tasks/lessons.md` — append a "Plan 20 closure" section.
- Modify: `tasks/todo.md` — row 20 marked ✅ Complete; tail block
  refreshed as "Plan 21 candidate scope" preserving the 4
  NOT-DOING carry-forwards per D5 + any new candidates surfaced
  during Plan 20 execution.
- Tag: `plan-20-response-model-pins-and-wrapper-audit` cut on
  green demo.

**Goal:** land Plan 20 closure following Plan 19 T6's shape.

**What to do:**
1. **`demo-plan-20.py`.** Per D7, the demo asserts each item is
   CLOSED with per-item structural assertions (file existence,
   Pydantic model_fields equality assertion via import + introspect,
   regex match for tools.ts changes per T3's locked mechanism,
   plan-doc table presence for T2 findings). No live LLM, no
   network. Final stdout line on a clean run: `PLAN 20 DEMO OK`.
2. **Lessons.** Plan 20 closure section in `tasks/lessons.md`:
   - "FastAPI `response_model` pin pattern adoption receipt" —
     Plan 19 T2.b's pattern scaled to 4 BaseModels cleanly;
     ~10-15 LOC per pin held; envelope BaseModels skip
     type-annotation pin on heterogeneous `dict[str, Any] | None`
     fields by design.
   - "Plan-author drift caught at authoring, not at execution" —
     Plan 20 D12 precedent: pre-execution grep revealed `routes/*`
     was the wrong surface premise; corrected to `endpoints/*` +
     shared envelopes via user-adjudicated `AskUserQuestion`
     before T1 dispatch. Cheaper than catching drift at
     implementer-time (Plan 16/19 T5 pattern fires at both
     layers).
   - "Wrapper-fanout audit findings" — whatever T2 surfaces
     (count, drift class confirmation/refutation, retype
     mechanism locked).
   - Anything else surfaced during T1-T3 review.
3. **todo.md update.** Row 20 marked ✅; tail block becomes
   "Plan 21 candidate scope" with the 4 preserved NOT-DOING
   carry-forwards per D5 plus any new candidates surfaced
   during Plan 20 execution. Preserved 4 (verbatim from Plan 19
   tail per D5):
   - `seedBrainMd` / `seedScope` rule-of-three (threshold not
     met; re-check at execution if Plan 20 added callers).
   - Per-thread cross-domain confirmation (architectural NO per
     spec §3 + Plan 16 D36).
   - "Topbar scope chip" drift watch (lesson-only per Plan 12).
   - Free-threaded Python PEP 703 for `_cached_ctx` (3.14
     trigger).
   - Plus: `resolve_out_dir` `parents[4]` iCloud hardening
     (Plan 19 T2 surprise #2, deferred from Plan 20 scope per
     user 1.A) — explicitly noted as deferred from Plan 20, not
     dropped.
   - Plus: any T2 findings the user deferred per T3 step 2.C
     (if any).
4. **Tag.** `plan-20-response-model-pins-and-wrapper-audit` cut
   on green `scripts/demo-plan-20.py` + green pytest + green
   vitest + green tsc --noEmit + green CI on macos-14 +
   windows-2022.
5. **Push.** Per D10, after closure tag: single `git push`
   covers Plan 20's commits. User authorization required.

**Per-task review:** combined spec + code-quality. Demo gate
count is not pinned per D7; closure shape mirrors Plan 19 T6.

## Owning subagents

- **brain-mcp-engineer (role-overloaded as brain-api-engineer)** —
  T1 (Python pin tests for the 4 BaseModels in
  `packages/brain_api/tests/`). The CLAUDE.md subagent list does
  NOT include a dedicated `brain-api-engineer` type —
  `brain-mcp-engineer` has handled brain_api work across Plans
  11 + 13 + 14 + 15 + 17 + 19.
- **brain-frontend-engineer** — T2 (TS-side audit of `tools.ts`
  wrapper-shape surface; classify hardcoded-vs-propagation; append
  findings table inline), T3 (TS retyping per user-adjudicated
  tier + retype mechanism; verify with vitest + tsc --noEmit).
- **brain-core-engineer** — T4 (demo script + lessons + closure
  carry-forward management). Demo script asserts mostly TS + AST
  shapes; brain-core-engineer's polish-pass closure precedent (Plan
  17 T17 + Plan 18 T5 + Plan 19 T6) holds.
- **brain-test-engineer** — may collaborate on T1 if the
  Pydantic introspection assertion needs nuance (e.g.,
  required-vs-optional pin for endpoints/* BaseModels per Plan
  19 T2's `_required_field_set` pattern); T2/T3 implementers
  empowered to land tests inline per Plan 18 D5's "combined
  review" practice.
- (No new tasks for brain-prompt-engineer, brain-ui-designer, or
  brain-installer-engineer in Plan 20. No new prompts; no UI
  surface change; no install / packaging change.)

## Workflow rules

Same as Plans 16 + 17 + 18 + 19:
- Sequential per-task dispatch via `superpowers:subagent-driven-development`.
- Combined spec + code-quality review per task.
- Implementer routes back to plan author on any unrecognized rule
  edge case (e.g., T1 BaseModel shape drift surfaced at exec time,
  T2 audit edge cases — what's wrapper-fanout vs root —, T3 tier
  decision adjudication beyond AskUserQuestion).
- Pause every ~3 tasks for user check-in (Plan 18 paused every 3;
  Plan 19 paused at T3; Plan 20's 4-task budget means a pause at
  T3 closure + plan-close after T4).
- No push without explicit user authorization at Plan 20 close
  (D10).
- pytest recipe on this iCloud-synced repo:
  `find .venv -name "*.pth" | xargs -I{} chflags 0 {} 2>/dev/null; uv run pytest <args>`
  on ONE command line. Or PYTHONPATH bypass:
  `unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src uv run --package <pkg> pytest packages/<pkg>/tests -q`.
- Per-task verification on `apps/brain_web/` MUST run BOTH `pnpm
  vitest run` AND `pnpm tsc --noEmit` per auto-memory
  `feedback_tsc_vs_vitest.md` discipline (Plan 19 T2 caught
  `activeTab: "all"` slipping past vitest).
- Visual QA (unlikely needed in Plan 20 — no UI surface change —
  but if T3 surfaces a live consumer bug needing browser
  verification): set `BRAIN_VAULT_ROOT="$HOME/Documents/brain"` +
  `BRAIN_WEB_OUT_DIR=apps/brain_web/out` explicitly on uvicorn
  per auto-memory `feedback_brain_web_out_dir.md`.
- Radix dialogs + axe `waitForAnimationsToFinish` recipe —
  unlikely relevant for Plan 20 (no new dialogs).
- Monkeypatching internal helper calls: patch BOTH helper's
  resolved-at-call-time namespace AND caller's namespace
  (latter `raising=False`) per Plan 17 T17 lesson — unlikely
  relevant for Plan 20 (pin tests read `model_fields` directly,
  no helper interception needed).
- Pydantic v2 `model_validator(mode="after")` does NOT roll back
  the triggering field mutation on raise (CLAUDE.md "What NOT to
  do"). Unlikely relevant for Plan 20 (no schema mutations).
- Hypothesis-first diagnosis (auto-memory
  `feedback_hypothesis_first_diagnosis.md`) — if T2's audit
  surfaces an unexpected drift verdict (e.g., a wrapper looks
  hardcoded but propagation works at runtime), INSTRUMENT before
  assuming the cause.

## File inventory (summary)

```
tasks/plans/
└── 20-response-model-pins-and-wrapper-audit.md   # SELF (this doc);
                                                  # T2 findings table +
                                                  # T1/T3 outcomes
                                                  # appended at exec time

packages/brain_api/
└── tests/
    ├── test_endpoint_setup_status_shape.py       # CREATE: T1.1 pin
    ├── test_endpoint_token_shape.py              # CREATE: T1.2 pin
    └── test_response_envelope_shapes.py          # CREATE: T1.3 + T1.4
                                                  # pins (or sibling
                                                  # filenames at
                                                  # implementer choice)

apps/brain_web/
└── src/lib/api/tools.ts                          # AUDIT (T2);
                                                  # possibly MODIFY (T3)
                                                  # per locked tier +
                                                  # retype mechanism

scripts/
└── demo-plan-20.py                               # CREATE (T4)

tasks/
├── lessons.md                                    # MODIFY: Plan 20 closure
│                                                 # section (T4)
└── todo.md                                       # MODIFY: row 20 ✅ + Plan 21
                                                  # candidate scope tail (T4)
```

## T1 outcome

Closed 2026-05-12. Plan 19 T1 audit-OK-but-unpinned gap closed for all
4 cited BaseModels via the canonical Plan 19 T2 two-tier shape (one
strict-equality field-set pin + one per-field `field.annotation` +
`field.is_required()` pin for each single-typed field, with the
heterogeneous `dict[str, Any] | None` fields pinning only
non-required defaulting per the spec D4 / responses.py module
docstring).

### (a) Pin test files created

| # | Sub-fix | File path | LOC | Tests |
|---|---------|-----------|-----|-------|
| T1.1 | `SetupStatusResponse` | `packages/brain_api/tests/test_endpoint_setup_status_shape.py` | 70 | 5 (1 field-set + 4 per-field type+required) |
| T1.2 | `TokenResponse` | `packages/brain_api/tests/test_endpoint_token_shape.py` | 41 | 2 (1 field-set + 1 per-field type+required) |
| T1.3 + T1.4 | `ToolResponse` + `ErrorResponse` | `packages/brain_api/tests/test_response_envelope_shapes.py` | 117 | 7 (2 field-set + 5 per-field — 3 type+required for single-typed `str` fields + 2 non-required pins for heterogeneous `dict[str, Any] | None` fields) |

### (b) Actual field sets verified at exec time

Re-derived from current main HEAD at task exec; **no drift vs plan-doc
citations**. All 4 BaseModels match the §T1 step 1 specification
exactly:

- `SetupStatusResponse.model_fields.keys() == {has_token, is_first_run, vault_exists, vault_path}` — all 4 single-typed primitives (`bool`/`bool`/`bool`/`str`), all required.
- `TokenResponse.model_fields.keys() == {token}` — single-typed `str`, required.
- `ToolResponse.model_fields.keys() == {text, data}` — `text: str` required; `data: dict[str, Any] | None` defaults to None (type-annotation pin skipped per heterogeneity rationale).
- `ErrorResponse.model_fields.keys() == {error, message, detail}` — `error: str` + `message: str` required; `detail: dict[str, Any] | None` defaults to None (type-annotation pin skipped per heterogeneity rationale).

### (c) Shape drift surfaced

**None.** Plan-doc citations matched current main HEAD on first
inspection — no codification of new shape required.

### (d) Test run output

Recipe used per `feedback_uv_uf_hidden.md` (chflags + pytest on the
same command line so Spotlight can't re-hide the `.pth` files):

```text
$ find .venv -name "*.pth" | xargs -I{} chflags 0 {} 2>/dev/null; \
  uv run --package brain_api pytest \
  packages/brain_api/tests/test_endpoint_setup_status_shape.py \
  packages/brain_api/tests/test_endpoint_token_shape.py \
  packages/brain_api/tests/test_response_envelope_shapes.py -v

============================== 14 passed, 5 warnings in 0.02s ===============================
```

Coverage: 14 tests total across the 3 new files. All PASSED. The 5
warnings are pre-existing global `DeprecationWarning`s from the
`<frozen importlib._bootstrap>` SWIG bindings (unrelated to this
task).

### Per-task review confirmation

- (a) Each field-set pin uses `set(...keys()) == {...}` strict equality — confirmed across all 4 BaseModels.
- (b) Cited field sets match current main HEAD at exec time — confirmed, no drift.
- (c) Per-field `field.annotation` + `field.is_required()` pin for each single-typed field across all 4 BaseModels — confirmed: 4 (SetupStatus) + 1 (Token) + 1 (ToolResponse.text) + 2 (ErrorResponse.error + message) = 8 type+required pins.
- (d) Heterogeneous fields (`ToolResponse.data` / `ErrorResponse.detail`, both `dict[str, Any] | None`) pin only `not field.is_required()` and skip the type-annotation pin — confirmed in both cases with inline rationale citing the responses.py module docstring.
- (e) Tests would fail RED on any key add/remove/rename OR any single-typed field's type-annotation change — confirmed (strict equality + `field.annotation is X` mechanics).

## T2 audit findings

Closed 2026-05-12. Surface enumerated at `apps/brain_web/src/lib/api/tools.ts`
current main HEAD. Single-line grep recipe (`grep -nE "Promise<ToolResponse<"`)
returned 21 lines (matches plan-doc authoring-time count), but multi-line
return-type declarations push the **actual wrapper count to 45** (38 root +
7 wrapper-fanout). Plan-doc's "21" figure was a single-line-grep artefact;
exec-time re-derivation per D4 surfaces the true count. The non-wrapper
exports `AUTONOMY_CATEGORIES` (l. 786) and `ALL_TOOL_NAMES` (l. 1246) are
read-only tuples and out of scope.

### Verdict summary

| Verdict | Count |
|---------|-------|
| **OK-PROPAGATES** (wrapper-fanout sharing explicit `ToolResponse<Foo>` alias with root) | 7 |
| **OK-NARROW-INTENTIONAL** (root calling `callTool(...)` directly with explicit shape) | 38 |
| **DRIFT-HARDCODED** | **0** |
| **INVESTIGATE** | 0 |
| **TOTAL** | 45 |

**Plan 19 T4's 7-wrapper drift class is fully closed.** All 7 `configSet`-routed
wrappers (`setDomainOverride`, `setPrivacyRailed`, `setDomainBudget`,
`setDomainRateLimit`, `setDomainAutonomy`, `setActiveDomain`,
`setCrossDomainWarningAcknowledged`) now declare
`Promise<ToolResponse<ConfigSetData>>` — identical to `configSet`'s root
return type — via the shared explicit named alias `ConfigSetData` (defined
once at l. 628-634, referenced by `configSet` at l. 639 + each wrapper).
Per the verdict guidance, this is OK-PROPAGATES — the wrappers share an
explicit alias with the root, so IDE hover/auto-complete at any of the 8
sites surfaces the same five-field shape (`status`, `key`, `value`,
`persisted`, `note`). No DRIFT-HARDCODED rows surfaced across the broader
38-root surface either; every root wrapper is intentionally narrow per the
"wrapper IS the typed surface" design.

### Findings table

| Wrapper | Line | Root call | Wrapper return type | Root return type | Verdict | Notes |
|---------|-----:|-----------|---------------------|------------------|---------|-------|
| `listDomains` | 100 | `callTool` (l. 107) | `ToolResponse<{ domains, entries?, active_domain? }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline shape. Plan 10/11 added optional fields. |
| `getIndex` | 123 | `callTool` (l. 132) | `ToolResponse<{ domain, frontmatter, body }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — Plan 18 T3.2 narrowed to backend shape. |
| `readNote` | 139 | `callTool` (l. 148) | `ToolResponse<{ path, frontmatter, body }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline shape. |
| `search` | 155 | `callTool` (l. 158) | `ToolResponse<{ hits: SearchHit[], top_k_used }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — references `SearchHit` interface. |
| `recent` | 171 | `callTool` (l. 174) | `ToolResponse<{ items: RecentEntry[], limit_used }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — Plan 19 T4.1 widened to include `limit_used`. |
| `listThreads` | 189 | `callTool` (l. 192) | `ToolResponse<{ threads: ChatThreadEntry[] }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — references `ChatThreadEntry` interface. |
| `exportThread` | 197 | `callTool` (l. 209) | `ToolResponse<{ thread_id, path, domain, markdown, filename, byte_length }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline shape (Issue #17). |
| `getBrainMd` | 228 | `callTool` (l. 231) | `ToolResponse<{ exists, body }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — Plan 18 T3.3 narrowed to backend shape. |
| `ingest` | 263 | `callTool` (l. 268) | `ToolResponse<IngestResultData>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — references `IngestResultData` discriminated union (l. 253). |
| `classify` | 271 | `callTool` (l. 281) | `ToolResponse<{ domain, confidence, [extra] }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline shape with escape hatch. |
| `bulkImport` | 336 | `callTool` (l. 341) | `ToolResponse<BulkImportData>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — references `BulkImportData` discriminated union (l. 319). |
| `proposeNote` | 356 | `callTool` (l. 363) | `ToolResponse<{ status, patch_id, target_path }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — Plan 19 T4.2 widened to include `status`. |
| `listPendingPatches` | 379 | `callTool` (l. 382) | `ToolResponse<{ count, patches: PendingPatch[] }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — Plan 19 T4.3 widened to include `count`. |
| `getPendingPatch` | 394 | `callTool` (l. 402) | `ToolResponse<{ envelope, patchset }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — opaque `Record<string, unknown>` payload shape. |
| `applyPatch` | 408 | `callTool` (l. 418) | `ToolResponse<{ patch_id, undo_id, applied_files, [extra] }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline shape with escape hatch. |
| `rejectPatch` | 438 | `callTool` (l. 444) | `ToolResponse<{ status: "rejected", patch_id, reason }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — Plan 18 T3.6 narrowed to backend shape. |
| `undoLast` | 472 | `callTool` (l. 475) | `ToolResponse<UndoLastData>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — references `UndoLastData` discriminated union (l. 468). |
| `costReport` | 496 | `callTool` (l. 504) | `ToolResponse<{ today_usd, month_usd, by_domain, by_mode }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — Plan 18 T3.8 narrowed to backend shape. |
| `lint` | 526 | `callTool` (l. 529) | `ToolResponse<{ status, message }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — Plan 18 T3.4 narrowed to stub-reality shape. |
| `configGet` | 532 | `callTool` (l. 535) | `ToolResponse<{ key, value }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline shape; read-only counterpart to `configSet`. |
| `repairConfig` | 582 | `callTool` (l. 583) | `ToolResponse<RepairConfigData>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — references `RepairConfigData` interface (l. 569). |
| `repairConfigApply` | 593 | `callTool` (l. 598) | `ToolResponse<{ status, path, config_version }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline shape. |
| `configSet` | 636 | `callTool` (l. 640) | `ToolResponse<ConfigSetData>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — references `ConfigSetData` interface (l. 628). Plan 19 T4.4 widened to include `status`/`persisted`/`note`. **Spot-check root for the 7 fanout rows below.** |
| `setDomainOverride` | 663 | `configSet` (l. 668) | `ToolResponse<ConfigSetData>` | `ToolResponse<ConfigSetData>` (l. 639) | OK-PROPAGATES | Wrapper-fanout. Shares explicit `ConfigSetData` alias with root. Plan 19 T4 closure verified — was DRIFT-HARDCODED pre-`7cd2b72`, now aligned. |
| `setPrivacyRailed` | 680 | `configSet` (l. 683) | `ToolResponse<ConfigSetData>` | `ToolResponse<ConfigSetData>` (l. 639) | OK-PROPAGATES | Wrapper-fanout. Shares explicit `ConfigSetData` alias. Plan 19 T4 closure verified. |
| `setDomainBudget` | 714 | `configSet` (l. 718) | `ToolResponse<ConfigSetData>` | `ToolResponse<ConfigSetData>` (l. 639) | OK-PROPAGATES | Wrapper-fanout. Whole-`BudgetCap`-payload semantics (see docstring l. 699-713). Plan 19 T4 closure verified. |
| `setDomainRateLimit` | 756 | `configSet` (l. 761) | `ToolResponse<ConfigSetData>` | `ToolResponse<ConfigSetData>` (l. 639) | OK-PROPAGATES | Wrapper-fanout. Whole-`RateLimitOverride`-payload semantics. Plan 19 T4 closure verified. |
| `setDomainAutonomy` | 812 | `configSet` (l. 817) | `ToolResponse<ConfigSetData>` | `ToolResponse<ConfigSetData>` (l. 639) | OK-PROPAGATES | Wrapper-fanout. Per-leaf semantics (one Switch = one wrapper call). Plan 19 T4 closure verified. |
| `setActiveDomain` | 832 | `configSet` (l. 835) | `ToolResponse<ConfigSetData>` | `ToolResponse<ConfigSetData>` (l. 639) | OK-PROPAGATES | Wrapper-fanout. Self-documenting wrapper around `configSet({key:"active_domain", value:slug})`. Plan 19 T4 closure verified. |
| `setCrossDomainWarningAcknowledged` | 850 | `configSet` (l. 853) | `ToolResponse<ConfigSetData>` | `ToolResponse<ConfigSetData>` (l. 639) | OK-PROPAGATES | Wrapper-fanout. Self-documenting wrapper for the cross-domain-modal acknowledgment flag. Plan 19 T4 closure verified. |
| `recentIngests` | 865 | `callTool` (l. 868) | `ToolResponse<{ ingests: RecentIngestEntry[] }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — Plan 18 T3.1 renamed outer key `items` → `ingests`. |
| `createDomain` | 882 | `callTool` (l. 893) | `ToolResponse<{ status: "created", domain: {slug, name, accent_color}, note }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — Plan 18 T3.10 narrowed to backend-nested shape. |
| `renameDomain` | 900 | `callTool` (l. 912) | `ToolResponse<{ from, to, files_updated, [extra] }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline shape with escape hatch. |
| `budgetOverride` | 936 | `callTool` (l. 947) | `ToolResponse<{ status: "override_set", override_until, override_delta_usd, note }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — Plan 18 T3.11 narrowed to backend shape. |
| `forkThread` | 962 | `callTool` (l. 969) | `ToolResponse<{ new_thread_id }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline single-field shape. |
| `brainMcpInstall` | 980 | `callTool` (l. 995) | `ToolResponse<{ status, config_path, backup_path, server_name, [extra] }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline shape with escape hatch. |
| `brainMcpUninstall` | 1007 | `callTool` (l. 1018) | `ToolResponse<{ status, config_path, backup_path?, server_name, [extra] }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline shape; `backup_path` optional vs install. |
| `brainMcpStatus` | 1030 | `callTool` (l. 1044) | `ToolResponse<{ status, config_path, config_exists, entry_present, executable_resolves, command, server_name, [extra] }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline shape (7 fields + extra). |
| `brainMcpSelftest` | 1060 | `callTool` (l. 1075) | `ToolResponse<{ status, ok, config_exists, entry_present, executable_resolves, command, config_path, server_name, [extra] }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline shape (8 fields + extra). |
| `brainSetApiKey` | 1094 | `callTool` (l. 1107) | `ToolResponse<{ status, provider, env_key, masked, path, [extra] }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline shape; plaintext key NEVER echoed. |
| `brainPingLlm` | 1122 | `callTool` (l. 1134) | `ToolResponse<{ ok, provider, model, latency_ms, error?, [extra] }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline shape; failures returned in envelope. |
| `brainBackupCreate` | 1156 | `callTool` (l. 1170) | `ToolResponse<{ status, backup_id, path, trigger, created_at, size_bytes, file_count, [extra] }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline shape (7 fields + extra). |
| `brainBackupList` | 1182 | `callTool` (l. 1184) | `ToolResponse<{ backups: BackupEntry[] }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — references `BackupEntry` interface (l. 1145). |
| `brainBackupRestore` | 1191 | `callTool` (l. 1202) | `ToolResponse<{ status, backup_id, trash_path, [extra] }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline shape; requires `typed_confirm=true`. |
| `brainDeleteDomain` | 1216 | `callTool` (l. 1229) | `ToolResponse<{ status, slug, trash_path, files_moved, undo_id, [extra] }>` | n/a (root) | OK-NARROW-INTENTIONAL | Root — explicit inline shape; requires `typed_confirm=true`. |

### Surface count → T3 scope decision

**0 DRIFT-HARDCODED rows.** Per D2's audit-then-size shape, T3's tiered
`AskUserQuestion` will surface a zero-fix branch (option 2.C "Defer all"
becomes the structural default — there's nothing to fix). Plan 19 T4's
commit `7cd2b72` already aligned the 7 known wrappers, and the broader
38-root surface has zero rows where TS covariance was masking
narrower-than-root return types. The 4-task Plan 20 budget closes cleanly
with T3 as a zero-fix closure plus a pointer-to-this-section receipt.

### Reproducibility

For any row above, the verdict can be re-derived in <30 seconds via:

1. Open `apps/brain_web/src/lib/api/tools.ts` to the cited wrapper line.
2. Inspect the body (`callTool` = root, anything else = fanout).
3. For fanouts: open the root function's line, compare the return-type
   declarations character-by-character.
4. For the 7 OK-PROPAGATES rows: each wrapper's return type is
   `Promise<ToolResponse<ConfigSetData>>` (matches `configSet`'s line 639
   declaration exactly).

Spot-check seeds (for reviewer's 2-3-row sampling):

- **`setActiveDomain` (l. 832)** — wrapper body at l. 835 is
  `configSet({ key: "active_domain", value: slug })`; root return type at
  l. 639 is `Promise<ToolResponse<ConfigSetData>>`; wrapper return type at
  l. 834 is also `Promise<ToolResponse<ConfigSetData>>`. Match. Verdict
  OK-PROPAGATES.
- **`brainBackupList` (l. 1182)** — wrapper body at l. 1184 is
  `callTool<{ backups: BackupEntry[] }>("brain_backup_list")`; no
  intermediate fanout. Verdict OK-NARROW-INTENTIONAL.
- **`bulkImport` (l. 336)** — wrapper body at l. 341 is
  `callTool<BulkImportData>("brain_bulk_import", args)`; references the
  `BulkImportData` discriminated union (l. 319). Root, explicit alias.
  Verdict OK-NARROW-INTENTIONAL.

## T3 outcome

Closed 2026-05-12. **Zero-fix closure.** T2 audit (commit `8ee3ba5`) surfaced
0 DRIFT-HARDCODED rows across all 45 wrappers in `apps/brain_web/src/lib/api/tools.ts`.
Per D2's audit-then-size + Q3=3.A tiered `AskUserQuestion` at exec time, the
user adjudicated **T3.A: zero-fix closure** — no source modifications.

### Tier locked

**T3.A — Zero-fix closure.** Plan 19 T4's `7cd2b72` commit (the 7-wrapper
`configSet` fix) is comprehensive; the broader 38-root surface is also
drift-free. Adding regression pins for a non-existent drift class would
be over-engineering per CLAUDE.md "engineered enough" principle.

### Retype mechanism chosen

**N/A — zero fixes mean no retyping needed.** For posterity / future plans:
the codebase's established convention is **explicit shared named alias**
(e.g., `ConfigSetData` interface at `tools.ts:628-634`, referenced by
`configSet` root at l. 639 + each of the 7 fanout wrappers). Future
wrapper-fanout helpers SHOULD adopt the same shape: declare a named
interface for the data payload, reference it via `Promise<ToolResponse<Foo>>`
at both root and wrappers.

### Regression check receipts

- `pnpm vitest run` — `Test Files 81 passed (81) | Tests 496 passed | 1 skipped (497) | Duration 6.07s`
- `pnpm tsc --noEmit` — clean exit (no errors)

Both verified at T3 close on current main HEAD (commit before T3 = `8ee3ba5`).

### Deferred to Plan 21 candidate

**None from T2 audit.** All 45 wrappers classified at T2 close:
0 DRIFT-HARDCODED, 7 OK-PROPAGATES, 38 OK-NARROW-INTENTIONAL.
No rows deferred.

### Per-row-shape commentary (forward-looking)

If a future plan adds new wrapper-fanout helpers in `tools.ts`, the
audit pattern is reproducible: `grep -nE "Promise<ToolResponse<"`,
trace each match's body for `callTool(...)` (root) vs another tools.ts
fn (fanout), check return-type alignment with root. The 45-row T2
findings table is the canonical reference shape for future audits.

## T4 outcome

_Filled in at T4 close. Demo gate count + commits + tag SHA +
push receipt._

## Plan 21 candidate scope

Filled in at T4 closure. The canonical record is the tail block of
`tasks/todo.md`; this section is a brief pointer. Preserved Plan 17 /
earlier carry-forwards per D5 (4 NOT-DOING items, unchanged from Plan
19 tail):

- `seedBrainMd` / `seedScope` rule-of-three (threshold not met).
- Per-thread cross-domain confirmation (architectural NO per spec §3 +
  Plan 16 D36).
- Topbar scope chip drift watch (lesson-only per Plan 12).
- Free-threaded Python PEP 703 for `_cached_ctx` (3.14 timeline
  trigger).

Plus carryforward of Plan 19's deferred candidate (per user 1.A
locking Small Plan 20 = #6 + #7, NOT #5):

- `resolve_out_dir` `parents[4]` iCloud / uv-editable hardening
  (Plan 19 T2 surprise #2; `BRAIN_WEB_OUT_DIR` env override is the
  durable workaround; cross-platform sweep territory).

Plus any new candidates surfacing from Plan 20 execution.

## Review

_Filled in at T4 close. Tag SHA + closure summary + bumps + verification
receipts + backlog forward._

---

**End of Plan 20.**
