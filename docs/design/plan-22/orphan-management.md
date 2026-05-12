# Orphan management — Settings tab mockup (Plan 22 T11 §2)

Implements per `tasks/plans/22-watched-folders-sync.md` §T13 (`panel-orphans.tsx`). New `SettingsTabId = "orphans"` slot in `settings-screen.tsx`.

## Surface intent

Orphans are vault notes whose source file disappeared (D2 mark-not-delete contract). The user adjudicates each one: restore (un-mark the orphan, the source must have come back) or delete (typed-confirm + trash). This surface is the *only* path to bulk orphan adjudication — `scope_guard` filters orphans from default queries (D2), so the user never sees them in chat / browse unless they come here.

## Why a Settings tab (not a standalone screen)

See README §"Why 'Orphans' is a Settings tab". Quick recap: Settings is where users go to fix things; orphans are a thing to fix; locating them here keeps the navigation surface minimal. The topbar indicator's orphan count + click-through provides discoverability for the "high attention" case.

## Layout (populated state, dark theme, 3 orphans grouped by source folder)

```
Settings → Orphans                                                           2 selected of 4
─────────────────────────────────────────────────────────────────────────────────────────────
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  Orphaned notes                                                                         │
│  These notes used to come from watched folders, but their source files no longer exist. │
│  Restore brings them back into your knowledge base; delete moves them to trash.         │
│                                                                                         │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│  ▾ Filter by folder:  [All folders ▾]    ▾ Filter by domain:  [All domains ▾]           │
│                                                                                         │
│  ╭─────────────────────────────────────────────────────────────────────────────────╮    │
│  │ [☑]  Selected: 2                                                                │    │
│  │      [↻ Restore selected]   [🗑 Delete selected…]   [Clear selection]           │    │
│  ╰─────────────────────────────────────────────────────────────────────────────────╯    │
│  (bulk-action bar; sticky-top when scrolling; only shown when ≥1 selected)              │
│                                                                                         │
│  ─── From /Users/chris/Notes/Research-Papers · [research] · 3 orphans  [select all] ─── │
│                                                                                         │
│  ╭─────────────────────────────────────────────────────────────────────────────────╮    │
│  │ [☑] ⚠ neural-architectures-survey-2024.md                                       │    │
│  │     Source: /Users/chris/Notes/Research-Papers/2024/neural-architectures.pdf    │    │
│  │     Orphaned 3 days ago · was last synced Tue 09:14                             │    │
│  │                                                          [↻ Restore]  [🗑 Delete]│    │
│  ╰─────────────────────────────────────────────────────────────────────────────────╯    │
│                                                                                         │
│  ╭─────────────────────────────────────────────────────────────────────────────────╮    │
│  │ [☑] ⚠ vision-transformer-followup.md                                            │    │
│  │     Source: /Users/chris/Notes/Research-Papers/2024/vision-transformer.pdf      │    │
│  │     Orphaned 3 days ago · was last synced Tue 09:14                             │    │
│  │                                                          [↻ Restore]  [🗑 Delete]│    │
│  ╰─────────────────────────────────────────────────────────────────────────────────╯    │
│                                                                                         │
│  ╭─────────────────────────────────────────────────────────────────────────────────╮    │
│  │ [ ] ⚠ rlhf-empirical-notes.md                                                   │    │
│  │     Source: /Users/chris/Notes/Research-Papers/old/rlhf-notes.md                │    │
│  │     Orphaned 11 days ago · was last synced Apr 24                               │    │
│  │                                                          [↻ Restore]  [🗑 Delete]│    │
│  ╰─────────────────────────────────────────────────────────────────────────────────╯    │
│                                                                                         │
│  ─── From /Users/chris/Documents/Work-Logs · [work] · 1 orphan  [select all] ─────────  │
│                                                                                         │
│  ╭─────────────────────────────────────────────────────────────────────────────────╮    │
│  │ [ ] ⚠ q1-planning-doc.md                                                        │    │
│  │     Source: /Users/chris/Documents/Work-Logs/2024-Q1/planning-doc.md            │    │
│  │     Orphaned 6 hours ago · was last synced Mon 16:02                            │    │
│  │                                                          [↻ Restore]  [🗑 Delete]│    │
│  ╰─────────────────────────────────────────────────────────────────────────────────╯    │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Per-row anatomy

| Element | Token / component | Purpose |
|---|---|---|
| Checkbox | shadcn `Checkbox` | Bulk-select |
| Warn icon `⚠` | Lucide `AlertTriangle`, `--warn` | Orphan badge |
| Note title | `--text`, `--ui-md`, font-weight 500 | The note's title (frontmatter `title` or slug fallback) |
| Source path | `--text-muted`, `--ui-sm`, `var(--mono)` | The last-known source path (frontmatter `source_path`) |
| Orphaned timestamp | `--text-dim`, `--ui-xs` | "Orphaned ${relative} · was last synced ${date}" |
| Restore button | `Button variant="ghost"`, `RotateCcw` icon, `--ok` accent on hover | Fires `brain_restore_orphan({note_path})` |
| Delete button | `Button variant="ghost"`, `Trash2` icon, `--danger` accent on hover | Opens `modal-orphan-delete` |

### Group separator

Each source-folder group has a `<h3>`-equivalent rule line: dashed/em-dash separator with the source path, domain badge, count, and a "select all in this group" affordance. Inspired by the Browse pane's domain grouping pattern.

### Background + container

- Rows are `--surface-1` on `--surface-0` page bg, `--hairline` border, `--r-md`, `--pad-md`.
- The bulk-action bar is `--surface-2` (slightly elevated), `--hairline-strong` border, sticky-top within the scroll container at `top: 0`.
- Group separator rules are 1px lines in `--hairline` with the metadata centered above the next row.

## States

### 1. Empty state (no orphans)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  Orphaned notes                                                                         │
│                                                                                         │
│                                                                                         │
│              ╭──────────────────────────────────────────────╮                           │
│              │                                              │                           │
│              │             [check-circle icon, 40px, --ok]  │                           │
│              │                                              │                           │
│              │      No orphaned notes.                      │                           │
│              │                                              │                           │
│              │      Every note in your vault still has a    │                           │
│              │      source file behind it. Nice work.       │                           │
│              │                                              │                           │
│              │      [View watched folders ›]                │                           │
│              ╰──────────────────────────────────────────────╯                           │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

- Empty state uses `--ok` accent (this is a *good* state to be in).
- Inline link goes back to `watched-folders-settings` for discoverability.

### 2. Loading state

Three skeleton rows + a skeleton bulk-action bar at top. Header + intro paragraph render immediately.

### 3. Error state

Inline banner mirroring `panel-domains` precedent:

```
║ ⚠ Couldn't load orphans.
║   <error.message>
║                                              [Try again ↻]
```

`role="alert"`, `data-testid="orphans-error-banner"`.

### 4. Bulk action in-flight

When user clicks "Restore selected" with 2 selected, the bulk bar shows: "Restoring 2 notes…" with spinner. Affected rows fade to 50% opacity + `aria-busy="true"`. On success, those rows animate out of the list (slide+fade, 240ms) and a toast fires. On partial failure, only the failed rows snap back to full opacity with the row's own `<div role="alert">` inline error.

### 5. Filter state (active filter)

When "Filter by folder" is set, only matching groups render. A "Showing 1 of 4 folders" indicator appears next to the filter dropdown. Clearing the filter restores all groups.

## Microcopy

- **Tab label:** "Orphans"
- **Icon (left sidebar):** Lucide `AlertTriangle`
- **Header H2:** "Orphaned notes"
- **Intro paragraph:** "These notes used to come from watched folders, but their source files no longer exist. Restore brings them back into your knowledge base; delete moves them to trash."
- **Filter labels:** "Filter by folder:" / "Filter by domain:"
- **Filter "all" option:** "All folders" / "All domains"
- **Bulk-action bar selection count:** `"Selected: ${n}"` (n ≥ 1)
- **Bulk restore CTA:** "Restore selected"
- **Bulk delete CTA:** "Delete selected…" (ellipsis signals confirmation modal)
- **Clear-selection CTA:** "Clear selection"
- **Group separator template:** `"From ${path} · ${domain-badge} · ${count} orphan${count===1?'':'s'}"`
- **Per-group select-all CTA:** "select all" (lowercase to de-emphasize)
- **Row sub-line template:** `"Source: ${source_path}"` (line 1) + `"Orphaned ${relative_time} · was last synced ${date}"` (line 2)
- **Restore button label:** "Restore"
- **Restore aria-label:** `"Restore ${note.title}"`
- **Delete button label:** "Delete"
- **Delete aria-label:** `"Delete ${note.title}"`
- **Empty-state heading:** "No orphaned notes."
- **Empty-state body:** "Every note in your vault still has a source file behind it. Nice work."
- **Empty-state link:** "View watched folders ›"
- **Error banner:** "Couldn't load orphans. <error.message>. Try again."
- **Restore success toast (single):** lead `"Note restored."` msg `"${note.title} is back in your knowledge base."`
- **Restore success toast (bulk):** lead `"${n} notes restored."` msg `"They're back in your knowledge base."`
- **Restore failure toast:** lead `"Couldn't restore."` msg from error.
- **Delete success toast (single):** lead `"Note deleted."` msg `"${note.title} moved to .brain/trash/. Undo via brain_undo_last."`
- **Delete success toast (bulk):** lead `"${n} notes deleted."` msg `"Moved to .brain/trash/. Undo via brain_undo_last."`
- **Delete failure toast:** lead `"Couldn't delete."` msg from error.

## Interaction

- **Click checkbox:** toggles selection state. If a group's per-checkbox flips all rows in the group to checked, the group "select all" affordance reflects the all-checked state.
- **Click "select all" (group):** toggles every row in that group.
- **Click "Restore" (row):** fires `brain_restore_orphan({note_path})` directly (no confirmation — restore is fully reversible by a subsequent re-orphan if the source file is missing again at next sync). Optimistic row removal; toast on success.
- **Click "Delete" (row):** opens `modal-orphan-delete` with that note prefilled.
- **Click "Restore selected" (bulk):** fires `brain_restore_orphan` per selected note (concurrent ok). Shows in-flight bar. Toast on completion with success/failure counts.
- **Click "Delete selected…" (bulk):** opens `modal-orphan-delete` in BULK MODE — typed-confirm with literal word `delete` (lowercase) + the count, e.g., "Type `delete 4 notes` to confirm". One typing exercise, batched delete. See `modal-orphan-delete.md` §Bulk mode.
- **Click "Clear selection":** unchecks all.
- **Click filter dropdown:** Radix `Select` opens; choosing applies filter immediately.

## Keyboard order

1. Filter by folder dropdown
2. Filter by domain dropdown
3. (If selected ≥1) Bulk-action bar: Restore selected → Delete selected → Clear selection
4. Per group: select-all checkbox → per-row: checkbox → Restore → Delete (then next row)

Selecting a row with `Space` checks the checkbox if focus is on it. Tab order skips into the next group naturally.

## Accessibility annotations

- The bulk-action bar uses `role="region"` with `aria-label="Bulk actions for selected orphans"` so screen readers announce its presence when it appears.
- Selection count is `aria-live="polite"` so adding / removing selections is announced.
- Group separators are real `<h3>` elements (visually rendered as the em-dash rule) so screen readers can navigate by heading.
- Each row's `aria-label` aggregates everything: `"${note.title}, orphaned from ${source_path}, ${orphaned_relative}"`.
- `Restore` and `Delete` buttons in a row are inside the same `<li>` so the row's `aria-label` provides context.
- The orphan `⚠` icon is `aria-hidden="true"`; the row's status is conveyed in the `aria-label`.
- Group separator carries a `aria-label="${count} orphans from ${path}, in ${domain} domain"` so navigating by heading announces the count.

## Hand-off notes for T13 (brain-frontend-engineer)

- Add `SettingsTabId = "orphans"` to the union. Tab def: `{ id: "orphans", label: "Orphans", icon: AlertTriangle }`. Place adjacent to `"watched-folders"`.
- Conditionally hide the tab if there are zero watched folders AND zero orphans (empty surface is unnecessary noise). Show the tab if EITHER condition is non-zero so the user can still get here when orphans accumulate and folders are unwatched.
- Wire `brain_list_orphans` (T5 tool) → display. Group by `source_folder_root` client-side from `OrphanEntry.watched_folder_id`.
- Reuse the optimistic-update + reconcile pattern from `panel-domains.tsx` for restore + delete.
- Bulk delete: open `TypedConfirmDialog` with `word="delete ${n} notes"` (literal phrase, case-sensitive) — easier to type than the slug-per-row but still mistake-proof. See `modal-orphan-delete.md` §Bulk mode for full spec.
- Selection state lives in component-local `Set<string>` — does NOT need to persist across tab switches (selection is a transient adjudication action).
- New zustand store `useOrphansStore` peer to `useWatchedFoldersStore`. Cross-store: when a folder is unwatched, its orphans remain (D2) — orphans store should NOT auto-filter them out.
