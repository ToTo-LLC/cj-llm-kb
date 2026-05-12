# Orphan typed-confirm delete modal mockup (Plan 22 T11 §6)

Implements per `tasks/plans/22-watched-folders-sync.md` §T15. **REUSES existing `TypedConfirmDialog`** (`components/dialogs/typed-confirm-dialog.tsx`) — does NOT introduce a new modal component. Same precedent as `brain_delete_domain` (`panel-domains.tsx` line 395-461).

## Surface intent

The user is about to permanently move an orphaned note's vault file to `.brain/trash/`. The action is technically reversible (trash retains 30 days, `brain_undo_last` reverts the move) but it's destructive enough that mistake-proofing is required. Typed-confirm with the note's slug guarantees the user is committing to THIS specific note, not muscle-memory-clicking through a list.

## Why typed-confirm with the slug (not "DELETE")

See README §"Why the orphan typed-confirm uses the slug". Quick recap: typing "DELETE" once teaches muscle memory; typing each note's unique slug is a distinct typing exercise that thwarts the muscle-memory case. Domain delete (Plan 11 T7) set this precedent.

## Layout (single-note mode)

```
                ╭───────────────────────────────────────────────────────╮
                │  ORPHAN MANAGEMENT                                    │  ← eyebrow
                │                                                       │
                │  Delete this orphaned note?                           │  ← DialogTitle
                │                                                       │
                ├───────────────────────────────────────────────────────┤
                │                                                       │
                │  ┌─────────────────────────────────────────────────┐  │  ← note-card,
                │  │ ⚠  neural-architectures-survey-2024.md          │  │     --surface-2 bg,
                │  │     research/neural-architectures-survey-...md  │  │     --hairline border
                │  │     Source: …/Research-Papers/2024/neural-      │  │
                │  │     architectures.pdf (no longer exists)        │  │
                │  └─────────────────────────────────────────────────┘  │
                │                                                       │
                │  The source file for this note no longer exists.      │  ← body, --text, --ui-md
                │  Deleting moves the note to your vault's trash.       │
                │                                                       │
                │  You can restore it from                              │
                │  ~/Documents/brain/.brain/trash/ within 30 days, or   │
                │  undo this with brain_undo_last.                      │
                │                                                       │
                ├───────────────────────────────────────────────────────┤
                │                                                       │
                │  TYPE neural-architectures-survey-2024 TO CONFIRM     │  ← uppercase label,
                │                                                       │     slug in --tt-cyan mono
                │  ┌─────────────────────────────────────────────────┐  │
                │  │ neural-architectures-survey-2024_               │  │  ← input, autofocus,
                │  └─────────────────────────────────────────────────┘  │     value shown matches → ok state
                │                                                       │
                ├───────────────────────────────────────────────────────┤
                │                                                       │
                │                       [Cancel]  [Delete permanently]  │  ← DialogFooter
                │                                                       │     Cancel ghost,
                │                                                       │     Delete = destructive variant
                │                                                       │     (red, --danger)
                ╰───────────────────────────────────────────────────────╯
                Modal max-width: 480px (matches TypedConfirmDialog default).
```

### Anatomy

| Element | Token / component | Purpose |
|---|---|---|
| Modal shell | `Modal` via `TypedConfirmDialog` | Plumbing |
| Note card | Custom `<div>`, `--surface-2`, `--hairline`, `--r-md` | Identifies the note being deleted |
| Warn icon | Lucide `AlertTriangle`, 16px, `--warn` | Orphan badge |
| Note title | `--text`, font-weight 500 | Title from frontmatter |
| Vault path | `--text-muted`, `--ui-sm`, `var(--mono)` | Relative path in vault |
| Source line | `--text-dim`, `--ui-sm`, `var(--mono)` | Last-known source path |
| Body explanation | `--text`, `--ui-md`, line-height 1.5 | Plain English what's about to happen |
| Restore hint | `--text-muted`, `--ui-sm` | Names the recovery paths |
| Typed-confirm label | `--text-muted`, `--ui-xs`, uppercase, letter-spaced | Mirrors `TypedConfirmDialog` |
| Slug in label | `--tt-cyan`, `var(--mono)` | The exact word the user must type |
| Input | shadcn `Input`, `tracking-wider` | The typing surface |
| Cancel button | `Button variant="ghost"` | No commitment |
| Delete button | `Button variant="destructive"` (`--danger` bg) | Until input matches, DISABLED |

## States

### 1. Default state (mount)

- Input is empty. Confirm button DISABLED.
- "Delete permanently" button reads — but stays disabled — until input EQUALS the slug exactly (case-sensitive).
- This is the existing `TypedConfirmDialog` behavior; no changes.

### 2. Input partially typed

- Confirm button stays DISABLED.
- No visible error (don't shame the user mid-type).

### 3. Input matches exactly

- Confirm button ENABLES with subtle 240ms color shift to `--danger` saturation.
- Reduced-motion: snap, no transition.

### 4. Confirm in-flight

- Confirm button shows spinner + label "Deleting…". Input disabled. Cancel still works (cancels the in-flight backend call via AbortController if implemented).
- On success: toast `"Note deleted."` msg `"${note.title} moved to .brain/trash/. Undo via brain_undo_last."`
- On failure: toast `"Couldn't delete."` msg from error. Modal stays open with the typed-confirm input still valid so user can retry.

## Layout (BULK mode — N > 1 orphans selected from `panel-orphans`)

When the user invokes "Delete selected…" from the orphan-management bulk action bar, this same modal opens with N orphans:

```
                ╭───────────────────────────────────────────────────────╮
                │  ORPHAN MANAGEMENT                                    │
                │                                                       │
                │  Delete 4 orphaned notes?                             │  ← N count in title
                │                                                       │
                ├───────────────────────────────────────────────────────┤
                │                                                       │
                │  ┌─────────────────────────────────────────────────┐  │
                │  │ ⚠  4 orphans selected:                          │  │  ← compact summary card
                │  │   • neural-architectures-survey-2024.md         │  │     up to 5 names, then
                │  │   • vision-transformer-followup.md              │  │     "...and N more"
                │  │   • rlhf-empirical-notes.md                     │  │
                │  │   • q1-planning-doc.md                          │  │
                │  └─────────────────────────────────────────────────┘  │
                │                                                       │
                │  The source files for these notes no longer exist.    │
                │  Deleting moves them to your vault's trash.           │
                │                                                       │
                │  You can restore each one from                        │
                │  ~/Documents/brain/.brain/trash/ within 30 days, or   │
                │  undo the whole batch with brain_undo_last.           │
                │                                                       │
                ├───────────────────────────────────────────────────────┤
                │                                                       │
                │  TYPE delete 4 notes TO CONFIRM                       │  ← literal phrase
                │                                                       │
                │  ┌─────────────────────────────────────────────────┐  │
                │  │ delete 4 notes_                                 │  │
                │  └─────────────────────────────────────────────────┘  │
                │                                                       │
                ├───────────────────────────────────────────────────────┤
                │                                                       │
                │                       [Cancel]  [Delete permanently]  │
                ╰───────────────────────────────────────────────────────╯
```

- **Typed phrase:** `"delete N notes"` (lowercase, where N is the count). Singular form `"delete 1 note"` for N=1 (though single-note flow normally uses single-note mode above).
- All other anatomy + states identical.
- Backend: parent iterates `brain_delete_orphan({note_path, typed_confirm: true})` over the selection. Failures are collected and surfaced as a partial-success toast.

## Microcopy (exact strings)

### Single-note mode

- **Eyebrow:** "ORPHAN MANAGEMENT"
- **Title:** "Delete this orphaned note?"
- **Note card title:** `${note.title}`
- **Note card vault path:** `${note.path_in_vault}`
- **Note card source line:** `"Source: ${last_known_source_path} (no longer exists)"`
- **Body:** "The source file for this note no longer exists. Deleting moves the note to your vault's trash."
- **Restore hint:** "You can restore it from `~/Documents/brain/.brain/trash/` within 30 days, or undo this with `brain_undo_last`."
- **Typed-confirm label:** `"TYPE ${note.slug} TO CONFIRM"` (slug rendered inline in `--tt-cyan` mono; mirrors `TypedConfirmDialog` line 73-75)
- **Confirm button (default):** "Delete permanently"
- **Confirm button (in-flight):** "Deleting…"
- **Cancel button:** "Cancel"
- **Success toast lead:** "Note deleted."
- **Success toast msg:** `"${note.title} moved to .brain/trash/. Undo via brain_undo_last."`
- **Failure toast lead:** "Couldn't delete."

### Bulk mode

- **Title:** `"Delete ${N} orphaned notes?"`
- **Note card summary:** `"${N} orphans selected:"` followed by `<ul>` of up to 5 slugs (`--ui-sm`); if N>5, append `"…and ${N - 5} more"` as a final `<li>` in `--text-dim`.
- **Body:** `"The source files for these notes no longer exist. Deleting moves them to your vault's trash."`
- **Restore hint:** `"You can restore each one from ~/Documents/brain/.brain/trash/ within 30 days, or undo the whole batch with brain_undo_last."`
- **Typed-confirm label:** `"TYPE delete ${N} notes TO CONFIRM"` (entire phrase in `--tt-cyan` mono)
- **Confirm button (in-flight):** `"Deleting ${N} notes…"`
- **Success toast lead (all succeeded):** `"${N} notes deleted."`
- **Success toast msg:** "Moved to `.brain/trash/`. Undo via `brain_undo_last`."
- **Partial-success toast lead:** `"${ok} of ${N} notes deleted."`
- **Partial-success toast msg:** `"${failed} failed. <first error.message>"`

## Interaction

- **Mount → focus:** the typed-confirm input (autoFocus, matches `TypedConfirmDialog` precedent).
- **Type matching slug:** confirm button enables in real-time.
- **Cancel / Esc / backdrop click:** close modal, no commitment.
- **Confirm:** fires `brain_delete_orphan({note_path, typed_confirm: true})` (single) or N concurrent / batched calls (bulk).
- **Mistype during typing:** no instant error — friction during exploration is rude. Match-or-not state is conveyed by the button's enabled/disabled state.

## Keyboard order

1. Typed-confirm input (autofocus)
2. Cancel button
3. Delete permanently button (only navigable via Tab once input is filled — but `disabled` doesn't block Tab; it blocks Activate)

Esc closes from any focus position. Enter inside the input does NOT auto-submit unless input matches; if input matches AND user presses Enter, fires Delete (matches `TypedConfirmDialog`'s native form-submit behavior).

## Accessibility annotations

- The typed-confirm label has `htmlFor` pointing to the input id (Radix-generated). Screen readers announce the input with its full context.
- Slug in the label is wrapped in `<code>` element matching `TypedConfirmDialog` precedent (line 74) — already gives screen readers a "code" semantic so the slug isn't read as a typo.
- Note card has `role="group"` with `aria-label="Orphan to be deleted: ${note.title}"`.
- `--danger` button background + white text: 8.4:1 dark / 8.7:1 light — both clear AA 4.5:1 and AAA 7:1.
- The `(no longer exists)` parenthetical in the source line is rendered inline — screen readers read it naturally.
- For bulk mode, the orphan-list `<ul>` has `aria-label="${N} orphans selected for deletion"`.
- Input has `tracking-wider` style (existing class) for visual distinctiveness — does NOT affect screen-reader voicing.

## Implementation guidance for T15

**Single-note mode:** the existing `TypedConfirmDialog` already does 90% of this. Open it with:

```ts
openDialog({
  kind: "typed-confirm",
  eyebrow: "ORPHAN MANAGEMENT",
  title: `Delete this orphaned note?`,
  body: `The source file for this note no longer exists. Deleting moves the note to your vault's trash. You can restore it from ~/Documents/brain/.brain/trash/ within 30 days, or undo this with brain_undo_last.`,
  word: note.slug,
  danger: true,
  onConfirm: async () => {
    await brainDeleteOrphan({ note_path: note.path, typed_confirm: true });
    // optimistic + toast pattern matches panel-domains delete flow
  },
});
```

The note-card header (with warn icon + title + source line) is the only piece `TypedConfirmDialog` doesn't natively support. **Recommendation:** extend `TypedConfirmDialog` to accept an optional `headerSlot: React.ReactNode` prop, OR create a thin wrapper `OrphanDeleteDialog` that composes `Modal` directly with the same input-state logic copied. The first option is cheaper (one prop addition, zero behavior change) and benefits any future dialog that wants a header card. Confirm with engineer at T15.

**Bulk mode:** `TypedConfirmDialog` already supports custom `word` — pass `word="delete ${N} notes"`. The bulk-summary card requires the same `headerSlot` extension recommendation.

**Confirm button label:** `TypedConfirmDialog` currently renders `"Delete permanently"` when `danger=true` (line 67) — matches this spec exactly. No new translation needed.

Cross-store: after success, `useOrphansStore.refresh()` reconciles. The orphan disappears from `panel-orphans`. If the orphan was the last one for a folder, the folder's orphan count in `panel-watched-folders` drops to zero — invalidate that store too.
