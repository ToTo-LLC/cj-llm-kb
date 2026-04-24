# brain — Design Delta v2

> **What this is:** a third-pass brief. v2 resolved most v1 gaps — this document flags (A) the remaining missing flows, (B) real inconsistencies with the built backend, and (C) minor cleanup items. Short because v2 is mostly right.
>
> **Date:** 2026-04-21
> **Read with:** `design-brief.md` (the baseline) + `design-delta.md` (v1, for context on what's changed).
> **Focus of this pass:** fix the 5 errors, design the 4 missing flows, trim the 2 cleanup items. Backend changes will land in Plan 07 — don't redesign around them.

---

## Table of contents

1. [What v2 got right](#what-v2-got-right)
2. [Errors to correct](#errors-to-correct)
3. [Still-missing flows](#still-missing-flows)
4. [Cleanup items](#cleanup-items)
5. [Backend changes coming in Plan 07](#backend-changes-coming-in-plan-07)

---

## What v2 got right

No changes needed to these. Preserve as-is:

- **Bulk import 4-step flow** (Pick → Scope → Dry-run → Apply) — full fixture with duplicates, uncertain, sensitive flags, 20-file cap, cancel-after-current-file. Use the same interaction patterns for any future multi-step flow.
- **Browse with Monaco editor + ⌘K search overlay + wikilink hover preview + Obsidian link** — the "editing vault directly" warning is the right voice.
- **Settings panels** — Providers, Integrations, Domains, BRAIN.md, Backups all landed with consistent shape. `sect-card` + `row-grid` pattern works well.
- **SystemOverlays host** — clean pattern for dialogs + banners + overlays routed through one mount point.
- **Dialog components** — `RejectReasonDialog`, `EditApproveDialog`, `TypedConfirmDialog`, `BudgetWall`, `OfflineBanner`, `MidTurnToast`, `DropOverlay` are the right set. The typed-confirm word varies cleanly by context (`DELETE` / `UNINSTALL` / `RESTORE` / domain name).
- **Per-category autonomy toggles** — adopted per v1 delta. Backend will extend to support (see §5).
- **Chat inline patch card + tool-call cards + streaming composer** — unchanged from v1; still right.

---

## Errors to correct

Five real inconsistencies between the design and the built backend (Plans 01–05). Fix these before Plan 07.

### E1. "Embeddings" cost category doesn't exist

**Where:** `BudgetWall` → `mini-breakdown` → `<li><span>Embeddings</span><span>$0.06</span></li>`

**Problem:** Spec §6 explicitly states *"No vector DB — retrieval is a tool call."* Plans 01–05 use BM25 only (sparse, local, no API cost). There is no embeddings spend to show.

**Fix:** remove the `Embeddings` line from the breakdown. The remaining three (Ask, Draft, Ingest) reflect reality. If you want a fourth to keep the column balanced, use **`Brainstorm`** or **`Classify`** (both real cost categories).

---

### E2. `brain mcp serve` CLI command doesn't exist

**Where:** `IntegrationsPanel` → "Other MCP clients" code block:

```json
"brain": {
  "command": "brain",
  "args": ["mcp", "serve"],
  "env": { "BRAIN_VAULT": "~/Documents/brain" }
}
```

**Problem:** Plan 04 shipped `brain mcp install | uninstall | selftest | status`. There is no `serve` subcommand. The actual MCP server entry is `python -m brain_mcp`, which is what `brain_core.integrations.claude_desktop.install(...)` writes to the Claude Desktop config.

**Fix:** update the snippet to:

```json
"brain": {
  "command": "python",
  "args": ["-m", "brain_mcp"],
  "env": {
    "BRAIN_VAULT_ROOT": "~/Documents/brain",
    "BRAIN_ALLOWED_DOMAINS": "research,work"
  }
}
```

(Note: env var is `BRAIN_VAULT_ROOT`, not `BRAIN_VAULT`. Plan 04 Task 21a pinned this.)

---

### E3. "OS keychain" claim is aspirational, not built

**Where:** `ProvidersPanel` → "API keys are stored only on this machine, in the OS keychain. They never leave your computer except to reach Anthropic." + later "Saved to the OS keychain. Visible only the first time you paste it."

**Problem:** Plan 01 stores secrets in `<vault>/.brain/secrets.env` — a plain-text file (mode 0600 on POSIX). There is no keychain integration today.

**Fix (pick one):**

- **Option A (recommended — matches reality):** soften the copy to *"API keys are stored only on this machine. They never leave your computer except to reach Anthropic."* Drop "keychain" references. Keep the masked display (`sk-ant-•••••••••••qXf2`) — that's purely a UI decision.
- **Option B:** keep the keychain copy. Plan 07 integrates the Python `keyring` library (Mac Keychain / Windows Credential Manager). Adds a dep; not trivial on Windows.

**My lean: Option A.** Local-file-in-secure-mode is defensible for a single-user local tool; keychain integration is polish.

---

### E4. Context-%-used meter is a lie

**Where:** Composer footer + transcript header → `<div className="ctx-meter">...<span>{ctxPct}%</span></div>`. Reducer hardcodes `ctxPct: 18`.

**Problem:** The backend does not emit a context-usage ratio. `cost_update` WS event has `tokens_in/out/cumulative_usd` but no context-fill metric. The meter currently shows a made-up number.

**Fix (pick one):**

- **Option A:** remove the meter entirely. Clean, honest.
- **Option B:** keep the meter but derive from cumulative tokens — compute `(cumulative_tokens_in / MAX_CONTEXT) * 100`. `MAX_CONTEXT = 200_000` for Sonnet. This is a reasonable approximation; show it as "≈18%" rather than "18%".
- **Option C:** defer to Plan 07 to add `context_pct_used` to `turn_end` or `cost_update` events. Hide the meter in v3; Plan 07 wires it on.

**My lean: Option B** — keep the meter, make it approximate, drop the exact percentage.

---

### E5. Tweaks panel should come out before ship

**Where:** `TweaksPanel` component + `showTweaks` state + `toggle_tweaks` action + window message protocol for design-tool activation.

**Problem:** It's a design-iteration overlay. Not a production feature. Its controls (theme, density, rail mode) already have proper homes (Settings → General for theme + density; rail-mode is cleaner removed entirely, see §4).

**Fix:** in v3 mockups, remove the Tweaks panel UI but keep the underlying preference plumbing (`density`, `theme`). Document that it's "design-time only" in a comment so the Plan 07 engineer knows.

---

## Still-missing flows

Four flows from the original brief that v2 didn't address. Each is a standalone design task.

### M1. Draft mode — open-doc picker + active doc panel

**Backend context:** Draft mode expects a single **open document** as primary context. The WS `SetOpenDocMessage` client frame tells the session which doc is open. Without an open doc, Draft mode can't do its job.

**What's needed in design:**

- **Empty-state when Draft is selected with no doc:** a prompt in the transcript area — "Pick a document to draft on" with two buttons: (a) "Open a vault file" (opens a mini file picker / search), (b) "Start a new scratch doc" (creates `<domain>/scratch/<thread-id>.md` on first save).
- **Active-doc panel:** once a doc is open, show its path + a compact reader/editor next to the transcript. Designer's call whether that's right-side panel, top strip, or collapsible drawer. The composer placeholder should tighten to reflect the active doc (e.g. "Drafting on `fisher-ury-interests.md`…").
- **Switch-doc affordance:** between turns only — click the path chip to open the picker again. Mid-turn switches emit `invalid_state` error (see M3).
- **Diff mode in the active-doc panel:** when the assistant proposes an edit via `edit_open_doc`, the patch-proposed event should visually attach to the open-doc panel rather than (or in addition to) the right-side pending rail. The Draft flow is doc-centric.

---

### M2. File-to-wiki dialog

**Backend context:** Spec §6 names "File to wiki" as a first-class chat action. Chat pane has a "File to wiki" button on assistant messages (already in design). The dialog behind that button isn't designed.

**What's needed in design:**

- Modal (or side-panel) with:
  - **Domain picker** — defaults to the active thread's primary domain; switchable.
  - **Note type picker** — `synthesis` (default) / `concept` / `entity` / `source`.
  - **Editable proposed path** — `<domain>/<type>/<auto-generated-slug>.md`, pre-filled. Path is editable; shows a warning if the target already exists.
  - **LLM-distilled body preview** — not the raw transcript; the LLM produces a clean standalone note. Show the first ~20 lines + "expand" affordance.
  - **Approve button** — triggers the normal patch approval flow. On success, the source thread's frontmatter gets `filed_to: [[<new-note>]]` (backend already handles this).
- **Voice:** calm, specific. "File this to the wiki?" as title. Not "Save" or "Export".

**Source thread backlink:** after approval, the assistant message that got filed should show a small chip ("Filed to `<path>` →") — reciprocal of the thread's `filed_to` frontmatter.

---

### M3. Mid-turn `invalid_state` toast kinds

**Backend context:** Plan 05 WS emits `{type: "error", code: "invalid_state", ...}` for two conditions the design doesn't handle:

1. Client sent `turn_start` while a turn is already active → server rejects with `invalid_state`.
2. Client sent `switch_mode` during an active turn → server rejects with `invalid_state`.

v2's `MidTurnToast` has `rate-limit`, `context-full`, `tool-failed` kinds. Missing the invalid-state ones.

**What's needed in design:**

Add two kinds to `MidTurnToast`:

- `invalid-state-turn`: lead "Finish this turn first." msg "Wait for it to complete, or cancel to start fresh."
- `invalid-state-mode`: lead "Can't switch mid-turn." msg "Mode change takes effect on the next turn."

Both are `tone: "warn"`, non-blocking, auto-dismiss on next turn event.

---

### M4. New-thread empty state

**Backend context:** Left-nav "New chat" button → clears transcript, new thread_id, focus composer. Currently the chat screen renders an empty transcript container and a composer — technically functional but visually underdone.

**What's needed in design:**

- A welcoming empty-state block in the transcript area with:
  - The current **scope** (which domains are in play), rendered prominently — sets user expectation for what brain can draw from.
  - The current **mode** with a one-line description ("Ask: cite from the vault" / "Brainstorm: push back, propose notes" / "Draft: collaborate on a document").
  - 2–3 **starter prompts** contextual to the mode (e.g. Brainstorm: "Argue with me about..." / Draft: "Rewrite this paragraph…").
- Composer remains at the bottom, focused by default.

No new copy needs to be long. The brief's voice principle ("calm, a little witty but never cute") applies.

---

### M5. Thread fork dialog *(optional — lower priority)*

**Backend context:** Chat has a "Fork" button. Plan 03's `ChatSession` doesn't currently support fork semantics; Plan 07 would add `ChatSession.fork_from(source_thread_id, turn_index)`. The dialog/flow is undesigned.

**What's needed in design:**

Small modal:

- "Fork from here" title.
- Shows which turn the fork is from (preview of the user's message + assistant response summary).
- Inputs: new thread title (pre-filled from current title + " (fork)"), mode selector (defaults to current), scope selector (defaults to current).
- On confirm: new thread is created with turns 1..N copied as context, user lands on the fresh composer.

**Priority:** lower than M1–M4. Can skip this pass and design it post-Plan-07 if needed.

---

## Cleanup items

### C1. Rail-mode (Pop-in vs Badge) toggle

**Where:** Tweaks panel + `railMode` state + settings flow.

**Recommendation:** drop it. Ship one default (pop-in) and revisit only if user feedback demands. One less mode = one less surface to design error states for. If kept, move from Tweaks to Settings → General (matches density's treatment).

### C2. DomainsPanel "Rename" button has no designed flow

**Where:** `DomainsPanel` → each row has a `Rename` button but no dialog mockup.

**What's needed:** small modal with current name + new-name input + warning ("Renames the folder and rewrites `[[wikilinks]]` that point into it — this may take a moment on large domains"). Typed confirmation for domains with > 50 notes.

**Or skip:** deferred to Plan 07 (rename-domain is a non-trivial backend operation — moving a folder + rewriting wikilinks across the vault). The design can show the Rename button as disabled-with-tooltip-"coming soon" if you want to keep the UI pattern but defer the implementation.

### C3. Bulk-import cost estimate precision

**Where:** Step 3 footer: `Estimated cost: ~$0.011/file · ~4.2s per file`.

**Recommendation:** keep the estimate but:
- Prefix with "Rough estimate" in small copy
- Drop the decimal precision on seconds ("~4s" not "~4.2s")
- Surface the basis: "Based on file size + Sonnet token rates"

---

## Backend changes coming in Plan 07

**For context only — do not redesign around these.** Plan 07 will extend the backend to match v2's design ambitions. Here's what's on the Plan 07 list:

1. **Per-category autonomy config keys** — `autonomous.ingest` / `autonomous.entities` / `autonomous.concepts` / `autonomous.index_rewrites`. Matches design's 4 toggles.
2. **Per-mode chat models** — `ChatSessionConfig.{ask,brainstorm,draft}_model`. Matches ProvidersPanel's model-per-stage table.
3. **Cost ledger tagging by mode/stage** — so BudgetWall breakdown reflects reality.
4. **`BulkPlan.items[].duplicate: bool`** — backend surfaces the `dup` flag dry-run already renders.
5. **Ingest history read tool** — `brain_recent_ingests` so Inbox's "Recent" tab works without folder-walking.
6. **Domain management** — `domain_order` config key + `brain_create_domain` (mkdir + seed `index.md`). Rename deferred.
7. **Ephemeral budget override** — session-scoped "Raise cap by $5 today" that resets.
8. **`ChatSession.fork_from(source_thread_id, turn_index)`** — supports M5.
9. **Context-%-used in WS events** — supports E4 Option C if picked.
10. **OS keychain integration** — only if E3 Option B is picked.
11. **Broken-wikilink existence check** — `brain_wikilink_status` or `exists: bool` on `brain_read_note` 404. Optional.

---

## Summary of what to do next

Priority order for v3 design pass:

1. **Fix E1–E5** (five small copy + removal changes). 15 minutes total.
2. **Design M1 (Draft mode)** — the biggest gap. Probably 30 minutes.
3. **Design M2 (File-to-wiki dialog)** — medium. 20 minutes.
4. **Design M3 (mid-turn invalid-state toasts)** — two new kinds. 10 minutes.
5. **Design M4 (new-thread empty state)** — medium. 15 minutes.
6. **Optional: M5 (fork dialog), C1 (drop rail-mode), C2 (rename-domain), C3 (cost estimate copy).** 20 minutes if all done.

After v3 lands, Plan 07 authoring begins — the design will be the frontend's contract and the backend extensions (§5) land as Plan 07 Group 1 before any frontend screens are built.

---

**End of delta v2.** Paste alongside `design-brief.md` + `design-delta.md` for the next design pass.
