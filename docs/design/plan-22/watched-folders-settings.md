# Watched folders — Settings tab mockup (Plan 22 T11 §1)

Implements per `tasks/plans/22-watched-folders-sync.md` §T13. Mirrors the visual rhythm of `panel-domains.tsx` (Plan 13 / 16 precedent). New `SettingsTabId = "watched-folders"` slot in `settings-screen.tsx`.

## Surface intent

Give the user direct, transparent control over every watched-folder lifecycle event: see what's watched, see when it last synced, see how many files are flowing, force a resync, or unwatch entirely. Reads from `brain_list_watched_folders` (T5 tool surface). Mutations dispatch to `brain_watch_folder` / `brain_unwatch_folder` / `brain_resync_folder` (also T5). Empty / loading / error states are first-class.

## Layout (populated state, dark theme, comfortable density)

```
Settings → Watched folders                                                  [Density: Comfortable ▾]
─────────────────────────────────────────────────────────────────────────────────────────────────
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│  Watched folders                                                                            │
│  Brain mirrors files from these folders into your knowledge base automatically.             │
│  Source files are the source of truth — vault edits to watched notes are overwritten        │
│  on the next sync. [Learn how watching works ›]                                             │
│                                                                                             │
│                                                          ┌──────────────────────────────┐   │
│                                                          │ + Watch a new folder         │   │
│                                                          └──────────────────────────────┘   │
│                                                          (primary CTA, --tt-cyan bg)        │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│  ╭──────────────────────────────────────────────────────────────────────────────────────╮   │
│  │ ◉ /Users/chris/Notes/Research-Papers                          [research]    [●ON  ]  │   │
│  │   ↳ 142 files · 3 orphans · last synced 4 minutes ago                                │   │
│  │                                                                                       │   │
│  │   [Include subfolders ✓]   [Resync now ↻]   [Open in Finder ↗]   [Unwatch ×]         │   │
│  ╰──────────────────────────────────────────────────────────────────────────────────────╯   │
│                                                                                             │
│  ╭──────────────────────────────────────────────────────────────────────────────────────╮   │
│  │ ◉ /Users/chris/Documents/Work-Logs                            [work]        [●ON  ]  │   │
│  │   ↳ 38 files · 0 orphans · last synced 1 hour ago                                    │   │
│  │                                                                                       │   │
│  │   [Include subfolders ✗]   [Resync now ↻]   [Open in Finder ↗]   [Unwatch ×]         │   │
│  ╰──────────────────────────────────────────────────────────────────────────────────────╯   │
│                                                                                             │
│  ╭──────────────────────────────────────────────────────────────────────────────────────╮   │
│  │ ◉ /Users/chris/Private/Journal                                [personal]    [●ON  ]  │   │
│  │   ↳ 7 files · 0 orphans · last synced 12 minutes ago                                 │   │
│  │   ⓘ This folder syncs into your personal domain (privacy-railed by default).         │   │
│  │                                                                                       │   │
│  │   [Include subfolders ✓]   [Resync now ↻]   [Open in Finder ↗]   [Unwatch ×]         │   │
│  ╰──────────────────────────────────────────────────────────────────────────────────────╯   │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Per-row anatomy

| Element | Token / component | Purpose |
|---|---|---|
| Domain dot `◉` | `var(--dom-{slug})` filled circle, 8px | Visual link to the domain (matches topbar scope chip color) |
| Path | `--text`, `var(--mono)`, `--ui-md` | Truncates with ellipsis at container width; full path in tooltip |
| Domain badge `[research]` | `Badge` shadcn primitive, `var(--dom-{slug}-soft)` bg | Domain pill |
| Toggle `[●ON ]` | shadcn `Switch` | `Switch` toggles watch on/off — clicking OFF opens `modal-watch-disable` |
| Sub-line | `--text-muted`, `--ui-sm` | File count · orphan count · last sync timestamp |
| Orphan count | `--warn` if `>0` else `--text-dim` | Color-cues attention without screaming |
| Privacy-rail note (personal only) | `--text-dim`, `--ui-xs` with `ⓘ` icon | Reminds user the folder is in a privacy-railed domain |
| "Include subfolders" | shadcn `Checkbox` (small) | Reflects `WatchedFolder.recursive` |
| "Resync now ↻" | `Button variant="ghost"`, `RotateCw` icon | Fires `brain_resync_folder({path})`; spinner on click |
| "Open in Finder ↗" | `Button variant="ghost"`, `ExternalLink` icon | macOS `open <path>` / Windows `explorer.exe <path>` |
| "Unwatch ×" | `Button variant="ghost"`, `X` icon | Opens `modal-watch-disable` confirmation |

### Background + container

- Outer panel scrolls within the `SettingsScreen` right column (same as `panel-domains`).
- Each row is `--surface-1` on `--surface-0` page bg, `--hairline` border, `--r-md` radius, `--pad-md` interior padding.
- Hover: row bg shifts to `--surface-3` (subtle, 120ms ease).
- Focus: keyboard-focus visible 2px outline in `--tt-cyan` per existing `Button` focus-visible.

## States

### 1. Empty state (zero folders watched)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Watched folders                                                                │
│  Brain mirrors files from these folders into your knowledge base automatically. │
│                                                                                 │
│                                                                                 │
│              ╭──────────────────────────────────────────────╮                   │
│              │                                              │                   │
│              │             [folder-plus icon, 40px]         │                   │
│              │                                              │                   │
│              │      No folders being watched yet.           │                   │
│              │                                              │                   │
│              │      Pick a folder and Brain will keep its   │                   │
│              │      notes in sync automatically.            │                   │
│              │                                              │                   │
│              │      ┌──────────────────────────────────┐    │                   │
│              │      │ + Watch a folder                 │    │                   │
│              │      └──────────────────────────────────┘    │                   │
│              │                                              │                   │
│              │      [How does watching work? ›]             │                   │
│              ╰──────────────────────────────────────────────╯                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

- Empty-state card: `--surface-1`, `--hairline`, `--r-md`, centered text-align, 480px max-width.
- "How does watching work?" → inline link opens a help drawer / docs page (deferred to Plan 22 closure if not in T13 scope).

### 2. Loading state (initial fetch)

Skeleton placeholder card with shimmer animation honoring `prefers-reduced-motion`. Three skeleton rows at the row height. Header CTA + intro paragraph render immediately (don't block on data).

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Watched folders                                                                │
│  Brain mirrors files from these folders into your knowledge base automatically. │
│                                                          [ + Watch a new folder]│
├─────────────────────────────────────────────────────────────────────────────────┤
│  ╭──────────────────────────────────────────────────────────────────────────╮   │
│  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  [░░░░]      [░░░░]                  │   │
│  │   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░                                │   │
│  ╰──────────────────────────────────────────────────────────────────────────╯   │
│  (two more skeleton rows)                                                       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

Token: skeleton blocks use `--surface-3` bg with a 1.4s linear-gradient sweep.

### 3. Error state (backend unreachable)

Inline error banner (mirrors `panel-domains` Plan 16 T4 `storeError` banner):

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ╔═══════════════════════════════════════════════════════════════════════════╗  │
│  ║ ⚠ Couldn't load watched folders.                                          ║  │
│  ║   <error.message verbatim>                                                ║  │
│  ║                                                          [Try again ↻]    ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════╝  │
│  (border --hairline-strong, bg --surface-2, danger-tinted icon)                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

`role="alert"`, `data-testid="watched-folders-error-banner"`. Matches the precedent at `panel-domains.tsx:497-506`.

### 4. Mutation in-flight state (per row)

When the user clicks "Resync now", the button shows inline spinner + label changes to "Syncing…". Other actions in the row are disabled (`aria-disabled="true"`) until the resync completes. Toast on success: `"Resync complete. 142 files checked, 2 new, 1 updated."` (success variant). Toast on failure: error message + retry hint.

### 5. New folder being added (transient)

After clicking "+ Watch a new folder" → `modal-watch-enable` → confirm → modal closes → optimistic row insertion at top of list with "Syncing initial batch…" status. Real backend call returns; optimistic row reconciles with canonical data.

## Microcopy (exact strings)

- **Tab label (left sidebar):** "Watched folders"
- **Icon (left sidebar):** Lucide `Eye` (matches the surface's metaphor; harmonizes with other Settings tab icons)
- **Header H2:** "Watched folders"
- **Intro paragraph:** "Brain mirrors files from these folders into your knowledge base automatically. Source files are the source of truth — vault edits to watched notes are overwritten on the next sync."
- **Inline link:** "Learn how watching works ›" (right after intro, before the CTA)
- **Primary CTA:** "+ Watch a new folder"
- **Toggle ON aria-label:** `"Watch ${folder.path}"` (state: checked)
- **Toggle OFF aria-label:** `"Stop watching ${folder.path}"` (state: unchecked)
- **Row sub-line template:** `"${file_count} files · ${orphan_count} orphans · last synced ${last_sync_relative}"`
- **Zero-orphan sub-line variant:** `"${file_count} files · last synced ${last_sync_relative}"` (omit orphan count if zero — cleaner)
- **Personal-domain note:** "This folder syncs into your personal domain (privacy-railed by default)."
- **Empty-state heading:** "No folders being watched yet."
- **Empty-state body:** "Pick a folder and Brain will keep its notes in sync automatically."
- **Empty-state CTA:** "+ Watch a folder"
- **Loading state (sr-only `aria-live="polite"` announcement):** "Loading watched folders…"
- **Error banner:** "Couldn't load watched folders. <error.message>. Try again."
- **Resync success toast:** lead `"Resync complete."` msg `"${checked} files checked, ${new} new, ${updated} updated, ${marked_orphan} marked orphaned."`
- **Resync failure toast:** lead `"Resync failed."` msg from error.
- **Unwatch success toast:** lead `"Stopped watching ${folder.basename}."` msg `"Existing notes kept. ${orphan_count} orphans remain marked."`

## Interaction

- **Click row body:** no-op (no row-level navigation; the row IS the surface).
- **Click toggle:** opens `modal-watch-disable` if currently ON (confirmation gates the action); restores the toggle to ON if user cancels. If currently OFF, the toggle is hidden — re-enabling means re-watching the folder via the modal (folder paths in OFF state are essentially "ex-watched" and we remove them entirely; OFF state shouldn't exist as a transient).
- **Click "Resync now":** fires `brain_resync_folder({path})` immediately. Optimistic spinner; toast on completion.
- **Click "Open in Finder":** OS-native open via existing `Integrations` helper.
- **Click "Unwatch ×":** opens `modal-watch-disable`.
- **Click "+ Watch a new folder":** opens `modal-watch-enable` with empty path (user picks via folder picker inside the modal).
- **Tooltip on path (hover):** shows full untruncated path.
- **Tooltip on orphan count (hover):** "View 3 orphaned notes from this folder →" — click navigates to Orphans tab filtered to this folder.

## Keyboard order (per row)

1. Toggle (Switch)
2. "Include subfolders" checkbox
3. "Resync now" button
4. "Open in Finder" button
5. "Unwatch" button

Tab sequences naturally; Shift+Tab reverses. No focus traps within rows.

## Accessibility annotations

- Each row is a `<li>` inside a `<ul role="list">` (Radix doesn't require this — the wrapper does for screen-reader navigability matching `panel-domains`).
- Domain dot is decorative (`aria-hidden="true"`); the badge text carries the domain semantics.
- Toggle has explicit `aria-label` (NOT just a sibling label) so the path is read with the toggle state.
- Row sub-line has `aria-label` aggregating the metrics (`"142 files, 3 orphans, last synced 4 minutes ago"`) so screen readers announce them as a unit, not three drifting strings.
- "Last synced" timestamp uses `<time datetime="ISO8601">` so user-agent + assistive-tech localize. Relative-time text ("4 minutes ago") is the visible label; the ISO is the machine value.
- Skeleton loading state announces "Loading watched folders…" via a visually-hidden `aria-live="polite"` region; resolved list announces nothing (the list itself is enough).
- Error banner has `role="alert"` so it interrupts the screen reader.
- Resync button while syncing: `aria-busy="true"` + `aria-label="Resyncing ${folder.path}, please wait"`.

## Hand-off notes for T13 (brain-frontend-engineer)

- Add `SettingsTabId = "watched-folders"` to the union in `settings-screen.tsx`. Tab definition: `{ id: "watched-folders", label: "Watched folders", icon: Eye }`. Place in the tab array between `"domains"` and `"brain-md"` — semantically grouped with content-source settings.
- Create `panel-watched-folders.tsx` matching the `panel-domains.tsx` orchestrator pattern: own the refresh callback + error banner, delegate row rendering to `WatchedFolderRow`.
- Create `panel-watched-folders-row.tsx` matching `panel-domains-row.tsx` — pure presentation, mutations come from the parent.
- Reuse the optimistic-update + reconcile-on-error pattern from `panel-domains.tsx` (lines 395-461) for watch / unwatch / resync.
- Wire to a new `useWatchedFoldersStore` zustand store (peer to `useDomainsStore`) so cross-component consumers (topbar indicator, orphans panel) re-render in lock-step. Mirrors Plan 13 T2 single-source-of-truth lesson.
- Toast variants + microcopy strings live in this file's "Microcopy" section. Do not invent new strings; if a string seems missing, ask the user.
- Cost-estimate display in `modal-watch-enable` consumes the same backend call wired here for the row's file count — single endpoint. Plan 22 T9 outputs a `WatchedFolder.last_sync_stats` shape; consume that.
