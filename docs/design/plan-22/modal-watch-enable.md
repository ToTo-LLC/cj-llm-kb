# Watch-enable confirmation modal mockup (Plan 22 T11 §4)

Implements per `tasks/plans/22-watched-folders-sync.md` §T15. New component `WatchEnableModal` wraps `Modal` (`components/dialogs/modal.tsx`).

## Surface intent

The user is about to opt their vault into a fundamentally new contract: **the source file is canonical, the vault note is a mirror**. This modal is the explicit consent step. The D1 overwrite-contract paragraph is the most important sentence in this entire feature surface — it MUST be clearly visible, in plain English, with no jargon. If the user doesn't understand this paragraph, the feature will surprise them later (a lost vault edit, a deleted note appearing orphaned).

Also doubles as the "Watch from Bulk Import" CTA destination per D6 — pre-fills folder + domain when arriving from a successful bulk-import flow.

## Layout (default — opened from Settings, empty path, all states visible)

```
                ╭───────────────────────────────────────────────────────╮
                │  WATCHED FOLDERS                                      │  ← eyebrow, --text-muted, uppercase
                │                                                       │
                │  Watch this folder for changes                        │  ← DialogTitle, --text, h3 weight
                │                                                       │
                │  Brain will mirror this folder's files into your      │  ← DialogDescription (visible)
                │  knowledge base and keep them in sync automatically.  │     --text-muted, --ui-md
                │                                                       │
                ├───────────────────────────────────────────────────────┤
                │                                                       │
                │  Folder                                               │
                │  ┌─────────────────────────────────────────────────┐  │
                │  │ /Users/chris/Notes/Research-Papers              │  │  ← Input readonly + Browse button
                │  │                                  [Choose folder]│  │     Click "Choose folder" opens
                │  └─────────────────────────────────────────────────┘  │     native folder picker
                │                                                       │
                │  Domain                                               │
                │  ┌─────────────────────────────────────────────────┐  │
                │  │ research                                     ▾  │  │  ← Select dropdown of user's domains
                │  └─────────────────────────────────────────────────┘  │
                │                                                       │
                │  [☑] Include subfolders                               │  ← Checkbox, default checked
                │                                                       │
                ├───────────────────────────────────────────────────────┤
                │                                                       │
                │  ╔═══════════════════════════════════════════════════╗│
                │  ║ ⚠  Heads-up: the source file is the source of    ║│  ← --warn-tinted callout box
                │  ║    truth. If you edit a note from this folder    ║│     border-l 3px --warn,
                │  ║    inside your vault, your edits will be         ║│     bg --surface-2,
                │  ║    overwritten the next time the source file     ║│     --text body, --warn icon
                │  ║    changes.                                      ║│
                │  ║                                                  ║│
                │  ║    Deleting a source file marks its note as an   ║│
                │  ║    orphan in your vault (it isn't deleted).      ║│
                │  ║    You can review orphans in Settings → Orphans. ║│
                │  ╚═══════════════════════════════════════════════════╝│
                │                                                       │
                ├───────────────────────────────────────────────────────┤
                │                                                       │
                │  ┌─ Initial sync ─────────────────────────────────┐   │  ← Cost-estimate panel,
                │  │ 142 files found · estimated cost ~$0.18         │   │     --surface-2 bg, --hairline border
                │  │ ⓘ Pulls in all .md / .pdf / .docx files now.   │   │     --text-muted helper
                │  └─────────────────────────────────────────────────┘   │
                │                                                       │
                ├───────────────────────────────────────────────────────┤
                │                                                       │
                │                              [Cancel]  [Watch and    │  ← DialogFooter
                │                                       sync now]      │     "Cancel" ghost, "Watch and sync
                │                                                       │     now" default + --tt-cyan accent
                ╰───────────────────────────────────────────────────────╯
                Modal max-width: 560px (slightly wider than default 520px
                to fit the warn-callout body without word-breaks).
```

### Anatomy

| Element | Token / component | Purpose |
|---|---|---|
| Modal shell | `Modal` from `components/dialogs/modal.tsx` | Eyebrow + title + description + footer plumbing |
| Eyebrow | `text-xs uppercase tracking-wider text-muted-foreground` (already in Modal) | Context label |
| Folder input + button | shadcn `Input readOnly` + `Button variant="outline"` | OS-native folder picker |
| Domain dropdown | shadcn `Select` | List of user's domains (default = active domain or domain detected from path) |
| "Include subfolders" | shadcn `Checkbox`, default checked | Maps to `recursive: true` arg of `brain_watch_folder` |
| Warn callout | Custom `<div>` with `--warn` left border, `--surface-2` bg, `--r-md` radius | The D1 source-canonical contract — the load-bearing UX moment |
| Warn callout icon | Lucide `AlertTriangle`, 18px, `--warn` color | Visual cue |
| Cost-estimate panel | Custom `<div>`, `--surface-2`, `--hairline`, `--r-md`, `--pad-md` | Transparency-by-default cost display |
| Cancel button | `Button variant="ghost"` | No commitment |
| Confirm button | `Button variant="default"`, primary `--tt-cyan` accent | "Watch and sync now" — verb does what cost meter implies |

## States

### 1. Default state (Settings entry, empty path)

- Folder input is empty placeholder: `"Choose a folder to watch…"`.
- Domain dropdown defaults to the currently-active domain.
- "Include subfolders" checkbox checked.
- Cost-estimate panel hidden (no folder chosen).
- "Watch and sync now" button DISABLED until a folder is selected.

### 2. Folder chosen (cost estimate fetched)

- Folder input shows path.
- Cost-estimate panel populated: `"${file_count} files found · estimated cost ~$${cost}"`.
- Helper line: `"ⓘ Pulls in all .md / .pdf / .docx files now."` (lists actual extensions from `IngestRouter` config).
- Confirm button ENABLED.

### 3. Cost estimate in-flight

- Folder is chosen.
- Cost-estimate panel shows skeleton: `"Estimating cost…"` with subtle spinner.
- Confirm button DISABLED with `aria-busy="true"` and label "Estimating…".
- Esc still cancels.

### 4. Cost estimate error

- Cost-estimate panel shows: `"⚠ Couldn't estimate cost. You can still watch this folder; sync will run with normal budget caps."`
- Confirm button ENABLED (don't block the user on a non-critical estimate).
- Inline retry link: `"[Try again]"` re-fires the estimate.

### 5. Pre-filled from Bulk Import (D6)

- Folder input PREFILLED with the bulk-imported folder.
- Domain dropdown PREFILLED with the detected domain.
- Eyebrow becomes `"BULK IMPORT → WATCH"` to signal continuity.
- Title becomes `"Watch this folder for ongoing changes"` (slightly different framing — user already saw the bulk-import success screen).
- All other states identical.
- Helper line under cost-estimate: `"ⓘ Your initial import already covered these files. Watching means future changes sync automatically."` (don't double-charge the user mentally).

### 6. Folder is already watched

- If the user picks a path that already has a `WatchedFolder` entry, validation error appears inline below the folder input:
- `"⚠ This folder is already being watched. Choose a different folder or manage it in Settings → Watched folders."`
- Confirm button DISABLED.

### 7. Folder is in a privacy-railed domain

- When the domain dropdown selection is railed (default: `personal`), an extra info-line appears below the domain dropdown:
- `"ⓘ Notes from this folder will be in your ${domain} domain (privacy-railed by default — they won't appear in default chat scope)."`
- Tone: factual, not warning.

### 8. Confirm in-flight

- After clicking "Watch and sync now": button shows spinner + label "Setting up watch…". All inputs disabled.
- Modal stays open until the backend response (the initial sync runs async — modal closes once `brain_watch_folder` returns the new `WatchedFolder` entry, with the initial-sync progress surfacing via a toast).
- Toast (success, lead): `"Watching ${folder.basename}."` msg `"Initial sync running — ${file_count} files. Track progress in Settings → Watched folders."`
- Toast (failure): `"Couldn't watch folder."` msg from error.

## Microcopy (exact strings — the load-bearing copy)

- **Eyebrow:** "WATCHED FOLDERS" (default) / "BULK IMPORT → WATCH" (Bulk Import entry)
- **Title:** "Watch this folder for changes" (default) / "Watch this folder for ongoing changes" (Bulk Import entry)
- **DialogDescription (visible):** "Brain will mirror this folder's files into your knowledge base and keep them in sync automatically."
- **Folder label:** "Folder"
- **Folder picker placeholder:** "Choose a folder to watch…"
- **Folder picker button:** "Choose folder"
- **Folder picker aria-label:** "Choose a folder to watch"
- **Already-watched error:** "This folder is already being watched. Choose a different folder or manage it in Settings → Watched folders."
- **Domain label:** "Domain"
- **Domain dropdown aria-label:** "Choose the domain for notes from this folder"
- **Privacy-rail info-line:** `"This folder will sync into your ${domain} domain (privacy-railed by default — these notes won't appear in default chat scope)."`
- **Subfolders checkbox:** "Include subfolders"
- **Subfolders helper (right of checkbox, --text-dim, --ui-xs):** "Also watches every folder inside this one."
- **D1 callout heading (sr-only):** "Important: overwrite contract"
- **D1 callout body line 1:** "**Heads-up:** the source file is the source of truth. If you edit a note from this folder inside your vault, your edits will be overwritten the next time the source file changes."
- **D1 callout body line 2:** "Deleting a source file marks its note as an orphan in your vault (it isn't deleted). You can review orphans in Settings → Orphans."
- **Cost-estimate panel heading:** "Initial sync"
- **Cost-estimate panel body template:** `"${file_count} files found · estimated cost ~$${cost.toFixed(2)}"`
- **Cost-estimate helper:** `"ⓘ Pulls in all ${extensions.join(' / ')} files now."`
- **Cost-estimate error:** "Couldn't estimate cost. You can still watch this folder; sync will run with normal budget caps. [Try again]"
- **Cost-estimate in-flight:** "Estimating cost…"
- **Cancel button:** "Cancel"
- **Confirm button (default):** "Watch and sync now"
- **Confirm button (in-flight):** "Setting up watch…"
- **Confirm button (estimating):** "Estimating…"
- **Success toast lead:** `"Watching ${folder.basename}."`
- **Success toast msg:** `"Initial sync running — ${file_count} files. Track progress in Settings → Watched folders."`
- **Failure toast lead:** "Couldn't watch folder."

## D1 contract paragraph — final agreed wording

> **Heads-up:** the source file is the source of truth. If you edit a note from this folder inside your vault, your edits will be overwritten the next time the source file changes.
>
> Deleting a source file marks its note as an orphan in your vault (it isn't deleted). You can review orphans in Settings → Orphans.

### Why this wording (rationale)

- **"Heads-up"** instead of "Warning" — non-technical, calm, doesn't alarm. The contract is a *trade-off the user is choosing*, not a hazard.
- **"the source file is the source of truth"** — a slight repetition but it cements the mental model. Plan 22 D1's exact phrase is "source canonical"; we render this as "source of truth" because non-technical users don't know "canonical" but understand "source of truth" from everyday usage (newspapers, citations).
- **"your edits will be overwritten the next time the source file changes"** — concrete, names the failure mode without hedging. Avoids passive ("might be lost") which sounds like a maybe.
- **"isn't deleted"** in the orphan paragraph — explicit reassurance. The non-technical user's first fear is "will Brain delete my notes?". Answering NO upfront is the trust cue.
- **"You can review orphans in Settings → Orphans"** — names the recourse path explicitly so the user knows where to go.

### Microcopy needing user feedback

- The phrase **"Heads-up"** vs alternatives ("Important", "Note:", "Before you continue:"). I picked "Heads-up" for warmth + non-corporate tone — non-technical users get less hostile vibes from it than from "Important" (which feels like a EULA). Open to user override.
- **"Watch and sync now"** as the CTA verb — alternatives are "Start watching", "Watch this folder", "Begin sync". I picked the action-summarizing phrase because the CTA does TWO things (register + initial sync) and the user benefits from knowing both before clicking. Open to user override.

## Interaction

- **Mount → focus:** the modal's first tabbable is the "Choose folder" button (default entry) OR the domain dropdown (Bulk Import entry, where folder is already filled). `onOpenAutoFocus` override per `Modal` API.
- **Choose folder click:** native OS folder picker (electron / browser file picker). On confirm, populates folder input + triggers cost-estimate fetch.
- **Domain change:** if path was already chosen, re-fire cost estimate (different domain = different `IngestRouter` may have different extension list).
- **Include subfolders toggle:** also re-fires cost estimate (toggling subfolders changes file count).
- **Cancel button + Esc + backdrop click:** all close modal, no commitment, no toast.
- **Confirm button:** validates inputs → fires `brain_watch_folder({path, domain, recursive})` → handles in-flight + completion as above.

## Keyboard order

1. "Choose folder" button (or skip to 2 if path is prefilled)
2. Domain dropdown
3. "Include subfolders" checkbox
4. (skip into D1 callout — non-interactive)
5. "Try again" link (only if cost-estimate error)
6. "Cancel" button
7. "Watch and sync now" button

Esc closes from any focus position. Enter on the confirm button activates it; Enter inside the domain dropdown closes the dropdown without submitting (Radix Select behavior).

## Accessibility annotations

- D1 callout has `role="note"` and is `aria-labelledby="<sr-only heading>"` so screen readers announce it as a distinct content region.
- Cost-estimate panel has `role="status" aria-live="polite"` so the populated estimate is announced to screen readers.
- Cost-estimate error has `role="alert"` so it interrupts.
- "Setting up watch…" button state has `aria-busy="true"` AND `aria-label="Setting up watch, please wait"` (Radix native handles `aria-disabled` via `disabled`).
- Folder picker button has `aria-haspopup="dialog"` (the OS folder picker counts).
- Domain dropdown has `aria-required="true"` (it always defaults to a valid value, so it can never actually be empty, but the attribute makes intent explicit).
- The "isn't deleted" italic emphasis in the orphan callout uses `<em>` (semantic emphasis), not `<i>` (visual italic).
- Color contrast: `--warn` icon at 18px is non-text (3:1 sufficient on either theme). Callout body text is `--text` on `--surface-2` (8.4:1 dark / 13:1 light, both clear AA 4.5:1).

## Implementation guidance for T15

- Compose: `<Modal width={560} ...><div>...</div></Modal>`. Reuse `Modal` for plumbing.
- The `Choose folder` button needs an OS-bridge — likely tap into the existing setup wizard's folder-picker pattern (Plan 06 / 07). Browser file-pickers may need `<input type="file" webkitdirectory>` for non-Electron deploys.
- Cost-estimate fetch needs a backend tool — if `brain_watch_folder` supports a `dry_run` arg, use that; otherwise create `brain_estimate_watch_cost`. Confirm with T9 implementer.
- Pre-fill from Bulk Import: parent (Bulk Import success screen, Plan 22 T15-adjacent) opens the modal via the `useDialogsStore.open({kind: "watch-enable", folder, domain})` pattern matching `panel-domains.tsx`'s rename / delete flow.
- The modal is dismissable mid-fetch (Esc, Cancel) — the cost-estimate fetch should be cancelable (AbortController) so we don't waste a backend call.
- Inline error display: matches `panel-domains` Plan 16 T4 banner pattern.
