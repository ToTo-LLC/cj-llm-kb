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

Audited 2026-05-11 against backend handlers under
`packages/brain_core/src/brain_core/tools/`. One row per exported
wrapper in `tools.ts` that declares a non-opaque `data` shape (i.e.,
typed beyond `Record<string, unknown>`). Wrappers that consume
`Record<string, unknown>` opaque payloads are excluded by design — see
footnote.

Verdict legend: **OK** — TS and backend agree exactly on key set +
types; **MINOR** — TS uses optional fields (`?:`) or an
`[extra: string]: unknown` index signature that absorbs the
discrepancy and runtime reads degrade gracefully; **DRIFT** — TS
declares required fields the backend does not emit (the T1 class —
silently `undefined` at runtime) OR backend emits keys not declared in
TS AND TS has no index-sig escape hatch (TS callers can't read those
fields without an `as`-cast). T3 fix candidates.

| TS interface / inline shape | Backend tool | Verdict | Notes |
|---|---|---|---|
| inline @ `listDomains()` (`tools.ts:87-98`) | `brain_list_domains` (`tools/list_domains.py:108-132`) | MINOR | TS marks `entries?` and `active_domain?` optional; backend always emits both. Permissive TS → safe runtime. |
| inline @ `getIndex()` (`tools.ts:101-104`) | `brain_get_index` (`tools/get_index.py:25-45`) | **DRIFT** | TS declares `{path, content}`; backend emits `{domain, frontmatter, body}`. **Zero overlap on keys.** Both TS-required fields silently `undefined`; backend's `domain/frontmatter/body` invisible to TS. No active consumer (function unused outside `tools.ts`). |
| inline @ `readNote()` (`tools.ts:107-115`) | `brain_read_note` (`tools/read_note.py:25-35`) | OK | Both sides: `{path, frontmatter, body}`. |
| `SearchHit` + inline @ `search()` (`tools.ts:36-41, 123-126`) | `brain_search` (`tools/search.py:26-55`) | OK | Both sides: `{hits: SearchHit[], top_k_used}`; hit shape `{path, title, snippet, score}` exact agreement. |
| `RecentEntry` + inline @ `recent()` (`tools.ts:55-58, 129-132`) | `brain_recent` (`tools/recent.py:34-63`) | **DRIFT** | T1 narrowed `RecentEntry` to `{path, modified_at}` correctly. **Outer-shape extra remains:** backend emits `{items, limit_used}`; TS declares `{items: RecentEntry[]}` with no index sig → `limit_used` invisible to TS. Practical severity nil (no consumer reads `limit_used`), but classification-strict DRIFT (extra-in-backend, no escape). |
| `ChatThreadEntry` + inline @ `listThreads()` (`tools.ts:137-150`) | `brain_list_threads` (`tools/list_threads.py:67-138`) | OK | Both sides: `{threads: [{thread_id, path, domain, mode, turns, cost_usd, updated_at}]}`. |
| inline @ `exportThread()` (`tools.ts:155-174`) | `brain_export_thread` (`tools/export_thread.py:50-76`) | OK | Both sides: `{thread_id, path, domain, markdown, filename, byte_length}`. |
| inline @ `getBrainMd()` (`tools.ts:177-181`) | `brain_get_brain_md` (`tools/get_brain_md.py:20-28`) | **DRIFT** | TS declares `{path, content}`; backend emits `{exists, body}`. **Zero overlap on keys.** Both TS-required fields silently `undefined`; backend's `exists/body` invisible to TS. No active consumer in `apps/brain_web/src/`. |
| inline @ `ingest()` (`tools.ts:185-202`) | `brain_ingest` (`tools/ingest.py:163-217`) | **DRIFT** | TS declares `{patch_id: string\|null, applied: boolean, domain: string\|null, [extra]}`. Three backend branches: error `{status, errors, note_path}`; applied `{status: "applied", note_path}`; pending `{status: "pending", patch_id, target_path}`. **No branch emits `applied` (boolean) or `domain`.** TS-required `applied`/`domain` silently `undefined`; `patch_id` only present in pending branch. Index sig absorbs backend extras. |
| inline @ `classify()` (`tools.ts:206-219`) | `brain_classify` (`tools/classify.py:123-143`) | MINOR | TS `{domain, confidence, [extra]}`; backend `{domain, confidence, source_type, needs_user_pick}` (happy) or `{domain, confidence, reason}` (scope-filter). Extras absorbed by TS index sig. |
| inline @ `bulkImport()` (`tools.ts:222-237`) | `brain_bulk_import` (`tools/bulk_import.py:158-241`) | **DRIFT** | TS declares `{plan: Array<...>, applied: boolean, [extra]}`. Backend branches emit `{status, reason, file_count}` (refused); `{status, file_count, skipped_count, items}` (planned, uses `items` NOT `plan`); `{status, applied: string[], quarantined, duplicate, failed}` (applied, uses `applied: string[]` NOT `applied: boolean`). **TS-required `plan` never emitted; `applied` type mismatch (`boolean` vs `string[]`).** Consumer at `components/bulk/step-pick-folder.tsx:138` already casts away TS shape and reads `data.items` raw, confirming the drift in practice. |
| inline @ `proposeNote()` (`tools.ts:242-250`) | `brain_propose_note` (`tools/propose_note.py:92-99`) | **DRIFT** | TS `{patch_id, target_path}` (no index sig); backend `{status, patch_id, target_path}`. Backend-only `status` invisible to TS callers. TS-required fields all present in backend; severity informational only. |
| `PendingPatch` + inline @ `listPendingPatches()` (`tools.ts:60-66, 253-256`) | `brain_list_pending_patches` (`tools/list_pending_patches.py:35-55`) | **DRIFT** | `PendingPatch` shape declares `{patch_id, target_path, reason, created_at, [extra]}` — index sig absorbs backend's `tool`/`mode` extras on the row level. **Outer shape `{patches: PendingPatch[]}` has no index sig; backend emits `{count, patches}` — `count` invisible to TS callers.** Severity informational only. |
| inline @ `getPendingPatch()` (`tools.ts:265-276`) | `brain_get_pending_patch` (`tools/get_pending_patch.py:49-67`) | OK | Both sides: `{envelope: Record<...>, patchset: Record<...>}`. |
| inline @ `applyPatch()` (`tools.ts:279-294`) | `brain_apply_patch` (`tools/apply_patch.py:114-122`) | MINOR | TS `{patch_id, undo_id, applied_files, [extra]}`; backend `{status, patch_id, undo_id, applied_files}`. Extra `status` absorbed by TS index sig. |
| inline @ `rejectPatch()` (`tools.ts:297-301`) | `brain_reject_patch` (`tools/reject_patch.py:44-51`) | **DRIFT** | TS declares `{patch_id, rejected: boolean}` (no index sig); backend emits `{status: "rejected", patch_id, reason}`. **TS-required `rejected` (boolean) NEVER emitted by backend — silently `undefined`.** Backend-only `status` and `reason` invisible to TS. The TS `rejected: boolean` shape appears to be plan-author drift from an earlier sketch that never landed. |
| inline @ `undoLast()` (`tools.ts:304-317`) | `brain_undo_last` (`tools/undo_last.py:59-73`) | **DRIFT** | TS declares `{undo_id, reverted_files, [extra]}`. Backend branches: `{status: "nothing_to_undo"}` (no undo_id, no reverted_files) and `{status: "reverted", undo_id}` (no reverted_files). **TS-required `reverted_files` NEVER emitted by backend** — silently `undefined`. `undo_id` is present only in the reverted branch (would also be undefined on nothing_to_undo). Index sig absorbs backend `status` extra. |
| inline @ `costReport()` (`tools.ts:322-333`) | `brain_cost_report` (`tools/cost_report.py:28-50`) | **DRIFT** | TS declares `{total_usd, by_operation, [extra]}`; backend emits `{today_usd, month_usd, by_domain, by_mode}`. **TS-required `total_usd` and `by_operation` NEVER emitted by backend** — both silently `undefined`. Backend's actual cost shape (`today_usd/month_usd/by_domain/by_mode`) absorbed by TS index sig but invisible to type-aware callers. Plan-author drift from an earlier cost-report sketch. |
| inline @ `lint()` (`tools.ts:336-347`) | `brain_lint` (`tools/lint.py:29-37`) | **DRIFT** | TS declares `{findings: Array<...>, [extra]}`; backend (stub, "not yet implemented") emits `{status: "not_implemented", message}`. **TS-required `findings` never emitted by stub.** Will become OK when Plan 09 lands the real lint engine and emits `findings`. Plan 09 implementers must align to the TS shape (or T3 narrows TS to current reality). |
| inline @ `configGet()` (`tools.ts:350-353`) | `brain_config_get` (`tools/config_get.py:81-84`) | OK | Both sides: `{key, value}`. |
| `RepairConfigStep` + `RepairConfigData` + inline @ `repairConfig()` (`tools.ts:370-379, 387-391, 400-401`) | `brain_repair_config` (`tools/repair_config.py:261-268`) | OK | Both sides: `{steps: RepairConfigStep[], repair_changes_pending, repaired_config}`; step shape `{step, status, message}` exact agreement. |
| inline @ `repairConfigApply()` (`tools.ts:411-419`) | `brain_repair_config_apply` (`tools/repair_config_apply.py:146-153`) | OK | Both sides: `{status, path, config_version}`. |
| inline @ `configSet()` (`tools.ts:422-426`) | `brain_config_set` (`tools/config_set.py:832-845, 901-910`) | **DRIFT** | TS declares `{key, value}` (no index sig). Backend branches emit `{status, key, value, persisted, note}` (always). **Backend-only `status`/`persisted`/`note` invisible to TS callers.** TS-required `key`/`value` present. Severity informational only. Also affects every `configSet`-routed wrapper (`setDomainOverride`, `setPrivacyRailed`, `setDomainBudget`, `setDomainRateLimit`, `setDomainAutonomy`, `setActiveDomain`, `setCrossDomainWarningAcknowledged`) which all return `Promise<ToolResponse<{key, value}>>` — same drift, single root in `configSet`. |
| `RecentIngestEntry` + inline @ `recentIngests()` (`tools.ts:68-74, 644-647`) | `brain_recent_ingests` (`tools/recent_ingests.py:41-90`) | **DRIFT** | TS declares `{items: RecentIngestEntry[]}` and `RecentIngestEntry = {source, domain, status, at, [extra]}`. Backend emits `{ingests: [...]}` (NOT `items`) with row shape `{source, source_type, domain, status, classified_at, cost_usd, ...}` (NOT `at`). **Both TS-required keys (`items` outer, `at` inner) silently `undefined`.** Consumer `lib/state/inbox-store.ts:139` reads `data.items` AND `it.at` — both fall through to the empty-array / undefined fallback, producing silently-empty Inbox rows. **Highest-impact DRIFT in this audit** (same shape as the T1 doc-picker bug; live consumer affected). |
| inline @ `createDomain()` (`tools.ts:650-667`) | `brain_create_domain` (`tools/create_domain.py:140-150`) | **DRIFT** | TS declares `{slug, name, accent_color, [extra]}` at top level. Backend emits `{status, domain: {slug, name, accent_color}, note}` — **TS-required `slug/name/accent_color` are NESTED under `domain` in backend**, not at top level. All three silently `undefined`. Index sig absorbs `status`/`domain`/`note` blindly. |
| inline @ `renameDomain()` (`tools.ts:670-687`) | `brain_rename_domain` (`tools/rename_domain.py:287-300`) | MINOR | TS `{from, to, files_updated, [extra]}`; backend `{status, from, to, files_updated, wikilinks_rewritten, undo_id}`. Extras absorbed by TS index sig. |
| inline @ `budgetOverride()` (`tools.ts:690-706`) | `brain_budget_override` (`tools/budget_override.py:79-93`) | **DRIFT** | TS declares `{amount_usd, duration_hours, expires_at, [extra]}`. Backend emits `{status, override_until, override_delta_usd, note}`. **All three TS-required fields (`amount_usd/duration_hours/expires_at`) NEVER emitted by backend** — silently `undefined`. Backend's `override_until`/`override_delta_usd` semantically equivalent but renamed; index sig absorbs them for `as`-cast reads. |
| inline @ `forkThread()` (`tools.ts:716-723`) | `brain_fork_thread` (`tools/fork_thread.py:167-170`) | OK | Both sides: `{new_thread_id}`. |
| inline @ `brainMcpInstall()` (`tools.ts:734-755`) | `brain_mcp_install` (`tools/mcp_install.py:75-83`) | OK | Both sides: `{status, config_path, backup_path, server_name}`; TS index sig harmless (no backend extras). |
| inline @ `brainMcpUninstall()` (`tools.ts:761-778`) | `brain_mcp_uninstall` (`tools/mcp_uninstall.py:45-61`) | OK | TS optional `backup_path?` accommodates the not_installed branch (which omits it). |
| inline @ `brainMcpStatus()` (`tools.ts:784-807`) | `brain_mcp_status` (`tools/mcp_status.py:49-60`) | OK | Both sides: `{status, config_path, config_exists, entry_present, executable_resolves, command, server_name}`. |
| inline @ `brainMcpSelftest()` (`tools.ts:814-839`) | `brain_mcp_selftest` (`tools/mcp_selftest.py:45-62`) | OK | Both sides: `{status, ok, config_exists, entry_present, executable_resolves, command, config_path, server_name}`. |
| inline @ `brainSetApiKey()` (`tools.ts:848-868`) | `brain_set_api_key` (`tools/set_api_key.py:76-85`) | OK | Both sides: `{status, provider, env_key, masked, path}`. |
| inline @ `brainPingLlm()` (`tools.ts:876-895`) | `brain_ping_llm` (`tools/ping_llm.py:47-123`) | OK | TS optional `error?` matches: backend emits `error` only on failure branches. All other keys present in every branch. |
| `BackupEntry` + inline @ `brainBackupCreate()` (`tools.ts:899-907, 910-933`) | `brain_backup_create` (`tools/backup_create.py:47-60`) | OK | Both sides: `{status, backup_id, path, trigger, created_at, size_bytes, file_count}`. |
| `BackupEntry` + inline @ `brainBackupList()` (`tools.ts:936-938`) | `brain_backup_list` (`tools/backup_list.py:27-45`) | OK | Both sides: `{backups: BackupEntry[]}`; `BackupEntry` shape exact agreement with backend row dict. |
| inline @ `brainBackupRestore()` (`tools.ts:945-961`) | `brain_backup_restore` (`tools/backup_restore.py:44-62`) | OK | Both sides: `{status, backup_id, trash_path}`; TS index sig harmless. |
| inline @ `brainDeleteDomain()` (`tools.ts:970-990`) | `brain_delete_domain` (`tools/delete_domain.py:101-113`) | OK | Both sides: `{status, slug, trash_path, files_moved, undo_id}`. |

**Summary:** 19 OK, 4 MINOR, 15 DRIFT (15 rows are T3 fix candidates).

**Drift-class breakdown** (helps T3 scope each):
- **T1-class — TS-required fields missing/wrong-typed in backend** (silently `undefined` at runtime; can break live consumers): `getIndex`, `getBrainMd`, `ingest`, `bulkImport`, `rejectPatch`, `undoLast`, `costReport`, `lint`, `recentIngests`, `createDomain`, `budgetOverride`. **11 rows.**
- **Extra-in-backend, no TS index-sig escape hatch** (backend emits keys TS can't read without cast; harmless to current callers): `recent` (outer), `proposeNote`, `listPendingPatches` (outer), `configSet`. **4 rows.**

**Live-consumer-impact heat map** (consumers in `apps/brain_web/src/` that consume drifted fields):
- `recentIngests` — `lib/state/inbox-store.ts:139` reads `data.items` (backend emits `ingests`) AND `it.at` (backend emits `classified_at`). Silently-empty Inbox rows. **HIGH (T1-shape live bug).**
- `bulkImport` — `components/bulk/step-pick-folder.tsx:138` already casts away the typed shape with an inline comment acknowledging the discrepancy. **LOW (consumer worked around).**
- All other DRIFT rows: no active consumer reading the drifted field, so no current runtime bug. **LOW.**

Footnote on exclusions: `tools.ts` exports 47 const declarations (`grep -E "^export const " ... | wc -l` = 47). Excluded from the audit table: `AUTONOMY_CATEGORIES` (data tuple, not a wrapper), `ALL_TOOL_NAMES` (registry tuple), and 7 `configSet`-routed wrappers (`setDomainOverride`, `setPrivacyRailed`, `setDomainBudget`, `setDomainRateLimit`, `setDomainAutonomy`, `setActiveDomain`, `setCrossDomainWarningAcknowledged`) — they all return `Promise<ToolResponse<{key, value}>>` and inherit `configSet`'s DRIFT row; counting them separately would multiply the same finding 7×. That leaves 47 − 2 − 7 = 38 wrapper rows audited, each mapping to a distinct backend handler. (Some named TS interfaces — `BackupEntry`, `RecentEntry`, etc. — are reused by multiple wrappers; those reuses are listed in the relevant wrapper's row but don't add to the row count.)

Spot-check pass (4 rows re-derived from backend after writing verdicts):
- `recentIngests` row → re-read `tools/recent_ingests.py:65-90`: confirms `data={"ingests": ingests}` with row keys `source, source_type, domain, status, classified_at, cost_usd`. TS declares `{items, ...}` and `at`. Confirmed **DRIFT**.
- `costReport` row → re-read `tools/cost_report.py:39-50`: confirms backend `{today_usd, month_usd, by_domain, by_mode}`. TS `{total_usd, by_operation}`. Confirmed **DRIFT**.
- `getPendingPatch` row → re-read `tools/get_pending_patch.py:61-67`: confirms `{envelope, patchset}`. TS matches. Confirmed **OK**.
- `forkThread` row → re-read `tools/fork_thread.py:167-170`: confirms `{new_thread_id}`. TS matches. Confirmed **OK**.

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

**T4 execution-time re-verification (2026-05-11, post-T3.11):** all
four greps still return zero matches. The docstring at
`packages/brain_core/tests/tools/test_config_set_persists.py:445`
correctly describes `validate_assignment=True` as enabled and
references Plan 16 T36's `@model_validator(mode="after")` no-rollback
quirk. Current line: `445` (unchanged from plan-write; the docstring
spans lines 439-453 inside `test_active_domain_must_be_in_domains`).

Quoted excerpt (the relevant portion of the docstring):
```
Plan 16 Task 36 enabled ``validate_assignment=True``
on ``Config`` (so per-field validators DO fire on assignment), but
``_check_active_domain_in_domains`` is a ``@model_validator(mode=
"after")`` — and a Pydantic v2 cross-field validator failure does
NOT roll back the triggering field mutation.
```

**Close verdict:** **ALREADY-DONE** (Plan 17 T10 precedent — audits
closing as already-done are valid outcomes when the premise has
shifted).

## Plan 19 candidate scope

Filled in at T5 closure. The canonical record is the tail block of
`tasks/todo.md`; this section is a brief pointer. Tracks:

- **Track A** — REST-endpoint drift parallel to T2's MCP-tool audit
  (`/api/upload` UploadResult; consider full REST-surface audit pass).
- **Track B** — UX fallout from Plan 18 narrows (`cost === 0`
  ingest-row badge suppression).
- **Track C** — 4 informational extra-in-backend DRIFTs deferred
  from T2 (`recent` outer / `proposeNote` / `listPendingPatches`
  outer / `configSet`).
- **Track D** — `planToFiles` type-tighten (accept
  `BulkImportPlannedItem[]` directly).
- **Preserved Plan 17 / earlier carry-forwards** —
  `seedBrainMd`/`seedScope` rule-of-three; per-thread cross-domain
  confirmation (architectural NO per spec §3 / Plan 16 D36);
  topbar scope chip drift watch (lesson-only); PEP 703 for
  `_cached_ctx` (3.14 timeline trigger).

## Review

- **Tag:** `plan-18-typed-surface-drift-closure` (cut on green demo
  by the user after final approval).
- **Closes:** every item in the Plan 17 candidate scope tail block
  of `tasks/todo.md` (preserved here for traceability): T1 closed
  the `recent()` typed-wrapper drift + the surfaced `doc-picker-dialog.tsx`
  MEDIUM-severity production bug; T2 produced 38-row sibling-drift
  audit (19 OK / 4 MINOR / 15 DRIFT); T3 closed the 11 T1-class
  DRIFTs (recentIngests / getIndex / getBrainMd / lint / ingest /
  rejectPatch / undoLast / costReport / bulkImport / createDomain /
  budgetOverride) with TS narrows + Python key-set pins; T4 closed
  the T36 stale-docstring residual as ALREADY-DONE.
- **Bumps:**
  - `RecentEntry` narrowed in `tools.ts` to `{path, modified_at}` (T1).
  - 11 typed wrappers narrowed to backend reality across `tools.ts`
    (T3.1-T3.11), 3 of which use discriminated-union types
    (`IngestResultData` / `UndoLastData` / `BulkImportData`).
  - 3 live consumer bugs closed: Inbox silently-empty rows
    (T3.1 recentIngests); undo toast always "Reverted 0 file(s)."
    (T3.7); budget-override toast computed from prop default
    not backend value (T3.11).
  - 11 Python key-set pin tests added under
    `packages/brain_core/tests/tools/` (single + multi-branch
    variants).
  - T2 audit findings recorded inline at `## T2 audit findings`.
  - T4 ALREADY-DONE evidence recorded inline at `## T4 outcome`.
  - 4 informational extra-in-backend DRIFTs (recent outer /
    proposeNote / listPendingPatches outer / configSet) deferred
    to Plan 19 per user adjudication of T2's surprise finding count.
  - Zero new dependencies; no schema changes; no spec text changes.
- **Verification:** `scripts/demo-plan-18.py` → `PLAN 18 DEMO OK`
  (16 gates); pytest + vitest + Playwright green on the implementer's
  local Mac (Windows CI cut at user-tag + push time per D7).
- **Backlog forward:** Plan 19 candidate scope per the tail block
  of `tasks/todo.md` (Track A REST drift / Track B UX fallout /
  Track C 4 deferred extras / Track D `planToFiles` type-tighten /
  preserved Plan 17 carry-forwards).

---

**End of Plan 18.**
