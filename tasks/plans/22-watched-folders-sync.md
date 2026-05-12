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

## Review

_Filled in at T18 close. Tag SHA + closure summary + bumps + verification
receipts + backlog forward._

---

**End of Plan 22.**
