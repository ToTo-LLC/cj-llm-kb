# Plan 17 — Residuals + spec annotations

**Authored:** 2026-05-08 (post Plan 16 close on 2026-05-08, tag
`plan-16-comprehensive-carry-forward` at `67d10d4`).
**Scope:** RESIDUALS ONLY. Plan 16 closed every Theme 10 architectural
move under locked decision 1.B; Plan 17 collects the carry-forwards
that surfaced during Plan 16 reviews + the closure stack's CI cascade.
**Shape:** 19 tasks across 4 themes + 1 closure task. Mirrors Plan 15's
polish-pass shape (10 tasks) at ~2× scale; per-task ~20-50 LOC budget;
combined spec + code-quality review per task per Plan 16 D35.

## At a glance

- **Theme A — Production wiring closure** (T1-T9): close architectural
  gaps from Plan 16 reviews (brain_api e2e, hot-reload completeness,
  zustand consumer migration, AST drift detection, doc cleanup, brain_mcp
  test extraction, no-mutate audit).
- **Theme B — Mypy + test debt** (T10-T11): Plan 15 carry-forward
  (`test_mcp_session_list_domains`) + remaining brain_api mypy debt
  (test annotation gaps + `auth.py:135` no-any-return + `schema.py:77`
  unused-ignore — the rank_bm25 + webvtt portion was closed in Plan 16
  closure stack `51a15db`).
- **Theme C — Spec annotations** (T12-T15): four spec edits + one design
  question that needs locking (multi-domain chat per-call enforcement
  — see locked decisions below).
- **Theme D — Misc tidy-ups** (T16-T18): three small cleanup tasks
  bundled.
- **Closure** (T19): demo + lessons + todo.md + tag.

## Why this plan exists (1-paragraph)

Plan 16 shipped 47 tasks under locked decision 1.B "full production."
Each task had narrow ~20-50 LOC PR shape with combined spec + code
review per task. Reviews surfaced 21 small carry-forwards that were too
narrow to land inline in Plan 16 (would have violated the per-task LOC
budget) but are real production-correctness or documentation gaps. Plan
16 closure (T47) filed them as Plan 17 candidate scope; the user
locked option (a) "single Plan 17 covering all four deliverables." This
plan executes that scope sequentially.

## Locked decisions

| # | Decision | Status | Why |
|---|---|---|---|
| D1 | **Single Plan 17, NOT split into 17 + 18.** | locked (user) | User chose option (a) over (b)/(c)/(d) at Plan 16 close. Single plan keeps the residuals together; faster to close than two phased plans. |
| D2 | **Per-task ~20-50 LOC PR shape; combined spec + code review per task.** | locked | Mirrors Plan 16 D35 / Plan 15 D11. Confirmed at 47-task scale in Plan 16. |
| D3 | **Sequential dispatch via `superpowers:subagent-driven-development`.** | locked | Same as Plan 16 / Plan 15. No parallelization. |
| D4 | **Multi-domain chat per-call enforcement (T13) — locked policy: NO ENFORCEMENT.** When a chat session has `len(config.domains) > 1`, `PerDomainBudgetGuard.check_for(domain=None)` no-ops. The spec annotation in T13 makes this explicit. | recommended; needs user sign-off before T13 | Plan 16 T28.5 implemented this as the multi-domain branch; the spec didn't capture the rationale. The alternative (enforce most-restrictive cap, OR enforce all caps independently) requires either picking a domain canonically (which the multi-domain mode deliberately doesn't) or short-circuiting on first violation (which couples the gate to query-time domain resolution). Locking "no enforcement" matches today's behavior and surfaces the trade-off in spec for future re-litigation. |
| D5 | **Spec annotations land in `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` directly, no new spec file.** | locked | Plan 16 T47 added 3 footnotes; Plan 17 T12-T15 add 4 more (or modify existing sections). Single source of truth. |
| D6 | **No new dependencies.** Plan 17 ships zero new pip / npm packages. | locked | All Plan 17 work is closure / docs / refactor. |
| D7 | **No demo gate count target.** Plan 17's demo asserts the residuals are CLOSED (e.g., grep for `autonomous.ingest` in docstrings returns 0); it doesn't enumerate gates 1..N. Mirrors Plan 11's "demo asserts the deferral closure" shape. | locked | The 47-gate demo in Plan 16 was a closure-of-Plan-16-themes artifact; Plan 17 is closure-of-Plan-16-residuals which doesn't carry the same gate-count contract. |

## Tech stack

Same as Plan 16: Python 3.12, pydantic v2, mypy --strict, ruff, vitest,
Playwright. No new tools. No new dependencies. CI runs on macos-14 +
windows-2022 per Plan 14's matrix.

## Demo gate description

`scripts/demo-plan-17.py` asserts:
- Each carry-forward is CLOSED (per-item assertion: file no longer
  contains the stale string, function exists at the new location, the
  spec section has the new annotation, etc.).
- Final line: `PLAN 17 DEMO OK`.

## Tasks

### Theme A — Production wiring closure

#### T1 — brain_api production AnthropicProvider e2e integration test

**Files:**
- Create: `packages/brain_api/tests/test_anthropic_e2e.py` (pytest-marked
  `integration`; skipped without `ANTHROPIC_API_KEY` env var).
- Modify: `.github/workflows/ci.yml` (add optional `integration` step
  gated on a `secrets.ANTHROPIC_TEST_API_KEY` repo secret; gracefully
  skips if absent).

**Goal:** Plan 16 T31.5 + T39.5 wired the per-domain rate-limit gate
end-to-end through brain_api's lifespan, but coverage is unit + pin
tests only. Add ONE end-to-end integration test exercising the full
brain_api → AnthropicProvider → leaky-bucket gate path with a real API
key fixture.

**What to do:**
1. **Test.** Use `pytest.mark.integration` or `@pytest.mark.skipif(
   "ANTHROPIC_API_KEY" not in os.environ)`. Construct a real
   `AnthropicProvider` via `_lifespan`, configure `rate_limit_per_domain
   = {"research": RateLimitOverride(requests_per_minute=2)}`, send 3
   tool calls in quick succession, assert the 3rd is queued or raises
   `RateLimitExceeded`.
2. **CI.** Optional integration step in ci.yml. Defaults to skip on PRs;
   runs on push-to-main if the test API key secret is set.

**Per-task review:** combined spec + code-quality. Review must verify
the integration step doesn't fail when the secret is unset.

#### T2 — brain_api ConfigWatcher live ctx.config update

**Files:**
- Modify: `packages/brain_api/src/brain_api/app.py` (`_lifespan` /
  `_on_config_change` callback).
- Create: `packages/brain_api/tests/test_lifespan_hot_reload.py` (or
  extend `test_lifespan_anthropic_wiring.py`).

**Goal:** Plan 16 T35 wired ConfigWatcher into brain_api's lifespan and
T39.5 added `_reset_ctx_cache` for brain_mcp, but brain_api's
`AppContext.tool_ctx.config` is read once at lifespan startup and never
re-read. Hot-reload works for fresh tool calls (each calls
`resolve_config`), but any code path that inspects `app.state.tool_ctx.config`
directly will see the stale snapshot.

**What to do:**
1. **Update on watcher event.** When `_on_config_change` fires, in
   addition to `invalidate_cache_for(config_path)`, also call
   `resolve_config(...)` and update `app.state.ctx.tool_ctx.config = new`.
   `ToolContext` is `frozen=True` per Plan 11; mutate in-place via
   `__dict__` assignment (Plan 16 T36 precedent).
2. **Pin test.** Mock the filesystem write event; assert
   `app.state.ctx.tool_ctx.config` updates within the debounce window
   (~100ms).

**Per-task review:** combined spec + code-quality. The frozen-dataclass
mutation needs explicit justification.

#### T3 — Migrate panel-budget to budget-store

**Files:**
- Modify: `apps/brain_web/src/components/settings/panel-budget.tsx`
  (replace inline `configGet`/`configSet` with `useBudget()` hook +
  `useBudgetStore` actions).
- Modify: `apps/brain_web/tests/unit/panel-budget.test.tsx` (mock the
  store instead of the API).

**Goal:** Plan 16 T43 created `budget-store.ts` + `useBudget()` hook
but did NOT migrate the existing consumers. Migrate panel-budget.tsx
first.

**What to do:** mechanical refactor; mirror panel-domains-row.tsx's
zustand consumption pattern.

**Per-task review:** combined spec + code-quality. No behavior change;
test deltas should be near-zero.

#### T4 — Migrate panel-domains-row to domain-overrides-store

**Files:**
- Modify: `apps/brain_web/src/components/settings/panel-domains-row.tsx`.
- Modify: `apps/brain_web/tests/unit/panel-domains-row.test.tsx`.

**Goal:** Same shape as T3 for the per-row LLM override editor.

**What to do:** mechanical migration; same pattern.

**Per-task review:** combined spec + code-quality.

#### T5 — Migrate domain-override-form to domain-overrides-store

**Files:**
- Modify: `apps/brain_web/src/components/settings/domain-override-form.tsx`.
- Modify: `apps/brain_web/tests/unit/domain-override-form.test.tsx`.

**Goal:** Same shape as T3/T4 for the form component.

**What to do:** mechanical migration; same pattern.

**Per-task review:** combined spec + code-quality.

#### T6 — TS-side AutonomyCategory drift detection

**Files:**
- Modify: `apps/brain_web/tests/unit/autonomy-category-drift.test.ts`
  (NEW or extend an existing schema-drift test).
- Possibly create: `apps/brain_web/scripts/check-autonomy-category-drift.ts`
  if a runtime check is preferred.

**Goal:** `AutonomyCategoryFlags` is defined in both Python (Pydantic
`Config.autonomous`) and TypeScript (`AutonomyCategory` literal union
in `lib/api/tools.ts`). T37 + T40 reviewers flagged drift risk. Add a
TS-side test that asserts the 5-flag set (`new_files`, `edits`,
`index_entries`, `concepts`, `draft`) is the canonical surface; if it
changes Python-side without TS-side, the test fails fast.

**What to do:**
1. **Test fixture.** TypeScript test reads a JSON fixture (committed at
   `apps/brain_web/tests/fixtures/autonomy-categories.json`) listing
   the 5 flags. The fixture is also referenced by a brain_core pytest
   that asserts `AutonomyCategoryFlags.model_fields.keys()` matches.
2. **Drift catches.** If Python adds a 6th flag without updating the
   fixture, brain_core pytest fails. If TS adds a 6th to the union
   without updating the fixture, vitest fails. The fixture is the
   pinned source of truth.

**Per-task review:** combined spec + code-quality. Confirm the fixture
location is reachable from both sides without symlinks.

#### T7 — Stale autonomous.ingest doc/comment cleanup

**Files:**
- Modify: `packages/brain_core/src/brain_core/tools/config_set.py:9`
  (module docstring example).
- Modify: `packages/brain_core/src/brain_core/tools/ingest.py:192`
  (inline comment).

**Goal:** Plan 16 T40 dropped the legacy flat `autonomous.<flag>` keys
from `_SETTABLE_KEYS`, but two doc/comment references at known line
numbers still mention them. Cosmetic but drift-tracking matters.

**What to do:** 2-line edits. Replace `autonomous.ingest` with
`autonomous.research.new_files` (the T40 wildcard shape) in both
locations.

**Per-task review:** combined spec + code-quality. Trivial; review
focuses on whether other stale references exist.

#### T8 — Extract `_on_config_change` to module-level (brain_mcp)

**Files:**
- Modify: `packages/brain_mcp/src/brain_mcp/__main__.py` (lift the
  callback out of the `_run` async function).
- Modify: `packages/brain_mcp/tests/test_ctx_cache_reset.py` (replace
  the inline reconstruction with a direct import of the lifted callback).

**Goal:** Plan 16 T35 review noted that the watcher callback is a
closure inside `_run`, making it awkward to unit-test directly. Extract
to a module-level function so test imports are clean.

**What to do:**
1. Lift `_on_config_change` to module level. It needs `config_path`
   (closure over) but can take that as a parameter or be partial-applied.
2. Update the test to import the function directly.

**Per-task review:** combined spec + code-quality.

#### T9 — Audit `_resolve_config` no-mutate contract

**Files:**
- Audit: `packages/brain_core/src/brain_core/tools/apply_patch.py`
  + every consumer that calls `_resolve_config(ctx)`.
- Modify (if needed): apply_patch.py if a defensive copy is warranted.
- Findings: append "T9 audit findings" to this plan file.

**Goal:** T39.5 made `apply_patch._resolve_config` read live `ctx.config`
(no longer a defaults-only snapshot). Confirm no future consumer
mutates the returned reference.

**What to do:**
1. **Audit.** Grep `_resolve_config(` across packages/. For each
   consumer, verify the returned Config is read-only.
2. **Decide.** If any consumer mutates, either (a) refactor to not
   mutate, OR (b) make `_resolve_config` return a deepcopy. Default:
   audit-only with a doc note enforcing the read-only contract.
3. **Findings.** "T9 audit findings" in plan doc.

**Per-task review:** combined spec + code-quality.

### Theme B — Mypy + test debt closure

#### T10 — Pre-existing test_mcp_session_list_domains failure

**Files:**
- Modify: `packages/brain_mcp/tests/test_session.py` (or wherever the
  test lives — locate via grep).

**Goal:** Plan 15's `raise_if_no_config` refactor residue. The test's
None-config setup needs migration to the new helper.

**What to do:**
1. **Locate.** Grep for `test_mcp_session_list_domains`.
2. **Migrate.** Replace the deprecated None-config assertion with the
   `raise_if_no_config(ctx, tool_name)` shape per Plan 15 D7.
3. **Pin.** Existing assertions adapt to the new error wording.

**Per-task review:** combined spec + code-quality. Verify the test
actually runs in current CI (was it being skipped silently?).

**T10 outcome (2026-05-11): ALREADY-DONE — no migration needed.**
The audit found that:
- The named test `test_mcp_session_list_domains` lives at
  `packages/brain_mcp/tests/test_tool_list_domains.py:32` and is a
  happy-path session-level test against a real seeded vault. It passes
  in current CI; was never failing post-Plan-15.
- The `raise_if_no_config` migration for `brain_list_domains` was
  already shipped in Plan 15 Task 8. Production callers:
  `packages/brain_core/src/brain_core/tools/list_domains.py:91,104`.
- The None-config behavior is pinned by
  `packages/brain_core/tests/tools/test_errors_raise_if_no_config.py
  ::test_list_domains_uses_helper` plus the parametrized helper tests
  covering every Plan-15 migrated tool. All green.
- The plan author's mental model was stale; T10 had nothing to do.
Closing T10 as already-done; no commit beyond this plan-doc update.

#### T11 — brain_api mypy debt closure (residuals)

**Files:**
- Modify: `packages/brain_api/src/brain_api/auth.py:135` (no-any-return).
- Modify: `packages/brain_api/src/brain_api/schema.py:77` (unused-ignore).
- Modify: `packages/brain_api/tests/**/*.py` (test annotation gaps;
  count + fix).
- Possibly modify: `packages/brain_api/pyproject.toml` (mypy strict
  config — confirm scope).

**Goal:** Plan 16 closure stack `51a15db` closed the `rank_bm25` +
`webvtt` portion; remaining brain_api mypy debt (~17 errors) needs
sweeping.

**What to do:**
1. **Run.** `cd packages/brain_api && uv run mypy --strict src tests
   2>&1 | head -50`. Capture full error list.
2. **Categorize.** Per-error: real type bug, missing annotation, or
   genuine pre-existing untyped third-party. Fix or `# type: ignore[...]`
   as appropriate.
3. **Add CI step.** Once green, add `mypy --strict` for brain_api to
   ci.yml as a hard-fail gate (mirrors brain_core's existing step).

**Per-task review:** combined spec + code-quality. Per-fix justification.

### Theme C — Spec annotations

#### T12 — Spec footnote: HYBRID gate algorithm in §3

**Files:**
- Modify: `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` (§3
  Vault, autonomy subsection).

**Goal:** Plan 16 T37 brainstorm locked the HYBRID gate semantics
(member-fields + category requires-flag for CONCEPTS/DRAFT only); T47
footnote covers the schema reshape but not the algorithm. Add an
explicit algorithm description so future implementers don't re-derive.

**What to do:** ~10-line spec footnote describing:
- Member-field gates (`new_files`, `edits`, `index_entries`) require the
  same-named flag in `config.autonomous[domain]` to be True.
- `CONCEPTS` / `DRAFT` patches additionally require the same-named
  category flag.
- `INGEST` / `ENTITIES` / `INDEX_REWRITES` patches: NO category-level
  requirement (member-field flags govern).
- Multi-member ANY-False ⇒ stage the WHOLE patch.

**Per-task review:** combined spec + code-quality.

#### T13 — Multi-domain chat per-call enforcement spec annotation

**Files:**
- Modify: `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` (§10
  Safety rails, budget caps subsection — extends the Plan 16 T47
  footnote).

**Goal:** Per locked D4 (above) — annotate the multi-domain chat NO-
ENFORCEMENT policy.

**What to do:** ~5-line addendum: when `len(config.domains) > 1`, the
per-domain budget guard passes `domain=None` and no-ops. Document
WHY (no canonical per-call domain in multi-domain mode) and the
re-litigation criterion (a future spec amendment).

**Per-task review:** combined spec + code-quality.

#### T14 — Spec annotation: callers must use `resolve_config`

**Files:**
- Modify: `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` (§10
  or wherever the config-loading section lives).

**Goal:** Plan 16 T34.5 migrated brain_api / brain_cli / brain_mcp to
`resolve_config`. The spec should make this contract explicit so
future callers don't re-introduce direct `load_config` calls (which
bypass cache invalidation participation).

**What to do:** ~5-line spec annotation: `resolve_config` is the
canonical entry point; `load_config` is the underlying primitive that
`resolve_config` wraps for cache misses. New code paths MUST call
`resolve_config` to participate in T35's cross-process invalidation.

**Per-task review:** combined spec + code-quality.

#### T15 — `_lifespan` accumulated comment-debt refactor (brain_api)

**Files:**
- Modify: `packages/brain_api/src/brain_api/app.py` (`_lifespan`
  function).

**Goal:** T39.5 added significant inline comments to `_lifespan`
describing the AnthropicProvider construction logic. The function is
now ~80 lines with prose commentary. Consolidate to a single docstring
+ minimal inline pointers; extract if a clean helper boundary emerges.

**What to do:**
1. **Read** the full function. Identify which comments are load-bearing
   (explain non-obvious behavior) vs. tutorial (explain obvious flow).
2. **Refactor.** Lift load-bearing comments to a structured docstring
   with named sections; remove tutorial-style narration.
3. **Verify.** All existing `_lifespan` tests still pass.

**Per-task review:** combined spec + code-quality. Diff size matters
here — over-aggressive trimming risks losing context.

### Theme D — Misc tidy-ups

#### T16 — `brain_recent` backend type contract drift

**Files:**
- Modify: `packages/brain_core/src/brain_core/tools/recent.py:54`
  (emit `items` instead of `notes`) OR
- Modify: `apps/brain_web/src/lib/api/tools.ts` (remove the FE adapter).

**Goal:** Plan 14 T11 added a frontend adapter for `data.notes` vs
`data.items`; backend at `recent.py:54` still emits `notes`. Pick a
side and align.

**What to do:**
1. **Decide.** Recommended: flip backend to `items` (matches the
   T11-introduced TypeScript naming convention; `items` is more generic
   for what is now a multi-source list).
2. **Update tests.** brain_core pytest + brain_api pytest.
3. **Remove FE adapter.** `apps/brain_web/src/lib/api/tools.ts`'s
   adapter shim becomes dead code.

**Per-task review:** combined spec + code-quality.

#### T17 — `repair_config_apply` atomicity audit

**Files:**
- Audit: `packages/brain_core/src/brain_core/tools/repair_config_apply.py`.
- Modify (if warranted): same file + tests.

**Goal:** T33 reviewer noted that `repair_config_apply` mutates
`ctx.config` in-memory before calling `save_config`. If `save_config`
raises, the in-memory copy is wrong until the user re-runs. T34's
version-check correctly handles eventual reload, but the contract
during failure is "stale in-memory until next read."

**What to do:**
1. **Audit.** Confirm the failure-mode behavior. Read the existing
   tests; verify they cover the post-failure state.
2. **Decide.** Recommended: wrap the mutation in
   `persist_config_or_revert` (Plan 11 T4 helper) so the in-memory
   state rolls back atomically on `save_config` failure.
3. **Pin tests.** Add a regression test that simulates `save_config`
   failure mid-mutation; assert `ctx.config` is unchanged post-failure.

**Per-task review:** combined spec + code-quality.

#### T18 — T33 nits bundled

**Files:**
- Modify: `apps/brain_web/src/components/dialogs/repair-config-dialog.tsx`.

**Goal:** Bundle the three T33 review nits:
- (a) Tab order spec comment (`:52`) says Re-run→steps→Re-apply→Cancel
  but DOM order is Cancel→Re-run→steps→Re-apply. Adjudicate (designer
  input may be needed).
- (b) Hex fallbacks in `ICON_BY_STATUS` JS object violate spirit of
  T13 stylelint rule (even though stylelint doesn't catch JS-object
  values). Replace with `var(--ok)` / `var(--warn)` / `var(--danger)`
  references.
- (c) No `AbortController` / `mountedRef` for `handleRun` / `handleApply`
  async callbacks. Add a `mountedRef` guard.

**What to do:** three small fixes in one file. Each ~5-15 LOC. Test
extensions for the AbortController behavior.

**Per-task review:** combined spec + code-quality. Tab order fix needs
brain-ui-designer input — route back if disagreement on canonical
order.

### Closure

#### T19 — Closure: demo + lessons + todo + tag

**Files:**
- Create: `scripts/demo-plan-17.py`.
- Modify: `tasks/lessons.md` (Plan 17 closure section).
- Modify: `tasks/todo.md` (row 17 → ✅ Complete; remove Plan 17
  candidate scope tail block; add Plan 18 candidate scope — RESIDUALS
  ONLY again, expected near-empty).

**Goal:** Land Plan 17 closure: demo + lessons + todo update.

**What to do:**
1. **demo-plan-17.py.** Per D7, the demo asserts each carry-forward is
   CLOSED. Final line: `PLAN 17 DEMO OK`.
2. **Lessons.** Plan 17 closure section: lessons surfaced during the
   18 task run.
3. **todo.md update.** Row 17 marked complete; tail block renamed Plan
   18 candidate scope (likely 1-3 items max — Plan 17 should clear
   most residuals).
4. **No new spec footnotes.** T12-T15 already added the spec
   annotations inline.

**Per-task review:** combined spec + code-quality. Demo gate count is
NOT pinned at a number per D7.

## Owning subagents

- **brain-core-engineer** — T1 (brain_api integration test),
  T2 (lifespan hot-reload), T6 (drift detection — Python side),
  T7 (doc cleanup), T9 (audit), T10 (test_mcp_session migration),
  T11 (brain_api mypy debt), T16 (backend type contract), T17
  (atomicity), T19 (demo + lessons).
- **brain-frontend-engineer** — T3, T4, T5 (zustand consumer migration),
  T6 (TypeScript drift detection — TS side), T18 (T33 nits).
- **brain-mcp-engineer** — T8 (callback extraction).
- **brain-ui-designer** — T18(a) microcopy/UX adjudication for the tab
  order question if disagreement surfaces.
- (No new tasks for brain-prompt-engineer or brain-installer-engineer
  in Plan 17.)

## Workflow rules

Same as Plan 16:
- Sequential per-task dispatch via `superpowers:subagent-driven-development`.
- Combined spec + code-quality review per task.
- Implementer routes back to plan author on any unrecognized rule edge
  case (e.g., D4 multi-domain enforcement re-litigation, T18(a) tab
  order designer disagreement).
- Pause every ~5 tasks for user check-in.
- No push without explicit user authorization at milestones.

## File inventory (summary)

```
docs/superpowers/specs/
└── 2026-04-13-cj-llm-kb-design.md      # MODIFY: §3 (T12 HYBRID gate algorithm); §10 (T13 multi-domain enforcement; T14 resolve_config contract)

packages/brain_core/
├── src/brain_core/tools/
│   ├── config_set.py                   # MODIFY: docstring (T7)
│   ├── ingest.py                       # MODIFY: comment (T7)
│   ├── recent.py                       # MODIFY: items vs notes (T16)
│   └── repair_config_apply.py          # MODIFY: persist_config_or_revert wrap (T17)
└── tests/
    ├── ...                             # extends per-task

packages/brain_api/
├── src/brain_api/
│   ├── app.py                          # MODIFY: _lifespan refactor (T15) + ctx.config update (T2)
│   ├── auth.py                         # MODIFY: no-any-return (T11)
│   └── schema.py                       # MODIFY: unused-ignore (T11)
└── tests/
    ├── test_anthropic_e2e.py           # NEW (T1)
    └── test_lifespan_hot_reload.py     # NEW or extend (T2)

packages/brain_mcp/
├── src/brain_mcp/__main__.py           # MODIFY: lift _on_config_change (T8)
└── tests/test_ctx_cache_reset.py       # MODIFY: import lifted callback (T8)

apps/brain_web/
├── src/components/settings/
│   ├── panel-budget.tsx                # MODIFY: useBudget (T3)
│   ├── panel-domains-row.tsx           # MODIFY: useDomainOverrides (T4)
│   └── domain-override-form.tsx        # MODIFY: useDomainOverrides (T5)
├── src/components/dialogs/
│   └── repair-config-dialog.tsx        # MODIFY: T33 nits (T18)
├── src/lib/api/tools.ts                # MODIFY: drop FE adapter (T16)
└── tests/
    ├── unit/                           # extends per-task
    └── fixtures/autonomy-categories.json  # NEW (T6)

scripts/
└── demo-plan-17.py                     # NEW (T19)

tasks/
├── lessons.md                          # MODIFY: Plan 17 closure section (T19)
├── todo.md                             # MODIFY: row 17 + Plan 18 candidate scope (T19)
└── plans/17-residuals-and-spec-annotations.md  # SELF (this doc)

.github/workflows/
└── ci.yml                              # MODIFY: optional integration step (T1); brain_api mypy step (T11)
```

## T9 audit findings

**Task:** confirm no consumer of
`brain_core.tools.apply_patch._resolve_config(ctx)` mutates the
returned `Config`. Post-Plan 16 T39.5 the helper returns
`ctx.config` directly (live shared reference) on the production
path, so any mutation would leak across consumers.

**Call sites grepped** (rg `_resolve_config(` across `packages/`):

- `packages/brain_core/src/brain_core/tools/apply_patch.py:97` —
  production consumer inside `handle(...)`. The returned reference
  is bound to a local `config` and passed positionally as
  `should_auto_apply(envelope.patchset, config, domain=domain)`. No
  attribute assignment, no `setattr`, no `object.__setattr__`, no
  method call on the local. Verdict: **read-only, no mutation**.
- `packages/brain_core/src/brain_core/tools/apply_patch.py:125` —
  the function definition itself (matched by the same grep). Not a
  consumer. Verdict: **n/a**.
- `packages/brain_core/tests/tools/test_apply_patch.py:230` —
  `test_resolve_config_falls_back_to_defaults_when_ctx_config_none`.
  Asserts `cfg.vault_path == vault` and `cfg.autonomous == {}`.
  Verdict: **read-only, no mutation**.
- `packages/brain_core/tests/tools/test_apply_patch.py:249` —
  `test_resolve_config_returns_ctx_config_by_identity`. Asserts
  `cfg_out is cfg_in`. Verdict: **read-only, no mutation**.

**Transitive read of `should_auto_apply`** (the one function the
production local is passed to,
`packages/brain_core/src/brain_core/autonomy.py:70`): only reads
`patchset.category`, `config.autonomous.get(domain)`, attribute
accesses on `flags`, and `getattr(flags, category_flag)`. No
mutation, no method call that could mutate. Verdict: **read-only,
no mutation**.

**Action taken:** added a `Read-only contract` block to the
`_resolve_config` docstring in `apply_patch.py` declaring that
callers MUST NOT mutate the returned reference (it IS
`ctx.config` on the production path). No code-logic changes.

## Plan 18 candidate scope (forwarded from Plan 17)

To be filled in at T19 closure. Expected NEAR-EMPTY: Plan 17 sweeps
every Plan 16 residual; what remains for Plan 18 is anything that
emerges DURING Plan 17 execution that's too narrow to land inline.

## Review (pending)

To be filled in on closure following Plan 10..16 format:
- **Tag:** `plan-17-residuals-and-spec-annotations` (cut on green
  demo).
- **Closes:** every item in the Plan 17 candidate scope tail block of
  `tasks/todo.md` (preserved here for traceability).
- **Bumps:** spec gains 3 footnotes (T12, T13, T14); ci.yml gains 2
  steps (T1 integration, T11 brain_api mypy); 3 frontend components
  migrate to zustand stores; 1 brain_mcp callback lifts to module level;
  brain_api `_lifespan` refactored. No schema changes.
- **Verification:** `scripts/demo-plan-17.py` → `PLAN 17 DEMO OK`;
  pytest + vitest + Playwright + Mac+Windows CI green.
- **Backlog forward:** Plan 18 candidate scope per Task 19 step 4.

---

**End of Plan 17.**
