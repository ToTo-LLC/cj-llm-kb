# Plan 16 — Comprehensive carry-forward closure

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Plan 16 D32 locks **sequential per-task dispatch with two-stage review** (Plan 11 + 12 + 13 + 14 + 15 discipline) — do NOT parallelize even when the dependency graph allows it. Plan 16 has the largest task count of any plan in this project (30 tasks); the discipline cost is justified because (a) most tasks are < 50 LOC polish that flush quickly through combined review, and (b) the two SCAFFOLD tasks for bigger architectural moves (per-domain budget caps, per-domain rate limits) need careful spec-correctness review even when the diff is small.

**Goal:** Close the entire Plan 15 candidate-scope carry-forward in one cohesive plan. ~50 items across 10 themes accumulated from Plan 12, 13, 14, and 15 reviews — landed here as 30 narrowly-scoped tasks. Two tracks: (a) **carry-forward closure** (themes 1–9; actual deferrals + reviews from prior plans, mostly < 50 LOC each); (b) **architectural foundations** (theme 10; bigger moves landed as SCAFFOLDS — the data model / API contract / lint plumbing — with full polish deferred to Plan 17+ once the foundations have a chance to settle and reveal the real ergonomics).

The 10 themes (numbered to match `tasks/todo.md` Plan 16 candidate-scope):

1. **Production correctness (top priority)** — `inbox-store.loadRecent` overwrite race. The only item where a real user can see a real bug today; lands at Task 1 to make plan-author intent visible.

2. **brain_api hardening** — `_spa_fallback Response | None` mypy `@overload` discriminating on `raise_on_miss`. Plan 14 Task 5 review M2 flagged the pre-existing mypy hole; Plan 15 deferred. Task 2.

3. **Plan 13 architectural follow-throughs (still open)** — 8 items from Plan 13 Tasks 2 + 3 reviews. Orphan `listDomains` consumer migration (Task 3); `removeDomainOptimistic` action + `useDomainsStore.error` inline banner (Task 4); `domainsLoaded` → `loaded` naming + drop/wire cross-domain-gate-store error field (Task 5); BroadcastChannel cross-tab pubsub (Task 6); `setAcknowledgedOptimistic` early-return alignment (Task 7); `panel-domains.tsx` 3-file split (Task 8).

4. **Plan 14 a11y deferrals (still open)** — 5 items. Repair-config dialog UI scaffold (Task 9); autonomy modal UI scaffold (Task 10); a11y-populated additions for Browse file-preview overlay + WikilinkHover tooltip + per-message Fork dialog (Task 11). Per D6, Tasks 9 + 10 are SCAFFOLDS sufficient to satisfy the a11y-populated.spec.ts gate; full UI/UX polish for repair-config goes through Task 28.

5. **CSS structural cleanup** — 4 items. `--tt-cyan-hover` token + `--brand-ember` foreground audit (Task 12); stylelint hardcoded-hex rule + `.prose`/`.msg-body`/`.turn-body` selector convention doc (Task 13).

6. **CI follow-throughs** — 7 items from Plan 14 Tasks 7 + 8 reviews. Workflow caching for uv + pnpm + Playwright browsers (Task 14); composite-action DRY for chflags + PYTHONPATH + npx playwright test (Task 15); `gh workflow run --validate` pre-commit + `pnpm install --frozen-lockfile --filter brain_web...` consistency (Task 16); Defender SmartScreen pre-step under feature-flag + PowerShell line-ending lesson capture (Task 17); CI duration observability per-job summary (Task 18).

7. **Test-quality follow-throughs** — 5 items. `waitForToolResponse` helper + `waitForTimeout` removal across `a11y-populated.spec.ts` (Task 19); `test.afterEach` cleanup contract + `text-[var(--bg)]` → `text-[var(--accent-foreground)]` in `patch-card.tsx:117` (Task 20). The 5th item — `seedBrainMd` / `seedScope` helper extraction — stays deferred per the rule-of-three threshold (current count = 3; threshold = 5); captured in NOT-DOING.

8. **Plan 15 review residuals** — 7 items. SVG mockup copy update (Task 21); 3 pre-existing TS errors in `cross-domain-modal.spec.ts` (Task 22); act() warnings sweep in `chat-screen.test.tsx` (Task 23); `test_config_get.py` `_mk_ctx` Path A alignment (Task 24); toast period normalization + Plan 07 forward-looking deferrals in `config_set.py` + `schema.py` + positive unit test for `PrivacyRailedGlossaryTooltip` (Task 25 — three trivially-small items grouped to keep task count down).

9. **Cleanup carried forward** — 1 lesson-only item (plan-text "topbar scope chip" inaccuracy drift watch). Captured in NOT-DOING with rationale.

10. **Bigger architectural moves** — 12 items. Per-domain budget caps SCAFFOLD (Task 26); per-domain rate limits SCAFFOLD (Task 27); repair-config UI screen + cross-process hot-reload SCAFFOLD (Task 28); `validate_assignment=True` on Config — perf-measure + locked decision (Task 29); per-domain autonomy categories brainstorm + lock (Task 30 — schema redesign needed; Plan 16 brainstorms only); "Set as default" topbar + generic zustand promotion + `pendingSendRef`-as-local audit (Task 31 — three trivially-small items grouped); generic "tool reads ctx.config" lint rule SCAFFOLD (Task 32). Two items DEFER outright: per-thread cross-domain confirmation (violates spec §4 "one-time"; captured in NOT-DOING) + migration tool for old `config.json` files (Pydantic defaults already handle missing fields; captured in NOT-DOING).

11. **(closure)** — Task 33: 33-gate demo + lessons + todo.md update + spec footnote per D31.

**Architecture.** Two-track narrative as above. Plan 16 is the largest plan in this project (30 tasks vs Plan 15's 11) because the user's directive is explicit: every original Plan 16 candidate-scope item lands as a task. The discipline that makes 30 tasks tractable: D32 locks combined spec-and-code-quality review per task (Plan 15 lesson — `< 50 LOC` tasks flush through combined review), and D33 locks each task to a single ~20-line PR shape so the per-task review surface stays small.

**Tech Stack.** Same gates as Plan 11 + 12 + 13 + 14 + 15 — Python 3.12, pydantic v2, `mypy --strict`, `ruff`, vitest + Playwright. GitHub Actions (Plan 14 Task 7+8 + Plan 15 Task 3). New tooling: `stylelint` (Task 13 — first plan to land it; npm workspace dep). No other new third-party deps.

**Demo gate.** `scripts/demo-plan-16.py` (chflags-prefixed per lesson 341) walks 33 gates — one assertion per substantive item plus regression + sentinel:

1. **inbox-store loadRecent merge** (T1): unit test asserts loadRecent preserves optimistic rows whose id is not in server response.
2. **_spa_fallback @overload** (T2): mypy strict on `static_ui.py` reports 0 errors; `Response | None` overloaded by `raise_on_miss`.
3. **bulk-screen + file-to-wiki use useDomains** (T3): grep both files; assert no direct `listDomains()` import; assert `useDomains()` import.
4. **removeDomainOptimistic + error banner** (T4): unit test asserts `panel-domains` delete handler calls `removeDomainOptimistic` BEFORE awaiting the API; render with `useDomainsStore.error` set; assert inline banner appears.
5. **Naming alignment + error field** (T5): grep `domains-store.ts` for `domainsLoaded`; assert renamed to `loaded`; cross-domain-gate-store `error` field is wired (or dropped per locked decision).
6. **BroadcastChannel cross-tab pubsub** (T6): jsdom test mounts two `useDomainsStore` consumers in separate "tabs" (BroadcastChannel mock); mutate from one; assert other re-renders within 100ms.
7. **setAcknowledgedOptimistic early-return** (T7): grep `cross-domain-gate-store.ts`; assert `setAcknowledgedOptimistic` body matches `setActiveDomainOptimistic`'s early-return shape.
8. **panel-domains 3-file split** (T8): assert file existence: `panel-domains.tsx` (orchestrator) + `panel-domains-row.tsx` + `panel-domains-add.tsx` + `panel-domains-active.tsx`.
9. **Repair-config dialog scaffold** (T9): grep `repair_config|repairConfig` in `apps/brain_web/src/`; expect non-empty result.
10. **Autonomy modal scaffold** (T10): grep `autonomy-modal|AutonomyModal` in `apps/brain_web/src/`; expect non-empty result.
11. **a11y-populated additions** (T11): Playwright runs the 3 new cases (file-preview overlay, WikilinkHover tooltip, per-message Fork dialog); 0 violations each.
12. **--tt-cyan-hover token + --brand-ember audit** (T12): grep `tokens.css` for `--tt-cyan-hover`; assert defined for both light + dark themes; assert no `var(--brand-ember)` foreground site fails 4.5:1 contrast in either theme.
13. **stylelint + selector doc** (T13): `npx stylelint apps/brain_web/src/**/*.css` exits 0; grep `brand-skin.css` for `.prose`/`.msg-body`/`.turn-body` convention comment block.
14. **Workflow caching** (T14): grep `.github/workflows/*.yml` for `actions/cache@v4`; assert uv + pnpm + Playwright browser caches present.
15. **Composite action DRY** (T15): assert `.github/actions/setup-brain-test-env/action.yml` exists; assert it's invoked by both Mac and Windows steps.
16. **Workflow validation + pnpm filter** (T16): `gh workflow run --validate` passes; `pnpm install` step uses `--filter brain_web...`.
17. **Defender SmartScreen + PowerShell lesson** (T17): grep `playwright.yml` for `Set-MpPreference -DisableRealtimeMonitoring` (feature-flag-gated); assert `tasks/lessons.md` Plan 16 section contains the PowerShell line-ending entry.
18. **CI duration observability** (T18): grep `playwright.yml` for `$GITHUB_STEP_SUMMARY` writeback step; assert per-job wall-clock + per-step breakdown.
19. **waitForToolResponse helper + waitForTimeout removal** (T19): grep `a11y-populated.spec.ts` for `waitForTimeout`; expect 0 hits; grep for `waitForToolResponse`; expect helper used.
20. **test.afterEach + patch-card token fix** (T20): grep `a11y-populated.spec.ts` for `test.afterEach`; expect non-zero hits across state-mutating cases; grep `patch-card.tsx` for `text-[var(--bg)]`; expect 0 hits.
21. **SVG mockup copy update** (T21): grep `state-1-initial.svg` + `state-2-settings-after-toggle.svg` for "private" copy; expect 0 hits or only "Privacy-railed" form.
22. **cross-domain-modal.spec.ts TS clean** (T22): `tsc --noEmit` on `apps/brain_web/tests/e2e/cross-domain-modal.spec.ts` reports 0 errors.
23. **chat-screen.test.tsx act() clean** (T23): vitest run captures stderr; assert no `act()` warnings emitted.
24. **test_config_get._mk_ctx required config** (T24): grep `test_config_get.py` for `_mk_ctx(`; assert all call sites pass `config=` kwarg explicitly (no `config=None` default).
25. **Toast period + Plan 07 deferrals + tooltip unit test** (T25): grep `panel-domains.tsx` toast strings; assert period-normalized; grep `config_set.py` + `schema.py` for "Plan 07 Task 5"; expect 0 hits; vitest `PrivacyRailedGlossaryTooltip` positive unit test passes.
26. **Per-domain budget caps SCAFFOLD** (T26): assert `Config.budget.per_domain: dict[str, BudgetOverride]` field exists in schema; assert reading + writing + serializing round-trips; full enforcement deferred to Plan 17+.
27. **Per-domain rate limits SCAFFOLD** (T27): assert `Config.providers[provider].rate_limit_per_domain: dict[str, RateLimitOverride]` schema field; full provider-client enforcement deferred to Plan 17+.
28. **Repair-config UI + hot-reload SCAFFOLD** (T28): assert `repair-config-dialog.tsx` exists with at least the auto-fallback-chain summary surface; assert `Config.config_version: int` field + `_resolve_config` reads version on every refresh (lays the groundwork for cross-process invalidation; full pubsub deferred).
29. **validate_assignment=True decision** (T29): per locked decision (D29 — see below): either `Config.model_config = ConfigDict(validate_assignment=True)` is set OR `tasks/lessons.md` documents the perf-measure outcome and decision to defer. KNOWN-LIMITATION pin test (`test_invalid_value_currently_persists_without_validation`) either passes (still deferred) or is updated to the new shape.
30. **Per-domain autonomy categories brainstorm-doc** (T30): assert `tasks/plans/16-comprehensive-carry-forward.md` Task 30 contains a "Findings" subsection with the locked decision shape (no implementation expected in Plan 16).
31. **Trio cleanup** (T31): "Set as default" topbar button scaffold present; `useBudget` / `useDomainOverrides` zustand-promotion scaffold present (or decision recorded); `pendingSendRef`-as-local audit doc filed.
32. **Generic ctx.config lint rule SCAFFOLD** (T32): assert ruff custom rule OR per-package mypy plugin entry checks for `ctx.config` reads outside the allowed entry-point list; runs as a CI step.
33. **`PLAN 16 DEMO OK`** sentinel.

Prints `PLAN 16 DEMO OK` on exit 0; non-zero on any gate failure.

**Owning subagents** (D32 distribution).
- `brain-frontend-engineer` — Tasks 1, 3, 4, 5, 6, 7, 8, 11 (frontend half), 23, 24 (frontend half — chat-screen test), 25 (tooltip unit test half), 27 (frontend scaffold half), 31 (frontend half)
- `brain-mcp-engineer` (role-overloaded brain-api-engineer per Plan 05 precedent) — Task 2 (`_spa_fallback` overload)
- `brain-ui-designer` — Tasks 9 + 10 (microcopy half — dialog copy + tooltip text), 21 (SVG mockup copy update), 28 (microcopy half for repair-config UI)
- `brain-test-engineer` — Tasks 11 (test half — a11y-populated additions), 17 (PowerShell lesson capture half), 19, 20, 22, 23 (warning sweep half), 33 (closure demo + lessons)
- `brain-installer-engineer` — Tasks 14, 15, 16, 17 (CI workflow half), 18
- `brain-core-engineer` — Tasks 24 (test_config_get _mk_ctx alignment), 25 (Plan 07 deferral docstring half), 26, 27 (backend scaffold half), 28 (Config.config_version half), 29, 30, 32
- `brain-frontend-engineer` + `brain-test-engineer` — Task 13 (stylelint + selector convention doc shared)

**Pre-flight** (main loop, before dispatching Task 1):
- Confirm Plan 15 closed clean: `git tag --list | grep plan-15-ci-and-polish` exists.
- Confirm no uncommitted changes on `main`. (At plan-authoring time, `git status` showed two staged plan-15-residual modifications under `packages/brain_cli/`; main loop must clean those before Task 1 dispatch.)
- Confirm `tasks/lessons.md` contains the Plan 15 closure section (6 lessons captured per Plan 15 Task 11 step 3).
- Confirm `CI` workflow is now green up to mypy debt — Plan 15 Task 1 cleared the 76 ruff violations; the residual gate failures should be limited to the pre-existing mypy `Response | None` hole that Task 2 closes.
- Confirm production `loadRecent` race is the genuine highest-priority item (ahead of architectural follow-throughs and bigger moves) — this ordering is load-bearing for plan-author intent: Plan 16 starts with the only user-visible bug.
- **Plan 16 inverts the default plan-sizing target.** Plan 11–15 averaged 9–11 tasks; Plan 16 lands 30. The discipline that makes 30 tractable: combined spec-and-code-quality review per task (Plan 15 lesson — `< 50 LOC` flushes through combined review fast), each task locked to a ~20-line PR shape, and D33 locks the rule that any task exceeding ~20 LOC at implementation time MUST split rather than expand.
- Note the recurring uv `UF_HIDDEN .pth` workaround (lesson 341 + Plan 12+13+14+15 refinements): chflags + PYTHONPATH same-line python invocation; do NOT use `uv run` (re-syncs and re-hides). Plan 15 Task 4 made this rule first-class in `brain start`; future supervisors / launchers / orchestration tools should follow.

---

## What Plan 16 explicitly does NOT do

These items appear in Plan 16 candidate scope but are deferred outright with rationale:

- **`seedBrainMd` / `seedScope` helper extraction.** Rule-of-three threshold not yet met (current callers: 3; threshold: 5). Plan 17+ if/when a 5th caller appears. Captured in `tasks/todo.md` Plan 17 candidate scope.

- **Plan-text "topbar scope chip" inaccuracy drift watch.** Lesson-only item (no code change). Already captured in `tasks/lessons.md` Plan 12 closure section; Plan 16 adds nothing actionable here. The drift watch IS the deferral.

- **Per-thread cross-domain confirmation.** Plan 12 D8 chose per-vault `Config` field; per-thread violates spec §4 "one-time". Re-litigating this requires a spec amendment first. Plan 16 D-NOT (rationale): the architectural decision was made deliberately, not by accident; re-opening it should go through a spec brainstorm not a polish plan.

- **Migration tool for old `config.json` files.** Pydantic defaults handle missing fields on read; `save_config` round-trips with the new shape on next mutation. The migration tool is a Plan 17+ candidate IF a real schema-breaking change ships AND existing user vaults exist in the wild — neither condition holds today. Captured as deliberate deferral.

- **Full polish of bigger architectural moves landed as SCAFFOLDS in Plan 16** — per-domain budget enforcement (Task 26 lands the schema only); per-domain rate-limit enforcement (Task 27 lands the schema only); repair-config UI full surface (Task 28 lands the dialog scaffold + Config.config_version); cross-process hot-reload pubsub (Task 28 lands version-bumped invalidation only — no pubsub yet); per-domain autonomy categories (Task 30 brainstorms + locks shape, no implementation). These are deliberately deferred to Plan 17+ because (a) the data model needs to settle on disk for at least one user-iteration before the UI surfaces; (b) plan-author bias toward "ship the data shape, defer the polish" matches Plan 11 (which landed `Config.privacy_railed: list[str]` as the first cut, deferred the modal jargon to Plan 15) and Plan 13 (which landed `cross-domain-gate-store` as the cross-instance fix, deferred the `error` field disposition to Plan 16 itself).

- **Spec amendment.** Plan 16 D31 chooses to land **one spec footnote** for Task 26 + 27 (per-domain budget + rate-limit caps schema) and **no other spec text changes**. The other items in Plan 16 are internal correctness / test-debt / polish / scaffold work that doesn't change user-facing surface area. Consistent with Plan 14 D9 (one spec footnote for CI gate), inconsistent with Plan 15 D11 (no spec text). The schema field IS user-facing surface — it's a future contract — so a footnote is warranted.

If any of these come up during implementation, file a TODO in Plan 17 candidate scope and keep moving.

---

## Decisions (locked 2026-05-06)

User to sign off on these recommendations on the dispatch round. Implementers MUST treat these as load-bearing once locked — any deviation requires a new round of plan-author sign-off before changing scope.

### Group I — Scope cut

| # | Decision | Locked | Why |
|---|---|---|---|
| Scope | Plan 16 covers all ~50 items from Plan 16 candidate scope as 30 tasks across 10 themes — production correctness (T1), brain_api hardening (T2), Plan 13 architectural follow-throughs (T3-T8), Plan 14 a11y deferrals (T9-T11), CSS structural cleanup (T12-T13), CI follow-throughs (T14-T18), test-quality (T19-T20), Plan 15 review residuals (T21-T25), bigger architectural moves as SCAFFOLDS (T26-T32), closure (T33). DEFERS: `seedBrainMd`/`seedScope` (rule-of-three not met), per-thread cross-domain (spec §4 violation), migration tool (no use case yet), full polish on bigger architectural moves (Plan 17+). | pending | "All carry-forward in one plan" cut. The user's directive: every original Plan 16 candidate-scope item is IN Plan 16. The trade-off is plan size (30 tasks); the discipline that makes it tractable is combined review per task + ~20-LOC PR shape per task. |

### Group II — Production correctness (T1)

| # | Decision | Locked | Why |
|---|---|---|---|
| D1 | `inbox-store.loadRecent` race fix shape: **id-keyed merge that preserves optimistic rows whose id is not in the server response.** Build a server-response-id Set, filter the current store's optimistic rows for ones not in the Set, prepend them to the merged result. Sequence-id check was rejected as more state without a clear win — id is already unique per source ingestion. | pending | "Sequence-id check" was rejected as adding a counter slot that has to stay synchronized across clients/tabs. "Replace store wholesale" is the current bug. The id-merge is surgical (~10 LOC) and matches React/zustand conventions for optimistic UI. Plan 14 Task 6's `waitForResponse` test arm becomes deletable once production is fixed; Task 1 deletes it as part of the same commit (production + test arm coupled). |

### Group III — brain_api hardening (T2)

| # | Decision | Locked | Why |
|---|---|---|---|
| D2 | `_spa_fallback Response | None` mypy fix: `@overload` discriminating on `raise_on_miss: Literal[True]` → `Response`, `raise_on_miss: Literal[False]` → `Response | None`. Single `@overload`-decorated stub pair; runtime body unchanged. | pending | "Skip — mypy ignore" was rejected as deferring the type-safety contract. "Refactor to two functions" was rejected as duplicating the body. `@overload` is the canonical pattern for `bool` discriminator → return type. ~10 LOC; the runtime body stays identical. |

### Group IV — Plan 13 architectural follow-throughs (T3-T8)

| # | Decision | Locked | Why |
|---|---|---|---|
| D3 | Migrate `bulk-screen.tsx` + `file-to-wiki-dialog.tsx` to `useDomains()`: drop direct `listDomains` API import; replace local React state hydrated from `listDomains()` with the `useDomains()` selector. Same shape as Plan 13 Task 2 did for `panel-domains.tsx`. Single PR per file (T3 covers both). | pending | "One file per task" was rejected as task-count bloat for two ~20 LOC migrations. "Skip — Plan 17+" was rejected because Plan 13 Task 2 review M3 said the threshold was met. Mirror migration is mechanical. |
| D4 | `removeDomainOptimistic(slug)` action lands in `domains-store.ts`; `panel-domains.tsx` delete handler calls it BEFORE awaiting the API; `useDomainsStore.error` is rendered as inline banner above the domains list. Two items, one PR (paired naturally — both are the delete-handler UX surface). | pending | "Skip optimistic action" was rejected — Plan 13 Task 2 review I1 explicitly recommended it. "Skip error banner" was rejected — same review recommended surfacing the error state that's already in the store but unrendered. Pairing them in one task is natural because both touch the same delete-handler. |
| D5 | `domainsLoaded` → `loaded` rename (matches `cross-domain-gate-store`'s `loaded` field naming); `cross-domain-gate-store.error` field is **wired** (rendered as inline banner in `panel-domains.tsx` settings tab too). | pending | "Drop the field" was the alternative — but Plan 13 Task 3 review I2 said the field exists for parity with `domains-store.error`; dropping it would re-introduce the asymmetry. Wiring it costs ~5 LOC and gives both stores consistent surface. |
| D6 | BroadcastChannel cross-tab pubsub: lands as a thin module-private layer in BOTH `domains-store.ts` AND `cross-domain-gate-store.ts`. On any `set()` that mutates the store, post to the channel; on inbound message, call `_internalSet()` (which doesn't echo). jsdom-mock for tests. | pending | "Skip — wait until user-visible" was rejected because Plan 13 Task 3 review I3 said the optimistic-clobber race is hypothetical-but-known; landing the pubsub now closes the class. "Single store only" was rejected as inconsistent — both stores have the same race shape. |
| D7 | `setAcknowledgedOptimistic` aligned to early-return pattern (matches `setActiveDomainOptimistic` in `domains-store.ts`). Mechanical refactor; ~5 LOC. | pending | "Skip" was rejected — Plan 13 Task 3 review M1 said the pattern divergence is drift-prone. Trivial fix. |
| D8 | `panel-domains.tsx` 3-file split: `panel-domains.tsx` (orchestrator + list), `panel-domains-row.tsx` (per-row editor), `panel-domains-add.tsx` (add-domain affordance), `panel-domains-active.tsx` (active-domain dropdown). The current file is ~580 LOC; the split lands ~200 LOC + 3 × ~120 LOC. Each child file owns its own props + tests. | pending | "2-file split (row + active)" was rejected as leaving the add-domain affordance under-isolated. "4-file split (orchestrator + row + add + active)" matches Plan 13 Task 3 review M3's recommendation exactly. |

### Group V — Plan 14 a11y deferrals (T9-T11)

| # | Decision | Locked | Why |
|---|---|---|---|
| D9 | Repair-config dialog UI **scaffold only** — landed as a minimal dialog with the auto-fallback-chain summary text + a "Run repair" button. Full polish (re-running the loader, surfacing per-step results, re-applying repaired config) deferred to Plan 17+ via Task 28 (which lands the underlying `Config.config_version` infrastructure). | pending | "Skip entirely" was rejected — Plan 14 Task 3 deferral receipt asked for a UI surface so a11y-populated.spec.ts can scan it. "Full polish" was rejected as out-of-scope for a polish plan. Scaffold is the minimum that satisfies the a11y gate AND lays the groundwork for full UI in Plan 17+. |
| D10 | Autonomy modal **scaffold only** — landed as a minimal modal that wraps the existing per-screen Switch toggles into a single dialog with global on/off + per-category overrides. Same SCAFFOLD shape as D9 (a11y-coverable surface; full polish deferred). | pending | Same rationale as D9. Plan 14 Task 3 deferral asked for the surface; the modal is a wrapper around existing logic, not a redesign. |
| D11 | a11y-populated additions (T11): 3 new cases in `a11y-populated.spec.ts` — Browse → file-preview overlay (NEW: build the dedicated overlay, not the inline split-pane); WikilinkHover tooltip (`role="tooltip"` axe scan); per-message Fork dialog (different trigger location from chat-sub-header Fork). | pending | "Skip file-preview overlay (use inline split-pane)" was rejected — the inline split-pane has different accessibility semantics; the dedicated overlay is what spec §8 implies. "Skip per-message Fork" was rejected — different trigger location IS a different a11y surface (focus restoration, escape behavior, etc.). |

### Group VI — CSS structural cleanup (T12-T13)

| # | Decision | Locked | Why |
|---|---|---|---|
| D12 | `--tt-cyan-hover` token lands as a theme-aware token in `tokens.css` (light = darker shade of `--tt-cyan`, dark = brighter shade of `--tt-cyan`); `.prose a:hover` routes through it. Audit other `var(--brand-ember)` foreground sites: list at least 4 (link in non-prose contexts, button accents, icon foregrounds, badges); fix any that fail 4.5:1 in either theme by routing through the theme-aware token. | pending | "Hardcoded hex hover" was rejected — Plan 14 lesson C3 closed the parallel case for the base `.prose a` color. "Skip the audit" was rejected — Plan 14 Task 5 review explicitly asked for it. |
| D13 | stylelint `no-hardcoded-hex-outside-root` rule lands; CI fails on hardcoded hex outside `:root` blocks. `.prose` / `.msg-body` / `.turn-body` selector convention doc lands as a comment block at the top of `brand-skin.css`: "Use `.prose` for ingested-content prose; `.msg-body` for chat message bodies; `.turn-body` for full chat-turn wrappers". | pending | "Document only, no stylelint" was rejected — the doc decays without enforcement. "stylelint only" was rejected — the rule is hard to read without the doc explaining the selector taxonomy. Together they're enforcement + onboarding. |

### Group VII — CI follow-throughs (T14-T18)

| # | Decision | Locked | Why |
|---|---|---|---|
| D14 | Workflow caching: `actions/cache@v4` for (a) uv venv + cache dir; (b) pnpm store; (c) Playwright browser binaries. Cache keys keyed on lockfile hashes. Conservative scope — caching is enable/disable, not optimization rework. | pending | "Skip" was rejected — Plan 14 Task 7+8 reviews said cold installs every run is the biggest CI duration cost. "Optimize the workflow shape (parallel jobs)" was rejected as out of scope; caching alone is the load-bearing fix. |
| D15 | Composite action DRY: new `.github/actions/setup-brain-test-env/action.yml` encapsulates uv install + pnpm install + chflags + PYTHONPATH preamble. Mac and Windows steps invoke it. Cross-platform via inputs (`shell`, `pythonpath_separator`). | pending | "Inline duplication" was rejected — Plan 14 Task 8 review explicitly noted the duplication. "Custom GitHub Action (separate repo)" was rejected as over-engineering for a project-private composite. |
| D16 | `gh workflow run --validate` lands as a pre-commit hook (`.pre-commit-config.yaml`) that runs against any modified `.github/workflows/*.yml` file. Same shape pre-commit framework already enforces ruff + prettier on this repo. `pnpm install --frozen-lockfile --filter brain_web...` replaces the workspace-wide install in playwright.yml — Mac and Windows both gain ~30s per run from the narrowed scope. | pending | Pairing T16's two items in one PR is natural — both are workflow-shape gates. |
| D17 | Defender SmartScreen pre-step lands under feature-flag (`env: DEFENDER_DISABLE: ${{ vars.DEFENDER_DISABLE || 'false' }}`); only fires when the workflow var is set. PowerShell line-ending discipline lesson lands in `tasks/lessons.md` Plan 16 section (UTF-8-BOM-on-PS5.1 vs UTF-8-no-BOM-on-pwsh). | pending | "Always disable Defender" was rejected as security-sensitive. "Skip the lesson" was rejected — even if the bug hasn't bit yet (current workflows use pwsh), the discipline is worth capturing for future-Claude. |
| D18 | CI duration observability: each job writes a per-step wall-clock + per-step status table to `$GITHUB_STEP_SUMMARY`. The summary is visible in the run UI without drilling into logs. Mac vs Windows comparison is just adjacent rows in the same workflow run summary. | pending | "Custom dashboard" was rejected as over-engineering. "Log-only" was rejected as not-discoverable. The `$GITHUB_STEP_SUMMARY` writeback is a built-in GitHub Actions feature; no third-party dependency. |

### Group VIII — Test-quality follow-throughs (T19-T20)

| # | Decision | Locked | Why |
|---|---|---|---|
| D19 | `waitForToolResponse(page, toolName)` helper lands in `apps/brain_web/tests/e2e/_helpers.ts`; deterministic wait on the first `/tools/<toolName>` response after the call site. All `waitForTimeout(...)` calls in `a11y-populated.spec.ts` (~11) replaced with deterministic helpers — `waitForToolResponse`, `waitForResponse`, `waitForLoadState`, `expect(...).toBeVisible({ timeout })`, etc. depending on what the beat is actually waiting for. | pending | "Convert one at a time across multiple tasks" was rejected as task-count bloat. "Drop the helper, inline" was rejected as repetitive. The helper is the lesson-343 production-shape replacement. |
| D20 | `test.afterEach` cleanup contract: every state-mutating test in `a11y-populated.spec.ts` (patch-card edit-approve at minimum; rename/delete domain if they leak) has an `afterEach` that reverts the mutation. `text-[var(--bg)]` → `text-[var(--accent-foreground)]` in `patch-card.tsx:117` lands in the same task (semantic-correctness fix; trivial). | pending | "Cleanup contract only" was rejected as task-count optimization — the patch-card token fix is a 1-line change that the cleanup-contract task touches anyway (it's in the same dialog). Pairing them is natural. |

### Group IX — Plan 15 review residuals (T21-T25)

| # | Decision | Locked | Why |
|---|---|---|---|
| D21 | SVG mockup copy update: `state-1-initial.svg` + `state-2-settings-after-toggle.svg` updated to use "Privacy-railed" in place of "private" copy. brain-ui-designer owns the SVG edits (text node replacements; preserve layout + design tokens). | pending | "Document only, don't update SVGs" was rejected — the mockups serve as designer reference + onboarding artifact; copy drift between TSX and SVG is a known onboarding pain. |
| D22 | 3 pre-existing TS errors in `tests/e2e/cross-domain-modal.spec.ts` fixed via `@ts-expect-error` with a comment explaining the intentional shape OR by narrowing the type at the call site (whichever fits each error individually). | pending | "Suppress all 3 with `@ts-ignore`" was rejected — `@ts-expect-error` is preferred (it errors when the suppression becomes unnecessary). "Skip — pre-existing" was rejected because Plan 15 Task 7 review explicitly asked for the sweep. |
| D23 | act() warnings sweep in `chat-screen.test.tsx`: each test that triggers async dispatch wraps the dispatch in `await act(async () => { ... })`. Vitest stderr captured + asserted clean. | pending | "Suppress with vitest config" was rejected — suppression hides the underlying bug class (un-awaited React state updates). "Skip" was rejected — Plan 15 Task 7 review noted the noisy log. |
| D24 | `test_config_get._mk_ctx` Path A alignment (matches Plan 15 Task 9 D8 — required `config: Config`, no `= None` default). All call sites updated. Mirrors the Plan 13 Task 1 None-policy strictness. | pending | "Skip — same shape as the others, just a fixture" was rejected because Plan 15 Task 9 review explicitly recommended the alignment for full consistency. The 4th `_mk_ctx` variant is the only outlier post-Plan 15. |
| D25 | Three trivially-small Plan 15 review residuals grouped in one PR: (a) toast lead/msg period normalization in `panel-domains.tsx`'s active-domain toast; (b) Plan 07 Task 5 forward-looking deferrals dropped from `config_set.py:81/90` + `schema.py:101` (mirrors Plan 15 Task 10 docstring cleanup); (c) positive unit test for `PrivacyRailedGlossaryTooltip` (Plan 15 Task 5 review). Each ~5 LOC; one PR. | pending | "Three separate tasks" was rejected as task-count bloat for ~15 LOC total. "Drop one of the three" was rejected — each is named explicitly in Plan 16 candidate scope. Pairing is natural; they're all "tiny clean-up" shape. |

### Group X — Bigger architectural moves (T26-T32)

| # | Decision | Locked | Why |
|---|---|---|---|
| D26 | Per-domain budget caps SCAFFOLD: `Config.budget.per_domain: dict[str, BudgetOverride]` field where `BudgetOverride` extends the existing override model with `monthly_cap_usd: float | None`. Schema only — no enforcement plumbing. Spec footnote in §6 (Cost) noting the field exists, full enforcement deferred. | pending | "Land enforcement too" was rejected — enforcement requires cost-ledger schema migration + per-call lookup; both are Plan 17+ work. "Skip — defer entirely" was rejected because Plan 16 candidate scope explicitly named the SCAFFOLD as Plan 16 work. The schema-first approach mirrors Plan 11 (which landed `Config.privacy_railed: list[str]` as schema first, then layered enforcement in Plan 12+). |
| D27 | Per-domain rate limits SCAFFOLD: `Config.providers[provider].rate_limit_per_domain: dict[str, RateLimitOverride]` field where `RateLimitOverride` is `requests_per_minute: int | None`. Schema only — no provider-client enforcement. Same spec footnote pattern as D26. | pending | Same rationale as D26 — schema-first, defer enforcement to Plan 17+. |
| D28 | Repair-config UI screen + cross-process hot-reload SCAFFOLDS paired in one task: dialog scaffold (per D9 — full surface deferred); `Config.config_version: int` field (incremented on every save_config); `_resolve_config` reads the version and re-loads if version mismatch is detected (single-process invalidation). Cross-process pubsub (e.g., brain_api notifying brain_mcp via on-disk SIGHUP-style file watch) is full Plan 17+ work. | pending | Pairing the two is natural because the repair-config UI's "re-apply" button needs the same `config_version` infrastructure that hot-reload would use. Single source of truth in the schema. |
| D29 | `validate_assignment=True` on Config: perf-measure outcome decides. Implementer measures `Config()` instantiation + assignment-heavy round-trip (e.g., 1000 random field assignments) with and without `validate_assignment=True`. If overhead < 10%, set the flag, update the KNOWN-LIMITATION pin test (`test_invalid_value_currently_persists_without_validation`) to pass with the new shape. If overhead > 10%, document the perf-measure outcome in `tasks/lessons.md` and defer (KNOWN-LIMITATION test stays as-is). | pending | "Just enable it" was rejected — Plan 11 Task 4 added the KNOWN-LIMITATION pin test specifically because the perf impact was untested. "Defer until measured" was rejected as not actionable. The measure-and-decide approach commits to the answer in Plan 16. |
| D30 | Per-domain autonomy categories: brainstorm-only task. Plan 16 produces a "Findings" subsection with the locked schema shape (e.g., `Config.autonomous: dict[str, dict[Literal["new_files","edits","index_entries"], bool]]`); no implementation. Plan 17+ implements the locked shape. | pending | "Implement now" was rejected — Plan 12 D1 chose DELETE for `resolve_autonomous_mode` because the per-domain shape wasn't yet decided. Plan 16 closes the brainstorm; Plan 17+ implements. "Skip the brainstorm" was rejected because the candidate scope explicitly asked for it. |
| D31 | Trio of trivially-small architectural moves grouped in T31: (a) "Set as default" topbar button SCAFFOLD — adds a button to the topbar scope picker that calls the existing `setActiveDomain` API; (b) generic zustand promotion across other hooks SCAFFOLD — start with `useBudget` (lift to `budget-store.ts`); (c) `pendingSendRef`-as-local audit — grep `chat-screen.tsx` + neighboring handlers for the same shape, file an audit doc with findings (no implementation unless an obvious extension hits). Each ~10-20 LOC; one PR. | pending | "Three separate tasks" was rejected as task-count bloat for ~50 LOC total. "Skip the audit (no surface today)" was rejected because Plan 15 Task 7 review explicitly asked for it. |
| D32 | Generic ctx.config lint rule SCAFFOLD: a custom mypy plugin OR a ruff custom rule that flags any `ctx.config` read outside the allowed entry-point list. CI step runs the lint; failures point to the audit. Scaffold is sufficient — full enforcement (e.g., automated rewrites, IDE integration) is Plan 17+. | pending | "Inline manual audit at every commit" was rejected as not-structural. "Full enforcement" was rejected as out-of-scope for a polish plan. The scaffold pins the contract; future tools layer on top. |

### Group XI — Plan shape (T33)

| # | Decision | Locked | Why |
|---|---|---|---|
| D33 | Plan 16 task count: 30 tasks + closure (T33). Mirrors Plan 14 (9 tasks) + Plan 15 (11 tasks) cadence at the polish-heavy upper end multiplied by the carry-forward scope. Each task narrowly scoped (~20 LOC PR shape; tasks exceeding ~20 LOC at implementation time MUST split rather than expand). Combined spec-and-code-quality review per task per Plan 15 lesson. NO `gh workflow run --validate` step lifted into pre-commit until Task 16 lands (otherwise it would block Tasks 1-15 dispatch). | pending | "Fewer tasks (~20)" was rejected — combining items beyond what's done in Group IV-IX would muddy review attribution. "More tasks (~40)" was rejected — pairing the trivially-small items (T20, T25, T31) keeps task count down without losing review granularity. |
| D34 | Demo gate composition: 33 gates. One assertion per substantive item plus regression + sentinel. Mirrors Plan 15's per-item gate shape. | pending | "Collapse to ~15 gates" was rejected — less granular failure signal. "More than 35 gates" was rejected — diminishing returns vs gate-runtime cost. |
| D35 | Sequential per-task dispatch via `superpowers:subagent-driven-development`. Combined spec-and-code-quality review per task (no separate spec-pass + code-pass). NO parallelization. Spec text touched: ONE footnote in §6 (Cost) for Tasks 26+27 (per-domain budget + rate-limit caps SCAFFOLD). All other tasks NO spec text changes. Owners as listed in "Owning subagents" above. | pending | "Two-stage review per task" was rejected — combined review caught all M-class issues in Plan 15's 11 tasks at < 50 LOC scope; Plan 16's 30 tasks are even smaller per-task. "Parallel where dep graph allows" was rejected for review-discipline reasons (Plan 11-15 all caught real bugs at sequential checkpoints). |

The implementer routes any unrecognized rule edge case (D1 alternative race-fix shape, D6 BroadcastChannel polyfill quirks, D26/D27/D28 schema field naming, D29 perf-measure threshold, D30 per-domain autonomy shape) back to the plan author for re-sign-off before changing scope.

---

## File structure produced by this plan

```
packages/brain_core/
├── src/brain_core/
│   ├── config/
│   │   └── schema.py                       # MODIFY: drop Plan 07 Task 5 forward-looking comment at line 101 (D25); add Config.config_version field (D28); add Config.budget.per_domain field (D26); add Config.providers[*].rate_limit_per_domain field (D27); per-domain autonomy SCAFFOLD per D30 findings (Plan 16 brainstorm-only)
│   │   └── loader.py                       # MODIFY: _resolve_config reads config_version, re-loads on mismatch (D28)
│   └── tools/
│       ├── config_set.py                   # MODIFY: drop Plan 07 Task 5 forward-looking comment at lines 81+90 (D25)
│       └── apply_patch.py                  # (no change — Plan 15 Task 10 already cleaned)
└── tests/
    ├── tools/
    │   └── test_config_get.py              # MODIFY: _mk_ctx requires config (D24)
    ├── config/
    │   ├── test_schema_per_domain_budget.py    # NEW: schema-only round-trip pin (D26)
    │   ├── test_schema_per_domain_rate_limit.py # NEW: schema-only round-trip pin (D27)
    │   ├── test_config_version_field.py    # NEW: version-bump + reload pin (D28)
    │   └── test_validate_assignment_perf.py # NEW: perf-measure for D29
    └── linting/
        └── test_ctx_config_lint_rule.py    # NEW: scaffold contract for D32

packages/brain_api/
└── src/brain_api/
    └── static_ui.py                        # MODIFY: _spa_fallback @overload on raise_on_miss (D2)

apps/brain_web/
├── src/components/
│   ├── settings/
│   │   ├── panel-domains.tsx               # MODIFY: use removeDomainOptimistic + render error banner (D4); 3-file split per D8; toast period + CTA copy normalization (D25)
│   │   ├── panel-domains-row.tsx           # NEW: per-row editor (D8)
│   │   ├── panel-domains-add.tsx           # NEW: add-domain affordance (D8)
│   │   └── panel-domains-active.tsx       # NEW: active-domain dropdown (D8)
│   ├── bulk/
│   │   └── bulk-screen.tsx                 # MODIFY: useDomains() (D3)
│   ├── dialogs/
│   │   ├── file-to-wiki-dialog.tsx         # MODIFY: useDomains() (D3)
│   │   ├── repair-config-dialog.tsx        # NEW: scaffold per D9 + D28
│   │   ├── autonomy-modal.tsx              # NEW: scaffold per D10
│   │   └── file-preview-overlay.tsx        # NEW: dedicated overlay per D11
│   ├── chat/
│   │   ├── chat-screen.tsx                 # MODIFY: per-message Fork dialog wired (D11); pendingSendRef-as-local audit findings (D31)
│   │   └── wikilink-hover.tsx              # MODIFY: a11y tooltip role + scan (D11)
│   └── topbar/
│       └── scope-picker.tsx                # MODIFY: "Set as default" button SCAFFOLD (D31)
├── src/lib/state/
│   ├── domains-store.ts                    # MODIFY: add removeDomainOptimistic (D4); domainsLoaded → loaded rename (D5); BroadcastChannel pubsub (D6)
│   ├── cross-domain-gate-store.ts          # MODIFY: wire error field (D5); BroadcastChannel pubsub (D6); setAcknowledgedOptimistic early-return (D7)
│   └── budget-store.ts                     # NEW: zustand promotion scaffold per D31(b)
├── src/lib/state/inbox-store.ts            # MODIFY: loadRecent id-keyed merge (D1)
├── tests/e2e/
│   ├── _helpers.ts                         # MODIFY: + waitForToolResponse helper (D19)
│   ├── a11y-populated.spec.ts              # MODIFY: 3 new cases (D11); waitForTimeout removal (D19); test.afterEach cleanup (D20)
│   └── cross-domain-modal.spec.ts          # MODIFY: 3 TS errors fixed (D22)
└── tests/unit/
    ├── inbox-store-loadRecent.test.ts      # NEW: race-fix pin (D1)
    ├── domains-store-removeOptimistic.test.ts # NEW: pin (D4)
    ├── domains-store-broadcast.test.ts     # NEW: cross-tab pubsub pin (D6)
    ├── cross-domain-gate-store-broadcast.test.ts # NEW: pin (D6)
    ├── panel-domains-row.test.tsx          # NEW: split component pin (D8)
    ├── repair-config-dialog.test.tsx       # NEW: scaffold pin (D9)
    ├── autonomy-modal.test.tsx             # NEW: scaffold pin (D10)
    ├── privacy-railed-glossary-tooltip.test.tsx # NEW: positive unit test (D25)
    └── chat-screen.test.tsx                # MODIFY: act() warnings cleared (D23)

packages/brain_cli/
└── (no changes — Plan 15 Task 4 already migrated)

packages/brain_mcp/
└── (no changes — Plan 12 + 13 wiring is current)

apps/brain_web/src/styles/
├── tokens.css                              # MODIFY: add --tt-cyan-hover token (D12)
└── brand-skin.css                          # MODIFY: .prose / .msg-body / .turn-body convention comment block (D13); .prose a:hover routes through --tt-cyan-hover (D12)

apps/brain_web/.stylelintrc.json            # NEW: stylelint config with no-hardcoded-hex-outside-root (D13)

.github/
├── actions/
│   └── setup-brain-test-env/
│       └── action.yml                      # NEW: composite action DRY (D15)
├── workflows/
│   ├── ci.yml                              # MODIFY: caching (D14); composite action (D15); summary writeback (D18)
│   └── playwright.yml                      # MODIFY: caching (D14); composite action (D15); pnpm install --filter (D16); SmartScreen pre-step (D17); summary writeback (D18)
└── pre-commit-config.yaml (or .pre-commit-config.yaml)
                                            # MODIFY: + gh workflow run --validate hook (D16)

docs/design/
├── cross-domain-modal/
│   ├── state-1-initial.svg                 # MODIFY: "private" → "Privacy-railed" (D21)
│   ├── state-2-settings-after-toggle.svg   # MODIFY: "private" → "Privacy-railed" (D21)
│   └── microcopy.md                        # MODIFY: align to current TSX surfaces (D21)
└── (other design files unchanged)

docs/superpowers/specs/
└── 2026-04-13-cj-llm-kb-design.md          # MODIFY: §6 (Cost) footnote noting per-domain budget + rate-limit caps SCAFFOLD (Plan 16 D26 + D27)

scripts/
└── demo-plan-16.py                         # NEW: 33-gate demo per D34

tasks/
├── plans/
│   └── 16-comprehensive-carry-forward.md   # this file
├── lessons.md                              # MODIFY: + Plan 16 closure section (8+ lessons captured)
└── todo.md                                 # MODIFY: row 16 → ✅ Complete; remove Plan 16 candidate-scope; add Plan 17 candidate-scope (post-Plan-16 deferrals + remaining bigger architectural moves)
```

---

## Per-task self-review checklist (runs in every TDD task)

Same discipline as Plan 11 + 12 + 13 + 14 + 15, **PLUS one new step (item 8) for stylelint once Task 13 lands.**

1. `export PATH="$HOME/.local/bin:$PATH"` — uv on PATH
2. New submodule? → `uv sync --reinstall-package brain_core` (or whichever package)
3. **uv `UF_HIDDEN` workaround** (lesson 341 + Plan 12+13+14+15 refinements): `chflags 0 /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/lib/python3.12/site-packages/_editable_impl_*.pth 2>/dev/null` — clamp BOTH `.pth` files in the SAME COMMAND LINE as the python invocation; do NOT rely on `uv run`. Escape hatch: `PYTHONPATH=packages/brain_core/src:packages/brain_mcp/src:packages/brain_api/src:packages/brain_cli/src .venv/bin/python -m pytest ...`.
4. `uv run pytest packages/brain_core packages/brain_mcp packages/brain_api packages/brain_cli -q` — green, no regressions (or chflags-prefixed equivalent)
5. `cd packages/<pkg> && /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/bin/python -m mypy src tests && cd -` — strict clean
6. `/Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/bin/python -m ruff check packages/<pkg> && /Users/chrisjohnson/Documents/Code/TomorrowToday/cj-llm-kb/.venv/bin/python -m ruff format --check packages/<pkg>` — clean (per-package; matches dev recipe)
7. **Plan 15 Task 1 step + onward:** `uv run ruff check . && uv run ruff format --check .` — **whole-repo clean**. Closes the per-package vs whole-repo gap that hid 76 violations across Plans 11–14.
8. **NEW (Plan 16 Task 13 + onward):** `cd apps/brain_web && npx stylelint 'src/**/*.css'` — clean. Closes the hardcoded-hex drift class.
9. Frontend tasks add: `cd apps/brain_web && npm run lint && npx vitest run && cd -`
10. Per `docs/style/plan-authoring.md` rule 5, every `len(...) == N` or count check is invariant-based, not total-based.
11. **Browser-in-the-loop verification** for any UI-touching task (Tasks 1, 3-13, 21, 23, 25, 28, 31): start brain, take screenshots pre and post change, attach to per-task review.
12. `git status` — clean after commit.

Any failure in 4–11 must be fixed before reporting DONE. No blanket ignores, no weakened assertions.

---

## Task 1 — `inbox-store.loadRecent` overwrite race fix (production correctness)

**Files:**
- Modify: `apps/brain_web/src/lib/state/inbox-store.ts:158`
- Create: `apps/brain_web/tests/unit/inbox-store-loadRecent.test.ts`
- Modify: `apps/brain_web/tests/e2e/ingest-drag-drop.spec.ts` (delete the Plan 14 Task 6 `waitForResponse` test arm now that production is fixed)

**Goal:** Per D1, fix the production race where `loadRecent` resolution unconditionally replaces the inbox-store, racing optimistic additions. Id-keyed merge that preserves optimistic rows whose id is not in the server response.

**What to do:**
1. **Locate the race.** `apps/brain_web/src/lib/state/inbox-store.ts:158` (line 158 is `set({ sources: items })`).
2. **Implement the merge.** Build `serverIds = new Set(items.map(i => i.id))`; let `current = get().sources`; let `optimisticPreserved = current.filter(s => !serverIds.has(s.id) && s.status === "queued")`. Set `sources: [...optimisticPreserved, ...items]`. Order: optimistic-preserved first (since `addOptimistic` prepends new rows, preserving prepend semantics).
3. **Pin test.** New `inbox-store-loadRecent.test.ts`: simulate `addOptimistic("foo-id")` then `loadRecent` resolving with `[{id: "bar-id"}, {id: "baz-id"}]`; assert final `sources` includes the optimistic `foo-id` AND the two server rows.
4. **Delete Plan 14 Task 6 test arm.** Now that production is fixed, the `waitForResponse` band-aid in `ingest-drag-drop.spec.ts` is deletable. Confirm spec passes WITHOUT the band-aid.

**Per-task review:** the unit test is the artifact. Browser verification: drag-drop a real source while the inbox is loading; assert the optimistic row stays visible until the real row arrives. Per-task self-review checklist runs to completion.

---

## Task 2 — `_spa_fallback Response | None` mypy `@overload` (brain_api hardening)

**Files:**
- Modify: `packages/brain_api/src/brain_api/static_ui.py:187`

**Goal:** Per D2, fix the pre-existing mypy hole. `_spa_fallback` returns `Response | None`; the `raise_on_miss` discriminator pins the type. `@overload` discriminating on `Literal[True] / Literal[False]`.

**What to do:**
1. **Add overload stubs.** Above the actual `def _spa_fallback`, add `@overload def _spa_fallback(self, path: str, *, raise_on_miss: Literal[True]) -> Response: ...` and `@overload def _spa_fallback(self, path: str, *, raise_on_miss: Literal[False]) -> Response | None: ...`. Import `Literal` and `overload` from `typing`.
2. **Verify mypy strict.** `cd packages/brain_api && .venv/bin/python -m mypy src tests` reports 0 errors on `static_ui.py`.
3. **Verify behavior unchanged.** Run `pytest packages/brain_api -q`; assert 181+ pass.

**Per-task review:** mypy is the artifact. Trivial change; runtime body unchanged. Per-task self-review checklist.

---

## Task 3 — Migrate `bulk-screen.tsx` + `file-to-wiki-dialog.tsx` to `useDomains()` (Plan 13 follow-through)

**Files:**
- Modify: `apps/brain_web/src/components/bulk/bulk-screen.tsx:20+44` (drop direct `listDomains`)
- Modify: `apps/brain_web/src/components/dialogs/file-to-wiki-dialog.tsx:11+134` (drop direct `listDomains`)

**Goal:** Per D3, replace direct `listDomains()` calls with the `useDomains()` selector. Mirror Plan 13 Task 2's `panel-domains.tsx` migration.

**What to do:**
1. **bulk-screen.tsx.** Remove `import { listDomains } from "@/lib/api/tools"`. Replace the local `listDomains()` call + state hydration with `const { domains } = useDomains();`. Drop any local React state holding domain entries.
2. **file-to-wiki-dialog.tsx.** Same shape.
3. **Verify.** No grep hits for `listDomains` in either file. Vitest unit tests for both still green.

**Per-task review:** the two files are ~20 LOC change each. Browser verification: open Bulk screen + file-to-wiki dialog; verify domain list renders identically to pre-migration. Per-task self-review checklist.

---

## Task 4 — `removeDomainOptimistic` action + `useDomainsStore.error` inline banner (Plan 13 follow-through)

**Files:**
- Modify: `apps/brain_web/src/lib/state/domains-store.ts` (add `removeDomainOptimistic(slug)` action)
- Modify: `apps/brain_web/src/components/settings/panel-domains.tsx` (delete handler calls action; render error banner above list)
- Create: `apps/brain_web/tests/unit/domains-store-removeOptimistic.test.ts`

**Goal:** Per D4, optimistic delete + error banner. Plan 13 Task 2 review I1 explicitly recommended both.

**What to do:**
1. **Add action.** `domains-store.ts`: `removeDomainOptimistic: (slug: string) => set(s => ({ domains: s.domains.filter(d => d.slug !== slug) }))`. Mirrors `setActiveDomainOptimistic`'s in-store-only pattern.
2. **Wire in delete handler.** `panel-domains.tsx` delete handler: call `removeDomainOptimistic(slug)` BEFORE awaiting the API. On API failure, call `useDomainsStore.getState().refresh()` to restore the row.
3. **Render error banner.** Above the domain list in `panel-domains.tsx`: `{error && <ErrorBanner>{error.message}</ErrorBanner>}`. Read `error` from `useDomainsStore`.
4. **Pin test.** Unit test asserts `removeDomainOptimistic` removes the slug from the store; subsequent `refresh()` restores it.

**Per-task review:** unit test + browser verification. Pre-existing pattern from Plan 13 Task 2; mirror is mechanical.

---

## Task 5 — Naming alignment (`domainsLoaded` → `loaded`) + cross-domain-gate-store error field wiring (Plan 13 follow-through)

**Files:**
- Modify: `apps/brain_web/src/lib/state/domains-store.ts` (rename `domainsLoaded` → `loaded`)
- Modify: `apps/brain_web/src/lib/state/cross-domain-gate-store.ts` (already has `loaded` per Plan 13 — verify; surface `error` field as banner)
- Modify: every consumer of `domainsLoaded` in `apps/brain_web/src/`
- Modify: `apps/brain_web/src/components/settings/panel-domains.tsx` (render `cross-domain-gate-store.error` as banner too)

**Goal:** Per D5, naming alignment between the two zustand stores; surface the cross-domain-gate-store's `error` field that exists but is not rendered.

**What to do:**
1. **Rename in store.** `domains-store.ts`: rename `domainsLoaded: boolean` to `loaded: boolean`. Update the action signatures.
2. **Update every consumer.** Grep for `domainsLoaded`; replace with `loaded`. Should be ~5-10 files.
3. **Wire cross-domain-gate-store error.** `panel-domains.tsx`: render the cross-domain-gate-store's `error` field as a banner above the privacy-rail toggle list. Same shape as the `domains-store.error` banner from Task 4.
4. **Vitest update.** Any tests asserting on the field name.

**Per-task review:** mechanical rename + UI surface. Per-task self-review checklist.

---

## Task 6 — BroadcastChannel cross-tab pubsub for `domains-store` + `cross-domain-gate-store` (Plan 13 follow-through)

**Files:**
- Modify: `apps/brain_web/src/lib/state/domains-store.ts` (add channel pubsub)
- Modify: `apps/brain_web/src/lib/state/cross-domain-gate-store.ts` (add channel pubsub)
- Create: `apps/brain_web/tests/unit/domains-store-broadcast.test.ts`
- Create: `apps/brain_web/tests/unit/cross-domain-gate-store-broadcast.test.ts`

**Goal:** Per D6, BroadcastChannel-based cross-tab pubsub. Mutations in tab A surface in tab B within 100ms without `page.reload()`.

**What to do:**
1. **Channel module.** New helper `apps/brain_web/src/lib/state/_broadcast.ts` exporting `createChannelPubsub<T>(name: string, onMessage: (data: T) => void)`. SSR-guarded (`typeof BroadcastChannel === "undefined"` returns no-op). Returns `{ post: (data: T) => void; close: () => void }`.
2. **Wire in `domains-store.ts`.** On every internal `set()` that updates domains/activeDomain (refresh, setActiveDomainOptimistic, removeDomainOptimistic), call `channel.post({ domains, activeDomain })`. On inbound message, call an `_internalSet` that updates state but does NOT echo (avoids ping-pong).
3. **Wire in `cross-domain-gate-store.ts`.** Same shape; channel name distinct.
4. **Pin tests.** jsdom mocks `BroadcastChannel` (jsdom 24+ has built-in support). Test mounts two store instances; mutates A; assert B re-renders within 100ms.

**Per-task review:** pin tests are the artifact. Browser verification: open two tabs of brain; mutate domains in one; verify the other reflects within ~100ms. Per-task self-review checklist.

---

## Task 7 — `setAcknowledgedOptimistic` early-return alignment (Plan 13 follow-through)

**Files:**
- Modify: `apps/brain_web/src/lib/state/cross-domain-gate-store.ts`

**Goal:** Per D7, align `setAcknowledgedOptimistic`'s body to the early-return pattern that `setActiveDomainOptimistic` uses (Plan 13 Task 3 review M1).

**What to do:**
1. **Compare patterns.** `setActiveDomainOptimistic`: `if (get().activeDomain === slug) return; set({ activeDomain: slug });`. `setAcknowledgedOptimistic` likely lacks the early-return.
2. **Align.** `setAcknowledgedOptimistic: (acked) => { if (get().acknowledged === acked) return; set({ acknowledged: acked }); }`.

**Per-task review:** ~5 LOC mechanical fix. Per-task self-review checklist.

---

## Task 8 — `panel-domains.tsx` 3-file split (Plan 13 follow-through)

**Files:**
- Modify: `apps/brain_web/src/components/settings/panel-domains.tsx` (orchestrator + list only)
- Create: `apps/brain_web/src/components/settings/panel-domains-row.tsx` (per-row editor)
- Create: `apps/brain_web/src/components/settings/panel-domains-add.tsx` (add-domain affordance)
- Create: `apps/brain_web/src/components/settings/panel-domains-active.tsx` (active-domain dropdown)
- Create: `apps/brain_web/tests/unit/panel-domains-row.test.tsx`

**Goal:** Per D8, split the 580-LOC `panel-domains.tsx` into 4 focused files. Each child file owns its own props + tests.

**What to do:**
1. **Move per-row editor.** Cut the per-domain row editor JSX + handlers into `panel-domains-row.tsx`. Export as `<PanelDomainsRow domain={...} onUpdate={...} onDelete={...} />`. Pass props from the orchestrator.
2. **Move add-domain affordance.** Cut into `panel-domains-add.tsx`.
3. **Move active-domain dropdown.** Cut the `ActiveDomainSelector` block into `panel-domains-active.tsx`.
4. **Orchestrator.** `panel-domains.tsx` becomes ~200 LOC: imports the three new files, owns the list iteration + error banner.
5. **Pin tests.** New `panel-domains-row.test.tsx` covers rename + accent-change + override edit. Existing `panel-domains.test.tsx` either splits or stays as integration.

**Per-task review:** the diff is mostly cut/paste. Browser verification: render Settings → Domains; verify visual identity to pre-split. Per-task self-review checklist.

---

## Task 9 — Repair-config dialog UI scaffold (a11y deferral)

**Files:**
- Create: `apps/brain_web/src/components/dialogs/repair-config-dialog.tsx`
- Create: `apps/brain_web/tests/unit/repair-config-dialog.test.tsx`
- Modify: `apps/brain_web/tests/e2e/a11y-populated.spec.ts` (add case)

**Goal:** Per D9, minimal dialog scaffold that satisfies the a11y-populated.spec.ts gate AND lays the groundwork for full UI in Plan 17+ (per Task 28 — the Config.config_version infrastructure).

**What to do:**
1. **Dialog component.** `<RepairConfigDialog isOpen onClose>` — radix-ui Dialog primitive (matches existing dialog conventions). Title: "Repair config". Body: short description of the auto-fallback chain ("If your config.json is corrupted, brain falls back to .bak then defaults"). Single "Run repair" button (calls a stub `repairConfig()` action that re-loads — full implementation in Task 28).
2. **brain-ui-designer copy.** Microcopy verbatim ("Repair config", "Run repair", description) lands as a designer artifact.
3. **a11y case.** New `a11y-populated.spec.ts` case opens the dialog from Settings → General; axe-core scan; 0 violations.

**Per-task review:** scaffold satisfies the a11y gate; full polish is Task 28. Per-task self-review checklist.

---

## Task 10 — Autonomy modal UI scaffold (a11y deferral)

**Files:**
- Create: `apps/brain_web/src/components/dialogs/autonomy-modal.tsx`
- Create: `apps/brain_web/tests/unit/autonomy-modal.test.tsx`
- Modify: `apps/brain_web/tests/e2e/a11y-populated.spec.ts` (add case)

**Goal:** Per D10, minimal autonomy modal that wraps the existing per-screen Switch toggles into a single dialog with global on/off + per-category overrides.

**What to do:**
1. **Modal component.** `<AutonomyModal isOpen onClose>` — radix-ui Dialog primitive. Title: "Autonomy mode". Body: Switch (global) + 3 per-category Switches (new files, edits, index entries). Trigger: a button on the topbar (or Settings → General).
2. **brain-ui-designer copy.** Microcopy verbatim.
3. **a11y case.** New `a11y-populated.spec.ts` case; axe-core scan; 0 violations.

**Per-task review:** scaffold-only; per-domain category schema is Task 30 (brainstorm-only). Per-task self-review checklist.

---

## Task 11 — a11y-populated additions: file-preview overlay + WikilinkHover tooltip + per-message Fork dialog

**Files:**
- Create: `apps/brain_web/src/components/dialogs/file-preview-overlay.tsx` (dedicated overlay, not inline split-pane)
- Modify: `apps/brain_web/src/components/chat/wikilink-hover.tsx` (verify `role="tooltip"` + a11y attributes)
- Modify: `apps/brain_web/src/components/chat/chat-screen.tsx` (per-message Fork dialog wired)
- Modify: `apps/brain_web/tests/e2e/a11y-populated.spec.ts` (add 3 cases)

**Goal:** Per D11, three a11y surfaces missing from Plan 14's a11y-populated coverage. Each adds a deterministic axe-core case.

**What to do:**
1. **file-preview overlay.** Replace Browse's inline split-pane with a dedicated overlay (radix-ui Dialog). The split-pane stays as the empty-state default; the overlay is the populated-state surface. New a11y case opens the overlay; axe-core scan; 0 violations.
2. **WikilinkHover tooltip.** Verify `role="tooltip"`, `aria-describedby` link from the trigger element, focusable on hover/focus. New a11y case hovers a wikilink; axe-core scans the rendered tooltip; 0 violations.
3. **Per-message Fork dialog.** A second Fork trigger on each message bubble (different from the chat-sub-header Fork). Wires to the same `<ForkThreadDialog>`. New a11y case clicks per-message Fork; axe-core scan; 0 violations.

**Per-task review:** 3 a11y cases pass on Mac AND Windows CI. Per-task self-review checklist.

---

## Task 12 — `--tt-cyan-hover` token + `--brand-ember` foreground audit (CSS structural cleanup)

**Files:**
- Modify: `apps/brain_web/src/styles/tokens.css` (add `--tt-cyan-hover` for both themes)
- Modify: `apps/brain_web/src/styles/brand-skin.css` (`.prose a:hover` routes through token; audit other foregrounds)

**Goal:** Per D12, hover-state token unification + audit of `var(--brand-ember)` foreground sites for the same dark-mode contrast trap Plan 14 Task 5 closed for `.prose a`.

**What to do:**
1. **Add token.** `tokens.css`: `--tt-cyan-hover` defined for `:root` (light shade) and `[data-theme="dark"]` (bright shade). Pick shades that meet 4.5:1 vs `--surface-1`.
2. **Route hover.** `brand-skin.css`: `.prose a:hover { color: var(--tt-cyan-hover); }`. Replace any direct `var(--brand-ember-2)` hover usage.
3. **Audit foregrounds.** `grep -rn "var(--brand-ember)" apps/brain_web/src/`. List ≥4 sites; for each, check 4.5:1 contrast in light + dark mode. Fix any failure by routing through the theme-aware token.

**Per-task review:** axe-core suite runs locally + CI; 0 contrast violations. Per-task self-review checklist.

---

## Task 13 — stylelint hardcoded-hex rule + `.prose` / `.msg-body` / `.turn-body` selector convention doc (CSS structural cleanup)

**Files:**
- Create: `apps/brain_web/.stylelintrc.json` (config with no-hardcoded-hex-outside-root rule)
- Modify: `apps/brain_web/package.json` (add stylelint dev-dep + script)
- Modify: `apps/brain_web/src/styles/brand-skin.css` (top-of-file convention comment block)
- Modify: `.github/workflows/playwright.yml` OR `.github/workflows/ci.yml` (add stylelint step)

**Goal:** Per D13, structural enforcement of "no hardcoded hex outside :root blocks" + onboarding doc for the selector taxonomy.

**What to do:**
1. **stylelint setup.** Install `stylelint` + `stylelint-config-standard` as dev-deps. `.stylelintrc.json` extends `stylelint-config-standard` and adds the custom rule (regex match for `#[0-9a-fA-F]+` outside `:root` declarations).
2. **CI step.** Add `npx stylelint 'apps/brain_web/src/**/*.css'` to a workflow.
3. **Convention comment.** Top of `brand-skin.css`: a comment block explaining `.prose` (ingested-content prose), `.msg-body` (chat message bodies), `.turn-body` (full chat-turn wrappers), with one-line guidance on which selector to use for new content.

**Per-task review:** stylelint runs clean on existing CSS (or any violation gets fixed in this task). Per-task self-review checklist.

---

## Task 14 — Workflow caching (uv + pnpm + Playwright browsers)

**Files:**
- Modify: `.github/workflows/ci.yml` (uv + pnpm caches)
- Modify: `.github/workflows/playwright.yml` (uv + pnpm + Playwright browser caches)

**Goal:** Per D14, eliminate cold-install duration on CI. `actions/cache@v4` for the three slow steps.

**What to do:**
1. **uv cache.** Cache `~/.cache/uv` keyed on `pyproject.toml + uv.lock` hash.
2. **pnpm cache.** Cache `apps/brain_web/.pnpm-store` keyed on `apps/brain_web/pnpm-lock.yaml` hash.
3. **Playwright browser cache.** Cache `~/.cache/ms-playwright` (Mac) + `%USERPROFILE%/AppData/Local/ms-playwright` (Windows) keyed on Playwright version.

**Per-task review:** measure CI duration pre/post; expect 30-60% reduction on cache hit. Per-task self-review checklist.

---

## Task 15 — Composite action / DRY for chflags + PYTHONPATH + npx playwright test

**Files:**
- Create: `.github/actions/setup-brain-test-env/action.yml`
- Modify: `.github/workflows/playwright.yml` (Mac + Windows steps invoke composite action)
- Modify: `.github/workflows/ci.yml` (Mac + Windows steps if CI uses the same recipe)

**Goal:** Per D15, eliminate the duplication Plan 14 Task 8 review noted.

**What to do:**
1. **Composite action.** `action.yml` declares inputs (`shell`, `pythonpath_separator`, `python_path`); steps run uv install + pnpm install + chflags (Mac only via `if`) + sets `PYTHONPATH` env.
2. **Workflow invocations.** Replace inline steps with `uses: ./.github/actions/setup-brain-test-env`.

**Per-task review:** workflow runs unchanged behavior; diff is line-count reduction. Per-task self-review checklist.

---

## Task 16 — `gh workflow run --validate` pre-commit + `pnpm install --filter brain_web...`

**Files:**
- Modify: `.pre-commit-config.yaml` (add gh workflow validate hook)
- Modify: `.github/workflows/playwright.yml` (pnpm install scope narrowed)

**Goal:** Per D16, structural guard against malformed workflow YAML + faster pnpm install on CI.

**What to do:**
1. **Pre-commit hook.** Custom hook that runs `gh workflow run --dry-run --validate` against any modified `.github/workflows/*.yml` file. Document in `tasks/lessons.md` Plan 16 section.
2. **pnpm install scope.** Replace workspace-wide `pnpm install --frozen-lockfile` with `pnpm install --frozen-lockfile --filter brain_web...`.

**Per-task review:** pre-commit hook fires on a deliberately-malformed test branch; pnpm install duration drops by ~30s on CI. Per-task self-review checklist.

---

## Task 17 — Defender SmartScreen pre-step + PowerShell line-ending lesson

**Files:**
- Modify: `.github/workflows/playwright.yml` (Defender step under feature flag)
- Modify: `tasks/lessons.md` (Plan 16 section: PowerShell line-ending entry)

**Goal:** Per D17, opt-in workaround for Windows CI Defender flakes + lesson capture for the line-ending discipline.

**What to do:**
1. **Defender step.** Add a `if: env.DEFENDER_DISABLE == 'true' && runner.os == 'Windows'` step running `Set-MpPreference -DisableRealtimeMonitoring $true`. Off by default; enable via workflow var.
2. **Lesson capture.** Add to Plan 16 closure section: "PowerShell line-ending discipline — UTF-8-BOM-on-PS5.1 vs UTF-8-no-BOM-on-pwsh. Current workflows use pwsh so this hasn't bit yet, but if a workflow ever runs on PS5.1, scripts must be saved as UTF-8 (no BOM)."

**Per-task review:** Defender step doesn't fire by default (verify off branch). Lesson captured. Per-task self-review checklist.

---

## Task 18 — CI duration observability per-job summary

**Files:**
- Modify: `.github/workflows/playwright.yml` (final step writes summary)
- Modify: `.github/workflows/ci.yml` (final step writes summary)

**Goal:** Per D18, surface per-step wall-clock to `$GITHUB_STEP_SUMMARY` for visibility.

**What to do:**
1. **Summary step.** Final step in each job: shell script that reads `$GITHUB_OUTPUT` step durations OR `$GITHUB_RUN_ID` via `gh api` and writes a Markdown table (Step | Duration | Status) to `$GITHUB_STEP_SUMMARY`.
2. **Verify.** Trigger a workflow run; verify the summary appears in the GitHub UI without drilling into logs.

**Per-task review:** summary row visible in GitHub Actions UI. Per-task self-review checklist.

---

## Task 19 — `waitForToolResponse` helper + `waitForTimeout` removal across `a11y-populated.spec.ts`

**Files:**
- Modify: `apps/brain_web/tests/e2e/_helpers.ts` (add `waitForToolResponse(page, toolName)`)
- Modify: `apps/brain_web/tests/e2e/a11y-populated.spec.ts` (replace ~11 `waitForTimeout` calls)

**Goal:** Per D19, deterministic waits replace sleep-based beats. Lesson 343 production-shape replacement.

**What to do:**
1. **Helper.** `waitForToolResponse(page, toolName)`: returns the first `/tools/<toolName>` response; uses `page.waitForResponse(r => r.url().includes(toolName) && r.status() === 200)`.
2. **Audit.** `grep "waitForTimeout" a11y-populated.spec.ts`; for each call, identify what beat is being awaited (mount, dialog open, route nav, tool call); replace with the appropriate deterministic wait.
3. **Verify.** Spec runs cleanly under `--repeat-each=5`.

**Per-task review:** spec stability is the artifact. Per-task self-review checklist.

---

## Task 20 — `test.afterEach` cleanup contract + `text-[var(--bg)]` → `text-[var(--accent-foreground)]` in `patch-card.tsx`

**Files:**
- Modify: `apps/brain_web/tests/e2e/a11y-populated.spec.ts` (+ afterEach for state-mutating cases)
- Modify: `apps/brain_web/src/components/pending/patch-card.tsx:117` (semantic token fix)

**Goal:** Per D20, codify the cleanup pattern + fix the semantic-correctness regression Plan 13 Task 6 review noted.

**What to do:**
1. **afterEach contract.** For each state-mutating case (patch-card edit-approve at minimum), add `test.afterEach` that reverts the mutation (e.g., reject the seeded patch). Document the contract at the top of `a11y-populated.spec.ts`.
2. **patch-card token.** `patch-card.tsx:117`: replace `text-[var(--bg)]` with `text-[var(--accent-foreground)]`. Visual check identical (the tokens are aliases under the current theme).

**Per-task review:** Per-task self-review checklist + browser verification on patch-card.

---

## Task 21 — SVG mockup copy update (Plan 15 review residual)

**Files:**
- Modify: `docs/design/cross-domain-modal/state-1-initial.svg`
- Modify: `docs/design/cross-domain-modal/state-2-settings-after-toggle.svg`
- Modify: `docs/design/cross-domain-modal/microcopy.md`

**Goal:** Per D21, replace "private" copy with "Privacy-railed" in the SVG mockups + microcopy doc.

**What to do:**
1. **SVG text nodes.** Open each SVG in the editor (or text-edit the XML directly); replace "private" / "kept private" with "Privacy-railed". Preserve layout.
2. **microcopy.md.** Update the doc to describe the current TSX copy (matches Plan 15 Task 5).

**Per-task review:** brain-ui-designer reviews. Visual diff of SVG vs current TSX; assert alignment. Per-task self-review checklist.

---

## Task 22 — 3 pre-existing TS errors in `cross-domain-modal.spec.ts` (Plan 15 review residual)

**Files:**
- Modify: `apps/brain_web/tests/e2e/cross-domain-modal.spec.ts`

**Goal:** Per D22, fix the 3 pre-existing TS errors with `@ts-expect-error` (preferred) or narrowing.

**What to do:**
1. **Identify.** `npx tsc --noEmit -p apps/brain_web` (or equivalent). 3 errors in `cross-domain-modal.spec.ts`.
2. **Fix each.** For each error, either `@ts-expect-error` with a comment explaining the intentional shape OR narrow the type at the call site.

**Per-task review:** `tsc --noEmit` reports 0 errors. Per-task self-review checklist.

---

## Task 23 — act() warnings sweep in `chat-screen.test.tsx` (Plan 15 review residual)

**Files:**
- Modify: `apps/brain_web/tests/unit/chat-screen.test.tsx` (or wherever `chat-screen.test.tsx` lives)

**Goal:** Per D23, wrap async dispatches in `act(async () => { ... })`; assert vitest stderr clean.

**What to do:**
1. **Identify async dispatches.** Each test that triggers `handleCrossDomainContinue` (or any async setState).
2. **Wrap.** `await act(async () => { fireEvent.click(...); await flushPromises(); });`.
3. **Verify.** vitest stderr no longer prints `act()` warnings.

**Per-task review:** stderr capture in vitest config; 0 warnings. Per-task self-review checklist.

---

## Task 24 — `test_config_get._mk_ctx` Path A alignment (Plan 15 review residual)

**Files:**
- Modify: `packages/brain_core/tests/tools/test_config_get.py`

**Goal:** Per D24, `_mk_ctx` requires explicit `config: Config` (matches Plan 15 Task 9 D8).

**What to do:**
1. **Audit `_mk_ctx`.** Currently: `def _mk_ctx(vault: Path, config: Config | None) -> ToolContext`. The 4th `_mk_ctx` variant from Plan 15.
2. **Align.** Make `config: Config` (no `| None`). Update every call site to pass an explicit `Config` instance (the None-config path is exclusively exercised through `test_errors_raise_if_no_config.py`).
3. **Verify.** `pytest packages/brain_core/tests/tools/test_config_get.py -q` passes.

**Per-task review:** Per-task self-review checklist.

---

## Task 25 — Toast period + Plan 07 deferrals + PrivacyRailedGlossaryTooltip unit test (Plan 15 review residuals trio)

**Files:**
- Modify: `apps/brain_web/src/components/settings/panel-domains.tsx` (toast period normalization)
- Modify: `packages/brain_core/src/brain_core/tools/config_set.py:81+90` (drop Plan 07 forward-looking comments)
- Modify: `packages/brain_core/src/brain_core/config/schema.py:101` (drop Plan 07 forward-looking comment)
- Create: `apps/brain_web/tests/unit/privacy-railed-glossary-tooltip.test.tsx`

**Goal:** Per D25, three trivially-small Plan 15 review residuals grouped in one PR.

**What to do:**
1. **Toast period.** `panel-domains.tsx` active-domain toast: ensure `${detail} Pick a different domain.` and `${detail} Try again.` have consistent end-of-detail period handling (no double period; no missing period before CTA).
2. **Plan 07 comments.** `config_set.py:81` ("Plan 07 Task 1 / Task 5"), `config_set.py:90` ("Plan 07 Task 2 / Task 5"), `schema.py:101` ("Plan 07 Task 5 wires real persistence"). Drop the forward-looking Plan 07 references; describe the current behavior. Mirrors Plan 15 Task 10's `apply_patch._resolve_config` cleanup.
3. **Tooltip unit test.** `privacy-railed-glossary-tooltip.test.tsx`: positive test that renders `<PrivacyRailedGlossaryTooltip>` and asserts the tooltip text on focus/hover.

**Per-task review:** ~15 LOC total. Per-task self-review checklist.

---

## Task 26 — Per-domain budget caps SCAFFOLD (bigger architectural moves)

**Files:**
- Modify: `packages/brain_core/src/brain_core/config/schema.py` (add `Config.budget.per_domain` field)
- Create: `packages/brain_core/tests/config/test_schema_per_domain_budget.py`
- Modify: `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` (§6 Cost footnote)

**Goal:** Per D26, schema-only SCAFFOLD. Field exists, round-trips, but no enforcement plumbing yet.

**What to do:**
1. **Schema.** `BudgetConfig` model gets `per_domain: dict[str, BudgetOverride]` field where `BudgetOverride.monthly_cap_usd: float | None`. Pydantic v2 model; default `{}`.
2. **Pin test.** Round-trip: write a Config with `per_domain={"research": BudgetOverride(monthly_cap_usd=10.0)}`; serialize to JSON; re-read; assert equality.
3. **Spec footnote.** §6 (Cost): "Plan 16 lands `Config.budget.per_domain: dict[str, BudgetOverride]` as schema scaffolding. Full enforcement (per-call lookup + cost-ledger schema migration) deferred to Plan 17+."

**Per-task review:** schema test + spec footnote. Per-task self-review checklist.

---

## Task 27 — Per-domain rate limits SCAFFOLD (bigger architectural moves)

**Files:**
- Modify: `packages/brain_core/src/brain_core/config/schema.py` (add `Config.providers[*].rate_limit_per_domain`)
- Create: `packages/brain_core/tests/config/test_schema_per_domain_rate_limit.py`
- Modify: `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` (§6 Cost footnote — combined with Task 26)

**Goal:** Per D27, schema-only SCAFFOLD. Mirrors Task 26's shape.

**What to do:**
1. **Schema.** `ProviderConfig.rate_limit_per_domain: dict[str, RateLimitOverride]` where `RateLimitOverride.requests_per_minute: int | None`.
2. **Pin test.** Round-trip.
3. **Spec footnote.** Combined with Task 26's footnote.

**Per-task review:** Per-task self-review checklist.

---

## Task 28 — Repair-config UI + cross-process hot-reload SCAFFOLDS

**Files:**
- Modify: `apps/brain_web/src/components/dialogs/repair-config-dialog.tsx` (full surface beyond Task 9 scaffold)
- Modify: `packages/brain_core/src/brain_core/config/schema.py` (`Config.config_version: int`)
- Modify: `packages/brain_core/src/brain_core/config/loader.py` (`_resolve_config` reads version, re-loads on mismatch)
- Create: `packages/brain_core/tests/config/test_config_version_field.py`

**Goal:** Per D28, repair-config dialog gets the "Run repair" button wired to a real action; Config gains a version field that single-process invalidation reads on every refresh.

**What to do:**
1. **`config_version` field.** Default `0`. Increment in `save_config` on every write.
2. **Loader hot-reload.** `_resolve_config` (or equivalent loader): keep an in-memory cache; on each request, stat the config file's `version` field; reload if changed.
3. **Repair-config button.** Wires to `repairConfig()` action that re-runs the loader against `.bak` if `config.json` is corrupt; surfaces per-step results in the dialog.

**Per-task review:** schema test + dialog surface verified in browser. Cross-process pubsub deferred to Plan 17+ (a separate subprocess SIGHUP-style file watch). Per-task self-review checklist.

---

## Task 29 — `validate_assignment=True` perf-measure + decision

**Files:**
- Create: `packages/brain_core/tests/config/test_validate_assignment_perf.py` (perf-measure benchmark)
- Modify: `packages/brain_core/src/brain_core/config/schema.py` (set `validate_assignment=True` IF perf passes)
- Modify: `tasks/lessons.md` (Plan 16 section: perf-measure outcome)

**Goal:** Per D29, measure perf overhead; decide based on threshold.

**What to do:**
1. **Benchmark.** `test_validate_assignment_perf.py`: run 1000 random field assignments with and without `validate_assignment=True`. Measure wall-clock.
2. **Decide.** If overhead < 10%, set `model_config = ConfigDict(validate_assignment=True)` on Config + sub-configs; update KNOWN-LIMITATION pin test (`test_invalid_value_currently_persists_without_validation`) to assert the new behavior. If overhead > 10%, document the perf-measure outcome in `tasks/lessons.md`; KNOWN-LIMITATION test stays.
3. **Either way.** Document the decision in `tasks/lessons.md` Plan 16 section.

**Per-task review:** perf-measure outcome + decision + (if enabled) updated pin test. Per-task self-review checklist.

---

## Task 30 — Per-domain autonomy categories — brainstorm-only

**Files:**
- Modify: `tasks/plans/16-comprehensive-carry-forward.md` (Task 30 Findings subsection)

**Goal:** Per D30, brainstorm + lock the schema shape for Plan 17+. NO implementation in Plan 16.

**What to do:**
1. **Brainstorm.** Schema shape: `Config.autonomous: dict[str, dict[Literal["new_files","edits","index_entries"], bool]]`. Current shape: `Config.autonomous: bool` (single global flag).
2. **Findings doc.** Append a "Task 30 findings" subsection to this plan file. Cover: (a) the locked schema shape; (b) migration story (existing `autonomous=True` becomes `{"<all-domains>": {"new_files": True, "edits": True, "index_entries": True}}`); (c) UI impact (Task 10's autonomy modal grows per-category sliders); (d) any open questions.
3. **No code change.** Plan 17+ implements.

**Per-task review:** findings doc IS the artifact. Per-task self-review checklist.

---

## Task 31 — "Set as default" topbar + generic zustand promotion + pendingSendRef-as-local audit

**Files:**
- Modify: `apps/brain_web/src/components/topbar/scope-picker.tsx` ("Set as default" button SCAFFOLD)
- Create: `apps/brain_web/src/lib/state/budget-store.ts` (zustand promotion of `useBudget`)
- Modify: `apps/brain_web/src/components/chat/chat-screen.tsx` (any pendingSendRef-as-local extensions)
- Append: `tasks/plans/16-comprehensive-carry-forward.md` (Task 31 audit doc)

**Goal:** Per D31, three trivially-small architectural moves grouped in one PR.

**What to do:**
1. **"Set as default" button.** Topbar scope picker gets a button that calls existing `setActiveDomain` API. ~10 LOC + one unit test.
2. **`budget-store.ts`.** Zustand promotion of `useBudget`. Mirror `domains-store.ts` shape. Migrate consumers.
3. **`pendingSendRef`-as-local audit.** Grep `chat-screen.tsx` + neighboring handlers for refs that span an await. Findings doc filed in this plan file's Review section. Implement extensions ONLY if an obvious bug class hits.

**Per-task review:** ~50 LOC total. Per-task self-review checklist.

---

## Task 32 — Generic `ctx.config` lint rule SCAFFOLD

**Files:**
- Create: ruff custom rule OR mypy plugin entry (location TBD by implementer)
- Modify: `.github/workflows/ci.yml` (add lint step)
- Create: `packages/brain_core/tests/linting/test_ctx_config_lint_rule.py`

**Goal:** Per D32, structural enforcement of "tools that need Config call `raise_if_no_config(ctx, ...)`; no other tool reads `ctx.config` directly".

**What to do:**
1. **Rule scaffold.** Either a ruff custom rule (if ruff supports project-local rules) OR a mypy plugin entry. Whitelist: `config_get`, `list_domains`, `config_set` (the 3 callers from Plan 15 Task 8). Anything else reading `ctx.config` triggers a lint error.
2. **CI step.** Lint step in `ci.yml`.
3. **Pin test.** `test_ctx_config_lint_rule.py`: scaffold contract — assert the rule fires on a known-bad pattern.

**Per-task review:** lint step runs in CI. Per-task self-review checklist.

---

## Task 33 — Closure: 33-gate demo + lessons + todo.md + spec footnote

**Files:**
- Create: `scripts/demo-plan-16.py`
- Modify: `tasks/lessons.md` (Plan 16 closure section)
- Modify: `tasks/todo.md` (row 16 → ✅ Complete; remove Plan 16 candidate-scope; add Plan 17 candidate-scope)
- Modify: `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` (§6 Cost footnote per Tasks 26+27)

**Goal:** Land the 33-gate demo. Lessons capture. todo.md update. ONE spec footnote per D31.

**What to do:**
1. **demo-plan-16.py.** Mirror `scripts/demo-plan-15.py` structure. Build the 33 gates per the demo gate description in plan header.
2. **Demo script execution prefix:** `chflags 0 .../_editable_impl_*.pth && .venv/bin/python scripts/demo-plan-16.py` per lesson 341.
3. **Lessons capture.** Mirror Plan 15 closure-section format. Closure summary, then one paragraph per lesson:
   - **Production race fix (T1).** `loadRecent` overwrite race: id-keyed merge preserves optimistic rows. The Plan 14 Task 6 `waitForResponse` band-aid is now deletable. Lesson: production races that surface under test conditions are real bugs; fix production, then delete the test arm.
   - **Architectural carry-forward at scale (T3-T8 + T26-T32).** Plan 16's 30-task shape was sustainable because (a) most tasks were < 50 LOC + combined review; (b) the SCAFFOLD shape for bigger moves let us land schema-first without committing to enforcement. Lesson: when carry-forward scope hits 50+ items, prefer 30 narrow tasks over 10 wide tasks.
   - **Schema-first SCAFFOLD pattern.** Per-domain budget + rate-limit caps landed as schema fields without enforcement. Mirrors Plan 11 (`Config.privacy_railed: list[str]` schema first, enforcement layered on later). Lesson: when a feature has uncertain UX ergonomics, ship the data shape first; let it sit on disk for a user-iteration before committing to the polish.
   - **BroadcastChannel cross-tab pubsub.** Closes the optimistic-clobber race class for both `domains-store` and `cross-domain-gate-store`. Lesson: when one store has a known race shape, audit sibling stores for the same shape; the second one is usually waiting in the wings.
   - **Stylelint as structural enforcement.** Plan 14 lesson C3 (theme-aware tokens) is now enforced by stylelint. Lesson: when a discipline relies on "remember to use the token", structural enforcement (stylelint, custom ruff rule) is the only durable fix.
   - **CI duration observability.** Plan 14 Task 7+8 added Mac+Windows matrix; Plan 16 Task 18 surfaces per-job wall-clock to `$GITHUB_STEP_SUMMARY`. Lesson: the act of measuring CI duration creates pressure to keep it down. Caching (Task 14) + composite action (Task 15) follow naturally.
   - **Brainstorm-only tasks have a place.** Task 30 (per-domain autonomy categories) lands findings, no implementation. Lesson: when a schema redesign is genuinely ambiguous, separating the brainstorm from the implementation across plans is better than rushing both into one plan.
   - **Forward-looking deferral comments at scale.** Plan 15 Task 10 cleaned one forward-looking deferral; Plan 16 Task 25 cleans three more. Lesson: every plan should have a "drop stale Plan-N references" sweep as an explicit task.
   - **Combined review held across 30 tasks.** Plan 15 lesson 5 said combined review is sufficient for < 50 LOC; Plan 16 stress-tested it at 30 tasks. Lesson: combined review scales with plan size IF per-task PR shape stays narrow.
4. **`tasks/todo.md` update.** Row 16 → ✅ Complete. Remove "Plan 16 candidate scope" tail section. Add "Plan 17 candidate scope (forwarded from Plan 16)" — pre-populate with the post-Plan-16 deferrals (full enforcement of per-domain budget caps; full enforcement of per-domain rate limits; cross-process hot-reload pubsub; per-domain autonomy implementation; migration tool IF/when needed; `seedBrainMd` / `seedScope` extraction once 5th caller appears; any new candidate scope discovered during Plan 16 execution).
5. **Spec footnote.** §6 (Cost): one paragraph noting `Config.budget.per_domain` + `Config.providers[*].rate_limit_per_domain` are SCAFFOLD fields; full enforcement deferred. NO other spec text changes.

**Per-task review:** demo gates 1-33 all green. Lessons capture is the Plan 16 retrospective. todo.md update is the closure handoff. Spec footnote is the one explicit user-facing surface change. Per-task self-review checklist runs to completion.

---

## Review (pending)

To be filled in on closure following Plan 10 + 11 + 12 + 13 + 14 + 15 format:
- **Tag:** `plan-16-comprehensive-carry-forward` (cut on green demo).
- **Closes:** all 50+ items from Plan 16 candidate scope (themes 1-9 directly; theme 10 as SCAFFOLDS or DEFERS). Plan 16 candidate-scope tail block in `tasks/todo.md` removed; Plan 17 candidate-scope tail block added.
- **Bumps:** schema gains 3 new fields (`Config.budget.per_domain`, `Config.providers[*].rate_limit_per_domain`, `Config.config_version`). New components: `RepairConfigDialog`, `AutonomyModal`, `FilePreviewOverlay`, `PanelDomainsRow` + `PanelDomainsAdd` + `PanelDomainsActive`, `BudgetStore`. New stores: `budget-store.ts`. New tooling: stylelint (with hardcoded-hex rule), pre-commit gh workflow validate hook, ctx.config lint rule scaffold. New CI infrastructure: composite action, workflow caching, per-job summary writeback, Defender SmartScreen feature flag.
- **Verification:** all 33 demo gates green (`scripts/demo-plan-16.py` → `PLAN 16 DEMO OK`); pytest count + vitest count + Playwright count + Mac+Windows CI green to be filled in.
- **Backlog forward:** Plan 17 candidate scope pre-populated per Task 33 step 4. Themes: full enforcement of bigger architectural moves landed as scaffolds (per-domain budget + rate-limit + autonomy + cross-process hot-reload pubsub); migration tool if/when needed; `seedBrainMd` / `seedScope` once 5th caller appears; any new candidate scope discovered during Plan 16 execution.
- **Forwards:** lessons captured in `tasks/lessons.md` under "Plan 16" feed Plan 17's authoring.

---

## Task 30 — Findings (to be filled by implementer)

To be appended by Task 30 implementer per D30. Expected shape:

- **Locked schema:** TBD (recommended: `Config.autonomous: dict[str, dict[Literal["new_files","edits","index_entries"], bool]]`).
- **Migration story:** TBD.
- **UI impact:** TBD.
- **Open questions:** TBD.

---

## Task 31 — pendingSendRef-as-local audit findings (to be filled by implementer)

To be appended by Task 31 implementer per D31(c). Expected shape:

- **Surfaces inspected:** TBD.
- **Refs spanning an await:** TBD.
- **Recommended extensions:** TBD (or "no extension needed").

---

**End of Plan 16.**
