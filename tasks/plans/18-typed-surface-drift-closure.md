# Plan 18 — Typed-surface drift closure

**Authored:** 2026-05-11 (post Plan 17 close on 2026-05-11, tag
`plan-17-residuals-and-spec-annotations` at `d48725d`).
**Scope:** Closure of the Plan 17 T16 review carry-forward — the
`recent()` typed-wrapper-vs-runtime drift in `apps/brain_web/src/lib/api/tools.ts`
that silently drops rows in `draft/doc-picker-dialog.tsx` when a scope
filter is active (and throws `TypeError` the moment the user types in
the search box) — PLUS a sibling-drift audit of the rest of `tools.ts`
to catch the class, not just the instance.
**Shape:** 4 substantive tasks + 1 closure task across 2 themes.
Mirrors Plan 17 D2 / Plan 16 D35: per-task ~20-100 LOC PR budget;
combined spec + code-quality review per task.

## At a glance

- **Theme A — Typed-surface drift closure** (T1-T3): fix the
  surfaced `recent()` bug, audit `tools.ts` for sibling typed-wrapper
  drift, and fix any findings (or close audit-only with a
  `RecentEntry` structural drift-pin if findings are zero).
- **Theme B — Plan 17 residual close-out** (T4): close the T36
  stale-docstring candidate as ALREADY-DONE (Plan 17 T10 precedent
  — grep verification.).
- **Closure** (T5): demo + lessons + todo.md + tag
  `plan-18-typed-surface-drift-closure`.

## Why this plan exists (1-paragraph)

Plan 17 T16 aligned the `brain_recent` backend on the `items` field
across backend + frontend and **flagged** the residual TypeScript
typed-wrapper drift in `tools.ts` — `RecentEntry` declares
`{path, title, modified, domain}` but the backend handler emits
`{path, modified_at}`. `browse-screen.tsx:233-248` reconstructs the
richer shape locally via `slugOf()` + `domainOf()` helpers and works
correctly; `draft/doc-picker-dialog.tsx:88` reads `it.domain` (silent
drop when `scope` is non-empty) and `:107` reads `it.domain.toLowerCase()`
(TypeError when the search box is non-empty). Plan 17 T16 review
classified this as MEDIUM severity but out of T16's scope; the
follow-up landed in `tasks/todo.md`'s Plan 18 candidate scope tail
block. Plan 18 closes the surfaced bug AND audits the rest of
`tools.ts` for the same class of drift — Plan 16 T6's lesson ("when
one store has a known race shape, audit ALL sibling stores for the
same shape") applies analogously to typed-wrapper surfaces.

## Locked decisions

| # | Decision | Status | Why |
|---|---|---|---|
| D1 | **`recent()` fix direction: narrow TS to backend reality** `{path, modified_at}`. Callers reconstruct `domain`/`title`/`modified` locally as `browse-screen.tsx:233-248` already does. | locked (user) | Smallest diff; backend remains source of truth. Option 1.B (widen backend) would change the `brain_recent` public surface and affect MCP consumers — wrong direction. Plan 17 T16 already locked "backend drives" when aligning the `items` field. |
| D2 | **T2 audit deliverable: append findings inline to this plan doc.** "T2 audit findings" section with one row per interface + verdict. | locked (user) | Plan 17 T9 precedent. Audit findings are point-in-time observations; the plan doc is their natural home. Option 2.B (separate report file) sprawls; option 2.C (JSON manifest) is an awkward shape for prose. |
| D3 | **T3 zero-findings outcome: audit-only + structural drift-pin for `RecentEntry`.** Docstring updates on every audited interface noting "audited against backend on 2026-05-11"; PLUS Plan 17 T6's fixture pattern scoped to `RecentEntry` only (fixture at `apps/brain_web/tests/fixtures/recent-entry-shape.json` checked by both a Python pin against the `brain_recent` handler and a TS pin against the `RecentEntry` interface). | locked (user) | Future-proofs the specific boundary that surfaced this class of bug without trying to boil the ocean across all 34 tools (option 3.C). Pure audit-only (option 3.A) leaves the next implementer relying on grep-and-pray. Plan 18 stays small; Plan 19 can decide whether to extend the drift-gate pattern to all 34 tools based on T2's findings. |
| D4 | **Demo gate: per-item closure assertion, no gate-count target.** | locked per Plan 17 D7 | Plan 17 D7 precedent — gate count is not pinned. T3 demo gate branches on T2's verdict (zero-findings ⇒ assert structural pin exists; 1+ findings ⇒ assert each fix landed). |
| D5 | **Per-task review: combined spec + code-quality.** Combined review held across 47 tasks in Plan 16; 18 in Plan 17. | locked per Plan 16 D35 / Plan 17 D2 | No reason to re-litigate at the Plan-11/Plan-15 polish-pass scale. |
| D6 | **No new dependencies.** Plan 18 ships zero new pip / npm packages. | locked per Plan 17 D6 | All Plan 18 work is closure / audit / docs / fix. |
| D7 | **Push 30 commits (Plans 16 + 17 + 18) AFTER Plan 18 closes.** Single `git push` covers all three plans at Plan 18 close. | locked (user) | Single decision point; lets CI surface any bundle-level residuals at one time. The risk of waiting is low — local work is tagged and `git log` shows the closure stack clearly. |
| D8 | **Sequential subagent dispatch via `superpowers:subagent-driven-development`.** | locked per Plan 16 D2 / Plan 17 D3 | Combined review per task plus sequential dispatch held across two prior plans at the polish-pass scale. |

## Tech stack

Same as Plans 16 + 17: Python 3.12, pydantic v2, mypy --strict, ruff,
vitest, Playwright. No new tools. No new dependencies. CI runs on
macos-14 + windows-2022 per Plan 14's matrix.

## Demo gate description

`scripts/demo-plan-18.py` asserts, in sequence:

1. **(T1.a)** `apps/brain_web/src/components/draft/doc-picker-dialog.tsx`
   contains no `it.domain` or `it.modified` reads — `rg "\\bit\\.(domain|modified)\\b"
   apps/brain_web/src/components/draft/doc-picker-dialog.tsx` returns
   zero lines (filtering for direct reads, not comments).
2. **(T1.b)** `apps/brain_web/src/lib/api/tools.ts`'s `RecentEntry`
   interface declares only `path` and `modified_at` — regex match on
   the interface body.
3. **(T2)** `tasks/plans/18-typed-surface-drift-closure.md` contains a
   non-empty `## T2 audit findings` section (markdown table with ≥1
   row).
4. **(T3)** Branch on the verdict captured in T2's section:
   - If T2 found **0 sibling drifts**: assert
     `apps/brain_web/tests/fixtures/recent-entry-shape.json` exists;
     assert `packages/brain_core/tests/test_recent_entry_drift.py`
     exists and passes when invoked; assert
     `apps/brain_web/tests/unit/recent-entry-drift.test.ts` exists.
   - If T2 found **1+ sibling drifts**: assert each finding's fix
     commit landed (per-finding assertion derived from T2 findings
     rows).
5. **(T4)** `tasks/plans/18-typed-surface-drift-closure.md` has a
   `## T4 outcome` section that states ALREADY-DONE and grep across
   `packages/brain_core/tests/` for the stale wording returns 0 hits.
6. **(T5)** `tasks/todo.md` row 18 marked ✅; `tasks/lessons.md` has a
   Plan 18 closure section; final stdout line is `PLAN 18 DEMO OK`.

## Tasks

### Theme A — Typed-surface drift closure

#### T1 — `recent()` typed-wrapper drift fix + doc-picker bug

**Files:**
- Modify: `apps/brain_web/src/lib/api/tools.ts` — narrow `RecentEntry`
  interface to `{path: string; modified_at: string}`; update the
  `recent` wrapper's return-type annotation to match
  (`Promise<ToolResponse<{items: RecentEntry[]}>>`); update the
  header doc comment to note the post-Plan-17/T16 alignment.
- Modify: `apps/brain_web/src/components/browse/browse-screen.tsx`
  — currently reconstructs the wider shape inline at lines 232-248
  via `slugOf(...)` and `domainOf(...)` against the narrower row. Once
  `RecentEntry` narrows, browse-screen needs a local display type
  (recommend: `type BrowseRowDisplay = {path, title, modified, domain}`)
  declared near the file's other local types. The reconstruction
  helpers stay. Existing tests should not need changes (the display
  shape is unchanged from the user's perspective).
- Modify: `apps/brain_web/src/components/draft/doc-picker-dialog.tsx`
  — locked fix shape uses path-prefix matching directly (no helper
  reconstruction needed):
  - **Line 88 scope filter:** replace
    `all.filter((it) => scope.includes(it.domain))` with
    `all.filter((it) => scope.some((s) => it.path.startsWith(s + "/")))`.
    Path-prefix is the source-of-truth for which-domain-a-row-belongs-to;
    the previous `it.domain` read was indirection-via-derived-field.
  - **Line 107 search filter:** drop the `|| it.domain.toLowerCase().includes(n)`
    clause. Path already contains the domain slug as the first segment
    (`research/foo.md`), so a search query of `research` matches via
    `it.path.toLowerCase().includes(n)` directly — the OR-clause is
    redundant under the path-prefixed layout.
  - **Line 188** uses `(d as RecentEntry & { words?: number }).words ?? 0` —
    `words` is never emitted by the backend so this is dead-code-ish
    (defaults to 0 unconditionally). Out of T1 scope; leave alone
    unless the implementer flags an interaction with the narrow.
- Create or modify: `apps/brain_web/tests/unit/doc-picker-dialog.test.tsx`
  — add a regression test that mocks `recent()` to return rows with
  the **real** backend shape (`{path, modified_at}` only — no
  `domain`, no `title`, no `modified`) and asserts (a) `scope`-based
  filtering correctly drops or keeps rows based on path-prefix;
  (b) the search-box filter doesn't throw `TypeError` on rows with
  undefined `domain`.

**Goal:** close the MEDIUM-severity production bug surfaced in Plan 17
T16's review. Backend remains source of truth; TS interface narrows
to match.

**What to do:**
1. **Narrow `RecentEntry`** at `tools.ts:43-48`.
2. **Update `browse-screen.tsx`** to use a local `BrowseRowDisplay`
   type for the post-reconstruction shape; the reconstruction code at
   lines 232-248 stays intact.
3. **Fix `doc-picker-dialog.tsx`** to either reconstruct `domain`
   locally or refactor the scope filter to use path-prefix matching
   directly. Adjudicate the cleaner shape during implementation.
4. **Pin test** in `tests/unit/doc-picker-dialog.test.tsx` against
   the real backend shape.
5. **Verify** by running the existing doc-picker test suite + the
   new regression test.

**Per-task review:** combined spec + code-quality. Reviewer must
verify (a) the regression test fails RED on the pre-fix code (mock
the OLD code; confirm scope filter drops rows); (b) the regression
test passes GREEN on the post-fix code; (c) no other consumer of
`RecentEntry` was missed (grep across `apps/brain_web/src/` for
`RecentEntry` references and check each one's expectations).

#### T2 — `tools.ts` sibling typed-wrapper-vs-runtime drift audit

**Files:**
- Modify (findings only): `tasks/plans/18-typed-surface-drift-closure.md`
  — append a `## T2 audit findings` section with one row per
  interface + verdict (drift YES/NO + nature of drift if YES).

**Goal:** audit every typed interface in `apps/brain_web/src/lib/api/tools.ts`
against the actual backend handler's `ToolResult.data` shape. Plan 16
T6's lesson — "when one store has a known race shape, audit ALL
sibling stores for the same shape" — applies analogously: `recent()`
is symptomatic; the audit catches the class.

**What to do:**
1. **Enumerate.** List every exported `interface` / `type` declaration
   in `tools.ts` that's directly used as a `callTool` return-type
   parameter:
   - `SearchHit` → `brain_search`
   - `RecentEntry` → `brain_recent` (just fixed in T1)
   - `PendingPatch` → `brain_list_pending_patches`
   - `RecentIngestEntry` → `brain_recent_ingests`
   - `ChatThreadEntry` → `brain_list_threads`
   - `BackupEntry` → `brain_backup_list`
   - `RepairConfigStep` / `RepairConfigData` → `brain_repair_config`
   - inline `ToolResponse<{...}>` shapes embedded in callTool sites
     (e.g., `listDomains`, `getIndex`, `readNote`, `forkThread`,
     ingest tools, write/patch tools, maintenance tools, MCP / API-
     key / backup / domain tools)
2. **Verify.** For each, locate the backend handler
   (`packages/brain_core/src/brain_core/tools/<tool>.py` or its
   sibling under brain_api/brain_mcp) and read the actual
   `ToolResult(data={...})` construction. Compare key sets:
   - TS-declared keys present in backend? ✓ or ✗
   - Backend-emitted keys present in TS? ✓ or ✗ (extra-in-backend is
     drift too — TS callers can't read them)
   - Type compatibility (string vs number vs nullable etc.)?
3. **Categorize verdicts:**
   - **OK** — TS and backend agree exactly.
   - **MINOR** — TS has optional fields backend doesn't emit; runtime
     reads degrade gracefully (e.g., `?: extra` patterns). NOT a fix
     candidate.
   - **DRIFT** — TS declares required fields backend doesn't emit
     (or vice versa). T3 fix candidate.
4. **File findings** as a markdown table appended to this plan doc
   under `## T2 audit findings`. Columns: TS interface | Backend tool
   | Verdict | Notes.

**Per-task review:** combined spec + code-quality. The audit
deliverable is the markdown table; reviewer confirms the verdicts
spot-check correctly against the backend code (sample 3-4 random rows
and re-derive verdict).

#### T3 — Fix drift findings or audit-only close with structural pin

**Files (branches on T2 verdict):**

**If T2 found 0 sibling DRIFT-class findings:**
- Create: `apps/brain_web/tests/fixtures/recent-entry-shape.json`
  — JSON fixture mirroring Plan 17 T6's `autonomy-categories.json`
  shape. Content: `{"keys": ["path", "modified_at"]}`.
- Create: `packages/brain_core/tests/test_recent_entry_drift.py`
  — Python pin reading the fixture and asserting the keys in the
  `brain_recent` handler's `ToolResult.data["items"][0]` exactly
  match. Use a minimal vault fixture (one domain, one note) to
  trigger the handler.
- Create: `apps/brain_web/tests/unit/recent-entry-drift.test.ts`
  — TS pin reading the fixture and asserting the `RecentEntry`
  interface's literal keys (via a small `keyof RecentEntry` helper)
  match. Mirror Plan 17 T6's `autonomy-category-drift.test.ts`.
- Modify (light): each TS interface audited in T2 — add a one-line
  JSDoc note: `/** Audited against backend handler on 2026-05-11
  (Plan 18 T2). */` or equivalent. Documents the audit boundary
  without adding runtime cost.

**If T2 found 1+ DRIFT-class findings:**
- For each finding: modify the TS interface OR backend handler
  (whichever direction the implementer + reviewer pick per the same
  "backend is source of truth" principle as T1's D1; only deviate
  with an explicit per-finding adjudication noted in plan doc).
- For each finding: add a regression pin test (Python or TS) that
  fails on a reintroduction of the drift. Pattern: a minimal handler-
  invocation test asserting the keys in the returned `data` dict.
- Skip the RecentEntry-specific structural pin (the per-finding pins
  cover the same shape more broadly).

**Goal:** close the audit cleanly — either ship the drift fixes with
per-finding regression pins, or ship audit-only with structural
protection for the specific surface that drove this plan.

**What to do:**
1. **Read T2 findings.** Count DRIFT-class rows.
2. **Branch.** Zero-findings ⇒ ship the RecentEntry fixture + Python
   pin + TS pin + docstring sweep. One-or-more findings ⇒ fix each
   + regression pin per finding; skip the standalone fixture.
3. **Append `## T3 outcome`** to this plan doc explaining the branch
   taken and per-finding receipts.

**Per-task review:** combined spec + code-quality. If zero-findings:
reviewer confirms the Python + TS pins both fail RED if the fixture
keys are mutated (drift simulation). If 1+ findings: reviewer
confirms per-finding pin tests fail RED if the drift is reintroduced.

### Theme B — Plan 17 residual close-out

#### T4 — Close T36 stale-docstring candidate as ALREADY-DONE

**Files:**
- Modify: `tasks/plans/18-typed-surface-drift-closure.md` — append a
  `## T4 outcome` section documenting the verification.

**Goal:** Plan 17 candidate list included a "T36 stale docstring at
`test_config_set_persists.py:445`" item ('Config doesn't enable
validate_assignment' — wrong post-T36; T36 reviewer recommended 1-
line follow-up commit"). Pre-plan-write audit found that the
grep for the stale wording (`"doesn't enable validate_assignment"`,
`"NOT enable validate_assignment"`, `"without validate_assignment"`)
across `packages/brain_core/tests/` returns ZERO hits. The docstring
at line 445 already correctly describes `validate_assignment=True` as
the **enabled** state and references the Plan 16 T36 rationale.

**What to do:**
1. **Re-verify** the grep at T4 execution time (state may have shifted
   since plan write — Plan 17 commit graph mostly closed it).
2. **Append `## T4 outcome` to this plan doc** documenting:
   - The grep recipe used.
   - The grep result (expected: 0 hits).
   - A pointer to the current correct docstring at
     `packages/brain_core/tests/tools/test_config_set_persists.py:445`
     (verify line number at execution time — file may have grown).
   - The close verdict: **ALREADY-DONE.** Plan 17 T10 precedent.
3. **No code commit.** Plan-doc note + this `## T4 outcome` section
   are the only artifacts.

**Per-task review:** combined spec + code-quality. Trivial; reviewer
confirms the grep evidence is recorded and reflects current state.

### Closure

#### T5 — Closure: demo + lessons + todo + tag

**Files:**
- Create: `scripts/demo-plan-18.py` — assert each gate per the demo
  description above.
- Modify: `tasks/lessons.md` — append a "Plan 18 closure" section.
- Modify: `tasks/todo.md` — row 18 marked ✅ Complete; tail block
  refreshed as "Plan 19 candidate scope" (preserves the 4 NOT-DOING
  carry-forwards with rationale).
- Tag: `plan-18-typed-surface-drift-closure` cut on green demo.

**Goal:** land Plan 18 closure following Plan 17 T19's shape exactly.

**What to do:**
1. **`demo-plan-18.py`.** Per D4, the demo asserts each carry-forward
   is CLOSED with per-item structural assertions (file existence,
   regex match, AST shape). No live LLM, no network. Final stdout
   line on a clean run: `PLAN 18 DEMO OK`.
2. **Lessons.** Plan 18 closure section in `tasks/lessons.md`:
   - "Typed-wrapper-vs-runtime drift class lesson" — generalize the
     `recent()` pattern. Future Plan-N authors should treat
     typed-surface declarations as audit-targets when one drift
     surfaces.
   - Whatever T2 audit findings produce — if zero, the lesson IS
     "audited and verified zero." If 1+, lessons cover the patterns.
   - Anything else surfaced during T1-T4 review.
3. **todo.md update.** Row 18 marked ✅; tail block becomes "Plan 19
   candidate scope" with the 4 preserved NOT-DOING carry-forwards:
   - seedBrainMd / seedScope rule-of-three (threshold not met).
   - Per-thread cross-domain confirmation (architectural NO per spec
     §3, Plan 16 D36).
   - "Topbar scope chip" drift watch (lesson-only per Plan 12).
   - Free-threaded Python PEP 703 for `_cached_ctx` (3.14 trigger).
4. **Tag.** `plan-18-typed-surface-drift-closure` cut on green
   `scripts/demo-plan-18.py` + green pytest + green vitest +
   green Playwright + green CI on macos-14 + windows-2022.
5. **Push.** Per D7, after closure tag: single `git push` covers
   Plans 16 + 17 + 18 (30+ commits ahead of origin at this point).
   User authorization required.

**Per-task review:** combined spec + code-quality. Demo gate count is
not pinned per D4; closure shape mirrors Plan 17 T19.

## Owning subagents

- **brain-frontend-engineer** — T1 (TS interface narrow + 2
  consumer fixes + unit test), T2 (TS-side audit pass), T3 (TS pin
  test + fixture; OR per-finding fixes branch). May bounce a
  follow-up to brain-core-engineer if a backend handler's
  `ToolResult.data` shape needs adjudication.
- **brain-core-engineer** — T3 (Python pin test against
  `brain_recent` handler in the zero-findings branch; per-finding
  Python pins in the 1+ branch), T4 (grep verification + plan-doc
  note), T5 (demo + lessons).
- **brain-test-engineer** — may collaborate on T1 / T3 unit tests if
  needed; the implementer is empowered to land tests inline per Plan
  17 D2's "combined review" practice.
- (No new tasks for brain-prompt-engineer, brain-ui-designer,
  brain-mcp-engineer, or brain-installer-engineer in Plan 18.)

## Workflow rules

Same as Plans 16 + 17:
- Sequential per-task dispatch via `superpowers:subagent-driven-development`.
- Combined spec + code-quality review per task.
- Implementer routes back to plan author on any unrecognized rule
  edge case (e.g., T1 cleaner-shape adjudication, T3 per-finding
  direction adjudication, T2 verdict edge cases).
- Pause every ~3 tasks for user check-in (smaller plan — Plan 16/17
  paused every ~5).
- No push without explicit user authorization at Plan 18 close (D7).

## File inventory (summary)

```
tasks/plans/
└── 18-typed-surface-drift-closure.md   # SELF (this doc); T2/T3/T4
                                        # findings appended at exec time

apps/brain_web/
├── src/lib/api/
│   └── tools.ts                        # MODIFY: narrow RecentEntry (T1);
│                                       # docstring sweep on each
│                                       # audited interface (T3 zero-
│                                       # findings branch)
├── src/components/
│   ├── browse/browse-screen.tsx        # MODIFY: local BrowseRowDisplay
│                                       # type post-T1 narrow (T1)
│   └── draft/doc-picker-dialog.tsx     # MODIFY: drop it.domain /
│                                       # it.modified reads (T1)
├── tests/
│   ├── unit/
│   │   ├── doc-picker-dialog.test.tsx  # CREATE or MODIFY: real-shape
│                                       # regression pin (T1)
│   │   └── recent-entry-drift.test.ts  # CREATE: TS drift pin
│                                       # (T3 zero-findings branch)
│   └── fixtures/
│       └── recent-entry-shape.json     # CREATE: drift gate fixture
│                                       # (T3 zero-findings branch)

packages/brain_core/
└── tests/
    └── test_recent_entry_drift.py      # CREATE: Python drift pin
                                        # (T3 zero-findings branch)

scripts/
└── demo-plan-18.py                     # CREATE (T5)

tasks/
├── lessons.md                          # MODIFY: Plan 18 closure
                                        # section (T5)
└── todo.md                             # MODIFY: row 18 ✅ + Plan 19
                                        # candidate scope tail (T5)
```

## T2 audit findings

To be filled in at T2 execution. Expected format:

| TS interface / inline shape | Backend tool | Verdict | Notes |
|---|---|---|---|
| (filled in at T2) | | | |

Verdict legend: **OK** — exact agreement; **MINOR** — TS optionals
backend doesn't emit, runtime degrades gracefully; **DRIFT** — T3 fix
candidate.

## T3 outcome

To be filled in at T3 execution. Will document the verdict-driven
branch taken (zero-findings vs. 1+ findings) and the per-deliverable
receipts (fixture path, pin test paths, any per-finding fix commits).

## T4 outcome

**Pre-plan-write audit (2026-05-11):** the grep candidates for the
T36 stale docstring all return zero matches in
`packages/brain_core/tests/`:

```bash
grep -rn "doesn't enable validate_assignment" packages/brain_core/tests/
grep -rn "does not enable validate_assignment" packages/brain_core/tests/
grep -rn "without validate_assignment" packages/brain_core/tests/
grep -rn "NOT enable validate_assignment" packages/brain_core/tests/
```

The docstring at
`packages/brain_core/tests/tools/test_config_set_persists.py:445`
correctly describes `validate_assignment=True` as enabled and
references Plan 16 T36's `@model_validator(mode="after")` no-rollback
quirk. Verification will be re-run at T4 execution time per the
task description; if state has shifted, the close verdict adapts.

**Expected close verdict:** ALREADY-DONE (Plan 17 T10 precedent).

## Plan 19 candidate scope (placeholder)

To be filled in at T5 closure. Expected content: the 4 preserved
NOT-DOING carry-forwards (seedBrainMd rule-of-three; per-thread
cross-domain NO; topbar scope chip drift watch; PEP 703 wait-for-3.14)
plus anything that emerges during Plan 18 execution that's too narrow
to land inline.

## Review (pending)

To be filled in on closure following Plan 11..17 format:
- **Tag:** `plan-18-typed-surface-drift-closure` (cut on green demo).
- **Closes:** every item in the Plan 17 candidate scope tail block of
  `tasks/todo.md` (preserved here for traceability).
- **Bumps:** `RecentEntry` shape narrows in `tools.ts`; doc-picker bug
  closed; `tools.ts` typed-surface audit findings recorded inline;
  T4 close-as-ALREADY-DONE evidence inline; zero new dependencies;
  no schema changes.
- **Verification:** `scripts/demo-plan-18.py` → `PLAN 18 DEMO OK`;
  pytest + vitest + Playwright + Mac+Windows CI green.
- **Backlog forward:** Plan 19 candidate scope per Task 5 step 3.

---

**End of Plan 18.**
