# Plan 16 — Comprehensive carry-forward closure

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Plan 16 D36 locks **sequential per-task dispatch with combined spec-and-code-quality review** (Plan 11 + 12 + 13 + 14 + 15 discipline) — do NOT parallelize even when the dependency graph allows it. Plan 16 has the largest task count of any plan in this project (47 tasks); the discipline cost is justified because (a) most tasks are < 50 LOC polish that flush quickly through combined review, and (b) per the user's locked decision **1.B (full production)**, every Theme 10 architectural move lands at production-grade — schema + enforcement + UI surface where applicable — which means each concern that previously sat as a single SCAFFOLD now expands to 2-4 narrow sequential tasks (schema → enforcement → UI surface), each ~20 LOC.

**Goal:** Close the entire Plan 15 candidate-scope carry-forward in one cohesive plan AT PRODUCTION-GRADE. ~50 items across 10 themes accumulated from Plan 12, 13, 14, and 15 reviews — landed here as 47 narrowly-scoped tasks. Two tracks: (a) **carry-forward closure** (themes 1–9; actual deferrals + reviews from prior plans, mostly < 50 LOC each); (b) **architectural completions** (theme 10; bigger moves landed at FULL PRODUCTION grade per locked decision 1.B — schema + enforcement + UI surface for each, decomposed into ~3 sequential tasks per concern). The user explicitly chose 1.B over the recommended 1.A scaffold-and-defer approach: Plan 16 ships the working features end-to-end rather than parking them as data-model scaffolds for Plan 17+. Only items genuinely blocked by external dependencies (e.g., per-thread cross-domain confirmation, which violates spec §4) remain deferred.

The 10 themes (numbered to match `tasks/todo.md` Plan 16 candidate-scope):

1. **Production correctness (top priority)** — `inbox-store.loadRecent` overwrite race. The only item where a real user can see a real bug today; lands at Task 1 to make plan-author intent visible.

2. **brain_api hardening** — `_spa_fallback Response | None` mypy `@overload` discriminating on `raise_on_miss`. Plan 14 Task 5 review M2 flagged the pre-existing mypy hole; Plan 15 deferred. Task 2.

3. **Plan 13 architectural follow-throughs (still open)** — 8 items from Plan 13 Tasks 2 + 3 reviews. Orphan `listDomains` consumer migration (Task 3); `removeDomainOptimistic` action + `useDomainsStore.error` inline banner (Task 4); `domainsLoaded` → `loaded` naming + drop/wire cross-domain-gate-store error field (Task 5); BroadcastChannel cross-tab pubsub (Task 6); `setAcknowledgedOptimistic` early-return alignment (Task 7); `panel-domains.tsx` 3-file split (Task 8).

4. **Plan 14 a11y deferrals (still open)** — 5 items. Repair-config dialog UI scaffold (Task 9); autonomy modal UI scaffold (Task 10); a11y-populated additions for Browse file-preview overlay + WikilinkHover tooltip + per-message Fork dialog (Task 11). Per D9 + D10, Tasks 9 + 10 are scaffolds sufficient to satisfy the a11y-populated.spec.ts gate; full UI/UX polish for repair-config lands at Task 33 (full Re-run + per-step + Re-apply flow); per-domain autonomy panel lands at Task 40 (`panel-autonomous.tsx` per-domain × per-category grid).

5. **CSS structural cleanup** — 4 items. `--tt-cyan-hover` token + `--brand-ember` foreground audit (Task 12); stylelint hardcoded-hex rule + `.prose`/`.msg-body`/`.turn-body` selector convention doc (Task 13).

6. **CI follow-throughs** — 7 items from Plan 14 Tasks 7 + 8 reviews. Workflow caching for uv + pnpm + Playwright browsers (Task 14); composite-action DRY for chflags + PYTHONPATH + npx playwright test (Task 15); `gh workflow run --validate` pre-commit + `pnpm install --frozen-lockfile --filter brain_web...` consistency (Task 16); Defender SmartScreen pre-step under feature-flag + PowerShell line-ending lesson capture (Task 17); CI duration observability per-job summary (Task 18).

7. **Test-quality follow-throughs** — 5 items. `waitForToolResponse` helper + `waitForTimeout` removal across `a11y-populated.spec.ts` (Task 19); `test.afterEach` cleanup contract + `text-[var(--bg)]` → `text-[var(--accent-foreground)]` in `patch-card.tsx:117` (Task 20). The 5th item — `seedBrainMd` / `seedScope` helper extraction — stays deferred per the rule-of-three threshold (current count = 3; threshold = 5); captured in NOT-DOING.

8. **Plan 15 review residuals** — 7 items. SVG mockup copy update (Task 21); 3 pre-existing TS errors in `cross-domain-modal.spec.ts` (Task 22); act() warnings sweep in `chat-screen.test.tsx` (Task 23); `test_config_get.py` `_mk_ctx` Path A alignment (Task 24); toast period normalization + Plan 07 forward-looking deferrals in `config_set.py` + `schema.py` + positive unit test for `PrivacyRailedGlossaryTooltip` (Task 25 — three trivially-small items grouped to keep task count down).

9. **Cleanup carried forward** — 1 lesson-only item (plan-text "topbar scope chip" inaccuracy drift watch). Captured in NOT-DOING with rationale.

10. **Bigger architectural moves at FULL PRODUCTION (1.B)** — 21 tasks across 6 architectural concerns. **Per-domain budget caps** (4 tasks: schema T26 → cost-ledger migration + rollups T27 → BudgetGuard enforcement T28 → UI surface T29). **Per-domain rate limits** (3 tasks: schema T30 → AnthropicProvider enforcement T31 → UI surface T32). **Repair-config UI + cross-process hot-reload** (3 tasks: full repair-config UI polish T33 → `Config.config_version` + single-process invalidation T34 → cross-process hot-reload via watchdog + SIGHUP T35). **`validate_assignment=True`** (1 task T36: measure → enable always per locked 1.B + document perf cost in lessons.md regardless of outcome). **Per-domain autonomy categories** (4 tasks: brainstorm + lock schema T37 → schema migration with read-time backwards-compat T38 → AutonomyGate per-domain enforcement T39 → UI surface `panel-autonomous.tsx` T40). **`brain config migrate` CLI** (1 task T41 — lifted from NOT-DOING per 1.B; landing as a clean rollover for users on the old flat `Config.autonomous: bool` shape). **Trio of trivially-small architectural moves at full implementation** (3 tasks: "Set as default" topbar full impl T42 → generic zustand promotion of `useBudget` + `useDomainOverrides` T43 → `pendingSendRef`-as-local audit + apply T44). **`ctx.config` lint rule** (2 tasks: ruff custom rule `BRN001` plumbing T45 → violation cleanup across the codebase T46). One item stays DEFER under 1.B for spec-architectural reasons: **per-thread cross-domain confirmation** (violates spec §4 "one-time"; captured in NOT-DOING with strengthened rationale that this is a SPEC-LEVEL no, not a "we didn't get to it" no — re-litigating requires a spec amendment first).

11. **(closure)** — Task 47: 47-gate demo + lessons + todo.md update + THREE spec footnotes per D36.

**Architecture.** Two-track narrative as above. Plan 16 is the largest plan in this project (47 tasks vs Plan 15's 11) because the user's directive is explicit (1.B): every original Plan 16 candidate-scope item lands as a task AT PRODUCTION-GRADE. The discipline that makes 47 tasks tractable: D36 locks combined spec-and-code-quality review per task (Plan 15 lesson — `< 50 LOC` tasks flush through combined review), and D34 locks each task to a single ~20-line PR shape so the per-task review surface stays small. Theme 10's expansion from 7 SCAFFOLD tasks (in v1) to 21 production tasks (in v2) is the bulk of the size delta: each concern decomposes into schema → enforcement → UI surface with a pin test for each layer.

**Tech Stack.** Same gates as Plan 11 + 12 + 13 + 14 + 15 — Python 3.12, pydantic v2, `mypy --strict`, `ruff`, vitest + Playwright. GitHub Actions (Plan 14 Task 7+8 + Plan 15 Task 3). New tooling: `stylelint` (Task 13 — first plan to land it; npm workspace dep), `watchdog` (Task 35 — Python file-watcher for cross-process hot-reload), `freezegun` (Task 31 — already a dev-dep in some packages; needed broader for rate-limit time-window tests). Ruff custom-rule entry (Task 45) lands as a project-local plugin entry per the ruff plugin API.

**Demo gate.** `scripts/demo-plan-16.py` (chflags-prefixed per lesson 341) walks 47 gates — one assertion per substantive task plus sentinel:

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
26. **Per-domain budget schema** (T26): assert `Config.budget.per_domain: dict[str, BudgetOverride]` Pydantic v2 field exists; round-trips through JSON serialization.
27. **Cost-ledger per-domain rollups** (T27): `costs.sqlite` `domain` column verified present (per spec); `cost_report.py` per-domain rollup query returns expected shape on a seeded ledger fixture.
28. **BudgetGuard per-domain enforcement** (T28): unit test seeds `Config.budget.per_domain["research"].monthly_cap_usd = 10.0`, sets `ctx.domain="research"`, simulates spend up to cap, asserts `BudgetCapExceeded` raises BEFORE the LLM call.
29. **Per-domain budget UI surface** (T29): vitest renders `panel-domains-row.tsx` with daily-cap + monthly-cap inputs; mutation triggers `setDomainBudget` API call (mocked); assert serialization shape matches schema.
30. **Per-domain rate-limit schema** (T30): assert `Config.providers[*].rate_limit_per_domain: dict[str, RateLimitOverride]` Pydantic field; round-trips.
31. **AnthropicProvider per-domain rate-limit enforcement** (T31): freezegun-driven test seeds `requests_per_minute=2`; first 2 calls in window pass; 3rd call within the same minute raises `RateLimitExceeded` (or queues per leaky-bucket semantics — locked in D27).
32. **Per-domain rate-limit UI surface** (T32): vitest renders `panel-domains-row.tsx` rate-limit input; mutation triggers `setDomainRateLimit` API call (mocked); shape matches schema.
33. **Repair-config UI full surface** (T33): vitest renders `repair-config-dialog.tsx` with Re-run button + per-step results panel + Re-apply repaired config button; full keyboard a11y + axe-core scan; 0 violations.
34. **`Config.config_version` + single-process invalidation** (T34): unit test asserts `save_config` increments version; `_resolve_config` re-loads on version mismatch; in-memory cache hits return the same object identity when version is unchanged.
35. **Cross-process hot-reload** (T35): pytest-asyncio test starts a subprocess running `_resolve_config` in a loop; main process writes a new config; subprocess detects the change via `watchdog` file event + SIGHUP within 500ms; new value visible.
36. **`validate_assignment=True` enabled + perf-documented** (T36 / locked 1.B): assert `Config.model_config = ConfigDict(validate_assignment=True)` is set unconditionally; KNOWN-LIMITATION pin test (`test_invalid_value_currently_persists_without_validation`) UPDATED to assert the new validation behavior; perf-measure benchmark output captured in `tasks/lessons.md` Plan 16 section regardless of overhead.
37. **Per-domain autonomy brainstorm + locked schema** (T37): assert this plan file's "Task 37 findings" subsection contains the locked schema shape (`Config.autonomous: dict[str, dict[Literal["new_files","edits","index_entries","concepts","draft"], bool]]`).
38. **Per-domain autonomy schema migration** (T38): unit test seeds an old-shape `config.json` (`{"autonomous": true}`); loader reads it; in-place migration produces the nested per-domain × per-category shape; pin test asserts round-trip.
39. **AutonomyGate per-domain enforcement** (T39): unit test seeds a domain with `edits=true` + `new_files=false`; `apply_patch` ctx threaded with `domain="research"`; an `edits`-only patch passes; a `new_files`-containing patch is gated for approval.
40. **Per-domain autonomy UI** (T40): vitest renders `panel-autonomous.tsx` with a per-domain × per-category grid; mutation triggers `setDomainAutonomy` API call; serialization matches schema.
41. **`brain config migrate` CLI** (T41): subprocess test runs `brain config migrate <old-config.json>`; output is a new-shape config.json; original file backed up to `config.json.pre-migrate.bak`.
42. **"Set as default" topbar button (full)** (T42): vitest renders topbar scope picker with Set-as-default button; click triggers `setActiveDomain` API call; toast appears confirming.
43. **Generic zustand promotion** (T43): grep `apps/brain_web/src/lib/state/` for `budget-store.ts` + `domain-overrides-store.ts`; assert both exist; assert `useBudget` / `useDomainOverrides` consumers updated to use the stores.
44. **`pendingSendRef`-as-local audit + apply** (T44): grep `chat-screen.tsx` + neighboring handlers for the canonical capture-into-local pattern; assert no remaining "ref-spans-await" anti-pattern instances; audit findings appended to plan file.
45. **`BRN001` ruff rule plumbing** (T45): grep `pyproject.toml` for `[tool.ruff.lint.brain]` allowed-entry-points list; assert rule fires on a known-bad pattern (`ctx.config` read in a non-allowlisted file).
46. **`BRN001` violation cleanup** (T46): `uv run ruff check . --select BRN001` reports 0 errors across the whole repo; any `# noqa: BRN001` carries a rationale comment.
47. **`PLAN 16 DEMO OK`** sentinel.

Prints `PLAN 16 DEMO OK` on exit 0; non-zero on any gate failure.

**Owning subagents** (D36 distribution).
- `brain-frontend-engineer` — Tasks 1, 3, 4, 5, 6, 7, 8, 9, 10, 11 (frontend half), 12, 13 (frontend + stylelint), 20 (patch-card half), 21, 22, 23, 25 (tooltip unit test half), 29, 32, 33, 40, 42, 43, 44
- `brain-mcp-engineer` (role-overloaded brain-api-engineer per Plan 05 precedent) — Task 2 (`_spa_fallback` overload), 35 (cross-process hot-reload — brain_api emits SIGHUP to brain_mcp)
- `brain-ui-designer` — Tasks 9 + 10 (microcopy half — dialog copy + tooltip text), 21 (SVG mockup copy update), 33 (microcopy half for repair-config UI full polish), 40 (microcopy half for autonomy panel)
- `brain-test-engineer` — Tasks 11 (test half — a11y-populated additions), 17 (PowerShell lesson capture half), 19, 20 (afterEach half), 22, 23 (warning sweep half), 47 (closure demo + lessons)
- `brain-installer-engineer` — Tasks 14, 15, 16, 17 (CI workflow half), 18, 35 (watchdog plumbing half), 41 (`brain config migrate` CLI), 45, 46 (BRN001 lint rule + cleanup)
- `brain-core-engineer` — Tasks 24 (test_config_get _mk_ctx alignment), 25 (Plan 07 deferral docstring half), 26 (per-domain budget schema), 27 (cost-ledger migration + rollups), 28 (BudgetGuard enforcement), 30 (rate-limit schema), 31 (AnthropicProvider rate-limit enforcement), 34 (config_version field + single-process invalidation), 36 (validate_assignment perf + enable), 37 (autonomy brainstorm + lock), 38 (autonomy schema migration), 39 (AutonomyGate enforcement)
- `brain-frontend-engineer` + `brain-test-engineer` — Task 13 (stylelint + selector convention doc shared)

**Pre-flight** (main loop, before dispatching Task 1):
- Confirm Plan 15 closed clean: `git tag --list | grep plan-15-ci-and-polish` exists.
- Confirm no uncommitted changes on `main`. (At plan-authoring time, `git status` showed two staged plan-15-residual modifications under `packages/brain_cli/`; main loop must clean those before Task 1 dispatch.)
- Confirm `tasks/lessons.md` contains the Plan 15 closure section (6 lessons captured per Plan 15 Task 11 step 3).
- Confirm `CI` workflow is now green up to mypy debt — Plan 15 Task 1 cleared the 76 ruff violations; the residual gate failures should be limited to the pre-existing mypy `Response | None` hole that Task 2 closes.
- Confirm production `loadRecent` race is the genuine highest-priority item (ahead of architectural follow-throughs and bigger moves) — this ordering is load-bearing for plan-author intent: Plan 16 starts with the only user-visible bug.
- **Plan 16 inverts the default plan-sizing target.** Plan 11–15 averaged 9–11 tasks; Plan 16 lands 47. The discipline that makes 47 tractable: combined spec-and-code-quality review per task (Plan 15 lesson — `< 50 LOC` flushes through combined review fast), each task locked to a ~20-line PR shape, and D34 locks the rule that any task exceeding ~20 LOC at implementation time MUST split rather than expand. The user's 1.B "full production" choice forced the v1 7-task SCAFFOLD bundle (Theme 10) to expand into 21 production tasks; rather than that being a tax, it's load-bearing — each schema field, enforcement plumb, and UI surface lands as a discrete reviewable unit.
- Note the recurring uv `UF_HIDDEN .pth` workaround (lesson 341 + Plan 12+13+14+15 refinements): chflags + PYTHONPATH same-line python invocation; do NOT use `uv run` (re-syncs and re-hides). Plan 15 Task 4 made this rule first-class in `brain start`; future supervisors / launchers / orchestration tools should follow.

---

## What Plan 16 explicitly does NOT do

These items appear in Plan 16 candidate scope but are deferred outright with rationale:

- **`seedBrainMd` / `seedScope` helper extraction.** Rule-of-three threshold not yet met (current callers: 3; threshold: 5). Plan 17+ if/when a 5th caller appears. Captured in `tasks/todo.md` Plan 17 candidate scope.

- **Plan-text "topbar scope chip" inaccuracy drift watch.** Lesson-only item (no code change). Already captured in `tasks/lessons.md` Plan 12 closure section; Plan 16 adds nothing actionable here. The drift watch IS the deferral.

- **Per-thread cross-domain confirmation.** Plan 12 D8 chose per-vault `Config` field; per-thread violates spec §4 "one-time". This is a **SPEC-LEVEL no, not a "we didn't get to it" no.** Under the user's 1.B "full production" directive, plan-author re-evaluated whether this should land here; the answer is still no, because the alternative is to amend the spec, which is a separate concern from a polish-and-completion plan. If the user wants per-thread semantics in the future, the path is: spec brainstorm → spec amendment → implementation plan. Plan 16 honors the existing spec rule and strengthens the deferral rationale rather than weakening it.

- **Spec amendments warranted by Plan 16's schema-and-enforcement landings.** Plan 16 lands **THREE spec footnotes** per D36 (locked below): (a) §6 (Cost) — per-domain budget caps full implementation (T26-T29) + per-domain rate limits full implementation (T30-T32); (b) §3 (Vault) — per-domain autonomy categories landing as a real schema field replacing the flat `Config.autonomous: bool` (T37-T40 + the migration tool T41); (c) §4 (Privacy) — strengthen the "one-time" clause to make explicit that per-thread cross-domain confirmation is an intentional architectural NO, not an oversight. Per the user's 1.B directive, the spec text grows where the implementation grows — Plan 16 is shipping production features, so the spec must reflect them.

- **Items deliberately landed at full production under 1.B (NOT deferred).** The following items previously appeared in Plan 16 v1's NOT-DOING list as "scaffold-and-defer"; per locked decision 1.B they have been LIFTED into Plan 16 as full production tasks: per-domain budget enforcement (now T26-T29); per-domain rate-limit enforcement (now T30-T32); repair-config UI full surface (now T33); cross-process hot-reload pubsub (now T35 via watchdog + SIGHUP); per-domain autonomy categories (now T37-T40 with full implementation, not just a brainstorm); migration tool for old `config.json` files (now T41 — `brain config migrate` CLI; lifted from NOT-DOING because per-domain autonomy schema migration T38 needs a clean rollover for users on the old flat shape). These are no longer NOT-DOING items.

If any of these come up during implementation, file a TODO in Plan 17 candidate scope and keep moving.

---

## Decisions (locked 2026-05-06)

All decisions locked at plan-author time. **Decisions 1.B / 2.A / 3.A / 4.A locked by user** on the v2 dispatch round; remaining decisions locked by recommendation. Implementers MUST treat these as load-bearing — any deviation requires a new round of plan-author sign-off before changing scope.

### Group I — Scope cut

| # | Decision | Locked | Why |
|---|---|---|---|
| Scope (1.B) | Plan 16 covers all ~50 items from Plan 16 candidate scope as 47 tasks across 10 themes AT FULL PRODUCTION GRADE per user-locked decision 1.B — production correctness (T1), brain_api hardening (T2), Plan 13 architectural follow-throughs (T3-T8), Plan 14 a11y deferrals (T9-T11), CSS structural cleanup (T12-T13), CI follow-throughs (T14-T18), test-quality (T19-T20), Plan 15 review residuals (T21-T25), bigger architectural moves at FULL PRODUCTION (T26-T46 — see Group X for the per-task breakdown), closure (T47). DEFERS: `seedBrainMd`/`seedScope` (rule-of-three not met) + per-thread cross-domain (spec §4 architectural NO; strengthened rationale below). | locked (user, 1.B) | The user explicitly chose 1.B over the recommended 1.A scaffold-and-defer approach. Trade-off accepted: plan size (47 tasks vs the 30-task scaffold variant); discipline that makes it tractable is combined review per task + ~20-LOC PR shape per task. The schema-only SCAFFOLD pattern from Plan 11 (`Config.privacy_railed: list[str]` ship-then-layer) is intentionally NOT used here because the user wants the features working end-to-end. |

### Group II — Production correctness (T1)

| # | Decision | Locked | Why |
|---|---|---|---|
| D1 | `inbox-store.loadRecent` race fix shape: **id-keyed merge that preserves optimistic rows whose id is not in the server response.** Build a server-response-id Set, filter the current store's optimistic rows for ones not in the Set, prepend them to the merged result. Sequence-id check was rejected as more state without a clear win — id is already unique per source ingestion. | locked | "Sequence-id check" was rejected as adding a counter slot that has to stay synchronized across clients/tabs. "Replace store wholesale" is the current bug. The id-merge is surgical (~10 LOC) and matches React/zustand conventions for optimistic UI. Plan 14 Task 6's `waitForResponse` test arm becomes deletable once production is fixed; Task 1 deletes it as part of the same commit (production + test arm coupled). |

### Group III — brain_api hardening (T2)

| # | Decision | Locked | Why |
|---|---|---|---|
| D2 | `_spa_fallback Response | None` mypy fix: `@overload` discriminating on `raise_on_miss: Literal[True]` → `Response`, `raise_on_miss: Literal[False]` → `Response | None`. Single `@overload`-decorated stub pair; runtime body unchanged. | locked | "Skip — mypy ignore" was rejected as deferring the type-safety contract. "Refactor to two functions" was rejected as duplicating the body. `@overload` is the canonical pattern for `bool` discriminator → return type. ~10 LOC; the runtime body stays identical. |

### Group IV — Plan 13 architectural follow-throughs (T3-T8)

| # | Decision | Locked | Why |
|---|---|---|---|
| D3 | Migrate `bulk-screen.tsx` + `file-to-wiki-dialog.tsx` to `useDomains()`: drop direct `listDomains` API import; replace local React state hydrated from `listDomains()` with the `useDomains()` selector. Same shape as Plan 13 Task 2 did for `panel-domains.tsx`. Single PR per file (T3 covers both). | locked | "One file per task" was rejected as task-count bloat for two ~20 LOC migrations. "Skip — Plan 17+" was rejected because Plan 13 Task 2 review M3 said the threshold was met. Mirror migration is mechanical. |
| D4 | `removeDomainOptimistic(slug)` action lands in `domains-store.ts`; `panel-domains.tsx` delete handler calls it BEFORE awaiting the API; `useDomainsStore.error` is rendered as inline banner above the domains list. Two items, one PR (paired naturally — both are the delete-handler UX surface). | locked | "Skip optimistic action" was rejected — Plan 13 Task 2 review I1 explicitly recommended it. "Skip error banner" was rejected — same review recommended surfacing the error state that's already in the store but unrendered. Pairing them in one task is natural because both touch the same delete-handler. |
| D5 | `domainsLoaded` → `loaded` rename (matches `cross-domain-gate-store`'s `loaded` field naming); `cross-domain-gate-store.error` field is **wired** (rendered as inline banner in `panel-domains.tsx` settings tab too). | locked | "Drop the field" was the alternative — but Plan 13 Task 3 review I2 said the field exists for parity with `domains-store.error`; dropping it would re-introduce the asymmetry. Wiring it costs ~5 LOC and gives both stores consistent surface. |
| D6 | BroadcastChannel cross-tab pubsub: lands as a thin module-private layer in BOTH `domains-store.ts` AND `cross-domain-gate-store.ts`. On any `set()` that mutates the store, post to the channel; on inbound message, call `_internalSet()` (which doesn't echo). jsdom-mock for tests. | locked | "Skip — wait until user-visible" was rejected because Plan 13 Task 3 review I3 said the optimistic-clobber race is hypothetical-but-known; landing the pubsub now closes the class. "Single store only" was rejected as inconsistent — both stores have the same race shape. |
| D7 | `setAcknowledgedOptimistic` aligned to early-return pattern (matches `setActiveDomainOptimistic` in `domains-store.ts`). Mechanical refactor; ~5 LOC. | locked | "Skip" was rejected — Plan 13 Task 3 review M1 said the pattern divergence is drift-prone. Trivial fix. |
| D8 | `panel-domains.tsx` 3-file split: `panel-domains.tsx` (orchestrator + list), `panel-domains-row.tsx` (per-row editor), `panel-domains-add.tsx` (add-domain affordance), `panel-domains-active.tsx` (active-domain dropdown). The current file is ~580 LOC; the split lands ~200 LOC + 3 × ~120 LOC. Each child file owns its own props + tests. | locked | "2-file split (row + active)" was rejected as leaving the add-domain affordance under-isolated. "4-file split (orchestrator + row + add + active)" matches Plan 13 Task 3 review M3's recommendation exactly. |

### Group V — Plan 14 a11y deferrals (T9-T11)

| # | Decision | Locked | Why |
|---|---|---|---|
| D9 | Repair-config dialog UI scaffold lands at T9 (minimal dialog with the auto-fallback-chain summary text + a "Run repair" button) sufficient to satisfy the a11y-populated gate. Full polish (Re-run / per-step results panel / Re-apply repaired config flow) lands at T33 per 1.B — under user-locked decision 1.B, the v1 Plan 17+ deferral for full polish is LIFTED into Plan 16 itself. T9 ↔ T33 split is justified because T9 needs to land before Task 11 closes a11y coverage (so a11y-populated extends), and T33 lands after T34 (which provides the `Config.config_version` infrastructure the Re-apply button calls). | locked | "Single-task scaffold-only" was rejected by 1.B. "Single-task full polish" was rejected because the a11y gate at T11 needs the surface to exist before T33 (which depends on T34). Splitting into T9 (scaffold) + T33 (full polish) is the natural sequence. |
| D10 | Autonomy modal scaffold lands at T10 (minimal modal wrapping the existing per-screen Switch toggles + global on/off) sufficient for the a11y-populated gate. Per-domain × per-category full surface lands at T40 (`panel-autonomous.tsx`) per 1.B — under user-locked decision 1.B, the v1 deferral is LIFTED. The T10 modal is a generic wrapper (anywhere-trigger); the T40 panel is the deep-config surface (Settings → Autonomous). They co-exist. | locked | "Single-task scaffold-only" was rejected by 1.B. "Drop the T10 modal entirely (only ship T40)" was rejected because the modal is the trigger surface from anywhere in the app; the panel is the deep-config surface. |
| D11 | a11y-populated additions (T11): 3 new cases in `a11y-populated.spec.ts` — Browse → file-preview overlay (NEW: build the dedicated overlay, not the inline split-pane); WikilinkHover tooltip (`role="tooltip"` axe scan); per-message Fork dialog (different trigger location from chat-sub-header Fork). | locked | "Skip file-preview overlay (use inline split-pane)" was rejected — the inline split-pane has different accessibility semantics; the dedicated overlay is what spec §8 implies. "Skip per-message Fork" was rejected — different trigger location IS a different a11y surface (focus restoration, escape behavior, etc.). |

### Group VI — CSS structural cleanup (T12-T13)

| # | Decision | Locked | Why |
|---|---|---|---|
| D12 | `--tt-cyan-hover` token lands as a theme-aware token in `tokens.css` (light = darker shade of `--tt-cyan`, dark = brighter shade of `--tt-cyan`); `.prose a:hover` routes through it. Audit other `var(--brand-ember)` foreground sites: list at least 4 (link in non-prose contexts, button accents, icon foregrounds, badges); fix any that fail 4.5:1 in either theme by routing through the theme-aware token. | locked | "Hardcoded hex hover" was rejected — Plan 14 lesson C3 closed the parallel case for the base `.prose a` color. "Skip the audit" was rejected — Plan 14 Task 5 review explicitly asked for it. |
| D13 | stylelint `no-hardcoded-hex-outside-root` rule lands; CI fails on hardcoded hex outside `:root` blocks. `.prose` / `.msg-body` / `.turn-body` selector convention doc lands as a comment block at the top of `brand-skin.css`: "Use `.prose` for ingested-content prose; `.msg-body` for chat message bodies; `.turn-body` for full chat-turn wrappers". | locked | "Document only, no stylelint" was rejected — the doc decays without enforcement. "stylelint only" was rejected — the rule is hard to read without the doc explaining the selector taxonomy. Together they're enforcement + onboarding. |

### Group VII — CI follow-throughs (T14-T18)

| # | Decision | Locked | Why |
|---|---|---|---|
| D14 | Workflow caching: `actions/cache@v4` for (a) uv venv + cache dir; (b) pnpm store; (c) Playwright browser binaries. Cache keys keyed on lockfile hashes. Conservative scope — caching is enable/disable, not optimization rework. | locked | "Skip" was rejected — Plan 14 Task 7+8 reviews said cold installs every run is the biggest CI duration cost. "Optimize the workflow shape (parallel jobs)" was rejected as out of scope; caching alone is the load-bearing fix. |
| D15 | Composite action DRY: new `.github/actions/setup-brain-test-env/action.yml` encapsulates uv install + pnpm install + chflags + PYTHONPATH preamble. Mac and Windows steps invoke it. Cross-platform via inputs (`shell`, `pythonpath_separator`). | locked | "Inline duplication" was rejected — Plan 14 Task 8 review explicitly noted the duplication. "Custom GitHub Action (separate repo)" was rejected as over-engineering for a project-private composite. |
| D16 | `gh workflow run --validate` lands as a pre-commit hook (`.pre-commit-config.yaml`) that runs against any modified `.github/workflows/*.yml` file. Same shape pre-commit framework already enforces ruff + prettier on this repo. `pnpm install --frozen-lockfile --filter brain_web...` replaces the workspace-wide install in playwright.yml — Mac and Windows both gain ~30s per run from the narrowed scope. | locked | Pairing T16's two items in one PR is natural — both are workflow-shape gates. |
| D17 | Defender SmartScreen pre-step lands under feature-flag (`env: DEFENDER_DISABLE: ${{ vars.DEFENDER_DISABLE || 'false' }}`); only fires when the workflow var is set. PowerShell line-ending discipline lesson lands in `tasks/lessons.md` Plan 16 section (UTF-8-BOM-on-PS5.1 vs UTF-8-no-BOM-on-pwsh). | locked | "Always disable Defender" was rejected as security-sensitive. "Skip the lesson" was rejected — even if the bug hasn't bit yet (current workflows use pwsh), the discipline is worth capturing for future-Claude. |
| D18 | CI duration observability: each job writes a per-step wall-clock + per-step status table to `$GITHUB_STEP_SUMMARY`. The summary is visible in the run UI without drilling into logs. Mac vs Windows comparison is just adjacent rows in the same workflow run summary. | locked | "Custom dashboard" was rejected as over-engineering. "Log-only" was rejected as not-discoverable. The `$GITHUB_STEP_SUMMARY` writeback is a built-in GitHub Actions feature; no third-party dependency. |

### Group VIII — Test-quality follow-throughs (T19-T20)

| # | Decision | Locked | Why |
|---|---|---|---|
| D19 | `waitForToolResponse(page, toolName)` helper lands in `apps/brain_web/tests/e2e/_helpers.ts`; deterministic wait on the first `/tools/<toolName>` response after the call site. All `waitForTimeout(...)` calls in `a11y-populated.spec.ts` (~11) replaced with deterministic helpers — `waitForToolResponse`, `waitForResponse`, `waitForLoadState`, `expect(...).toBeVisible({ timeout })`, etc. depending on what the beat is actually waiting for. | locked | "Convert one at a time across multiple tasks" was rejected as task-count bloat. "Drop the helper, inline" was rejected as repetitive. The helper is the lesson-343 production-shape replacement. |
| D20 | `test.afterEach` cleanup contract: every state-mutating test in `a11y-populated.spec.ts` (patch-card edit-approve at minimum; rename/delete domain if they leak) has an `afterEach` that reverts the mutation. `text-[var(--bg)]` → `text-[var(--accent-foreground)]` in `patch-card.tsx:117` lands in the same task (semantic-correctness fix; trivial). | locked | "Cleanup contract only" was rejected as task-count optimization — the patch-card token fix is a 1-line change that the cleanup-contract task touches anyway (it's in the same dialog). Pairing them is natural. |

### Group IX — Plan 15 review residuals (T21-T25)

| # | Decision | Locked | Why |
|---|---|---|---|
| D21 | SVG mockup copy update: `state-1-initial.svg` + `state-2-settings-after-toggle.svg` updated to use "Privacy-railed" in place of "private" copy. brain-ui-designer owns the SVG edits (text node replacements; preserve layout + design tokens). | locked | "Document only, don't update SVGs" was rejected — the mockups serve as designer reference + onboarding artifact; copy drift between TSX and SVG is a known onboarding pain. |
| D22 | 3 pre-existing TS errors in `tests/e2e/cross-domain-modal.spec.ts` fixed via `@ts-expect-error` with a comment explaining the intentional shape OR by narrowing the type at the call site (whichever fits each error individually). | locked | "Suppress all 3 with `@ts-ignore`" was rejected — `@ts-expect-error` is preferred (it errors when the suppression becomes unnecessary). "Skip — pre-existing" was rejected because Plan 15 Task 7 review explicitly asked for the sweep. |
| D23 | act() warnings sweep in `chat-screen.test.tsx`: each test that triggers async dispatch wraps the dispatch in `await act(async () => { ... })`. Vitest stderr captured + asserted clean. | locked | "Suppress with vitest config" was rejected — suppression hides the underlying bug class (un-awaited React state updates). "Skip" was rejected — Plan 15 Task 7 review noted the noisy log. |
| D24 | `test_config_get._mk_ctx` Path A alignment (matches Plan 15 Task 9 D8 — required `config: Config`, no `= None` default). All call sites updated. Mirrors the Plan 13 Task 1 None-policy strictness. | locked | "Skip — same shape as the others, just a fixture" was rejected because Plan 15 Task 9 review explicitly recommended the alignment for full consistency. The 4th `_mk_ctx` variant is the only outlier post-Plan 15. |
| D25 | Three trivially-small Plan 15 review residuals grouped in one PR: (a) toast lead/msg period normalization in `panel-domains.tsx`'s active-domain toast; (b) Plan 07 Task 5 forward-looking deferrals dropped from `config_set.py:81/90` + `schema.py:101` (mirrors Plan 15 Task 10 docstring cleanup); (c) positive unit test for `PrivacyRailedGlossaryTooltip` (Plan 15 Task 5 review). Each ~5 LOC; one PR. | locked | "Three separate tasks" was rejected as task-count bloat for ~15 LOC total. "Drop one of the three" was rejected — each is named explicitly in Plan 16 candidate scope. Pairing is natural; they're all "tiny clean-up" shape. |

### Group X — Bigger architectural moves at FULL PRODUCTION (T26-T46) — locked 1.B

| # | Decision | Locked | Why |
|---|---|---|---|
| D26 | **Per-domain budget caps — full production** (T26-T29; 4 tasks): T26 schema (`Config.budget.per_domain: dict[str, BudgetOverride]` with `monthly_cap_usd: float \| None` + `daily_cap_usd: float \| None`; Pydantic v2 + tests). T27 cost-ledger migration (verify `costs.sqlite` `domain` column already exists per spec; per-domain rollup queries land in `cost_report.py`; tests). T28 BudgetGuard per-call enforcement (`BudgetGuard` reads per-domain caps; raises `BudgetCapExceeded` BEFORE the LLM call when domain-specific cap exceeded; threading via `ctx.config` + `ctx.domain`; pin tests for both daily + monthly windows). T29 UI surface (`panel-domains-row.tsx` per-row gets "Daily cap" + "Monthly cap" optional inputs; persists via `setDomainBudget` API call). Spec footnote in §6 (Cost). | locked (user, 1.B) | Per 1.B "full production": ship the feature working end-to-end. T27's cost-ledger migration leverages the existing `domain` column (no new migration; verify only). The 4-task decomposition is dictated by D33's ~20-LOC PR-shape rule — schema + migration + enforcement + UI are each ~20 LOC. |
| D27 | **Per-domain rate limits — full production** (T30-T32; 3 tasks): T30 schema (`Config.providers[provider].rate_limit_per_domain: dict[str, RateLimitOverride]` with `requests_per_minute: int \| None`; Pydantic + tests). T31 AnthropicProvider enforcement (provider-client reads per-domain rate-limit cap; uses **leaky-bucket semantics** — locked by recommendation: queues briefly when overflow is mild, raises `RateLimitExceeded` when queue depth exceeds `requests_per_minute * 2`; freezegun-driven tests). T32 UI surface (`panel-domains-row.tsx` rate-limit input — extends T29's row component; persists via `setDomainRateLimit` API). Spec footnote in §6 (Cost) — combined with D26's footnote. | locked (user, 1.B; leaky-bucket recommendation locked) | Per 1.B "full production". Leaky-bucket recommendation locked over sliding-window because (a) leaky-bucket queues smooth bursty traffic, (b) sliding-window is harder to reason about correctness for, (c) Anthropic's own rate limiter is documented as bucket-shaped. Implementer routes back if leaky-bucket is the wrong fit at implementation time. |
| D28 | **Repair-config UI + cross-process hot-reload — full production** (T33-T35; 3 tasks): T33 repair-config dialog full polish (Re-run button + per-step results panel + Re-apply repaired config flow; replaces v1 D9's SCAFFOLD wording — D9 is now scaffold-at-T9, full polish at T33). T34 `Config.config_version: int` field (default 0; increment in `save_config` on every write; `_resolve_config` reads version + re-loads on mismatch — single-process invalidation; pin tests). T35 cross-process hot-reload (`watchdog` Python file-watcher on `<vault>/.brain/config.json`; on change event, brain_api emits SIGHUP signal to brain_mcp subprocess; brain_mcp's signal handler triggers config re-load; `pytest-asyncio` + `freezegun` tests; new `watchdog` dev-dep). Spec footnote in §6 reflects hot-reload semantics. | locked (user, 1.B) | Per 1.B "full production": v1 deferred cross-process pubsub to Plan 17+; lifted into Plan 16. SIGHUP is the canonical UNIX signal-based IPC; on Windows we use `signal.SIGTERM` + a marker file fallback (Python's `signal.SIGHUP` doesn't exist on Windows — implementer routes back if a cleaner abstraction is needed). |
| D29 | **`validate_assignment=True` perf-measure + ENABLE ALWAYS** (T36; 1 task): per locked decision 3.A (with 1.B amendment): implementer measures `Config()` instantiation + assignment-heavy round-trip (1000 random field assignments) with and without `validate_assignment=True`. **Regardless of measurement outcome, the flag is set unconditionally** (`Config.model_config = ConfigDict(validate_assignment=True)`). Measurement is to surface the perf cost, not gate the rollout. KNOWN-LIMITATION pin test (`test_invalid_value_currently_persists_without_validation`) is UPDATED to assert the new validation behavior (no longer KNOWN-LIMITATION). Perf-measure outcome documented in `tasks/lessons.md` Plan 16 section regardless of overhead — if overhead ≥ 10%, lessons.md captures the perf-impact note (this is a divergence from v1's "defer if > 10%" wording — under 1.B, full production lands regardless). | locked (user, 3.A + 1.B amendment) | The user explicitly chose 3.A and 1.B together. Per 1.B, deferring on a perf measurement isn't an option for Plan 16; the measurement is informational. Plan 11 Task 4's KNOWN-LIMITATION pin test is the artifact that becomes a positive validation test. |
| D30 | **Per-domain autonomy categories — full production** (T37-T40; 4 tasks): T37 brainstorm + lock task (produces "Task 37 findings" subsection in this plan file with locked schema shape: `Config.autonomous: dict[str, dict[Literal["new_files","edits","index_entries","concepts","draft"], bool]]`). T38 schema migration (Pydantic field shape changes from flat `Config.autonomous: AutonomousConfig` to nested per-domain × per-category; **read-time backwards-compat migration** for old config.json files (one-time in-place transformation: flat `autonomous: true` becomes `{"<all-domains>": {"new_files": true, "edits": true, "index_entries": true, "concepts": true, "draft": true}}`). T39 AutonomyGate enforcement (`AutonomyGate` reads per-domain category; `apply_patch._resolve_config` threads `ctx.domain`; pin tests cover edits-only domain + new-files-gated domain). T40 UI surface (Settings → Autonomous → `panel-autonomous.tsx` per-domain × per-category grid; tests). | locked (user, 1.B) | Per 1.B "full production": v1 deferred everything past the brainstorm to Plan 17+; lifted to T37-T40. The schema migration in T38 is **in-place at read time**, distinct from T41's `brain config migrate` CLI which is a one-shot user-runnable tool. Both land — T38's read-time migration handles silent rollover; T41's CLI gives users an explicit migration with backup. |
| D31 | **`brain config migrate` CLI tool** (T41; 1 task): lifted from v1 NOT-DOING per 1.B. CLI subcommand `brain config migrate <path>` reads an old-shape config.json + rewrites in the new shape; original file backed up to `config.json.pre-migrate.bak`; idempotent (re-runs are no-ops). Subprocess test coverage. | locked (user, 1.B; lift from NOT-DOING) | Per 1.B's "full production" + the per-domain autonomy schema migration in T38, users on the old `Config.autonomous: bool` shape need a clean rollover path; while T38's read-time migration handles silent rollover, the explicit CLI tool gives users (a) a backup file, (b) a deterministic point-in-time when the migration happened, (c) a hook for future schema evolution. v1 deferred; v2 lifts. |
| D32 | **Trio of architectural moves at FULL implementation** (T42-T44; 3 tasks; v1 was T31 "scaffold-only"): T42 "Set as default" topbar button (full impl — button on topbar scope picker calling existing `setActiveDomain`; toast on success; ~10 LOC + unit test). T43 generic zustand promotion (`useBudget` → `budget-store.ts` + `useDomainOverrides` → `domain-overrides-store.ts`; mirror Plan 12's `useDomains` + Plan 13's `useCrossDomainGate` patterns; consumers updated). T44 `pendingSendRef`-as-local audit + APPLY (audit `chat-screen.tsx` + neighboring handlers; APPLY the capture-into-local pattern wherever the ref-spans-await anti-pattern is found — NOT just file an audit doc per v1; findings appended to plan file). | locked (user, 1.B) | Per 1.B: each item lands at full implementation, not as a scaffold-with-deferred-polish. T42 is trivially small (~10 LOC). T43 mirrors existing zustand-promotion shape. T44 was previously "audit-only with no implementation" in v1; under 1.B the audit IS followed by the apply step. |
| D33 | **`ctx.config` lint rule via Ruff custom rule, locked** (T45-T46; 2 tasks): per locked decision 4.A (recommendation): T45 ruff custom rule plumbing (implement `BRN001` "ctx.config read outside allowed entry-points" via ruff's plugin API; allowed entry-points list lives in `pyproject.toml` `[tool.ruff.lint.brain]` section; tests with sample violations). T46 violation cleanup (run the rule across the codebase; fix all violations OR add `# noqa: BRN001` with rationale comment; CI step gates `ruff check . --select BRN001`). The mypy-plugin alternative is dropped — ruff is the locked tool. Rule name `BRN001` locked (BRN namespace = brain custom rules). | locked (user, 4.A) | The user explicitly chose 4.A. Ruff's plugin API is more mature than mypy's for project-local rules; ruff already runs in pre-commit + CI. `BRN001` namespace reserves the future for additional brain-specific rules (`BRN002`, etc.). |

### Group XI — Plan shape (T47)

| # | Decision | Locked | Why |
|---|---|---|---|
| D34 | Plan 16 task count: **47 tasks** + closure (T47). v2 expansion: v1 was 30 tasks + closure; under 1.B, Theme 10 expanded from 7 SCAFFOLD tasks to 21 production tasks (+14 net), and the `brain config migrate` CLI lifted from NOT-DOING (+1 net). Net: 30 + 14 + 1 + closure renumber = 47 tasks + T47 closure. Mirrors Plan 14 (9 tasks) + Plan 15 (11 tasks) cadence at the polish-heavy upper end multiplied by carry-forward scope multiplied by 1.B's full-production multiplier. Each task narrowly scoped (~20 LOC PR shape; tasks exceeding ~20 LOC at implementation time MUST split rather than expand). Combined spec-and-code-quality review per task per Plan 15 lesson. NO `gh workflow run --validate` step lifted into pre-commit until Task 16 lands (otherwise it would block Tasks 1-15 dispatch). | locked | "Stay at 30 tasks (1.A scaffold-and-defer)" was rejected by user-locked 1.B. "Pair Theme 10 tasks more aggressively (~40 tasks)" was rejected because schema + migration + enforcement + UI each warrant their own review surface; pairing them muddies attribution. |
| D35 | Demo gate composition: **47 gates**. One assertion per substantive task + sentinel. Mirrors Plan 15's per-item gate shape. v2 grows from v1's 33 to 47 along with task count. | locked | "Collapse to ~25 gates" was rejected — less granular failure signal makes Theme 10's per-domain schema/enforcement/UI debugging painful. "More than 50 gates" was rejected — diminishing returns vs gate-runtime cost; the 1:1 task-to-gate ratio is right. |
| D36 | Sequential per-task dispatch via `superpowers:subagent-driven-development`. Combined spec-and-code-quality review per task (no separate spec-pass + code-pass). NO parallelization. **Spec text touched: THREE footnotes** — (a) §6 (Cost) for T26-T29 + T30-T32 (per-domain budget + rate-limit caps full production); (b) §3 (Vault) for T37-T41 (per-domain autonomy categories full implementation + migration tool); (c) §4 (Privacy) strengthening the "one-time" clause to make explicit that per-thread cross-domain confirmation is an intentional architectural NO (not an oversight). All other tasks NO spec text changes. Owners as listed in "Owning subagents" above. | locked | "Two-stage review per task" was rejected — combined review caught all M-class issues in Plan 15's 11 tasks at < 50 LOC scope; Plan 16's 47 tasks are even smaller per-task. "Parallel where dep graph allows" was rejected for review-discipline reasons. "One spec footnote (v1)" was rejected because under 1.B, the spec text grows where the implementation grows: Theme 10 ships three substantive feature areas → three footnotes. |

The implementer routes any unrecognized rule edge case (D1 alternative race-fix shape, D6 BroadcastChannel polyfill quirks, D26 budget-cap edge cases like multi-domain ctx, D27 leaky-bucket vs sliding-window choice, D28 SIGHUP-on-Windows fallback, D29 perf-measure ≥ 10% lessons-doc shape, D30 autonomy schema field naming, D33 BRN001 ruff plugin shape) back to the plan author for re-sign-off before changing scope.

---

## File structure produced by this plan

```
packages/brain_core/
├── src/brain_core/
│   ├── config/
│   │   ├── schema.py                       # MODIFY: drop Plan 07 Task 5 forward-looking comment at line 101 (D25); add Config.config_version field (T34); add Config.budget.per_domain field (T26); add Config.providers[*].rate_limit_per_domain field (T30); per-domain autonomy schema reshape (T38); validate_assignment=True (T36)
│   │   ├── loader.py                       # MODIFY: _resolve_config reads config_version, re-loads on mismatch (T34); read-time backwards-compat migration for old autonomous shape (T38)
│   │   └── hot_reload.py                   # NEW: watchdog file-watcher + cross-process notifier per T35
│   ├── budget/
│   │   ├── per_domain_guard.py             # NEW: BudgetGuard reads per-domain caps, raises BudgetCapExceeded (T28)
│   │   └── cost_report.py                  # MODIFY: per-domain rollup queries (T27)
│   ├── llm/providers/
│   │   └── anthropic.py                    # MODIFY: per-domain leaky-bucket rate-limit enforcement (T31)
│   ├── autonomy/
│   │   └── gate.py                         # MODIFY: AutonomyGate reads per-domain category (T39)
│   ├── tools/
│   │   ├── config_set.py                   # MODIFY: drop Plan 07 Task 5 forward-looking comment at lines 81+90 (D25); + setDomainBudget + setDomainRateLimit + setDomainAutonomy keys (T26+T30+T38)
│   │   └── apply_patch.py                  # MODIFY: thread ctx.domain into AutonomyGate (T39)
│   └── cli/
│       └── migrate.py                      # NEW: `brain config migrate` subcommand (T41)
└── tests/
    ├── tools/
    │   └── test_config_get.py              # MODIFY: _mk_ctx requires config (D24)
    ├── config/
    │   ├── test_schema_per_domain_budget.py        # NEW: schema round-trip pin (T26)
    │   ├── test_schema_per_domain_rate_limit.py    # NEW: schema round-trip pin (T30)
    │   ├── test_config_version_field.py            # NEW: version-bump + reload pin (T34)
    │   ├── test_hot_reload.py                      # NEW: pytest-asyncio cross-process pin (T35)
    │   ├── test_validate_assignment_perf.py        # NEW: perf-measure for T36 (lessons.md captures outcome regardless)
    │   ├── test_validate_assignment_enforcement.py # NEW: validation enforcement pin (T36, replaces KNOWN-LIMITATION)
    │   ├── test_autonomy_schema_migration.py       # NEW: read-time backwards-compat pin (T38)
    │   └── test_config_migrate_cli.py              # NEW: subprocess test for `brain config migrate` (T41)
    ├── budget/
    │   ├── test_per_domain_guard.py        # NEW: BudgetGuard daily + monthly cap pin (T28)
    │   └── test_cost_report_rollup.py      # NEW: per-domain rollup queries (T27)
    ├── llm/
    │   └── test_anthropic_rate_limit.py    # NEW: freezegun leaky-bucket pin (T31)
    ├── autonomy/
    │   └── test_gate_per_domain.py         # NEW: AutonomyGate per-domain enforcement pin (T39)
    └── linting/
        └── test_brn001_lint_rule.py        # NEW: BRN001 ruff custom rule contract test (T45)

packages/brain_api/
└── src/brain_api/
    ├── static_ui.py                        # MODIFY: _spa_fallback @overload on raise_on_miss (D2)
    └── routes/
        └── config.py                       # MODIFY: setDomainBudget + setDomainRateLimit + setDomainAutonomy endpoints (T26+T30+T38)

packages/brain_mcp/
└── src/brain_mcp/
    └── server.py                           # MODIFY: SIGHUP handler triggers config re-load (T35)

apps/brain_web/
├── src/components/
│   ├── settings/
│   │   ├── panel-domains.tsx               # MODIFY: use removeDomainOptimistic + render error banner (D4); 3-file split per D8; toast period + CTA copy normalization (D25)
│   │   ├── panel-domains-row.tsx           # NEW: per-row editor (D8); + Daily cap + Monthly cap inputs (T29); + rate-limit input (T32)
│   │   ├── panel-domains-add.tsx           # NEW: add-domain affordance (D8)
│   │   ├── panel-domains-active.tsx        # NEW: active-domain dropdown (D8)
│   │   └── panel-autonomous.tsx            # NEW: per-domain × per-category grid for autonomy (T40)
│   ├── bulk/
│   │   └── bulk-screen.tsx                 # MODIFY: useDomains() (D3)
│   ├── dialogs/
│   │   ├── file-to-wiki-dialog.tsx         # MODIFY: useDomains() (D3)
│   │   ├── repair-config-dialog.tsx        # NEW: scaffold per D9 (T9); full polish — Re-run + per-step results + Re-apply (T33)
│   │   ├── autonomy-modal.tsx              # NEW: scaffold per D10 (T10)
│   │   └── file-preview-overlay.tsx        # NEW: dedicated overlay per D11 (T11)
│   ├── chat/
│   │   ├── chat-screen.tsx                 # MODIFY: per-message Fork dialog wired (T11); pendingSendRef-as-local apply (T44)
│   │   └── wikilink-hover.tsx              # MODIFY: a11y tooltip role + scan (T11)
│   └── topbar/
│       └── scope-picker.tsx                # MODIFY: "Set as default" button — full impl per D32 (T42)
├── src/lib/state/
│   ├── domains-store.ts                    # MODIFY: add removeDomainOptimistic (D4); domainsLoaded → loaded rename (D5); BroadcastChannel pubsub (D6)
│   ├── cross-domain-gate-store.ts          # MODIFY: wire error field (D5); BroadcastChannel pubsub (D6); setAcknowledgedOptimistic early-return (D7)
│   ├── budget-store.ts                     # NEW: zustand promotion of useBudget per D32 (T43)
│   └── domain-overrides-store.ts           # NEW: zustand promotion of useDomainOverrides per D32 (T43)
├── src/lib/state/inbox-store.ts            # MODIFY: loadRecent id-keyed merge (D1)
├── tests/e2e/
│   ├── _helpers.ts                         # MODIFY: + waitForToolResponse helper (D19)
│   ├── a11y-populated.spec.ts              # MODIFY: 3 new cases (T11); waitForTimeout removal (T19); test.afterEach cleanup (T20); + repair-config full surface case (T33); + autonomy panel case (T40)
│   └── cross-domain-modal.spec.ts          # MODIFY: 3 TS errors fixed (D22)
└── tests/unit/
    ├── inbox-store-loadRecent.test.ts             # NEW: race-fix pin (T1)
    ├── domains-store-removeOptimistic.test.ts     # NEW: pin (T4)
    ├── domains-store-broadcast.test.ts            # NEW: cross-tab pubsub pin (T6)
    ├── cross-domain-gate-store-broadcast.test.ts  # NEW: pin (T6)
    ├── panel-domains-row.test.tsx                 # NEW: split component pin + budget caps + rate limit (T8 + T29 + T32)
    ├── panel-autonomous.test.tsx                  # NEW: per-domain × per-category grid pin (T40)
    ├── repair-config-dialog.test.tsx              # NEW: scaffold pin (T9); full surface pin (T33)
    ├── autonomy-modal.test.tsx                    # NEW: scaffold pin (T10)
    ├── privacy-railed-glossary-tooltip.test.tsx   # NEW: positive unit test (T25)
    ├── scope-picker-set-as-default.test.tsx       # NEW: button + toast pin (T42)
    ├── budget-store.test.ts                       # NEW: zustand promotion pin (T43)
    ├── domain-overrides-store.test.ts             # NEW: zustand promotion pin (T43)
    └── chat-screen.test.tsx                       # MODIFY: act() warnings cleared (T23); pendingSendRef capture-into-local apply (T44)

packages/brain_cli/
└── src/brain_cli/commands/
    └── config.py                           # MODIFY: + `migrate` subcommand wires to brain_core.cli.migrate (T41)

apps/brain_web/src/styles/
├── tokens.css                              # MODIFY: add --tt-cyan-hover token (D12)
└── brand-skin.css                          # MODIFY: .prose / .msg-body / .turn-body convention comment block (D13); .prose a:hover routes through --tt-cyan-hover (D12)

apps/brain_web/.stylelintrc.json            # NEW: stylelint config with no-hardcoded-hex-outside-root (D13)

pyproject.toml                              # MODIFY: + [tool.ruff.lint.brain] allowed-entry-points list (T45); BRN001 plugin entry registered

.github/
├── actions/
│   └── setup-brain-test-env/
│       └── action.yml                      # NEW: composite action DRY (D15)
├── workflows/
│   ├── ci.yml                              # MODIFY: caching (D14); composite action (D15); summary writeback (D18); + ruff BRN001 lint step (T46)
│   └── playwright.yml                      # MODIFY: caching (D14); composite action (D15); pnpm install --filter (D16); SmartScreen pre-step (D17); summary writeback (D18)
└── pre-commit-config.yaml (or .pre-commit-config.yaml)
                                            # MODIFY: + gh workflow run --validate hook (D16); + ruff BRN001 hook (T46)

docs/design/
├── cross-domain-modal/
│   ├── state-1-initial.svg                 # MODIFY: "private" → "Privacy-railed" (D21)
│   ├── state-2-settings-after-toggle.svg   # MODIFY: "private" → "Privacy-railed" (D21)
│   └── microcopy.md                        # MODIFY: align to current TSX surfaces (D21)
└── (other design files unchanged)

docs/superpowers/specs/
└── 2026-04-13-cj-llm-kb-design.md          # MODIFY: §6 (Cost) footnote noting per-domain budget + rate-limit full implementation (T26-T29 + T30-T32); §3 (Vault) footnote noting per-domain autonomy categories full implementation (T37-T41); §4 (Privacy) clause strengthening for per-thread cross-domain confirmation (architectural NO)

scripts/
└── demo-plan-16.py                         # NEW: 47-gate demo per D35

tasks/
├── plans/
│   └── 16-comprehensive-carry-forward.md   # this file
├── lessons.md                              # MODIFY: + Plan 16 closure section (12+ lessons captured)
└── todo.md                                 # MODIFY: row 16 → ✅ Complete; remove Plan 16 candidate-scope; add Plan 17 candidate-scope (residuals only — no full-feature carry-forwards remain since 1.B landed everything)
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
11. **Browser-in-the-loop verification** for any UI-touching task (Tasks 1, 3-13, 21, 23, 25, 29, 32, 33, 40, 42, 43, 44): start brain, take screenshots pre and post change, attach to per-task review.
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

**Goal:** Per D9, minimal dialog scaffold that satisfies the a11y-populated.spec.ts gate. Full polish lands at Task 33 (which calls into Task 34's `Config.config_version` infrastructure).

**What to do:**
1. **Dialog component.** `<RepairConfigDialog isOpen onClose>` — radix-ui Dialog primitive (matches existing dialog conventions). Title: "Repair config". Body: short description of the auto-fallback chain ("If your config.json is corrupted, brain falls back to .bak then defaults"). Single "Run repair" button (calls a stub `repairConfig()` action that re-loads — full implementation in Task 33).
2. **brain-ui-designer copy.** Microcopy verbatim ("Repair config", "Run repair", description) lands as a designer artifact.
3. **a11y case.** New `a11y-populated.spec.ts` case opens the dialog from Settings → General; axe-core scan; 0 violations.

**Per-task review:** scaffold satisfies the a11y gate; full polish is Task 33. Per-task self-review checklist.

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

**Per-task review:** scaffold-only; per-domain category schema lands at Task 38 (after Task 37's brainstorm-and-lock); the deep-config UI panel at Task 40 (`panel-autonomous.tsx`). Per-task self-review checklist.

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

## Task 26 — Per-domain budget caps schema (full production T26-T29 / 1.B)

**Files:**
- Modify: `packages/brain_core/src/brain_core/config/schema.py` (add `Config.budget.per_domain` field)
- Create: `packages/brain_core/tests/config/test_schema_per_domain_budget.py`

**Goal:** Per D26 step 1 of 4: schema lands. Field exists, round-trips. No enforcement yet (T28 lands enforcement; T29 lands UI).

**What to do:**
1. **Schema.** `BudgetConfig` model gets `per_domain: dict[str, BudgetOverride]` field. New `BudgetOverride` model: `monthly_cap_usd: float | None = None`, `daily_cap_usd: float | None = None`. Pydantic v2; default `{}`.
2. **Pin test.** Round-trip: write a Config with `per_domain={"research": BudgetOverride(monthly_cap_usd=10.0, daily_cap_usd=1.0)}`; serialize to JSON; re-read; assert equality.
3. **Validation.** `monthly_cap_usd` and `daily_cap_usd` both must be > 0 if set; both can be None (meaning "no cap"); validator rejects negative or zero values.

**Per-task review:** schema test + Pydantic v2 validator coverage. Per-task self-review checklist.

---

## Task 27 — Cost-ledger per-domain rollups (full production T26-T29 / 1.B)

**Files:**
- Verify: `packages/brain_core/src/brain_core/cost/schema.py` (`costs.sqlite` `domain` column already exists per spec)
- Modify: `packages/brain_core/src/brain_core/cost/cost_report.py` (add per-domain rollup query)
- Create: `packages/brain_core/tests/budget/test_cost_report_rollup.py`

**Goal:** Per D26 step 2 of 4: surface per-domain spend totals. Spec specifies the `domain` column on `costs.sqlite` already exists; verify and add the rollup queries.

**What to do:**
1. **Verify schema.** `cost/schema.py`: confirm `domain TEXT` column on `cost_entry` table. If not, ADD it (defensible migration since this is a derived cache per spec — `vault is source of truth, SQLite is a cache`).
2. **Rollup query.** `cost_report.py`: new function `domain_spend_within_window(domain: str, since: datetime) -> Decimal` returns total cost in window for given domain. Same shape as existing total-spend rollup.
3. **Pin test.** Seed ledger with 3 entries across 2 domains; assert rollup returns correct sum per domain.

**Per-task review:** `pytest packages/brain_core/tests/budget/test_cost_report_rollup.py -q` green. Per-task self-review checklist.

---

## Task 28 — BudgetGuard per-domain enforcement (full production T26-T29 / 1.B)

**Files:**
- Create: `packages/brain_core/src/brain_core/budget/per_domain_guard.py`
- Modify: `packages/brain_core/src/brain_core/llm/budget_guard.py` (or wherever the existing top-level guard lives — verify path at implementation time)
- Modify: any LLM call site that currently invokes the budget guard (thread `ctx.domain` through)
- Create: `packages/brain_core/tests/budget/test_per_domain_guard.py`

**Goal:** Per D26 step 3 of 4: enforce per-domain caps per-call. `BudgetGuard.check(ctx)` reads `ctx.config.budget.per_domain[ctx.domain]`; raises `BudgetCapExceeded` BEFORE the LLM call when daily or monthly cap is exceeded.

**What to do:**
1. **Per-domain guard.** New `PerDomainBudgetGuard.check(ctx: ToolContext) -> None`. Reads `ctx.config.budget.per_domain.get(ctx.domain)`; if no override or both caps None, no-op. Otherwise, queries `cost_report.domain_spend_within_window` for the daily and monthly windows; if either spent ≥ cap, raise `BudgetCapExceeded("domain={...}, window={daily|monthly}, spent={...}, cap={...}")`.
2. **Wire in.** Existing top-level `BudgetGuard.check` chains to `PerDomainBudgetGuard.check` after its own check passes. Threading: the LLM-call entry point (look at `chat.py` + `apply_patch.py`) already builds `ctx`; ensure `ctx.domain` is set.
3. **Pin tests.** `test_per_domain_guard.py`: (a) no override → no-op; (b) only daily set, under cap → no-op; (c) daily exceeded → raises; (d) only monthly set, under cap → no-op; (e) monthly exceeded → raises; (f) both set, only one exceeded → raises with correct window in message.

**Per-task review:** all 6 pin-test cases pass. Per-task self-review checklist. Browser verification: set a $1 daily cap on a test domain; chat 10 turns; verify the cap kicks in.

---

## Task 29 — Per-domain budget UI in panel-domains-row (full production T26-T29 / 1.B)

**Files:**
- Modify: `apps/brain_web/src/components/settings/panel-domains-row.tsx` (per Task 8 split — extends with budget cap inputs)
- Modify: `apps/brain_web/src/lib/api/tools.ts` (add `setDomainBudget` API call)
- Modify: `packages/brain_api/src/brain_api/routes/config.py` (add `setDomainBudget` endpoint)
- Modify: `apps/brain_web/tests/unit/panel-domains-row.test.tsx` (extend with budget cap test cases)

**Goal:** Per D26 step 4 of 4: UI surface lets users set per-domain budget caps via Settings → Domains.

**What to do:**
1. **UI.** `panel-domains-row.tsx`: add a "Budget caps" subsection with 2 optional `<input type="number" min="0" step="0.01">` for "Daily cap (USD)" and "Monthly cap (USD)". Empty inputs = `None`. Live-validation: must be > 0 if set.
2. **API call.** `tools.ts`: `setDomainBudget(slug: string, cap: BudgetOverride): Promise<void>`.
3. **API endpoint.** `routes/config.py`: POST `/tools/setDomainBudget` calls `config_set` with key `budget.per_domain.<slug>`.
4. **Persistence.** On blur, save to backend. Toast on success ("Budget caps saved for {domain}.").
5. **Test.** Extend `panel-domains-row.test.tsx`: render with no caps → both inputs empty; type "10" in monthly → mutation triggers `setDomainBudget`; assert payload shape matches schema.

**Per-task review:** vitest + browser verification. Per-task self-review checklist.

---

## Task 30 — Per-domain rate limits schema (full production T30-T32 / 1.B)

**Files:**
- Modify: `packages/brain_core/src/brain_core/config/schema.py` (add `Config.providers[*].rate_limit_per_domain`)
- Create: `packages/brain_core/tests/config/test_schema_per_domain_rate_limit.py`

**Goal:** Per D27 step 1 of 3: schema lands. Field exists, round-trips. No enforcement yet (T31 lands enforcement; T32 lands UI).

**What to do:**
1. **Schema.** `ProviderConfig` (per-provider config under `Config.providers["anthropic"]` etc.) gets `rate_limit_per_domain: dict[str, RateLimitOverride]` field. New `RateLimitOverride` model: `requests_per_minute: int | None = None`. Pydantic v2; default `{}`.
2. **Pin test.** Round-trip with `rate_limit_per_domain={"research": RateLimitOverride(requests_per_minute=60)}`.
3. **Validation.** `requests_per_minute` must be > 0 if set; reject negative or zero.

**Per-task review:** Per-task self-review checklist.

---

## Task 31 — AnthropicProvider per-domain rate-limit enforcement (leaky-bucket; full production T30-T32 / 1.B)

**Files:**
- Modify: `packages/brain_core/src/brain_core/llm/providers/anthropic.py`
- Create: `packages/brain_core/tests/llm/test_anthropic_rate_limit.py`

**Goal:** Per D27 step 2 of 3: AnthropicProvider reads per-domain rate limit; enforces via leaky-bucket semantics (queue brief overflow; raise on excessive overflow).

**What to do:**
1. **Leaky-bucket state.** Module-private `_per_domain_buckets: dict[str, LeakyBucket]`. New `LeakyBucket(rpm: int)` class: tracks tokens replenished at `rpm/60` per second, capacity = `rpm`; `acquire()` blocks (asyncio sleep) up to `bucket_size_seconds` or raises `RateLimitExceeded` if queue depth > `rpm * 2`.
2. **Wire into call.** Before the actual `client.messages.create(...)` call: read `config.providers["anthropic"].rate_limit_per_domain.get(ctx.domain)`; if no override or `requests_per_minute` is None, bypass. Otherwise, await `_get_bucket(ctx.domain, rpm).acquire()`.
3. **Pin tests with freezegun.** (a) `rpm=2`, send 2 calls within same minute → both pass; (b) 3rd call within window queues briefly; (c) overflow beyond `rpm * 2` raises `RateLimitExceeded`; (d) advance clock by 1 minute → bucket replenishes; (e) different domain has independent bucket.

**Per-task review:** `pytest packages/brain_core/tests/llm/test_anthropic_rate_limit.py -q` green. Per-task self-review checklist.

---

## Task 32 — Per-domain rate-limit UI in panel-domains-row (full production T30-T32 / 1.B)

**Files:**
- Modify: `apps/brain_web/src/components/settings/panel-domains-row.tsx` (extends T29's row component)
- Modify: `apps/brain_web/src/lib/api/tools.ts` (add `setDomainRateLimit` API call)
- Modify: `packages/brain_api/src/brain_api/routes/config.py` (add `setDomainRateLimit` endpoint)
- Modify: `apps/brain_web/tests/unit/panel-domains-row.test.tsx` (extend with rate-limit cases)

**Goal:** Per D27 step 3 of 3: UI surface for per-domain rate-limit setting.

**What to do:**
1. **UI.** `panel-domains-row.tsx`: add "Rate limit" subsection with one optional `<input type="number" min="1">` for "Requests per minute". Empty = `None`. Live-validation: must be > 0 if set.
2. **API call.** `setDomainRateLimit(slug, override)`.
3. **API endpoint.** `routes/config.py`: POST `/tools/setDomainRateLimit`.
4. **Test.** Extend `panel-domains-row.test.tsx` with rate-limit case.

**Per-task review:** vitest + browser verification. Per-task self-review checklist.

---

## Task 33 — Repair-config dialog full polish (full production T33-T35 / 1.B)

**Files:**
- Modify: `apps/brain_web/src/components/dialogs/repair-config-dialog.tsx` (full polish beyond T9 scaffold)
- Modify: `apps/brain_web/src/lib/api/tools.ts` (add `repairConfig` API call returning per-step results)
- Modify: `apps/brain_api/src/brain_api/routes/config.py` (add `repairConfig` endpoint that runs the loader chain + returns per-step results)
- Modify: `apps/brain_web/tests/unit/repair-config-dialog.test.tsx` (extend with full-surface assertions)
- Modify: `apps/brain_web/tests/e2e/a11y-populated.spec.ts` (full surface case)

**Goal:** Per D28 step 1 of 3: T9 landed the scaffold; T33 lands the full polish — Re-run / per-step results panel / Re-apply repaired config flow.

**What to do:**
1. **Re-run button.** Triggers `repairConfig()` API call. Spinner during the run.
2. **Per-step results panel.** Each step in the loader chain (`config.json read` → `validate` → `.bak fallback if invalid` → `defaults fallback if .bak invalid`) renders as a row with status (success/warning/error) + a one-line description. Mirrors `brain doctor` output shape.
3. **Re-apply button.** If the repaired config differs from the in-memory copy, "Re-apply" writes the repaired config to disk via `save_config`. Disabled if no diff.
4. **a11y.** Full keyboard navigation: Tab order through Re-run → results → Re-apply. Escape closes. axe-core: 0 violations on populated state.

**Per-task review:** vitest + a11y case + browser verification. Per-task self-review checklist.

---

## Task 34 — Config.config_version field + single-process invalidation (full production T33-T35 / 1.B)

**Files:**
- Modify: `packages/brain_core/src/brain_core/config/schema.py` (`Config.config_version: int`)
- Modify: `packages/brain_core/src/brain_core/config/loader.py` (`save_config` increments; `_resolve_config` reads version + re-loads on mismatch)
- Create: `packages/brain_core/tests/config/test_config_version_field.py`

**Goal:** Per D28 step 2 of 3: Config gains a version field; single-process loader invalidates its in-memory cache when version changes.

**What to do:**
1. **`config_version` field.** Default `0`. Increment in `save_config` on every write (atomic + locked + backup chain stays the same).
2. **Loader invalidation.** `_resolve_config` (or whichever loader is the single-process cache layer): keep an in-memory `_cached_config: Config | None`; on each request, stat the file's `config_version` (parse JSON head only — don't re-read whole file unless mismatch); if mismatch or no cache, full re-load.
3. **Pin tests.** (a) `save_config` increments version; (b) `_resolve_config` returns cached object on consecutive calls when no save in between (object identity); (c) after `save_config`, next `_resolve_config` returns new object.

**Per-task review:** Per-task self-review checklist.

---

## Task 35 — Cross-process hot-reload via watchdog + SIGHUP (full production T33-T35 / 1.B)

**Files:**
- Create: `packages/brain_core/src/brain_core/config/hot_reload.py` (watchdog file-watcher + cross-process notifier)
- Modify: `packages/brain_mcp/src/brain_mcp/server.py` (SIGHUP handler triggers config re-load)
- Modify: `packages/brain_api/src/brain_api/main.py` (or wherever the lifespan hook is — start the watcher; on change, signal MCP subprocess)
- Modify: `pyproject.toml` (add `watchdog` dev-dep — verify it's not already there)
- Create: `packages/brain_core/tests/config/test_hot_reload.py`

**Goal:** Per D28 step 3 of 3: cross-process hot-reload. brain_api watches `<vault>/.brain/config.json`; on change, signals brain_mcp subprocess to re-load.

**What to do:**
1. **Watcher.** `hot_reload.py`: `ConfigWatcher(config_path: Path, on_change: Callable[[], None])` using `watchdog.observers.Observer` + `FileSystemEventHandler`. Start in brain_api lifespan.
2. **Cross-process notify.** brain_api keeps the brain_mcp subprocess pid (existing `brain mcp install` flow); on change, send `signal.SIGHUP` (Unix) or write a marker file (`<vault>/.brain/run/config-version`) that brain_mcp polls (Windows fallback). Document the platform split clearly in `hot_reload.py` docstring.
3. **MCP handler.** `brain_mcp/server.py`: register `signal.signal(SIGHUP, ...)` (Unix) or filesystem polling (Windows) → on signal, call `loader._invalidate_cache()` to force next `_resolve_config` to re-read.
4. **Pin test.** `pytest-asyncio` test: spawn subprocess running an `_resolve_config` loop; main process writes a new config; subprocess detects change within 500ms; new value visible.

**Per-task review:** pytest-asyncio test passes on Mac AND Windows CI. Per-task self-review checklist.

---

## Task 36 — `validate_assignment=True` perf-measure + ENABLE ALWAYS (full production / 1.B + 3.A)

**Files:**
- Create: `packages/brain_core/tests/config/test_validate_assignment_perf.py` (perf benchmark; OUTCOME captured to lessons.md)
- Modify: `packages/brain_core/src/brain_core/config/schema.py` (set `model_config = ConfigDict(validate_assignment=True)` UNCONDITIONALLY)
- Modify: `packages/brain_core/tests/config/test_invalid_value_currently_persists_without_validation.py` → rename + flip semantics → `test_validate_assignment_enforcement.py` (asserts the new validation behavior)
- Modify: `tasks/lessons.md` (Plan 16 section: perf-measure outcome, regardless of overhead)

**Goal:** Per D29 (locked 1.B + 3.A): measure perf overhead → enable the flag REGARDLESS of outcome → document the cost. The KNOWN-LIMITATION pin test becomes a positive validation pin.

**What to do:**
1. **Benchmark.** `test_validate_assignment_perf.py`: 1000 random field assignments with and without `validate_assignment=True`. Capture wall-clock delta as a number; assert that the test always passes (this is informational, not a gate).
2. **Enable unconditionally.** `schema.py`: `Config.model_config = ConfigDict(validate_assignment=True)`. Apply same to sub-configs (`BudgetConfig`, `ProviderConfig`, etc.) where assignment validation matters.
3. **Flip pin test.** `test_invalid_value_currently_persists_without_validation` → `test_validate_assignment_enforcement`: now asserts that an invalid assignment raises `ValidationError` instead of silently persisting.
4. **Lessons.md capture.** Plan 16 section: paragraph noting the perf overhead measurement (e.g., "measured X% overhead on 1000 random field assignments"). Per 1.B: enable regardless. If overhead ≥ 10%, additionally note the perf-impact in the lesson with a recommendation to revisit if Config-instantiation hot-paths emerge.

**Per-task review:** old KNOWN-LIMITATION test is now a positive pin; perf data captured in lessons.md. Per-task self-review checklist.

---

## Task 37 — Per-domain autonomy categories — brainstorm + lock schema (full production T37-T40 / 1.B)

**Files:**
- Modify: `tasks/plans/16-comprehensive-carry-forward.md` (Task 37 Findings subsection appended)

**Goal:** Per D30 step 1 of 4: brainstorm + lock the schema shape. Plan 16 implements the locked shape in T38-T40 (NOT deferred to Plan 17+ per 1.B).

**What to do:**
1. **Brainstorm.** Final shape: `Config.autonomous: dict[str, dict[Literal["new_files","edits","index_entries","concepts","draft"], bool]]`. Categories chosen to mirror the patch-set member fields plus `concepts` and `draft` for chat-mode autonomy.
2. **Findings doc.** Append "Task 37 findings" subsection to this plan file. Cover: (a) the LOCKED schema (not "recommended"); (b) read-time backwards-compat migration: existing `autonomous: bool = true` becomes `{slug: {"new_files": true, "edits": true, "index_entries": true, "concepts": true, "draft": true} for slug in domains}`; (c) UI impact (T40 panel-autonomous.tsx grid — domains × categories); (d) interaction with T10 autonomy modal (modal becomes the quick global on/off; panel becomes the deep-config); (e) confirmed open questions resolved at lock time.
3. **No code change in T37.** T38 implements the schema migration; T39 the AutonomyGate; T40 the UI.

**Per-task review:** findings doc IS the artifact. Per-task self-review checklist.

---

## Task 38 — Per-domain autonomy schema migration (full production T37-T40 / 1.B)

**Files:**
- Modify: `packages/brain_core/src/brain_core/config/schema.py` (`Config.autonomous` field shape change)
- Modify: `packages/brain_core/src/brain_core/config/loader.py` (read-time backwards-compat transformation)
- Create: `packages/brain_core/tests/config/test_autonomy_schema_migration.py`

**Goal:** Per D30 step 2 of 4: the schema field shape changes from flat to nested per-domain × per-category. Old config.json files transparently migrate at read time.

**What to do:**
1. **Schema.** `Config.autonomous: dict[str, dict[Literal[...], bool]]` (per T37's locked shape). Default: `{slug: {"new_files": false, ...} for slug in default_domains}` (or empty dict; default to all-False at lock time).
2. **Read-time migration.** `loader._migrate_legacy_autonomous(raw: dict) -> dict`: if `raw["autonomous"]` is a `bool`, expand to nested shape using current domain list (read from `raw["domains"]`). Idempotent: if already nested, no-op.
3. **Pin tests.** (a) old shape `{"autonomous": true}` migrates to nested; (b) old shape `{"autonomous": false}` migrates to all-false nested; (c) already-nested shape passes through unchanged; (d) round-trip after migration produces nested shape.

**Per-task review:** Per-task self-review checklist.

---

## Task 39 — AutonomyGate per-domain enforcement (full production T37-T40 / 1.B)

**Files:**
- Modify: `packages/brain_core/src/brain_core/autonomy/gate.py` (or wherever the existing autonomy check lives; refactor for per-domain)
- Modify: `packages/brain_core/src/brain_core/tools/apply_patch.py` (thread `ctx.domain` into the gate)
- Create: `packages/brain_core/tests/autonomy/test_gate_per_domain.py`

**Goal:** Per D30 step 3 of 4: AutonomyGate reads per-domain × per-category flags. apply_patch threads ctx.domain.

**What to do:**
1. **Gate.** `AutonomyGate.check_category(ctx: ToolContext, category: Literal[...]) -> bool` returns True if the category is autonomous-approved for `ctx.domain`. Reads `ctx.config.autonomous[ctx.domain][category]`.
2. **apply_patch.** Iterate the patch set's member fields (`new_files`, `edits`, `index_entries`, `concepts`, `draft`); for each non-empty field, call `AutonomyGate.check_category(ctx, "<field>")`; if any returns False, route the WHOLE patch through the approval queue (not partial — partial-apply opens up scope-guard concerns).
3. **Pin tests.** (a) all-true autonomy → patch auto-applies; (b) `new_files=false` + patch contains new_files → routed to approval; (c) `edits=false` + patch contains edits but not new_files → routed; (d) all-false → routed.

**Per-task review:** Per-task self-review checklist + browser verification (toggle a category off; verify a patch hitting that category goes to approval queue).

---

## Task 40 — Per-domain autonomy UI panel (full production T37-T40 / 1.B)

**Files:**
- Create: `apps/brain_web/src/components/settings/panel-autonomous.tsx` (per-domain × per-category grid)
- Modify: `apps/brain_web/src/lib/api/tools.ts` (add `setDomainAutonomy` API call)
- Modify: `packages/brain_api/src/brain_api/routes/config.py` (`setDomainAutonomy` endpoint)
- Create: `apps/brain_web/tests/unit/panel-autonomous.test.tsx`
- Modify: `apps/brain_web/tests/e2e/a11y-populated.spec.ts` (add panel-autonomous case)

**Goal:** Per D30 step 4 of 4: Settings → Autonomous gets the per-domain × per-category grid surface.

**What to do:**
1. **UI.** `panel-autonomous.tsx`: rows = domains, columns = categories (`new_files`, `edits`, `index_entries`, `concepts`, `draft`); each cell is a `<Switch>`. Header row labels columns; first column lists domain slug + accent dot.
2. **API call.** `setDomainAutonomy(slug, category, value)`.
3. **API endpoint.** POST `/tools/setDomainAutonomy` calls `config_set` with key `autonomous.<slug>.<category>`.
4. **a11y.** Each Switch has `aria-label="<domain> {category}"` for screen readers. Tab through the grid in row-major order. axe-core: 0 violations.
5. **Tests.** vitest unit test renders the grid; e2e a11y case opens the panel; axe-core scan.

**Per-task review:** Per-task self-review checklist + browser verification.

---

## Task 41 — `brain config migrate` CLI (lifted from NOT-DOING per 1.B)

**Files:**
- Create: `packages/brain_core/src/brain_core/cli/migrate.py` (`migrate_config_file(path: Path) -> MigrationResult`)
- Modify: `packages/brain_cli/src/brain_cli/commands/config.py` (+ `migrate` subcommand)
- Create: `packages/brain_core/tests/config/test_config_migrate_cli.py`

**Goal:** Per D31: CLI subcommand `brain config migrate <path>` rewrites old-shape config.json to new shape; backs up the original.

**What to do:**
1. **Core function.** `migrate_config_file(path: Path) -> MigrationResult`: read file → run `_migrate_legacy_autonomous` (T38) + any other migrations → write back. Backup original to `<path>.pre-migrate.bak` BEFORE write. Idempotent: re-runs detect already-new shape and no-op.
2. **CLI plumbing.** `brain_cli/commands/config.py`: Typer `app.command("migrate")` that calls `migrate_config_file` against the given path (default `~/Documents/brain/.brain/config.json`).
3. **Pin tests.** (a) old-shape file migrates; backup created; (b) re-run is a no-op + no new backup; (c) backup naming is stable (no overwrite if `.pre-migrate.bak` already exists — append `.1`, `.2`, etc.).

**Per-task review:** subprocess test runs the actual CLI; verifies output. Per-task self-review checklist.

---

## Task 42 — "Set as default" topbar button (full implementation per D32)

**Files:**
- Modify: `apps/brain_web/src/components/topbar/scope-picker.tsx`
- Create: `apps/brain_web/tests/unit/scope-picker-set-as-default.test.tsx`

**Goal:** Per D32(a) (1.B full impl, not v1's scaffold): topbar scope picker gets a "Set as default" button that calls existing `setActiveDomain` API; success toast.

**What to do:**
1. **Button.** Inside the open dropdown of the scope picker, add a footer row "Set selected as default" button. Disabled when no selection, or when selection equals current `activeDomain`.
2. **Wiring.** On click, calls `setActiveDomain(slug)` from existing `domains-store.ts`. On success, push toast: "Default domain set to {slug}.". On failure, toast with error.
3. **Test.** Unit test: render with `activeDomain="research"`, select "personal" in dropdown, click button → assert `setActiveDomain("personal")` called → assert toast.

**Per-task review:** ~15 LOC + test. Per-task self-review checklist + browser verification.

---

## Task 43 — Generic zustand promotion: useBudget + useDomainOverrides (full implementation per D32)

**Files:**
- Create: `apps/brain_web/src/lib/state/budget-store.ts` (mirrors `domains-store.ts` shape)
- Create: `apps/brain_web/src/lib/state/domain-overrides-store.ts`
- Modify: `apps/brain_web/src/hooks/useBudget.ts` (becomes a thin selector over `budget-store`)
- Modify: `apps/brain_web/src/hooks/useDomainOverrides.ts` (becomes a thin selector over `domain-overrides-store`)
- Update consumers (grep for both hook usages; verify cross-instance pubsub continues to work)
- Create: `apps/brain_web/tests/unit/budget-store.test.ts`
- Create: `apps/brain_web/tests/unit/domain-overrides-store.test.ts`

**Goal:** Per D32(b): two more zustand-promotion migrations matching Plan 12's `useDomains` and Plan 13's `useCrossDomainGate` pattern.

**What to do:**
1. **`budget-store.ts`.** Persists current spend snapshot; refresh action; loaded flag; error field.
2. **`domain-overrides-store.ts`.** Persists per-domain LLM/autonomy overrides; mutations call API + update store optimistically.
3. **Hook refactors.** Both hooks become 3-line selectors.
4. **Consumer migration.** Grep + verify no behavioral change.
5. **Pin tests.** Mirror `domains-store.test.ts` shape; assert refresh + optimistic mutations + cross-instance via BroadcastChannel (T6 plumbing reused if applicable).

**Per-task review:** ~30 LOC per store + tests. Per-task self-review checklist + browser verification.

---

## Task 44 — pendingSendRef-as-local audit + APPLY (full implementation per D32)

**Files:**
- Audit: `apps/brain_web/src/components/chat/chat-screen.tsx` + neighboring handlers (`fork-thread-dialog.tsx`, `compose-dialog.tsx`, etc.)
- Modify: any file where the ref-spans-await anti-pattern appears
- Append findings to `tasks/plans/16-comprehensive-carry-forward.md` (Task 44 audit findings subsection)

**Goal:** Per D32(c) (1.B full impl, not v1's audit-only): audit + APPLY the capture-into-local pattern wherever the ref-spans-await anti-pattern appears.

**What to do:**
1. **Audit.** Grep `apps/brain_web/src/` for `useRef(` plus any `await` in the same handler. List each candidate site with file:line.
2. **For each site.** Apply the canonical pattern: capture `ref.current` into a local synchronously, clear the ref BEFORE the await, dispatch from the local. Add a unit test that exercises the throw-leak path (mock the await to throw; assert ref is cleared).
3. **Findings doc.** Append "Task 44 findings" subsection to this plan file: (a) sites inspected; (b) sites that needed the fix (with diff); (c) sites that didn't (with rationale).

**Per-task review:** every fix site has a regression test. Per-task self-review checklist + browser verification on chat-screen send path.

---

## Task 45 — Ruff custom rule BRN001 plumbing (full production per D33)

**Files:**
- Create: `packages/brain_core/src/brain_core/_lint/brn001.py` (or `tools/lint/brn001.py` — locate per ruff plugin API conventions)
- Modify: `pyproject.toml` (`[tool.ruff.lint.brain]` allowed-entry-points list; ruff plugin entry registration)
- Create: `packages/brain_core/tests/linting/test_brn001_lint_rule.py`

**Goal:** Per D33 step 1 of 2: ruff custom rule `BRN001` flags `ctx.config` reads outside the allowed entry-points list.

**What to do:**
1. **Rule plumbing.** Per ruff's plugin API (project-local rule), implement an AST visitor that catches `Attribute(value=Name("ctx"), attr="config")` reads and reports `BRN001` if the file is not in the allowed-entry-points list.
2. **`pyproject.toml`.** New `[tool.ruff.lint.brain]` section with `allowed-entry-points = ["packages/brain_core/src/brain_core/tools/config_get.py", "packages/brain_core/src/brain_core/tools/list_domains.py", "packages/brain_core/src/brain_core/tools/config_set.py", "packages/brain_core/src/brain_core/tools/_errors.py", ...]`. Implementer adds others as the rule discovers legitimate sites.
3. **Tests.** `test_brn001_lint_rule.py`: (a) sample violation file → rule fires; (b) sample allowed file → no fire; (c) `# noqa: BRN001` suppresses.

**Per-task review:** rule fires on a known-bad pattern in tests. Per-task self-review checklist.

---

## Task 46 — BRN001 violation cleanup across the codebase (full production per D33)

**Files:**
- Modify: every file ruff flags (run the rule across `packages/`, `apps/brain_web/` if applicable)
- Modify: `.github/workflows/ci.yml` (add `ruff check . --select BRN001` step)
- Modify: `.pre-commit-config.yaml` (add BRN001 to the existing ruff hook)

**Goal:** Per D33 step 2 of 2: run BRN001 across the repo; fix all violations OR add `# noqa: BRN001` with rationale.

**What to do:**
1. **Run.** `uv run ruff check . --select BRN001`. Capture all violations.
2. **For each violation.** Either (a) refactor to use `raise_if_no_config(ctx, tool_name)` (the canonical entry-point from Plan 15 Task 8); or (b) add the file to `[tool.ruff.lint.brain].allowed-entry-points` if it's a legitimate read site; or (c) add `# noqa: BRN001  # rationale: ...` if one-off justified.
3. **CI step.** ci.yml gets `uv run ruff check . --select BRN001` as a hard-fail gate.
4. **Pre-commit.** Add BRN001 to the existing ruff hook (already in pre-commit per Plan 15 Task 1).

**Per-task review:** `uv run ruff check . --select BRN001` reports 0 errors. Per-task self-review checklist.

---

## Task 47 — Closure: 47-gate demo + lessons + todo.md + spec footnotes

**Files:**
- Create: `scripts/demo-plan-16.py`
- Modify: `tasks/lessons.md` (Plan 16 closure section)
- Modify: `tasks/todo.md` (row 16 → ✅ Complete; remove Plan 16 candidate-scope; add Plan 17 candidate-scope — residuals only)
- Modify: `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` (THREE footnotes per D36)

**Goal:** Land the 47-gate demo. Lessons capture. todo.md update. THREE spec footnotes per D36.

**What to do:**
1. **demo-plan-16.py.** Mirror `scripts/demo-plan-15.py` structure. Build the 47 gates per the demo gate description in plan header.
2. **Demo script execution prefix:** `chflags 0 .../_editable_impl_*.pth && .venv/bin/python scripts/demo-plan-16.py` per lesson 341.
3. **Lessons capture.** Mirror Plan 15 closure-section format. Closure summary, then one paragraph per lesson:
   - **Production race fix (T1).** `loadRecent` overwrite race: id-keyed merge preserves optimistic rows. The Plan 14 Task 6 `waitForResponse` band-aid is now deletable. Lesson: production races that surface under test conditions are real bugs; fix production, then delete the test arm.
   - **Full-production interpretation of carry-forward at scale (T26-T46 + 1.B).** Plan 16's 47-task shape was sustainable because (a) most tasks were < 50 LOC + combined review; (b) Theme 10's expansion from 7 SCAFFOLD tasks to 21 production tasks landed each schema/enforcement/UI as a discrete reviewable unit. Lesson: when the user chooses "ship the feature working end-to-end" over "ship the data shape and defer", the natural decomposition is one task per layer (schema → migration → enforcement → UI), not one task per concern.
   - **Per-domain × per-category schema reshape (T37-T41).** The autonomy schema went from `bool` to `dict[str, dict[Literal[...], bool]]` in one plan because (a) T37 brainstormed + locked the shape; (b) T38 landed read-time backwards-compat migration; (c) T39 enforcement; (d) T40 UI; (e) T41 explicit CLI migration. Lesson: schema-shape changes that touch many call sites are tractable IF the migration is explicit (CLI tool) AND the read-time fallback (T38) covers users who never run the CLI.
   - **Leaky-bucket vs sliding-window for rate limiting (T31).** Locked leaky-bucket recommendation upheld at implementation time. Lesson: the decision rationale ("queue smooths bursty traffic; sliding-window is harder to reason about correctness for; Anthropic's own limiter is bucket-shaped") proved load-bearing — implementer routed back zero times.
   - **Cross-process hot-reload via SIGHUP + watchdog (T35).** Unix uses signal.SIGHUP; Windows fallback is filesystem polling on a marker file. Lesson: cross-process IPC should not assume Unix; Windows needs a fallback at the design phase, not an afterthought during implementation.
   - **`validate_assignment=True` enabled despite perf overhead (T36 / 1.B).** Per locked decision 1.B + 3.A, the flag landed regardless of measurement outcome. Lesson: when "ship the correctness improvement" beats "preserve a perf budget that may not matter in practice", measure-and-document beats measure-and-gate.
   - **BroadcastChannel cross-tab pubsub (T6).** Closes the optimistic-clobber race class for both `domains-store` and `cross-domain-gate-store`. Lesson: when one store has a known race shape, audit sibling stores for the same shape; the second one is usually waiting in the wings.
   - **Stylelint as structural enforcement (T13).** Plan 14 lesson C3 (theme-aware tokens) is now enforced by stylelint. Lesson: when a discipline relies on "remember to use the token", structural enforcement is the only durable fix.
   - **CI duration observability (T18).** Plan 14 Task 7+8 added Mac+Windows matrix; Plan 16 Task 18 surfaces per-job wall-clock to `$GITHUB_STEP_SUMMARY`. Lesson: the act of measuring CI duration creates pressure to keep it down. Caching (T14) + composite action (T15) follow naturally.
   - **Ruff custom rule BRN001 (T45-T46).** ctx.config reads outside the allowed-entry-points list now fail CI. Lesson: when a discipline has a small, well-defined scope (3-5 legitimate read sites), an AST-level lint rule is the right shape; it's cheaper than a code review checklist and survives staff turnover.
   - **`pendingSendRef`-as-local audit + apply (T44 / 1.B).** v1 had this as audit-only; under 1.B the audit IS followed by the apply step. Lesson: "file an audit doc" is rarely the right ending — audits without follow-up rot into wishlists. Apply OR add to NOT-DOING with a strengthened spec rationale; don't leave the middle state.
   - **Combined review held across 47 tasks.** Plan 15 lesson 5 said combined review is sufficient for < 50 LOC; Plan 16 stress-tested it at 47 tasks. Lesson: combined review scales with plan size IF per-task PR shape stays narrow. Plan 16 confirms the upper-bound claim from Plan 15.
4. **`tasks/todo.md` update.** Row 16 → ✅ Complete. Remove "Plan 16 candidate scope" tail section. Add "Plan 17 candidate scope (forwarded from Plan 16)" — pre-populate with the residuals-only post-Plan-16 deferrals: `seedBrainMd` / `seedScope` extraction once 5th caller appears; per-thread cross-domain confirmation (still NOT-DOING per spec §4); any new candidate scope discovered during Plan 16 execution. Note that under 1.B, the v1 "bigger architectural moves" carry-forward is empty — everything landed in Plan 16.
5. **Spec footnotes (THREE per D36).** (a) §6 (Cost): per-domain budget caps + rate limits full implementation (T26-T29 + T30-T32). (b) §3 (Vault) [or §5 (Autonomy) depending on spec layout]: per-domain autonomy categories full implementation + migration tool (T37-T41). (c) §4 (Privacy): strengthen the "one-time" clause to make explicit that per-thread cross-domain confirmation is an intentional architectural NO.

**Per-task review:** demo gates 1-47 all green. Lessons capture is the Plan 16 retrospective. todo.md update is the closure handoff. Three spec footnotes are the user-facing surface change. Per-task self-review checklist runs to completion.

---

## Review (pending)

To be filled in on closure following Plan 10 + 11 + 12 + 13 + 14 + 15 format:
- **Tag:** `plan-16-comprehensive-carry-forward` (cut on green demo).
- **Closes:** all 50+ items from Plan 16 candidate scope (themes 1-9 directly; theme 10 at FULL PRODUCTION per locked 1.B). Plan 16 candidate-scope tail block in `tasks/todo.md` removed; Plan 17 candidate-scope tail block added (residuals only).
- **Bumps:** schema gains 4 new fields (`Config.budget.per_domain`, `Config.providers[*].rate_limit_per_domain`, `Config.config_version`, `Config.autonomous` reshape from `bool` → nested per-domain × per-category) + `validate_assignment=True` flag. New components: `RepairConfigDialog` (full polish), `AutonomyModal`, `FilePreviewOverlay`, `PanelDomainsRow` + `PanelDomainsAdd` + `PanelDomainsActive`, `PanelAutonomous`, `BudgetStore`, `DomainOverridesStore`. New CLI: `brain config migrate`. New infrastructure: `watchdog` file-watcher, cross-process SIGHUP signaling, `BRN001` ruff rule, leaky-bucket rate-limit enforcement. New tooling: stylelint (with hardcoded-hex rule), pre-commit gh workflow validate hook, BRN001 lint rule. New CI infrastructure: composite action, workflow caching, per-job summary writeback, Defender SmartScreen feature flag.
- **Verification:** all 47 demo gates green (`scripts/demo-plan-16.py` → `PLAN 16 DEMO OK`); pytest count + vitest count + Playwright count + Mac+Windows CI green to be filled in.
- **Backlog forward:** Plan 17 candidate scope pre-populated per Task 47 step 4. Themes: residuals only — `seedBrainMd` / `seedScope` once 5th caller appears; per-thread cross-domain (still NOT-DOING by spec). Under 1.B, the v1 "bigger architectural moves" carry-forward block is EMPTY — everything landed in Plan 16.
- **Forwards:** lessons captured in `tasks/lessons.md` under "Plan 16" feed Plan 17's authoring.

---

## Task 37 — Findings

This subsection is the brainstorm artifact T37 was asked to produce (D30 step
1 of 4). It locks the schema shape, the migration algorithm, the autonomy-
gate signature evolution, and the modal-vs-panel UI split that T38, T39, and
T40 codify. Where the brainstorm deviates from the spec's nominated shape it
flags the deviation explicitly and parks it as a "deferred for sign-off"
item; T38 should not start until the user has weighed in on those.

### 0. Pre-flight context (what already exists today)

- `Config.autonomous: AutonomousConfig` (schema.py:291–306) — a flat,
  category-bucket BaseModel with five booleans: `ingest`, `entities`,
  `concepts`, `index_rewrites`, `draft`. All default `False`.
- `PatchCategory` (vault/types.py:12–27) — six values: `INGEST`, `ENTITIES`,
  `CONCEPTS`, `INDEX_REWRITES`, `DRAFT`, `OTHER`. The first five map 1:1 to
  the five `AutonomousConfig` flags; `OTHER` never auto-applies.
- `should_auto_apply(patchset, config) -> bool` (autonomy.py:39–45) — reads
  `patchset.category`, looks up `_CATEGORY_TO_FLAG`, and returns
  `config.autonomous.<flag>`. No domain awareness.
- `apply_patch._resolve_config(ctx)` (apply_patch.py:114–132) — returns a
  defaults-only `Config(vault_path=ctx.vault_root)`; the real config is NOT
  read here yet (Plan 16+ work, deliberately deferred). Tests monkeypatch
  this stub.
- `PatchSet` (vault/types.py:47–62) — has member fields `new_files: list`,
  `edits: list`, `index_entries: list`, `log_entry: str | None`, plus
  `category: PatchCategory`. Note `log_entry` is a member field but is not
  in the spec's nominated category set (it's a single string log line, not
  a vault mutation).
- `AutonomyModal` (autonomy-modal.tsx) — T10 scaffold uses three categories
  `newFiles` / `edits` / `indexEntries` (member-field-shaped). The scaffold
  comment at line 14–20 already names T37/T38 as the place where the real
  per-domain shape gets locked. `concepts` and `draft` are absent from the
  scaffold.
- `DomainOverride` (schema.py:309–326) — Plan 12 D1 explicitly DROPPED a
  per-domain autonomy field from this model. The new shape MUST live
  somewhere else (this brainstorm picks "top-level dict on `Config`",
  consistent with `BudgetConfig.per_domain` and
  `ProviderConfig.rate_limit_per_domain`).
- `Config` already has `validate_assignment=True` (T36, schema.py:379), so
  any nested BaseModel we land here gets free per-field validation on
  `setattr`.

### 1. Locked schema

Adopting the spec's nominated category set verbatim, with one Pydantic-
shape choice (BaseModel over TypedDict). The locked field declaration on
`Config`:

```python
class AutonomyCategoryFlags(BaseModel):
    """Per-category auto-apply flags for one domain.

    Lives under :attr:`Config.autonomous` keyed by domain slug. The five
    keys are a HYBRID surface — three are :class:`PatchSet` member-field
    names (``new_files``, ``edits``, ``index_entries``); two are
    :class:`PatchCategory` values (``concepts``, ``draft``). The category
    selection is intentional: chat-mode autonomy ("draft a note for me")
    is naturally category-shaped, while ingest / propose-note autonomy is
    naturally member-field-shaped (the user reasons about "do I trust
    auto-creating new files?" not "do I trust the INGEST bucket?").
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    new_files: bool = False
    edits: bool = False
    index_entries: bool = False
    concepts: bool = False
    draft: bool = False


class Config(BaseModel):
    ...
    autonomous: dict[str, AutonomyCategoryFlags] = Field(default_factory=dict)
```

**TypedDict vs BaseModel — locked to BaseModel.** TypedDict is lighter and
JSON-friendly, but BaseModel buys five things we want for free:

1. `validate_assignment=True` (T36-locked) catches typos at runtime, not
   silently. With TypedDict, `cfg.autonomous["research"]["new_filez"] =
   True` would silently land — the unknown key isn't validated.
2. `extra="forbid"` rejects unknown category keys at load time, not at
   gate evaluation time.
3. Sub-model `model_dump` / `model_validate` round-trip for free (the
   loader currently `Config.model_validate(raw)`s the whole tree).
4. The pattern matches every existing per-domain map in the codebase
   (`BudgetOverride`, `RateLimitOverride`) — consistency over micro-perf.
5. T39's `should_auto_apply` can read `flags.new_files` (attribute access)
   instead of `flags["new_files"]` (dict access); the typed read is mypy-
   strict-friendly and matches existing `config.autonomous.ingest` ergonomics
   today.

**Why `AutonomyCategoryFlags` (not `dict[Literal[...], bool]`).** The
spec's nominated shape is `dict[str, dict[Literal[...], bool]]`. Pydantic
v2 does accept `dict[Literal[...], bool]` as a value type, but it forbids
`extra` enforcement (every key in the Literal is required, missing keys
default to `MISSING` then fail validation; or — depending on Pydantic
version — they default-construct to `False` silently). A named BaseModel
with explicit `bool = False` defaults gives us the right semantics: every
flag defaults False, unknown flags raise, and partial JSON like
`{"research": {"new_files": true}}` round-trips cleanly with the other
four flags inferred as False. This is a SHAPE-EQUIVALENT clarification
(not a deviation) — the JSON on disk under the spec's nominated typing
and under `AutonomyCategoryFlags` is byte-identical.

**Cross-field validator (NEW):**

```python
@model_validator(mode="after")
def _check_autonomy_keys_in_domains(self) -> Config:
    orphans = [slug for slug in self.autonomous if slug not in self.domains]
    if orphans:
        raise ValueError(
            f"autonomous keys {orphans!r} are not in domains {self.domains!r}; "
            "remove the entry or add the domain first."
        )
    return self
```

Mirrors the existing `_check_domain_overrides_keys_in_domains` validator
(schema.py:524–535). Without it, deleting a domain leaves orphan autonomy
entries that silently come back if the slug is re-added — the same risk
that motivated the orphan-rejection rule for `domain_overrides`.

### 2. Member-field vs category semantics — explicit decisions

This is the core architectural tension flagged in the task brief. The new
shape is a hybrid (three member-field keys + two category keys), so the
gate has to adjudicate two semantically different questions in one pass.
Locked decisions:

**Q1 — Multi-member patches with mixed flags. LOCKED: any-False ⇒ stage the
WHOLE patch.** A patch with `new_files=[...]` AND `edits=[...]` against a
domain config of `{new_files: false, edits: true}` routes to the approval
queue. Rationale:

- Partial-apply is a scope-guard hazard. If we auto-applied the `edits`
  half and staged the `new_files` half, the user would have to mentally
  reconcile "this patch was 60% applied"; one half could land while the
  other waits in pending/, producing a half-consistent vault state. Atomic
  apply through `VaultWriter.apply` is the contract — partial-apply
  violates it.
- Worse, the integrate step often emits patches where new files and edits
  are causally coupled (a new note PLUS an index entry referencing the new
  note). Partial-apply could leave a dangling wikilink in the index file
  pointing at a note that never landed.
- The spec's T39 step 2 hint ("if any returns False, route the WHOLE
  patch through the approval queue (not partial — partial-apply opens up
  scope-guard concerns)") matches this conclusion.

Trade-off acknowledged: a domain with `{new_files: true, edits: false}`
and a patch that contains BOTH never auto-applies. The user might
reasonably expect "only the new_files flag matters here". The fix is the
UI surface — T40's panel makes the AND-gate explicit so the user
understands flipping `edits` off blocks every multi-member patch in that
domain. Documented in T40 microcopy.

**Q2 — `category=CONCEPTS` patch with `edits=[...]`. LOCKED: intersection
(BOTH `concepts=True` AND `edits=True` required).** The hybrid shape
treats member-field flags and category flags as orthogonal AND-gated
filters. A CONCEPTS-category patch that touches `edits` requires the user
to opt INTO both the concepts bucket AND the edits-touch surface for that
domain. Rationale:

- "Intent" (category) and "blast radius" (member fields) are different
  axes. A user who trusts the LLM's concept-page judgment but doesn't
  trust it to silently rewrite existing files needs a way to say "auto-
  apply concept NEW FILES but stage concept EDITS." Intersection gives
  that.
- The "any-False ⇒ stage" rule from Q1 already implies intersection over
  member fields; adding category-AND-member is the natural extension.
- Easier to relax later than to tighten later. A union policy ("either
  flag enabled ⇒ auto-apply") would be a privacy regression to walk back.

Trade-off acknowledged: the AND gate makes "auto-apply ALL concept
patches in this domain" require the user to flip on `concepts=True` AND
all three of `new_files`/`edits`/`index_entries=True`. The deep-config
panel UI must surface this clearly; "Enable all categories" toggle row
on the panel reduces friction.

**Q3 — `INGEST`, `ENTITIES`, `INDEX_REWRITES` PatchCategory values under
the new shape. LOCKED: option (b) — the three orphan categories become
PatchCategory-only metadata; the new member-field flags govern autonomy.**
Concretely:

- `INGEST` ⇒ no longer reads a top-level "ingest" bool. The new gate
  inspects the patch's actual member fields (a typical INGEST patch is
  `new_files=[...] + index_entries=[...]`) and AND-gates against
  `{new_files, index_entries}` for the target domain.
- `ENTITIES` ⇒ same. Entity patches are typically `new_files` (a new
  person/concept page) + `edits` (existing pages get backlinks).
- `INDEX_REWRITES` ⇒ AND-gates against the `index_entries` member-field
  flag.

Rationale: there's no clean 1:1 mapping ("INGEST → new_files" silently
ignores the index_entries half of an ingest patch; "ENTITIES → ???"
literally has no clean target). Option (a) loses information; option (b)
preserves the semantic shift the spec is making (member-field-shaped
autonomy is the point of T37). The `category` field stays on PatchSet —
it's still useful for the approval-queue UI (group pending patches by
intent: "5 ingest, 3 concept, 2 entity"), the cost ledger's
operation-tagging, and lint heuristics. It just doesn't drive the gate
anymore.

Trade-off acknowledged: this is a real semantic shift away from the spec
rationale's "categories chosen to mirror the patch-set member fields plus
`concepts` and `draft` for chat-mode autonomy." The spec implies a 5-
flag surface; option (b) preserves the 5 flags exactly but reframes
their meaning (3 member-field flags are the gate; 2 category flags
preserve the chat-mode-autonomy distinction the spec calls out). The
brainstorm believes this matches the spec's INTENT but DEVIATES from a
strictly literal reading of D30. Flagged as a deferred sign-off item
below.

### 3. Migration from existing `AutonomousConfig` (flat) to nested

The task brief's hypothetical "old shape `autonomous: bool = true`" is
incorrect — the current shape on disk is the structured `AutonomousConfig`
object with five named booleans. T38's migration must handle BOTH the
hypothetical legacy bool AND the real existing-on-disk structured shape.

**LOCKED migration algorithm (T38 codifies):**

```python
def _migrate_legacy_autonomous(raw: dict) -> dict:
    """Idempotent: rewrites raw["autonomous"] in place if it's an old shape.

    Three accepted input shapes:
      1. Already nested (post-migration):
           {"research": {"new_files": false, ...}, ...}
         -> no-op.
      2. Flat AutonomousConfig (real existing on-disk shape):
           {"ingest": false, "entities": false, "concepts": false,
            "index_rewrites": false, "draft": false}
         -> expand per the mapping table below for every slug in raw["domains"].
      3. Hypothetical legacy bool (forward-compat for any user who
         hand-edited config.json to a single bool — never shipped, but
         cheap to handle):
           true / false
         -> all-True (or all-False) for every slug in raw["domains"].
    """
```

**Mapping table for shape (2) → (1):**

| Old flag (`AutonomousConfig`) | Maps to (per domain)                              |
|-------------------------------|---------------------------------------------------|
| `ingest=true`                 | `new_files=true`, `index_entries=true`            |
| `ingest=false`                | (no-op; defaults are False)                       |
| `entities=true`               | `new_files=true`, `edits=true`                    |
| `entities=false`              | (no-op)                                           |
| `concepts=true`               | `concepts=true`                                   |
| `concepts=false`              | (no-op)                                           |
| `index_rewrites=true`         | `index_entries=true`                              |
| `index_rewrites=false`        | (no-op)                                           |
| `draft=true`                  | `draft=true`                                      |
| `draft=false`                 | (no-op)                                           |

Notes on the mapping:

- `ingest` is the trickiest cell. An ingest patch typically creates a
  source note (`new_files`) AND adds index entries (`index_entries`).
  Mapping `ingest=true` to BOTH preserves the user's prior intent ("yes,
  auto-apply ingest patches") under the new member-field gate. Mapping
  to only `new_files` would break ingest auto-apply for any patch that
  touches indices.
- `entities` has no clean target (Q3 above). The migration choice
  `new_files=true, edits=true` reflects what entity patches typically
  contain. This is the most aggressive cell of the migration — it grants
  edit-autonomy to a domain that previously only had entity-bucket
  autonomy. **DEFERRED** for user sign-off below; conservative
  alternative is to drop `entities=true` on migration (no target
  flags get set) and surface a one-time toast: "Your old `entities`
  autonomy flag had no clean equivalent in the new per-category shape;
  please re-enable specific categories per domain in Settings → Autonomy."
- Multiple True flags compose with logical OR per cell: `ingest=true,
  entities=true` ⇒ `new_files=true` (from both), `edits=true` (from
  entities), `index_entries=true` (from ingest).
- The migration runs once at load time (T38 codifies). The on-disk
  shape after the next `save_config` is the new nested form;
  `_migrate_legacy_autonomous` is idempotent so a re-run is a no-op.
- A `brain config migrate` CLI subcommand (T41) writes the migrated
  shape back AND backs up the original — so users who want to inspect
  the diff can see exactly what flags landed where.

**Pin tests T38 should land** (in addition to the spec's listed pins):

- (e) flat `{"ingest": true}` ⇒ nested `{slug: {"new_files": true,
  "index_entries": true}}` for every slug in domains.
- (f) flat `{"entities": true}` ⇒ migration outcome per the chosen
  policy (DEFERRED — sign-off determines whether this maps to
  `{new_files, edits}` or to nothing-with-a-toast).
- (g) flat `{"ingest": true, "concepts": true}` ⇒ nested with
  `new_files=True, index_entries=True, concepts=True` per domain;
  `edits=False, draft=False`.
- (h) round-trip after migration: `Config(**migrated).model_dump()` ==
  migrated.

### 4. Defaults at lock time

**LOCKED: empty dict `{}` (NOT all-False explicit).** Rationale:

- An empty dict is the "no per-domain entries configured" signal. The
  gate function (T39) treats a missing key as "all-False" for that
  domain — equivalent semantics to an explicit all-False entry, but
  smaller on-disk footprint and clearer "user has not touched this"
  state for the UI.
- The migration path (above) writes explicit per-domain entries for
  every slug in `domains` whenever the user had non-default flags;
  fresh installs land at `{}` until the user toggles something.
- CLAUDE.md principle #3 ("LLM writes are always staged, never direct")
  is honored either way — both `{}` and `{slug: AutonomyCategoryFlags()}`
  produce all-False evaluation. The choice is purely cosmetic on disk.
- Consistent with `BudgetConfig.per_domain: dict[str, BudgetOverride] =
  Field(default_factory=dict)` and `ProviderConfig.rate_limit_per_domain`.

The cross-field validator catches orphan entries (Section 1). The "is
this domain configured?" UI predicate is `slug in cfg.autonomous`.

### 5. `should_auto_apply` signature evolution (T39 sketch)

Current (autonomy.py:39):

```python
def should_auto_apply(patchset: PatchSet, config: Config) -> bool:
    flag_name = _CATEGORY_TO_FLAG.get(patchset.category)
    if flag_name is None:
        return False
    return bool(getattr(config.autonomous, flag_name))
```

T39 evolution sketch (NOT for implementation in T37 — T39 lands it):

```python
def should_auto_apply(
    patchset: PatchSet,
    config: Config,
    *,
    domain: str,
) -> bool:
    """Per-domain × per-category gate.

    Returns True iff the patchset's content is fully covered by enabled
    flags for ``domain``. Algorithm:

      1. OTHER category never auto-applies (preserved invariant).
      2. Look up ``flags = config.autonomous.get(domain)``. If missing,
         return False (no entry ⇒ all-False).
      3. Build the "required-True" set:
         - For every non-empty member field on patchset
           (new_files, edits, index_entries), require flags.<member>.
         - For category in {CONCEPTS, DRAFT}, additionally require
           flags.<category-name>.
         - For category in {INGEST, ENTITIES, INDEX_REWRITES}, NO extra
           category-level requirement (Q3 decision: those become
           metadata; member fields govern).
      4. If every required flag is True, return True. Else False.
    """
```

Key signature changes vs today:

- `domain: str` becomes a kwarg (keyword-only to keep the pos-arg
  signature broken at the type level — every existing call site MUST
  update; mypy and the test suite catch the migration).
- `OTHER` short-circuit moves up (no behavior change vs today).
- Returns False on missing-domain (no entry ⇒ all-False semantic).
- The category-flag check (Q3) only fires for CONCEPTS and DRAFT.

Call sites that need updating:

- `apply_patch.handle` (apply_patch.py:87) — already has `ctx.allowed_domains`
  AND `ctx.domain` (Plan 16 T28 added the per-call narrowed domain to
  `ToolContext`). T39 plumbs `ctx.domain` (or, if `None`, derives from
  `envelope.target_path.parts[0]`) into `should_auto_apply(...,
  domain=...)`.
- `_resolve_config(ctx)` (apply_patch.py:114–132) — STILL the test seam.
  T39 should NOT replace this with a real config read (that's a separate
  Plan 16+ task per the existing docstring). The defaults-only stub
  preserves test isolation; the new shape just means the stub returns a
  Config with `autonomous={}`, which evaluates to "all-False everywhere"
  and matches today's test fixtures' baseline.
- `tests/test_autonomy.py` — every test must update to pass `domain=...`
  AND construct `Config(autonomous={"research": AutonomyCategoryFlags(...)})`
  instead of `AutonomousConfig(...)`. T39 lands the test-file rewrite
  alongside the gate.

### 6. UI mapping — modal vs panel under the new shape

**LOCKED architecture:**

- **Modal (T10 scaffold, finalized at T40):** "quick global on/off."
  The modal becomes a per-CURRENT-DOMAIN quick toggle. Global-row toggle
  flips ALL FIVE category flags for the active domain
  (`config.activeDomain`) atomically. Per-category rows toggle one flag
  for the active domain. The modal NEVER touches non-active-domain
  entries. Rationale: the modal's whole point is "I want to flip
  autonomy on/off for what I'm working on right now"; bleeding into
  other domains would be surprising.
- **Panel (T40, NEW):** `panel-autonomous.tsx`. A grid: rows = domains,
  columns = the five categories. Each cell is a `<Switch>` bound to
  `config.autonomous[slug][category]`. This is the deep-config surface
  — every cell is independently toggleable.

**T10 modal scaffold updates** required at T40 lock-time:

- Three-category surface (`newFiles`, `edits`, `indexEntries`) becomes
  five-category (add `concepts`, `draft`).
- The "global autonomy" row's semantic changes from "are per-category
  controls enabled?" to "are all five flags True for the active
  domain?". All-True ⇒ checked; all-False ⇒ unchecked; mixed ⇒
  indeterminate (use `data-state="indeterminate"` on the underlying
  Switch primitive).
- `onChange` callback gains a domain hint OR is replaced by a direct
  `setDomainAutonomy(activeDomain, category, value)` API call (T40 lands
  the API).
- The current "disabled when global is off" pattern (lines 144–159 in
  autonomy-modal.tsx) goes AWAY. Per-category rows are independently
  toggleable; the global row is a convenience fan-out.

**Panel a11y / interaction notes (T40):**

- Each `<Switch>` cell: `aria-label="Auto-apply {category} in {domain}"`.
- Tab order: row-major (domain A's five cells, then domain B's five).
- A "Reset to defaults" button per row (sets all five flags False for
  that domain). A "Disable all autonomy" footer button (clears the
  whole `autonomous` dict to `{}`).
- The modal and panel share state via the same config-store; flipping a
  cell in either UI is reflected in the other on next paint.

### 7. Open questions resolved at lock time

| # | Question                                                              | Resolution                                                                                                                                          |
|---|-----------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | TypedDict vs BaseModel for the per-domain value                       | BaseModel (`AutonomyCategoryFlags`) — gets `validate_assignment` + `extra="forbid"` for free; matches every other per-domain map.                   |
| 2 | Default for `Config.autonomous`                                       | Empty dict `{}`; the gate treats missing-domain as all-False.                                                                                       |
| 3 | Multi-member patches with mixed flags (Q1)                            | Any-False ⇒ stage the WHOLE patch. No partial apply.                                                                                                |
| 4 | `category=CONCEPTS` + `edits=[...]` semantics (Q2)                    | Intersection: both `concepts=True` AND `edits=True` required.                                                                                       |
| 5 | Where the new shape lives on `Config`                                 | Top-level `Config.autonomous: dict[str, AutonomyCategoryFlags]` (NOT inside `DomainOverride` — Plan 12 D1 dropped that). Mirrors `budget.per_domain`. |
| 6 | Cross-field validator (orphan slug rejection)                         | YES — mirrors `_check_domain_overrides_keys_in_domains`.                                                                                            |
| 7 | OTHER category in the new gate                                        | Still always-False short-circuit at the top of `should_auto_apply` (preserved invariant; pin test stays green).                                     |
| 8 | `domain` arg on `should_auto_apply`                                   | Keyword-only; every call site updates explicitly.                                                                                                   |
| 9 | What `_resolve_config(ctx)` returns post-migration                    | Same defaults-only stub; with `autonomous={}` default it produces all-False evaluation, matching today's test fixtures' baseline.                   |
| 10 | Modal scope (cross-domain or active-domain only)                      | Active-domain only. Cross-domain editing lives in the panel.                                                                                        |

### 8. Open questions DEFERRED for user sign-off (BLOCKING T38)

These are questions the brainstorm cannot resolve unilaterally because
they alter user-facing behavior or deviate from a literal reading of D30.
T38 should NOT start until the user signs off on these.

**D-1 (DEVIATION FROM SPEC). Q3 / Section 5 step 3: should the gate's
category-flag check fire for ALL five `_CATEGORY_TO_FLAG` keys (literal
reading of D30 — preserves today's mapping) or ONLY for `CONCEPTS` and
`DRAFT` (the brainstorm's recommended reading — `INGEST`, `ENTITIES`,
`INDEX_REWRITES` become PatchCategory-only metadata, gate is governed
by member-field flags)?** The recommended option is the latter — it's
the only way to make the hybrid 5-key shape coherent without losing
information. But it IS a semantic shift the user should sign off on
before T38/T39 codifies it.

**D-2. Migration of `entities=True` (Section 3 mapping table).** The
recommended mapping is `entities=True ⇒ {new_files: true, edits: true}`
per domain. The conservative alternative is to drop `entities=True` on
migration with a one-time toast asking the user to re-enable specific
categories. The aggressive option grants edit-autonomy to a domain
that previously did not have it; the conservative option silently
disables a flag the user explicitly turned on. Recommend the aggressive
option (preserves prior intent) but flag for sign-off because edit-
autonomy is a scope-guard-adjacent capability.

**D-3. Migration of `index_rewrites=True`.** Recommended mapping is
`index_rewrites=True ⇒ {index_entries: true}` per domain. This is
straightforward (1:1 by name), but the brainstorm wants to confirm the
user is fine with `index_rewrites` being deprecated as a Config field
name in favor of `index_entries` in the new shape (the new shape's
Literal must use the member-field name; `index_rewrites` was the old
category bucket name). No content change, just a name normalization.

**D-4. Default behavior for users with NO existing `AutonomousConfig`
on disk (i.e. a fresh install or a config.json predating the
field).** Recommended: `autonomous={}` (matches Section 4). The user
gets all-False evaluation everywhere, which matches today's
"out-of-the-box auto-applies nothing" guarantee from CLAUDE.md
principle #3. No deviation here — flagging only because the migration
helper's branch coverage needs this case explicitly tested (T38 pin
(c) "already-nested" should also include "field absent entirely").

### 9. Readiness for T38

**Ready to codify** if the user signs off on D-1, D-2, D-3, D-4 above.
Sign-offs are independent — D-1 is the only one that materially shifts
T39's gate algorithm (it changes which `_CATEGORY_TO_FLAG` keys the
category-flag check evaluates). D-2/D-3/D-4 only affect T38's migration
mapping table.

If the user accepts the brainstorm's recommendations on all four,
T38 → T39 → T40 can proceed sequentially without further design
iteration. If the user wants the literal-D30 reading on D-1, the
T39 gate algorithm sketch in Section 5 step 3 needs adjustment (the
`{INGEST, ENTITIES, INDEX_REWRITES}` branch becomes a category-flag
check on the still-existing `ingest`, `entities`, `index_rewrites`
keys), but the rest of the design is unchanged — T38's schema shape
is identical under either reading.

**One quirk noted (no fix in T37 per scope rules):** `apply_patch.py`
imports `Config` from `brain_core.config.schema` but never reads it
from `ctx.config` — it always returns the defaults-only stub from
`_resolve_config`. This is documented as a deliberate test seam, but
T39 will need to decide whether to keep the seam (pass the stub-Config
through with `autonomous={}` ⇒ everything stages) or finally wire
`ctx.config` for real. The brainstorm recommends KEEPING the seam in
T39 (smallest surface change; Plan 16+ tackles real config plumbing)
and filing a follow-up task for "wire `_resolve_config` to read
`ctx.config` when present." Out of scope for T37 to land.

---

## Task 44 — pendingSendRef-as-local audit findings (to be filled by implementer)

To be appended by Task 44 implementer per D32(c). Expected shape:

- **Sites inspected:** TBD.
- **Sites that needed the fix (with diff):** TBD.
- **Sites that didn't need it (with rationale):** TBD.
- **Regression tests added:** TBD.

---

**End of Plan 16.**
