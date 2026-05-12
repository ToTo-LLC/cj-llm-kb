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
