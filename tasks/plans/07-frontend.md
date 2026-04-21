# Plan 07 — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **DRAFT — pending section-by-section review. Task-level steps are intentionally unfilled below the outline until the architecture / scope / decisions sections are approved.**

**Goal:** Ship `brain_web` — a Next.js 15 single-user web app that drives the `brain_api` REST + WebSocket surface with the v3-approved design. After this plan, `brain` is a usable product: the user opens `http://localhost:4317`, completes setup, and starts ingesting + chatting.

**Architecture:**
Plan 07 adds one new workspace member (`apps/brain_web/`) and makes a set of strictly-additive backend extensions in Group 1 (per-category autonomy, per-mode chat models, cost ledger tagging, Draft-mode WS event, new tools, fork helper). Frontend is Next.js 15 App Router, server-side auth (Next.js server reads `.brain/run/api-secret.txt`, browser never sees the raw token), WebSocket client pinned to `SCHEMA_VERSION = "2"`. UI follows the approved v3 design (light + dark, Tailwind + shadcn/ui, TomorrowToday color tokens, Roboto typography).

- REST: typed `apiFetch<T>` client with one handler per tool type, proxied through Next.js API route (`/api/proxy/[...path]`)
- WebSocket: typed event client with auto-reconnect, pinned to v2
- State: Zustand for app state (theme, mode, scope, active thread, transcript, pending patches, etc.); React Query for server state (tools listing, cost, notes)
- Routing: App Router with dynamic segments for `chat/[thread_id]`, `browse/[...path]`, `settings/[tab]`
- Auth: filesystem-token read in a Next.js API route (`/api/proxy/*`); browser-side JS never sees the raw token
- Design: approved artifacts at `docs/design/` (design brief + 2 delta passes + v3 zip); frontend implements them pixel-true

**Tech stack (new deps):**
- `next@15` — App Router + React Server Components
- `react@18`, `react-dom@18`
- `typescript@5.5+`
- `tailwindcss@3.4+` + `postcss` + `autoprefixer`
- `@radix-ui/react-*` (via shadcn/ui) — dialog, popover, select, toggle-group, etc.
- `lucide-react` — icon set (shadcn default)
- `zustand@4` — client state
- `@tanstack/react-query@5` — server state
- `monaco-editor` + `@monaco-editor/react` — Browse edit mode + BRAIN.md editor
- `playwright` — e2e tests
- `vitest` + `@testing-library/react` — unit tests
- `axe-core` + `@axe-core/playwright` — a11y gate

**Demo gate:** `uv run python scripts/demo-plan-07.py` runs end-to-end against a temp vault + `FakeLLMProvider`:
1. Spawn `brain_api` via ASGITransport (Plan 05 pattern)
2. Spawn Next.js in production build via subprocess on a free port
3. Playwright drives: setup wizard, drag-drop ingest, chat turn with mode switch, pending approval, bulk dry-run, fork thread, settings panel change
4. Assert no console errors, no a11y violations (axe-core), all WS events received in order
5. Capture screenshot receipt for review

Prints `PLAN 07 DEMO OK` on exit 0. Cross-platform sweep runs on Mac + Windows via CI matrix.

**Owning subagents:**
- `brain-core-engineer` — Group 1 backend extensions (Tasks 1–5)
- `brain-frontend-engineer` — Groups 2–5 frontend work (Tasks 6–22)
- `brain-test-engineer` — Group 6 Playwright + cross-platform + demo + close (Tasks 23–25)

**Pre-flight** (main loop, before Task 1):
- Confirm `plan-05-api` tag exists at `origin/main` (it does)
- Confirm `docs/design/` contents:
  - `design-brief.md` (baseline)
  - `design-delta.md`, `design-delta-v2.md` (iterations)
  - `plan-07-preflight.md` (decisions D1a/D2a/D3a/D4a/D5a pinned)
  - v3 design zip extracted somewhere accessible for pixel reference
- Decide on P1–P8 below (Plan-07-specific decisions)

---

## Scope — in and out

**In scope for Plan 07:**
- **Backend extensions** (strictly additive, Group 1): `PatchSet.category` + autonomy gate, per-mode chat models, cost ledger mode/stage tagging, `cumulative_tokens_in` on `CostUpdateEvent`, `DocEditChatEvent` + `doc_edit_proposed` WS event, `SCHEMA_VERSION = "2"`, 4 new tools (`brain_recent_ingests`, `brain_create_domain`, `brain_rename_domain`, `brain_budget_override`), `BulkPlan.items[].duplicate`, `ChatSession.fork_from()` with summary helper, 12 new `_SETTABLE_KEYS` entries
- **`apps/brain_web/`** new workspace package: Next.js 15 + TypeScript + Tailwind + shadcn/ui + Roboto fonts + TT color tokens
- Server-side auth proxy (Next.js API route reads `.brain/run/api-secret.txt`)
- Typed API client + WS client (v2-pinned) with auto-reconnect
- 6 primary screens: Chat, Inbox, Pending, Browse, Bulk import, Settings
- Setup wizard (6 steps + auto-detect first-run)
- Global shell: top bar (scope picker, mode switcher, cost meter, theme toggle, rail toggle, settings gear), left nav (threads grouped by date, workspace nav), right rail (context-sensitive: pending patches / linked notes)
- All system overlays: Modal, RejectReason, EditApprove, TypedConfirm, FileToWiki, Fork, RenameDomain, OfflineBanner, BudgetWall, MidTurnToast, DropOverlay, ConnectionIndicator
- Draft mode: DocPicker + DocPanel + inline edit rendering from `doc_edit_proposed`
- Light + dark themes (data-theme attribute on `<html>`)
- Density (comfortable / compact) persisted to localStorage
- WCAG 2.2 AA compliance (axe-core gate)
- Playwright e2e for 5 primary flows
- Vitest unit tests for utility fns + hooks + typed client
- Cross-platform sweep (Mac + Windows)
- 14-gate demo script

**Explicitly out of scope** (deferred):
- **Mobile / tablet responsive** — 1024px minimum, desktop-first (spec §8)
- **OS keychain integration** — plain-text `.brain/secrets.env` stays; keyring library is Plan 09 polish
- **Live broken-wikilink detection** — frontend uses a client-side set; `brain_wikilink_status` tool is deferred
- **Vector DB / embeddings** — spec §6 explicit prohibition
- **Multi-user / permissions** — single-user only
- **Login / signup / billing** — no auth UI
- **Cloud sync** — Obsidian Sync etc. are the user's problem
- **Marketing pages** — app only; no `/about` / `/pricing`
- **Help center / knowledge base** — docs site separate
- **Progressive rollout / feature flags / A/B testing** — single-target
- **Analytics / telemetry** — zero telemetry per CLAUDE.md principle #10
- **"Recent ingests" sourced from filesystem walk** — use `brain_recent_ingests` tool added in Task 4
- **Advanced Draft-mode features** — single-doc collaboration only; no multi-doc open, no collaborative editing, no version history beyond UndoLog
- **`brain start` process management** — Plan 08. Plan 07's demo runs uvicorn + Next.js manually or via test harness.

---

## Decisions pinned (from `plan-07-preflight.md` — D1a through D5a)

Five pre-flight decisions are already locked. Repeated here for task-authoring context:

| # | Decision | Choice |
|---|---|---|
| D1a | Draft-mode WS event shape | New `doc_edit_proposed` event (separate from `patch_proposed`); bumps `SCHEMA_VERSION` to `"2"` |
| D2a | Rename-domain execution | Atomic `brain_rename_domain` tool with single UndoLog entry (bypasses PatchSet machinery) |
| D3a | Fork carry-context options | Ship all three (summary/full/none); summary via new `brain_core.chat.fork.summarize_turns` Haiku helper |
| D4a | Ephemeral budget override | `budget.override_until` + `budget.override_delta_usd` config pair + `brain_budget_override` tool |
| D5a | Context-fill metric | `cumulative_tokens_in` on `CostUpdateEvent`; frontend derives ratio from 200k window |

See `docs/design/plan-07-preflight.md` §1–§4 for implementation details.

---

## Decisions needed (Plan 07-specific — block Task 1)

Eight forks specific to the frontend. Recommendations marked **(rec)**.

### P1 — Monorepo structure: `apps/` vs `packages/`?

Spec §3 puts `brain_web` under `apps/` ("Next.js 15 + TypeScript + Tailwind + shadcn/ui"). Current workspace uses `packages/` for all Python members. Mixing `apps/` + `packages/` is fine (Turborepo convention) but adds a wrinkle to root `pyproject.toml` globs.

- **(rec) P1a** — put `brain_web` at `apps/brain_web/`, matching spec §3. Root `pyproject.toml` `members` stays `["packages/*"]`. Node workspace (if any) is a separate root `package.json`.
- **P1b** — put it at `packages/brain_web/` to match Python convention. Spec mismatch; easier root layout.

**Recommendation: P1a.** Matches spec. One-time root `pyproject.toml` globbing is trivial.

### P2 — Client state management

- **(rec) P2a** — Zustand for client state (theme, mode, scope, rail state, sys overlays) + React Query for server state (tool listings, cost report, notes). Two libraries, each specialized. Matches design-tool prototype's reducer pattern via Zustand.
- **P2b** — All React Context + useReducer. Zero dependencies beyond React; more boilerplate.
- **P2c** — Redux Toolkit + RTK Query. Heavier; established patterns; unnecessary.

**Recommendation: P2a.** Minimal deps, matches the prototype's shape.

### P3 — WebSocket client architecture

- **(rec) P3a** — One long-lived WS connection per active chat thread. Connection opens when thread becomes active, closes on thread switch (or app close). State lives in a `useWebSocket(threadId)` hook. Plan 05 WS is one-connection-per-thread by design.
- **P3b** — Single multiplexed WS for all threads. Frontend routes events by thread_id. Matches Plan 05 Checkpoint 6 discussion about concurrency, but backend WS endpoint is `/ws/chat/<thread_id>` — one per thread is more natural.

**Recommendation: P3a.** Matches backend contract.

### P4 — UI component library: pure shadcn/ui vs wrapped in custom

- **(rec) P4a** — Generate shadcn/ui primitives into `src/components/ui/` (shadcn's standard flow — copy-paste components), then build custom components (PatchCard, DocPanel, etc.) that compose them. Design tokens in `src/styles/tokens.css`.
- **P4b** — Radix primitives directly + custom Tailwind. Skip shadcn. More control; more work.

**Recommendation: P4a.** shadcn/ui is the spec-named stack; no reason to deviate.

### P5 — Monaco editor delivery

- **(rec) P5a** — `@monaco-editor/react` + lazy-import. Monaco is ~2MB; only load when Browse edit mode or BRAIN.md editor opens. Register custom theme matching TT tokens at first-load.
- **P5b** — `react-codemirror` instead. Lighter but less featureful. Matches VS Code expectations worse.
- **P5c** — Plain `<textarea>` for MVP, swap later. Regresses from v3 design.

**Recommendation: P5a.** Matches spec §8 and v3 design explicitly showing Monaco-style UI.

### P6 — Testing scope — how deep?

- **(rec) P6a** — Vitest unit tests for: typed API client, WS event parsing, reducers/hooks, utility fns. React Testing Library for: dialog components, Composer interactions, DocPanel rendering. Playwright for: 5 end-to-end primary flows (setup wizard, ingest drag-drop, chat turn, patch approval, bulk dry-run). Axe-core on every Playwright page.
- **P6b** — Playwright only. Skips unit layer. Faster initial; slower feedback when a hook regresses.
- **P6c** — Vitest only. Skips e2e. Unit tests can't catch full-stack wiring bugs.

**Recommendation: P6a.** Three-layer test pyramid matches Plans 01–05.

### P7 — Dev environment: Next.js dev server vs static export?

- **(rec) P7a** — Next.js dev server (`next dev`) during development. Production build (`next build && next start`) for demo and Plan 08 distribution. SSR for the auth proxy route; everything else can be static-friendly.
- **P7b** — Static export (`output: "export"`). No auth proxy possible (static can't read filesystem at runtime). Would need to expose the token to the browser. Rejects the core auth-security model.

**Recommendation: P7a.** The `/api/proxy/*` route needs server runtime for secret-token filesystem read.

### P8 — Plan 08 handoff assumption — `brain start` launches Next.js how?

- **(rec) P8a** — Plan 08's `brain start` launches TWO subprocesses: uvicorn for `brain_api` on port 4317, and `next start` for `brain_web` on port 4316 (or whatever Next.js picks). `brain_web` proxies `/api/proxy/*` to `127.0.0.1:4317`. User's browser opens `http://localhost:4316`. Plan 07 ships the production build; Plan 08 wraps the launcher.
- **P8b** — Serve static-exported Next.js from within brain_api itself (mounted at `/ui`). Avoids two processes. Breaks SSR for the proxy route — can't do.

**Recommendation: P8a.** Clean separation; P7a reinforces this.

---

## File structure produced by this plan

```
apps/                                # NEW top-level directory (spec §3)
└── brain_web/                       # NEW workspace member
    ├── package.json
    ├── next.config.mjs
    ├── tsconfig.json
    ├── tailwind.config.ts
    ├── postcss.config.mjs
    ├── components.json               # shadcn/ui config
    ├── public/
    │   ├── fonts/                    # Roboto family (copied from v3 design zip)
    │   └── assets/                   # logo, color-orbs.png
    ├── src/
    │   ├── app/                      # Next.js 15 App Router
    │   │   ├── layout.tsx            # root layout + global shell + theme + system overlays
    │   │   ├── page.tsx              # redirect to /chat or /setup
    │   │   ├── chat/
    │   │   │   ├── page.tsx          # empty state + new-chat
    │   │   │   └── [thread_id]/page.tsx
    │   │   ├── inbox/page.tsx
    │   │   ├── browse/
    │   │   │   ├── page.tsx
    │   │   │   └── [...path]/page.tsx
    │   │   ├── pending/page.tsx
    │   │   ├── bulk/page.tsx
    │   │   ├── settings/
    │   │   │   ├── page.tsx          # redirect to /settings/general
    │   │   │   └── [tab]/page.tsx
    │   │   ├── setup/page.tsx        # 6-step wizard (first-run takeover)
    │   │   └── api/
    │   │       └── proxy/
    │   │           └── [...path]/route.ts   # server-side token read + HTTP proxy
    │   ├── components/
    │   │   ├── ui/                   # shadcn-generated: button, dialog, popover, select, etc.
    │   │   ├── shell/                # Topbar, LeftNav, RightRail, SystemOverlays
    │   │   ├── chat/                 # Message, ToolCall, Composer, NewThreadEmpty
    │   │   ├── draft/                # DocPicker, DocPanel, doc-edit rendering
    │   │   ├── pending/              # PatchCard, PatchDetail, DiffView
    │   │   ├── dialogs/              # RejectReason, EditApprove, TypedConfirm, FileToWiki, Fork, RenameDomain
    │   │   ├── system/               # OfflineBanner, BudgetWall, MidTurnToast, DropOverlay, ConnectionIndicator
    │   │   ├── inbox/                # DropZone, SourceRow, Tabs
    │   │   ├── browse/               # FileTree, Reader, SearchOverlay, MonacoEditor, WikilinkHover
    │   │   ├── bulk/                 # Stepper, DryRunTable, ApplyProgress
    │   │   ├── settings/             # 8 panels
    │   │   └── setup/                # Wizard steps
    │   ├── lib/
    │   │   ├── api/                  # apiFetch, typed tool bindings
    │   │   ├── ws/                   # WS client (v2), event types, reconnect
    │   │   ├── auth/                 # server-side token read (used in route.ts)
    │   │   ├── state/                # Zustand stores
    │   │   └── utils/                # formatting, cn() (shadcn)
    │   └── styles/
    │       ├── globals.css
    │       └── tokens.css            # TT color tokens + dark/light
    ├── tests/
    │   ├── e2e/                      # Playwright
    │   │   ├── setup-wizard.spec.ts
    │   │   ├── ingest-drag-drop.spec.ts
    │   │   ├── chat-turn.spec.ts
    │   │   ├── patch-approval.spec.ts
    │   │   └── bulk-import.spec.ts
    │   └── unit/                     # Vitest
    │       ├── api-client.test.ts
    │       ├── ws-event-parser.test.ts
    │       └── (components).test.tsx
    └── playwright.config.ts

packages/brain_core/src/brain_core/
├── autonomy.py                       # NEW — should_auto_apply(patchset, config)
├── chat/
│   ├── session.py                    # MODIFIED: per-mode models + Draft DocEditChatEvent
│   └── fork.py                       # NEW — fork_from + summarize_turns helper
├── cost/ledger.py                    # MODIFIED: mode + stage tagging + by_mode summary
├── vault/types.py                    # MODIFIED: PatchSet.category field
├── ingest/bulk.py                    # MODIFIED: BulkItem.duplicate field
└── tools/
    ├── recent_ingests.py             # NEW
    ├── create_domain.py              # NEW
    ├── rename_domain.py              # NEW (atomic via UndoLog)
    ├── budget_override.py            # NEW
    ├── apply_patch.py                # MODIFIED: consults should_auto_apply
    └── config_set.py                 # MODIFIED: 12 new keys

packages/brain_mcp/src/brain_mcp/tools/
├── recent_ingests.py                 # NEW (shim)
├── create_domain.py                  # NEW (shim)
├── rename_domain.py                  # NEW (shim)
└── budget_override.py                # NEW (shim)

packages/brain_api/src/brain_api/chat/
├── events.py                         # MODIFIED: DocEditProposedEvent; SCHEMA_VERSION = "2"
└── session_runner.py                 # MODIFIED: maps DocEditChatEvent → WS

scripts/
└── demo-plan-07.py                   # 14-gate demo driving the live frontend

docs/design/
├── (existing design brief + deltas + pre-flight — unchanged)
└── screenshots/                      # demo receipts captured during QA

docs/testing/
└── manual-qa.md                      # cross-platform manual QA checklist

pyproject.toml                        # unchanged (Python packages) — Node workspace is separate
package.json                          # NEW root Node workspace
```

---

## Per-task self-review checklist

Same 12-point discipline as Plans 01–05 plus frontend specifics:

1. `export PATH="$HOME/.local/bin:$PATH"`
2. New submodule? → `uv sync --reinstall-package <pkg>`. New Node package? → `cd apps/brain_web && pnpm install` (or npm).
3. `uv run pytest packages/brain_core packages/brain_cli packages/brain_mcp packages/brain_api -q` — full Python suite green
4. `cd packages/<pkg> && uv run mypy src tests` — strict clean (run from package dir)
5. `cd apps/brain_web && pnpm type-check` (or `tsc --noEmit`) — clean
6. `cd apps/brain_web && pnpm test -- --run` — Vitest unit tests green
7. `cd apps/brain_web && pnpm playwright test` — Playwright e2e green
8. `uv run ruff check . && uv run ruff format --check .` — clean
9. `cd apps/brain_web && pnpm lint` — ESLint clean
10. `find .venv -name "* [0-9].py"` — empty
11. No Anthropic SDK imports outside `brain_core/llm/providers/anthropic.py`
12. No vault writes outside `VaultWriter`; no `scope_guard` bypasses
13. `git status` clean after commit; commit message matches the task's convention

---

## Task outline (details intentionally unfilled pending section review)

**25 tasks in 6 groups, 5 checkpoints.** Mirrors Plans 04/05's shape.

### Group 1 — Backend extensions (Tasks 1–5)
- [ ] **Task 1 — Autonomy gate + `PatchSet.category` + config keys** (`brain_core.autonomy.should_auto_apply`, 5 new `autonomous.*` config keys, `brain_apply_patch` wires the gate, `brain_mcp` shim updated)
- [ ] **Task 2 — Per-mode chat models + `DocEditChatEvent`** (3 new `*_model` config keys, `ChatSession` selects model by mode, new `ChatEventKind.DOC_EDIT` emitted by Draft-mode responses)
- [ ] **Task 3 — Cost ledger mode/stage tagging + `cumulative_tokens_in`** (`CostEntry.{mode,stage}` optional fields, `CostSummary.by_mode` dict, `CostUpdateEvent.cumulative_tokens_in` int, all call sites updated)
- [ ] **Task 4 — 4 new tools + `BulkPlan.duplicate`** (`brain_recent_ingests`, `brain_create_domain`, `brain_rename_domain`, `brain_budget_override`; state.sqlite migration for ingest history; `BulkImporter.plan` sets `duplicate: bool`; `_SETTABLE_KEYS` gains 12 new keys; 4 brain_mcp shims)
- [ ] **Task 5 — `ChatSession.fork_from` + `doc_edit_proposed` WS event + SCHEMA_VERSION=2** (`brain_core.chat.fork.fork_from(source_id, turn, carry, mode, …)` + `summarize_turns(turns, llm) -> str` helper; `brain_api.chat.events.DocEditProposedEvent`; bump `SCHEMA_VERSION = "2"`; `SessionRunner._convert_chat_event` maps DOC_EDIT kind)

**Checkpoint 1 after Task 5:** backend surface complete. Plan 07 Phase C+D starts from here.

### Group 2 — Frontend foundation (Tasks 6–10)
- [ ] **Task 6 — `apps/brain_web/` Next.js 15 package skeleton** (package.json, tsconfig, next.config, tailwind.config, postcss, components.json, `/app/layout.tsx` + `/app/page.tsx` + redirect-to-chat, root Node workspace glue, README)
- [ ] **Task 7 — Design tokens + theme + shadcn/ui install** (Roboto fonts under `/public/fonts/`, `tokens.css` with TT palette + light/dark via `data-theme`, density via `data-density`, install shadcn primitives: button, dialog, popover, select, toggle-group, tabs, input, textarea, checkbox, switch, separator)
- [ ] **Task 8 — Auth proxy route** (`/api/proxy/[...path]/route.ts` — server-side reads `.brain/run/api-secret.txt`, attaches `X-Brain-Token`, forwards to `brain_api` at `http://127.0.0.1:4317`, strips sensitive headers on response; rejects if token file missing → returns 503 with setup-required payload)
- [ ] **Task 9 — Typed API client + WS client (v2-pinned)** (`lib/api/client.ts` typed `apiFetch<T>`; `lib/api/tools.ts` per-tool bindings derived from OpenAPI; `lib/ws/client.ts` WS client with SCHEMA_VERSION pin, typed event parsing, auto-reconnect with exponential backoff)
- [ ] **Task 10 — Global shell** (Topbar, LeftNav, RightRail components; App Router integration; Zustand stores for theme/mode/scope/view/rail; render system overlays in layout.tsx)

**Checkpoint 2 after Task 10:** shell renders; empty routes navigate; auth proxy works; WS client connects.

### Group 3 — Dialog system + setup (Tasks 11–13)
- [ ] **Task 11 — Dialog primitives** (Modal base, RejectReasonDialog, EditApproveDialog, TypedConfirmDialog, all wired through a central SystemOverlays host)
- [ ] **Task 12 — System overlays** (OfflineBanner, BudgetWall with session breakdown + model-switch hint, MidTurnToast with 5 kinds including invalid-state-turn + invalid-state-mode, DropOverlay, ConnectionIndicator in topbar)
- [ ] **Task 13 — Setup wizard** (6 steps: Welcome, Vault location, LLM provider, Starting theme, BRAIN.md, Claude Desktop integration; auto-detect first-run — skip wizard if `BRAIN.md` exists AND API key set; route to `/setup` from `/` when needed)

**Checkpoint 3 after Task 13:** plumbing works; all dialogs rendered; setup wizard functional against real backend.

### Group 4 — Core screens (Tasks 14–18)
- [ ] **Task 14 — Chat transcript + streaming** (Message component, ToolCall collapsible cards, inline patch-proposed card, msg-actions (File/Fork/Copy/Quote), NewThreadEmpty with mode-specific starters)
- [ ] **Task 15 — Chat composer + WS wiring** (Composer with mode + scope chips + context meter + attach + send/cancel; WS `turn_start` message; stream `delta` events into streamingText; handle `tool_call`/`tool_result`/`cost_update`/`patch_proposed`/`turn_end`; route invalid-state errors to MidTurnToast)
- [ ] **Task 16 — Pending screen** (list with filter chips, PatchCard with domain accent + isNew bell, PatchDetail pane with DiffView + target path + reason + from-thread chip + per-patch actions; Approve-all / Reject-all loop; Undo-last header button; EditApprove modal flow)
- [ ] **Task 17 — Inbox screen** (DropZone with drag-and-drop + paste-URL + browse-files; tabs: In progress / Needs attention / Recent; SourceRow with type icon + domain chip + status + progress bar; Autonomous ingest toggle bound to `autonomous.ingest` config)
- [ ] **Task 18 — Browse screen** (FileTree grouped by domain; Reader with frontmatter + body + meta strip; ⌘K SearchOverlay calling brain_search; Monaco editor for edit mode + "Save as patch" flow; WikilinkHover popover; Obsidian link button; backlinks/outlinks in right rail)

**Checkpoint 4 after Task 18:** daily-driver flows work end-to-end against live backend.

### Group 5 — Specialized flows (Tasks 19–22)
- [ ] **Task 19 — Draft mode** (DraftEmpty component; DocPickerDialog with fuzzy filter + new-blank-scratch; DocPanel rendering inline `doc_edit_proposed` events as highlighted regions; Apply/Discard routes through `brain_apply_patch` if `autonomous.draft=false`, else applies directly)
- [ ] **Task 20 — FileToWiki + Fork + RenameDomain dialogs** (FileToWiki with note-type picker + path builder + collision detection + frontmatter preview; Fork with source-summary card + all three carry options + title hint; RenameDomain with rewrite-frontmatter checkbox)
- [ ] **Task 21 — Bulk import 4-step flow** (Stepper (Pick → Scope → Dry-run → Apply); DryRunTable with per-file checkbox + route-to + confidence bar + duplicate/uncertain/sensitive flags; ApplyProgress with per-file state + cancel-after-current-file; refusal UX for > 20 files without max_files)
- [ ] **Task 22 — Settings: 8 panels** (General, Providers with per-stage model table + test-connection, Budget with caps + alert threshold, Autonomous mode per-category toggles, Integrations with Claude Desktop status + MCP snippet, Domains with drag-reorder + add + delete + rename, BRAIN.md Monaco editor with Save-as-patch, Backups with trigger + list + restore)

**Checkpoint 5 after Task 22:** entire app surface live. Manual pass-through of every screen + dialog.

### Group 6 — QA + demo + close (Tasks 23–25)
- [ ] **Task 23 — Playwright e2e + axe-core a11y** (5 e2e specs: setup wizard, ingest drag-drop, chat turn, patch approval, bulk dry-run; axe-core on every page asserting 0 violations at AA level; CI matrix Mac + Windows)
- [ ] **Task 24 — Cross-platform sweep + `scripts/demo-plan-07.py` (14 gates) + `docs/testing/manual-qa.md`** (cross-platform: path handling, line endings, Windows-reserved filenames, Next.js build on both OS; 14 gates match the demo brief; manual QA checklist documents how to exercise flows not covered by Playwright)
- [ ] **Task 25 — Hardening sweep + coverage + tag `plan-07-frontend`** (Batch A behavior fixes from tracked deferrals; Batch B comments + TODO cleanup; Batch C lessons-only; coverage targets: brain_web ≥ 75% (components + lib), brain_core regression ≥ 94%; tag locally, close commit)

---

## Module-boundary checkpoints

Five review pause points:

1. **After Task 5** — backend complete; frontend implementation starts from stable ground
2. **After Task 10** — foundation (package + tokens + auth + client + shell) frozen before dialogs
3. **After Task 13** — plumbing + setup wizard functional against real backend
4. **After Task 18** — daily-driver chat/pending/inbox/browse flows live
5. **After Task 22** — entire app surface live; ready for QA
6. **After Task 25** — plan close, tag, demo receipt

---

## Detailed per-task steps

*Intentionally unfilled. After the outline, decisions, and file structure are approved, I will fill in per-task bite-sized steps (test-first, exact code, exact commands, expected output) group-by-group following Plans 04/05's rhythm.*
