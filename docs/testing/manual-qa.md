# Manual QA checklist

Human-runnable smoke checklist for the **brain** app. Run on a clean
Mac 13+ VM **and** a clean Windows 11 VM before every version tag. CI
enforces unit, integration, and e2e coverage; this checklist covers the
gaps no automated suite can reach — real drag-drop from Finder/Explorer,
real Claude Desktop round-trip, real font rendering on two OSes, real
network timing.

## How to run

1. Fresh VM (no prior brain install).
2. Run the installer (`install.sh` on Mac, `install.ps1` on Windows).
3. Open http://localhost:4317 — landing lands on `/setup`.
4. Walk each section in order. Tick each box in a copy of this file.
5. Any unchecked box is a release blocker. File the bug, link it here,
   re-run after the fix.

Target: ≥60 items, all green, on both OSes. Typical run time: 45 min.

---

## 1. Setup wizard (fresh install)

- [ ] `/` redirects to `/setup` on first run (no BRAIN.md)
- [ ] Step 1 of 6 — Welcome panel renders with the app name visible
- [ ] Step 2 — Vault location prefilled with `~/Documents/brain`
- [ ] Step 2 — Browse button opens the native file picker
- [ ] Step 3 — API key field accepts input and masks on blur
- [ ] Step 3 — Continue works with an empty API key (field is optional)
- [ ] Step 4 — Theme options (dark / light / auto) are clickable
- [ ] Step 5 — BRAIN.md seed picker shows ≥3 templates
- [ ] Step 5 — "Skip this" leaves BRAIN.md unseeded
- [ ] Step 6 — Claude Desktop install button is visible
- [ ] Step 6 — "Start using brain" routes to `/chat`
- [ ] No `console.error` on any step (DevTools open)
- [ ] Back button on steps 2-6 decrements the step counter
- [ ] Refresh on any step resumes at that step (localStorage persistence)

## 2. Chat

- [ ] Empty `/chat` shows the "What are we working on?" empty state
- [ ] Sending "hello" starts a streaming turn within 2s
- [ ] Cancel button mid-stream stops deltas cleanly (no orphaned `...`)
- [ ] Mode switch (Ask / Brainstorm / Draft) between turns persists visually
- [ ] Scope picker checkbox changes take effect on the next turn
- [ ] Fork thread button opens a dialog; confirming routes to the new thread
- [ ] "File to wiki" from a message surfaces a note suggestion
- [ ] Re-opening a thread shows prior turns in order
- [ ] Thread auto-title appears within 2 turns

## 3. Pending patches

- [ ] Staged patch appears in `/pending` within 1s of proposal
- [ ] Diff view renders both sides side-by-side at ≥1024px width
- [ ] "Approve" toast fires and patch disappears from the list
- [ ] "Edit then approve" opens the inline editor; Monaco loads
- [ ] Reject requires a typed reason (non-empty)
- [ ] "Undo last" reverts the last-applied patch and re-stages the previous state
- [ ] "Approve all" handles ≥5 patches without the UI freezing

## 4. Browse

- [ ] Left file tree mirrors the vault directory structure
- [ ] Clicking a `.md` file opens it in the preview pane
- [ ] `⌘K` (Mac) / `Ctrl+K` (Windows) opens the search overlay
- [ ] Search returns results within 300ms on a vault of ≥50 notes
- [ ] Hovering a `[[wikilink]]` shows a preview tooltip
- [ ] Clicking the "Open in Obsidian" button launches the correct vault
- [ ] Edit mode toggles to Monaco; save stages a patch (not a direct write)

## 5. Draft mode

- [ ] Picking a doc from the picker loads it into the editor
- [ ] A draft-mode turn emits `doc_edit_proposed` (visible in network panel)
- [ ] "Apply" merges the edit into the preview without reload
- [ ] "Reject" leaves the doc unchanged
- [ ] Switching docs mid-session clears the pending edit state

## 6. Inbox

- [ ] Drag a `.txt` file from Finder/Explorer onto the window → row appears
- [ ] Drag a `.md` file → classifies into the correct domain within 5s
- [ ] Drag a `.pdf` → shows "PDFs coming soon" toast (variant: warn)
- [ ] Paste a URL anywhere outside an input → row appears + domain classified
- [ ] Paste plain text ≥100 chars → row appears + classified
- [ ] "Retry failed" on a failed row re-runs classification
- [ ] Failed rows surface a plain-English error message + next action

## 7. Bulk import

- [ ] Folder picker accepts a directory of ≥5 mixed `.md`/`.txt` files
- [ ] Cap-override warning shows if total > 50 files
- [ ] Dry-run table shows per-file route (domain + pending-patch preview)
- [ ] Per-file override dropdown re-routes one file to another domain
- [ ] "Apply" progress bar advances without freezing the UI
- [ ] Cancel mid-bulk stops further work but keeps already-applied patches

## 8. Settings (8 panels)

- [ ] General — theme toggle persists across reload
- [ ] Providers — API key save round-trips (masked on reload)
- [ ] Domains — list matches vault top-level directories
- [ ] Domains — rename dialog requires typed confirmation
- [ ] Integrations — Claude Desktop install button reports status
- [ ] Budget — override dialog accepts $ amount + hours
- [ ] Logs — recent entries render with timestamps
- [ ] Backups — "Create now" succeeds and the new row appears

## 9. Accessibility

- [ ] Tab through `/chat` keyboard-only — no trapped focus
- [ ] Tab through `/pending` — every interactive element is reachable
- [ ] Screen reader (VoiceOver Mac / Narrator Windows) reads the composer label
- [ ] `prefers-reduced-motion: reduce` disables slide-in animations
- [ ] axe-core DevTools extension reports 0 violations on `/chat`, `/browse`, `/pending`
- [ ] Focus ring is clearly visible in both light and dark themes
- [ ] Colour contrast meets WCAG 2.2 AA on body text (run axe check)

## 10. Theme + responsive

- [ ] Dark theme renders every screen (walk each route)
- [ ] Light theme renders every screen
- [ ] Theme toggle does not flash unstyled content
- [ ] At 1024px viewport the shell collapses cleanly (right rail hides if needed)
- [ ] At 1024px no horizontal scrollbar appears on any route
- [ ] Resizing from 1920 → 1024 → 1920 restores full layout without breakage

## 11. Cross-platform specifics

- [ ] **Mac**: Cmd+K opens search; Ctrl+K does NOT hijack focus
- [ ] **Windows**: Ctrl+K opens search; does NOT conflict with browser shortcut
- [ ] **Mac**: Finder drag-drop of a folder with spaces in the name works
- [ ] **Windows**: Explorer drag-drop of a folder from `C:\Users\...` works
- [ ] **Windows**: long path (>260 chars) in the vault root does not crash ingest
- [ ] **Windows**: CRLF-only source file ingests without line-ending artifacts
- [ ] Roboto font renders (no fallback to Arial/system) — check DevTools Computed tab
- [ ] Monaco editor loads with no WASM errors in the console

## 12. Claude Desktop round-trip (real)

- [ ] Click "Install" in Settings → Integrations
- [ ] Claude Desktop config file updated (check on disk)
- [ ] Open Claude Desktop — restart if needed
- [ ] "brain" appears in the MCP server list with a green indicator
- [ ] Send a message in Claude Desktop that triggers `brain_search`
- [ ] Tool call returns results that match the vault
- [ ] Selftest button in Settings reports "selftest passed"

## 13. Real-world ingest (5 sample sources)

- [ ] Ingest a PDF chapter — classification lands in the right domain
- [ ] Ingest a web article (URL paste) — title + summary populated
- [ ] Ingest a personal journal entry — routes to `personal/` (if scope allows)
- [ ] Ingest a codebase README — picks up code-doc structure
- [ ] Ingest a meeting transcript — entities + concepts extracted

## 14. Autonomous mode

- [ ] Toggle "Autonomous mode" on in Settings
- [ ] Next ingest auto-approves without manual review
- [ ] Undo last still reverts auto-approved writes
- [ ] Toggle off — new proposals stage normally

## 15. Vault-safe uninstall

- [ ] `brain uninstall` prompts for typed confirmation
- [ ] Declining the prompt leaves the vault untouched
- [ ] Confirming removes the app binaries but NOT `~/Documents/brain`
- [ ] Re-installing re-detects the existing vault

---

## Reporting

If you find a bug, file an issue with:

1. The checklist item number (e.g. "2.3: cancel button leaves orphaned `...`").
2. OS + version, browser + version.
3. Steps to reproduce (copy-paste from this file).
4. Screenshot or screen recording.
5. Expected vs actual.

Block the release until every box is green on both OSes.
