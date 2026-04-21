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

### Group 1 — Backend extensions (Tasks 1–5)

**Pattern:** every task in Group 1 is strictly additive to Plans 01–05. Hard gate at Checkpoint 1: all prior tests (brain_core ~427, brain_cli 30, brain_mcp 99, brain_api 129 = 685 passed + 11 skipped as of `plan-05-api`) stay green. New tests land alongside new code.

---

### Task 1 — `PatchSet.category` + autonomy gate + 5 config keys

**Owning subagent:** brain-core-engineer

**Files:**
- Modify: `packages/brain_core/src/brain_core/vault/types.py` — add `PatchCategory` `StrEnum` + `PatchSet.category: PatchCategory = PatchCategory.OTHER` field
- Create: `packages/brain_core/src/brain_core/autonomy.py` — `should_auto_apply(patchset, config) -> bool`
- Modify: `packages/brain_core/src/brain_core/tools/apply_patch.py` — consult `should_auto_apply` gate before staging
- Modify: `packages/brain_core/src/brain_core/tools/config_set.py` — add 5 `autonomous.*` entries to `_SETTABLE_KEYS`
- Modify: `packages/brain_core/src/brain_core/tools/ingest.py` — set `patchset.category = PatchCategory.INGEST` before return
- Modify: `packages/brain_core/src/brain_core/tools/propose_note.py` — derive category from target path (`<dom>/entities/*` → ENTITIES, `<dom>/concepts/*` → CONCEPTS, `<dom>/index.md` → INDEX_REWRITES, else OTHER)
- Modify: `packages/brain_core/src/brain_core/config/schema.py` — add `autonomous: AutonomousConfig` nested model with 5 bool fields (default False each)
- Create: `packages/brain_core/tests/test_autonomy.py` — 6 tests (gate honors each category, missing category defaults to False, `brain_apply_patch` skips staging when gate True, skips if disabled, full flow via MCP shim preserves Plan 04 inline-JSON on rate-limit)
- Create: `packages/brain_core/tests/tools/test_patch_category.py` — 2 tests (propose_note derives category from path; ingest sets INGEST)

**Context for the implementer:**

The autonomy gate is the single architectural piece that lets design's 4 autonomy toggles work. Shape:

```python
# brain_core/vault/types.py
from enum import StrEnum

class PatchCategory(StrEnum):
    INGEST = "ingest"
    ENTITIES = "entities"
    CONCEPTS = "concepts"
    INDEX_REWRITES = "index_rewrites"
    DRAFT = "draft"
    OTHER = "other"


class PatchSet(BaseModel):
    # ... existing fields ...
    category: PatchCategory = PatchCategory.OTHER  # NEW, defaults to OTHER so Plan 04 call-sites don't regress
```

```python
# brain_core/autonomy.py
"""Autonomy gate — consulted by brain_apply_patch before staging.

Returns True if the given patchset should apply directly without going
through the Pending queue. Plan 04 default: always False (all patches stage).
Plan 07 extends: per-category config key can enable auto-apply.
"""

from __future__ import annotations

from brain_core.config.schema import Config
from brain_core.vault.types import PatchCategory, PatchSet


def should_auto_apply(patchset: PatchSet, config: Config) -> bool:
    """Consult config.autonomous.<category> for the patch's category.

    Returns False if the config key is unset or False. Returns False for
    PatchCategory.OTHER (never auto-apply uncategorized patches — safety).
    """
    if patchset.category == PatchCategory.OTHER:
        return False
    key = patchset.category.value  # "ingest" / "entities" / ...
    return bool(getattr(config.autonomous, key, False))
```

```python
# brain_core/config/schema.py — add alongside existing BudgetConfig
class AutonomousConfig(BaseModel):
    ingest: bool = False
    entities: bool = False
    concepts: bool = False
    index_rewrites: bool = False
    draft: bool = False

class Config(BaseModel):
    # ... existing ...
    autonomous: AutonomousConfig = Field(default_factory=AutonomousConfig)
```

**`brain_apply_patch` wiring:**

```python
# brain_core/tools/apply_patch.py
# Before staging via ctx.pending_store.put(...):
from brain_core.autonomy import should_auto_apply
from brain_core.config.loader import load_config  # or however the tool currently resolves config

config = load_config(vault_root=ctx.vault_root)
if should_auto_apply(envelope.patchset, config):
    receipt = ctx.writer.apply(envelope.patchset, allowed_domains=(domain,))
    ctx.pending_store.mark_applied(envelope.patch_id)
    return ToolResult(
        text=f"auto-applied patch {envelope.patch_id} → {len(receipt.applied_files)} file(s)",
        data={
            "status": "auto_applied",
            "patch_id": envelope.patch_id,
            "undo_id": receipt.undo_id,
            "applied_files": [p.as_posix() for p in receipt.applied_files],
        },
    )
# else: existing stage-via-pending-store path (Plan 04 unchanged)
```

**`brain_propose_note` category derivation:**

```python
# brain_core/tools/propose_note.py
from brain_core.vault.types import PatchCategory, PatchSet, NewFile

def _category_for_path(path: Path) -> PatchCategory:
    parts = path.parts
    if len(parts) < 2:
        return PatchCategory.OTHER
    # <domain>/<subdir>/<slug>.md — parts[1] is the subdir
    subdir = parts[1]
    if subdir == "entities":
        return PatchCategory.ENTITIES
    if subdir == "concepts":
        return PatchCategory.CONCEPTS
    if path.name == "index.md":
        return PatchCategory.INDEX_REWRITES
    return PatchCategory.OTHER

# Inside handle():
patchset = PatchSet(
    new_files=[NewFile(path=p, content=content)],
    reason=reason,
    category=_category_for_path(p),
)
```

### Step 1 — Failing test

Create `packages/brain_core/tests/test_autonomy.py`:

```python
"""Tests for brain_core.autonomy.should_auto_apply."""

from __future__ import annotations

from pathlib import Path

import pytest

from brain_core.autonomy import should_auto_apply
from brain_core.config.schema import AutonomousConfig, Config
from brain_core.vault.types import NewFile, PatchCategory, PatchSet


def _patchset(category: PatchCategory = PatchCategory.OTHER) -> PatchSet:
    return PatchSet(
        new_files=[NewFile(path=Path("research/notes/x.md"), content="x")],
        reason="test",
        category=category,
    )


def _config(**autonomy) -> Config:
    return Config(
        vault_path=Path("/tmp/vault"),
        autonomous=AutonomousConfig(**autonomy),
    )


def test_other_category_never_auto_applies() -> None:
    """OTHER is the safe default — even if caller sets autonomous.other it wouldn't apply."""
    assert should_auto_apply(_patchset(PatchCategory.OTHER), _config(ingest=True, entities=True)) is False


def test_ingest_category_applies_when_enabled() -> None:
    assert should_auto_apply(_patchset(PatchCategory.INGEST), _config(ingest=True)) is True


def test_ingest_category_does_not_apply_when_disabled() -> None:
    assert should_auto_apply(_patchset(PatchCategory.INGEST), _config(ingest=False)) is False


def test_each_category_honors_own_flag() -> None:
    for cat in (PatchCategory.ENTITIES, PatchCategory.CONCEPTS, PatchCategory.INDEX_REWRITES, PatchCategory.DRAFT):
        key = cat.value
        assert should_auto_apply(_patchset(cat), _config(**{key: True})) is True
        assert should_auto_apply(_patchset(cat), _config(**{key: False})) is False


def test_disabled_categories_do_not_cross_enable() -> None:
    """Turning on ingest autonomy doesn't affect entities."""
    assert should_auto_apply(_patchset(PatchCategory.ENTITIES), _config(ingest=True)) is False


def test_default_config_everything_false() -> None:
    """Out-of-the-box config auto-applies nothing."""
    cfg = Config(vault_path=Path("/tmp/vault"))
    for cat in PatchCategory:
        assert should_auto_apply(_patchset(cat), cfg) is False
```

Create `packages/brain_core/tests/tools/test_patch_category.py`:

```python
"""Verify tool handlers stamp the right PatchCategory on emitted PatchSets."""

from __future__ import annotations

from pathlib import Path

from brain_core.tools.propose_note import _category_for_path
from brain_core.vault.types import PatchCategory


def test_propose_note_entities_path() -> None:
    assert _category_for_path(Path("research/entities/person.md")) == PatchCategory.ENTITIES


def test_propose_note_concepts_path() -> None:
    assert _category_for_path(Path("research/concepts/tactical-empathy.md")) == PatchCategory.CONCEPTS


def test_propose_note_index_rewrites() -> None:
    assert _category_for_path(Path("research/index.md")) == PatchCategory.INDEX_REWRITES


def test_propose_note_synthesis_is_other() -> None:
    assert _category_for_path(Path("research/synthesis/foo.md")) == PatchCategory.OTHER


def test_propose_note_notes_is_other() -> None:
    assert _category_for_path(Path("research/notes/foo.md")) == PatchCategory.OTHER
```

### Step 2 — Implement

Apply the code sketches above. For `config_set._SETTABLE_KEYS`, add:

```python
_SETTABLE_KEYS: frozenset[str] = frozenset({
    "budget.daily_usd",
    "log_llm_payloads",
    # NEW:
    "autonomous.ingest",
    "autonomous.entities",
    "autonomous.concepts",
    "autonomous.index_rewrites",
    "autonomous.draft",
})
```

### Step 3 — Run + commit

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb && uv sync --reinstall-package brain_core --reinstall-package brain_mcp
uv run pytest packages/brain_core packages/brain_cli packages/brain_mcp packages/brain_api -q
```

Expected: **685 prior + 13 new = 698 passed + 11 skipped** (6 autonomy + 5 patch-category + 2 apply-patch-gate tests).

Gates (mypy strict, ruff, ghost files). Commit:

```bash
git commit -m "feat(core): plan 07 task 1 — PatchSet.category + autonomy gate + 5 config keys"
```

---

### Task 2 — Per-mode chat models + `DocEditChatEvent` + Draft-mode emission

**Owning subagent:** brain-core-engineer

**Files:**
- Modify: `packages/brain_core/src/brain_core/chat/session.py` — `ChatSessionConfig.{ask,brainstorm,draft}_model: str | None = None`; `ChatSession.turn` selects model by mode
- Modify: `packages/brain_core/src/brain_core/chat/types.py` — add `ChatEventKind.DOC_EDIT` enum member
- Modify: `ChatSession.turn` Draft-mode path — detect structured edit output (schema TBD: assistant emits JSON block with `edits: [{op, anchor, text}]`) → emit one `DOC_EDIT` event per item
- Modify: `packages/brain_core/src/brain_core/tools/config_set.py` — add 3 `*_model` entries
- Create: `packages/brain_core/tests/chat/test_per_mode_models.py` — 3 tests (ask uses ask_model, brainstorm uses brainstorm_model, fallback to default)
- Create: `packages/brain_core/tests/chat/test_doc_edit_emission.py` — 2 tests (Draft-mode turn emits DOC_EDIT, Ask-mode does not)

**Context for the implementer:**

**Per-mode model selection** is a two-line change in `ChatSession.turn`:

```python
# brain_core/chat/session.py — inside turn(user_message):
mode_model_attr = f"{self.mode.value}_model"  # "ask_model" / "brainstorm_model" / "draft_model"
model = getattr(self._config, mode_model_attr, None) or self._config.model
# ... use `model` in the LLMRequest below ...
```

**Draft-mode DOC_EDIT emission.** The assistant in Draft mode should emit structured edits when it wants to modify the open doc. Wire via a system-prompt addition + response parsing:

1. Draft-mode system prompt (in `brain_core/prompts/chat-draft.md`) gets a section: "When you want to edit the open document, emit a fenced json block tagged `edits`. Shape: `{"edits": [{"op": "insert"|"delete"|"replace", "anchor": {"kind": "line", "value": N} | {"kind": "text", "value": "..."}, "text": "..."}]}`."
2. After the turn's stream ends, `ChatSession.turn` scans the assistant message for `\`\`\`edits\n{...}\n\`\`\`` fences; for each edit object, yields a `ChatEvent(kind=ChatEventKind.DOC_EDIT, data=edit_dict)`.
3. The edit block stays in the assistant message (rendered as a normal markdown code block in non-Draft surfaces); the events are additional structured signal for Draft-mode WS clients.

Note: this is the backend-side contract. The WS-layer `doc_edit_proposed` event (Task 5) maps each `DOC_EDIT` ChatEvent to a typed WS frame.

### Step 1 — Failing tests

```python
# packages/brain_core/tests/chat/test_per_mode_models.py
async def test_ask_mode_uses_ask_model(...) -> None:
    config = ChatSessionConfig(model="default-model", ask_model="ask-specific-model", ...)
    # Assert LLMProvider.complete gets called with model="ask-specific-model"

async def test_fallback_to_default_when_mode_model_unset(...) -> None:
    config = ChatSessionConfig(model="default-model", ask_model=None, ...)
    # Assert LLMProvider.complete gets model="default-model"
```

```python
# packages/brain_core/tests/chat/test_doc_edit_emission.py
async def test_draft_mode_emits_doc_edit_events(...) -> None:
    # Queue a FakeLLM response containing:
    #   ```edits
    #   [{"op": "insert", "anchor": {"kind": "line", "value": 3}, "text": "new line"}]
    #   ```
    # Run a Draft-mode turn; collect events.
    # Assert: one event with kind=DOC_EDIT, data matches the edit dict.

async def test_ask_mode_does_not_emit_doc_edit(...) -> None:
    # Same LLM response; Ask mode.
    # Assert: zero DOC_EDIT events (the fence is parsed as plain markdown in Ask).
```

### Step 2 — Implement

1. Add `ask_model`, `brainstorm_model`, `draft_model` to `ChatSessionConfig`. Re-run Plan 03 regression tests — they default to None and fall back to `model`, so no change.
2. Modify `ChatSession.turn` to select model per step 1 above.
3. Add `ChatEventKind.DOC_EDIT` to the enum.
4. Add the edit-fence parser. Parse once at end of stream (after final `delta`), yield a `DOC_EDIT` event for each edit object. Only in Draft mode (`if self.mode == ChatMode.DRAFT`).
5. Update the `chat-draft.md` prompt to document the `\`\`\`edits` fence convention.

### Step 3 — Run + commit

Expected: **698 + 5 = 703 passed + 11 skipped**.

```bash
git commit -m "feat(core): plan 07 task 2 — per-mode chat models + DocEditChatEvent + Draft-mode edit fence"
```

---

### Task 3 — Cost ledger mode/stage tagging + `cumulative_tokens_in`

**Owning subagent:** brain-core-engineer

**Files:**
- Modify: `packages/brain_core/src/brain_core/cost/ledger.py` — `CostEntry.{mode,stage}: str | None = None`; `CostSummary.by_mode: dict[str, float]`
- Modify: `packages/brain_core/src/brain_core/chat/session.py` — pass `mode=self.mode.value` in cost-record calls
- Modify: `packages/brain_core/src/brain_core/ingest/pipeline.py` — pass `stage=` in `_classify` / `_summarize` / `_integrate` cost records
- Modify: `packages/brain_api/src/brain_api/chat/events.py` — `CostUpdateEvent.cumulative_tokens_in: int = 0` (new field; default keeps existing tests passing)
- Modify: `packages/brain_api/src/brain_api/chat/session_runner.py` — track cumulative tokens in SessionRunner state; include in emitted `CostUpdateEvent`
- Modify: `packages/brain_core/tests/cost/test_ledger.py` — add 3 tests for mode/stage tagging + by_mode summary
- Modify: `packages/brain_api/tests/test_chat_events.py` + `test_ws_chat_turn.py` — verify cumulative_tokens_in surfaces correctly

**Context for the implementer:**

**`CostEntry` additions are optional** — default None preserves all Plan 02–05 call sites.

```python
# brain_core/cost/ledger.py
@dataclass(frozen=True)
class CostEntry:
    timestamp: datetime
    operation: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    domain: str
    mode: str | None = None   # NEW — "ask" / "brainstorm" / "draft" / None
    stage: str | None = None  # NEW — "classify" / "summarize" / "integrate" / None


@dataclass(frozen=True)
class CostSummary:
    today_usd: float
    month_usd: float
    by_domain: dict[str, float]
    by_mode: dict[str, float]   # NEW — e.g. {"ask": 0.12, "brainstorm": 0.03, "draft": 0.08, "": 0.04}

# CostLedger.summary aggregates mode from entries; None mode becomes empty-string key
```

**`cumulative_tokens_in` on WS event:**

`SessionRunner` already gets `CostUpdateChatEvent` from brain_core (per-turn deltas). Add a running total:

```python
# brain_api/chat/session_runner.py
class SessionRunner:
    def __init__(self, ...) -> None:
        # existing fields
        self._cumulative_tokens_in = 0

    def _convert_chat_event(self, e):
        if isinstance(e, CostUpdateChatEvent):
            self._cumulative_tokens_in += e.tokens_in
            return CostUpdateEvent(
                tokens_in=e.tokens_in,
                tokens_out=e.tokens_out,
                cost_usd=e.cost_usd,
                cumulative_usd=e.cumulative_usd,
                cumulative_tokens_in=self._cumulative_tokens_in,  # NEW
            )
        # ... other cases ...
```

### Step 1 — Failing tests

```python
# brain_core/tests/cost/test_ledger.py
def test_cost_entry_accepts_mode_and_stage() -> None:
    entry = CostEntry(..., mode="ask", stage=None)
    assert entry.mode == "ask"
    assert entry.stage is None

def test_summary_returns_by_mode_breakdown(tmp_path) -> None:
    ledger = CostLedger(db_path=tmp_path / "costs.sqlite")
    ledger.record(CostEntry(..., mode="ask", cost_usd=0.05))
    ledger.record(CostEntry(..., mode="brainstorm", cost_usd=0.03))
    ledger.record(CostEntry(..., mode=None, stage="classify", cost_usd=0.01))
    s = ledger.summary(today=..., month=(2026, 4))
    assert s.by_mode == {"ask": pytest.approx(0.05), "brainstorm": pytest.approx(0.03), "": pytest.approx(0.01)}

def test_chat_turn_records_mode(...) -> None:
    # Run a real ChatSession Ask-mode turn; assert a CostEntry was recorded with mode="ask"
```

```python
# brain_api/tests/test_ws_chat_turn.py
async def test_cost_update_includes_cumulative_tokens_in(...) -> None:
    # Queue FakeLLM to report tokens_in=1500 on the turn
    # Open WS, send turn_start, drain events
    # Assert the cost_update frame has cumulative_tokens_in >= 1500
```

### Step 2 — Implement

See sketches above. Keep `CostEntry`'s `mode`/`stage` kwargs optional so Plan 02–05 call sites compile without change.

### Step 3 — Run + commit

Expected: **703 + 4 = 707 passed + 11 skipped**. The existing `test_cost_report` and BudgetWall tests pin `by_domain` — verify the new `by_mode` field doesn't break them (add to the envelope but don't remove anything).

```bash
git commit -m "feat(core,api): plan 07 task 3 — cost ledger mode/stage tagging + cumulative_tokens_in"
```

---

### Task 4 — 4 new tools + `BulkPlan.duplicate` + 12 `_SETTABLE_KEYS`

**Owning subagent:** brain-core-engineer

**Files:**
- Create: `packages/brain_core/src/brain_core/tools/recent_ingests.py` + shim at `packages/brain_mcp/src/brain_mcp/tools/recent_ingests.py` + smoke test
- Create: `packages/brain_core/src/brain_core/tools/create_domain.py` + shim + smoke test
- Create: `packages/brain_core/src/brain_core/tools/rename_domain.py` + shim + smoke test (ATOMIC — uses UndoLog)
- Create: `packages/brain_core/src/brain_core/tools/budget_override.py` + shim + smoke test
- Modify: `packages/brain_core/src/brain_core/ingest/bulk.py` — `BulkItem.duplicate: bool = False`; `BulkImporter.plan()` sets it via `IngestPipeline._already_ingested` check per file
- Modify: `packages/brain_core/src/brain_core/cost/ledger.py` — `is_over_budget(config, today)` consults `config.budget.override_until` + `override_delta_usd`
- Modify: `packages/brain_core/src/brain_core/config/schema.py` — `BudgetConfig.override_until: datetime | None` + `override_delta_usd: float = 0.0`
- Modify: `packages/brain_core/src/brain_core/state/migrations/` — add `0003_ingest_history.sql` if needed (for `recent_ingests`)
- Modify: `packages/brain_core/src/brain_core/tools/config_set.py` — `_SETTABLE_KEYS` gains: `ask_model`, `brainstorm_model`, `draft_model`, `domain_order`, `budget.override_until`, `budget.override_delta_usd` (6 new keys on top of the 5 autonomy keys from Task 1 = 11 total; 12th is `BulkImporter.plan`-surfaced `duplicate` which isn't a config key — 11 total `_SETTABLE_KEYS` entries added across Tasks 1 + 4)

**Context for the implementer:**

### `brain_recent_ingests`

**Purpose:** power Inbox "Recent" / "In progress" / "Needs attention" tabs.

**Input:** `{limit?: int = 20}`. **Output:** `{ingests: [{source, domain, source_type, status, patch_id?, classified_at, cost_usd, error?}]}`.

**Implementation:** reads from a new `ingest_history` table in `state.sqlite`. Plan 02 already stores content-hash records for idempotency in a `sources` table; extend with a history view:

```sql
-- 0003_ingest_history.sql
CREATE TABLE IF NOT EXISTS ingest_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,
  source_type TEXT,
  domain TEXT,
  status TEXT NOT NULL,  -- 'ok' / 'quarantined' / 'failed' / 'skipped_duplicate'
  patch_id TEXT,
  classified_at TEXT NOT NULL,  -- ISO timestamp
  cost_usd REAL DEFAULT 0.0,
  error TEXT
);
CREATE INDEX IF NOT EXISTS idx_ingest_history_classified_at ON ingest_history(classified_at DESC);
```

`IngestPipeline.ingest()` INSERTs a row after every run (success or failure). `brain_recent_ingests` SELECTs with `LIMIT`.

### `brain_create_domain`

**Input:** `{slug: str, name: str, accent_color?: str = "#888"}`. **Output:** `{status: "created", domain: {slug, name, accent_color}}`. Fails if slug already exists or fails `^[a-z][a-z0-9-]{1,24}$` regex.

**Implementation:** `<vault>/<slug>/{index.md, log.md}` created with seed content; `config.domain_order` list gets the new slug appended via `brain_config_set`.

### `brain_rename_domain` (D2a — ATOMIC, not a PatchSet)

**Input:** `{from: str, to: str, rewrite_frontmatter: bool = True}`. **Output:** `{status: "renamed", from, to, files_updated: int, wikilinks_rewritten: int, undo_id: str}`.

**Implementation:**
1. Validate `to` doesn't exist; both slugs match the regex.
2. Iterate `<vault>/<from>/**/*.md` — for each file, rewrite `domain: <from>` in frontmatter (if flag set), write atomically.
3. Iterate every other vault file — find `[[<slug>]]` wikilinks where the target resolves into `<from>/` and rewrite to point into `<to>/`. (Most wikilinks are slug-only, not path-qualified, so this is usually a no-op unless the vault uses `[[<dir>/<slug>]]` style.)
4. Atomic `os.rename(<vault>/<from>, <vault>/<to>)`.
5. Update `config.domain_order`: replace `from` → `to` in-place.
6. Write a single UndoLog record with `kind=rename_domain, from, to, files_touched: [...]` so `brain_undo_last` can revert.

### `brain_budget_override`

**Input:** `{amount_usd: float, duration_hours: int = 24}`. **Output:** `{status: "override_set", override_until: ISO, override_delta_usd}`. Sets `config.budget.override_until = now + duration_hours` and `config.budget.override_delta_usd = amount_usd`.

### `BulkPlan.duplicate` flag

`BulkImporter.plan()` already runs `_already_ingested(content_hash)` as a side-effect of classification. Store the flag on each `BulkItem`:

```python
@dataclass(frozen=True)
class BulkItem:
    spec: Path
    slug: str
    classified_domain: str | None
    confidence: float | None
    duplicate: bool = False  # NEW
```

Frontend uses the flag in the bulk-import dry-run table (design's `dup` warn-chip).

### Step 1 — Failing tests

One smoke test per tool (4 tests) + one `BulkPlan.duplicate` test + one `is_over_budget` override test = 6 tests.

### Step 2 — Implement

Apply sketches above. For `rename_domain`, pay careful attention to atomicity — the `os.rename` is the commit point; do frontmatter rewrites FIRST (so a crash mid-way leaves `<from>/` still mostly intact), the folder-rename LAST.

### Step 3 — Run + commit

Expected: **707 + 6 smoke + 4 × 1 shim preservation = 717 passed + 11 skipped**. Also update all 4 new tool INPUT_SCHEMAs in brain_core.tools registry; `GET /api/tools` now returns 22 tools, not 18 — update `test_lists_eighteen_tools_after_extraction` to 22.

```bash
git commit -m "feat(core): plan 07 task 4 — 4 new tools (recent_ingests, create/rename_domain, budget_override) + BulkPlan.duplicate"
```

---

### Task 5 — `ChatSession.fork_from` + `doc_edit_proposed` WS event + `SCHEMA_VERSION = "2"`

**Owning subagent:** brain-core-engineer

**Files:**
- Create: `packages/brain_core/src/brain_core/chat/fork.py` — `fork_from(source_id, turn_index, *, carry, mode, vault_root, ...) -> ChatSession` + `summarize_turns(turns, llm) -> str` helper
- Modify: `packages/brain_api/src/brain_api/chat/events.py` — add `DocEditProposedEvent`; bump `SCHEMA_VERSION = "2"`
- Modify: `packages/brain_api/src/brain_api/chat/session_runner.py` — `_convert_chat_event` maps `ChatEventKind.DOC_EDIT` → `DocEditProposedEvent`
- Modify: ALL Plan 05 tests that pinned `SCHEMA_VERSION == "1"` — flip to `"2"` (expect ~3 tests across `test_chat_events.py`, `test_ws_chat_handshake.py`, `scripts/demo-plan-05.py`)
- Create: `packages/brain_core/tests/chat/test_fork.py` — 4 tests (full carry copies N turns; none carry starts empty; summary carry runs an LLM call; invalid turn_index raises)

**Context for the implementer:**

### `ChatSession.fork_from`

Classmethod on `ChatSession` (or free function in `brain_core.chat.fork`). Signature:

```python
def fork_from(
    source_thread_id: str,
    turn_index: int,
    *,
    vault_root: Path,
    allowed_domains: tuple[str, ...],
    llm: LLMProvider,
    # ... other ChatSession kwargs that would flow from AppContext ...
    mode: ChatMode | None = None,   # None → inherit from source thread
    carry: Literal["full", "none", "summary"] = "full",
    title_hint: str | None = None,
) -> ChatSession:
    """Create a new thread with turns 0..turn_index of source thread as initial context."""
    source = ChatSession.load(source_thread_id, vault_root, ...)
    turns_to_carry = source.turns[:turn_index + 1]

    if carry == "none":
        initial_turns = []
    elif carry == "full":
        initial_turns = list(turns_to_carry)
    elif carry == "summary":
        summary = summarize_turns(turns_to_carry, llm)
        initial_turns = [ChatTurn.system(summary)]
    else:
        raise ValueError(f"unknown carry mode: {carry!r}")

    new_thread_id = _new_thread_id(title_hint)
    return ChatSession(
        thread_id=new_thread_id,
        initial_turns=initial_turns,
        mode=mode or source.mode,
        vault_root=vault_root,
        ...
    )


def summarize_turns(turns: list[ChatTurn], llm: LLMProvider, model: str = "claude-haiku-4-5-20251001") -> str:
    """Cheap Haiku-powered summary of N turns. ~400 tokens target."""
    transcript_text = "\n\n".join(f"{t.role}: {t.body}" for t in turns)
    response = await llm.complete(
        LLMRequest(
            model=model,
            system="Summarize the following chat transcript in ~4 sentences, preserving the key factual claims and the open question the user was working on.",
            messages=[LLMMessage(role="user", content=transcript_text)],
            max_tokens=600,
        )
    )
    return response.content.strip()
```

### `SCHEMA_VERSION = "2"` — breaking change

Plan 05 pinned `"1"`. Adding a new event type `doc_edit_proposed` is technically backwards-compatible (clients that don't know it can ignore), but we bump to `"2"` to make the addition explicit and let the frontend opt in on handshake. The frontend's WS client (Task 9) expects `schema_version: "2"` and logs a warning if it sees `"1"` (graceful — still works if only missing DOC_EDIT).

### `DocEditProposedEvent`

```python
# brain_api/chat/events.py
class DocEditProposedEvent(BaseModel):
    type: Literal["doc_edit_proposed"] = "doc_edit_proposed"
    edits: list[dict[str, Any]]  # each item: {op, anchor: {kind, value}, text}
```

Add to the `ServerEvent` union + `serialize_server_event` pathway.

### `_convert_chat_event` mapping

```python
# session_runner.py
if isinstance(e, ChatEvent) and e.kind == ChatEventKind.DOC_EDIT:
    # Per Task 2, Draft-mode may emit multiple DOC_EDIT events per turn (one per edit).
    # We batch them into a single DocEditProposedEvent? Or emit one event per edit?
    # Choice: one WS event per DOC_EDIT ChatEvent — simpler, frontend can batch UI.
    return DocEditProposedEvent(edits=[e.data])
```

### Step 1 — Failing tests

```python
# brain_core/tests/chat/test_fork.py
@pytest.mark.asyncio
async def test_fork_full_carry_copies_turns(...) -> None:
    source = _make_source_with_turns(5)
    forked = await fork_from(source.thread_id, 3, carry="full", llm=FakeLLMProvider(), ...)
    assert len(forked._turns) == 4  # turns 0..3

@pytest.mark.asyncio
async def test_fork_none_carry_empty(...) -> None:
    forked = await fork_from(..., carry="none", ...)
    assert forked._turns == []

@pytest.mark.asyncio
async def test_fork_summary_carry_runs_llm(...) -> None:
    fake = FakeLLMProvider()
    fake.queue("Summary text.")
    forked = await fork_from(..., carry="summary", llm=fake, ...)
    assert len(forked._turns) == 1
    assert "Summary text" in forked._turns[0].body

@pytest.mark.asyncio
async def test_fork_invalid_turn_index_raises(...) -> None:
    source = _make_source_with_turns(3)
    with pytest.raises(IndexError):
        await fork_from(source.thread_id, 99, carry="full", ...)
```

```python
# brain_api/tests/test_chat_events.py
def test_schema_version_is_2() -> None:
    from brain_api.chat.events import SCHEMA_VERSION
    assert SCHEMA_VERSION == "2"

def test_doc_edit_proposed_serializes() -> None:
    ev = DocEditProposedEvent(edits=[{"op": "insert", "anchor": {"kind": "line", "value": 3}, "text": "hello"}])
    out = serialize_server_event(ev)
    assert out["type"] == "doc_edit_proposed"
```

### Step 2 — Implement

See sketches. Update Plan 05 tests that pinned `SCHEMA_VERSION == "1"`.

### Step 3 — Run + commit

Expected: **717 + 4 fork + 2 event + ~3 flipped schema_version tests = ~726 passed + 11 skipped**.

```bash
git commit -m "feat(core,api): plan 07 task 5 — ChatSession.fork_from + doc_edit_proposed WS event + SCHEMA_VERSION=2"
```

---

**Checkpoint 1 — pause for main-loop review.**

5 backend-extension tasks landed. Summary:
- **Autonomy gate** — `PatchSet.category` + 5 autonomy config keys. `brain_apply_patch` auto-applies when gate returns True.
- **Per-mode chat models** — `ChatSessionConfig.{ask,brainstorm,draft}_model` optional, fallback to default.
- **DocEditChatEvent** — Draft-mode assistant responses with `\`\`\`edits` fence emit structured events.
- **Cost ledger mode/stage tagging** — `CostEntry.{mode,stage}` + `CostSummary.by_mode`.
- **`cumulative_tokens_in` WS field** — for context-fill meter.
- **4 new tools** — `brain_recent_ingests`, `brain_create_domain`, `brain_rename_domain` (atomic), `brain_budget_override`.
- **`BulkPlan.duplicate`** — surfaces dry-run duplicate detection.
- **12 new `_SETTABLE_KEYS`** — config schema supports every frontend-touchable setting.
- **`ChatSession.fork_from` + summarize_turns helper** — supports ForkDialog's 3 carry modes.
- **`SCHEMA_VERSION = "2"`** + `doc_edit_proposed` WS event — frontend WS client pins v2.

Expected combined test count: **~726 passed + 11 skipped** (up from 685 + 11). Tool surface: **22 tools** (up from 18). Hard gate: brain_mcp tests unchanged at 99; brain_cli unchanged at 30.

Main loop reviews:

- Does the `PatchCategory` enum cover every real patchset shape, or are there cases falling into `OTHER` that shouldn't? (Filesystem edits from `brain_propose_note` to `<domain>/sources/` become OTHER — correct: source edits should stage, not auto-apply. Edits to `<domain>/synthesis/` also OTHER — user-curated territory.)
- Is the `\`\`\`edits` fence convention for Draft-mode structured edits the right shape? LLM emits JSON inside a fenced code block; frontend doesn't see the fence (it's parsed out by `ChatSession`). Alternative: separate sidecar message? Cleaner but more LLM surface to specify.
- `rename_domain` via UndoLog is atomic but non-standard. Document clearly as an exception to "every vault write through VaultWriter/PatchSet."
- SCHEMA_VERSION bump — frontend MUST pin `"2"`. If a v1-only client connects during the transition, what happens? Backend always sends v2; a v1-expecting client warns in its handshake check but continues. Document.

Before Task 6, confirm the backend surface is stable — frontend construction depends on `apiFetch<T>` types derived from OpenAPI + typed WS events from `brain_api.chat.events`.

---
