# brain — Design Delta v1

> **What this is:** a second-pass brief. The initial design (`CJ Knowledge LLM.zip`, ingested 2026-04-21) covers the daily-driver paths well. This document enumerates the gaps between that design and the built backend (Plans 01–05) + the master design brief (`design-brief.md`). Feed this back to the design tool for a second pass.
>
> **How to read:** each gap has a **state**, a **spec** (what's needed), and a **resolution** (what to design). Three categories: screens that need a full design pass (§1), smaller missing pieces (§2), new concepts from the design that need validation (§3). §4 is one backend decision that unblocks a design choice.

---

## 1. Screens that need a full design pass

### 1.1 Bulk import — dry-run review + apply progress

**State:** `BulkScreen` is a single CTA ("Pick a folder" / "Use a path"). No dry-run flow, no per-file review, no apply progress.

**Spec:**
- 4-step flow: (1) folder picker, (2) scope (target domain OR "auto-classify"), (3) dry-run review, (4) apply with streaming progress.
- Dry-run review is a **table**, one row per file: filename, type icon (PDF/URL/TXT/EML), classified domain chip, confidence bar, include-checkbox, per-file re-route dropdown (to override the classifier's domain guess).
- **`max_files` hard threshold:** if folder has > 20 files AND `dry_run=false` AND no explicit `max_files` cap, the backend refuses. UX: after picking a large folder, show "47 files — too many to apply at once. Pick how many to import:" with a slider/input (min 1, max=folder size).
- Apply step: progress bar (`N of 47 applied`), per-file status live-updating (queued → extracting → classifying → summarizing → integrating → done / failed), a **cancel button** that gracefully stops after the in-flight file.
- Done state: summary card (`42 applied · 3 quarantined · 2 failed` with expandable failure list).
- Skipped files (unsupported types, hidden, duplicates) surface in a separate "Skipped" sub-list with reason.

**Resolution:** design wireframes + mockups for all 4 steps + error/cancel states. This is a primary workflow — users will bulk-import historical Obsidian vaults.

---

### 1.2 Browse — Markdown editor + full-text search

**State:** `BrowseScreen` is read-only. Frontmatter is hardcoded. No search box. No "edit this note" affordance.

**Spec (spec §8):**
- **Edit mode toggle** on the reader — switches to Monaco Markdown editor with live preview (split-pane? tabbed? designer's call). Save triggers a patch through the normal approval flow (or autonomous apply if the user has that on for manual edits — design question).
- **Full-text search** — persistent search box at the top of the tree or reader. Typing filters both the file tree AND opens a results panel. Results are BM25 hits from `brain_search` with snippet + score. Clicking a result jumps to the file + highlights the match.
- **Wikilink hover preview** — hovering a `[[wikilink]]` shows a small popover with the target note's first paragraph. Clicking navigates. Broken wikilinks (target doesn't exist yet) are visually distinct (dashed underline? muted color?) — the design already has a `.wikilink.broken` class, so preserve that styling.
- **"Open in Obsidian" link** on every note's meta strip — launches `obsidian://open?vault=brain&file=<path>`. Small link-icon button next to the path.

**Resolution:** designs for (a) edit mode entry + Monaco pane + save-as-patch, (b) search UI (overlay or split panel), (c) wikilink hover card, (d) Obsidian button placement.

---

### 1.3 Draft mode — open-doc context

**State:** composer placeholder mentions "Open a document and collaborate inline…". No UI for picking a doc, no indication of the active doc, no inline-edit surface.

**Spec (Plan 03 + Plan 05 WS):**
- Draft mode expects a single **open document** as primary context. The backend `SetOpenDocMessage` WS frame tells the session which doc is open.
- Entering Draft mode with no doc open → empty-state prompt: "Pick a document to draft on" with two paths: (a) browse for a vault file, (b) start a new blank scratch doc that will land at `<domain>/scratch/<thread-id>.md` when approved.
- Once a doc is open: show its path + a compact preview/editor on the right side OR above the composer. Assistant responses in Draft mode can emit `edit_open_doc` patches that propose edits to that specific file.
- Switching docs mid-thread is allowed — the user can `set_open_doc` again at any turn boundary. Design how this transition feels.

**Resolution:** mockup Draft mode's entry state, the in-session open-doc panel, and the mid-turn doc-switch.

---

### 1.4 Settings — detail panels (Providers / Integrations / Domains / BRAIN.md / Backups)

**State:** Three tabs are designed (General, Autonomous mode, Budget & costs). Five tabs are placeholder ("form fields, same pattern").

**Spec per tab:**

- **LLM providers:** paste API key (masked after save), model choice per chat-mode (Ask/Brainstorm/Draft may use different models) + per-ingest-stage (classify → summarize → integrate), "test connection" button (calls `/healthz` + a cheap ping).
- **Integrations → Claude Desktop:** status badges (detected / installed / verified), per-action buttons (install / uninstall / regenerate config / selftest / copy config snippet for other MCP clients like Cursor + Zed). Backend = Plan 04's `brain mcp install/uninstall/selftest/status`.
- **Domains:** list all domains with note counts, add-domain form (name + color accent picker), delete-domain with typed confirmation, reorder (drag handles) — affects default scope order in the top-bar picker.
- **BRAIN.md editor:** full Monaco markdown editor, preview toggle, save triggers a vault write (through patch flow — it's a vault file). This is the user's voice/persona for the LLM.
- **Backups:** "Back up now" button (triggers a timestamped tarball), list of past backups with date + size, restore flow (typed confirmation; destructive).

**Resolution:** mock all 5. They're form-heavy but each has at least one distinctive interaction (test-connection, domain-color picker, BRAIN.md editor, backup list row with restore).

---

### 1.5 Error + offline states

**State:** Inbox has good failure rows. Chat + Pending + Browse + Settings don't have visible error/offline states.

**Spec:**
- **Backend offline banner:** when `/healthz` fails, persistent banner across the top of the app: "brain is offline — [retry]" + each screen grays out interactive controls.
- **Rate-limited toast:** 429 from any REST call → toast "Slow down — retrying in 12s" with a live countdown and a "wait" or "cancel" affordance. Per-bucket messaging (`patches` vs `tokens` — different explanation text).
- **Budget-exceeded wall:** 429 with `retry_after` in hours (daily cap hit) → full-screen soft wall on Chat ("Daily budget exceeded. Your remaining calls are paused until midnight. [raise cap] [wait]"). Other screens still work in read-only mode.
- **Chat turn failed mid-stream:** when a `{type: "error", recoverable: true}` frame arrives during a turn, show an inline error card in place of the assistant message: "That turn didn't finish — [try again] or [cancel]".
- **WebSocket disconnect:** status-bar indicator shows reconnecting spinner. Events buffered locally (optimistic UI) where safe.
- **Per-screen empty + loading + error** for Pending, Browse, Bulk import, Settings that aren't explicitly designed yet.

**Resolution:** one mockup per state, systematically applied across screens. Write in the voice-and-copy style from the brief (calm, blameless, actionable).

---

## 2. Smaller missing pieces

### 2.1 Mid-turn invalid-state feedback

Plan 05 WS emits `{type: "error", code: "invalid_state", ...}` when the client sends `switch_mode` or `turn_start` during an active turn. The design has no visible response. **Resolution:** an unobtrusive toast "Finish this turn first" that dismisses on turn_end.

### 2.2 "Edit, then approve" flow

Button exists in pending-detail. The editor (Monaco inline? modal?) is undesigned. **Resolution:** mockup the edit-in-patch experience — probably Monaco in the detail pane replacing the read-only diff, save-button returns to the patch-preview with the modified content staged.

### 2.3 Per-patch reject-with-reason dialog

Reject button exists; the reason-entry dialog isn't shown. Backend requires a reason string. **Resolution:** modal or inline popover with textarea + confirm/cancel.

### 2.4 Typed confirmations for irreversible actions

Settings → Domains → Delete domain is irreversible (removes N notes). Backups → Restore is irreversible. Uninstall Claude Desktop integration is reversible but shouldn't be one-click. **Resolution:** consistent typed-confirmation pattern (user types `DELETE` or the domain name) across all 3 cases. The design brief's "no quick-click destruction" principle applies here.

### 2.5 Thread title auto-rename animation

Plan 03 renames threads after turn 2. Design has titles but doesn't show the transition. **Resolution:** small fade-in / typewriter treatment when the title updates. Non-critical.

### 2.6 "New thread" flow

Left nav has "New chat" button. Clicking should clear the transcript and focus the composer — design confirms this via `setActiveThread(null)`. **Resolution:** add an empty-state mockup for the fresh chat screen (no messages, placeholder prompt, prominent composer).

### 2.7 Context-%-used meter semantics

Design shows "context 18%" in composer. Backend doesn't currently emit a context-used ratio. **Resolution:** either (a) frontend approximates from turn count (crude), or (b) add `context_pct_used` to the `cost_update` or `turn_end` WS event. Flag for Plan 07 + a tiny brain_api change.

### 2.8 Broken-wikilink detection

Design styles broken wikilinks differently. Requires knowing "does `<domain>/notes/foo.md` exist?". **Resolution:** a lightweight backend endpoint — either add `exists: bool` to `brain_read_note`'s response on 404, or a new `brain_wikilink_status` batch endpoint for a note's graph. Flag for Plan 07.

---

## 3. New concepts introduced by the design — adopt / adapt / reject

### 3.1 Per-category autonomous mode toggles

**Design proposes:** 4 toggles (Source ingest / Entity updates / Concept notes / Index rewrites) each flipping autonomy independently. "Index rewrites" flagged as `danger`.

**Backend today:** Plan 04's `brain_config_set` only accepts 2 keys (`budget.daily_usd`, `log_llm_payloads`). Autonomy is currently one global flag per-call (`brain_ingest(autonomous=true)`) — no persisted per-category config.

**Recommendation:** **ADOPT** the design. Per-category is the right UX — index.md rewrites are materially riskier than source ingest. Plan 07 authoring needs to include a small brain_core extension:
- Add config keys: `autonomous.ingest`, `autonomous.entities`, `autonomous.concepts`, `autonomous.index_rewrites` (all default false)
- `_SETTABLE_KEYS` grows to include these
- `brain_apply_patch` consults the relevant key based on `patchset.kind` — if autonomous for that category, bypass pending-queue; else stage

Alternative: keep design as-is, persist per-category state frontend-only until Plan 09 formalizes. Technically works, loses state on browser refresh — not great.

### 3.2 "Approve all" / "Reject all" bulk actions

**Design proposes:** header buttons on Pending screen.

**Backend today:** no batch endpoint. Frontend loops over individual `brain_apply_patch` / `brain_reject_patch`.

**Recommendation:** **ADOPT**, frontend-looped. Show a progress indicator during the loop ("Approving 12 of 23…") + allow cancel mid-loop. A dedicated batch endpoint is a Plan 09 optimization if needed.

### 3.3 Drop-file-onto-chat overlay

**Design proposes:** full-screen "Drop to attach to this turn" overlay when dragging a file during chat.

**Semantics open:** (a) ingest via `brain_ingest` then inject the resulting note into the next turn's context, or (b) attach the raw content to the turn without going through ingest.

**Recommendation:** **ADOPT (a)** — ingest-then-attach. Cleaner mental model: everything that enters the vault goes through ingest. The turn composer gets a pill chip showing the attached source + a "detach" × button before send. This needs a small WS extension: `TurnStartMessage.attached_sources: list[str]?` with `patch_id` values. Flag for Plan 07.

### 3.4 Inline patch-proposal card in assistant messages

**Design proposes:** a "Staged a new note at `<path>` [Review in panel →]" card rendered below an assistant message when that message triggered a patch.

**Recommendation:** **ADOPT**. Natural fit — frontend composes the card from the WS `patch_proposed` event correlated to the active assistant message. No backend change.

### 3.5 Tool-call collapsible cards inline

**Design proposes:** inline `ToolCall` component rendering tool name + args + results. Default-closed, expand on click, shows BM25 hits.

**Recommendation:** **ADOPT**. Direct consumption of `tool_call` + `tool_result` WS events. No backend change.

### 3.6 Density toggle (Comfortable vs Compact) + Rail mode (Pop-in vs Badge)

**Design proposes:** Settings → General controls + Tweaks panel.

**Recommendation:** **ADOPT density**, **DEFER rail-mode**. Density is a meaningful user preference. Rail-mode (popin vs badge) adds state complexity for marginal gain — ship one default (popin) and iterate if users ask.

### 3.7 Tweaks panel (design-mode overlay)

**Design proposes:** floating panel for iterating theme/density/rail mode at design time.

**Recommendation:** **STRIP** before ship. It's a design-iteration tool, not a production feature. Keep the underlying preference plumbing; remove the UI surface.

### 3.8 "Already set up → open app" skip on wizard step 1

**Design proposes:** small link in bottom-right corner of the welcome step.

**Recommendation:** **ADOPT**, but the app should also auto-detect setup completion — if `BRAIN.md` exists AND API key is configured AND vault has any notes, skip the wizard entirely. The "open app" link becomes a rarely-seen escape hatch.

### 3.9 Thread grouping by date ("Today" / "Yesterday" / "This week" / "Last week")

**Design proposes:** left-nav thread list grouped with date headers.

**Recommendation:** **ADOPT**. Pure frontend — backend returns threads, frontend groups by `updated` timestamp.

### 3.10 Per-domain file count + "hidden by default" label for personal

**Design proposes:** domain count shown in scope picker dropdown; file tree shows `— 23 notes, hidden by default` for the personal domain.

**Recommendation:** **ADOPT**. Counts derive from `brain_recent` or a new thin `brain_domain_stats` helper. If not exposed, frontend can walk — but a tool is cleaner. Flag as small optional backend addition.

### 3.11 "Autonomous ingest" top-bar switch on Inbox

**Design proposes:** Inbox page has its own autonomous switch (separate from the global Pending-screen one).

**Recommendation:** **ADAPT** — make both switches bind to the SAME underlying config key (the `autonomous.ingest` flag from §3.1). Don't let them diverge. The Inbox one and the Pending one must be reflections of the same state.

---

## 4. Backend decision needed

**Per-category autonomous mode** (§3.1) is the one design proposal that requires a backend commitment.

**Options:**

- **A (recommended):** Plan 07 authoring adds a brain_core extension — new config keys (`autonomous.ingest` / `autonomous.entities` / `autonomous.concepts` / `autonomous.index_rewrites`), `_SETTABLE_KEYS` grows, `brain_apply_patch` consults the key based on a new `patchset.category: Literal[...]` tag that tool authors populate (`brain_ingest` → "ingest", `brain_propose_note` for entities folder → "entities", etc.). This is strictly additive, testable, and matches the design's mental model.

- **B:** single global toggle (current spec). Simplifies backend; design drops to one switch. Works but feels coarse for "should brain rewrite my curated index.md" kind of questions — low-risk ingest gets lumped with high-risk index rewrites.

**My recommendation: A.** Worth a small Plan 07 scope bump. Until you pick, the design's per-category toggles persist frontend-only (ephemeral).

---

## 5. Summary of what's strong + what's next

**Strong in current design:**
- Chat screen (streaming, tool-call cards, inline patch proposals, composer with scope/mode/context)
- Pending lifecycle (list + detail with diff view, approve/edit/reject, autonomous banner)
- Setup wizard (6-step, clear voice, smart "already set up" skip)
- Top-bar information architecture (scope picker, mode switcher, cost meter)
- Toast system with undo + countdown
- Dark/light modes + TomorrowToday token palette

**Priority for next design pass, in order:**

1. **Bulk import** (primary workflow, fully placeholder)
2. **Error + offline states** (reliability story)
3. **Browse edit mode + search** (spec §8 core)
4. **Settings detail panels** (5 placeholders to fill)
5. **Draft mode open-doc** (undifferentiated from Ask/Brainstorm today)
6. **Smaller pieces** from §2 (lower priority but each is a small lift)

Once these land: Plan 07 (frontend implementation) gets authored against the complete mockup set. Backend lift for Plan 07 is small — §4's per-category autonomy extension + two small helpers (§2.7 context meter, §2.8 broken-wikilink check) + possibly §3.10 domain stats.

---

**End of delta.** Paste this back into the design tool alongside the original brief — it'll know where to focus.
