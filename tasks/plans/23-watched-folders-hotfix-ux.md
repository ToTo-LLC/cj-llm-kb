# Plan 23 — Watched-folders hot-fix + UX one-liners

**Authored:** 2026-05-12 (post Plan 22 close on 2026-05-12, tag
`plan-22-watched-folders-sync` at `af98b2e`).
**Scope:** Close the one truly critical Plan 22 carry-forward (the
`list_watched_folders` `pydantic.ValidationError` catch gap surfaced
by T16) plus two cheap UX one-liner fixes (watch-enable modal domain
dropdown defaulting to `activeDomain` not `domains[0]`; topbar
indicator fetching on its own mount instead of relying on Settings
panel mount). Smallest plan since Plan 21 (3 tasks). Per user scope
lock: B = hot-fix + UX one-liners; T2 width = 2.A (activeDomain +
topbar mount-refresh, NOT cross-store reconcile).
**Shape:** 2 substantive tasks + 1 closure. Mirrors Plan 21's small/
focused precedent.

## At a glance

- **Theme A — Critical hot-fix** (T1): catch
  `pydantic_core.ValidationError` alongside the existing
  `FrontmatterError` in
  `packages/brain_core/src/brain_core/tools/list_watched_folders.py:72`
  (`_walk_watched_folder_counts` helper). Without this, a single
  malformed-frontmatter watched-folder note in the vault crashes the
  Settings → Watched folders tab + Topbar indicator (Plan 22 T16
  surfaced this via Playwright cleanup + filed it as the only
  critical Plan 23 carry-forward). ~3 LOC + regression-pin test.
- **Theme B — Bundled UX one-liners** (T2):
  - **T2.a — activeDomain dropdown default.** `watch-enable-modal.tsx`
    currently defaults the domain dropdown to `Config.domains[0]`
    (typically `"personal"`). It should default to
    `Config.active_domain` (e.g., `"research"` per the topbar scope
    chip). Caught at the T15 manual chrome verification pause (Plan 22).
    ~1 LOC + 1-2 unit tests.
  - **T2.b — Topbar indicator own mount-time fetch.** The Plan 22 T14
    indicator currently relies on Settings-panel-mount to populate
    `useWatchedFoldersStore.folders`. If the user lands directly on
    a chat / inbox / browse route, the indicator renders with stale /
    empty state until they navigate to Settings → Watched folders.
    Add a `useEffect` mount-time fetch (call
    `useWatchedFoldersStore.fetch()` if folders is empty + not
    in-flight). ~5 LOC + 1 unit test.
- **Closure** (T3): demo + lessons + todo + tag
  `plan-23-watched-folders-hotfix-ux`.

## Why this plan exists (1 paragraph)

Plan 22 closed 2026-05-12 with 19 carry-forward Plan 23 candidates.
Honest re-assessment surfaced exactly one as truly critical: the
`list_watched_folders.ValidationError` catch gap. Without that fix,
any user with malformed frontmatter in a watched-folder note (e.g.,
an `orphaned_at` field that fails Pydantic strict validation; a
hand-edit that violates `extra="forbid"`; a legacy note from before
Plan 22's frontmatter additions) will see the Settings → Watched
folders tab crash + the Topbar indicator fail to populate. The
defensive `purgeWatchedFolderPollution` workaround in
`apps/brain_web/tests/e2e/watched-folders.spec.ts` (T16) is evidence
the failure mode is real + reproducible. Plan 23 catches the
exception properly so the listing degrades gracefully (skip the bad
note + structlog-warn) instead of crashing the surface. The two
bundled UX one-liners (T2.a + T2.b) are cheap value-adds caught at
Plan 22 implementer + controller-verification pauses — folded into
the same plan rather than deferred so the polish ships alongside the
crash fix.

## Locked decisions

| # | Decision | Status | Why |
|---|---|---|---|
| D1 | **Scope = B hot-fix + UX one-liners.** T1 = critical ValidationError catch; T2 = bundled 2.A UX (activeDomain default + topbar mount-refresh). | locked (user B) | Closes the only Plan 22 production-crash risk + ships 2 visible UX improvements per Plan 22 controller-verification + T15 implementer flagging. The fixes are independent (backend vs frontend) but bundle cleanly because both are <30 LOC each. |
| D2 | **T2 width = 2.A.** Two fixes only (activeDomain + topbar refresh). NOT the wider 2.B (which would also include cross-store reconcile for orphan_count). | locked (user 2.A) | Keeps T2 cheap; cross-store reconcile stays as a Plan 24 candidate (it's "stale UI on re-mount" — re-mount fixes it; not a real bug). |
| D3 | **Push at Plan 23 close after user authorization.** Single `git push origin main` covers all Plan 23 commits; explicit `git push origin <tag>` for the lightweight tag (per Plan 20 closure observation — `--follow-tags` skips lightweight tags). | locked per Plan 20 D10 / Plan 21 D10 / Plan 22 D12 | Standard cadence held across four prior plans. |
| D4 | **Combined spec + code-quality review per task.** | locked per Plan 19 D8 / Plan 20 D8 / Plan 21 D8 / Plan 22 D10 | Held across seven prior polish-and-feature plans. |
| D5 | **Sequential subagent dispatch.** | locked per Plan 19-22 precedent | T1 (brain-core) → T2 (brain-frontend) → T3 (brain-core closure). |
| D6 | **No new dependencies.** | locked per Plan 19-22 precedent | All fixes use existing surfaces. |
| D7 | **Preserved 4 NOT-DOING (unchanged since Plan 17).** `seedBrainMd` rule-of-three, per-thread cross-domain (architectural NO per Plan 16 D36), topbar scope chip drift watch (lesson-only per Plan 12), PEP 703 `_cached_ctx` (3.14+ trigger). | locked per Plan 20 D5 / Plan 21 D5 / Plan 22 D5 | No triggers fired. Stay in Plan 24 candidate scope. |
| D8 | **Demo gate count: ~6-8.** Per-item closure assertion mirroring Plan 19-22 pattern. | locked per Plan 21 D7 / Plan 22 D7 | Small plan → small gate count. |
| D9 | **Pause cadence: none mid-plan.** Plan 23's 3-task budget means no intermediate pause; just plan-close after T3. | locked at authoring | Pause cadence is for larger plans (~5-tasks-per-pause). Plan 23 is too small to benefit. |
| D10 | **Plan 24 candidate scope = remaining 16 Plan 22 carry-forwards (which already includes the 4 preserved NOT-DOING).** Plan 22's 19-item Plan 23 candidate scope minus the 3 items Plan 23 addresses (T1 critical + T2.a activeDomain + T2.b topbar mount-refresh) = 16 items unchanged into Plan 24 candidate: 7 UX polish + 4 architectural + 1 dev-loop + 4 preserved NOT-DOING. | locked at authoring | The other 16 items remain at Plan 22-end priority levels; user adjudicates at Plan 24 brainstorm. |

## Tech stack

Same as Plans 16-22: Python 3.12, pydantic v2, mypy --strict, ruff,
structlog, vitest, Playwright. No new tools. No new dependencies.
CI runs on macos-14 + windows-2022 per Plan 14's matrix.

## Demo gate description

`scripts/demo-plan-23.py` asserts, in sequence:

1. **(T1.a)** `packages/brain_core/src/brain_core/tools/list_watched_folders.py`
   `_walk_watched_folder_counts` catches `pydantic_core.ValidationError`
   (or `pydantic.ValidationError`; verify import path at exec time)
   alongside the existing `FrontmatterError` catch. Regex match on
   the except clause OR AST inspection.
2. **(T1.b)** Regression-pin test exists at
   `packages/brain_core/tests/tools/test_list_watched_folders.py`
   (or sibling file) that constructs a vault with a deliberately
   malformed watched-folder note, calls
   `brain_list_watched_folders`, and asserts: (a) the call does NOT
   raise; (b) the malformed note is skipped from the count; (c) a
   structlog warning was emitted (use a logs-capture fixture).
3. **(T2.a)** `apps/brain_web/src/components/dialogs/watch-enable-modal.tsx`
   domain dropdown initial value derives from
   `config.active_domain` (NOT `config.domains[0]`). Regex match on
   the initialization expression.
4. **(T2.b)** Unit test for the watch-enable modal asserts the
   default selected domain is `activeDomain` when `activeDomain` is
   set (use a fixture with `activeDomain = "research"` and
   `domains[0] = "personal"`).
5. **(T2.c)** `apps/brain_web/src/components/shell/watched-folders-topbar-indicator.tsx`
   has a mount-time fetch (regex match for `useEffect` calling
   `fetch()` or similar) that runs when the component mounts AND the
   store is empty AND not currently fetching.
6. **(T2.d)** Unit test for the topbar indicator asserts that
   mounting the component when the store is empty triggers a fetch
   call.
7. **(T3)** `tasks/todo.md` row 23 marked ✅; `tasks/lessons.md` has
   a Plan 23 closure section; final stdout line is `PLAN 23 DEMO OK`.

## Tasks

### Theme A — Critical hot-fix

#### T1 — `list_watched_folders` `ValidationError` catch

**Files:**
- Modify: `packages/brain_core/src/brain_core/tools/list_watched_folders.py`
  — extend the existing `except FrontmatterError` clause in
  `_walk_watched_folder_counts` (around line 72; verify at exec time)
  to also catch `pydantic_core.ValidationError` (or
  `pydantic.ValidationError`; check the existing imports + project
  convention). Log via structlog at warning level with the bad note's
  path + the error message; continue the walk (skip the bad note from
  counts).
- Create or extend: `packages/brain_core/tests/tools/test_list_watched_folders.py`
  — regression-pin test for the ValidationError-handling branch.

**Goal:** Close the only Plan 22 production-crash risk.

**What to do:**
1. **Read the existing function** at exec time to confirm the helper
   name + line range. Plan-doc cites
   `_walk_watched_folder_counts` at line 72 (T16 outcome); verify per
   Plan 16/19/20 T5 grep-before-assuming lesson.
2. **Identify the right exception class.** Pydantic v2 exposes
   `pydantic.ValidationError` (public API) which is an alias for
   `pydantic_core.ValidationError` internally. Use whatever the rest
   of `brain_core` imports for consistency — likely `pydantic.ValidationError`.
3. **Extend the except clause.** Change `except FrontmatterError:` to
   `except (FrontmatterError, ValidationError):` (or split into two
   except blocks if you want different log messages per failure mode
   — but a single combined block with a clear log message is
   acceptable). Mirror the existing structlog call's shape.
4. **Regression-pin test.** Construct a `tmp_path` vault with:
   - Valid watched-folder note (good frontmatter).
   - Watched-folder note with malformed frontmatter that fails
     Pydantic strict validation (e.g., `orphaned: "yes"` instead of
     `orphaned: true`, OR an unknown field with `extra="forbid"` —
     pick whichever shape actually triggers `ValidationError` vs
     `FrontmatterError`; verify via a quick experiment).
   - Call `brain_list_watched_folders` via dispatch.
   - Assert: returns successfully; the bad note is NOT in the count;
     a structlog warning was captured (use `structlog.testing.capture_logs`).
5. **Verify the full brain_core suite** stays green (no regressions
   from the wider except).

**Per-task review:** combined spec + code-quality. Reviewer confirms
(a) the `ValidationError` import is the right class (Pydantic v2
public API or its internal alias — must match what `Frontmatter` /
`WatchedFolder` raise on validation failure); (b) the structlog
warning message includes both the note path + the error message
(diagnostic value); (c) the regression-pin test fails RED if the
except clause is reverted to `FrontmatterError`-only; (d) no behavior
change for the happy path (notes with valid frontmatter still count).

### Theme B — Bundled UX one-liners

#### T2 — activeDomain default + topbar mount-refresh

**Files:**
- Modify: `apps/brain_web/src/components/dialogs/watch-enable-modal.tsx`
  — change domain dropdown initial value from
  `config.domains[0]` to `config.active_domain` (or the equivalent
  selector — verify the existing store shape at exec time).
- Modify: `apps/brain_web/src/components/shell/watched-folders-topbar-indicator.tsx`
  — add a `useEffect` that calls
  `useWatchedFoldersStore.fetch()` on mount when:
  - The store's `folders` is empty AND
  - The store is not already in-flight (no concurrent fetch).
- Modify: `apps/brain_web/tests/unit/watch-modals.test.tsx` — add
  unit test asserting `activeDomain` is the default selected value
  in the watch-enable modal's domain dropdown.
- Modify: `apps/brain_web/tests/unit/topbar-watched-status.test.tsx`
  — add unit test asserting the indicator triggers a store fetch
  on mount when the store is empty.

**Goal:** Two visible UX improvements. Caught at Plan 22 controller-
verification + T16 implementer-flagged.

**What to do:**

**T2.a — activeDomain default**
1. Locate the domain-dropdown initialization in `watch-enable-modal.tsx`.
   T15 outcome notes the default uses `domains[0]`.
2. Read the existing `useDomainsStore` (or equivalent) selector
   pattern. There should be an `activeDomain` selector — Plan 12 / 13
   added it. Verify via grep.
3. Change the initial value to use `activeDomain` if present, fall
   back to `domains[0]` if not (defensive — `activeDomain` should
   always be set in production but tests may not set it).
4. Mockup reference: `docs/design/plan-22/modal-watch-enable.md`
   §"Form inputs" — Plan 22 plan-doc said "domain dropdown (pre-filled
   if available)"; T15 implementer noted the mockup-specified
   `activeDomain` default was not implemented. T2.a closes that gap.

**T2.b — Topbar mount-refresh**
1. Read the existing `watched-folders-topbar-indicator.tsx` to find
   its current data source. T14 outcome describes it as subscribing
   to `useWatchedFoldersStore.folders`.
2. Add a `useEffect` block that runs on mount + calls
   `useWatchedFoldersStore.fetch()` if `folders.length === 0` AND not
   currently fetching. This handles the case where the user lands
   directly on a non-Settings route — the indicator will populate
   itself instead of showing stale state.
3. Avoid double-fetching: respect the existing in-flight flag (T12's
   store has `state.loading` or similar — verify shape).
4. Edge case: if the user already triggered a fetch elsewhere (e.g.,
   Settings panel mount fired the fetch), the in-flight check
   prevents a duplicate concurrent fetch.

**Per-task verification (frontend per `feedback_tsc_vs_vitest.md`):**

```bash
cd apps/brain_web && pnpm vitest run --reporter=verbose tests/unit/watch-modals.test.tsx tests/unit/topbar-watched-status.test.tsx
cd apps/brain_web && pnpm tsc --noEmit
# Full suite for regression
cd apps/brain_web && pnpm vitest run
```

**Per-task review:** combined. Reviewer confirms (a) T2.a uses
`activeDomain` selector + defensive fallback; (b) T2.b mount fetch
respects in-flight flag (no double-fetch); (c) both unit tests fail
RED if the changes are reverted; (d) vitest + tsc clean.

### Closure

#### T3 — Closure: demo + lessons + todo + tag

**Files:**
- Create: `scripts/demo-plan-23.py` — assert each gate (~7 gates).
- Modify: `tasks/lessons.md` — append a Plan 23 closure section.
- Modify: `tasks/todo.md` — row 23 marked ✅; tail block refreshed as
  Plan 24 candidate scope.
- Tag: `plan-23-watched-folders-hotfix-ux` cut on green demo.

**Goal:** land Plan 23 closure following Plan 21 T3 / Plan 22 T17
shape.

**What to do:**
1. **`demo-plan-23.py`** asserts the 7 gates per D8. Mirrors Plan 22
   T17 / Plan 21 T3 structural-assertion pattern.
2. **Lessons.** Plan 23 closure section in `tasks/lessons.md`:
   - "Honest re-assessment of `critical` works." Plan 22 closure
     flagged 19 Plan 23 candidates; Plan 23 brainstorm narrowed to 1
     truly critical + 2 cheap wins. Avoiding the temptation to bundle
     all 19 kept Plan 23 shippable in 3 tasks.
   - "Pydantic v2 strict validation propagates to user-facing tools."
     T1 closes the gap where a single malformed frontmatter note
     crashed the entire watched-folders surface. Strict-validation
     errors should be caught at the tool-dispatch layer + degraded
     gracefully via structlog warnings, NOT propagated to the UI as
     crash payloads. **Rule:** tool dispatchers that walk the vault
     MUST catch both `FrontmatterError` and `ValidationError` when
     parsing per-note frontmatter; the walk skips bad notes + logs;
     the user sees a partial result instead of a crash.
   - "Plan 22 controller-verification at T15 pause caught a real UX
     bug." The activeDomain default was flagged at T15 implementer
     concern #2; controller's manual chrome session confirmed it; T2.a
     closes it. Validates the pause-cadence + browser-verification
     loop established in Plan 22.
   - "Topbar refresh contract." Components that subscribe to a store
     should ALSO fetch on their own mount if the store may be empty.
     Don't assume some other component populated the store first.
     Plan 23 T2.b closes this for the watched-folders topbar
     indicator; pattern applies to any future indicator-style
     components.
3. **todo.md update.** Row 23 ✅; tail block becomes "Plan 24
   candidate scope" with the 16 remaining Plan 22 carry-forwards +
   4 preserved NOT-DOING per D10.
4. **Tag.** `plan-23-watched-folders-hotfix-ux` cut on green
   `scripts/demo-plan-23.py` + green pytest + green vitest + green
   tsc.
5. **Push.** Per D3, after closure tag: single `git push origin main`
   covers all Plan 23 commits; explicit `git push origin <tag>` for
   the lightweight tag. User authorization required.

**Per-task review:** combined. Demo gate count ~7 per D8.

## Owning subagents

- **brain-core-engineer** — T1 (ValidationError catch + regression test
  in brain_core.tools), T3 (closure precedent from Plan 17/18/19/20/21/22).
- **brain-frontend-engineer** — T2 (UI fixes + vitest).

## Workflow rules

Same as Plans 16-22:
- Sequential per-task dispatch via `superpowers:subagent-driven-development`.
- Combined spec + code-quality review per task.
- No mid-plan pause (D9).
- No push without explicit user authorization at Plan 23 close (D3).
- pytest recipe per `feedback_uv_uf_hidden.md`:
  `find .venv -name "*.pth" | xargs -I{} chflags 0 {} 2>/dev/null; uv run pytest <args>`
  OR PYTHONPATH bypass per `feedback_uv_uf_hidden.md` 2026-05-12
  update section.
- Frontend per-task verification: `pnpm vitest run` AND
  `pnpm tsc --noEmit` per `feedback_tsc_vs_vitest.md`.
- Plan-author drift watch (Plan 16/19/20/22 lesson): implementers
  MUST grep before assuming a file/symbol location. Plan-doc cites
  `list_watched_folders.py:72` for T1; verify at exec time.

## File inventory (summary)

```
tasks/plans/
└── 23-watched-folders-hotfix-ux.md         # SELF (this doc)

packages/brain_core/
├── src/brain_core/tools/
│   └── list_watched_folders.py             # MODIFY: catch ValidationError (T1)
└── tests/tools/
    └── test_list_watched_folders.py        # MODIFY: add regression-pin test (T1)

apps/brain_web/
├── src/components/
│   ├── dialogs/watch-enable-modal.tsx      # MODIFY: activeDomain default (T2.a)
│   └── shell/watched-folders-topbar-indicator.tsx  # MODIFY: mount-time fetch (T2.b)
└── tests/unit/
    ├── watch-modals.test.tsx               # MODIFY: assert activeDomain default (T2.a)
    └── topbar-watched-status.test.tsx      # MODIFY: assert mount-time fetch (T2.b)

scripts/
└── demo-plan-23.py                         # CREATE (T3)

tasks/
├── lessons.md                              # MODIFY: Plan 23 closure section (T3)
└── todo.md                                 # MODIFY: row 23 ✅ + Plan 24 candidate (T3)
```

## T1 outcome

_Filled in at T1 close. ValidationError import + class verified;
regression-pin test path + count; brain_core full-suite delta._

## T2 outcome

_Filled in at T2 close. activeDomain default fix + topbar mount-fetch
fix; vitest + tsc clean; per-test fail-RED-on-revert verified._

## T3 outcome

**Status:** DONE (2026-05-12, brain-core-engineer).

**Files created:**
- `scripts/demo-plan-23.py` (~365 LOC) — 7-gate closure demo. Cached
  file reads, single-purpose gate functions, fail-fast main loop;
  mirrors `demo-plan-21.py` shape (smallest demo since Plan 21).

**Files modified:**
- `tasks/lessons.md` — appended `## Plan 23` closure section (6
  lessons + handoff paragraph) per the lesson template.
- `tasks/todo.md` — row 23 marked `✅ Complete` with deliverable
  summary; tail block refreshed from "Plan 23 candidate scope" to
  "Plan 24 candidate scope" with 16 items (down from Plan 22's 19 by
  the 3 Plan 23 closed: T1 + T2.a + T2.b). 4 sections (UX polish /
  architectural / dev-loop friction / preserved NOT-DOING).
- `tasks/plans/23-watched-folders-hotfix-ux.md` — this T3 outcome
  block + `## Review` section appended at EOF.

**Demo verification:**
```
$ unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src \
    uv run python scripts/demo-plan-23.py
  ok Gate 1 — T1.a ValidationError catch: ...
  ok Gate 2 — T1.b regression pin: ...
  ok Gate 3 — T2.a activeDomain default: ...
  ok Gate 4 — T2.b activeDomain default test: ...
  ok Gate 5 — T2.c topbar mount-fetch: ...
  ok Gate 6 — T2.d topbar mount-fetch test: ...
  ok Gate 7 — T3 closure: ...

PLAN 23 DEMO OK
```

**Gate density:** 7 gates per plan-doc D8 (~6-8 target). 2 gates per
substantive task (code-content + test-existence) + 1 closure gate.
Matches the plan-doc §"Demo gate description" mapping exactly (T1.a,
T1.b, T2.a, T2.b, T2.c, T2.d, T3).

**Tag:** `plan-23-watched-folders-hotfix-ux` (lightweight, per project
convention) cut after the green demo. NOT PUSHED per D3 — single
`git push origin main` + explicit `git push origin <tag>` requires
user authorization at Plan 23 close.

## Review

**Status:** ✅ Complete — tag `plan-23-watched-folders-hotfix-ux` cut at T3 HEAD on 2026-05-12. Push deferred per D3 (user authorization required at Plan 23 close).

**Closure summary.** Smallest plan since Plan 21 (3 tasks). Plan 22 closed 2026-05-12 with 19 carry-forward candidates; Plan 23 brainstorm honestly re-assessed and narrowed scope to 1 truly critical (the `list_watched_folders` `ValidationError` catch gap surfaced at T16) + 2 cheap UX one-liner wins flagged at Plan 22 T15 implementer + controller-verification pauses. The remaining 16 items roll into Plan 24 candidate scope at Plan 22-end priority levels — nothing lost, everything just-in-time. **Theme A — Critical hot-fix (T1).** `_walk_watched_folder_counts` in `packages/brain_core/src/brain_core/tools/list_watched_folders.py` extended to catch `pydantic.ValidationError` alongside the existing `FrontmatterError`. Pre-T1 a single malformed-frontmatter watched-folder note in the vault crashed the Settings → Watched folders tab + Topbar indicator (Plan 22 T16 surfaced this via Playwright `purgeWatchedFolderPollution` cleanup helper — the defensive workaround was evidence the failure mode was real). T1 outcome split the existing single `except (OSError, UnicodeDecodeError, FrontmatterError):` block into two: silent skip for transient I/O + warn-and-skip for content corruption — adding observability for the previously-silent `FrontmatterError` branch as a v1.5 improvement bundled with the v1 crash fix. Regression-pin test `test_validation_error_note_skipped_without_crash` at `test_list_watched_folders.py:153` uses `structlog.testing.capture_logs` to assert warn-event + path + error fields populated; RED-on-revert verified. brain_core: 1156 → 1157 passed (+1). **Theme B — Bundled UX one-liners (T2).** T2.a — watch-enable modal domain dropdown initial value changed from `domains[0]?.slug` to `activeDomain || domains[0]?.slug ?? "research"`. Applied to BOTH the `useState` lazy initializer AND the post-resolve hydration `useEffect` so activeDomain wins regardless of data-loading order. T2.b — topbar indicator added `loaded` selector + `React.useEffect` block that fires `void refresh()` when `!loaded`. Chose `!loaded` gate over plan-doc's literal `folders.length === 0` phrasing — the literal would re-fetch forever for zero-watched-folder users; `!loaded` correctly stops firing once the store resolves. Matches `useDomains()` first-mount auto-refresh precedent at `use-domains.ts:117-121`. brain_web: 585 → 586 passed (+6 new tests across watch-modals.test.tsx + topbar-watched-status.test.tsx). **Closure (T3).** `scripts/demo-plan-23.py` 7-gate demo prints `PLAN 23 DEMO OK`.

**Verification receipts.**

- `scripts/demo-plan-23.py` — 7/7 gates pass; final stdout `PLAN 23 DEMO OK`.
- `packages/brain_core/tests/tools/test_list_watched_folders.py` — 5 → 6 tests pass (+1 `test_validation_error_note_skipped_without_crash`).
- `apps/brain_web/tests/unit/watch-modals.test.tsx` — 24 → 27 tests pass (+3 T2.a default-activeDomain pin tests).
- `apps/brain_web/tests/unit/topbar-watched-status.test.tsx` — 16 → 19 tests pass (+3 T2.b mount-fetch pin tests; 2 pre-existing tests repaired in place).
- `apps/brain_web/tests/unit/scope-picker-set-as-default.test.tsx` — 5 tests pass (mock extension only; no test count change).
- `pnpm tsc --noEmit` clean on brain_web post-T2.

**Bumps and deltas.** Zero spec rollback risk. Zero schema changes. Zero new external dependencies. Backend surface: +1 except-tuple member (`pydantic.ValidationError`) on `_walk_watched_folder_counts` + 1 structlog warning event (`watched_folder_note_frontmatter_invalid`). Frontend surface: +1 useDomains() destructure (`activeDomain`) in `watch-enable-modal.tsx` + 1 mount-time `useEffect` in `watched-folders-topbar-indicator.tsx`. Test surface: +1 brain_core test + +6 brain_web tests (3 watch-modals + 3 topbar mount-fetch). No tool surface change (45 tools unchanged from Plan 22).

**Backlog forward (Plan 24 candidate scope).** See `tasks/todo.md` tail block. 16 items across 4 sections (priority order): 7 UX polish (native folder picker, AbortController on confirm, cross-store reconcile, orphans-only topbar coverage gap, Open-in-Finder backend, bulk action progress, OrphanEntry fields, topbar entrance transition), 4 architectural (`_build_pipeline` 4-site dup, `_watched_folders_changed` cross-package dup, brain_api + brain_mcp parallel watchers, Stage-4 archive deferral), 1 dev-loop friction (workspace editable flip), 4 preserved NOT-DOING items (unchanged since Plan 17). Plan 24 will be authored just-in-time once the user reviews + locks scope. Plan 24 trigger candidates: a real ValidationError-class crash in a different tool dispatcher would re-prioritize the catch-extension pattern across the tool registry; a 4th `_build_pipeline` call site would re-prioritize the factory lift.

---

**End of Plan 23.**

## Plan 24 candidate scope

Filled in at T3 closure. The canonical record is the tail block of
`tasks/todo.md`. Per D7 + D10, the 16 Plan 22 carry-forwards that
Plan 23 did NOT address (including the 4 preserved NOT-DOING) roll
into Plan 24 candidate scope unchanged:

**From Plan 22 carry-forward (16 items remaining):**
- UX polish (7): native folder picker, AbortController on confirm
  in-flight, cross-store reconcile (orphan_count stale), orphans-only
  topbar state coverage gap, Open-in-Finder backend helper, bulk
  action progress feedback, OrphanEntry lacks last_synced_at + title
  fields, topbar 200ms entrance transition.
- Architectural (4): `_build_pipeline` 4-site duplication,
  `_watched_folders_changed` cross-package duplication, brain_api +
  brain_mcp parallel watchers → duplicate log entries,
  Stage-4 archive deferral (handler API extract-without-archive
  split).
- Dev-loop (1): workspace `editable = true` flip for brain_api /
  brain_mcp / brain_cli.

**Preserved Plan 17/earlier NOT-DOING (unchanged):**
- `seedBrainMd` / `seedScope` helper extraction (rule-of-three at
  3/5 callers).
- Per-thread cross-domain confirmation (architectural NO per Plan
  16 D36).
- Topbar scope chip drift watch (lesson-only per Plan 12).
- PEP 703 free-threaded Python `_cached_ctx` (3.14 timeline trigger).

These are NOT a Plan 24 commitment — Plan 24 is just-in-time
authored when triggered.

## T1 outcome

**Status:** DONE (2026-05-12, brain-core-engineer).

**Files modified:**
- `packages/brain_core/src/brain_core/tools/list_watched_folders.py`
  — added `import structlog` + `from pydantic import ValidationError`
  + `logger = structlog.get_logger(__name__)`; split existing single
  `except (OSError, UnicodeDecodeError, FrontmatterError)` into two
  blocks — silent skip for I/O errors (unchanged behavior); warning
  log + skip for `(FrontmatterError, ValidationError)` (new
  observable + crash-proof). Helper docstring updated to cite Plan
  23 T1. Net source delta: +13 LOC, -1 LOC.
- `packages/brain_core/tests/tools/test_list_watched_folders.py` —
  added `structlog.testing.capture_logs` import + new test
  `test_validation_error_note_skipped_without_crash` (+72 LOC).

**Helper location verified:** `_walk_watched_folder_counts`
declared at line 47 (pre-change) / line 52 (post-change). Plan-doc
cited "line 72" — that was actually the `except` line, not the
function def line. Existing 5-test file + structure unchanged.

**ValidationError class:** `from pydantic import ValidationError`.
Verified `pydantic.ValidationError is pydantic_core.ValidationError`
returns `True` (Pydantic v2 public alias for the internal Rust-
implemented class). Used the public `pydantic` import for
consistency with the rest of the codebase (the module already
imports from `pydantic`, not `pydantic_core`).

**Single combined except vs split:** Split into two except blocks.
Rationale: `OSError` / `UnicodeDecodeError` are transient I/O
failures that aren't actionable for ops (file moved/deleted mid-
walk, encoding edge cases) — preserving the existing silent-skip
keeps log noise down. `FrontmatterError` / `ValidationError` are
diagnostic content-corruption signals that ops will want to see —
adding a warning for the new class while leaving the existing
class silent would be inconsistent. Bundling them gives uniform
observability for "this note's frontmatter is broken — please fix
or migrate" diagnosis. Net: 2 LOC more than a single combined
except with one log call, but clearer intent and avoids surprise
log spam for transient I/O.

**Test approach:** Test seeds a vault with one valid watched-folder
note + one note whose frontmatter is valid YAML (so
`parse_frontmatter` does NOT raise `FrontmatterError`) but has
`type: "not-a-valid-literal"` which fails Pydantic's `Literal`
enforcement at `Frontmatter.model_validate`. This is the cleanest
ValidationError-specific shape (vs `FrontmatterError`-specific
shape which would be e.g. unterminated `---` fence). Test asserts:
(a) handle returns successfully (no uncaught exception); (b) bad
note skipped from `file_count`; (c) good note still counted; (d)
exactly one structlog warning captured with event name + `path` +
`error` fields populated; (e) `log_level == "warning"`.

**RED verification:** Stashed source change, re-ran new test —
failed RED with `pydantic_core._pydantic_core.ValidationError`
escaping uncaught from `Frontmatter.from_dict`. Restored fix —
test passes GREEN. Confirms the test fails RED if the
`ValidationError` catch is reverted.

**Test counts:** `packages/brain_core/tests/tools/test_list_watched_folders.py`
5 → 6 tests, all passing. Brain_core full suite baseline 1156 →
1157 passed (+1), 5 skipped (unchanged), 0 failures.

**mypy:** Clean on the changed file.

**Commit cadence:** Single `fix(plan-23)` commit per Plan 23 D3
(no push). Plan-doc receipts appended in a separate
`docs(plan-23)` commit.

## T2 outcome

**Status:** DONE (2026-05-12, brain-frontend-engineer).

**Files modified:**
- `apps/brain_web/src/components/dialogs/watch-enable-modal.tsx` —
  T2.a: changed domain dropdown initial value from
  `domains[0]?.slug ?? "research"` to
  `activeDomain || domains[0]?.slug ?? "research"`. Pulled
  `activeDomain` from existing `useDomains()` hook (Plan 12 T5 / Plan
  11 T6 already exposed it). Updated post-resolve hydration useEffect
  to mirror the same precedence (`activeDomain || domains[0]!.slug`).
  Net source delta: +13 LOC, -2 LOC (mostly rationale comment).
- `apps/brain_web/src/components/shell/watched-folders-topbar-indicator.tsx`
  — T2.b: added `loaded` selector + `useEffect` block that fires
  `void refresh()` when `!loaded`. Matches the `useDomains()`
  first-mount auto-refresh pattern (Plan 12 T5). Net source delta:
  +22 LOC, -0 LOC (mostly rationale comment).
- `apps/brain_web/tests/unit/watch-modals.test.tsx` — added
  `_setDomainsCacheForTesting` import + 3 new tests under WatchEnableModal
  describe: (1) defaults to activeDomain when set, (2) defensive
  fallback to `domains[0]` when activeDomain is empty, (3)
  `prefilledDomain` overrides activeDomain default (the Bulk Import →
  Watch bridge). 24 → 27 tests in file. +120 LOC.
- `apps/brain_web/tests/unit/topbar-watched-status.test.tsx` — added
  default `listWatchedFoldersMock.mockResolvedValue` in `beforeEach`
  + fixed two pre-existing tests broken by the new mount-fetch
  (empty-state was relying on `loaded: false` + no mock = crash;
  error-state was asserting call-count-of-1 but mount now fires once
  before click). Added new "Plan 23 T2.b mount-fetch" describe with
  3 spy-on-refresh tests: (1) refresh fires when `loaded === false`,
  (2) does NOT re-fire when `loaded === true`, (3) does NOT re-fire
  when `loaded === true` with empty folders (regression-pin against
  weakening the gate to `folders.length === 0`). 16 → 19 tests in file.
  +83 LOC, -5 LOC.
- `apps/brain_web/tests/unit/scope-picker-set-as-default.test.tsx` —
  extended `@/lib/api/tools` mock to include `listWatchedFolders` so
  the Topbar render in this test file doesn't crash on the new
  mount-fetch. Resolves with empty folders; per-test overrides not
  needed (scope-picker tests don't care about watched-folder shape).
  +13 LOC.

**T2.a activeDomain selector + defensive fallback:** Pulled via
`useDomains()` hook destructure (existing API since Plan 11 T6,
formalized in Plan 12 T5's selector). Hook returns
`{ domains, activeDomain, loading, error, refresh }`. The
`useDomains()` selector reads from `useDomainsStore.activeDomain`
which is `string` (empty string until first hydration, or against a
pre-Plan-11-T6 backend). Defensive fallback shape:
`activeDomain || domains[0]?.slug ?? "research"`. Three-stage
fallback handles: (1) hydrated active_domain (happy path), (2) empty
activeDomain + populated domains list (defensive — tests + pre-T6
backend), (3) empty domains list (last-resort literal matching the
setup wizard's default).

**T2.b in-flight flag + useEffect dependency array:** The store's
in-flight serialization is a module-private `inFlightPromise`, NOT a
state field. The store's own `refresh()` action handles dedup
internally (`if (inFlightPromise) return inFlightPromise`), so the
component just calls `refresh()` — concurrent fetches from peer
mounts (e.g., Settings panel + topbar in the same render tree) only
trigger one network call. Gate at the component level uses the
`loaded` state field (matches `useDomains()` first-mount auto-refresh
precedent at `apps/brain_web/src/lib/hooks/use-domains.ts:117-121`).
Dep array: `[loaded, refresh]`. `refresh` is a zustand action with
stable reference per store lifetime, so the effect re-runs only when
`loaded` flips false → true (post-fetch) or via test seam
`_resetForTesting`. Chose `!loaded` over the plan-doc's literal
`folders.length === 0 && !in-flight` phrasing: the plan-doc gate
would re-fetch forever for a user whose vault legitimately has zero
watched folders (loaded=true, folders=[] → empty check trips on every
mount). `!loaded` correctly stops firing once the store resolves —
matched by the third regression-pin test.

**Test count delta:**
- `watch-modals.test.tsx`: 24 → 27 (+3 T2.a tests).
- `topbar-watched-status.test.tsx`: 16 → 19 (+3 T2.b tests).
- `scope-picker-set-as-default.test.tsx`: 5 → 5 (no new tests; mock
  extension only).
- brain_web full suite: 585 → 586 passed (+6 new) — net 586 in
  full-suite count because the existing T14 file's empty-state test
  and error-state test split / no-longer-pass-with-old-assertions
  were repaired in place (not new tests).

**RED-on-revert verification:** `git stash push` reverted both source
files. Re-ran `pnpm vitest run tests/unit/watch-modals.test.tsx
tests/unit/topbar-watched-status.test.tsx`:
- T2.a "defaults to activeDomain (not domains[0])" — **FAILED RED**
  with the trigger text reading `"research"` (the alphabetically-first
  `domains[0]`) instead of the seeded activeDomain `"work"`. Confirms
  the activeDomain default fix is load-bearing.
- T2.b "fires refresh() on mount when loaded === false" — **FAILED
  RED** with `expected "spy" to be called 1 times, but got 0 times`
  because the pre-T2.b indicator had no mount-effect. Confirms the
  useEffect is load-bearing.
- The defensive-fallback test (T2.a "falls back to domains[0]") and
  the "does NOT re-fire" tests (T2.b regression-pins) STILL PASS on
  the reverted source — they pin behavior that existed before the fix
  too (defensive paths + absence-of-fetch). This is correct: those are
  regression-pins guarding the gate from weakening, not tests of new
  behavior.

`git stash pop` restored sources; full suite re-runs green.

**Vitest + tsc clean:** Full brain_web vitest 586 passed (1 skipped),
0 failures. `pnpm tsc --noEmit` clean (no output).

**Pre-existing test repair note:** Two tests in
`topbar-watched-status.test.tsx` needed updates because the new
mount-fetch changes their preconditions:
- Empty-state test (L192-199 pre-edit) previously rendered with
  default state and never called `listWatchedFolders`. Post-T2.b it
  fires the mount-fetch; needed a default `mockResolvedValue` in
  `beforeEach`.
- Error-state test (L303-334 pre-edit) asserted exactly one
  `refresh` call after click. Post-T2.b the mount-effect fires
  `refresh` once before the click, so the click adds a second call.
  Updated assertion to delta-against-post-mount-count.
Both repairs are mechanically forced by T2.b — they don't soften any
pin.

**Microtask race lesson (informational):** Initial T2.b test
implementation used `listWatchedFoldersMock` call-count assertions
and failed in sibling-test order even though it passed in isolation.
Diagnosis: the previous test's mount-fetch leaves a pending Promise
whose `.then` mutates `useWatchedFoldersStore.loaded` AFTER
`beforeEach`'s `_resetForTesting()` runs but BEFORE the new test's
render — a `useEffect` deps capture-time race. Refactored to spy on
the store's `refresh` action directly (matching the existing T14
error-state spy pattern at L304) which decouples the assertion from
the store's internal in-flight Promise lifecycle entirely. Cleaner
and more robust regardless of microtask ordering. Worth noting in
`tasks/lessons.md` at plan close if not already covered.

**Commit cadence:** Single bundled `fix(plan-23)` commit per Plan 23
D3 (no push). Plan-doc receipts appended in a separate
`docs(plan-23)` commit.
