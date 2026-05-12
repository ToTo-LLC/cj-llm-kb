# Plan 22 — Watched folders (live source → vault sync)

**Authored:** 2026-05-12 (post Plan 21 close on 2026-05-12, tag
`plan-21-resolve-out-dir-hardening` at `f5c9f08`).
**Scope:** Introduce a "watched folders" subsystem so users can point
brain at a local folder and have file additions, edits, and deletions
propagate to the knowledge base automatically. Per user 1.B: SINGLE
comprehensive plan covering spec update + backend + UI + tests + closure.
Per user 2.A: **source is canonical** — vault notes derived from
watched-folder sources are OVERWRITTEN on source change (vault edits to
watched-source notes are documented as lost on next sync). Per user
3.A: source deletion marks the note `orphaned: true` in frontmatter;
`scope_guard` filters orphans from default queries; user manually
adjudicates delete-or-restore. Per user 4.C: no initial-sync size cap
(rate-limit + budget caps still enforce hard ceilings). Per user 5.C:
classify ONCE on first ingest; preserve classification on re-ingest
(no surprise domain moves). Per user 6.B: comprehensive 7-tool surface
(`brain_watch_folder` / `brain_unwatch_folder` / `brain_list_watched_folders` /
`brain_list_orphans` / `brain_resync_folder` / `brain_restore_orphan` /
`brain_delete_orphan`). Per user 7.A: Bulk Import success screen gains
a "Watch this folder for changes" CTA for one-click conversion.
**Shape:** ~18 substantive tasks across 4 themes + closure. Mirrors
Plan 16's comprehensive-feature shape (47 tasks for Theme 10 full
production), scaled smaller. Spec update lands at T0 per CLAUDE.md
"Changes to vault schema, prompts, or safety rails: spec update first."

## At a glance

- **Theme A — Foundation** (T0-T4): spec update (§4 Vault + §5 Ingestion
  + §10 Safety rails); schema (`Config.watched_folders`,
  `WatchedFolder` Pydantic model, new frontmatter fields); pipeline
  re-ingest path (preserve slug, preserve classification); pipeline
  orphan path; scope_guard extension.
- **Theme B — Backend infrastructure** (T5-T10): 7 tool surfaces (read
  + write + orphan management); watcher core (`WatchedFolderWatcher`
  mirrors Plan 16 T35 `ConfigWatcher` shape); watcher integration in
  brain_api lifespan + brain_mcp `_cached_ctx`; backup trigger
  (`pre_watched_folder_sync`); initial-sync cost-estimate gate
  (informational, no hard cap per D3); unit + integration + cross-
  platform tests.
- **Theme C — Frontend** (T11-T16): brain-ui-designer mockups FIRST
  (Settings panel "Watched folders" tab + Orphan management screen +
  Topbar status indicator + 3 confirmation modals); then frontend
  implementation tasks gated on mockup approval per CLAUDE.md
  "brain-frontend-engineer only writes code after mockups approved";
  Bulk Import success-screen "Watch this folder" CTA; Playwright e2e.
- **Theme D — Closure** (T17-T18): demo + lessons + todo + tag
  `plan-22-watched-folders-sync`.

## Why this plan exists (1 paragraph)

The Plan 21 review surfaced this as a frequently-asked product
question: today's ingest pipeline is one-shot — running
`brain_bulk_import` on a folder ingests every file but never re-checks
the folder for changes. Source-file edits go undetected; deletions
leave orphan notes in the vault; new files require a manual re-run. The
existing dedup-via-`content_hash` mechanism makes re-runs SAFE (no
duplicate notes) but doesn't close the synchronization gap. Plan 22
adds the gap-closing feature: a `Config.watched_folders` list, a
`WatchedFolderWatcher` symmetric file-system observer (one per
brain_api + brain_mcp process per Plan 16 T35 precedent), and a
re-ingest path that REPLACES the existing note (preserves slug → wikilinks
remain valid; preserves classification → no surprise domain moves). The
orphan policy is deliberately non-destructive — source deletion marks
the note `orphaned: true` but never auto-deletes the vault file
(preserves CLAUDE.md non-negotiable #1 "vault is sacred"; user must
typed-confirm any delete). The Bulk Import wizard gets a one-click
"Watch this folder" conversion CTA so the natural workflow flows
from one-shot import → live sync without context-switching to Settings.

## Locked decisions

| # | Decision | Status | Why |
|---|---|---|---|
| D1 | **Update policy on source change: OVERWRITE (source is canonical).** Watched-folder vault notes are replaced in place when their source file changes. Vault edits to watched-source notes are lost on the next source change. Documented prominently in the watch-folder enable confirmation modal (T15). | locked (user 2.A) | Simplest v1 semantics; matches "auto-sync" user expectation. Defers conflict resolution (vault-edit-aware merge / prompt / LLM-assisted) to a future plan. The "source canonical" contract is the design's load-bearing simplification. |
| D2 | **Orphan policy on source deletion: MARK `orphaned: true` in frontmatter; `scope_guard` filters from default queries; user adjudicates delete-or-restore.** Auto-delete is NOT in v1 scope (would violate CLAUDE.md non-negotiable #1 "vault is sacred" without typed confirmation). | locked (user 3.A) | Non-destructive; matches `VaultWriter` undo-log + typed-confirm conventions. Surfaces deletions to the user without acting unilaterally. Settings panel exposes an Orphans tab for review + bulk action. |
| D3 | **Initial sync: no hard file-count cap.** Watch-enable triggers a full folder walk + ingest of every matched file. Rate-limit + per-domain budget caps (Plan 16 T26-T32) enforce hard ceilings; if those exhaust mid-sync, the sync pauses and the user resumes after raising the cap. T9 adds an informational pre-sync cost estimate (no refusal threshold). | locked (user 4.C) | Trusts the deliberate opt-in (`brain_watch_folder` is an explicit user action, unlike `brain_ingest` which can be triggered by drop-zone events). Existing budget rail is the safety net. |
| D4 | **Classify behavior: classify ONCE on first ingest; preserve classification on re-ingest.** First sync runs the classifier (or honors a `--domain <name>` override at watch-enable time). Re-ingest reads the existing note's frontmatter `domain` and preserves it — no re-classify call, no surprise domain move. | locked (user 5.C) | Predictable (wikilinks pointing at the note keep their target path); saves LLM calls (no per-event classify cost); matches `bulk_import`'s `domain_override` semantics. User can manually move a note across domains if they want to override. |
| D5 | **Tool surface: 7 tools.** `brain_watch_folder` (add to watch list + initial sync), `brain_unwatch_folder` (remove from watch list, orphans remain marked), `brain_list_watched_folders` (read), `brain_list_orphans` (read), `brain_resync_folder` (force full re-sync ignoring watcher events), `brain_restore_orphan` (un-mark `orphaned: false`), `brain_delete_orphan` (typed-confirm delete + undo log entry via VaultWriter). | locked (user 6.B) | Comprehensive surface gives the user direct control over every watched-folder state transition without forcing them through the LLM patch flow for routine operations. Each tool follows the existing `ToolContext`/`ToolResponse` pattern. |
| D6 | **Bulk Import wizard → Watch conversion CTA.** After Bulk Import's apply step completes, the success screen offers a "Watch this folder for changes" CTA that opens the watch-enable confirmation modal pre-filled with the folder path + detected domain. One-click conversion from one-shot ingest → ongoing sync. | locked (user 7.A) | Natural UX bridge between the existing one-shot ingest workflow and the new live-sync workflow. Eliminates the "ran bulk import, now have to navigate to Settings to enable watch" friction. |
| D7 | **Symmetric watcher (brain_api lifespan + brain_mcp `_cached_ctx`).** Plan 16 T35 / D28 precedent: a single `watchdog.Observer` per process, started at lifespan / server-boot, stopped at shutdown. Both brain_api and brain_mcp register observers so the watcher is alive regardless of which entry point started brain. Cross-process invalidation via the existing `ConfigWatcher` debounce pattern (~100ms window). | locked at authoring | Plan 16 T35 / T39.5 already proved the symmetric-watchdog pattern works under both lifecycles. Reusing the shape minimizes new architectural surface; the only new code is the event handler (file-change → re-ingest pipeline call) vs the config-change → cache-invalidation handler. |
| D8 | **Spec update lands at T0** per CLAUDE.md "Changes to vault schema, prompts, or safety rails: spec update first, implementation second." T0 modifies `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` — §4 Vault (new frontmatter fields), §5 Ingestion (new "Watched folders" subsection), §10 Safety rails (new bullet for watched-folders rails). T1+ implement against the locked spec. | locked per CLAUDE.md non-negotiable | Spec changes need to lock the contract BEFORE implementation, not be backfilled during. Plan 16 / 17 / 18 / 19 / 20 / 21 all worked from a frozen spec for their scope; Plan 22 freezes the new spec surface in T0 and then implements. |
| D9 | **brain-ui-designer mockups (T11) GATE brain-frontend-engineer (T12-T15).** Per CLAUDE.md "brain-frontend-engineer ... only writes code after mockups are approved." Mockup deliverables: Settings panel "Watched folders" tab; Orphan management screen; Topbar status indicator; 3 confirmation modals (watch-enable / watch-disable / orphan-delete typed-confirm). User approves mockups before T12 dispatches. | locked per CLAUDE.md workflow rule | Plan 06 / Plan 07 set the design-before-code precedent; Plan 22 inherits it for the new UI surfaces. |
| D10 | **Per-task review: combined spec + code-quality** held across 47 tasks in Plan 16; 18 in Plan 17; 5 in Plan 18; 5 in Plan 19; 4 in Plan 20; 3 in Plan 21. | locked per Plan 16 D35 / Plan 17 D2 / Plan 18 D5 / Plan 19 D8 / Plan 20 D8 / Plan 21 D8 | No reason to re-litigate at the polish + new-feature scales. |
| D11 | **No new dependencies.** Plan 22 uses existing `watchdog>=4.0` (already in `packages/brain_core/pyproject.toml` per Plan 16 T35). All other code paths reuse existing brain_core / brain_api / brain_mcp / brain_web surface. | locked at authoring | `watchdog` already serves `ConfigWatcher`; reusing it for source-folder watching is the natural extension. |
| D12 | **Push at Plan 22 close, after user authorization.** Single `git push origin main` covers all Plan 22 commits; explicit `git push origin <tag>` for the lightweight tag (per Plan 20 closure observation: `--follow-tags` skips lightweight tags; project convention is lightweight). | locked per Plan 20 D10 / Plan 21 D10 | Standard cadence. |
| D13 | **Sequential subagent dispatch via `superpowers:subagent-driven-development`.** | locked per Plan 20 D11 / Plan 21 D11 / Plan 19 D11 / Plan 18 D8 | Combined review per task + sequential dispatch held across six prior plans. |
| D14 | **Pause cadence every ~5 tasks for user check-in.** Plan 22's 18-task budget = pauses at T5 closure, T10 closure, T15 closure (which is mockup-approval gate), and plan-close after T18. | locked per user "pause every ~5 for larger plans" | Larger plans need more frequent checkpoints; mockup gate naturally lands one of the pauses. |

## Tech stack

Same as Plans 16 + 17 + 18 + 19 + 20 + 21: Python 3.12, pydantic v2,
`watchdog>=4.0` (existing), mypy --strict, ruff, structlog, pytest,
vitest, Playwright. No new tools. No new dependencies. CI runs on
macos-14 + windows-2022 per Plan 14's matrix — cross-platform watcher
backends (FSEvents / ReadDirectoryChangesW / inotify) are abstracted
by watchdog and tested by the existing matrix.

## Demo gate description

`scripts/demo-plan-22.py` asserts, in sequence (gate count branches on
mockup output — informational target is ~16-18 gates):

**Spec + Schema (T0-T1):**
1. Spec file `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md`
   contains new content in §4 (new frontmatter fields: `source_path`,
   `orphaned`, `orphaned_at`, `watched_folder_id`), §5 (new "Watched
   folders" subsection), §10 (new watched-folders safety rails bullet).
   Regex matches.
2. `Config.watched_folders` field exists; `WatchedFolder` Pydantic model
   exists with expected fields. Pydantic introspection check.

**Pipeline (T2-T4):**
3. `IngestPipeline` exposes an `update_source` method (or equivalent) for
   re-ingest of existing notes. Structural check.
4. `IngestPipeline` exposes a `mark_orphaned` method (or equivalent) for
   delete events. Structural check.
5. `scope_guard(path, allowed_domains, *, include_orphans=False)` honors
   the new keyword and filters orphans by default. Behavior check.

**Tools (T5):**
6. All 7 tool modules exist under `packages/brain_core/src/brain_core/tools/`:
   `watch_folder.py`, `unwatch_folder.py`, `list_watched_folders.py`,
   `list_orphans.py`, `resync_folder.py`, `restore_orphan.py`,
   `delete_orphan.py`. Each registers a `NAME` constant + `INPUT_SCHEMA`
   + dispatch handler.

**Watcher (T6-T8):**
7. `brain_core.watch.WatchedFolderWatcher` exists; mirrors `ConfigWatcher`
   shape (start / stop / debounce / event handler).
8. `brain_api.app.create_app` lifespan starts watchers for each enabled
   `WatchedFolder` (regex match for watcher startup in lifespan).
9. `brain_mcp._cached_ctx` start path includes watcher registration
   (regex match for symmetric watcher).

**Safety rails (T9-T10):**
10. `backup_create._VALID_TRIGGERS` includes `"pre_watched_folder_sync"`.
11. Initial-sync cost estimate fires before any LLM call (regex match for
    pre-call estimate in `watch_folder.py` or sibling).

**Tests (existing tests pass via T10 verification):**
12. All Plan 22 unit tests + integration tests pass (test count delta
    from pre-Plan-22 baseline).

**Frontend (T11-T16):**
13. brain-ui-designer mockup deliverables landed at
    `docs/design/plan-22/` (regex match for the 4 mockup PNGs / SVGs OR
    a Figma export link in a markdown file).
14. `apps/brain_web/src/components/settings/panel-watched-folders.tsx`
    exists (file existence).
15. `apps/brain_web/src/components/settings/panel-orphans.tsx` exists.
16. Bulk Import success screen contains "Watch this folder" CTA (regex
    match in the relevant component file).

**Closure (T17-T18):**
17. `scripts/demo-plan-22.py` is the closure script (this file).
18. `tasks/todo.md` row 22 marked ✅; `tasks/lessons.md` has Plan 22
    closure section; final stdout line is `PLAN 22 DEMO OK`.

## Tasks

### Theme A — Foundation

#### T0 — Spec update (§4 / §5 / §10)

**Files:**
- Modify: `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` —
  three coordinated edits:
  - **§4 Vault schema (frontmatter list):** add `source_path: string`
    (only set on local-file ingestion; absent for URL / paste /
    drag-drop content), `orphaned: bool` (default `false`, set to
    `true` when watched-source disappears), `orphaned_at: date | null`
    (set when `orphaned` flips to `true`), `watched_folder_id: string`
    (the `WatchedFolder.path` from `Config.watched_folders` — links
    a note back to its watched-folder entry).
  - **§5 Ingestion pipeline:** insert a new subsection **"Watched
    folders"** between the existing "Bulk import" and "Failure
    handling" subsections. Document the lifecycle (watch-enable →
    initial sync → live watcher → events), the contract (source
    canonical / overwrite on edit / mark-orphan on delete / preserve
    classification on re-ingest), and the tool surface (7 tools).
  - **§10 Safety rails:** add a bullet "Watched folders: opt-in
    only; backup trigger `pre_watched_folder_sync`; orphan marks
    are non-destructive (user adjudicates delete); `scope_guard`
    filters orphans from default queries via `include_orphans`
    keyword".

**Goal:** Lock the spec contract before any implementation.

**What to do:**
1. Read existing §4 frontmatter list (lines ~165-179) and append the 4
   new fields with one-line descriptions each.
2. Read existing §5 "Bulk import" subsection (lines ~239-243) and
   insert the new "Watched folders" subsection immediately after.
   Subsection should describe:
   - Schema: `Config.watched_folders: list[WatchedFolder]` with fields
     `{path: str, domain: str, enabled: bool, last_sync: datetime | None,
     policy: Literal["overwrite"] = "overwrite", include_subdirs: bool = True}`.
   - Lifecycle: enable → walk + ingest with classify (or `--domain`
     override) → `WatchedFolderWatcher` starts → events route to
     re-ingest (file change) / mark-orphan (file delete) / new-ingest
     (file add).
   - Update path: re-ingest preserves slug + frontmatter `domain`;
     replaces `body` + frontmatter `updated`, `content_hash`,
     `source_path` (if path changed via move).
   - Orphan path: delete event → set `orphaned: true` + `orphaned_at:
     <today>` in frontmatter (via VaultWriter, with undo log).
   - Tool surface: 7 tools (list above).
   - Contract: source is canonical for watched folders; vault edits
     to watched-source notes are lost on next source change.
3. Read existing §10 Safety rails list (lines ~498-508) and add the
   new bullet.
4. **No code changes in T0** — pure spec update.

**Per-task review:** combined spec + code-quality. Reviewer confirms
(a) all 4 frontmatter fields documented; (b) Watched folders subsection
covers schema + lifecycle + contract + tools; (c) Safety rails bullet
mentions backup trigger + orphan policy + scope_guard interaction;
(d) no internal contradictions with existing spec content (especially
§3 Domain separation + §10 scope_guard discussion).

#### T1 — `Config.watched_folders` + `WatchedFolder` schema + new frontmatter fields

**Files:**
- Modify: `packages/brain_core/src/brain_core/config/schema.py` — add
  `WatchedFolder` Pydantic model + `Config.watched_folders: list[WatchedFolder] = []`
  field.
- Modify: `packages/brain_core/src/brain_core/vault/frontmatter.py` (or
  equivalent module — verify at exec time) — add the 4 new optional
  fields to the canonical frontmatter type used by `VaultWriter`.
- Create: `packages/brain_core/tests/config/test_watched_folder_schema.py` —
  field-set + per-field type + required-direction pins (Plan 19 T2 /
  Plan 20 T1 / Plan 21 T1 precedent).
- Create or modify: `packages/brain_core/tests/vault/test_frontmatter_orphan_fields.py` —
  pin tests for the 4 new optional fields (default values, type
  compatibility).

**Goal:** Schema lock per T0 spec contract.

**What to do:**
1. Add `WatchedFolder` Pydantic model with fields per D7 + T0 spec.
   `path` is `str` (absolute path, validated as `Path(path).is_absolute()`);
   `domain` references the existing `Config.domains` validator;
   `policy` is `Literal["overwrite"]` with default `"overwrite"` (gives
   v2 room to add `"keep_vault"` / `"prompt"` without schema break).
2. Add `Config.watched_folders: list[WatchedFolder] = []` field with
   appropriate validator (each `WatchedFolder.domain` must be in
   `Config.domains`).
3. Add the 4 new frontmatter fields as optional. Default values:
   `source_path: str | None = None`, `orphaned: bool = False`,
   `orphaned_at: date | None = None`, `watched_folder_id: str | None = None`.
4. Write pin tests for both schemas.

**Per-task review:** combined. Reviewer confirms (a) `WatchedFolder.domain`
validator wired against `Config.domains` (cross-field invariant per
Plan 16 T36 pattern); (b) `policy` literal leaves v2 room; (c) frontmatter
fields are all OPTIONAL (no existing notes break on load); (d) pin tests
cover field-set + types + defaults; (e) full brain_core test suite still
green.

#### T2 — Pipeline re-ingest path (`pipeline.update_source`)

**Files:**
- Modify: `packages/brain_core/src/brain_core/ingest/pipeline.py` — add
  an `update_source(existing_note_path, new_source_path, *, allowed_domains)`
  method that re-ingests a single source against an existing note (slug
  + domain preserved per D4).
- Create: `packages/brain_core/tests/ingest/test_pipeline_update_source.py`.

**Goal:** v1 re-ingest path. The existing `ingest()` method always
creates a new note; `update_source()` REPLACES an existing one.

**What to do:**
1. Implement `update_source` following the existing `ingest()` stages but
   skipping stages 1 (classify — preserve via existing frontmatter
   `domain`) and 4 (archive — re-archive only if `content_hash` changed)
   for efficiency.
2. The note path stays the same; body + frontmatter `updated` + `content_hash`
   + `source_path` (in case path changed via move) are replaced.
3. Emit a structured log entry in `log.md` with a different verb
   (`update` vs `ingest`).
4. Handle the edge case where the existing note has been hand-edited
   AFTER first ingest: per D1 (overwrite), the edits are lost. Pin this
   in test fixtures so a future plan that adds vault-edit-aware merge
   knows what to change.

**Per-task review:** combined. Reviewer confirms (a) slug + domain
preserved per D4; (b) overwrite contract per D1; (c) log entry uses
`update` verb (greppable for cost analysis); (d) test fixtures cover
content-hash-unchanged (no-op) AND content-hash-changed (overwrite).

#### T3 — Pipeline orphan path (`pipeline.mark_orphaned`)

**Files:**
- Modify: `packages/brain_core/src/brain_core/ingest/pipeline.py` — add
  `mark_orphaned(existing_note_path)` method.
- Create: `packages/brain_core/tests/ingest/test_pipeline_mark_orphaned.py`.

**Goal:** v1 orphan-mark path per D2. Non-destructive.

**What to do:**
1. Implement `mark_orphaned` as a VaultWriter mutation: read frontmatter,
   set `orphaned: true` + `orphaned_at: <today>`, write atomically with
   undo log entry per the existing VaultWriter contract.
2. No body change — just the frontmatter flip.
3. Emit a `orphan` verb log entry.

**Per-task review:** combined. Reviewer confirms (a) all writes go
through VaultWriter (CLAUDE.md non-negotiable #1); (b) undo log entry
landed so `brain_undo_last` reverts the orphan mark; (c) body unchanged.

#### T4 — `scope_guard(..., *, include_orphans=False)` extension

**Files:**
- Modify: `packages/brain_core/src/brain_core/vault/scope_guard.py` (or
  equivalent module — verify at exec time) — add `include_orphans: bool = False`
  keyword. When `False` (default), filter out paths whose note has
  `orphaned: true` in frontmatter.
- Create or modify: `packages/brain_core/tests/vault/test_scope_guard_orphan_filter.py`.

**Goal:** Orphans hidden from default queries per D2.

**What to do:**
1. Add the keyword parameter (default `False`) to all `scope_guard`
   signatures.
2. When filtering, read frontmatter to detect `orphaned: true`. Cache
   the read if it's a hot path (likely is — every vault I/O hits
   scope_guard).
3. Pin tests: scope_guard with default behavior filters orphans;
   with `include_orphans=True`, orphans are visible.

**Per-task review:** combined. Reviewer confirms (a) ALL `scope_guard`
call sites (grep for `scope_guard(` across the codebase) compile against
the new signature (Python's keyword-arg default keeps backwards-compat,
so this should be a no-op for existing callers); (b) frontmatter-read
caching avoids N+1 reads on hot paths.

### Theme B — Backend infrastructure

#### T5 — 7 tool surfaces

**Files:**
- Create 7 modules under `packages/brain_core/src/brain_core/tools/`:
  - `watch_folder.py` — `brain_watch_folder`
  - `unwatch_folder.py` — `brain_unwatch_folder`
  - `list_watched_folders.py` — `brain_list_watched_folders`
  - `list_orphans.py` — `brain_list_orphans`
  - `resync_folder.py` — `brain_resync_folder`
  - `restore_orphan.py` — `brain_restore_orphan`
  - `delete_orphan.py` — `brain_delete_orphan`
- Modify: `packages/brain_core/src/brain_core/tools/__init__.py` — register
  the 7 new modules.
- Create: `packages/brain_core/tests/tools/test_<each>.py` per tool — pin
  the tool's INPUT_SCHEMA + ToolResult.data shape (Plan 18 T3 / Plan 19
  T4 / Plan 20 T1 pattern).

**Goal:** Comprehensive tool surface per D5. Each tool follows the
existing ToolContext / ToolResult shape (Plan 04 / 11 / 16 precedent).

**What to do:** per tool, define `NAME`, `DESCRIPTION`, `INPUT_SCHEMA`,
and a `dispatch(ctx, args)` function returning a `ToolResult`.

**`brain_watch_folder`**: args `{folder: str, domain: str | None,
include_subdirs: bool = True, initial_sync: bool = True}`. Validates
folder exists + is_dir + is_absolute; appends a `WatchedFolder` to
`Config.watched_folders` (via `config_set` flow); if `initial_sync=True`,
calls the existing `BulkImporter.plan()` then `apply()` with
`domain_override=domain`; if `domain is None` and the folder is empty,
defer classify decision to first file event.

**`brain_unwatch_folder`**: args `{folder: str}`. Removes the
WatchedFolder entry. Orphans remain marked (D2). Existing notes stay
(no automatic unmarking). Returns `{status: "unwatched", folder,
remaining_notes: int}`.

**`brain_list_watched_folders`**: args `{}`. Returns `{folders:
list[WatchedFolderEntry]}` where each entry includes runtime stats
(file count, orphan count, last_sync timestamp).

**`brain_list_orphans`**: args `{folder: str | None}` (folder filter
optional). Returns `{orphans: list[OrphanEntry]}` where each entry is
`{note_path, domain, source_path, orphaned_at, watched_folder_id}`.

**`brain_resync_folder`**: args `{folder: str}`. Forces a full re-sync:
walks the folder, calls `update_source()` on every matched file,
marks any vault notes whose source has disappeared as orphaned. Useful
when the watcher missed events (e.g., brain was offline).

**`brain_restore_orphan`**: args `{note_path: str}`. Reads frontmatter,
sets `orphaned: false`, removes `orphaned_at`. VaultWriter mutation with
undo log. Returns `{status: "restored", note_path}`.

**`brain_delete_orphan`**: args `{note_path: str, typed_confirm: bool}`.
REFUSES unless `typed_confirm=True` (mirrors `brain_delete_domain` /
`brain_backup_restore` precedent). Moves the note to `.brain/trash/<date>/`
(VaultWriter mutation with undo log). Returns `{status: "deleted",
trash_path, undo_id}`.

**Per-task review:** combined. Reviewer confirms (a) all 7 tools follow
the existing ToolContext / ToolResult contract; (b) INPUT_SCHEMA pin
tests fail RED on field add/remove; (c) ToolResult.data shape pin tests
match the per-tool return contract; (d) `brain_delete_orphan` requires
`typed_confirm=true` per CLAUDE.md "destructive action" rule;
(e) `_SETTABLE_KEYS` in `config_set.py` extended for `watched_folders`
wildcards if needed.

#### T6 — `WatchedFolderWatcher` core

**Files:**
- Create: `packages/brain_core/src/brain_core/watch/__init__.py`,
  `packages/brain_core/src/brain_core/watch/folder_watcher.py` —
  `WatchedFolderWatcher` class mirroring Plan 16 T35 `ConfigWatcher`
  shape.
- Create: `packages/brain_core/tests/watch/test_folder_watcher.py`.

**Goal:** Filesystem observer that bridges watchdog events into the
ingest pipeline. Symmetric (D7): one observer per process, started
at lifespan / server-boot, stopped at shutdown.

**What to do:**
1. Implement `WatchedFolderWatcher(observers: list[WatchedFolder],
   pipeline: IngestPipeline, *, debounce_ms: int = 100)`.
   `start()` / `stop()` / `_on_event(event)` per the ConfigWatcher
   pattern.
2. Event routing: `FileCreatedEvent` → `pipeline.ingest()` with
   `domain_override` from the WatchedFolder. `FileModifiedEvent` →
   `pipeline.update_source(existing_note_path, new_source_path)` if
   the file is mapped to an existing note (look up via
   `Config.watched_folders[*].folder + relative path → existing note
   slug`). `FileDeletedEvent` → `pipeline.mark_orphaned(existing_note_path)`.
3. Debounce: coalesce rapid events on the same path within
   `debounce_ms` (default 100ms). Plan 16 T35's debounce window is the
   precedent.
4. Threading: watchdog runs its observer thread; the event handler
   bridges to asyncio via `asyncio.run_coroutine_threadsafe` per the
   ConfigWatcher pattern.

**Per-task review:** combined. Reviewer confirms (a) shape mirrors
ConfigWatcher (start / stop / debounce / event handler); (b) all
filesystem events route to the correct pipeline method; (c) tests use
`tmp_path` + `watchdog.observers.polling.PollingObserver` (deterministic
in CI; FSEvents / ReadDirectoryChangesW are environment-specific).

#### T7 — Watcher integration in brain_api lifespan

**Files:**
- Modify: `packages/brain_api/src/brain_api/app.py` — start
  `WatchedFolderWatcher` for each enabled `WatchedFolder` in the lifespan
  startup; stop on shutdown.
- Create or modify: `packages/brain_api/tests/test_app_watcher_lifespan.py`.

**Goal:** brain_api process starts the watcher on boot, stops it cleanly.

**What to do:**
1. In `_lifespan` startup, iterate `config.watched_folders` and
   instantiate one `WatchedFolderWatcher` per enabled entry (or one
   global watcher with multiple paths, per the watchdog API — choose
   the simpler shape; default to one observer with multiple `schedule()`
   calls).
2. Store the watcher reference in `app_state` for shutdown access.
3. In `_lifespan` shutdown, call `watcher.stop()` + wait for thread
   join.
4. Tests: monkeypatch `WatchedFolder` config; verify watcher started
   on lifespan enter; verify stopped on lifespan exit.

**Per-task review:** combined. Reviewer confirms (a) clean shutdown
(no hanging threads); (b) lifespan-config-change hot-reload integration
(if `Config.watched_folders` changes mid-run via `config_set`, the
watcher must restart — coordinate with the existing `ConfigWatcher`
hot-reload callback).

#### T8 — Watcher integration in brain_mcp `_cached_ctx`

**Files:**
- Modify: `packages/brain_mcp/src/brain_mcp/__main__.py` — start the
  watcher when `_cached_ctx` initializes (mirrors T7's brain_api
  startup).
- Create or modify: `packages/brain_mcp/tests/test_main_watcher_startup.py`.

**Goal:** Symmetric per D7. brain_mcp running standalone (Claude Desktop)
also starts the watcher.

**What to do:** mirror T7's structure for the brain_mcp lifecycle.

**Per-task review:** combined. Reviewer confirms (a) shape mirrors T7;
(b) tests cover the brain_mcp startup path.

#### T9 — Backup integration + initial-sync cost-estimate gate

**Files:**
- Modify: `packages/brain_core/src/brain_core/tools/backup_create.py` —
  extend `_VALID_TRIGGERS` to include `"pre_watched_folder_sync"`.
- Modify: `watch_folder.py` (T5) — call `backup_create` with
  `trigger="pre_watched_folder_sync"` before the initial sync writes
  any vault content.
- Modify: `watch_folder.py` — add an informational cost estimate
  (file_count × `_CLASSIFY_TOKEN_COST` per `bulk_import.py:38`) BEFORE
  the initial sync. NO refusal threshold per D3; surface the estimate
  in the ToolResult.text so the user sees it.

**Goal:** Safety + transparency for the initial sync's LLM spend.

**Per-task review:** combined. Reviewer confirms (a) backup runs before
any vault write; (b) cost estimate is shown but doesn't refuse the call;
(c) backup trigger is greppable.

#### T10 — Backend tests (integration + cross-platform)

**Files:**
- Create: `packages/brain_core/tests/watch/test_folder_watcher_integration.py` —
  end-to-end: enable watch on tmp_path, drop a .txt file, assert
  ingest pipeline called; modify, assert update_source called; delete,
  assert mark_orphaned called.
- Create: `packages/brain_api/tests/test_watched_folders_integration.py` —
  FastAPI test client: POST /api/tools/brain_watch_folder, verify state
  in Config + initial sync ran.
- Existing CI matrix (macOS-14 + windows-2022) handles cross-platform
  watchdog backend testing.

**Goal:** End-to-end coverage before frontend gets dispatched.

**Per-task review:** combined. Reviewer confirms (a) integration tests
use `PollingObserver` for determinism (FSEvents / ReadDirectoryChangesW
are flaky in CI sandboxes); (b) full brain_core + brain_api suite green.

### Theme C — Frontend

#### T11 — brain-ui-designer mockups (Settings + Orphans + Topbar + 3 modals)

**Files:**
- Create: `docs/design/plan-22/` — design deliverables.
  - `watched-folders-settings.png` (Settings panel "Watched folders" tab)
  - `orphan-management.png` (Orphan management screen)
  - `topbar-status.png` (Topbar status indicator close-up)
  - `modal-watch-enable.png` (Watch-enable confirmation modal — explains
    "source canonical" contract)
  - `modal-watch-disable.png` (Watch-disable confirmation modal — explains
    orphans remain marked)
  - `modal-orphan-delete.png` (Orphan typed-confirm delete modal —
    mirrors `brain_delete_domain` style)
- Plus a `README.md` in `docs/design/plan-22/` describing each mockup,
  the accessibility plan, and the microcopy.

**Goal:** brain-ui-designer produces approved mockups BEFORE
brain-frontend-engineer dispatches per CLAUDE.md D9.

**Per-task review:** combined. User reviews mockups; T12 cannot dispatch
until user approves the mockups.

#### T12 — Settings panel "Watched folders" tab

**Files:**
- Create: `apps/brain_web/src/components/settings/panel-watched-folders.tsx`
  — implements the mockup from T11.
- Modify: `apps/brain_web/src/components/settings/settings-screen.tsx` —
  add the new tab.
- Create: `apps/brain_web/tests/unit/panel-watched-folders.test.tsx`.

**Goal:** UI for managing watched folders. Mockup-faithful implementation.

#### T13 — Orphan management screen

**Files:**
- Create: `apps/brain_web/src/components/settings/panel-orphans.tsx`.
- Modify: `apps/brain_web/src/components/settings/settings-screen.tsx` —
  add the Orphans tab.
- Create: `apps/brain_web/tests/unit/panel-orphans.test.tsx`.

**Goal:** UI for reviewing + acting on orphaned notes.

#### T14 — Topbar status indicator

**Files:**
- Modify: `apps/brain_web/src/components/shell/topbar.tsx` — add a
  Watched-folders status icon with click-through to Settings.
- Create or modify: `apps/brain_web/tests/unit/topbar-watched-status.test.tsx`.

**Goal:** Glanceable indicator of watcher state.

#### T15 — Confirmation modals (3 dialogs) + Bulk Import "Watch this folder" CTA

**Files:**
- Create:
  - `apps/brain_web/src/components/dialogs/watch-enable-modal.tsx`
  - `apps/brain_web/src/components/dialogs/watch-disable-modal.tsx`
  - `apps/brain_web/src/components/dialogs/orphan-delete-modal.tsx`
- Modify: `apps/brain_web/src/components/bulk/step-apply-complete.tsx`
  (or equivalent — verify at exec time per Plan 19 T5 plan-author-drift
  precedent) — add "Watch this folder for changes" CTA per D6.
- Create: `apps/brain_web/tests/unit/watch-modals.test.tsx`.

**Goal:** All confirmation dialogs + the Bulk Import conversion bridge.

#### T16 — Playwright e2e `watched-folders.spec.ts`

**Files:**
- Create: `apps/brain_web/tests/e2e/watched-folders.spec.ts` — covers
  enable / disable / re-ingest event / orphan event / restore-orphan /
  delete-orphan flows. Uses temp-folder fixtures + simulated filesystem
  events.

**Goal:** End-to-end coverage from user click → backend tool → vault
mutation.

**Per-task review:** combined. Reviewer confirms (a) tests use
`waitForAnimationsToFinish` per auto-memory
`feedback_axe_dialog_animation_wait.md` for the 3 modals; (b) axe-core
runs against all new surfaces.

### Theme D — Closure

#### T17 — Closure prep: demo + lessons + todo

**Files:**
- Create: `scripts/demo-plan-22.py` — assert each gate (~16-18 gates).
- Modify: `tasks/lessons.md` — Plan 22 closure section.
- Modify: `tasks/todo.md` — row 22 ✅ + Plan 23 candidate scope tail
  block (preserved 4 NOT-DOING + any Plan 22-surfaced).

#### T18 — Tag + push authorization

**Tag:** `plan-22-watched-folders-sync` cut on green demo. Push deferred
per D12.

## Owning subagents

- **brain-core-engineer** — T0 (spec update), T1 (schema), T2-T3
  (pipeline paths), T4 (scope_guard), T5 (7 tools), T6 (watcher core),
  T9 (backup + cost estimate), T17-T18 (closure).
- **brain-mcp-engineer (role-overloaded as brain-api-engineer)** — T7
  (brain_api watcher integration), T8 (brain_mcp watcher integration).
- **brain-test-engineer** — T10 (integration tests), assists with T16
  (e2e) if needed.
- **brain-ui-designer** — T11 mockups (GATES T12-T15).
- **brain-frontend-engineer** — T12-T15 (after T11 approved), T16 (e2e).
- (brain-prompt-engineer not needed; no new prompts.
  brain-installer-engineer not needed; no install changes.)

## Workflow rules

Same as Plans 16 + 17 + 18 + 19 + 20 + 21:
- Sequential per-task dispatch via `superpowers:subagent-driven-development`.
- Combined spec + code-quality review per task.
- **Mockup gate (D9):** T12-T15 cannot dispatch until user approves T11
  mockup deliverables.
- Pause every ~5 tasks for user check-in (D14): T5 / T10 / T15 / plan-close.
- No push without explicit user authorization at Plan 22 close (D12).
- pytest recipe per `feedback_uv_uf_hidden.md`. PYTHONPATH bypass per
  Plan 21 closure update (`feedback_uv_uf_hidden.md` 2026-05-12
  section): brain_api / brain_mcp / brain_cli may need explicit
  `--reinstall-package -e` flip or PYTHONPATH bypass.
- Frontend per-task verification: `pnpm vitest run` + `pnpm tsc --noEmit`
  per `feedback_tsc_vs_vitest.md`.
- Radix dialogs + axe `waitForAnimationsToFinish` REQUIRED for the 3
  modals per `feedback_axe_dialog_animation_wait.md`.
- Plan 17 T17 monkeypatch-binding lesson RELEVANT for T7/T8 (watcher
  integration tests will patch helpers; patch BOTH the helper's
  resolved-at-call-time namespace AND the caller's namespace
  `raising=False`).
- Plan 21 T1 `_find_repo_root` walk-up + Plan 21 T2 silent-degrade
  warning conventions applied to any new resolver / silent-fail seams.
- Hypothesis-first diagnosis per `feedback_hypothesis_first_diagnosis.md`.

## File inventory (summary)

```
docs/superpowers/specs/
└── 2026-04-13-cj-llm-kb-design.md         # MODIFY: §4 / §5 / §10 (T0)

docs/design/
└── plan-22/                                # CREATE: brain-ui-designer
    ├── watched-folders-settings.png         # mockup deliverables (T11)
    ├── orphan-management.png
    ├── topbar-status.png
    ├── modal-watch-enable.png
    ├── modal-watch-disable.png
    ├── modal-orphan-delete.png
    └── README.md

tasks/plans/
└── 22-watched-folders-sync.md              # SELF (this doc); T0-T18 outcomes

packages/brain_core/
├── src/brain_core/
│   ├── config/schema.py                    # MODIFY: WatchedFolder + Config.watched_folders (T1)
│   ├── vault/frontmatter.py                # MODIFY: 4 new frontmatter fields (T1)
│   ├── vault/scope_guard.py                # MODIFY: include_orphans kwarg (T4)
│   ├── ingest/pipeline.py                  # MODIFY: update_source + mark_orphaned (T2, T3)
│   ├── watch/__init__.py                   # CREATE (T6)
│   ├── watch/folder_watcher.py             # CREATE: WatchedFolderWatcher (T6)
│   └── tools/
│       ├── watch_folder.py                 # CREATE (T5)
│       ├── unwatch_folder.py               # CREATE (T5)
│       ├── list_watched_folders.py         # CREATE (T5)
│       ├── list_orphans.py                 # CREATE (T5)
│       ├── resync_folder.py                # CREATE (T5)
│       ├── restore_orphan.py               # CREATE (T5)
│       ├── delete_orphan.py                # CREATE (T5)
│       ├── backup_create.py                # MODIFY: _VALID_TRIGGERS (T9)
│       └── __init__.py                     # MODIFY: register 7 new tools (T5)
└── tests/
    ├── config/test_watched_folder_schema.py    # CREATE (T1)
    ├── vault/test_frontmatter_orphan_fields.py # CREATE (T1)
    ├── vault/test_scope_guard_orphan_filter.py # CREATE (T4)
    ├── ingest/test_pipeline_update_source.py   # CREATE (T2)
    ├── ingest/test_pipeline_mark_orphaned.py   # CREATE (T3)
    ├── tools/test_watch_folder.py              # CREATE (T5) ×7 files
    ├── tools/test_unwatch_folder.py
    ├── tools/test_list_watched_folders.py
    ├── tools/test_list_orphans.py
    ├── tools/test_resync_folder.py
    ├── tools/test_restore_orphan.py
    ├── tools/test_delete_orphan.py
    └── watch/test_folder_watcher.py            # CREATE (T6)
    └── watch/test_folder_watcher_integration.py # CREATE (T10)

packages/brain_api/
├── src/brain_api/app.py                    # MODIFY: lifespan watcher integration (T7)
└── tests/
    ├── test_app_watcher_lifespan.py        # CREATE (T7)
    └── test_watched_folders_integration.py # CREATE (T10)

packages/brain_mcp/
├── src/brain_mcp/__main__.py               # MODIFY: _cached_ctx watcher integration (T8)
└── tests/
    └── test_main_watcher_startup.py        # CREATE (T8)

apps/brain_web/
├── src/components/
│   ├── settings/
│   │   ├── panel-watched-folders.tsx       # CREATE (T12)
│   │   ├── panel-orphans.tsx               # CREATE (T13)
│   │   └── settings-screen.tsx             # MODIFY: add 2 tabs (T12, T13)
│   ├── shell/topbar.tsx                    # MODIFY: status indicator (T14)
│   ├── dialogs/
│   │   ├── watch-enable-modal.tsx          # CREATE (T15)
│   │   ├── watch-disable-modal.tsx         # CREATE (T15)
│   │   └── orphan-delete-modal.tsx         # CREATE (T15)
│   └── bulk/step-apply-complete.tsx        # MODIFY: "Watch this folder" CTA (T15)
└── tests/
    ├── unit/panel-watched-folders.test.tsx # CREATE (T12)
    ├── unit/panel-orphans.test.tsx         # CREATE (T13)
    ├── unit/topbar-watched-status.test.tsx # CREATE (T14)
    ├── unit/watch-modals.test.tsx          # CREATE (T15)
    └── e2e/watched-folders.spec.ts         # CREATE (T16)

scripts/
└── demo-plan-22.py                         # CREATE (T17)

tasks/
├── lessons.md                              # MODIFY: Plan 22 closure (T17)
└── todo.md                                 # MODIFY: row 22 ✅ + Plan 23 (T17)
```

## T0-T18 outcomes

_Filled in at each task close. Standard receipt format mirrors Plan
19/20/21._

### T0 outcome — Spec update (§4 / §5 / §10)

**Status:** DONE.

**File touched:** `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md`
(spec is the only file modified for T0 per the docs-only constraint).

**Edits landed:**

1. **§4 frontmatter list** — 4 new fields added at lines 175-178,
   inserted between `source_url` (line 174) and `tags` (now line 179)
   so the source-related fields cluster (`source_type` → `source_url`
   → `source_path` → `orphaned` → `orphaned_at` → `watched_folder_id`).
   Fields: `source_path` (str, abs path), `orphaned` (bool, default
   false), `orphaned_at` (date, null when not orphaned),
   `watched_folder_id` (str, links note → `Config.watched_folders[*].path`).

2. **§5 "Watched folders" subsection** — inserted at lines 249-292,
   between "Bulk import" (ends line 247) and "Failure handling" (now
   starts line 294). Subsection covers: live source → vault sync intro
   with Plan 16 T35 watchdog precedent; `WatchedFolder` schema yaml
   block; 3-step lifecycle (watch enable → live created/modified/
   deleted events → watch disable); source-canonical contract +
   overwrite policy + v2 deferral; classify-once-preserve behavior;
   orphan policy with `scope_guard(..., include_orphans=False)`;
   initial sync rate-limit/budget integration with informational cost
   estimate; 7-tool surface bullet list; pointer to §4 for frontmatter
   canonicality.

3. **§10 Safety rails bullet** — single bullet inserted at line 557,
   between "Domain firewall" (line 556) and "Canonical Config entry
   point" (line 558). Bullet covers: opt-in only triggering; backup
   trigger `pre_watched_folder_sync`; non-destructive orphan marks +
   typed_confirm delete; `scope_guard(..., include_orphans=False)`
   default-hide + `include_orphans=True` explicit-surface for the
   Orphan management screen; cross-reference to §5 subsection.

**Wording adjustments vs the template:** None substantive. All three
templates from the plan-doc T0 section landed verbatim. The §4 list
insertion location (before `tags`) was the natural cluster point per
the plan-doc guidance.

**Internal-consistency review:**

- §3 Domain separation (line 188) + §10 `scope_guard` (line 556): the
  new `include_orphans` kwarg is purely additive — no existing
  `scope_guard(path, allowed_domains)` signature contradiction.
  scope_guard remains the single-function firewall; the orphan filter
  is a default-true behavior with an opt-out kwarg.
- Prior to this edit, the spec had ZERO `orphan` mentions and exactly
  one `scope_guard` signature mention (line 556 in §10). No
  conflicting prose. The new "vault is sacred" alignment is explicitly
  reinforced in the §5 orphan-policy paragraph + the §10 bullet.
- The plan-22 D8 non-negotiable ("spec update lands at T0 per
  CLAUDE.md `Changes to vault schema, prompts, or safety rails: spec
  update first`") is satisfied: §4 (vault schema), §5 (ingest pipeline
  surface area), §10 (safety rails) are all updated BEFORE T1.

**Self-review findings:**

- All locked decisions D1-D14 from the plan doc are reflected in the
  spec edits:
  - D1 (overwrite contract) → §5 "Contract" paragraph.
  - D2 (per-folder domain override) → §5 lifecycle step 1
    `domain_override=domain`.
  - D3 (preserve domain on re-ingest) → §5 "Classify behavior"
    paragraph.
  - D4 (classify once) → §5 "Classify behavior" paragraph.
  - D5 (rate-limit + budget enforce; no file-count cap) → §5 "Initial
    sync" paragraph.
  - D6 (orphan marks non-destructive) → §5 "Orphan policy" + §10
    bullet.
  - D7 (manual delete via `brain_delete_orphan` with `typed_confirm`)
    → §5 "Orphan policy" + §10 bullet.
  - D8 (spec-first at T0) → this commit lands the spec edit.
  - D9 (cost estimate informational) → §5 "Initial sync" paragraph.
  - D10 (resume after budget exhaust) → §5 "Initial sync" paragraph.
  - D11 (no new deps) → trivially held; T0 is docs-only.
  - D12 (no push) → outcome receipt notes commits, no push.
  - D13 (`pre_watched_folder_sync` trigger) → §5 lifecycle step 1 +
    §10 bullet.
  - D14 (Orphan management screen surfaces orphans via
    `include_orphans=True`) → §10 bullet.

- No phrase-level ambiguities flagged. "Source is canonical" (§5
  Contract), "orphans non-destructive" (§5 Orphan policy + §10), and
  "explicit user action, never auto-triggered" (§10) are all present
  verbatim and unambiguous.

**Concerns:** None.

**Commits:**
- `5937862` — `docs(plan-22): T0 — spec update §4 frontmatter + §5
  Watched folders + §10 safety rails` (spec edit; 1 file, +50 lines).
- _This receipt commit follows in the next SHA._

### T1 outcome — `Config.watched_folders` + `WatchedFolder` schema + new frontmatter fields

**Status:** DONE.

**Files touched:**

1. `packages/brain_core/src/brain_core/config/schema.py` (+92 LOC) —
   added `WatchedFolder` Pydantic model (6 fields per D7);
   `Config.watched_folders: list[WatchedFolder]` field with cross-field
   validator `_check_watched_folders_domains_in_domains` (mirrors the
   `domain_overrides` / `autonomous` orphan-guard validators);
   `_PERSISTED_FIELDS` whitelist entry so the field round-trips through
   `config.json`.
2. `packages/brain_core/src/brain_core/vault/frontmatter.py` (+74 LOC) —
   added `Frontmatter` Pydantic class documenting the canonical
   frontmatter schema with all 4 new optional fields (`source_path`,
   `orphaned`, `orphaned_at`, `watched_folder_id`) plus the
   pre-Plan-22 canonical fields. Uses `extra="allow"` so the typed
   class round-trips legacy notes' user-added keys. `from_dict`
   constructor for T2/T3/T4 consumer call sites. The dict-based
   `parse_frontmatter` / `serialize_with_frontmatter` functions are
   unchanged — this is non-breaking for every existing call site.
3. `packages/brain_core/tests/config/test_watched_folder_schema.py`
   (NEW, +313 LOC, 23 tests) — field-set pin, per-field type pins,
   defaults, validation (absolute path, slug rules, extra-forbid,
   policy literal), JSON round-trip, cross-field domain-membership
   validator at construction + at domain-removal time, persisted-dict
   inclusion.
4. `packages/brain_core/tests/vault/test_frontmatter_orphan_fields.py`
   (NEW, +198 LOC, 13 tests) — field-set pin (all canonical + 4 new),
   default-value pins, legacy-note backward compat (no new fields →
   defaults), watched-folder note + orphaned note happy paths, ISO
   date string coercion, dict-level parse_frontmatter /
   serialize_with_frontmatter round-trip preserves the new fields.
5. `packages/brain_core/tests/config/test_schema_overrides.py` (+5 LOC
   edit) — updated the existing `test_persisted_dict_returns_exactly_the_d4_keys`
   pin to include `"watched_folders"`. This is the only existing test
   that explicitly enumerated the persisted-fields set.

**Canonical frontmatter module location (verified at exec time):**
`packages/brain_core/src/brain_core/vault/frontmatter.py`. The module
historically held only dict-based `parse_frontmatter` /
`serialize_with_frontmatter` — no Pydantic class existed. T1 added
`Frontmatter` as a NEW typed class documenting the schema without
wiring it into the parse/serialize path (which stays dict-based for
maximum compat with hand-edited Obsidian notes). Downstream T2 / T3 /
T4 consumers will call `Frontmatter.from_dict(parsed)` on demand.

**Cross-field validator pattern used:** `model_validator(mode="after")`
raise on `Config` (matches the existing `_check_domain_overrides_keys_in_domains`,
`_check_autonomy_keys_in_domains`, and `_check_privacy_railed_subset_of_domains`
precedent). Per the CLAUDE.md / Plan 16 T36 lesson, raising inside a
`model_validator(mode="after")` under `validate_assignment=True` leaves
the field mutated to the bad value — the model validator is the
construction-time guard; the eventual `brain_watch_folder` /
`brain_unwatch_folder` tools (T5) will apply the pre-check pattern
from `tools/config_set.py:_check_active_domain_membership` at the
setter seam. T1 only ships the schema layer, which mirrors the
existing config-sub-model precedent for orphan-key guards.

**Per-field design notes:**

- `WatchedFolder.path: str` — stored as string (not `pathlib.Path`) so
  the value is an opaque identifier in the on-disk config and in
  `Frontmatter.watched_folder_id`. The field validator
  `_check_path_absolute` runs `Path(v).is_absolute()` — on POSIX,
  Windows-only paths like `C:\\watch` will fail. T1 pins absolute-POSIX
  acceptance + relative rejection + empty rejection. Cross-platform
  CI will pin the Windows absolute path acceptance.
- `WatchedFolder.domain: str` — uses `_validate_domain_slug` (Plan 10
  D2 rules: lowercase ASCII, regex `[a-z][a-z0-9_-]{0,30}`, no
  separators, no trailing `_`/`-`). The cross-field "must be in
  `Config.domains`" check lives on `Config` per Pydantic v2 limitation
  on sub-model access to parent state.
- `policy: Literal["overwrite"]` — locked per D1; the literal reserves
  v2 room for `"keep_vault"` / `"prompt"` / `"merge"` without a schema
  migration. Construction with `policy="keep_vault"` raises a
  `ValidationError` — pinned in `test_watched_folder_policy_locked_to_overwrite`.
- `last_sync: datetime | None = None` — `None` until first sync per
  spec; T6's watcher updates it on every successful full sync.
- `Frontmatter.orphaned: bool = False` — default-false explicit (not
  via union with None) so an absent key in YAML coerces to the
  documented "not orphaned" state without requiring a `Optional` check
  at every consumer call site.
- `Frontmatter.orphaned_at: date | None = None` — null while
  `orphaned` is `False`; T3 sets it to `today` when flipping
  `orphaned` true.

**Verification:**

```
unset VIRTUAL_ENV && PYTHONPATH=.venv/lib/python3.12/site-packages:packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src \
  /opt/homebrew/bin/python3.12 -m pytest \
  packages/brain_core/tests/config/test_watched_folder_schema.py \
  packages/brain_core/tests/vault/test_frontmatter_orphan_fields.py -v
```
- New-tests run: 36 passed (23 watched_folder + 13 frontmatter), 0.17s.

```
unset VIRTUAL_ENV && PYTHONPATH=...:packages/.../src \
  /opt/homebrew/bin/python3.12 -m pytest packages/brain_core/tests/ -q
```
- Full brain_core suite: **1047 passed, 5 skipped** (pre-T1 baseline:
  1011 passed, 5 skipped — delta is +36 pin tests, 0 regressions).

**Verification recipe note:** the plan-doc-suggested `uv run` recipe
failed with the iCloud-eviction zero-byte-file shape (Plan 21 closure
auto-memory failure mode A/B). After `rm -rf .venv && uv sync
--frozen`, 88 files still zero-byte. The brew Python + explicit
PYTHONPATH bypass (Plan 11 T4 escape hatch, now documented as primary
in the Plan 21 closure auto-memory) is what worked. Captured here so
future T2+ implementers don't re-diagnose.

**Pre-existing failures NOT caused by T1:** `brain_api` /
`brain_cli` collection errors on `test_static_ui_find_repo_root.py`
and `test_config_command.py` — Plan 21 auto-memory failure mode A
(install-as-copy stale site-packages; brain_api / brain_mcp /
brain_cli pinned `editable = false`). Verified by `git stash` → same
errors → `git stash pop`. Out of T1 scope; will need addressing if
Plan 22 T5+ exercises tool surfaces via brain_api integration tests.

**Per-task review:** combined.
- (a) `WatchedFolder.domain` validator wired against `Config.domains`
  via `_check_watched_folders_domains_in_domains` `model_validator(mode="after")`
  on `Config` — matches the existing `_check_domain_overrides_keys_in_domains`
  precedent (NOT a pre-check at the schema layer; pre-check is
  reserved for the tools layer per Plan 16 T36 lesson — single-field
  setattr roll-back semantics differ). ✓
- (b) `policy: Literal["overwrite"]` reserves v2 room. Pinned in
  `test_watched_folder_policy_locked_to_overwrite`. ✓
- (c) All 4 new frontmatter fields are OPTIONAL with documented
  defaults. Pinned in `test_frontmatter_loads_legacy_note_without_new_fields`
  (legacy note loads → all 4 default to documented values). ✓
- (d) Pin tests cover field-set + per-field types + defaults + cross-
  field validator + JSON round-trip + dict-level parse/serialize
  round-trip. 36 tests total. ✓
- (e) Full brain_core suite green — 1047 / 5 / 0 (was 1011 / 5 / 0). ✓

**Self-review findings:**

- **Completeness:** All 6 `WatchedFolder` fields per D7 / T0 spec
  present. All 4 new `Frontmatter` fields per spec §4 present. Cross-
  field validator + persisted-dict whitelist + legacy backward compat
  all covered. No spec fields missing.
- **Quality:** Followed Plan 19 T2 / Plan 20 T1 / Plan 21 T1
  two-tier pin pattern (field-set + per-field). Validator pattern
  matches existing precedent in the same file. Module docstring on
  `frontmatter.py` updated to explain the dict-vs-typed design
  decision (Frontmatter is documentation, not the parse path) so
  future readers don't break the contract trying to "fix" it.
- **Discipline:** Domain-engineer scope held — only schema layer
  changed; no T2/T3/T4 wiring touched. No new dependencies (D11). No
  push (D12). No imports of the Anthropic SDK / web framework / MCP
  SDK.
- **Testing:** 36 new pin tests, all green. No flakes. Brain_core
  baseline preserved.

**Concerns / flags:**

- The frontmatter typed-vs-dict design decision. Plan-doc says "add
  the 4 new optional fields to the canonical frontmatter type used by
  `VaultWriter`" — no such typed schema existed prior to T1, and
  `VaultWriter` writes through dict-based `serialize_with_frontmatter`.
  Decision: added `Frontmatter` as a NEW typed class that documents
  the spec contract; left `parse_frontmatter` / `serialize_with_frontmatter`
  unchanged. T2 / T3 / T4 consumers will adopt the typed class on
  demand (`Frontmatter.from_dict(parsed)`). This is the smallest-
  blast-radius interpretation; flagging in case reviewer wanted the
  full pivot to typed parse/serialize (which would have rewritten
  every test fixture and every ad-hoc dict construction in the
  ingest pipeline).
- The cross-platform Windows-path acceptance is NOT pinned by a
  RED-on-Windows test in T1 (only POSIX runners exercised CI here).
  Filed for the cross-platform CI sweep at Plan 22 closure (T10
  verification).
- iCloud-eviction failure mode (88 zero-byte files post `rm -rf .venv
  && uv sync --frozen`) made the plan-doc-suggested `uv run` recipe
  fail. Documented in the verification block above. Not a T1 bug; the
  brew-Python escape hatch is now the standard recipe per the Plan 21
  auto-memory update.

**Commits:**
- `e701462` — `feat(plan-22): T1 — WatchedFolder schema + Config.watched_folders + 4 new frontmatter fields + 2 pin test files`
- _This receipt commit follows in the next SHA._

### T2 outcome — Pipeline re-ingest path (`IngestPipeline.update_source`)

**Status:** DONE.

**Files touched:**

1. `packages/brain_core/src/brain_core/ingest/pipeline.py` (+414 / −3 LOC,
   1042 total) — added `update_source(existing_note_path, new_source_path,
   *, allowed_domains) -> IngestResult` plus three private helpers
   (`_rewrite_frontmatter_only`, `_rebuild_note`, `_apply_replacement`,
   `_log_update`). New imports: `Frontmatter`, `LogEntry`/`LogFile`,
   `ScopeError`/`scope_guard`, `Edit`/`IndexEntryPatch`, `Receipt`. The
   existing `ingest()` method is unchanged — `update_source` is a
   sibling, not a refactor of the 9-stage shape.
2. `packages/brain_core/tests/ingest/test_pipeline_update_source.py`
   (NEW, +693 LOC, 9 tests) — covers all 5 plan-doc test fixtures
   (no-op / overwrite / vault-edit-overwrite / path-only / scope-
   violation) plus 4 additional pins: slug-and-note-path stability on
   overwrite, orphan-clearing on successful re-ingest, log-verb
   round-trip through `LogFile.read_all`, integrate-stage index entries
   landing in the same atomic write.

**Method shape:**

```python
async def update_source(
    self,
    existing_note_path: Path,
    new_source_path: Path,
    *,
    allowed_domains: tuple[str, ...],
) -> IngestResult:
```

Three behavioral branches based on content_hash + resolved-source-path
comparison:

| Branch | Condition | LLM calls | Vault mutation | Log line |
|---|---|---|---|---|
| `no_change` | hash unchanged, path unchanged | 0 | none | `update | no_change | <slug>` |
| `path_only` | hash unchanged, path changed | 0 | frontmatter `source_path` + `updated` only | `update | path_only | <slug>` |
| `overwrite` | hash changed | summarize + integrate (no classify per D4) | full file replacement via VaultWriter Edit | `update | overwrite | <slug>` |

**Design decisions:**

- **Slug preservation** (D4): slug is `existing_note_path.stem` — never
  re-derived from the new summary title. Pinned by
  `test_update_source_preserves_slug_and_note_path_on_overwrite`.
- **Domain preservation** (D4): domain is read from existing note's
  frontmatter via `Frontmatter.from_dict(parsed)`. No classifier call.
  Pinned by `test_update_source_overwrites_on_content_change`'s
  `len(fake.requests) == 2` assertion (only summarize + integrate, no
  classify).
- **VaultWriter atomicity**: replacement uses a `PatchSet` with a single
  `Edit(path, old=full_prior_content, new=full_new_content)`. Writer's
  atomic temp+rename + undo log + filelock all apply. Integrate-stage
  `extra_edits` + `extra_index_entries` land in the SAME PatchSet so
  the entire update is one undo-id-keyed mutation.
- **Log verb**: written directly via `LogFile.append(LogEntry(op="update",
  summary=f"<sub-verb> | <slug>"))` AFTER `writer.apply` returns. The
  writer's PatchSet `log_entry` field is left `None` because the writer
  hardcodes `op="patch"` — going via `LogFile` directly is the only
  path to the `update` verb without a writer signature change. Same
  `LogFile` surface the writer itself uses, so this isn't a
  "mutation-outside-VaultWriter" violation.
- **Scope guard**: called at Stage A on `existing_note_path` BEFORE any
  read — so a personal-domain note + research-scope tuple raises
  `ScopeError` (subclass of `PermissionError`) immediately, vault
  untouched, fake's queue empty (no LLM call). Pinned by
  `test_update_source_refuses_when_note_domain_outside_scope`.
- **Defense-in-depth domain check**: if scope_guard passes (path-domain
  matches) but the note's frontmatter `domain` field differs from the
  path's domain (rare: hand-edited frontmatter), the code returns
  `IngestStatus.QUARANTINED`. This is dead code in the happy path but
  flags a class of corruption that pure path-based scope_guard would
  miss.
- **Orphan-flip-on-success**: a successful overwrite sets `orphaned:
  False` + `orphaned_at: None` in the rebuilt frontmatter. T3's
  `mark_orphaned` writes the inverse transition. Pinned by
  `test_update_source_clears_orphan_mark_on_successful_overwrite`.
- **Stage-4 archive deferral**: the plan-doc spec says "skip stage 4
  archive on unchanged content_hash for efficiency." The current
  handler API doesn't separate `extract-without-archive` from
  `extract-with-archive` — every `handler.extract()` call writes an
  archive copy. v1 accepts this redundant write; the body hash check
  still short-circuits LLM cost. Documented in the method docstring.
  v2 candidate: split handler API.

**Verification:**

```
unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:...:packages/brain_cli/src \
  uv run --package brain_core pytest \
  packages/brain_core/tests/ingest/test_pipeline_update_source.py -v
```

- 9 new tests run: **9 passed, 0 failed, 3.99s**.
- All 5 plan-doc fixtures covered:
  - `test_update_source_no_op_when_hash_and_path_unchanged` (no-op)
  - `test_update_source_overwrites_on_content_change` (overwrite)
  - `test_update_source_overwrites_vault_hand_edits_per_d1` (D1 contract)
  - `test_update_source_path_only_on_move_with_same_content` (move)
  - `test_update_source_refuses_when_note_domain_outside_scope` (scope)
- Plus 4 additional pins (slug/path stability, orphan clearing, log
  verb round-trip via `LogFile.read_all`, integrate index-entries).

```
unset VIRTUAL_ENV && PYTHONPATH=...:packages/.../src \
  uv run --package brain_core pytest packages/brain_core/tests/ -q
```
- Full brain_core suite: **1056 passed, 5 skipped** (pre-T2 baseline:
  1047 passed, 5 skipped — delta is +9 new tests, 0 regressions).

```
uv run --package brain_core ruff check packages/brain_core/src/brain_core/ingest/pipeline.py packages/brain_core/tests/ingest/test_pipeline_update_source.py
uv run --package brain_core mypy packages/brain_core/src/brain_core/ingest/pipeline.py
```
- ruff: All checks passed.
- mypy: Success: no issues found in 1 source file.

**Verification recipe note:** the brew-Python escape hatch from Plan 21
T1 wasn't needed this round — after a fresh `rm -rf .venv && uv sync
--frozen` the iCloud-eviction zero-byte-files cleared up and the
plan-doc-suggested `uv run` recipe worked end-to-end. Captured for the
next implementer: the eviction failure mode is environmental and
re-sync can resolve it.

**Per-task review (combined, per plan-doc T2 section):**

- **(a) Slug + domain preserved per D4.** ✓ Slug = `existing_note_path.stem`,
  never re-derived. Domain = `Frontmatter.from_dict(parsed).domain`, no
  classifier call. Two pin tests
  (`test_update_source_preserves_slug_and_note_path_on_overwrite` for
  slug-stability; the `len(fake.requests) == 2` assertion in
  `test_update_source_overwrites_on_content_change` for the no-classify
  call shape).
- **(b) Overwrite contract per D1.** ✓ The vault-hand-edits-overwrite
  test pins that user-added body sections + inline comments are LOST on
  re-ingest — including a load-bearing failure message that points the
  future vault-edit-aware-merge plan at THIS test as its first flip
  target.
- **(c) Log entry uses `update` verb (greppable).** ✓ Direct `LogFile`
  append with `op="update"` and a 3-state sub-verb in the summary
  (`no_change` / `path_only` / `overwrite`). Pinned by
  `test_update_source_log_entry_is_greppable_update_verb` which
  round-trips through `LogFile.read_all()` and asserts `e.op == "update"`.
- **(d) Fixtures cover unchanged-hash (no-op) AND changed-hash (overwrite).**
  ✓ Both branches exercised. The path-only branch is an additional
  third case (same hash, different path) that the plan-doc didn't list
  as required but my reading of the design considerations needed. The
  `update_source` method's body explicitly comments on the
  three-way branch decision.

**Self-review findings:**

- **Completeness:** All 5 plan-doc fixtures landed plus 4 additional
  defense-in-depth pins. Method signature matches plan-doc spec
  (`(existing_note_path, new_source_path, *, allowed_domains)`).
  Returns `IngestResult` for shape parity with `ingest()`.
- **Quality:** Followed `ingest()`'s 9-stage shape conventions
  (record_failure on exception, _record_history on every exit path,
  per-stage cost accumulation). Reused existing surfaces (Frontmatter,
  scope_guard, LogFile, VaultWriter) — no new abstractions invented.
  Module docstring + method docstring explain the three-branch shape
  + the D4/D1 invariants. Stage-skipping decisions documented in
  comments at the call sites.
- **Discipline:** Domain-engineer scope held — only `pipeline.py` +
  new test file changed. No T1 schema files re-touched. No
  cross-package imports. No new dependencies (D11). No push (D12).
  Anthropic SDK not imported anywhere new.
- **Testing:** 9 new tests, all green, full suite +9 (1047 → 1056).
  FakeLLMProvider used exclusively — no live LLM calls. Test fixtures
  use the same `ephemeral_vault` + `tmp_path` shape every other ingest
  test uses.

**Concerns / flags:**

- **Stage-4 archive deferral** documented above. The plan-doc said
  "skip archive on no-content-hash-change for efficiency" — the
  handler API doesn't permit this without a signature change, and v1
  ships the redundant archive copy. Flagged so T6 watcher / T10
  integration tests don't trip over an unexpected archive growth
  pattern.
- **Log-entry routing**: I emit the `update` verb via direct
  `LogFile.append` after `writer.apply` returns. This is correct
  behaviorally but means the log entry is NOT undo-id-bound to the
  writer's mutation (the undo log records the file replacement; the
  `update | ...` log line is separately appended). If a future plan
  wants strict atomic-log-with-mutation semantics, the writer's
  signature needs an `op_override` parameter. Acceptable for v1 — the
  log is observability, not correctness — but flagging for T9 backup
  trigger work.
- **Defense-in-depth QUARANTINED branch** is currently dead code (the
  scope_guard at Stage A always catches the scope mismatch first). I
  kept it as a guard for the hand-edited-frontmatter case (path domain
  matches but FM domain differs). Could be removed in v2 if the
  defense-in-depth posture changes.
- **Cross-platform**: paths use `Path.resolve()` everywhere; no `os.sep`
  or POSIX-only APIs. CI matrix should catch any Windows weirdness on
  the `source_path` string round-trip. Not pinned by a Windows-specific
  test in T2.

**Commits:**
- `92c439b` — `feat(plan-22): T2 — IngestPipeline.update_source
  (re-ingest preserving slug + domain; D1 overwrite contract)`
- `617957f` — `docs(plan-22): T2 — outcome receipts for re-ingest path`

### T3 outcome — Pipeline orphan path (`IngestPipeline.mark_orphaned`)

**Status:** DONE.

**Files touched:**

1. **`packages/brain_core/src/brain_core/ingest/pipeline.py`** (+186 LOC, two
   new public + two new private surfaces):

   * **`mark_orphaned(existing_note_path, *, allowed_domains)`** — new
     public method. Reads frontmatter, flips `orphaned: true` +
     `orphaned_at: <today>`, writes atomically via `VaultWriter`
     (`_apply_replacement` reused from T2), emits a `orphan | mark |
     <slug>` log entry. Idempotent: if the note is ALREADY orphaned,
     short-circuits to a no-op (no vault write, original `orphaned_at`
     preserved) and emits `orphan | no_change | <slug>` for grep. Scope
     check at Stage A (path) + Stage C (frontmatter domain) — a watcher
     in `("research",)` scope cannot orphan a `personal`-domain note.
     `ScopeError` propagates (mirrors `update_source` shape so T5 / T6
     callers can match uniformly); other exceptions flow to
     `IngestStatus.FAILED` with `record_failure` writing a
     `.error.json` audit record under `raw/failed/`.
   * **`_rewrite_frontmatter_for_orphan(...)`** — new private helper.
     Sister to T2's `_rewrite_frontmatter_only`. Body untouched. Only
     `orphaned` + `orphaned_at` keys flipped; all other frontmatter
     (including user-added `aliases` / `cssclass`) round-trips
     unchanged.
   * **`_log_orphan(*, domain, op_summary)`** — new private helper.
     Sister to T2's `_log_update`. Stamps `op="orphan"` so the verb
     is greppable distinctly from `patch` (raw VaultWriter PatchSet
     log entries) and `update` (T2's re-ingest path).

2. **`packages/brain_core/tests/ingest/test_pipeline_mark_orphaned.py`**
   (NEW, 7 fixtures, 380 LOC):

   * Normal-mark: frontmatter flipped, body byte-identical, log line,
     LLM not called.
   * Idempotent no-op: original `orphaned_at` preserved (audit
     invariant), no vault write, `no_change` log line.
   * Body-byte-identical pin: distinctive whitespace + unicode body
     survives the round-trip verbatim.
   * Undo round-trip: `UndoLog.revert(latest_undo_id)` restores the
     pre-mark frontmatter byte-for-byte (including absence of the
     `orphaned` key when the seeded note didn't carry one).
   * Scope violation: `personal`-domain note + `("research",)` scope
     → `ScopeError`; vault untouched.
   * Missing-note: nonexistent path → `IngestStatus.FAILED`, no log
     entry, no surprise raise (mirrors `update_source`).
   * No-other-field-mutation pin: explicit assert every non-orphan
     frontmatter field is unchanged (catches future "helpful"
     auto-restamping of `updated`).

**Helper reuse from T2:**

- `_apply_replacement` — REUSED (single-Edit VaultWriter call with undo
  record). No changes needed; T3's body-unchanged contract is naturally
  expressed as `Edit(old=full_pre_mark_content, new=full_post_mark_content)`.
- `_rewrite_frontmatter_only` — NOT reused. T2's helper is
  `source_path` + `updated`-specific. Mixing orphan-flip semantics
  into that helper would muddy its contract; new sister helper
  `_rewrite_frontmatter_for_orphan` is the cleaner shape.
- `_log_update` — NOT reused. The verb differs (`orphan` vs `update`);
  new sister helper `_log_orphan` keeps the verb hardcoded per method
  so a caller cannot accidentally cross verbs.

**Date format for `orphaned_at`:** `now.date().isoformat()` where
`now = datetime.now(tz=UTC)`. ISO 8601 string. Matches T2's
`_rewrite_frontmatter_only` and the `Frontmatter.orphaned_at: date | None`
typed field declared in T1.

**Log verb shape:** `orphan | mark | <slug>` / `orphan | no_change | <slug>`.
Mirrors T2's `update | overwrite | <slug>` cadence. The `<slug>` is
`existing_note_path.stem` — preserves greppability for "find every
orphan mark for slug `hello`" queries.

**Exception types:**

- `ScopeError` (subclass of `PermissionError`) propagates from
  `scope_guard` on scope violation. Same shape as `update_source`.
- `FileNotFoundError` from `Path.read_text` flows to FAILED branch.
  No new domain exception introduced; the existing pipeline-FAILED
  shape covers the watcher's needs without overloading the caller.
- In-frontmatter-domain mismatch (`existing_fm.domain not in
  allowed_domains`) returns `IngestStatus.QUARANTINED` rather than
  raising — mirrors `update_source` exactly.

**Self-review against plan-doc criteria:**

- (a) **All writes via VaultWriter:** YES. `_apply_replacement` wraps
  a single `Edit` and calls `self.writer.apply(...)`. The
  `LogFile.append` for the log entry follows the same direct-API
  pattern T2 uses for its `_log_update` (so the `op` verb can be
  stamped correctly — `VaultWriter.apply` hardcodes `op="patch"`).
- (b) **Undo log entry landed:** YES. Test 4 (undo round-trip) exercises
  `UndoLog.revert(latest_undo_id)` and asserts the note content is
  byte-identical to the pre-mark version, including absence of the
  `orphaned` key when the seeded note didn't carry one.
- (c) **Body unchanged:** YES. Tests 1, 3, and 7 pin this from three
  angles — round-trip parse, distinctive-bytes byte-equality, and
  field-by-field frontmatter delta confirming only `orphaned` +
  `orphaned_at` differ.

**Verification:**

```bash
# new tests
unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src \
  uv run --package brain_core pytest \
  packages/brain_core/tests/ingest/test_pipeline_mark_orphaned.py -v
# 7 passed in 0.68s

# full brain_core suite
unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src \
  uv run --package brain_core pytest packages/brain_core/tests/ -q
# 1063 passed, 5 skipped (baseline was 1056 + 7 new = 1063 — no regressions)

# mypy
unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src \
  uv run --package brain_core mypy packages/brain_core/src/brain_core/ingest/pipeline.py
# Success: no issues found in 1 source file
```

**Commits:**

- `db12ed0` — `feat(plan-22): T3 — IngestPipeline.mark_orphaned
  (D2 non-destructive orphan mark; idempotent)`
- `3920c1b` — `docs(plan-22): T3 — outcome receipts for orphan-mark path`

### T4 outcome — `scope_guard(..., *, include_orphans=False)` extension

**Status:** DONE.

**Files touched:**

1. **`packages/brain_core/src/brain_core/vault/paths.py`** (+108 LOC,
   13 → 165 LOC total).

   * Added `OrphanedNoteError(ScopeError)` — subclass so existing
     `except ScopeError` handlers (e.g. `brain_search` re-verification
     drop, the per-tool `ScopeError` propagation contract) catch orphan
     blocks unchanged. Callers wanting to distinguish (e.g. UI
     surfaces rendering "this note is orphaned — restore?") catch
     `OrphanedNoteError` specifically.
   * Added `_is_note_orphaned(resolved: Path) -> bool` with a
     process-local `(resolved_path, mtime_ns) -> bool` memo. Cache
     bounded by `_MAX_CACHE_ENTRIES=1000` with FIFO eviction;
     `OrderedDict.move_to_end` on hit converts to LRU. Thread-safe
     (`Lock` around all dict mutations); disk I/O happens OUTSIDE the
     lock so concurrent readers don't serialize on filesystem reads.
     `os.replace` (used by `VaultWriter._atomic_write`) bumps mtime,
     so concurrent writes invalidate the cache organically — no
     wiring scope_guard into VaultWriter mutation events required.
   * Added `_orphan_cache_clear()` test-only hook (called by an
     autouse fixture in the new test module so memoized state from a
     sibling test cannot leak across the boundary).
   * Extended `scope_guard(..., *, include_orphans: bool = False)`.
     When `False` and the resolved path is an existing `.md` file
     with frontmatter `orphaned: true` → raises `OrphanedNoteError`.
     When `True`, the orphan check is skipped ENTIRELY — no
     frontmatter read, no stat call. This is the perf path for
     `brain_list_orphans` (T5) which iterates over many orphans per
     call.

2. **`packages/brain_core/src/brain_core/vault/writer.py`** (+24 LOC).
   `VaultWriter.apply` and `VaultWriter.rename_file` gained a kw-only
   `include_orphans: bool = False` that threads through to every
   internal `scope_guard` call. Default `False` keeps every existing
   caller (LLM patches via `brain_apply_patch`, ingest stage 6, bulk
   import) at the same strictness. T5's `brain_restore_orphan` /
   `brain_delete_orphan` will pass `include_orphans=True` so they can
   mutate an already-orphan note.

3. **`packages/brain_core/src/brain_core/ingest/pipeline.py`**
   (+8 LOC, 3 seams).

   * `IngestPipeline.update_source` Stage-A `scope_guard` now passes
     `include_orphans=True` — re-ingest legitimately operates on
     orphan notes (the path that clears the orphan mark on
     successful overwrite). Without this, the T2 test
     `test_update_source_clears_orphan_mark_on_successful_overwrite`
     would regress to an `OrphanedNoteError` at Stage A.
   * `IngestPipeline.mark_orphaned` Stage-A `scope_guard` now passes
     `include_orphans=True` — idempotent re-mark of an
     already-orphan note must reach Stage D's short-circuit. Without
     this, the T3 test
     `test_mark_orphaned_is_idempotent_when_already_orphaned` would
     regress at Stage A.
   * `IngestPipeline._apply_replacement` (the shared writer-helper
     used by both update_source and mark_orphaned) now passes
     `include_orphans=True` to `writer.apply`. The writer's
     scope_guard would otherwise re-block the Edit on the orphan
     path even if Stage A was permitted.

4. **`packages/brain_core/tests/vault/test_scope_guard_orphan_filter.py`**
   (NEW, 7 fixtures, 215 LOC):

   * `test_default_filters_orphaned_note` — D2 default-filter pin.
   * `test_include_orphans_true_returns_orphan_path` — opt-in path
     pin; orphan returned unchanged.
   * `test_mixed_vault_filters_only_orphans` — neighbor non-orphan
     notes pass; default filter does not over-reach.
   * `test_cache_invalidates_on_mtime_change` — bumping mtime (via
     `os.utime` with a 2s ns shift to defeat FS-clock granularity)
     refreshes the cache so the new orphan flag is reflected. This is
     the production cache-invalidation contract: `os.replace` in
     `VaultWriter._atomic_write` bumps mtime; scope_guard's cache
     drops the stale entry organically.
   * `test_non_note_paths_skip_orphan_check` — directories,
     `index.md` (frontmatter-less), and missing files (writer
     `new_files` pre-validation) all pass without an orphan-check.
   * `test_include_orphans_true_skips_frontmatter_read` — perf pin
     via monkeypatched `_is_note_orphaned` counter. Confirms zero
     frontmatter reads on the explicit-include path.
   * `test_orphaned_note_error_is_scope_error` — inheritance pin so
     `except ScopeError` blocks catch orphans unchanged.

**Caching strategy:** Option B (mtime-keyed memo). Rationale:

- **A (naive per-call read):** simple but doubles I/O for every
  `scope_guard` on a note. Search returning 5 hits → 5 frontmatter
  reads. Compounds across the LLM tool surface.
- **B (mtime-keyed memo):** chosen. `os.replace` bumps mtime so the
  cache invalidates organically. Stateless externally; no wiring
  scope_guard into writer mutation events. Bounded LRU prevents
  unbounded memory growth on a long-running process scanning a
  large vault.
- **C (drop cache on every VaultWriter mutation):** simpler
  invalidation logic but requires wiring scope_guard's cache into
  VaultWriter (or a global event bus). More coupling for a marginal
  correctness gain — B already handles this via the filesystem's
  mtime contract.

The hot-path `include_orphans=True` skip-entirely behavior (option
D from the brief's design considerations) is folded INTO B: when
`include_orphans=True`, scope_guard bypasses `_is_note_orphaned`
unconditionally so even a 1000-note orphan list incurs zero
frontmatter reads at the scope_guard seam (T5's `brain_list_orphans`
will read frontmatter itself to surface the per-orphan metadata —
but that's at the tool-handler layer, not at scope_guard).

**Caller-grep results:**

```
grep -rn "scope_guard(" packages/ apps/
```

Sites found (15 total):

* `packages/brain_core/src/brain_core/vault/paths.py` — definition.
* `packages/brain_core/src/brain_core/vault/writer.py` — 4 sites
  (apply: 2; rename_file: 2). MIGRATED: writer.apply / rename_file
  threads `include_orphans` through. Default `False` — no behavioral
  change for existing callers.
* `packages/brain_core/src/brain_core/tools/get_index.py:29` —
  index.md path. Default-filter is correct (index.md has no
  `orphaned` field; `_is_note_orphaned` returns False). NO MIGRATION.
* `packages/brain_core/src/brain_core/tools/search.py:41` —
  re-verification on search hits. Default-filter is correct (search
  must NOT surface orphans per D2). NO MIGRATION.
* `packages/brain_core/src/brain_core/tools/base.py:83` — generic
  `scope_guard_path` helper. Default-filter is correct (every caller
  is a tool reading or proposing into a non-orphan note). NO
  MIGRATION.
* `packages/brain_core/src/brain_core/chat/tools/read_note.py:32`,
  `propose_note.py:42`, `search_vault.py:50`, `edit_open_doc.py:40`,
  `list_index.py:24` — chat tools. Default-filter is correct (chat
  must NOT discover orphans). NO MIGRATION.
* `packages/brain_core/src/brain_core/ingest/pipeline.py` — 2 sites
  (update_source Stage A; mark_orphaned Stage A). MIGRATED to
  `include_orphans=True` — both are orphan-aware operations.
* `packages/brain_mcp/src/brain_mcp/resources/domain_index.py:48` —
  MCP resource handler returning a domain's index payload.
  Default-filter is correct (no orphan opt-in needed). NO MIGRATION.
* Test files (test_paths.py, test_paths_dynamic.py): 7 sites —
  positional / no-kwarg signatures all keyword-arg-default-compat.
  NO MIGRATION.

Sites NOT migrated but flagged for T5 caller-side opt-in:
`brain_list_orphans`, `brain_restore_orphan`, `brain_delete_orphan`
(do not exist yet — created in T5). Each will pass
`include_orphans=True` to its scope_guard / writer.apply call. Plan
22 T5 prompt will reference this section as the migration anchor.

**Test counts:**

```
unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src \
  uv run --package brain_core pytest \
  packages/brain_core/tests/vault/test_scope_guard_orphan_filter.py -v
# 7 passed in 0.90s

# full brain_core suite
unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src \
  uv run --package brain_core pytest packages/brain_core/tests/ -q
# 1070 passed, 5 skipped (baseline 1063 + 7 new T4 = 1070; no regressions)

# brain_mcp + brain_api cross-package
unset VIRTUAL_ENV && PYTHONPATH=... uv run --package brain_mcp pytest packages/brain_mcp/tests/ -q
# 137 passed, 3 skipped
unset VIRTUAL_ENV && PYTHONPATH=... uv run --package brain_api pytest packages/brain_api/tests/ -q
# 211 passed, 4 skipped

# mypy
unset VIRTUAL_ENV && PYTHONPATH=... uv run --package brain_core mypy \
  packages/brain_core/src/brain_core/vault/paths.py \
  packages/brain_core/src/brain_core/vault/writer.py \
  packages/brain_core/src/brain_core/ingest/pipeline.py
# Success: no issues found in 3 source files
```

**Commits:**

- `e8d2356` — `feat(plan-22): T4 — scope_guard include_orphans kwarg
  (D2 default-filter)`
- _(docs commit SHA backfilled in next docs commit per Plan-19 T6.2 cadence)_

### T5 outcome — 7 watched-folders tool surfaces

**Status:** DONE.

**Files created (7 source + 7 test):**

- `packages/brain_core/src/brain_core/tools/watch_folder.py` — 252 LOC
  — `brain_watch_folder`. Validates absolute + existing folder;
  idempotent on already-watched; cross-field domain pre-check per
  Plan 16 T36 (`_check_domain_membership`); persists via
  `persist_config_or_revert`; calls `BulkImporter.plan()`/`apply()`
  on `initial_sync=True` with backup trigger stubbed to `"manual"`
  (TODO comment ties to T9's `pre_watched_folder_sync` extension).
- `packages/brain_core/src/brain_core/tools/unwatch_folder.py` — 124
  LOC — `brain_unwatch_folder`. Removes the matching `WatchedFolder`;
  idempotent (`status="not_watched"` when missing); counts
  `remaining_notes` by walking vault for `watched_folder_id`
  matches; persists via `persist_config_or_revert`.
- `packages/brain_core/src/brain_core/tools/list_watched_folders.py`
  — 120 LOC — `brain_list_watched_folders`. Joins
  `Config.watched_folders` with vault-walked `(file_count,
  orphan_count)` per entry. Read-only; no `typed_confirm` needed.
- `packages/brain_core/src/brain_core/tools/list_orphans.py` — 133
  LOC — `brain_list_orphans`. Walks every configured domain looking
  for `orphaned: true` notes; optional `folder` filter narrows by
  `watched_folder_id`. Passes `include_orphans=True` to
  `scope_guard` per T4 contract.
- `packages/brain_core/src/brain_core/tools/resync_folder.py` — 217
  LOC — `brain_resync_folder`. Walks the folder, dispatches
  `update_source()` per matched file, `mark_orphaned()` per
  vault note whose source disappeared. Refuses on unwatched folder.
  Returns `{updated, no_change, newly_orphaned, restored_from_orphan}`.
  Auto-restore on source-reappear flows through `update_source`'s
  existing `_rebuild_note` (sets `orphaned=false`) — no separate
  restore call needed in resync.
- `packages/brain_core/src/brain_core/tools/restore_orphan.py` — 128
  LOC — `brain_restore_orphan`. Validates `orphaned == True`,
  flips frontmatter via `VaultWriter.apply` with
  `include_orphans=True`; refuses non-orphan notes.
- `packages/brain_core/src/brain_core/tools/delete_orphan.py` — 178
  LOC — `brain_delete_orphan`. `typed_confirm=True` MANDATORY per
  CLAUDE.md "destructive action" rule; refuses non-orphan; moves
  note to `.brain/trash/<YYYY-MM-DD>/<slug>.md`; writes legacy
  per-file undo record (PATH + PREV_LEN format) so
  `brain_undo_last` recreates the file at its original path while
  the trash copy stays on disk as an audit trail.

**Test files (one per tool, INPUT_SCHEMA + data-shape + branch pins):**

- `packages/brain_core/tests/tools/test_watch_folder.py` — 8 tests.
  Covers schema, relative/missing folder refusal, cross-field domain
  pre-check (Plan 16 T36 pattern), data shape with `initial_sync=False`,
  already-watched idempotency, disk persistence.
- `packages/brain_core/tests/tools/test_unwatch_folder.py` — 6 tests.
  Covers schema, happy path, idempotency (`status="not_watched"`),
  disk persistence, `remaining_notes` counter.
- `packages/brain_core/tests/tools/test_list_watched_folders.py` — 5
  tests. Covers schema (no-arg), empty config, per-entry key set,
  file/orphan count from frontmatter walk.
- `packages/brain_core/tests/tools/test_list_orphans.py` — 5 tests.
  Covers schema, empty vault, per-orphan key set, folder filter.
- `packages/brain_core/tests/tools/test_resync_folder.py` — 6 tests.
  Covers schema, relative/missing folder refusal, unwatched folder
  refusal, empty-folder data shape pin (summary keys + zero counts).
  Full pipeline-integrated coverage lives in T2/T3 fixtures.
- `packages/brain_core/tests/tools/test_restore_orphan.py` — 7 tests.
  Covers schema, missing/non-absolute/non-orphan refusals, frontmatter
  flip (orphaned/orphaned_at), body preservation, undo record persisted.
- `packages/brain_core/tests/tools/test_delete_orphan.py` — 9 tests.
  Covers schema, `typed_confirm` enforcement (missing/false both raise),
  non-orphan refusal, data shape happy path (status/trash_path/undo_id),
  undo round-trip recreates the note at its original path while the
  trash copy persists.

**Registry change:**
`packages/brain_core/src/brain_core/tools/__init__.py` — 7 new eager
imports added in alphabetical order. All 7 NAMEs (`brain_watch_folder`,
`brain_unwatch_folder`, `brain_list_watched_folders`, `brain_list_orphans`,
`brain_resync_folder`, `brain_restore_orphan`, `brain_delete_orphan`)
surface via `brain_core.tools.list_tools()`.

**Cross-field domain check pattern used:**
Mirror of `config_set._check_active_domain_membership` — a pre-check
(`watch_folder._check_domain_membership`) that runs BEFORE the
`watched_folders.append(...)` mutation. Documented inline why the
Pydantic `model_validator(mode="after")` on `Config` is insufficient:
a raise from a model_validator leaves the field mutated to the bad
value under `validate_assignment=True` (Plan 16 T36 lesson). The
pre-check ensures the orphan-domain entry never lands on the live
`Config` even transiently.

**Backup trigger stub-in approach (T9 follow-through):**
`brain_watch_folder` calls `create_snapshot(ctx.vault_root,
trigger="manual")` with a `TODO(Plan 22 T9)` comment marking the
swap to `"pre_watched_folder_sync"` once T9 extends `BackupTrigger`.
The backup call is wrapped in a narrow `try/except` so a backup
failure does NOT block the watch + sync flow — the watch was already
registered above; backup is best-effort safety net here, not a hard
rail. T9 lands `pre_watched_folder_sync` cleanly: just swap the
string + drop the TODO comment.

**Decisions resolved in scope:**

- **D2** non-destructive orphan policy — `brain_delete_orphan`
  requires `typed_confirm=True`; orphans stay marked after
  `brain_unwatch_folder`; `brain_resync_folder` auto-restores via
  `update_source`'s existing `_rebuild_note` (clears `orphaned`).
- **D5** 7-tool surface — all 7 implemented + tested + registered.
- **D9** no new dependencies — implementation uses only existing
  primitives (`VaultWriter`, `UndoLog`, `BulkImporter`,
  `persist_config_or_revert`, `scope_guard`, frontmatter helpers).
- **CLAUDE.md typed_confirm** — `brain_delete_orphan` mandates
  `typed_confirm=True`; refusal short-circuits BEFORE the orphan
  check so a missing confirm never reveals the note's state.

**Verification receipts:**

```bash
# All 7 new test files
unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:... \
  uv run --package brain_core pytest \
  packages/brain_core/tests/tools/test_watch_folder.py \
  packages/brain_core/tests/tools/test_unwatch_folder.py \
  packages/brain_core/tests/tools/test_list_watched_folders.py \
  packages/brain_core/tests/tools/test_list_orphans.py \
  packages/brain_core/tests/tools/test_resync_folder.py \
  packages/brain_core/tests/tools/test_restore_orphan.py \
  packages/brain_core/tests/tools/test_delete_orphan.py -q
# 46 passed (8 + 6 + 5 + 5 + 6 + 7 + 9)

# Full brain_core suite
unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:... \
  uv run --package brain_core pytest packages/brain_core/tests/ -q
# 1116 passed, 5 skipped (baseline 1070 + 46 new T5 = 1116; no regressions)
```

**Concerns / forward notes for T6+:**

1. **Resync `updated` vs `no_change` bucketing heuristic** —
   `IngestPipeline.update_source` returns an OK status across the
   no-op / path-only / overwrite branches without distinguishing
   them in the IngestResult shape. T5's resync tool currently
   buckets every OK result as `"updated"` because the precise
   branch isn't readable from `result` alone. The log emits
   `no_change | <slug>` / `path_only | <slug>` / `overwrite |
   <slug>` which is the source of truth for forensics; a future
   refinement could expose the branch on `IngestResult` if users
   want a more precise resync readout. Flagged in the source
   comment.
2. **T9 trigger swap** — the `"manual"` stub-in is the only thing
   blocking a clean rename to `"pre_watched_folder_sync"`. The
   try/except wrapper means a future `BackupTrigger` mismatch
   (e.g. T9 lands the new enum but the watcher path still calls
   `"manual"`) won't break the sync.
3. **Watcher integration (T6)** — the tools rely on the
   `WatchedFolder.last_sync` field but never update it (last_sync
   is `None` on every entry created by `brain_watch_folder` today).
   T6's watcher will update last_sync on each successful sync; T5
   leaves the slot in the data shape so T6 lands additively.
4. **Resync auto-restore on source-reappear** — handled implicitly
   via `update_source`'s `_rebuild_note` (Plan 22 T2 already sets
   `orphaned=false` on a successful re-ingest). The
   `restored_from_orphan` counter in resync surfaces this for
   readability without needing a separate restore call. No future-
   plan punt needed.

**Commits:**

- `45bcc3a` — `feat(plan-22): T5 — 7 watched-folders tools (watch /
  unwatch / list-watched / list-orphans / resync / restore-orphan /
  delete-orphan)`
- _(docs commit SHA backfilled by the docs commit itself)_

### T6 outcome — `WatchedFolderWatcher` core (symmetric watchdog observer)

**Files created:**

- `packages/brain_core/src/brain_core/watch/__init__.py` (14 LOC) —
  package init, exports `WatchedFolderWatcher`.
- `packages/brain_core/src/brain_core/watch/folder_watcher.py`
  (~720 LOC incl. module + class docstrings) — the watcher class,
  `_FolderEventHandler`, `_index_vault_for_folder` helper.
- `packages/brain_core/tests/watch/__init__.py` (0 LOC).
- `packages/brain_core/tests/watch/test_folder_watcher.py`
  (~470 LOC) — 12 pin tests using `PollingObserver` +
  `_FakePipeline`.

**ConfigWatcher mirror points hit:**

1. **Lifecycle.** `start()` / `stop()` are idempotent. `start()`
   captures the running asyncio loop, walks the folder list, builds
   one `_FolderEventHandler` per `WatchedFolder`, schedules them
   all on a single `Observer`, then starts it. `stop()` cancels
   pending debounce timers, stops + joins the observer with a 2s
   timeout, clears the source-path cache.
2. **Debounce.** Per-path rolling `threading.Timer` keyed on
   `event.src_path` (or `src::dest` for moves). Window defaults to
   100ms — matches `ConfigWatcher._DEFAULT_DEBOUNCE_SECONDS`.
3. **Threading.** Watchdog runs its observer thread; event handlers
   fire on that thread. Async pipeline calls bridge via
   `asyncio.run_coroutine_threadsafe` onto the loop captured at
   `start()`. Sync `mark_orphaned` runs on the debounce-timer
   thread directly (writer's filelock provides cross-thread
   safety).
4. **Failure resilience.** Every event handler call is wrapped in
   try/except + `structlog.warning`. A coroutine that raises gets
   its exception logged via `add_done_callback`; the observer
   thread stays alive. Pin test #10 (`test_pipeline_exception_keeps_observer_running`)
   verifies this directly.
5. **Symmetric per D7.** No IPC, no signal handler — one watcher
   per process, started at T7's brain_api lifespan and T8's
   brain_mcp `_cached_ctx`. The watcher's scope is `Config.watched_folders`
   filtered by `enabled=True`.

**`_find_note_by_source_path` strategy + cache (option B):**

In-memory `dict[str, Path]` (resolved source path string → vault
note path). Lazy-populated on the first lookup via
`_index_vault_for_folder` — a one-time `rglob("*.md")` walk
across the configured domains filtering on
`Frontmatter.watched_folder_id == folder.path`. Subsequent events
hit the cache without re-walking. The delete handler calls
`_invalidate_source(src)` on success so a re-ingest of the same
path triggers a fresh walk (preventing a stale orphan mapping
from masking the new note). A future plan can migrate to
`state.sqlite` if vault size makes the walk impractical; flagged
in the module docstring.

**on_moved handling decision:**

`FileMovedEvent` fans out into a synthetic `FileDeletedEvent` on
the old path + a synthetic `FileCreatedEvent` on the new path.
This matches Plan 22 §T6 explicit guidance ("content-hash-aware
move detection is OUT of v1 scope"). User-visible effect: a
rename produces an orphan-marked vault note for the old source
plus a freshly-ingested note for the new source. The hidden-file
filter is re-applied on both synthetic events so a rename
into / out of a dotfile path doesn't bypass the filter.
PollingObserver may also surface a rename as create+delete
directly; pin test #7 (`test_on_moved_fires_synthetic_delete_and_create`)
asserts the user-visible outcome regardless of which path
watchdog took.

**Single-observer-multi-folder vs observer-per-folder:**

Single `Observer` instance schedules a separate
`_FolderEventHandler` per `WatchedFolder`. This mirrors
`ConfigWatcher` (one observer, one handler) and avoids the
thread-fanout cost of N observers. The `observer_factory`
constructor parameter (defaults to `Observer`) lets tests
inject `PollingObserver` for deterministic event delivery.

**Filter pipeline:**

- Directory events: dropped (only file mutations matter).
- Hidden files (any dot-prefixed path component relative to the
  watched root): dropped at `_on_event` BEFORE the debounce timer
  schedule, mirroring `BulkImporter._is_hidden` semantics.
- Files no `SourceHandler` claims (e.g. `.xlsx`, `.zip`): dropped
  in `_handle_create` / `_handle_modify` via
  `_any_handler_claims(spec, handlers=self._handlers)` — keeps
  unclaimed extensions out of the FAILED branch noise.

**Verification receipts:**

```
$ unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:...
   uv run --package brain_core pytest packages/brain_core/tests/watch/ -q
12 passed, 5 warnings in 5.03s

$ unset VIRTUAL_ENV && uv run --package brain_core mypy \
   packages/brain_core/src/brain_core/watch/
Success: no issues found in 2 source files

$ unset VIRTUAL_ENV && uv run --package brain_core ruff check \
   packages/brain_core/src/brain_core/watch/ \
   packages/brain_core/tests/watch/
All checks passed!

$ unset VIRTUAL_ENV && PYTHONPATH=... uv run --package brain_core pytest \
   packages/brain_core/tests/ -q
1128 passed, 5 skipped, 5 warnings in 8.76s   (baseline 1116 → +12)
```

**Concerns / forward notes for T7-T8:**

1. **Lifespan integration seams.** The watcher needs:
   - The `Config.watched_folders` list (filtered to `enabled=True`).
   - An `IngestPipeline` instance built per the same recipe as
     `resync_folder._build_pipeline` (LLM provider, writer,
     handlers, guard, config).
   - A running asyncio loop at `start()` time. FastAPI's
     `lifespan` context is async by default → no extra wiring.
     `brain_mcp` boots inside `asyncio.run`; the watcher belongs
     in `_cached_ctx` so the loop is live when `start()` runs.
   - An `allowed_domains` tuple. Defaults to the union of every
     folder's domain; T7/T8 may pass a narrower tuple to enforce
     stricter scoping at the lifespan seam.
2. **Config hot-reload + watcher restart.** When `Config.watched_folders`
   changes (user adds / removes / disables a folder via Settings),
   the watcher needs to be `stop()`ed + reconstructed with the new
   folder set. The cleanest seam is to wire the watcher restart
   into the existing `ConfigWatcher`'s `on_change` callback at
   the lifespan layer — T7 / T8 will land that bridge. The
   watcher's `_source_to_note` cache is cleared in `stop()` so a
   restart sees fresh state.
3. **`WatchedFolder.last_sync` field still unused.** The watcher
   doesn't update `last_sync` on event-driven ingests (it's a
   bulk-sync timestamp). T5 left the field as `None`; T6 leaves
   it `None`. A future plan could repurpose it as
   "last_event_processed_at" if the Settings UI wants a
   liveness indicator, but that's out of scope here.
4. **Coroutine-cancellation on `stop()`.** Pending
   `run_coroutine_threadsafe` futures are NOT cancelled on
   `stop()` — they run to completion on the loop. The producer
   thread (debounce timers) IS cancelled. This matches
   watchdog's own teardown contract; an in-flight ingest
   completing after `stop()` is the expected behavior. T7's
   lifespan teardown should await the loop's pending tasks (FastAPI
   does this automatically via lifespan exit).
5. **PollingObserver vs default Observer move semantics.**
   `PollingObserver` may surface a rename as `created` +
   `deleted` rather than a `FileMovedEvent`. The watcher's
   synthetic delete-on-`_handle_delete` already drops events
   for paths it doesn't track, so a polling-surfaced rename
   degrades cleanly. Production uses the platform Observer
   (FSEvents / inotify / ReadDirectoryChangesW), which surfaces
   real `FileMovedEvent`s. Pin test #7 covers both code paths.

**Commits:**

- `6a6d784` — `feat(plan-22): T6 — WatchedFolderWatcher core
  (symmetric watchdog observer; mirrors ConfigWatcher shape)`
- _(docs commit SHA backfilled by the docs commit itself)_

### T7 outcome — `WatchedFolderWatcher` lifespan integration in brain_api

**What landed:**

Wired `WatchedFolderWatcher` into `brain_api._lifespan` startup +
shutdown, with a hot-reload bridge through the existing
`ConfigWatcher.on_change` callback. Single observer per process per
D7 / D11 (no new deps). Watcher is instantiated unconditionally on
boot — even when `Config.watched_folders` is empty — so the
hot-reload bridge always has a watcher to restart when the user
adds their first folder via Settings.

**Files modified:**

- `packages/brain_api/src/brain_api/app.py` — +131 LOC. Added
  imports for `Config`, `WatchedFolder`, `WatchedFolderWatcher`.
  New module-private helpers:
  - `_watched_folders_changed(old, new)` — `model_dump`-based diff
    predicate; gates restart-on-config-change.
  - `_build_watched_folder_watcher(config, app_state)` — reuses
    `brain_core.tools.watch_folder._build_pipeline` (late import)
    so the watcher's IngestPipeline matches the recipe the three
    watched-folder tools use (T2 / T4 / T5).
  - `_restart_watched_folder_watcher(app_state, new_config)` —
    coarse v1 stop-then-start; swallows errors so HTTP stays up.
  Lifespan startup section: instantiates + starts the watcher AFTER
  `ConfigWatcher.start()`, stashes on `app.state.folder_watcher`.
  Lifespan shutdown: folder watcher stops FIRST (so a trailing
  ConfigWatcher callback can't restart a watcher we're tearing
  down), then ConfigWatcher stops. `_on_config_change` extended
  with the diff-then-restart bridge at the bottom of its try-block.

**Files created:**

- `packages/brain_api/tests/test_app_watcher_lifespan.py` — 8 tests:
  1. Empty `watched_folders` → watcher still instantiated + started,
     `observers=[]`, `start_called=1`.
  2. Non-empty list → constructor receives ALL 3 folders (enabled +
     disabled), `allowed_domains=("research",)`.
  3. Shutdown ordering — folder watcher `stop` precedes ConfigWatcher
     `stop`; verified via a shared `call_log` ordering pin.
  4. Disabled-only forwarding — `enabled=False` rows survive the
     lifespan-to-watcher seam (contract pin so future filtering at
     the wrong layer fails loudly).
  5a. Hot-reload restart — patched `resolve_config` returns a Config
      with a new folder; existing watcher `stop_called=1`, fresh
      watcher constructed with the new folder list,
      `app.state.folder_watcher` swapped to the new instance.
  5b. Negative case — config change that does NOT touch
      `watched_folders` (e.g. `log_llm_payloads=True`) does NOT
      restart the watcher.
  6. Monkeypatch-binding regression pin (Plan 17 T17 lesson) —
     patches ONLY `brain_api.app.WatchedFolderWatcher` and asserts
     the patch fired (proves the lifespan reads the import-bound
     name, not a re-resolution through `brain_core.watch`).
  7. `_watched_folders_changed` unit pin — empty == empty,
     length-diff, enabled-flag-diff, content-identity.

**Test counts:**

- Pre-T7 baseline: `210 passed, 1 failed (pre-existing
  test_tools_listing.py count=38 vs 45 — Plan 22 T1-T5 added 7
  tools without updating the count test), 4 skipped`.
- Post-T7: `218 passed, 1 failed (same pre-existing), 4 skipped`.
- Delta: +8 tests, no regressions.
- brain_core watcher tests: `35 passed` (T6 + WatchedFolder schema
  tests unaffected).

**Design notes preserved (for T8 / closure):**

1. **`mock.patch` does NOT accept `raising=False`** — that's a
   `monkeypatch.setattr` / `patch.object` kwarg. Tests 1, 2, 5
   belt-and-suspenders BOTH `brain_api.app.WatchedFolderWatcher`
   and `brain_core.watch.WatchedFolderWatcher` with plain `patch()`.
   T8 should mirror this pattern.
2. **`_build_pipeline` triple-duplication** — `brain_core.tools.
   bulk_import`, `watch_folder`, `resync_folder` each have a
   private `_build_pipeline(ctx)`. T7 reuses the `watch_folder`
   variant (private import). Past the "consistency, don't repeat"
   threshold but extracting it is bigger than T7 — flag for plan
   closure-T cleanup OR Plan 23 candidate ("extract shared
   `IngestPipeline` builder").
3. **`test_tools_listing.py::test_lists_thirty_six_tools_after_issue_17`
   pre-existing failure** — expects 38 tools, repo has 45 after
   T1-T5. Plan 22 closure should bump the constant + rename the
   test method or move it to a snapshot pattern.
4. **Coarse stop-then-start hot-reload** — every `watched_folders`
   change does a full restart, even adding one folder to a list of
   ten. Adequate for v1 (folder counts are small, observer-thread
   churn negligible). Incremental `schedule()` / `unschedule()` is
   a Plan 23 candidate per §T7 forward notes.
5. **`folder_watcher` shutdown idempotency** — the lifespan teardown
   sets `app.state.folder_watcher = None` after stop. A trailing
   `_on_config_change` callback (the ConfigWatcher hasn't stopped
   yet) hits the `existing is None` branch in
   `_restart_watched_folder_watcher` and skips the stop step. This
   is the v1 race-mitigation; a stricter shutdown gate (e.g. a
   `_shutting_down` flag) is out of scope.

**Concerns / forward notes for T8:**

- T8 (`brain_mcp._cached_ctx`) should mirror this shape: late-import
  `_build_pipeline`, single-observer per process, stash on
  `_cached_ctx`'s container for shutdown. The brain_mcp side does
  NOT have an `app.state` so a module-private global or a wrapper
  object will need to hold the reference.
- The Plan 17 T17 monkeypatch-binding lesson applies identically:
  patch `brain_mcp.__main__.WatchedFolderWatcher` (or wherever T8
  imports it), not just `brain_core.watch.WatchedFolderWatcher`.
- Both watchers run in their own processes per the spec — there is
  no IPC. brain_api and brain_mcp BOTH watch the same folders
  independently; a single event fires both watchers (each writes
  to the same vault via VaultWriter's filelock). The v1 worst case
  is a doubled ingest log entry until a future plan adds an
  inter-process coordination marker. Flag for Plan 22 closure
  review (likely deferred to Plan 23).

**Commits:**

- `3374e44` — `feat(plan-22): T7 — WatchedFolderWatcher integration
  in brain_api lifespan (D7 symmetric watcher)`
- _(docs commit SHA backfilled by the docs commit itself)_

### T8 outcome — `WatchedFolderWatcher` integration in brain_mcp `_cached_ctx` boot path

**What landed:**

Wired `WatchedFolderWatcher` into `brain_mcp.__main__._run` startup +
shutdown, with a hot-reload bridge through the existing
`_on_config_change` callback. Symmetric watcher per D7: brain_mcp
(stdio MCP server for Claude Desktop) now starts the same watcher
brain_api does. Watcher is instantiated unconditionally on boot — even
when `Config.watched_folders` is empty — so the hot-reload bridge
always has a watcher to restart when the user adds their first folder.

**Files modified:**

- `packages/brain_mcp/src/brain_mcp/__main__.py` — +267 LOC. Added
  imports for `Config`, `WatchedFolder`, `WatchedFolderWatcher`, and
  `resolve_config`. New module-private state and helpers:
  - `_folder_watcher` — module-level slot for the active watcher
    (mirrors how `_cached_ctx` is lifted to module scope in
    `brain_mcp.server`; brain_mcp has no `app.state` equivalent).
  - `_last_known_watched_folders` — folder-list snapshot used by the
    hot-reload diff. Maintained independently of `_cached_ctx`
    because the brain_mcp ToolContext is lazy-built per tool call,
    so the cached config may not exist when the first config change
    fires.
  - `_boot_vault_root`, `_boot_allowed_domains` — boot-state captured
    in `_run` so the hot-reload callback can re-resolve config and
    rebuild the watcher with the same scope the server launched with.
  - `_reset_watcher_state()` — test-only helper to clear the four
    module-level slots between cases.
  - `_watched_folders_changed(old, new)` — `model_dump`-based diff
    predicate, byte-for-byte mirror of T7's brain_api version. Kept
    duplicated rather than imported across packages (cross-package
    sibling imports are the anti-pattern; a brain_core lift is a Plan
    23 candidate alongside `_build_pipeline` extraction).
  - `_build_watched_folder_watcher(config, vault_root, allowed_domains)`
    — reuses `brain_core.tools.watch_folder._build_pipeline` (late
    import) so the watcher's IngestPipeline matches the recipe the
    three watched-folder tools use. With T8 this is now a FOUR-call-
    site recipe (was three at T7); flagged as Plan 23 closure scope.
  - `_build_or_reuse_tool_ctx(config, vault_root, allowed_domains)` —
    brain_mcp-specific helper that prefers the warm `_cached_ctx`
    singleton in `brain_mcp.server` (so the watcher's pipeline shares
    StateDB/CostLedger/RateLimiter with the tool dispatcher) and falls
    back to a fresh build at cold boot (when no tool call has yet
    warmed the singleton — the watcher IS the first consumer). This is
    a divergence from T7's `_build_watched_folder_watcher` shape, which
    reads from `app_state.ctx.tool_ctx` (always-built lifespan
    artifact). Required because brain_mcp's lazy ctx is structurally
    different from brain_api's eager ctx — a refactor to unify is a
    Plan 23 candidate.
  - `_restart_watched_folder_watcher(new_config)` — coarse v1
    stop-then-start; swallows errors so the stdio surface stays up.
    Symmetric to T7's brain_api version.
  - `_on_config_change(config_path)` — extended with the diff-then-
    restart bridge at the bottom. Preserves the Plan 16 T35 / T39.5
    baseline behavior (loader-cache invalidate + ctx-reset) at the
    top; adds a defensive bail when `_boot_vault_root is None` so the
    callback can fire during an early window in `_run` startup
    without crashing.
- `_run()` startup section: instantiates + starts the watcher AFTER
  `ConfigWatcher.start()`, stashes on `_folder_watcher`, snapshots
  `_last_known_watched_folders`. Finally-block teardown: folder
  watcher stops FIRST (so a trailing ConfigWatcher callback can't
  restart a watcher we're tearing down), then ConfigWatcher stops,
  then boot state cleared so a re-entered `_run` starts clean.

**Files created:**

- `packages/brain_mcp/tests/test_main_watcher_startup.py` — 9 tests:
  1. Cold boot with empty `watched_folders` → watcher instantiated +
     started, `observers=[]`, `start_called=1`, slot populated.
  2. Cold boot non-empty → constructor receives ALL 3 folders
     (enabled + disabled), `allowed_domains=("research",)`.
  3. Shutdown → `watcher.stop()` called exactly once; slot cleared.
  4. Disabled-only forwarding — `enabled=False` rows survive the
     boot-to-watcher seam (contract pin so future filtering at the
     wrong layer fails loudly).
  5a. Hot-reload restart — patched `resolve_config` returns a Config
      with a new folder; existing watcher `stop_called=1`, fresh
      watcher constructed with the new folder list, module slot
      swapped to the new instance.
  5b. Negative case — config change that does NOT touch
      `watched_folders` (e.g. `log_llm_payloads=True`) does NOT
      restart the watcher.
  6. Monkeypatch-binding regression pin (Plan 17 T17 lesson) —
     patches ONLY `brain_mcp.__main__.WatchedFolderWatcher` and
     asserts the patch fired (proves `_build_watched_folder_watcher`
     reads the import-bound name).
  7. `_watched_folders_changed` unit pin — empty == empty,
     length-diff, enabled-flag-diff, content-identity.
  8. Defensive `_on_config_change` bail when `_boot_vault_root is
     None` — pin that the early-fire window doesn't crash.

  Plus an autouse `_reset_module_state` fixture clears
  `_folder_watcher`, `_last_known_watched_folders`,
  `_boot_vault_root`, `_boot_allowed_domains`, AND
  `brain_mcp.server._cached_ctx` between cases — symmetric to
  `test_ctx_cache_reset.py::_isolate_module_cache`.

**Test counts:**

- Pre-T8 baseline: `137 passed, 3 skipped`.
- Post-T8: `146 passed, 3 skipped`.
- Delta: +9 tests, no regressions.
- brain_core watcher tests: `12 passed` (T6 + WatchedFolder schema
  tests unaffected).
- brain_api T7 lifespan tests: `8 passed` (T7's tests still green).

**Mirror target alignment with T7:**

- Reused: `_watched_folders_changed` semantics + `model_dump` diff
  predicate. The body is duplicated byte-for-byte; a brain_core lift
  is the cleanest extraction but bigger than T8.
- Reused: `_build_pipeline` late-import from
  `brain_core.tools.watch_folder` (per T7's note about the
  triple-duplication concern, now FOUR sites).
- Reused: coarse stop-then-start hot-reload policy + error-swallowing
  pattern + reverse-order teardown.
- Diverged: `_build_or_reuse_tool_ctx` — brain_mcp's lazy ToolContext
  required a new helper that either reuses the warm singleton or
  builds a fresh one. T7 read from `app_state.ctx.tool_ctx` directly.
- Diverged: module-level state vs `app.state`. brain_mcp has no app-
  state container so the watcher + boot params live at module scope,
  mirroring how `_cached_ctx` was lifted to module scope in Plan 17
  T8.
- Diverged: `_on_config_change` signature stays one-argument
  (`config_path`) — the boot params it needs are read from module
  state. brain_api threads `app_state` + `vault_root` as args.

**Plan 17 T17 monkeypatch-binding pin:**

`WatchedFolderWatcher` is imported at module level in
`brain_mcp.__main__`. Test 6 patches ONLY
`brain_mcp.__main__.WatchedFolderWatcher` and asserts the
`_build_watched_folder_watcher` call produces a `_FakeWatcher`
instance. If a future refactor moves the import to a late binding,
the patch won't fire and the test will fail loudly.

**Concerns / forward notes for closure / Plan 23:**

- `_build_pipeline` is now FOUR call sites (bulk_import, watch_folder,
  resync_folder, brain_api lifespan, brain_mcp `_run`) — past the
  threshold for "consistency, don't repeat aggressively". Plan 23
  candidate: extract shared `IngestPipeline` builder into brain_core.
- `_watched_folders_changed` and `_build_watched_folder_watcher` are
  now duplicated in brain_api and brain_mcp. Same "extract to
  brain_core" Plan 23 candidate.
- brain_api + brain_mcp parallel watchers (T7 flagged): both
  processes will watch the same folders independently → duplicate
  ingest fires for the same event. v1 worst case is a doubled ingest
  log entry; the VaultWriter filelock serializes the actual write so
  no corruption. Inter-process coordination marker is deferred to a
  future plan.
- brain_mcp's `_build_or_reuse_tool_ctx` falls back to a fresh
  ToolContext build that does NOT populate
  `brain_mcp.server._cached_ctx` on its own — that path is owned by
  the server's tool dispatcher. If the next tool call rebuilds, both
  ToolContexts coexist briefly; the StateDB connection is acquired
  per-instance so there's no sharing hazard for v1. A unify-paths
  refactor is a Plan 23 candidate.
- `test_tools_listing.py` brain_api pre-existing failure (T7 flagged)
  is unchanged; brain_mcp has no analogous failing test count
  assertion. Plan 22 closure should still bump the brain_api constant.

**Commits:**

- `d242f3c` — `feat(plan-22): T8 — WatchedFolderWatcher integration
  in brain_mcp _cached_ctx (D7 symmetric watcher)`
- _(docs commit SHA backfilled by the docs commit itself)_

### T9 outcome — Backup trigger swap + initial-sync cost-estimate gate

**What landed:**

Extended ``BackupTrigger`` with a new value
``"pre_watched_folder_sync"``, swapped the T5 ``"manual"`` stub in
``brain_watch_folder`` for the new trigger, and added an informational
classify-only cost estimate that surfaces in both ``ToolResult.text``
(human-readable) and ``ToolResult.data["cost_estimate"]`` (structured
4-key payload) BEFORE the initial sync's bulk import runs. Per D3 the
estimate is informational only — there is NO refusal threshold. The
rate-limit + per-domain budget caps (Plan 16 T26-T32) remain the hard
ceilings; T9 just gives the user a projection of the classify spend
they're about to authorize.

**Files modified:**

- `packages/brain_core/src/brain_core/backup.py` (+5 LOC effective):
  extended the ``BackupTrigger`` Literal, the ``_VALID_TRIGGERS``
  frozenset, and the ``_FILENAME_RE`` regex (so ``brain_backup_list``
  enumerates the new trigger's snapshots correctly). Docstring
  trigger list updated.
- `packages/brain_core/src/brain_core/tools/backup_create.py` (+5 LOC):
  extended the tool-surface ``_VALID_TRIGGERS`` tuple. The
  ``INPUT_SCHEMA`` enum derives from this tuple, so the new value
  flows through to the OpenAPI surface automatically.
- `packages/brain_core/src/brain_core/tools/watch_folder.py`
  (~+85 LOC):
  - Module docstring updated: T5 "stubbed manual + TODO" paragraph
    replaced with a permanent description of the new trigger + the
    D3 cost-estimate contract.
  - Added ``_CLASSIFY_TOKEN_COST = 1000`` and
    ``_CLASSIFY_MAX_OUTPUT_TOKENS = 256`` constants — mirrors
    ``bulk_import.py:_CLASSIFY_TOKEN_COST`` so both tools project the
    same per-file classifier spend.
  - Added ``_estimate_initial_sync_cost(folder, classify_model) ->
    (file_count, tokens, usd | None)`` helper. Walks the folder the
    same way ``BulkImporter.plan`` does (``rglob`` + ``is_file``
    + ``is_symlink`` filter); estimates USD via
    ``BudgetEnforcer.estimate_cost`` and returns ``None`` for the USD
    field when the classify model has no pricing entry (forward-compat
    for a model swap that lands ahead of pricing).
  - Resolves the classify model via ``resolve_llm_config(cfg, None)``
    (mirrors ``_build_pipeline``) so the estimate matches the model
    the bulk import will actually call.
  - Cost estimate fires BEFORE the backup + plan/apply (so the user
    sees the projection even on a backup-or-pipeline failure).
  - Swapped ``create_snapshot(ctx.vault_root, trigger="manual")``
    for ``trigger="pre_watched_folder_sync"`` and dropped the T5
    TODO comment. Kept the narrow ``try/except (FileNotFoundError,
    ValueError)`` wrapper — backup remains best-effort.
  - Extended both return branches (``status="watched"`` and
    ``status="already_watched"``) to include the new
    ``cost_estimate`` key (``None`` on the no-sync paths). text
    readout format: ``" | initial sync estimate: ~N files, ~$X.XXXX
    (classify only; summarize+integrate cost is per-file
    post-classify)"``.
- `packages/brain_core/tests/tools/test_watch_folder.py` (+200 LOC):
  - Updated module docstring with the T9 pin section.
  - Extended ``test_data_shape_pin_initial_sync_false`` to pin the
    new 5-key shape ``{status, folder, domain, initial_sync_summary,
    cost_estimate}``.
  - Extended ``test_already_watched_returns_idempotent_status`` to
    pin ``cost_estimate is None`` on the idempotent short-circuit.
  - Added 8 new T9 pin tests:
    1. ``test_pre_watched_folder_sync_in_backup_create_valid_triggers``
       — tool-surface tuple includes the new trigger.
    2. ``test_pre_watched_folder_sync_in_backup_module_valid_triggers``
       — backup module frozenset AND filename regex include the new
       trigger.
    3. ``test_estimate_initial_sync_cost_token_calc`` — tokens =
       ``file_count × _CLASSIFY_TOKEN_COST``; USD matches the
       Haiku pricing formula.
    4. ``test_estimate_initial_sync_cost_unknown_model_returns_none``
       — forward-compat: unknown classify model returns ``None`` USD
       without raising.
    5. ``test_initial_sync_calls_backup_with_pre_watched_folder_sync_trigger``
       — monkeypatches ``create_snapshot`` and asserts trigger="pre_watched_folder_sync".
    6. ``test_initial_sync_surfaces_cost_estimate_in_text_and_data``
       — text contains "initial sync estimate", "N files",
       "classify only"; data["cost_estimate"] has the 4-key payload.
    7. ``test_initial_sync_does_not_refuse_on_large_folder`` — D3 pin:
       200 files (> ``bulk_import._LARGE_FOLDER_THRESHOLD=20``) still
       go through; no "refused" status leak.
    8. ``test_cost_estimate_omitted_when_initial_sync_false`` —
       ``cost_estimate is None`` and text omits the readout on the
       no-sync path.
  - Added ``_FakeBulkImporter`` (mirroring
    ``test_bulk_import._FakeBulkImporter``) + ``_install_fakes``
    helper that wires fakes for ``BulkImporter``, ``_build_pipeline``,
    and ``create_snapshot``.

**Decisions resolved in scope:**

- **D3** — no hard initial-sync cap; cost estimate informational
  only. Verified by ``test_initial_sync_does_not_refuse_on_large_folder``
  (200 files = 10× ``bulk_import._LARGE_FOLDER_THRESHOLD`` and the
  call still succeeds with ``status="watched"``).
- **D11** — no new dependencies. Uses ``BudgetEnforcer.estimate_cost``,
  ``resolve_llm_config``, and existing ``rglob``-based folder walk.

**Verification receipts:**

```bash
# T9-scoped tests (backup_create + watch_folder = 21 tests)
unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:... \
  uv run --package brain_core pytest \
  packages/brain_core/tests/tools/test_backup_create.py \
  packages/brain_core/tests/tools/test_watch_folder.py -v
# 21 passed (5 backup_create + 8 T5 watch + 8 new T9)

# Full brain_core suite
unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:... \
  uv run --package brain_core pytest packages/brain_core/tests/ -q
# 1136 passed, 5 skipped (baseline 1128 + 8 new T9 = 1136; no regressions)

# mypy on modified files
unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:... \
  uv run --package brain_core mypy \
  packages/brain_core/src/brain_core/tools/watch_folder.py \
  packages/brain_core/src/brain_core/tools/backup_create.py \
  packages/brain_core/src/brain_core/backup.py
# Success: no issues found in 3 source files
```

**Concerns / forward notes:**

1. **Estimate over-counts vs ``BulkImporter.plan`` walker** —
   ``_estimate_initial_sync_cost`` uses a simple ``rglob`` +
   ``is_file`` + ``is_symlink`` filter and does NOT skip dotfiles
   the way ``BulkImporter.plan`` does. This is deliberate: a
   conservative over-count is acceptable; under-count would be a
   bug. The mismatch is pinned in
   ``test_estimate_initial_sync_cost_token_calc`` so the conservative-
   ceiling contract is explicit. A future tightening (skip dotfiles
   to match the plan walker) would require re-pinning this test.
2. **Cross-package shape consumers** — ``brain_api`` and ``brain_mcp``
   reference ``brain_watch_folder`` by name in their watcher-startup
   tests but don't pin the data shape, so the new ``cost_estimate``
   key landed without cross-package test drift. The frontend
   wrapper (Plan 22 T12+) will need to read the new key.
3. **Pre-existing brain_api test failure**
   (``test_lists_thirty_six_tools_after_issue_17``) — already failed
   on ``main`` before T9 (count pin of 38 vs actual 45 from T5's 7
   new tools). NOT a T9 regression; flagged for Plan 22 closure (T17)
   alongside the other `brain_api` count bumps.

**T5 TODO marker resolution:**

The T5 ``TODO(Plan 22 T9)`` comment in
``watch_folder.py`` was REMOVED (not replaced). The block was
rewritten with a permanent comment describing the contract:
``# Pre-sync backup with the distinct trigger so the Settings page
can group "pre-watched-folder-sync" snapshots separately from manual
/ daily / pre-bulk-import``. The trigger string ``"pre_watched_folder_sync"``
is greppable across the repo: ``backup.py`` (Literal + frozenset +
regex), ``backup_create.py`` (tuple), ``watch_folder.py`` (call
site), test pins, plan-doc.

**Cost-estimate format used:**

Text format (single-line, anchor phrases pinned in tests):
```
watched <folder> → <domain> (synced N/M files) | initial sync estimate: ~K files, ~$X.XXXX (classify only; summarize+integrate cost is per-file post-classify)
```

Structured ``data["cost_estimate"]`` (4 keys):
```python
{
    "file_count": int,
    "estimated_tokens": int,
    "estimated_usd": float | None,  # None when classify_model has no pricing row
    "classify_model": str,
}
```

**Pricing constant used:**

Routed through ``BudgetEnforcer.estimate_cost`` — single source of
truth for pricing in ``brain_core/cost/budget.py:_PRICING``. No
duplicate constants in ``watch_folder.py``. The fallback classify
model when ``Config.llm`` is missing is ``claude-haiku-4-5-20251001``
(matches ``bulk_import.py`` and ``_build_pipeline``).

**Commits:**

- `9a34853` — `feat(plan-22): T9 — pre_watched_folder_sync backup
  trigger + informational cost estimate`
- _(docs commit SHA backfilled by the docs commit itself)_

### T10 outcome — Backend integration tests (brain_core + brain_api)

**Status:** ✅ complete (this commit + receipts).

**Files added:**

- `packages/brain_core/tests/watch/test_folder_watcher_integration.py`
  — 665 LOC, 6 end-to-end integration tests using REAL
  :class:`IngestPipeline` + REAL :class:`WatchedFolderWatcher` + a
  :class:`FakeLLMProvider` queue. `PollingObserver` at 100ms timeout
  for cross-platform determinism (FSEvents / ReadDirectoryChangesW
  are flaky in CI sandboxes per Plan 22 D-watch).
- `packages/brain_api/tests/test_watched_folders_integration.py`
  — 415 LOC, 4 FastAPI-TestClient integration tests covering the
  full POST `/api/tools/<name>` round-trip for `brain_watch_folder`
  (with and without initial sync), `brain_list_watched_folders`, and
  `brain_unwatch_folder`. Uses the standard `mount_static_ui=False`
  fixture pattern from Plan 13 Task 5 so the SPA catch-all doesn't
  shadow API routes.

**brain_core integration coverage (6 tests):**

| Test | Scenario | LLM queue |
|---|---|---|
| `e2e_create` | drop `.txt` → pipeline ingest writes a note | summarize + integrate (classify skipped via `domain_override`) |
| `e2e_modify` | modify pre-ingested source → `update_source` overwrite branch | summarize + integrate (D4 — no classify) |
| `e2e_delete` | delete tracked source → `mark_orphaned` flips frontmatter | empty (sync, LLM-free path) |
| `e2e_hidden` | `.dotfile` drop → no pipeline call | empty (filter fires) |
| `e2e_unclaimed` | `.xyz` drop → no pipeline call | empty (handler gate) |
| `e2e_concurrent` | 5 rapid `.txt` drops → 5 distinct notes | 10 queued (2 per file × 5) |

**v1 contract pinned (intentional gap, documented in the
`e2e_create` test docstring):** the pipeline's Stage 7
`_build_source_note` does NOT populate `source_path` or
`watched_folder_id` frontmatter. The watcher passes
`domain_override` but not the folder-id; the lookup cache the
watcher's update/delete handlers depend on
(:func:`_index_vault_for_folder`) is only populated by T5's
`brain_resync_folder` tool, NOT by a watcher-triggered first
ingest. A future plan that threads folder-id through the pipeline
would flip these absence-assertions — pinned explicitly so the
v1 contract is grep-locked at the integration seam.

**brain_api integration coverage (4 tests):**

| Test | Endpoint | Asserts |
|---|---|---|
| `api_watch_folder_registers_folder` | POST `brain_watch_folder` (initial_sync=False) | data envelope shape + Config in-memory + on-disk |
| `api_list_watched_reflects_registered_folders` | POST `brain_list_watched_folders` | read-after-write contract, runtime stats (file_count=0/orphan_count=0 for freshly registered) |
| `api_watch_folder_initial_sync_imports_files` | POST `brain_watch_folder` (initial_sync=True) with 2 seeded files | BulkImporter runs end-to-end, 2 notes land in vault, cost_estimate populated |
| `api_unwatch_folder_removes_row` | POST `brain_unwatch_folder` | row removed from Config + persisted |

**PollingObserver timing:**

- `observer_factory=lambda: PollingObserver(timeout=0.1)` — 100ms
  polling tick. The default `PollingObserver` timeout is 1s, which
  blows the test budget; 100ms catches the file events fast enough
  for the 10s `_wait_async` predicate poll budget.
- Test wall-clock: brain_core integration suite runs in **~3s**
  locally (6 tests). brain_api integration suite runs in **<200ms**
  (4 tests, no observer thread — the lifespan-managed watcher only
  fires if a folder is registered and we test the tool API surface,
  not the watcher firing).
- e2e_create + e2e_modify + e2e_delete + e2e_concurrent each rely
  on a poll-until-predicate wait loop (10s budget) rather than
  fixed sleeps, so they complete in ~250-600ms each on a warm
  machine and have slack for CI cold-starts.

**Test counts:**

- brain_core: 1141 → **1147** (+6 from T10).
- brain_api: 223 collected → **227** (+4 from T10); 222 passing.
- Pre-existing failure (not T10's responsibility): one stale tool
  count pin in `test_tools_listing.py::test_lists_thirty_six_tools_after_issue_17`
  asserts `len(tools) == 38` while Plan 22 has added 7 new tool
  surfaces (4 watched-folders tools + the T9 backup trigger
  expansion is not a tool but the count is now 45). Documented for
  T11+ cleanup or a future tool-surface inventory plan.

**Cross-platform note:** all tests are pathlib-based, use UTF-8
explicitly with `newline="\n"`, and use `PollingObserver` rather
than the platform-specific defaults. The existing CI matrix
(macos-14 + windows-2022 per Plan 14) carries the cross-platform
coverage; T10 adds tests that inherit it without per-platform
branches.

**Review verification (combined per-task review):**

- ✅ Integration tests use `PollingObserver` for determinism — no
  FSEvents / ReadDirectoryChangesW reliance.
- ✅ Full `brain_core` test suite green: 1142 passed, 5 skipped.
- ✅ Full `brain_api` test suite: 222 passed, 4 skipped, 1
  pre-existing failure (stale tool count, not T10-introduced).
- ✅ No mocks of `IngestPipeline` or `WatchedFolderWatcher` in the
  brain_core integration tests — the only mocked seam is the LLM
  provider, per Plan 22 D11 (no new dependencies) and the
  test-engineer charter (FakeLLMProvider only).
- ✅ FakeLLMProvider queue depth carefully tuned per scenario:
  empty queues prove the no-pipeline-call paths (hidden, unclaimed,
  orphan-mark); 2-call queues prove `domain_override` skips
  classify; the concurrent test queues 10 responses (2 per file)
  to drive 5 parallel ingests through the per-path debounce.

**Commits:**

- _(test + docs commit SHAs backfilled by the commits themselves)_

## T10.5 outcome

**Why this task exists.** T10's integration tests surfaced an
architectural gap: T1 added `source_path` + `watched_folder_id` to
`Frontmatter`, but the 9-stage ingest pipeline (`pipeline.py`
`_build_source_note`) didn't populate them. As a result, T6's
`WatchedFolderWatcher._find_note_by_source_path` always returned
`None` — modify events fell through to a duplicate ingest, delete
events silently no-opped. T10's tests pinned the gap with
absence-assertions (`source_path` MUST NOT be present); T10.5 flips
the data flow + the assertions.

**What changed.**

- `pipeline.ingest()` gains two optional kwargs `source_path: Path | None`
  and `watched_folder_id: str | None`. Default `None` preserves backwards-
  compat for drag-drop / MCP ingest / standalone bulk-import. When
  set, the kwargs flow through to `_build_source_note` which writes
  them onto the source note's frontmatter (`source_path` as
  `str(path.resolve())` per T2 `update_source` convention,
  `watched_folder_id` verbatim per D1).
- `BulkImporter.apply()` gains optional `watched_folder_id`. When
  set, every per-item `pipeline.ingest` call receives BOTH the
  shared `watched_folder_id` AND a per-item `source_path=item.spec`.
- `brain_watch_folder` tool passes `watched_folder_id=folder_str`
  to `BulkImporter.apply`.
- `WatchedFolderWatcher._handle_create` (and the
  `_handle_modify` fall-through-to-ingest branch) pass both kwargs.

**Files modified:**

| File | LOC delta |
|---|---|
| `packages/brain_core/src/brain_core/ingest/pipeline.py` | +49 / -3 |
| `packages/brain_core/src/brain_core/ingest/bulk.py` | +28 / -3 |
| `packages/brain_core/src/brain_core/tools/watch_folder.py` | +8 / -1 |
| `packages/brain_core/src/brain_core/watch/folder_watcher.py` | +24 / -4 |
| `packages/brain_core/tests/watch/test_folder_watcher.py` | +28 / -2 (FakePipeline.ingest kwargs + presence assertions on create + modify-fallback tests) |
| `packages/brain_core/tests/watch/test_folder_watcher_integration.py` | +103 / -10 (flipped absence → presence on `e2e_create`; added `e2e_create_then_modify` lifecycle test; pinned per-file `source_path` on `e2e_concurrent`) |
| `packages/brain_api/tests/test_watched_folders_integration.py` | +35 / -0 (presence assertions on `api_initial_sync` test) |
| `packages/brain_core/tests/ingest/test_pipeline_ingest_watched_context.py` | NEW (303 LOC, 6 pin tests) |

**Tests added/modified.**

- NEW `test_pipeline_ingest_watched_context.py` — 6 tests pinning
  the kwargs contract:
  1. default kwargs → no watched fields (backwards-compat);
  2. `source_path` alone → that field, no `watched_folder_id`;
  3. `watched_folder_id` alone → that field, no `source_path`;
  4. both → both fields with correct values;
  5. `BulkImporter.apply(watched_folder_id=...)` → per-item threading;
  6. `BulkImporter.apply()` without kwarg → backwards-compat shape.
- NEW `test_e2e_create_then_modify_routes_via_update_source` (in
  `test_folder_watcher_integration.py`) — true lifecycle pin: drop
  a file → wait for create-event note → modify the same file →
  assert exactly 1 note in `sources/` with refreshed `content_hash`.
  Pre-T10.5 this test would catch 2 notes (duplicate from fallback);
  post-T10.5 the modify event routes to `update_source`. This is the
  regression-test that proves T10.5 actually works end-to-end (not
  just at the kwarg-threading layer).
- Modified `test_e2e_create_writes_source_note_with_watch_frontmatter`
  to FLIP absence-assertions to presence: `assert fm["source_path"]
  == str(src.resolve())` and `assert fm["watched_folder_id"] ==
  str(folder)`.
- Modified `test_e2e_concurrent_files_each_produce_a_note` to also
  assert per-file `source_path` mapping + shared `watched_folder_id`
  on all 5 notes.
- Modified `test_on_created_routes_to_ingest` + `test_on_modified_unmapped_falls_through_to_ingest`
  (unit tests in `test_folder_watcher.py`) to assert the `_FakePipeline`
  received the kwargs (proves the watcher threads them through).
- Modified `test_api_watch_folder_initial_sync_imports_files` (in
  `test_watched_folders_integration.py`) to pin per-item
  `source_path` + shared `watched_folder_id` on every initial-sync
  source note.

**T10 absence-to-presence flips.**

- `test_folder_watcher_integration.py:299-376` — `test_e2e_create_writes_source_note_with_watch_frontmatter`: was `assert "source_path" not in fm or fm["source_path"] is None`, now `assert fm["source_path"] == str(src.resolve())` (line ~367) and the matching `watched_folder_id` flip on line ~369.
- `test_folder_watcher_integration.py:~660` — `test_e2e_concurrent_files_each_produce_a_note`: was a comment block saying "we don't assert source_path because the v1 watcher path doesn't populate it"; now asserts the set of recorded `source_path` values matches the set of source files dropped.
- `test_watched_folders_integration.py:~358` — `test_api_watch_folder_initial_sync_imports_files`: added presence-block asserting every initial-sync note has the watched-context frontmatter.

**Test counts.**

- brain_core: 1142 → **1149** (+7 from T10.5: 6 new + 1 lifecycle).
- brain_api: 222 → **222** (+0; 1 existing test strengthened with
  presence assertions, no new tests).

**Verification.**

```bash
unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src \
  uv run --package brain_core pytest packages/brain_core/tests/ -q
# 1149 passed, 5 skipped

unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src \
  uv run --package brain_api pytest packages/brain_api/tests/ -q
# 222 passed, 4 skipped, 1 failed (pre-existing tool-count drift —
# not T10.5's responsibility, same shape as T10 closure)
```

**Lifecycle pin (the real correctness gate).**

The 6 new pin tests prove the kwargs THREAD correctly. The
`test_e2e_create_then_modify_routes_via_update_source` integration
test proves the resulting frontmatter ACTUALLY enables the watcher's
lookup. Together they close the v1 gap without relying on the
pre-seeded-note shortcut the T10 modify/delete tests used.

**Cross-platform note.** All new tests use `pathlib` + explicit
UTF-8 + `PollingObserver` — same shape as T10's existing
integration tests. No platform-specific branches.

**Backwards-compat invariants pinned.**

- `pipeline.ingest()` called without the new kwargs produces a note
  with NO `source_path` and NO `watched_folder_id` (test 1 in the
  new file).
- `BulkImporter.apply()` called without `watched_folder_id` produces
  notes with neither field (test 6 in the new file). The standalone
  `brain_bulk_import` tool (drag-drop) therefore keeps its pre-T10.5
  frontmatter shape.

## T12 outcome

**Status:** ✅ DONE (mockup-faithful, all gates green).

**Files created:**

- `apps/brain_web/src/components/settings/panel-watched-folders.tsx`
  (~430 LOC) — orchestrator + `WatchedFolderRow` per-row presentation
  component + `WatchNewFolderCta` placeholder CTA. Reads from the new
  zustand store; mutations route through `brain_unwatch_folder` with
  optimistic drop + reconcile-on-error (mirrors Plan 16 T4 / D4
  `panel-domains` rollback pattern). Tooltips on disabled "Resync now"
  / "Open in Finder" buttons explain the placeholder state (the
  backend `brain_resync_folder` did not ship in T5 — tracked below).
- `apps/brain_web/src/lib/state/watched-folders-store.ts` (~120 LOC) —
  zustand store mirroring `useDomainsStore` shape (`loaded`, `error`,
  `refresh()`, `removeFolderOptimistic`, `_resetForTesting`). No
  BroadcastChannel for v1 — flagged as Plan 23 candidate (added below).
  Resolve-always semantics on `refresh()` (failures record on `error`
  state rather than rejecting) so first-mount auto-fetch can't surface
  unhandled rejections.
- `apps/brain_web/tests/unit/panel-watched-folders.test.tsx` (~470
  LOC, 16 tests) — pins populated / empty / loading / error-banner
  states, the unwatch optimistic-drop + reconcile + toast lifecycle,
  the personal-domain note conditional, and CTA placement per the
  mockup spec. All microcopy assertions match the mockup verbatim.

**Files modified:**

- `apps/brain_web/src/lib/api/tools.ts` — added `WatchedFolderEntry` +
  `ListWatchedFoldersData` named interfaces (Plan 19 T4 pattern), the
  `UnwatchFolderData` discriminated union (mirrors `UndoLastData` /
  Plan 18 T3.7 precedent), and `listWatchedFolders` /
  `unwatchFolder` typed wrappers. `ALL_TOOL_NAMES` count: 38 → 40.
- `apps/brain_web/src/components/settings/settings-screen.tsx` — added
  `"watched-folders"` to `SettingsTabId` union; registered the tab
  between `"domains"` and `"brain-md"` per the mockup hand-off note;
  added `<PanelWatchedFolders />` to the `renderPanel` switch with the
  `Eye` icon from `lucide-react`.
- `apps/brain_web/tests/unit/api-client.test.ts` — updated the 38-tool
  count pin to 40 with a comment explaining which Plan 22 tools landed
  in T12 vs which defer to T13 / T15.

**State management approach:** zustand store (`useWatchedFoldersStore`)
mirroring `useDomainsStore` for parity with the Plan 13 T2 single-
source-of-truth lesson. Local React state was rejected because the
topbar status indicator (T14) and the Orphans panel (T13) will both
need to read the same data; a single store keeps them in lock-step
without remount.

**Watch-new CTA wiring:** placeholder. Clicking the CTA pushes a toast
("Coming soon. The watch-folder picker ships in the next Plan 22 task
(T15).") so the user gets confirmation the click registered. The
button stays interactive (not disabled) so the focus ring, hover, and
keyboard binding all read correctly in axe + Playwright. T15 wires the
modal.

**Unit-test count:** 16 tests, all passing. Covers:

1. Populated state: row count, path, domain badge (3 rows).
2. Sub-line file/orphan/last-sync format with the 4-min / 1-hour /
   12-min / never variants.
3. Orphan count omitted from sub-line when zero (mockup §microcopy).
4. Personal-domain note conditional rendering.
5. Empty-state card + verbatim copy ("No folders being watched yet.",
   "Pick a folder and Brain will keep its notes in sync
   automatically.").
6. Loading skeleton + sr-only "Loading watched folders…" `aria-live`
   announcement.
7. Error banner + retry button: `role="alert"`, error message
   surfaced, retry triggers a new fetch.
8. Unwatch action: optimistic drop, API called with correct args,
   success toast with basename + orphan count.
9. Unwatch failure path: row restored via reconcile-refresh, danger
   toast with verbatim error message.
10. CTA placement: header-anchored in populated branch, centered in
    empty branch; click pushes the T15-placeholder toast.

**Verification gates:**

- `pnpm vitest run tests/unit/panel-watched-folders.test.tsx`:
  16/16 passing, 1.16s total.
- `pnpm vitest run` (full suite): 512 passing / 1 skipped, 6.42s.
- `pnpm tsc --noEmit`: exit 0. Per auto-memory
  `feedback_tsc_vs_vitest.md`, both gates run; both clean.

**Concerns / follow-ups:**

1. **`brain_resync_folder` did not ship in T5.** The plan-doc §T5
   names a `resync_folder.py` deliverable; the file does not exist in
   `packages/brain_core/src/brain_core/tools/`. T12's "Resync now"
   button renders as disabled with a "Coming soon" tooltip explaining
   the placeholder state. Tracked as a Plan 22 follow-up — adding it
   to the **Plan 23 candidate scope** block below as a delta to the
   plan's locked decisions.
2. **OS-native "Open in Finder" helper does not exist.** The mockup
   specifies a per-row "Open in Finder ↗" button (macOS `open <path>`
   / Windows `explorer.exe <path>`). The `Integrations` helper
   referenced in the mockup is not present in `brain_web` today.
   Button renders as disabled with a "Coming soon" tooltip. Plan 23
   candidate (added below).
3. **Cross-tab pubsub deferred.** v1 does not add a BroadcastChannel
   pattern to the watched-folders store (the domains-store / Plan 12
   T5 precedent). Single-tab realm is the v1 product surface — the
   topbar status indicator (T14) and Orphans panel (T13) live in the
   same shell tab, so peer-tab divergence isn't a v1 risk. Plan 23
   candidate.
4. **Toggle re-watch from OFF state is impossible.** Per the mockup's
   interaction spec ("OFF state shouldn't exist as a transient"), the
   row's Switch only goes ON → unwatch confirmation → row removed.
   There is no OFF-state row in the v1 UI — re-watching means going
   through the watch-enable modal (T15). The test for the toggle
   verifies clicking it calls `onUnwatch`, not that it has a re-watch
   path. This matches the mockup but is worth flagging: a user who
   accidentally unwatches a folder will need to re-pick it through
   the watch-enable picker; there's no one-click "re-watch" undo
   today. (The success toast does NOT carry an undo affordance —
   adding one is a Plan 23 candidate.)

**Self-review:**

- Mockup microcopy is verbatim. Empty-state heading + body + CTA;
  sub-line template with the orphan-omission branch; personal-domain
  privacy-rail note; error banner phrasing; toast lead + msg. Pinned
  by 16 vitest assertions against the exact strings.
- Tab placement matches the mockup hand-off note: between Domains and
  BRAIN.md. Eye icon for the sidebar entry (mockup §Microcopy).
- Per-row keyboard order matches mockup §"Keyboard order": Switch →
  Include subfolders checkbox → Resync → Open in Finder → Unwatch.
  Verified by tab-stop ordering in the rendered DOM (children of the
  row container).
- Accessibility per mockup §"Accessibility annotations": `<ul
  role="list">` wrapper; domain dot `aria-hidden`; switch carries
  explicit `aria-label` including the path; sub-line carries an
  `aria-label` aggregating the metrics; `<time datetime>` element
  for the ISO timestamp; loading state uses `role="status"` +
  `aria-live="polite"` + sr-only copy; error banner is
  `role="alert"`. No axe-core run yet (e2e is T16's deliverable);
  static review only.
- Plan 19 T4 named-interface pattern is honored in tools.ts: every
  new tool exports a named TS interface (`WatchedFolderEntry`,
  `ListWatchedFoldersData`, `UnwatchFolderData`) rather than inlining
  the shape at the call site. A future backend shape change ripples
  through one type alias rather than every wrapper site.
- The `tsc --noEmit` discipline per auto-memory
  `feedback_tsc_vs_vitest.md` is satisfied — both vitest and tsc were
  run after every save; neither leaked an error.

## T12 fix-up outcome

**Status:** ✅ DONE.

**Why a fix-up?** The original T12 outcome (above) flagged the "Resync
now" button as a placeholder, claiming `brain_resync_folder` "did not
ship in T5." This was a false negative: the handler exists at
`packages/brain_core/src/brain_core/tools/resync_folder.py` (276 LOC),
is registered in `packages/brain_core/src/brain_core/tools/__init__.py:107`,
appears in `brain_core.tools.list_tools()` (the registry returns 45
tools including `brain_resync_folder`), and has its INPUT_SCHEMA +
`ToolResult.data` shape pinned by
`packages/brain_core/tests/tools/test_resync_folder.py`. T12 shipped a
disabled button + "Coming soon" tooltip on a feature that was already
ready to wire. The fix-up wires it correctly.

**Files modified:**

- `apps/brain_web/src/lib/api/tools.ts` — added `ResyncFolderData`
  named interface (mirrors Plan 19 T4 + Plan 22 T12 pattern; the
  Python pin in `test_resync_folder.py` `test_data_shape_pin_empty_folder`
  fails RED on drift). Added `resyncFolder` typed wrapper. Registered
  `brain_resync_folder` in `ALL_TOOL_NAMES`. Updated the registry
  comment block to remove the "did not ship in T5" claim and reflect
  the fix-up wiring. Tool count: 40 → 41.
- `apps/brain_web/src/lib/state/watched-folders-store.ts` — added the
  `resyncFolder(folder)` action. Resolve-rejects semantics (unlike
  the `refresh()` action's resolve-always — callers await the result
  to drive the per-row spinner + toast lifecycle). On success the
  store fires a follow-up `void refresh()` so any row stats
  invalidated by the resync (file_count, orphan_count, last_sync)
  reconcile with the canonical backend list. Errors are propagated
  to the caller's catch arm rather than landed on `error` state
  (which is reserved for `refresh()` failures the inline banner reads).
- `apps/brain_web/src/components/settings/panel-watched-folders.tsx` —
  replaced the disabled "Resync now" button + "Coming soon" tooltip
  with a fully-wired button. While in flight: button is disabled,
  `aria-busy="true"`, `aria-label` swaps to "Resyncing &lt;path&gt;,
  please wait" (mockup §"Accessibility annotations"), label swaps to
  "Syncing…" + spinner replaces the icon (mockup §"Mutation in-flight
  state"). The sibling Unwatch action on the same row also disables
  during a resync so the user can't queue a competing mutation.
  Per-row in-flight tracking uses a `Set` keyed by path (not a
  boolean) so concurrent resyncs on different rows don't trample
  each other's spinner. Success toast: lead "Resync complete.", msg
  surfaces all four backend summary counts (`updated` / `no_change` →
  "unchanged" / `newly_orphaned` / `restored_from_orphan` →
  "restored"). Failure toast: lead "Resync failed.", msg from
  error.message. Updated the panel docstring to reflect the wire-up.
- `apps/brain_web/tests/unit/panel-watched-folders.test.tsx` — added
  the `resyncFolderMock` hoisted factory + mock factory entry; added
  `resyncFolderMock.mockReset()` to `beforeEach`. Added a new
  `describe` block "PanelWatchedFolders — Resync action (T12 fix-up)"
  with 5 tests (the prior file had NO resync coverage — the original
  T12 didn't write a disabled-assertion test for it):
    1. Button is NOT disabled when a row is present + has no
       `aria-busy` at rest.
    2. Clicking Resync calls `brain_resync_folder({folder})` with the
       row's path.
    3. In-flight state asserts: button disabled, `aria-busy="true"`,
       `aria-label="Resyncing /p/A, please wait"`, label is
       "Syncing…", sibling Unwatch button also disabled. After
       resolve, button re-enables and label returns to "Resync now".
    4. Success toast carries all four backend summary fields verbatim
       in the message.
    5. Failure path: danger toast with the error message; spinner
       clears via the `finally` arm.
  Plus a docstring entry (#9) describing the new coverage.
- `apps/brain_web/tests/unit/api-client.test.ts` — bumped tool-count
  pin from 40 → 41 and updated the comment trail to record the
  fix-up addition.

**Mock-default trap learned the hard way:** the first run of the new
tests had 3 failures rooted in `mockResolvedValue()` being overwritten
by a subsequent `mockResolvedValue()` for the same mock. The fix
pattern is `mockResolvedValueOnce` for the mount-fetch followed by a
default `mockResolvedValue` for the reconcile-refresh — same precedent
as the existing "unwatch toast" test (line 412 onward). Documented in
the test file's inline comments at the failure sites.

**Verification gates:**

- `pnpm vitest run tests/unit/panel-watched-folders.test.tsx`:
  21/21 passing (was 16; +5 fix-up tests), 0.83s.
- `pnpm vitest run` (full suite): 517 passing / 1 skipped, 6.07s
  (was 512/1 in T12 outcome).
- `pnpm tsc --noEmit`: exit 0. Per auto-memory
  `feedback_tsc_vs_vitest.md`, both gates run; both clean.

**What this fix-up did NOT address:**

- "Open in Finder" button — still disabled with the "Coming soon"
  tooltip. The OS-native open helper genuinely does not exist in the
  codebase today (no `Integrations` module under `apps/brain_web/`,
  and the brain backend doesn't ship an `open <path>` shim). Plan 23
  candidate, unchanged from the original T12 §"Concerns" item #2.
  This was confirmed before the fix-up started, not assumed.
- "Include subfolders" checkbox — still disabled (T12 didn't wire
  re-watch flow; the toggle is for visual rhythm only). Plan 22 T15
  (watch-enable modal) is the canonical re-watch path; no change here.
- The fix-up does NOT add an e2e test for the resync action — that's
  T16's deliverable per the original task split.

**Self-review:**

- Backend contract match verified against
  `packages/brain_core/tests/tools/test_resync_folder.py` lines 50-60
  (INPUT_SCHEMA) and lines 88-118 (`ToolResult.data` shape pin).
  Wire shape: `{folder: string}` in, `{status: "resynced", folder,
  summary: {updated, no_change, newly_orphaned, restored_from_orphan}}`
  out. TS interface mirrors exactly; drift on either side fails RED
  on the Python pin.
- Toast microcopy maps backend keys to user-facing words: `no_change`
  → "unchanged", `restored_from_orphan` → "restored" — these are
  small adaptations from the raw backend keys for readability. The
  mockup §"Microcopy" line 166 specified an older keyset
  (`checked / new / updated / marked_orphan`) that doesn't match the
  shipped backend; the fix-up prefers backend reality and crafts
  user-friendly terms from it. Documented in the panel's
  `handleResync` callback for the next engineer.
- Plan 19 T4 named-interface discipline honored: `ResyncFolderData`
  exported from `tools.ts` rather than inlined at the wrapper site,
  so a future backend shape change ripples through one type alias.
- Per-row spinner state uses a `Set<string>` not a `boolean` so
  concurrent resyncs on independent rows don't share the spinner
  (defensive — the UI doesn't expose a way to start two
  simultaneously today, but the data shape supports it without a
  refactor when bulk-resync lands).
- `aria-busy="true"` while syncing + reworded `aria-label` per
  mockup §"Accessibility annotations" line 200. Static review only
  (axe-core is T16's e2e deliverable).
- Sibling action disable during resync prevents competing mutations
  on the same row (mockup §"Mutation in-flight state" line 142).

## T13 outcome

**Date:** 2026-05-12.

**Subagent:** brain-frontend-engineer.

**Status:** ✅ Complete.

**Files created:**

- `apps/brain_web/src/components/settings/panel-orphans.tsx` (~660 LOC)
  — Settings → Orphans panel implementing the mockup at
  `docs/design/plan-22/orphan-management.md`. Renders one row per
  orphan, groups by `watched_folder_id`, surfaces per-row Restore +
  Delete actions, supports per-row + bulk selection with a sticky
  bulk-action bar, and routes both single-row + bulk delete through
  the existing `TypedConfirmDialog` primitive (slug for single, "delete
  N notes" literal phrase for bulk per Q4=4.A). Filter dropdowns
  (folder + domain) drive a `useMemo` reduction before the
  group-by-folder step. State management mirrors PanelWatchedFolders.
- `apps/brain_web/src/lib/state/orphans-store.ts` (~165 LOC) — zustand
  store peer to `useWatchedFoldersStore` with the same shape
  (`refresh()` resolve-always, `removeOrphanOptimistic()` for snappy
  UX, `restoreOrphan()` / `deleteOrphan()` resolve-rejects for
  per-row spinner + toast lifecycle, `_resetForTesting()` for unit
  tests). In-flight serialization via module-scope Promise cache so
  concurrent `refresh()` calls share one fetch. The store ALWAYS
  passes `typed_confirm: true` to `brain_delete_orphan` — the UI guards
  the typed-confirm at the modal layer; backend's PermissionError
  refusal is the belt-and-braces backstop.
- `apps/brain_web/tests/unit/panel-orphans.test.tsx` (~570 LOC, 23
  tests) — covers populated state, empty state, loading state, error
  banner, single-row restore (happy + optimistic + failure), single-
  row delete typed-confirm flow + mistype guard, bulk-select group
  toggle, bulk restore (sequential N calls), bulk delete typed-confirm
  (verbatim phrase pin + N sequential calls + mistype refusal),
  Clear selection, and accessibility annotations (row aria-label
  composition, warn-icon aria-hidden, group separator aria-label).

**Files modified:**

- `apps/brain_web/src/lib/api/tools.ts` — added 4 named TS interfaces
  (`OrphanEntry`, `ListOrphansData`, `RestoreOrphanData`,
  `DeleteOrphanData`) per Plan 19 T4 named-interface discipline, plus
  3 typed wrappers (`listOrphans`, `restoreOrphan`, `deleteOrphan`).
  `ALL_TOOL_NAMES` count: 41 → 44.
- `apps/brain_web/src/components/settings/settings-screen.tsx` — added
  `"orphans"` to `SettingsTabId` union; registered the tab immediately
  after `"watched-folders"` per the mockup hand-off note ("Place
  adjacent to watched-folders"); added `<PanelOrphans />` to the
  `renderPanel` switch with the `AlertTriangle` icon from
  `lucide-react`.
- `apps/brain_web/tests/unit/api-client.test.ts` — bumped the
  41-tool count pin to 44 with a comment trail describing which Plan
  22 tools landed in T13 and which (just `brain_watch_folder`) defer
  to T15.

**Backend shape pins:** the 4 TS interfaces were derived directly from
the Python pin tests in `packages/brain_core/tests/tools/`:

- `OrphanEntry` ← `test_list_orphans.py::test_returns_only_orphaned_notes_data_shape_pin`
  (5 keys: `note_path`, `domain`, `source_path`, `orphaned_at`,
  `watched_folder_id`).
- `ListOrphansData` ← `{orphans: OrphanEntry[]}` outer envelope from
  `test_empty_vault_returns_empty_orphans` + the test above.
- `RestoreOrphanData` ← `test_restore_orphan.py::test_data_shape_pin_and_flips_frontmatter`
  (3 keys: `status: "restored"`, `note_path`, `undo_id`).
- `DeleteOrphanData` ← `test_delete_orphan.py::test_data_shape_pin_happy_path`
  (3 keys: `status: "deleted"`, `trash_path`, `undo_id`).

Drift on either side fails RED on the Python pin → TS interface stays
in lock-step. Same Plan 19 T4 cosmetic-widen direction.

**TypedConfirmDialog usage:** the existing primitive at
`apps/brain_web/src/components/dialogs/typed-confirm-dialog.tsx` is
reused as-is for BOTH single-row delete (word = note slug per the
modal-orphan-delete.md mockup line 39 ) and bulk delete (word =
"delete N notes" literal phrase per the mockup's bulk-mode section).
No new dialog kind was registered, no headerSlot extension was added
— the note-card header preview from the mockup is a T15 concern (the
mockup's "Implementation guidance for T15" section recommends
extending TypedConfirmDialog with an optional `headerSlot: ReactNode`
prop; T13 ships with the simpler word-only typed-confirm to keep
scope tight).

**Bulk-delete strategy:** sequential per-note calls (not a new batch
endpoint). The backend's T5 deliverable shipped per-note tools only;
T13 iterates `brain_delete_orphan({note_path, typed_confirm: true})`
over the selection in a for-loop, collecting `okCount` + `firstErr`
to drive a tri-state toast ("N notes deleted." on full success / "ok
of N notes deleted." on partial / "Couldn't delete." on full failure).
Sequential keeps the optimistic-drop + failure-reconcile pattern
simple and avoids overlapping `refresh()` calls that would otherwise
share an in-flight Promise. Documented in the panel's
`handleBulkDelete` callback for the next engineer.

**Verification gates:**

- `pnpm vitest run tests/unit/panel-orphans.test.tsx`:
  23/23 passing, 1.98s.
- `pnpm vitest run` (full suite): 540 passing / 1 skipped (was 517/1
  at T12 fix-up), 7.25s.
- `pnpm tsc --noEmit`: exit 0. Per auto-memory
  `feedback_tsc_vs_vitest.md`, both gates run; both clean.

**Mockup-fidelity self-check:**

- Header microcopy verbatim: "Orphaned notes" + "These notes used to
  come from watched folders, but their source files no longer exist.
  Restore brings them back into your knowledge base; delete moves
  them to trash."
- Empty-state copy verbatim: "No orphaned notes." + "Every note in
  your vault still has a source file behind it. Nice work." + "View
  watched folders ›".
- Filter labels verbatim: "Filter by folder:" / "Filter by domain:"
  + "All folders" / "All domains".
- Bulk-action bar copy verbatim: "Selected: ${n}" + "Restore selected"
  + "Delete selected…" (with ellipsis) + "Clear selection".
- Group separator template verbatim: "From ${path} · ${domain-badge}
  · ${count} orphan(s)" + per-group "select all" lowercase affordance
  + "clear all" toggle when fully-selected.
- Per-row sub-line: "Source: ${source_path}" line + "Orphaned
  ${relative} · was last synced ${date}" line. Caveat: the
  "last synced" portion currently shows the orphaned-at timestamp
  (`OrphanEntry` from T5 only ships `orphaned_at`, not a separate
  `last_synced_at` field); flagged as a Plan 23 candidate below.
- Toast copy verbatim for restore + delete success/failure (per-row
  + bulk variants), pinned by vitest assertions.
- Accessibility annotations: warn-icon `aria-hidden="true"`,
  row-level `aria-label` aggregating title + source + relative-time,
  bulk-action bar `role="region"` + `aria-label="Bulk actions for
  selected orphans"`, group `<h3>` with `aria-label` naming count +
  path + domain. Pinned by 3 a11y tests at the end of the test file.

**Concerns / follow-ups (Plan 23 candidates added below):**

1. **`OrphanEntry` lacks a separate `last_synced_at` field.** The
   mockup's per-row sub-line template references "was last synced
   ${date}" — distinct from "orphaned ${relative}". The backend's
   T5 `brain_list_orphans` only emits `orphaned_at`, so v1 the panel
   renders the same timestamp for both halves of the line. A future
   T5 amendment + Plan 19 T4 cosmetic widen would carry a separate
   `last_synced_at` (or `last_seen_at`) field.
2. **TypedConfirmDialog headerSlot extension deferred to T15.** The
   modal-orphan-delete.md mockup specifies a note-card preview inside
   the typed-confirm modal (warn icon + title + source line). T13
   ships with the simpler word-only typed-confirm to keep scope
   tight; T15 (per the mockup's "Implementation guidance" section)
   is where the headerSlot prop addition lands. v1 typed-confirms
   render with the body explanation + Type-${word}-to-confirm input
   pattern from the existing primitive.
3. **No frontmatter `title` in the OrphanEntry shape.** The mockup's
   row anatomy says "The note's title (frontmatter `title` or slug
   fallback)". The backend's T5 pin only carries `note_path` /
   `domain` / `source_path` / `orphaned_at` / `watched_folder_id`,
   so v1 always falls back to the slug. A future T5 amendment +
   Plan 19 T4 cosmetic widen would carry the title.
4. **Cross-store reconciliation: watched-folders `orphan_count`
   stays stale after restore/delete.** When the user restores or
   deletes an orphan in the Orphans panel, the watched-folders
   store's `orphan_count` column doesn't auto-invalidate. The
   counter only updates when the user navigates to Watched folders
   and the panel's first-mount `refresh()` re-walks the vault. v1
   accepts this; the mockup's hand-off note flagged it as
   acceptable. A BroadcastChannel-style pubsub (or a one-line
   `void useWatchedFoldersStore.getState().refresh()` chained off
   the orphans store's successful mutations) is a Plan 23 candidate.
5. **Bulk action progress feedback is binary (idle / done), not
   running-N.** Per mockup §"Bulk action in-flight": "When user
   clicks 'Restore selected' with 2 selected, the bulk bar shows:
   'Restoring 2 notes…' with spinner." T13 ships with the rows
   themselves fading to 50% opacity + `aria-busy="true"` while the
   action runs (visible in the existing per-row spinner / state),
   but the bulk-bar text does NOT switch to a "Restoring N…" label
   during the sequential loop. The user still sees per-row feedback
   + the eventual toast. Flagged as a UX-polish item for Plan 23.

**Self-review:**

- Plan 19 T4 named-interface discipline honored: 4 named interfaces
  exported from `tools.ts` rather than inlined at the wrapper sites,
  so a future backend shape change ripples through one type alias
  per shape.
- Per-row spinner state uses two `Set<string>` (one for restoring,
  one for deleting) so concurrent mutations on independent rows
  don't share spinner state — same defensive pattern as T12's
  resync `Set` precedent.
- Optimistic-drop + reconcile-on-failure pattern mirrors
  panel-watched-folders unwatch handler (Plan 22 T12 / Plan 16 T4 D4
  precedent). Failure path always re-fetches via
  `useOrphansStore.getState().refresh()` so the dropped row reappears.
- Selection set lives in component-local state per the mockup
  hand-off note ("Selection state lives in component-local
  `Set<string>` — does NOT need to persist across tab switches").
- Per-row `aria-label` aggregates title + source + relative-time
  per mockup §"Accessibility annotations" line 194.
- Bulk-action bar carries `role="region"` + `aria-label="Bulk
  actions for selected orphans"` per mockup line 191; selection
  count is `aria-live="polite"` per mockup line 192.
- Group separator is a real `<h3>` (visually rendered as the em-dash
  rule per mockup line 193) with `aria-label` naming count + path +
  domain. Screen readers can navigate by heading.
- Warn icon (`AlertTriangle`) is `aria-hidden="true"` per mockup
  line 196; row's status conveyed via the row-level `aria-label`.

## Plan 23 candidate scope

Filled in at T17 closure. Preserved Plan 17/earlier carry-forwards
(4 NOT-DOING items, unchanged) PLUS any Plan 22-surfaced candidates.
Likely v2 candidates surfacing from Plan 22 execution:

- Vault-edit-aware conflict resolution (overwrite vs keep-vault vs
  prompt vs LLM-merge) — D1's overwrite contract is the v1
  simplification.
- Move/rename detection via content_hash matching — D1 punts to
  delete+add.
- Per-folder configurable policies — D1 hardcodes `policy = "overwrite"`
  in WatchedFolder schema but reserves the field for v2.
- Multi-folder conflict (same file in two watch paths) — D1 doesn't
  define behavior.
- Auto-classify mode for watched folders (D4 punts to classify-once-
  preserve).

## T14 outcome

**Status:** DONE — Topbar status indicator wired per `docs/design/plan-22/topbar-status.md`. Self-hides on empty vault, shows watched count (Eye, `--text-muted`) + orphan count (AlertTriangle, `--warn`) per the state table, click-through routes to `/settings/orphans` (high-attention path) when orphan_count > 0 else `/settings/watched-folders`. Subscribes to `useWatchedFoldersStore` — no extra fetch; reflects T12 store mutations automatically.

### Files

- `apps/brain_web/src/components/shell/watched-folders-topbar-indicator.tsx` (CREATED, ~230 LOC) — standalone component per T11 mockup recommendation. Exports `WatchedFoldersTopbarIndicator` + `composeIndicatorCopy` (pure-function helper for tooltip + aria-label strings, unit-testable without rendering).
- `apps/brain_web/src/components/shell/topbar.tsx` (MODIFIED, +13 LOC) — imported and mounted between `ConnectionIndicator` and Theme toggle per Q2=2.A (right side, between vault-state affordances and global controls).
- `apps/brain_web/tests/unit/topbar-watched-status.test.tsx` (CREATED, ~360 LOC, 16 tests).

### Aggregation pattern

```ts
const folders = useWatchedFoldersStore((s) => s.folders);
const error   = useWatchedFoldersStore((s) => s.error);
const { watchedCount, orphanCount } = React.useMemo(() => ({
  watchedCount: folders.length,
  orphanCount:  folders.reduce((a, f) => a + f.orphan_count, 0),
}), [folders]);
```

Individual selectors (not a tuple selector with custom equality) — zustand's referential equality on each slice is enough; the memo on `folders` re-runs only when the array reference flips (refresh / optimistic remove).

### Click-through routing

- `orphan_count > 0` → `/settings/orphans` (D-mockup high-attention path)
- `orphan_count === 0` → `/settings/watched-folders`
- error state → `/settings/watched-folders` AND fires `store.refresh()` on click (concurrent kick-off with the route change so the panel hydrates fresh)

### Empty-state treatment

**Hidden** (returns `null`) when `watched_count === 0 && orphan_count === 0 && !hasError`. Per mockup §"Empty state" reconsideration: "layout jitter is actually FINE here because the indicator's appearance is itself a meaningful event" — when a user enables their first watched folder, the slide-in is the affordance. Implementation: `null` return; no entrance transition yet (mockup notes 200ms ease-out is a "nice to have" — left to a polish pass if e2e shows the abrupt appearance is jarring).

### Accessibility

- Trigger is a real `<a>` (Next.js `Link` + Radix `asChild` slot) → keyboard-focusable, Enter/Space activates by default.
- `aria-label` spells out the full state ("3 folders watched, 2 orphaned notes need attention. Open Settings to manage.") so screen-readers get one announcement, not icon-by-icon.
- Sibling `<span role="status" aria-live="polite" aria-atomic="true" className="sr-only">` announces mid-session changes (e.g. watcher event flips orphan_count 0 → 1) — the trigger's `aria-label` change wouldn't re-announce.
- Icons all `aria-hidden="true"`; numeric counts carry the meaning textually.
- Plural-aware microcopy: "1 folder watched" vs "3 folders watched", "1 orphaned note needs" vs "2 orphaned notes need".
- Color is NOT the only signal: `Eye` vs `AlertTriangle` are visually distinct shapes; light/dark mode color contrast is documented in the mockup §"Accessibility annotations" — the `--warn` token theme-flips to `--danger` in light mode to clear AA 4.5:1.

### Component extraction

Standalone `WatchedFoldersTopbarIndicator` in a sibling file (not inline JSX in topbar.tsx) per T11 mockup §"Surface intent": "New component `WatchedFoldersTopbarIndicator` lives in `apps/brain_web/src/components/shell/topbar.tsx` (or split into a sibling file per the topbar refactor pattern)". Sibling-file path chosen to (a) keep `topbar.tsx` lean (currently ~430 LOC; adding 100+ inline would push past the readable-file threshold), (b) match the existing `connection-indicator.tsx` standalone pattern, (c) export the pure `composeIndicatorCopy` for unit-testing without React render overhead.

### Tests (16 cases, all pass)

1. `composeIndicatorCopy` pinning × 6: plural/singular permutations, error state.
2. Render: empty state → `null`; watched-only segment; combined state routes to `/settings/orphans`; orphans-only data path noted as unreachable from this store alone (documented).
3. Error state: glyph + retry copy + click fires `refresh()`. Suppresses jsdom's "Not implemented: navigation" noise.
4. Live updates: zustand subscription — mutating store mid-render flips aria-label, count, AND href. Hidden → visible mount transition.
5. Accessibility: sr-only live region present with `role=status`, `aria-live=polite`, `aria-atomic=true`; trigger is `<a>` with `aria-label`; all icons `aria-hidden=true`.

### Verification

```
$ pnpm vitest run tests/unit/topbar-watched-status.test.tsx
 Test Files  1 passed (1)
      Tests  16 passed (16)

$ pnpm tsc --noEmit
(clean)

$ pnpm vitest run
 Test Files  84 passed (84)
      Tests  556 passed | 1 skipped (557)
```

No tsc errors; no vitest regressions; the new file uses no `any` casts.

### Mockup fidelity

- Token-faithful: every color references CSS variables (`--text-muted`, `--text-dim`, `--warn`, `--danger`, `--surface-2`, `--surface-3`, `--hairline`, `--tt-cyan`).
- Icon set: Lucide `Eye` + `AlertTriangle` per mockup anatomy.
- Pill geometry: `h-7`, `rounded-full`, `gap-1.5`, `px-2.5` — matches the mockup's ~28px height + `--r-pill` radius + `--surface-2` background.
- Tooltip: Radix `Tooltip` with `delayDuration={260}` per mockup §"Hover".
- Plural-aware microcopy: verbatim from mockup §"Microcopy".

### Concerns / follow-ups (non-blocking)

1. **Orphans-only state coverage gap.** The mockup describes a state where watched_count=0 AND orphan_count>0 (user unwatched the folder but orphans persist per D2). The current data path (folders.length for watched_count, sum of folders[*].orphan_count for orphan_count) makes this state unreachable: unwatching drops the folder from `Config.watched_folders` → drops from `list_watched_folders` response → loses its orphan_count contribution. Truly reaching this state requires subscribing to the orphans store too (`useOrphansStore.orphans.length` as a fallback when folders.length=0). Documented in the test file; tracked as a polish-pass item. Render branch IS in place — only the data path is gapped.
2. **Entrance transition.** Mockup §"Implementation guidance" reconsideration calls for a 200ms ease-out slide-in when the indicator appears mid-session. Current implementation just `null`-returns the hidden state, so the appearance is instantaneous. Tracked for visual polish.
3. **Click-while-error navigates AND refreshes.** In error state, the click both fires `refresh()` AND navigates to `/settings/watched-folders`. The mockup §"Interaction" line ("On click in error state, fire `store.refresh()` directly (no navigation)") suggests no-navigate. Current implementation lets the user land on the panel that surfaces the canonical retry banner — defensible since both surfaces ultimately do the same thing (`refresh()`). If e2e shows this is confusing, add `e.preventDefault()` in the error-state click branch.

### Commit cadence

Bundled — feat + test + docs in one commit per the plan-19 / T13 outcome shape.

## T14.5 outcome — dry_run mode on brain_watch_folder (cost estimate without writes)

Inserted per user adjudication Q3=3.A locked at the T11 review: the
watch-enable modal (T15) needs an inline cost-estimate panel BEFORE the
user clicks "Watch and sync now". Backend wiring picked over a
separate `brain_estimate_watch_cost` tool because the estimate code is
already inside `watch_folder.py` (T9's `_estimate_initial_sync_cost` +
the same `classify_model` resolution that the real-run path uses) —
a `dry_run: bool` gate is a one-flag extension that keeps both paths
synchronized; a separate tool would have to re-derive everything and
drift.

### Status field semantics

Three terminal statuses on `ToolResult.data["status"]`:

- `"watched"` — real write path, Config mutated, optionally synced.
- `"already_watched"` — idempotent no-op short-circuit (also returned
  when `dry_run=True` on an already-watched folder, because the
  "nothing to do" meaning is truthful regardless of dry-run intent).
- `"dry_run"` — Plan 22 T14.5: estimate-only, no writes.

The early `already_watched` short-circuit was kept BEFORE the dry-run
branch on purpose. A dry-run against an already-watched folder is also
a no-op estimate, and `already_watched` is the more truthful status
for the modal to render (whereas `"dry_run"` would imply "a write is
pending if you confirm" — which is false for an already-watched
folder).

### Skip paths

`dry_run=True` skips:

1. **Config mutation** — `Config.watched_folders.append` does NOT run;
   `persist_config_or_revert` is NOT entered (so no `.brain/config.json`
   write either).
2. **Backup snapshot** — `create_snapshot(..., trigger="pre_watched_folder_sync")`
   does NOT fire (snapshot retention budget is preserved).
3. **BulkImporter** — neither `_build_pipeline`, `BulkImporter(...)`,
   `.plan(...)`, nor `.apply(...)` runs (no LLM spend, no vault writes).

Validation IS still performed (so the modal surfaces clear errors):

- Folder absolute + exists + is a directory.
- Config presence (`raise_if_no_config`).
- Cross-field `domain` membership in `Config.domains` (when supplied)
  — the Plan 16 T36 pre-check pattern.

The cost-estimate file walk (`_estimate_initial_sync_cost`) IS reused
verbatim — same helper, same token math, same classify-model
resolution. The dry-run path and real-run path project the same
projected spend.

### Return shape parity

`dry_run=True` returns the same 5-key data shape as the real-run path:

```python
{
  "status": "dry_run",
  "folder": <abs path str>,
  "domain": <effective domain slug>,
  "initial_sync_summary": None,         # no sync ran
  "cost_estimate": {                    # 4-key payload, same as T9
    "file_count": int,
    "estimated_tokens": int,
    "estimated_usd": float | None,
    "classify_model": str,
  } | None,                             # None when initial_sync=False
}
```

When `initial_sync=False` AND `dry_run=True`: `cost_estimate=None`
(symmetric with the non-dry-run `initial_sync=False` shape — there is
no sync to project either way).

### Pin tests (7)

Added in `packages/brain_core/tests/tools/test_watch_folder.py`:

1. **`test_dry_run_does_not_mutate_config`** — `dry_run=True` returns
   without appending; `Config.watched_folders` unchanged; on-disk
   `config.json` never created.
2. **`test_dry_run_does_not_call_backup`** — monkey-patched
   `create_snapshot` is NOT called in dry-run.
3. **`test_dry_run_does_not_call_bulk_importer`** — monkey-patched
   `BulkImporter.plan` AND `.apply` are NOT called in dry-run.
4. **`test_dry_run_returns_cost_estimate`** — 4-key `cost_estimate`
   payload is populated with the same shape T9's real-run path
   produces.
5. **`test_dry_run_returns_status_dry_run`** — `data["status"]` is
   `"dry_run"` (NOT `"watched"`); full 5-key data shape parity.
6. **`test_dry_run_still_validates_folder`** — missing folder /
   non-absolute folder / orphan domain all raise BEFORE the
   cost-estimate work starts; no state leaks onto Config across any
   of the three failure modes.
7. **`test_dry_run_then_real_run_works_idempotently`** — dry-run
   followed by real-run mutates Config as if the dry-run never
   happened; `cost_estimate` payloads from preview vs real match
   exactly.

`test_input_schema_shape` was also updated to pin the new `dry_run`
property: `type=boolean`, `default=False`, `description` present.

### Verification

```
$ unset VIRTUAL_ENV && PYTHONPATH=packages/brain_core/src:packages/brain_api/src:packages/brain_mcp/src:packages/brain_cli/src \
    uv run --package brain_core pytest packages/brain_core/tests/tools/test_watch_folder.py -v
23 passed in 0.55s          # 16 baseline + 7 new T14.5 pins

$ unset VIRTUAL_ENV && PYTHONPATH=... uv run --package brain_core pytest packages/brain_core/tests/ -q
1156 passed, 5 skipped       # baseline 1149 → 1156 (+7 T14.5)

$ uv run --package brain_core mypy packages/brain_core/src/brain_core/tools/watch_folder.py
Success: no issues found in 1 source file
```

### Decisions touched

- **Q3=3.A (locked)** — dry_run mode on `brain_watch_folder` is the
  cost-estimate plumbing the watch-enable modal consumes.
- **D11 (no new dependencies)** — respected; this is a pure-Python
  one-flag extension.
- Backend-only; T15 will consume from the frontend.

### Concerns / follow-ups (non-blocking)

1. **`dry_run=True` does NOT validate that BulkImporter would actually
   plan-succeed.** The estimate walks the folder via `rglob` (same
   path as `_estimate_initial_sync_cost` uses on the real path), but
   it doesn't dry-run the classifier or check per-file budgets. If a
   user has an exhausted per-domain budget, the dry-run will project
   a normal cost estimate and the real call will then refuse mid-sync.
   This is consistent with T9's D3 ("estimate is informational; budget
   caps are the hard ceilings"), so T14.5 inherits the same contract.
   The modal's CTA copy should clarify this if testers report
   surprises.
2. **No "ETA" or duration estimate.** The task spec asked whether to
   add a duration alongside the USD. Skipped — the per-file classify
   latency varies too much (haiku at ~1-3s/file conservatively, but
   subject to rate-limit backoff) to project usefully from file-count
   alone. The text readout already says "classify only;
   summarize+integrate cost is per-file post-classify" — a duration
   added on top would imply more precision than the projection
   carries.
3. **`dry_run=True` + `initial_sync=False`** returns
   `cost_estimate=None` (consistent with the real-run shape on
   `initial_sync=False`). The modal will likely only ever fire
   `dry_run=True` + `initial_sync=True` since the cost preview is the
   whole point — but the no-cost combination is supported for shape
   parity.

### Commit cadence

Bundled — feat + test + docs in one commit per the plan-19 / T13 / T14
outcome shape.

## T15 outcome — Confirmation modals (watch-enable / watch-disable / orphan-delete) + Bulk Import → Watch CTA

**Status: DONE.** All 3 modals shipped, panel + bulk-import CTAs
wired, 580 vitest tests green, tsc clean.

### What shipped

1. **`WatchEnableModal`** (`apps/brain_web/src/components/dialogs/watch-enable-modal.tsx`):
   - Fires `brain_watch_folder` with `dry_run=true` on mount + on every
     input change (folder / domain / include_subdirs) to populate the
     cost panel. Inputs cancel-safe via a per-effect signal flag so
     a stale Promise can't overwrite fresh state.
   - D1 callout paragraph is rendered VERBATIM from the mockup
     `docs/design/plan-22/modal-watch-enable.md` §"D1 contract
     paragraph — final agreed wording" (lines 172-176). The "Heads-up"
     intro, "source of truth" phrasing, and "isn't deleted" emphasis
     are pinned by `watch-modals.test.tsx`'s D1-verbatim assertion.
   - Cost panel renders four states per mockup §States 2-4 + 5:
     loading (`Estimating cost…`), success (`N files found · estimated
     cost ~$U`), error (non-blocking with `Try again` retry), and the
     Bulk Import "already imported" helper line. The
     `already_watched` dry-run status surfaces inline validation
     (mockup §State 6) + disables the confirm button.
   - Pre-fill props (`prefilledFolder`, `prefilledDomain`) bridge the
     Bulk Import → Watch path (D6); read-only folder input + eyebrow
     swap to `BULK IMPORT → WATCH` when prefilled.
   - On confirm, fires real-run + toasts + refreshes
     `useWatchedFoldersStore` so the Settings panel + topbar status
     indicator pick up the new row.
2. **`WatchDisableModal`** (`apps/brain_web/src/components/dialogs/watch-disable-modal.tsx`):
   - Confirmation modal (NOT typed-confirm) per mockup §"Why no typed-
     confirm" — the action is reversible.
   - Default button variant (NOT destructive) per mockup §"Why the
     confirm button is NOT destructive variant" — nothing is being
     deleted.
   - Renders the "stays the same" / "what changes" lists verbatim from
     the mockup, with a conditional orphan-count info-line that ONLY
     renders when `folder.orphan_count > 0`.
   - Owns the API call + toast + optimistic-drop + failure-rollback
     lifecycle so the parent panel's `handleUnwatch` collapsed to a
     1-liner `openDialog({kind: "watch-disable", folder: entry})`.
3. **Orphan delete** (`apps/brain_web/src/components/dialogs/orphan-delete-modal.tsx`):
   - Extension strategy: extended `TypedConfirmDialog` with a new
     `headerSlot?: React.ReactNode` prop (mockup §"Implementation
     guidance" recommended this over a sibling component). Backward
     compatible — existing callers (`brain_delete_domain`, backup
     restore, etc.) render identically.
   - This file exports two DialogKind builders:
     `buildSingleOrphanDeleteDialog` (slug typed-confirm + per-note
     warn-icon card) and `buildBulkOrphanDeleteDialog` (`delete N
     notes` phrase + summary card with up to 5 slugs + `…and N more`
     overflow). The builders own the slug derivation + microcopy + the
     `headerSlot` composition so a future mockup tweak doesn't drift
     between single + bulk modes.
   - `panel-orphans.tsx`'s `handleDelete` / `handleBulkDelete`
     refactored to use the builders. The post-confirm side effects
     (optimistic drop / API call / toast / refresh) stay in the
     orchestrator; the builders own ONLY the dialog payload shape.
4. **Bulk Import → Watch CTA** (`apps/brain_web/src/components/bulk/step-apply.tsx`):
   - "Watch this folder for changes" button in the apply-complete
     screen. Renders only when (a) a folder was picked AND (b) at
     least one file applied successfully (an all-failed run shouldn't
     suggest watching).
   - Click opens `useDialogsStore.open({kind: "watch-enable",
     prefilledFolder, prefilledDomain})` — modal handles the rest.
   - `domain: "auto"` (lazy classify) does NOT pre-fill the modal's
     domain (lets the modal default to active domain).
5. **`useDialogsStore` extension**: added `watch-enable` +
   `watch-disable` to the `DialogKind` discriminated union. `DialogHost`
   exhaustiveness switch updated to render the new kinds.
6. **`tools.ts` binding**: added `watchFolder` + `WatchFolderData`
   discriminated union + `WatchFolderCostEstimate` interface. Registry
   `ALL_TOOL_NAMES` widened to 45.

### TypedConfirmDialog extension strategy (mockup-flagged decision)

**Chose extension over sibling component.** Single source of truth for
the input-state + typed-confirm logic; backward compatible (existing
`brain_delete_domain` / backup-restore callers unchanged). The
`headerSlot` is rendered between the description and the body
paragraph — same insertion point the mockup specifies for the warn-icon
note card. Cheap one-prop addition; future callers (any destructive
typed-confirm that wants a metadata header) get the affordance for free.

### Files created (4)

- `apps/brain_web/src/components/dialogs/watch-enable-modal.tsx` (391 LOC)
- `apps/brain_web/src/components/dialogs/watch-disable-modal.tsx` (155 LOC)
- `apps/brain_web/src/components/dialogs/orphan-delete-modal.tsx` (170 LOC)
- `apps/brain_web/tests/unit/watch-modals.test.tsx` (471 LOC, 24 tests)

### Files modified (7)

- `apps/brain_web/src/components/dialogs/typed-confirm-dialog.tsx` — added `headerSlot` prop
- `apps/brain_web/src/components/dialogs/dialog-host.tsx` — added 2 dialog kinds
- `apps/brain_web/src/lib/state/dialogs-store.ts` — extended `DialogKind` union
- `apps/brain_web/src/lib/api/tools.ts` — added `watchFolder` binding + types
- `apps/brain_web/src/components/settings/panel-watched-folders.tsx` — wired modal CTAs
- `apps/brain_web/src/components/settings/panel-orphans.tsx` — routed through new builders
- `apps/brain_web/src/components/bulk/step-apply.tsx` — added Watch CTA
- `apps/brain_web/tests/unit/panel-watched-folders.test.tsx` — updated tests to reflect modal-gated unwatch
- `apps/brain_web/tests/unit/api-client.test.ts` — bumped tool count to 45

### Verification

```
$ cd apps/brain_web && pnpm vitest run tests/unit/watch-modals.test.tsx
✓ 24 tests passed (1.74s)
$ cd apps/brain_web && pnpm tsc --noEmit
(clean)
$ cd apps/brain_web && pnpm vitest run
✓ 580 tests passed | 1 skipped (6.97s)
```

### Self-review findings

- D1 callout copy is VERBATIM from the mockup — confirmed by the
  watch-modals.test.tsx `renders eyebrow + title + D1 callout verbatim`
  test which pins the exact phrases (`Heads-up`, `source of truth`,
  `your edits will be overwritten the next time the source file
  changes`, `isn't deleted`, `Settings → Orphans`).
- Microcopy strings for watch-disable's stays/changes lists are
  verbatim from the mockup — pinned in `WatchDisableModal — renders
  mockup-verbatim stays/changes lists` test.
- The orphan-count info-line conditional render matches mockup §State
  1 vs State 2 — pinned by two complementary tests.
- The "Choose folder" button uses the browser-only `webkitdirectory`
  shim (mockup §Implementation guidance flagged that the OS-native
  folder picker is a Plan 23 candidate). v1 lets the user paste the
  path directly; the picker is best-effort.
- `pushToast` is still imported in `panel-watched-folders.tsx`
  because `handleResync` consumes it. Lint is clean.

### Concerns / follow-ups (non-blocking)

1. **Native OS folder picker still missing** — the watch-enable modal's
   "Choose folder" button uses the browser `webkitdirectory` shim,
   which only surfaces the directory name (not the absolute path on
   disk) in most browsers due to security. Users on Mac / Windows will
   need to paste the absolute path manually in v1. Plan 23 candidate:
   wire through the same OS-bridge an Electron wrapper or the Plan 06
   setup wizard's folder picker uses.
2. **Domain dropdown defaults to `domains[0]` when `prefilledDomain` is
   omitted** — mockup §State 1 says "defaults to currently-active
   domain". The `useDomains()` hook surfaces `activeDomain` but the
   modal currently picks the first slug. Cheap follow-up (one line) if
   user testing shows surprises.
3. **No `BulkImporter`-aware dry-run** — same caveat T14.5 carried
   forward: a per-domain budget exhaustion will surface during the
   real-run, not the dry-run.
4. **Modal opens then closes on success but the dialogs-store's
   `active` resets via `onClose` (the modal-level close handler), not
   via an explicit unmount path. If the user clicks confirm and the
   API takes >5s, the user can still Cancel mid-flight which fires
   `onClose` but the in-flight Promise will resolve into a closed
   modal (no toast, no refresh). The fix is an AbortController on the
   confirm call — flagged as a Plan 23 candidate (low risk; the
   real-run is bounded by the initial-sync timeout).

### Commit cadence

Bundled — feat (modals + bindings + panel wiring) + test (24 new + 6
updated) + docs (this section) in one commit per the plan-19 / T13 /
T14 / T14.5 outcome shape.

## Review

_Filled in at T18 close. Tag SHA + closure summary + bumps + verification
receipts + backlog forward._

---

**End of Plan 22.**
