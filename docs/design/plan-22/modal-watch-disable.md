# Watch-disable confirmation modal mockup (Plan 22 T11 §5)

Implements per `tasks/plans/22-watched-folders-sync.md` §T15. New component `WatchDisableModal` wraps `Modal`.

## Surface intent

The user is about to unwatch a folder. The action is reversible (they can re-enable later) but has two consequences the user should know:
1. **Existing notes stay** — Brain doesn't delete the imported notes when you stop watching.
2. **Orphans stay marked** — any notes already marked orphan (from prior source deletions) remain marked; the user adjudicates them separately via Settings → Orphans.

This is a confirmation modal, NOT a typed-confirm. The action is reversible — typing is friction that's only justified when undo is hard (D2 explicit guidance about typed-confirm for destructive actions).

## Layout

```
                ╭───────────────────────────────────────────────────────╮
                │  WATCHED FOLDERS                                      │  ← eyebrow
                │                                                       │
                │  Stop watching this folder?                           │  ← DialogTitle
                │                                                       │
                │  /Users/chris/Notes/Research-Papers                   │  ← path, --mono, --text-muted
                │                                                       │
                ├───────────────────────────────────────────────────────┤
                │                                                       │
                │  Brain will stop monitoring this folder for changes.  │  ← body, --text, --ui-md
                │                                                       │
                │  Here's what stays the same:                          │  ← --text-muted, --ui-sm
                │                                                       │
                │     ✓  Existing notes from this folder stay in your   │  ← --ok check icon
                │        knowledge base.                                │
                │                                                       │
                │     ✓  Notes already marked as orphans stay marked.   │
                │        You can review them in Settings → Orphans.     │
                │                                                       │
                │     ✓  You can start watching this folder again any   │
                │        time.                                          │
                │                                                       │
                │  Here's what changes:                                 │  ← --text-muted, --ui-sm
                │                                                       │
                │     →  New or edited source files won't sync.         │  ← arrow indicator (Lucide ArrowRight)
                │                                                       │
                │     →  Deleted source files won't mark new orphans.   │
                │                                                       │
                ├───────────────────────────────────────────────────────┤
                │                                                       │
                │   ⓘ The folder's 3 orphans from earlier deletions    │  ← --info-tinted inline note,
                │     will still be there. Manage them in Settings →    │     conditional render
                │     Orphans.                                         │
                │                                                       │
                ├───────────────────────────────────────────────────────┤
                │                                                       │
                │                          [Cancel]  [Stop watching]    │  ← DialogFooter
                │                                                       │     Cancel ghost,
                │                                                       │     Stop watching = default
                │                                                       │     (NOT destructive variant —
                │                                                       │      this is reversible)
                ╰───────────────────────────────────────────────────────╯
                Modal max-width: 480px
```

### Anatomy

| Element | Token / component | Purpose |
|---|---|---|
| Modal shell | `Modal` from `components/dialogs/modal.tsx` | Plumbing |
| Path display | `--mono`, `--text-muted`, `--ui-sm`, `--surface-2` bg, `--r-sm`, `--pad-sm` | The folder being unwatched |
| "What stays" section | `<ul>` with check icons | Reassurance |
| "What changes" section | `<ul>` with arrow icons | Honest description of what stops |
| Check icon `✓` | Lucide `Check`, 14px, `--ok` | "Good news / no change" |
| Arrow icon `→` | Lucide `ArrowRight`, 14px, `--text-muted` | "This is what shifts" |
| Conditional orphan-count note | `<div>` with `--info` accent border-l 3px, `--surface-2` bg | Only renders if `folder.orphan_count > 0` |
| Cancel button | `Button variant="ghost"` | No commitment |
| Confirm button | `Button variant="default"` (NOT destructive) | Reversible action |

## States

### 1. Default state (no orphans associated)

As above, BUT the "ⓘ The folder's N orphans…" inline note is OMITTED. The body lists 3 "stays" + 2 "changes" bullets without the orphan-specific callout.

### 2. Folder has orphans

Renders the `--info` callout inline note with the orphan count. Microcopy: `"ⓘ The folder's ${N} orphan${N===1?'':'s'} from earlier deletions will still be there. Manage them in Settings → Orphans."`

### 3. Confirm in-flight

- Confirm button shows spinner + label "Stopping…". Inputs disabled. Esc still cancels.
- Toast (success): `"Stopped watching ${folder.basename}."` msg `"Existing notes kept. ${orphan_count} orphans remain marked."`
- Toast (failure): `"Couldn't stop watching."` msg from error.

## Microcopy (exact strings)

- **Eyebrow:** "WATCHED FOLDERS"
- **Title:** "Stop watching this folder?"
- **Path display (just renders the path verbatim):** `${folder.path}` in mono
- **DialogDescription (visible):** "Brain will stop monitoring this folder for changes."
- **"Stays" heading:** "Here's what stays the same:"
- **Stays bullet 1:** "Existing notes from this folder stay in your knowledge base."
- **Stays bullet 2:** "Notes already marked as orphans stay marked. You can review them in Settings → Orphans."
- **Stays bullet 3:** "You can start watching this folder again any time."
- **"Changes" heading:** "Here's what changes:"
- **Changes bullet 1:** "New or edited source files won't sync."
- **Changes bullet 2:** "Deleted source files won't mark new orphans."
- **Orphan-count info-line (conditional):** `"ⓘ The folder's ${N} orphan${N===1?'':'s'} from earlier deletions will still be there. Manage them in Settings → Orphans."`
- **Cancel button:** "Cancel"
- **Confirm button (default):** "Stop watching"
- **Confirm button (in-flight):** "Stopping…"
- **Success toast lead:** `"Stopped watching ${folder.basename}."`
- **Success toast msg:** `"Existing notes kept. ${orphan_count} orphans remain marked."`
- **Failure toast lead:** "Couldn't stop watching."

## Microcopy choice rationale

### "Stop watching" vs alternatives

- **"Stop watching"** wins over "Unwatch" because "unwatch" is jargon-y / Twitter-y. "Stop watching" is a direct verb phrase in plain English.
- Wins over "Disable" because "disable" is engineer-speak. Users understand "stop watching" intuitively.

### "Here's what stays" / "Here's what changes" pattern

- Mirrors the D2 contract: the user needs to know what DOESN'T disappear (their notes) and what DOES change (new sync events). Splitting into two columns of mental-model would feel like a comparison; splitting into "stays" + "changes" feels like a friendly conversation.
- Each bullet is concrete + non-technical. No "the watcher will deregister from the observer pool" — that's an implementation detail.

### Why no typed-confirm

- The action is REVERSIBLE — the user can re-enable watching from the same Settings tab. There's no irreversibly-lost data.
- Typed-confirm is friction reserved for actions where undo is HARD (delete domain, delete note, restore backup).
- A confirmation modal with a clear "what stays / what changes" body is enough to prevent the accidental-click case.

### Why the confirm button is NOT destructive variant

- D2 contract: orphans stay marked, existing notes stay. Nothing is deleted.
- The destructive variant (red) primes the user to expect loss — false alarm.
- Default variant (`--tt-cyan` / theme-aware) is the right cue: a deliberate but non-destructive action.

## Interaction

- **Mount → focus:** the "Cancel" button is the first tabbable (safer default; user can confirm via Tab → Enter if intentional).
- **Cancel / Esc / backdrop click:** close modal, no commitment.
- **Confirm button:** fires `brain_unwatch_folder({path})` → handles in-flight + completion. Modal closes on success.

## Keyboard order

1. Cancel button
2. Stop watching button

(Esc closes from any focus position.)

## Accessibility annotations

- "Stays" and "Changes" headings are `<h4>` elements (Modal already provides `<h2>`-equivalent for the title via Radix `DialogTitle`).
- Bullet lists are real `<ul>` + `<li>` so screen-reader navigation by list works.
- Check icon and arrow icon are `aria-hidden="true"` — the bullet text carries semantics.
- Conditional orphan-count info-line has `role="note"` and `aria-label="Orphan notice: ${N} orphans from earlier deletions remain"`.
- The default-focus on Cancel is a safety design — accidental-Enter on modal mount cancels rather than confirming.

## Implementation guidance for T15

- Compose: `<Modal width={480} ...>...</Modal>`.
- Parent invokes via `useDialogsStore.open({kind: "watch-disable", folder})`.
- Backend call: `brain_unwatch_folder({path: folder.path})`. Returns the updated state (no folder, orphan-count unchanged).
- After successful unwatch, the parent `panel-watched-folders.tsx` removes the row optimistically + toasts.
- Cross-store: `useWatchedFoldersStore.refresh()` after success; `useOrphansStore` doesn't need to change (orphans stay marked per D2).
