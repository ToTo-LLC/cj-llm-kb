# Plan 22 — Watched Folders: design mockups

**Status:** awaiting user approval (gates Plan 22 T12-T15 per D9).
**Author:** brain-ui-designer (T11).
**Format:** structured-text ASCII wireframes (one `.md` per surface). PNG/Figma exports are deferred — the engineer needs precise component composition + microcopy + state semantics, all of which structured text captures verbatim with no translation loss. If the user wants pixel renders for review, this README is the source-of-truth brief Figma can mirror against.

## Why ASCII wireframes (not PNG/Figma)

1. **Microcopy is the load-bearing artifact.** The watch-enable modal's overwrite-contract sentence MUST be written, reviewed, and locked verbatim — a PNG export hides typos. Per Plan 12 cross-domain-modal precedent (`docs/design/cross-domain-modal/microcopy.md`), microcopy lives in markdown and is the source of truth.
2. **Component reuse is high.** Every surface here composes existing primitives: `Modal`, `TypedConfirmDialog`, `Button`, `Switch`, `Checkbox`, `Input`, `Popover`, `Tooltip`. The mockups specify *which* primitive at *which* slot — that is more useful to the engineer than a pixel render.
3. **Token-driven theming flips automatically.** Light/dark + density variants are derived from `tokens.css` + `brand-skin.css`; specifying tokens in the mockup is enough.
4. **User adjudicates format.** The user can request revision rounds or Figma exports after reviewing the structured-text — Plan 06 set this precedent.

## Files

| File | Surface | Plan 22 reference |
|---|---|---|
| `watched-folders-settings.md` | Settings → "Watched folders" tab | T11 mockup §1, T13 implementation |
| `orphan-management.md` | Settings → "Orphans" tab | T11 mockup §2, T13 implementation |
| `topbar-status.md` | Topbar status indicator (eye icon + counts) | T11 mockup §3, T14 implementation |
| `modal-watch-enable.md` | Watch-enable confirmation modal (D1 source-canonical contract) | T11 mockup §4, T15 implementation |
| `modal-watch-disable.md` | Watch-disable confirmation modal (orphans remain marked) | T11 mockup §5, T15 implementation |
| `modal-orphan-delete.md` | Orphan typed-confirm delete modal (mirrors `brain_delete_domain`) | T11 mockup §6, T15 implementation |

## Design-system tokens reused

- **Surfaces:** `--surface-0` (page), `--surface-1` (main card), `--surface-2` (card / nested), `--surface-3` (hover), `--surface-4` (inputs).
- **Hairlines:** `--hairline` (default border), `--hairline-strong` (emphasized border, error banners).
- **Text:** `--text` (primary), `--text-muted` (helper / labels), `--text-dim` (least-emphasized — for timestamps, counts).
- **Status:** `--ok` (success / restored), `--warn` (orphan badge, watch-enable cost), `--danger` (delete CTA, error banner), `--info` (watch state idle).
- **Accent (CTAs / interactive):** `--tt-cyan` is theme-aware (Plan 14 T6: dark = `#E06A4A`, light = `#C64B2E` ember). Used for the "Watch and sync now" CTA, "Watch a new folder" CTA, and the typed-confirm slug callout. NOT used for destructive — those use `--danger` via the `Button variant="destructive"` shadcn variant.
- **Domain accents:** `--dom-research` / `--dom-work` / `--dom-personal` for domain badges next to watched folders (matches existing topbar scope chips + browse pane). User-created domains pull from `ACCENT_SWATCHES` per existing `panel-domains.tsx` pattern.
- **Spacing:** `--pad-md` (12px) for row padding, `--gap-md` (12px) inter-row, `--pad-lg` (20px) for section padding. Compact density (`[data-density="compact"]`) compresses these per existing convention.
- **Radii:** `--r-sm` (5px) for inline inputs / chips, `--r-md` (12px) for cards / modals, `--r-pill` (60px) for status pills.
- **Type:** `--ui-md` (13px) body, `--ui-sm` (12px) helper, `--ui-xs` (11px) timestamps.
- **Motion:** `--dur` (240ms) for the typed-confirm input state shift; `--ease` Bezier. Reduced-motion users still see the destructive style on a properly-typed input — the transition is decoration, not signal.

## Components reused (no new primitives)

| Existing component | Used in |
|---|---|
| `Modal` (`components/dialogs/modal.tsx`) | All 3 modals — eyebrow + title + description + footer plumbing already a11y-correct |
| `TypedConfirmDialog` (`components/dialogs/typed-confirm-dialog.tsx`) | `modal-orphan-delete` (delegate to this; do NOT reimplement) |
| `Button` (`components/ui/button.tsx`) | Every CTA; `variant="destructive"` for delete, `variant="default"` for primary, `variant="ghost"` for cancel |
| `Switch` (`components/ui/switch.tsx`) | Per-folder enable toggle in the watched-folders list |
| `Input` (`components/ui/input.tsx`) | Folder path display (readonly), typed-confirm input, slug input |
| `Checkbox` (`components/ui/checkbox.tsx`) | Bulk-select on orphans, "Include subdirectories" on watch-enable |
| `Tooltip` + `TooltipContent` + `TooltipTrigger` | Topbar status hover, orphan info tooltips |
| `Popover` | Bulk-action menu on orphans |
| Lucide icons | `Eye` (watch state), `EyeOff` (unwatched), `AlertTriangle` (orphan badge), `RotateCw` (resync), `FolderPlus` (add watched folder), `Trash2` (delete), `RefreshCw` (restore), `Folder` (path indicator) |

## New components (proposed — T13 may inline these)

- **`PanelWatchedFolders`** (Settings tab orchestrator) — analogous to `PanelDomains`.
- **`PanelOrphans`** (Settings tab orchestrator) — analogous to `PanelDomains`.
- **`WatchedFolderRow`** (per-row) — analogous to `PanelDomainsRow`.
- **`OrphanRow`** (per-row).
- **`WatchEnableModal`** — wraps `Modal` with the D1 contract body + cost-estimate display.
- **`WatchDisableModal`** — wraps `Modal` with the D2 orphan-policy explanation body.
- **`WatchedFoldersTopbarIndicator`** — small button + tooltip + popover-or-link.

`modal-orphan-delete` reuses `TypedConfirmDialog` directly (no new component).

## Accessibility plan (WCAG 2.2 AA + axe-core gate)

- **Keyboard nav:** every interactive element reachable via Tab. Focus order on each surface is documented in each mockup file (§Keyboard order). The watch-enable modal's first tabbable is the domain dropdown (NOT the "Watch and sync now" CTA — opening the modal should land focus on the first input the user might edit, not on the destructive-adjacent confirm). Per Plan 14 D2: `Esc` closes any open modal; `Enter` only submits when focus is in a form field, not when focus is on the destructive CTA (which requires an explicit click or Space).
- **Screen reader labels:**
  - Per-row toggle: `aria-label="Watch ${folder.path}"` / `aria-label="Stop watching ${folder.path}"`.
  - Bulk-select checkbox: `aria-label="Select ${count} orphans"` / `aria-label="Deselect all orphans"`.
  - Topbar indicator: `aria-label="${watchedCount} folders watched, ${orphanCount} orphaned notes"`.
  - Status badges (orphan count): `role="status"` so screen readers announce updates without interruption.
- **Color contrast (axe AA gate):** every text-on-surface pair clears 4.5:1 small / 3:1 large. The orphan warning badge uses `--warn` (`#FDEB9E` on dark `#1A1A1A` = 12.9:1; on light `#FAFAF8` the badge inverts to `--danger` text on `--warn`-soft background for 5.2:1). Delete CTA uses `--danger` background + white text (8.4:1 dark, mirrored light). Verified against existing `panel-domains.tsx` precedent which passed Plan 13 T6 a11y nudges.
- **Reduced motion:** the typed-confirm input's color shift on valid match honors `prefers-reduced-motion: reduce` by snapping instead of transitioning (existing `Input` component handles this).
- **Radix dialog animation gotcha (per auto-memory):** axe runs in playwright e2e must `waitForAnimationsToFinish(page, "[role='dialog']")` before scanning — Radix dialogs hold mid-animation opacity that fails color-contrast until animation completes. Tests already use the helper at `apps/brain_web/tests/e2e/_helpers.ts`.
- **Typed-confirm input:** mirrors `TypedConfirmDialog` — `autoFocus`, case-sensitive match, danger-variant button until exact match. `aria-describedby` points to the body sentence explaining what the typed word does.

## Microcopy summary (full strings live in each mockup file)

| Surface | Critical microcopy excerpt |
|---|---|
| Watched folders settings empty state | "No folders being watched yet. Pick a folder and Brain will keep its notes in sync automatically." |
| Watch-enable modal title | "Watch this folder for changes" |
| Watch-enable modal D1 contract paragraph | "**Heads-up:** the source file is the source of truth. If you edit a note from this folder inside your vault, your edits will be overwritten the next time the source file changes." |
| Watch-disable modal title | "Stop watching <folder>?" |
| Watch-disable modal body | "Brain will leave the existing notes alone — nothing is deleted. Notes already marked as orphans stay marked. You can start watching this folder again any time." |
| Orphan-delete modal title | "Delete <note-title>?" |
| Orphan-delete modal D2 explanation | "The source file for this note no longer exists. Deleting moves the note to your vault's trash; you can restore it from `~/Documents/brain/.brain/trash/` within 30 days, or undo this with `brain_undo_last`." |
| Topbar indicator tooltip | "3 folders watched · 2 orphaned notes need attention" |

## Design rationale

### Why "Orphans" is a Settings tab (not a standalone screen)

**Decision:** Orphans live as a new Settings tab (`Settings → Orphans`), not as a standalone top-level nav item.

**Trade-off considered:** A standalone "Library" / "Vault health" top-level nav surface would give orphans more visibility, but it also adds a navigation surface for a low-frequency action. Settings is where users go to fix things; orphans are a thing to fix; the location is correct. The topbar status indicator (with its count badge) handles discoverability for the "high-attention" case where orphans accumulate.

**Why not split orphans between a tab AND a standalone screen?** Two surfaces = two paths to drift. Single source of truth.

### Why the topbar indicator shows two counts (watched + orphans), not one

**Decision:** `[eye icon] 3 / [alert icon] 2` — two distinct numbers, two distinct affordances.

**Trade-off considered:** A single "vault health" badge (e.g., "5 items") would be tidier but obscures the actionable distinction: "3 folders watched" is FYI (positive state), "2 orphans" is a call-to-action (needs adjudication). Splitting them lets the orphan count visually use `--warn` while the watch count uses neutral text, so the user's eye lands on what needs attention. Matches the Plan 12 topbar precedent of using color + count for the cross-domain badge.

### Why "Watch and sync now" instead of "Watch this folder"

**Decision:** the primary CTA on the watch-enable modal is "**Watch and sync now**", not "Watch this folder".

**Trade-off considered:** "Watch this folder" is shorter and matches the title. But the action does TWO things — register the folder in the watcher AND perform an initial full sync (per T7 watcher contract) — and users deserve to know the second one before they click. "Sync now" prepares them for the cost-estimate spend (which is also displayed inline). The CTA's verb does what the cost meter implies it does.

### Why source-canonical overwrite contract gets a callout box (not a fine-print line)

**Decision:** D1's "vault edits are lost" warning is rendered as a dedicated info-callout box with the `--warn` icon, not as one of three bullets in the body.

**Trade-off considered:** Burying it as a bullet (less alarming) vs. surfacing it as a callout (clearer trust signal). CLAUDE.md non-negotiable #9 says "Non-technical usability is a requirement. ... Every destructive action requires typed confirmation." Vault overwrite is destructive to user edits, even if the action that triggered it (a source file change) is automatic and silent. The callout box matches the precedent set by `cross-domain-modal` for warnings the user must internalize before opting in.

### Why the orphan typed-confirm uses the slug (not "DELETE")

**Decision:** `modal-orphan-delete` requires the user to type the **note slug**, mirroring `brain_delete_domain` precedent.

**Trade-off considered:** Typing "DELETE" is faster but less mistake-proof (one screen of "DELETE" muscle-memory could blast through several modals). Typing the slug means each delete is a distinct typing exercise, which is exactly the friction we want for a destructive action that consumes 30 seconds of attention. Plan 11 T7 set this precedent for domain deletion; orphan deletion mirrors it.

## Open questions for user review

1. **Topbar indicator placement:** the mockup puts the indicator left of the scope chip (right side of topbar). Confirm placement vs. left side near brand chip.
2. **Cost estimate display in watch-enable modal:** mockup shows it as a `--warn`-tinted inline panel with file count + $ estimate. Alternative: show only on hover/click of an "Estimate cost" link. Recommendation = inline (transparency-by-default).
3. **Resync action confirmation:** does forcing a full re-sync need its own modal, or is the inline "Resync" button + immediate fire okay? Mockup omits a confirm modal (resync is idempotent + non-destructive). Confirm.
4. **Bulk-restore vs. bulk-delete on orphans:** bulk-restore is one click (no typed-confirm — restore is undo-able). Bulk-delete fires `TypedConfirmDialog` once with the count + word `delete` (or per-orphan typed-confirm, which is more friction). Mockup shows the single typed-confirm-with-count pattern. Confirm.
5. **Cost estimate source:** the watch-enable cost estimate needs a backend endpoint (T9 has the math). Mockup assumes a `brain_estimate_watch_cost` or similar — Plan 22 may inline this in `brain_watch_folder` as a `dry_run` arg. Frontend implementer to confirm wiring at T15.

## Commit hygiene

Per plan-22 §T11: commit at task-close. Mockup files land under `docs/design/plan-22/` and do not affect runtime — single commit covers all six mockup files + README.
