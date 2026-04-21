# brain — UI Design Brief

> **This document is the complete context for designing the `brain` web UI.** Hand it to an external design tool (Claude design or similar). It is self-contained — a designer can read this alone and produce a full design system + all screens without pulling in any other files.
>
> **Date:** 2026-04-21
> **Status:** Backend complete (Plans 01–05). UI design is the next gate before frontend implementation (Plan 07).
> **Target stack:** Next.js 15 + React + TypeScript + Tailwind + shadcn/ui.

---

## Table of contents

1. [The ask — what to produce](#the-ask)
2. [Product overview — what brain is](#product-overview)
3. [Users](#users)
4. [System architecture at a glance](#system-architecture)
5. [API contract — what the frontend talks to](#api-contract)
6. [Domain concepts — vault, domains, scope, patches, chats](#domain-concepts)
7. [Global layout](#global-layout)
8. [Screens to design](#screens-to-design)
9. [Setup wizard](#setup-wizard)
10. [Design principles](#design-principles)
11. [Voice, tone, microcopy](#voice-tone-microcopy)
12. [Accessibility](#accessibility)
13. [Visual constraints](#visual-constraints)
14. [What NOT to design](#what-not-to-design)
15. [Deliverables](#deliverables)
16. [Open design questions](#open-design-questions)

---

## The ask

Design the complete UI for `brain` — a local-first, LLM-maintained personal knowledge base that runs on the user's own machine. The backend is already built; you're designing the Next.js web app that wraps it.

**Produce, in order:**

1. **Design system + tokens** — color palette (light + dark), typography scale, spacing scale, radius scale, shadow scale. Output as Tailwind config + shadcn theme tokens.
2. **Information architecture & flows** — the global nav, how screens connect, key task flows (ingest a source, approve a patch, run a chat turn).
3. **Wireframes** for every screen — show layout skeleton, content regions, interaction affordances. Include empty / loading / populated / error states.
4. **High-fidelity mockups** for every screen — light AND dark modes. All interaction states (idle, hover, focus, active, disabled, loading).
5. **Component inventory** — the shadcn/ui primitives you use + any custom components, with their variants.
6. **Accessibility plan** — keyboard navigation map, screen reader labeling, focus management, reduced-motion behavior, contrast verification. WCAG 2.2 AA minimum.
7. **Microcopy** — every button label, form hint, error message, empty-state message, setup-wizard prose.

The UI serves a **single non-technical user on their own machine**. No multi-user, no permissions model beyond the scope system described below, no billing, no signup. Localhost only.

---

## Product overview

`brain` is a personal knowledge base that:

- **Ingests** — the user drops sources in (URLs, PDFs, text, tweets, email, meeting transcripts). An LLM pipeline summarizes, classifies, and integrates each source into the vault as Markdown notes.
- **Chats** — the user has conversations with an LLM that has access to the vault. Three chat modes: **Ask** (cite from the vault), **Brainstorm** (push back, propose new notes), **Draft** (collaborate on an open document).
- **Maintains** — every vault write is staged as a typed patch and presented to the user for approval. The user can approve, edit-then-approve, reject, or undo any change.

The vault is a folder of Markdown files at `~/Documents/brain/`. Everything is Obsidian-compatible. The user can edit files directly if they want.

**Mental model:** this is the user's personal second brain. The LLM is the curator. The user is the editor-in-chief who approves or rejects every change.

### Product principles (non-negotiable)

These come from `CLAUDE.md` — they constrain design decisions:

1. **The vault is sacred.** Every vault mutation must be explicit, reversible, and traceable. The UI must surface this — no "stealth writes."
2. **Privacy-first.** Zero telemetry. Zero analytics. The design must not imply or require any network call outside LLM providers.
3. **LLM writes are always staged.** "Staged" is a first-class concept in the UI. A patch exists in a pending queue before any vault write happens.
4. **Scope guard.** Notes live in **domains** (research / work / personal). The `personal` domain is a privacy rail — it never appears in wildcard queries. The UI must make scope visible at all times.
5. **Cost is visible.** Every LLM call has a dollar cost. The UI shows a running cost meter and budget caps.
6. **Plain English errors.** No stack traces, no exception class names. Every error has a plain-English message and a next action.
7. **Non-technical usability.** Every destructive action requires typed confirmation. Setup happens in the browser, not the terminal. Drag, drop, and paste everywhere content can enter.

---

## Users

**Primary user:** one non-technical knowledge worker on their own machine. They use the web app daily. They probably don't know what `git` is but are comfortable with Obsidian, Notion, or similar note apps.

**Characteristics:**
- Has a meaningful existing note-taking practice they want to augment.
- Cares about privacy — data stays local.
- Wants the LLM to do the organizational heavy lifting (summarize, classify, file, cross-link) while they stay in control of what lands in the vault.
- Uses desktop (Mac or Windows) — mobile is out of scope.
- Screen size: **1024 px minimum width**. Full-HD and larger are the sweet spot.

**Secondary user:** power users who also use Claude Desktop and talk to the vault via MCP. They don't use the web app exclusively, but when they do, they expect parity with what Claude Desktop can see.

**Non-users:**
- Teams. This is single-user.
- Mobile users. Not designed for.
- Blind users relying on screen readers for heavy editing — we support screen readers per WCAG 2.2 AA but editing Markdown via screen reader is not a target flow.

---

## System architecture

```
┌──────────────────┐   HTTP/WS    ┌──────────────┐
│  brain_web       │ ───────────► │  brain_api   │
│  (Next.js UI)    │              │  (FastAPI)   │─┐
└──────────────────┘              └──────────────┘ │
                                                   │ imports
┌──────────────────┐   stdio MCP  ┌──────────────┐ │
│  Claude Desktop  │ ───────────► │  brain_mcp   │─┤
└──────────────────┘              └──────────────┘ │
                                                   │
┌──────────────────┐              ┌──────────────┐ │
│  Terminal        │ ───────────► │  brain_cli   │─┤
└──────────────────┘              └──────────────┘ │
                                                   ▼
                                   ┌────────────────────────────────┐
                                   │  brain_core (Python library)   │
                                   │  vault + ingest + chat + tools │
                                   └────────────────────────────────┘
                                                   │
                                                   ▼
                                   ┌────────────────────────────────┐
                                   │  ~/Documents/brain/  (vault)   │
                                   │  .brain/state.sqlite  (cache)  │
                                   │  .brain/costs.sqlite  (cost)   │
                                   └────────────────────────────────┘
```

The frontend only talks to `brain_api`. The API runs at `http://localhost:4317` by default. Auth is a filesystem-token + Origin/Host check — the Next.js server reads the token, the browser never sees it raw.

---

## API contract

This is the fixed contract the design must respect. The API is already built and tested.

### Auth

- **Token:** random 32-byte hex written to `<vault>/.brain/run/api-secret.txt` at server start. Next.js server reads it and attaches `X-Brain-Token` on every request. Browser never has the raw token.
- **Origin/Host:** server rejects non-loopback Origins (CSRF defense). Both HTTP and WebSocket handshakes enforce this.
- **The UI assumes auth is handled.** You don't design a login screen. There is no login.

### REST endpoints

- `GET /healthz` → `200 {"status": "ok"}`. Used for the initial splash / "is the backend alive?" check.
- `GET /api/tools` → lists all 18 tools with their input schemas. Use for dynamic UI.
- `POST /api/tools/<name>` → dispatches a tool call. Request body matches the tool's JSON schema. Response envelope: `{"text": string, "data": object | null}`.
- Error response envelope: `{"error": string, "message": string, "detail": object | null}`. Status codes: 400 (invalid_input), 403 (scope / refused), 404 (not_found), 406 (not_acceptable), 429 (rate_limited, includes `Retry-After` header + `detail.bucket` + `detail.retry_after_seconds`), 500 (internal).

### 18 tools the UI can call

The frontend calls these via `POST /api/tools/<name>`. Every tool returns `{text, data}`.

**Read tools** (6):
- `brain_list_domains` — `{}` → `{domains: [str, ...]}`
- `brain_get_index` — `{domain?: str}` → `{domain, frontmatter, body}` (returns `<domain>/index.md`)
- `brain_read_note` — `{path: str}` → `{frontmatter, body, path}`
- `brain_search` — `{query: str, top_k?: int, domains?: [str]}` → `{hits: [{path, title, snippet, score}], top_k_used}`
- `brain_recent` — `{domain?: str, limit?: int}` → `{notes: [{path, modified_at}], limit_used}`
- `brain_get_brain_md` — `{}` → `{exists, body}` (the user's system prompt / persona)

**Ingest tools** (3):
- `brain_ingest` — `{source: str, autonomous?: bool, domain_override?: str}` → staged or applied. Default stages a patch (returns `patch_id`). `autonomous=true` applies immediately.
- `brain_classify` — `{content: str, hint?: str}` → `{domain, confidence, source_type, needs_user_pick}`
- `brain_bulk_import` — `{folder: str, dry_run?: bool=true, max_files?: int}` → plan or applied summary.

**Write/patch tools** (5):
- `brain_propose_note` — `{path, content, reason}` → `{status: "pending", patch_id, target_path}`
- `brain_list_pending_patches` — `{limit?: int}` → `{count, patches: [{patch_id, created_at, tool, target_path, reason, mode}]}` (metadata only; never includes patch body)
- `brain_apply_patch` — `{patch_id}` → `{status: "applied", patch_id, undo_id, applied_files}`
- `brain_reject_patch` — `{patch_id, reason}` → `{status: "rejected", ...}`
- `brain_undo_last` — `{undo_id?}` → `{status: "reverted" | "nothing_to_undo", undo_id}`

**Maintenance tools** (4):
- `brain_cost_report` — `{}` → `{today_usd, month_usd, by_domain: {domain: usd}}`
- `brain_lint` — stub; returns `{status: "not_implemented"}` for now (Plan 09 will land real linting). Hide in UI or show a disabled "Coming soon" item.
- `brain_config_get` — `{key}` → `{key, value}` (refuses keys that look like secrets)
- `brain_config_set` — `{key, value}` → in-memory only until Plan 07 persistence lands. Design for it anyway.

### WebSocket chat

`WS /ws/chat/<thread_id>?token=<secret>` — one WebSocket per chat thread. `thread_id` is `^[a-z0-9][a-z0-9-]{0,63}$` (kebab-case, cross-platform safe).

**Handshake** (server sends first):

1. `{type: "schema_version", version: "1"}` — pin the wire format version
2. `{type: "thread_loaded", thread_id, mode, turn_count}`

**Client messages** (send at any time):

- `{type: "turn_start", content: str, mode?: "ask"|"brainstorm"|"draft"}` — begin a turn
- `{type: "cancel_turn"}` — cancel the in-flight turn
- `{type: "switch_mode", mode: "ask"|"brainstorm"|"draft"}` — only between turns
- `{type: "set_open_doc", path: str|null}` — target for Draft mode

**Server events** (stream during a turn):

- `turn_start{turn_number}` — server acks a client turn_start
- `delta{text}` — streaming token chunk from the assistant (append to the rendered assistant message)
- `tool_call{id, tool, arguments}` — LLM invoked a tool. Render as an inline collapsible card.
- `tool_result{id, data}` — tool returned. Render below the call.
- `cost_update{tokens_in, tokens_out, cost_usd, cumulative_usd}` — tick the cost meter
- `patch_proposed{patch_id, target_path, reason}` — LLM staged a patch. Animate into the right-side Pending panel.
- `turn_end{turn_number, title?}` — end of turn (title is populated after turn 2 auto-rename)
- `cancelled{turn_number}` — client cancelled this turn
- `error{code, message, recoverable}` — turn failed. If `recoverable=true`, the connection stays open for the next turn.

Event order in a normal turn: `turn_start` → `delta`* → (optional `tool_call` → `tool_result`) → `delta`* → (optional `patch_proposed`) → `cost_update` → `turn_end`.

### Rate limits

Two buckets: `patches` (20/min default) and `tokens` (100k/min default). When either is drained, calls return 429 with `Retry-After: <seconds>` header. The UI should show a discreet "rate limited — retrying in N seconds" toast and back off gracefully.

### Costs

Every LLM call costs money (fractions of a cent typically). The UI shows cumulative cost per turn, per day, per month. Hard budget caps (configurable) stop new calls — the UI must explain this clearly, not just say "request failed."

---

## Domain concepts

### Vault

A folder at `~/Documents/brain/`. Structure:

```
~/Documents/brain/
├── BRAIN.md              # user's system prompt / persona (editable)
├── research/             # domain 1
│   ├── index.md          # hand-curated + LLM-maintained index of the domain
│   ├── log.md            # append-only log of changes
│   ├── notes/            # concept notes (LLM-integrated)
│   ├── sources/          # raw ingested sources (one file per source)
│   ├── entities/         # per-person / per-org notes
│   ├── concepts/         # conceptual notes
│   ├── synthesis/        # user-written or chat-distilled syntheses
│   └── chats/            # saved chat threads (one file per thread)
├── work/                 # domain 2 (same shape)
├── personal/             # domain 3 (same shape, privacy-railed)
└── raw/                  # pre-classification inbox
    ├── inbox/
    ├── failed/
    └── archive/
```

Files are Markdown with YAML frontmatter. Everything is Obsidian-compatible. Wikilinks like `[[karpathy-llm-wiki]]` are first-class.

### Domains

Three domains by default: **research**, **work**, **personal**. The user can add more (future).

- **Research** and **work** are general-purpose.
- **Personal** is privacy-railed. It never appears in wildcard queries. The user has to explicitly opt in to "include personal" to see it in searches or chats.

Every screen that shows content must indicate **current scope** — which domains are visible. Scope switching is a core interaction.

### Patches

An LLM-proposed change to the vault. Patches have:
- `patch_id` — sortable timestamp-ish string
- `target_path` — the file being changed (or created)
- `reason` — plain-English why
- `tool` — which tool proposed it (`brain_propose_note`, `brain_ingest`, etc.)
- `mode` — which chat mode created it (for chat-originated patches)
- `created_at`

Patches are **metadata** in the pending queue. The **body** of a patch (actual diff) is fetched only when the user opens the patch card.

Patches transition: `pending` → `applied` OR `rejected`. Applied patches generate an `undo_id` that can revert them.

### Chats

A chat is a Markdown file at `<domain>/chats/<yyyy-mm-dd>-<slug>.md`. Frontmatter tracks `mode, scope, model, created, updated, turns, cost_usd`. Body is alternating `## User` / `## Assistant` sections. Tool calls render as fenced code blocks.

A thread belongs to one primary domain but can have scope over multiple domains during the conversation.

### File-to-wiki

During a chat, the user can click "File this to the wiki" on any assistant message. A dialog opens: pick domain, type (synthesis / concept / source note), edit the proposed path, review the LLM-distilled body, approve. On approve, a new vault note is created via the normal patch approval flow. The source chat thread gets a `filed_to` frontmatter pointer.

---

## Global layout

The app runs at `http://localhost:4317`. Every screen shares this frame:

```
┌─────────────────────────────────────────────────────────────────┐
│ [top bar]  domain switcher | mode switcher | cost | settings    │
├──────────────┬───────────────────────────────────┬──────────────┤
│ [left nav]   │ [main content — the current       │ [right panel]│
│              │  screen]                           │              │
│ Chat         │                                    │ context-     │
│ Inbox        │                                    │ sensitive    │
│ Browse       │                                    │              │
│ Pending ●    │                                    │              │
│ Bulk import  │                                    │              │
│ Settings     │                                    │              │
└──────────────┴───────────────────────────────────┴──────────────┘
```

### Top bar

- **Domain switcher** — dropdown or segmented control showing current domain scope. "research" / "work" / "research + work" / "+ personal (explicit)".
- **Mode switcher** — visible only on chat screens. Segmented control: Ask / Brainstorm / Draft.
- **Cost meter** — today's USD + daily budget gauge. Click → cost detail.
- **Settings gear** — opens Settings.

### Left nav

- **Chat** — thread list + new chat
- **Inbox** — drop zone for sources; watches `raw/inbox/`
- **Browse** — file tree + Markdown reader/editor
- **Pending changes** — with unread badge (count of pending patches)
- **Bulk import** — folder picker + dry-run review flow
- **Settings** — multiple tabs

### Right panel

Context-sensitive. On chat screens: pending patches for quick approve-in-place. On browse: metadata + backlinks. On other screens: hidden or empty.

---

## Screens to design

Six primary screens + setup wizard + global components. For each screen, design **all four states**: empty (first-time), loading, populated (happy path), error.

### 1. Chat

The most important screen. Daily driver.

**Purpose:** have a conversation with an LLM that has access to the user's vault.

**Layout regions:**
- Left sidebar: thread list (grouped by date, with titles + modes indicated)
- Center: active thread transcript (streaming)
- Bottom of center: composer (multiline input, mode+scope pill, attach button, send)
- Right panel: pending changes that this chat has created

**Key data:**
- Thread title (auto-generated after turn 2)
- Turn-by-turn transcript with alternating user/assistant
- Inline tool call cards (collapsible)
- Cost per turn + cumulative
- Active mode (Ask / Brainstorm / Draft)
- Active scope (which domains visible)

**Key interactions:**
- Streaming assistant response (delta events render character-by-character or word-by-word)
- Cancel mid-turn (button visible while streaming)
- Switch mode (between turns only; UI rejects mid-turn switch with a toast)
- "File this to the wiki" on any assistant message → opens file-to-wiki dialog
- Fork the thread from any turn → new thread with prior context copied in
- Export thread → pasteboard / file
- Attach a source to the thread → ingests + the result is available for the next turn
- Drag a file onto the composer → ingest + include
- Paste text or URL → ingest + include

**States:**
- **Empty:** no threads yet. Show a CTA like "Start your first brain chat" with big composer.
- **Loading:** streaming in-progress. Show typing indicator + cancel button.
- **Populated:** active thread, multiple messages.
- **Error:** backend disconnected ("brain is offline — [retry]"), turn failed mid-stream ("that turn didn't finish — [new turn]"), rate limited ("slow down — retry in 12 seconds"), out of budget ("daily budget exceeded — [open settings]").

**Design questions to explore:**
- How do mode switches communicate their behavior change? (Ask is conservative; Brainstorm is speculative; Draft is collaborative.)
- Where does scope live — per-thread, per-turn, or global?
- How do pending patches surface in the chat context without being noisy?
- How do tool calls render — fully expanded, collapsed by default, or somewhere in between?
- How is the "context used" meter shown (how much of the 200K LLM context window is filled)?

### 2. Inbox

**Purpose:** the user drops sources here. Sources get classified, summarized, integrated.

**Layout:**
- Prominent drop zone (large target area).
- Tabs: Pending (in-flight ingest) / In progress / Failed / Recent (completed)
- List below tabs: one row per source with status, domain, source type, progress

**Key data:**
- Source title (from ingest)
- Source type icon (URL, PDF, Email, Tweet, Text, Transcript)
- Classification result (domain + confidence)
- Status (queued / extracting / classifying / summarizing / integrating / done / failed)
- Cost per source

**Key interactions:**
- Drag-and-drop files onto the drop zone
- Paste text or a URL (Cmd-V anywhere)
- Click "browse" → file picker
- Click a failed item → retry or see error
- Click a done item → jump to its source note in Browse
- "Autonomous mode" toggle → auto-approve ingest patches without user review (a safety-critical setting; must be clearly explained)

**States:**
- **Empty:** no sources yet. Show the drop zone with "Drop files here, paste URLs, or [browse]"
- **Loading:** sources in flight. Per-source progress bars.
- **Populated:** history list.
- **Error:** specific failure cards ("Couldn't read this PDF (scanned without OCR)"; "URL timed out — [retry]"; "Classifier unsure — [pick domain]").

**Design questions:**
- What does classification ambiguity look like? (The classifier returns a confidence score and a `needs_user_pick` flag.)
- How does autonomous mode present its safety implications without being paranoid?
- Should there be a "preview before ingest" option for URLs / PDFs?

### 3. Pending changes

**Purpose:** the approval queue for every LLM-proposed vault mutation.

**Layout:**
- Header: count + bulk actions (approve all / reject all / select multiple)
- List of patch cards, newest first
- Each card: target path, reason, tool, source chat (if any), created_at
- Clicking a card opens a detail view with side-by-side diff (monaco read-only)
- Per-card actions: Approve / Approve-with-edits / Reject (with reason)
- Global "Autonomous mode" toggle at top right with clear off/on state + copy explaining what it does

**Key data:**
- Patch metadata (see API contract above)
- Patch body (diff) — loaded on demand
- Source context (if the patch came from a chat, link to that chat)
- File preview (what the vault looked like before vs after)

**Key interactions:**
- Click card → expand to show diff
- Approve → triggers `brain_apply_patch` → vault write + 5-second undo toast
- Approve with edits → opens an editor where user can tweak the patch before applying
- Reject → dialog with reason field (required)
- Bulk select + bulk approve / bulk reject
- Filter by tool, by source, by domain
- Click target path → jump to that path in Browse (once approved)

**States:**
- **Empty:** "Nothing pending" with calm affordance (maybe a sparkle icon — it means the LLM isn't proposing anything right now).
- **Loading:** patches being fetched.
- **Populated:** list of patches.
- **Error:** "couldn't load patches — [retry]" (rare — this should be very reliable).

**Design questions:**
- How is the autonomous-mode toggle distinguished from normal toggles (it has safety implications)?
- How do you prevent accidental approval? (Typed confirmation for bulk actions; debounced single-click approval?)
- What's the undo window UX — toast with countdown, persistent until dismissed?

### 4. Browse

**Purpose:** a file-tree-and-reader view of the vault.

**Layout:**
- Left: collapsible tree of the active domain (folders: notes, sources, entities, concepts, synthesis, chats)
- Center: rendered Markdown of the selected file + metadata strip (frontmatter key-values)
- Right: backlinks (notes that link to this one) + forward links (notes this one links to)
- Top of center: Edit toggle → switches to monaco Markdown editor with live preview

**Key data:**
- File tree of the current domain
- Rendered Markdown of current file
- Frontmatter
- Backlinks + outlinks (derived from wikilink graph)
- File mtime

**Key interactions:**
- Click a file in the tree → render in center
- Click a wikilink in the rendered view → jump to that note
- Click a backlink → jump
- Click Edit → enter monaco editor; Save triggers a patch (through approval flow OR autonomous depending on setting)
- Full-text search box at top (triggers `brain_search`)
- "Open in Obsidian" link via `obsidian://` URI scheme
- New note button → patch proposal

**States:**
- **Empty:** domain has no notes yet. Show "The research domain is empty. Drop a source in Inbox or start a chat in Brainstorm mode to seed it."
- **Loading:** loading a large file.
- **Populated:** file tree + reader.
- **Error:** "couldn't read that file" (frontmatter error fallback), "file not found" (stale link).

**Design questions:**
- How does search result UX flow — side panel, top overlay, full-screen search mode?
- How does edit mode communicate "you're editing the vault directly — no LLM in the loop"?
- How do wikilinks render when the target doesn't exist yet (red? italic? brackets visible)?

### 5. Bulk import

**Purpose:** ingest a whole folder of files (e.g. a year of meeting notes, a reading archive).

**Layout:**
- Step 1: pick a folder (native OS picker or drag)
- Step 2: pick a target domain (or "classify automatically")
- Step 3: dry-run review table — one row per file with columns: filename, type, classified domain, confidence, "include in import" checkbox
- Step 4: apply with streaming progress

**Key data:**
- Folder path
- Target domain (or auto-classify)
- Per-file plan (spec, slug, classified_domain, confidence)
- Per-file apply result (ok / quarantined / failed / skipped_duplicate)

**Key interactions:**
- Pick folder
- Pick target domain (dropdown) OR toggle "auto-classify"
- Dry-run runs — shows a table with ability to uncheck or re-route individual items
- Start import → progress bar, cancellable
- On completion → summary + link to see results in Browse

**States:**
- **Empty:** "Pick a folder of sources to import in bulk"
- **Loading (dry-run):** "Classifying 47 files…"
- **Populated (dry-run result):** review table with sort/filter
- **Loading (applying):** progress bar with "N of 47 applied"
- **Done:** summary card
- **Error:** specific per-file failures listed

**Design questions:**
- How does "max_files" cap surface (hard-stop: apply refuses on >20 files without explicit cap)?
- How does cancellation feel mid-apply (graceful stop vs immediate)?
- Can the user rescue partial imports?

### 6. Settings

**Purpose:** everything configurable.

**Layout:**
- Left sidebar: setting categories
- Right: form for the selected category

**Categories (tabs):**
1. **General** — app-level stuff (theme, sidebar behavior, etc.)
2. **LLM providers** — API keys, model choice per chat-mode (Ask/Brainstorm/Draft can use different models), default for ingest (which model summarizes vs integrates vs classifies)
3. **Budget & costs** — daily + monthly caps (hard stops), alert thresholds, cost breakdown by domain + by model
4. **Autonomous mode** — per-tool toggles for auto-apply vs always-stage. This is the most safety-critical settings panel; design for clarity.
5. **Integrations** — Claude Desktop status (installed? verified? regenerate config? remove) + copy-snippet for other MCP clients (Cursor, Zed, etc.)
6. **Domains** — list domains, add/remove a domain, reorder (affects default scope)
7. **BRAIN.md editor** — edit the vault's system prompt / persona. This is the user's voice for the LLM.
8. **Backups** — trigger a backup, list past backups, restore from backup

**States:**
- All standard form states per field (idle / focused / error / saved).
- Global "unsaved changes" banner if navigating away mid-edit.

**Design questions:**
- How is "daily budget exceeded" enforced in the user's mental model — a wall, a warning, a soft limit?
- Where does the API key go — is it ever visible to the user post-paste, or one-way write?
- How do autonomous-mode toggles communicate safety tradeoffs — each toggle is a small "I trust the LLM with this category of change"?

---

## Setup wizard

A full-screen first-run takeover. Six steps, all skippable where safe. The user has NEVER used brain before.

1. **Welcome** — explain what brain is, the local-first model, why the vault lives in `~/Documents/brain`. Offer "tell me more" + "let's go".
2. **Vault location** — confirm or change the default path. Default is good; advanced users can move it.
3. **LLM provider** — paste an Anthropic API key (for now; later: multiple providers). Test the key with a small ping. Link to "how do I get one?"
4. **First domain** — pick a starting theme (research / personal knowledge / work / start blank). This seeds `research/index.md` with a welcome note.
5. **BRAIN.md** — optional. Describe yourself to brain. A pre-filled template with editable fields (name, what you work on, how you like to be spoken to, topics you care about).
6. **Claude Desktop integration** — offer to install the MCP server into Claude Desktop's config. Skippable. Shows success state if Claude Desktop is detected; explains how to set up manually if not.

After setup: land on Chat with an empty thread and a composer primed with "What would you like to start with?"

**Design questions:**
- Wizards fail when they're too many steps or too few. Is six right? Could it be three (welcome, key, go)?
- How does the "skip this" affordance feel — does it imply "you'll regret it" or "no stress, configure later in Settings"?
- Setup is the highest-abandonment surface. Design specifically for non-technical confidence.

---

## Design principles

Distilled from the product and from `CLAUDE.md`. Follow these when making design trade-offs.

1. **Stage, then act.** Every vault change is staged first. The UI must make the "staged" state feel stable, not transient. No "just click OK to confirm" patterns for destructive actions — typed confirmation for deletes, 5-second undo for applied patches.
2. **Show the scope.** The current domain(s) must be visible on every screen. Switching scope is a deliberate action, never implicit.
3. **Surface cost.** Cumulative dollar cost is visible on every chat screen. Budget caps are real — the UI enforces them rather than explaining them post-hoc.
4. **Plain English, every time.** Error messages read like a human wrote them. "Couldn't reach Claude — check your API key in Settings" not "ConnectionError: 403 Forbidden".
5. **Non-technical first.** The user isn't a developer. No Markdown syntax exposed in the chat composer (use formatting controls). No path strings in UI unless the user asks for them. No "JSON validation failed" errors.
6. **Reversible by default.** Everything has an undo path within the most recent 5 seconds or via the Pending changes history. Nothing is silently destructive.
7. **Privacy-visible.** Personal domain is clearly distinguished (different color accent? padlock icon?). When it's in scope, the UI says so, every time.
8. **Calm, not cluttered.** This is a long-dwell app — the user spends hours here. Visual density matters. Breathing room is a feature.
9. **Obsidian-friendly.** Wikilinks render as wikilinks. The user can open any file in Obsidian at any time. Don't fight the underlying file format.
10. **Local-first feeling.** Loading states should be fast because everything is local. Empty states should feel like "ready when you are," not "server down."

---

## Voice, tone, microcopy

**Voice:** calm, competent, a little witty but never cute. Think: a smart colleague who respects your time. No exclamation points in error messages. No emoji in system UI (user-generated content can have whatever).

**Tone by context:**
- **First-run / setup:** friendly, reassuring. "This runs on your machine — nothing leaves unless you tell it to."
- **Empty states:** helpful nudges. "Drop a PDF here to get started." Not "No data! Add some!"
- **Success:** understated. "Added to research" not "GREAT SUCCESS!!!"
- **Warnings:** clear. "Daily budget exceeded. Turning off new calls until tomorrow or [raise cap]."
- **Errors:** blameless, actionable. "Couldn't reach Claude. Check your internet or [see logs]."
- **Dangerous actions:** specific. "Delete the 'personal' domain? Type 'DELETE' to confirm. This removes 237 notes permanently — no undo."

**Microcopy principles:**
- Button labels are verbs. "Approve" not "OK". "Cancel this turn" not "Stop".
- Field labels are nouns. "Source path" not "enter source path".
- Helper text explains, doesn't instruct. "Typically your Documents folder" not "please enter a valid path".
- Never say "please".
- Prefer "brain" (lowercase, product-as-noun) over "the brain" or "your brain".

---

## Accessibility

Target: **WCAG 2.2 AA** minimum. Non-negotiable requirements:

- **Keyboard navigation:** every screen is fully usable without a mouse. Tab order is logical (matches visual order). Shortcuts are documented and discoverable (press `?` shows a shortcut cheatsheet).
- **Focus indicators:** visible on every interactive element. Not just the browser default — a consistent custom outline that meets 3:1 contrast.
- **Screen reader labels:** every icon-only button has `aria-label`. Every form field has a linked label. Every custom widget declares its role.
- **Contrast:** 4.5:1 for body text, 3:1 for UI components + large text. Verify both light and dark modes.
- **Reduced motion:** respect `prefers-reduced-motion`. Streaming chat tokens should still appear, but swoosh/bounce animations disappear.
- **Errors announced:** form validation errors are announced to screen readers via `aria-live` regions.
- **Modal management:** focus trapped in modals; Escape closes; focus returns to the invoking element.
- **Color is never the only signal:** status (pending / applied / rejected / failed) uses an icon + a label, not just a color.
- **Zoom:** the app remains usable at 200% browser zoom (no horizontal scroll, text doesn't overlap).

Produce `docs/design/a11y.md` with:
- Keyboard shortcut map
- Focus order diagrams per screen
- Screen reader announcements for key actions (turn_start, patch_proposed, error)
- Reduced-motion specification

---

## Visual constraints

- **Desktop-first**, 1024 px minimum width. Design at 1440 px; verify at 1024 px minimum and 1920 px maximum.
- **Light + dark modes** for every mockup.
- **Tailwind + shadcn/ui.** Use shadcn primitives where they fit; design custom components only when shadcn doesn't cover the need.
- **Monaco editor** for code/Markdown editing (diff view, file editing). It has its own theming — match your design tokens.
- **No custom icon set unless necessary.** Use `lucide-react` (shadcn default). If you introduce a brand icon (logo, mark), keep it tiny and rare.
- **Typography:** one sans-serif for UI, one monospace for code/path strings. Pick system-safe stacks + one optional web font.
- **Rounded corners:** consistent scale. shadcn defaults are a good starting point.
- **Color palette:** start from shadcn's neutrals + one or two accent colors. Research/work/personal domains likely need distinguishing accents (without being garish).

Produce `docs/design/tokens.md` with:
- Color scales (light + dark, with labeled semantic names)
- Typography scale
- Spacing scale
- Radius scale
- Shadow scale
- Tailwind config diff
- shadcn theme JSON

---

## What NOT to design

- **Mobile / tablet layouts.** Out of scope.
- **Multi-user / team / permissions UI.** Single-user only.
- **Login / signup / account.** No accounts.
- **Billing / pricing.** Free, local-first, no commerce.
- **Cloud sync screens.** Vault is local; sync is the user's responsibility (Obsidian Sync, Dropbox, etc.).
- **Marketing / landing pages.** Design tool (this app) only. No `/about`, no `/pricing`.
- **Help center / knowledge base.** There's a docs site separately.
- **Admin / moderation tools.**
- **Onboarding emails.** No email, no push notifications.
- **Analytics dashboards.** Zero telemetry. If the user wants usage stats, they look at the cost ledger.

---

## Deliverables

Produce these artifacts in `docs/design/`:

1. **`tokens.md`** — design tokens + Tailwind config + shadcn theme
2. **`flows/`** — folder with IA map + key task flows (ingest, approve, chat turn, setup)
3. **`wireframes/`** — one file per screen with all states (empty/loading/populated/error)
4. **`mockups/`** — light AND dark hi-fi mockups per screen, all interaction states
5. **`components.md`** — component inventory with variants
6. **`a11y.md`** — accessibility plan (see Accessibility section above)
7. **`copy.md`** — microcopy strings for every surface

File format: your call. Markdown with embedded images works if you use a collaborative canvas (Figma, Sketch) and paste links + exports. Pure Markdown with ASCII/Mermaid is acceptable for flows + wireframes if images aren't available. Hi-fi mockups need to be renderable somehow (images or Figma links).

---

## Open design questions

Not exhaustive — these are the known forks where the spec doesn't pin a choice:

1. **Mode affordance.** Ask/Brainstorm/Draft share the composer. How is the mode-shift communicated visually? Color? Icon? Composer placeholder text change?
2. **Scope communication.** Is scope a per-screen concept (global top bar) or a per-surface concept (sidebar filter, composer pill)? Spec says "domain switcher" in the top bar but the interaction cost is high on long chat sessions.
3. **Pending-panel behavior during chat.** Pop in from the right when a patch is proposed mid-turn? Or stay stable and just badge?
4. **Autonomous-mode safety.** Single global toggle? Per-tool toggles? Per-domain? (Spec says it's configurable per tool; the UI must not trivialize it.)
5. **Cost display density.** Always visible in the top bar, even when the user doesn't care? Or minimized to a small dot that expands on hover?
6. **Thread list density.** How many threads can the user skim visually before needing search? Group by date vs by domain vs flat list?
7. **File-to-wiki dialog.** Modal overlay? Side panel? Inline expansion? (It's a frequent action — don't make it ceremonial.)
8. **Wikilink broken-link style.** Red? Bracketed? Ghost? Some signal that [[this-doesnt-exist]] is a future note, not a mistake.
9. **Empty-domain styling.** The personal domain may often be empty or near-empty. Does its empty state differ from research's?
10. **Onboarding density.** Six-step wizard vs progressive disclosure vs single long welcome screen. The user is non-technical but opinionated about privacy.

---

## Reference

If the designer wants deeper context:

- **Full design spec:** `docs/superpowers/specs/2026-04-13-cj-llm-kb-design.md` (in the repo)
- **Backend architecture details:** `CLAUDE.md` at repo root
- **API contract:** `packages/brain_api/src/brain_api/routes/tools.py` + `chat.py` + `brain_api/chat/events.py`
- **Tool schemas (live):** `GET /api/tools` on a running backend returns the authoritative INPUT_SCHEMA for every tool
- **Existing test vaults:** `packages/brain_api/tests/conftest.py::seeded_vault` shows a minimal realistic vault layout

---

**End of brief.** Start with the design system + tokens, then IA + flows, then wireframes for Chat and Pending changes (highest complexity), then the rest of the screens, then hi-fi mockups, then component inventory + a11y + copy.

Mockups should explicitly call out any deviation from this brief — the backend is fixed, the UI decisions aren't.
