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

_Filled in at T3 close. Demo gate count + commits + tag SHA._

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

## Review

_Filled in at T3 close. Tag SHA + closure summary + bumps +
verification receipts + backlog forward._

---

**End of Plan 23.**
