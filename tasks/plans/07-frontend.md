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

### Group 2 — Frontend foundation (Tasks 6–10)

**Pattern:** every task in Group 2 lands a different layer of the Next.js app. Tasks build bottom-up: package skeleton → design tokens → auth proxy → typed clients → shell. Each checkpoint-worthy substrate is testable in isolation.

**Node workspace setup note:** `apps/brain_web/` gets its own `package.json`. A root `package.json` at `/Users/chrisjohnson/Code/cj-llm-kb/package.json` declares the workspace (`"workspaces": ["apps/*"]`). Use **pnpm** as the package manager — strict dep resolution, fast cold installs, good Next.js compatibility. If the user already has npm/yarn preferences, adapt in Task 6 but document.

**Node + tooling versions** (pinned to avoid drift):
- Node 20.x LTS (minimum)
- pnpm 9.x (`corepack enable` + `corepack prepare pnpm@latest --activate`)
- Next.js 15.0+
- React 18.3+
- TypeScript 5.5+
- Tailwind CSS 3.4+

---

### Task 6 — `apps/brain_web/` Next.js 15 package skeleton

**Owning subagent:** brain-frontend-engineer

**Files:**
- Create: root `package.json` — workspace declaration
- Create: `apps/brain_web/package.json`
- Create: `apps/brain_web/tsconfig.json`
- Create: `apps/brain_web/next.config.mjs`
- Create: `apps/brain_web/tailwind.config.ts`
- Create: `apps/brain_web/postcss.config.mjs`
- Create: `apps/brain_web/.eslintrc.json`
- Create: `apps/brain_web/.gitignore` (standard Next.js)
- Create: `apps/brain_web/README.md` — "how to run dev mode"
- Create: `apps/brain_web/src/app/layout.tsx` — minimal root layout
- Create: `apps/brain_web/src/app/page.tsx` — redirects to `/chat`
- Create: `apps/brain_web/src/app/chat/page.tsx` — placeholder "Chat (Task 14)"
- Create: `apps/brain_web/src/styles/globals.css` — Tailwind directives only
- Create: `apps/brain_web/tests/unit/app.test.tsx` — smoke test for layout + page rendering

**Context for the implementer:**

Task 6 lands the absolute minimum to run `pnpm dev` and see a page. No design tokens yet, no shadcn, no auth — pure Next.js 15 App Router skeleton. Goal: prove the workspace wiring works + smoke test via `pnpm test`.

**Key pyproject interaction:** do NOT add `brain_web` to the root Python `pyproject.toml`'s `[project].dependencies` — it's a Node package, not a Python package. The `pyproject.toml`'s workspace glob stays `["packages/*"]`. Node workspace is a parallel universe.

**Root `package.json`:**

```json
{
  "name": "cj-llm-kb",
  "private": true,
  "packageManager": "pnpm@9.15.0",
  "workspaces": ["apps/*"],
  "scripts": {
    "dev": "pnpm --filter brain_web dev",
    "build": "pnpm --filter brain_web build",
    "test": "pnpm --filter brain_web test"
  }
}
```

**`apps/brain_web/package.json`:**

```json
{
  "name": "brain_web",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "next dev --port 4316",
    "build": "next build",
    "start": "next start --port 4316",
    "lint": "next lint",
    "type-check": "tsc --noEmit",
    "test": "vitest",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "next": "15.0.3",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "@types/node": "^22",
    "@types/react": "^18.3",
    "@types/react-dom": "^18.3",
    "typescript": "^5.5",
    "eslint": "^9",
    "eslint-config-next": "15.0.3",
    "vitest": "^2",
    "@testing-library/react": "^16",
    "@testing-library/jest-dom": "^6",
    "@vitejs/plugin-react": "^4",
    "jsdom": "^25",
    "@playwright/test": "^1.48",
    "axe-core": "^4.10",
    "@axe-core/playwright": "^4.10"
  }
}
```

Tailwind, shadcn, Zustand, React Query are LATER tasks — keep Task 6 minimal.

**`apps/brain_web/next.config.mjs`:**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Dev origin for browser; matches brain_api's CSRF-acceptable loopback.
  experimental: {
    // Placeholder for future config.
  },
};

export default nextConfig;
```

**`apps/brain_web/tsconfig.json`:**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

**`apps/brain_web/src/app/layout.tsx`:**

```tsx
import type { Metadata } from "next";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "brain",
  description: "Your LLM-maintained personal knowledge base.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark">
      <body>{children}</body>
    </html>
  );
}
```

**`apps/brain_web/src/app/page.tsx`:**

```tsx
import { redirect } from "next/navigation";

export default function RootPage() {
  redirect("/chat");
}
```

**`apps/brain_web/src/app/chat/page.tsx`:**

```tsx
export default function ChatPage() {
  return (
    <main style={{ padding: "2rem" }}>
      <h1>Chat</h1>
      <p>Placeholder — Task 14 fills in the real chat surface.</p>
    </main>
  );
}
```

**`apps/brain_web/src/styles/globals.css`:**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

(Tailwind directives only; Task 7 adds the token layer.)

### Step 1 — Failing test

`apps/brain_web/tests/unit/app.test.tsx`:

```tsx
import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import ChatPage from "@/app/chat/page";

describe("ChatPage", () => {
  test("renders the placeholder heading", () => {
    render(<ChatPage />);
    expect(screen.getByRole("heading", { name: /chat/i })).toBeInTheDocument();
  });
});
```

Vitest config — `apps/brain_web/vitest.config.ts`:

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/unit/setup.ts"],
  },
  resolve: {
    alias: { "@": resolve(__dirname, "./src") },
  },
});
```

`apps/brain_web/tests/unit/setup.ts`:

```typescript
import "@testing-library/jest-dom/vitest";
```

### Step 2 — Run + commit

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb && pnpm install
cd apps/brain_web && pnpm type-check
pnpm test -- --run
pnpm build  # sanity — production build succeeds
pnpm dev    # manual: open http://localhost:4316 → /chat loads
```

Expected: smoke test passes; type-check clean; production build succeeds; `http://localhost:4316/chat` renders the placeholder.

```bash
git commit -m "feat(web): plan 07 task 6 — brain_web Next.js 15 package skeleton"
```

---

### Task 7 — Design tokens + theme + shadcn/ui install

**Owning subagent:** brain-frontend-engineer

**Files:**
- Copy: v3 design zip's `fonts/Roboto-*.ttf` → `apps/brain_web/public/fonts/`
- Copy: v3 design zip's `assets/{color-orbs.png, logo-color.png, logo-white.png}` → `apps/brain_web/public/assets/`
- Create: `apps/brain_web/src/styles/tokens.css` — TT color palette + semantic tokens (based on v3 design zip's `tt-tokens.css`)
- Modify: `apps/brain_web/src/styles/globals.css` — import tokens, add font-face declarations, base element styles
- Modify: `apps/brain_web/tailwind.config.ts` — extend with TT colors + custom spacing/radius/font scales
- Create: `apps/brain_web/components.json` — shadcn/ui config
- Run: `pnpm dlx shadcn@latest init` (one-time) + `pnpm dlx shadcn@latest add button dialog popover select toggle-group tabs input textarea checkbox switch separator`
- Create: `apps/brain_web/src/lib/utils.ts` — shadcn's `cn()` utility (generated by shadcn)
- Create: `apps/brain_web/src/components/theme-provider.tsx` — theme switching via `data-theme` attribute
- Create: `apps/brain_web/tests/unit/theme.test.tsx` — 3 tests (theme default, theme toggle, density toggle)

**Context for the implementer:**

Task 7 lands the visual foundation. Design tokens come from the v3 design zip's `assets/tt-tokens.css` — copy verbatim, then add semantic aliases for shadcn.

**Why shadcn over raw Radix:** shadcn generates source-level components into `src/components/ui/` so you can modify them. Radix primitives stay as deps (`@radix-ui/react-*`) but shadcn's styling + composition layer is ours to edit.

**Key tokens from v3 zip's `tt-tokens.css`:**

Brand palette (`--tt-cream`, `--tt-teal`, `--tt-cyan`, `--tt-orange`, `--tt-sage`, plus their light/dark variants). Domain accents: `--dom-research` (cyan), `--dom-work` (sage), `--dom-personal` (orange). Neutrals: `--surface-0` through `--surface-5`, `--text`, `--text-muted`, `--text-dim`, `--hairline`.

**Theme switching:** v3 uses `document.documentElement.dataset.theme = 'dark'|'light'`. Matches. Density via `data-density='comfortable'|'compact'`. Tokens define variants for both axes.

**Root layout change:**

```tsx
// apps/brain_web/src/app/layout.tsx
import "@/styles/tokens.css";  // NEW
import "@/styles/globals.css";
import { ThemeProvider } from "@/components/theme-provider";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
```

**`ThemeProvider`:** client component that reads `localStorage.getItem("brain-theme")` on mount, applies `data-theme` to `<html>`, exposes a context for `useTheme()` hook. SSR-safe: no window access during render; `suppressHydrationWarning` on `<html>` tolerates the FOUC-less hydration flash.

**`components.json` (shadcn config):**

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/styles/globals.css",
    "baseColor": "neutral",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  }
}
```

**Tailwind config extension:**

```typescript
// apps/brain_web/tailwind.config.ts
import type { Config } from "tailwindcss";

export default {
  darkMode: ["class", "[data-theme='dark']"],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "tt-cream": "var(--tt-cream)",
        "tt-teal": "var(--tt-teal)",
        "tt-cyan": "var(--tt-cyan)",
        "tt-orange": "var(--tt-orange)",
        "tt-sage": "var(--tt-sage)",
        "dom-research": "var(--dom-research)",
        "dom-work": "var(--dom-work)",
        "dom-personal": "var(--dom-personal)",
        surface: {
          0: "var(--surface-0)",
          1: "var(--surface-1)",
          2: "var(--surface-2)",
          3: "var(--surface-3)",
          4: "var(--surface-4)",
          5: "var(--surface-5)",
        },
        hairline: "var(--hairline)",
        text: {
          DEFAULT: "var(--text)",
          muted: "var(--text-muted)",
          dim: "var(--text-dim)",
        },
      },
      fontFamily: {
        sans: ["Roboto", "system-ui", "sans-serif"],
        mono: ['"Roboto Mono"', "SF Mono", "monospace"],
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "6px",
        md: "8px",
        lg: "12px",
      },
    },
  },
  plugins: [],
} satisfies Config;
```

### Step 1 — Failing tests

`apps/brain_web/tests/unit/theme.test.tsx`:

```tsx
import { describe, expect, test } from "vitest";
import { render, act } from "@testing-library/react";

import { ThemeProvider, useTheme } from "@/components/theme-provider";

function ThemeTestHarness({ onMount }: { onMount: (ctx: ReturnType<typeof useTheme>) => void }) {
  const ctx = useTheme();
  onMount(ctx);
  return null;
}

describe("ThemeProvider", () => {
  test("defaults to dark theme when localStorage empty", () => {
    localStorage.clear();
    render(<ThemeProvider><ThemeTestHarness onMount={(ctx) => {
      expect(ctx.theme).toBe("dark");
    }} /></ThemeProvider>);
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  test("toggles to light", () => {
    let setThemeRef: ((t: "dark" | "light") => void) | null = null;
    render(<ThemeProvider><ThemeTestHarness onMount={(ctx) => {
      setThemeRef = ctx.setTheme;
    }} /></ThemeProvider>);
    act(() => setThemeRef!("light"));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("brain-theme")).toBe("light");
  });

  test("density toggles independently", () => {
    let setDensityRef: ((d: "comfortable" | "compact") => void) | null = null;
    render(<ThemeProvider><ThemeTestHarness onMount={(ctx) => {
      setDensityRef = ctx.setDensity;
    }} /></ThemeProvider>);
    act(() => setDensityRef!("compact"));
    expect(document.documentElement.dataset.density).toBe("compact");
  });
});
```

### Step 2 — Implement

1. Copy fonts + assets from v3 design zip.
2. Port `tt-tokens.css` verbatim → `apps/brain_web/src/styles/tokens.css`. Adapt font-face paths to `/fonts/Roboto-Regular.ttf` (relative to public/).
3. Extend `globals.css` — add `@font-face` blocks, `body { font-family: var(--sans); background: var(--surface-0); color: var(--text); }`, reset defaults.
4. Run `pnpm dlx shadcn@latest init` — accepts components.json above.
5. Run `pnpm dlx shadcn@latest add button dialog popover select toggle-group tabs input textarea checkbox switch separator scroll-area tooltip dropdown-menu` — generates components into `src/components/ui/`.
6. Create `theme-provider.tsx` as a client component with context.
7. Wire into `layout.tsx`.

### Step 3 — Run + commit

```bash
pnpm test -- --run   # theme tests + Task 6 smoke
pnpm build           # production build works
pnpm dev             # manual: http://localhost:4316 shows Roboto + dark theme
```

```bash
git commit -m "feat(web): plan 07 task 7 — design tokens + theme + shadcn/ui primitives"
```

---

### Task 8 — Auth proxy route (server-side token read)

**Owning subagent:** brain-frontend-engineer

**Files:**
- Create: `apps/brain_web/src/lib/auth/token.ts` — server-only token reader
- Create: `apps/brain_web/src/app/api/proxy/[...path]/route.ts` — HTTP proxy for REST calls
- Create: `apps/brain_web/tests/unit/auth-token.test.ts` — 4 tests (token read success, missing file returns null, malformed handled, cache invalidation)
- Create: `apps/brain_web/tests/unit/proxy-route.test.ts` — 4 tests (proxy forwards token, rejects when token missing, strips sensitive headers, handles 5xx)

**Context for the implementer:**

**The security property:** the browser never sees `X-Brain-Token` raw. The token lives at `<vault>/.brain/run/api-secret.txt` (mode 0600). The Next.js server process reads it, attaches it server-side to outbound requests to `http://127.0.0.1:4317` (brain_api), and returns the response to the browser stripped of the token header.

**Browser-side JS** makes all API calls to `/api/proxy/api/tools/brain_search` etc. — the Next.js server intercepts via the catch-all route, reads the token once per server process (cached), forwards, returns.

**Token location resolution:**
- Env var `BRAIN_VAULT_ROOT` is the primary source (matches brain_api's Plan 05 convention). Defaults to `~/Documents/brain` if unset.
- Token at `<vault_root>/.brain/run/api-secret.txt`.

**Token read implementation:**

```typescript
// apps/brain_web/src/lib/auth/token.ts
// Server-only — never imported in Client Components.
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { homedir } from "node:os";

// Module-level cache. Invalidated on SIGHUP or process restart.
let cachedToken: string | null = null;
let cacheMiss = false;

export async function readToken(): Promise<string | null> {
  if (cachedToken) return cachedToken;
  if (cacheMiss) return null;

  const vaultRoot = process.env.BRAIN_VAULT_ROOT || join(homedir(), "Documents", "brain");
  const tokenPath = join(vaultRoot, ".brain", "run", "api-secret.txt");

  try {
    const token = (await readFile(tokenPath, "utf-8")).trim();
    if (!token) {
      cacheMiss = true;
      return null;
    }
    cachedToken = token;
    return token;
  } catch (err: unknown) {
    // ENOENT is expected pre-backend-boot — not an error state.
    cacheMiss = true;
    return null;
  }
}

export function invalidateTokenCache() {
  cachedToken = null;
  cacheMiss = false;
}
```

**Proxy route:**

```typescript
// apps/brain_web/src/app/api/proxy/[...path]/route.ts
import { NextRequest, NextResponse } from "next/server";
import { readToken } from "@/lib/auth/token";

const API_BASE = process.env.BRAIN_API_URL || "http://127.0.0.1:4317";

// Strip these on response — never leak server-internal headers to the browser.
const STRIPPED_RESPONSE_HEADERS = new Set([
  "x-brain-token",
  "server",
]);

async function proxy(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const token = await readToken();
  if (!token) {
    return NextResponse.json(
      { error: "setup_required", message: "brain_api token not found. Is brain_api running?" },
      { status: 503 },
    );
  }

  const urlSuffix = "/" + path.join("/") + (req.nextUrl.search || "");
  const targetUrl = API_BASE + urlSuffix;

  const headers = new Headers(req.headers);
  headers.set("X-Brain-Token", token);
  headers.set("Origin", `http://localhost:4316`);  // brain_api expects loopback Origin
  headers.delete("host");  // don't forward the frontend's Host

  const body = ["GET", "HEAD"].includes(req.method) ? undefined : await req.arrayBuffer();

  const upstream = await fetch(targetUrl, {
    method: req.method,
    headers,
    body,
    redirect: "manual",
  });

  const outHeaders = new Headers();
  for (const [k, v] of upstream.headers) {
    if (!STRIPPED_RESPONSE_HEADERS.has(k.toLowerCase())) outHeaders.set(k, v);
  }

  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: outHeaders,
  });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as DELETE, proxy as PATCH };
```

### Step 1 — Failing tests

```typescript
// apps/brain_web/tests/unit/auth-token.test.ts
import { describe, test, expect, beforeEach, vi } from "vitest";

vi.mock("node:fs/promises");
vi.mock("node:os", () => ({ homedir: () => "/home/test" }));

import { readFile } from "node:fs/promises";
import { readToken, invalidateTokenCache } from "@/lib/auth/token";

describe("readToken", () => {
  beforeEach(() => {
    invalidateTokenCache();
    vi.resetAllMocks();
    delete process.env.BRAIN_VAULT_ROOT;
  });

  test("reads + strips whitespace", async () => {
    (readFile as any).mockResolvedValue("abc123\n");
    const token = await readToken();
    expect(token).toBe("abc123");
  });

  test("returns null when file missing", async () => {
    (readFile as any).mockRejectedValue({ code: "ENOENT" });
    const token = await readToken();
    expect(token).toBeNull();
  });

  test("caches after first read", async () => {
    (readFile as any).mockResolvedValue("abc123");
    await readToken();
    await readToken();
    expect(readFile).toHaveBeenCalledTimes(1);
  });

  test("respects BRAIN_VAULT_ROOT env var", async () => {
    process.env.BRAIN_VAULT_ROOT = "/custom/vault";
    (readFile as any).mockResolvedValue("xyz");
    await readToken();
    expect(readFile).toHaveBeenCalledWith(
      expect.stringContaining("/custom/vault/.brain/run/api-secret.txt"),
      "utf-8",
    );
  });
});
```

```typescript
// apps/brain_web/tests/unit/proxy-route.test.ts
// Mock the token reader + global fetch; call route.POST directly.
// Verify: 503 when no token; correct headers attached on forward; stripped on response.
```

### Step 2 — Implement

See sketches. Key edge cases: `path` param is an array (catch-all), preserve query string, handle streaming response body (pass-through `upstream.body`).

### Step 3 — Run + commit

Expected: 8 new tests. Pnpm test green; manual smoke — start brain_api via uvicorn, start brain_web via `pnpm dev`, hit `http://localhost:4316/api/proxy/healthz` → `200 {"status": "ok"}`.

```bash
git commit -m "feat(web): plan 07 task 8 — auth proxy route (server-side token read + HTTP forward)"
```

---

### Task 9 — Typed API client + WS client (v2-pinned)

**Owning subagent:** brain-frontend-engineer

**Files:**
- Create: `apps/brain_web/src/lib/api/client.ts` — `apiFetch<T>` typed wrapper
- Create: `apps/brain_web/src/lib/api/tools.ts` — per-tool typed bindings (18 + 4 new = 22 tools)
- Create: `apps/brain_web/src/lib/api/types.ts` — shared types (`ToolResponse`, `ErrorResponse`, `RateLimitDetail`)
- Create: `apps/brain_web/src/lib/ws/client.ts` — WS client class with reconnect + event parsing
- Create: `apps/brain_web/src/lib/ws/events.ts` — typed event discriminated union (mirror `brain_api.chat.events`)
- Create: `apps/brain_web/src/lib/ws/hooks.ts` — `useWebSocket(threadId)` React hook (P3a: one WS per thread)
- Create: `apps/brain_web/tests/unit/api-client.test.ts` — 5 tests (success, 4xx error envelope, 429 Retry-After, 5xx, token rejection)
- Create: `apps/brain_web/tests/unit/ws-events.test.ts` — 6 tests (parse schema_version, parse each client-bound event, reject unknown type, round-trip server event)
- Create: `apps/brain_web/tests/unit/ws-client.test.ts` — 4 tests (connect, handshake schema v2, reconnect on close, cancel turn request)

**Context for the implementer:**

### `apiFetch<T>` — the typed API primitive

```typescript
// apps/brain_web/src/lib/api/types.ts
export interface ToolResponse<D = Record<string, unknown>> {
  text: string;
  data: D | null;
}

export interface ErrorResponse {
  error: string;
  message: string;
  detail: Record<string, unknown> | null;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    public readonly detail: Record<string, unknown> | null,
    message: string,
  ) {
    super(message);
  }
}
```

```typescript
// apps/brain_web/src/lib/api/client.ts
import type { ToolResponse, ErrorResponse } from "./types";
import { ApiError } from "./types";

export async function apiFetch<D = Record<string, unknown>>(
  path: string,
  init?: RequestInit,
): Promise<ToolResponse<D>> {
  const response = await fetch("/api/proxy" + path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (!response.ok) {
    let body: ErrorResponse;
    try {
      body = await response.json();
    } catch {
      throw new ApiError(response.status, "unknown", null, response.statusText);
    }
    throw new ApiError(response.status, body.error, body.detail, body.message);
  }

  return response.json();
}
```

### Per-tool bindings (22 tools)

```typescript
// apps/brain_web/src/lib/api/tools.ts
import { apiFetch } from "./client";

// READ TOOLS
export const listDomains = () =>
  apiFetch<{ domains: string[] }>("/api/tools/brain_list_domains", {
    method: "POST",
    body: JSON.stringify({}),
  });

export const search = (query: string, opts?: { top_k?: number; domains?: string[] }) =>
  apiFetch<{ hits: Array<{ path: string; title: string; snippet: string; score: number }>; top_k_used: number }>(
    "/api/tools/brain_search",
    { method: "POST", body: JSON.stringify({ query, ...opts }) },
  );

// ... (18 more tools, all shaped alike) ...

// NEW IN PLAN 07
export const recentIngests = (limit?: number) =>
  apiFetch<{ ingests: Array<IngestRecord> }>("/api/tools/brain_recent_ingests", {
    method: "POST",
    body: JSON.stringify({ limit: limit ?? 20 }),
  });

export const createDomain = (slug: string, name: string, accentColor?: string) =>
  apiFetch("/api/tools/brain_create_domain", {
    method: "POST",
    body: JSON.stringify({ slug, name, accent_color: accentColor }),
  });

export const renameDomain = (from: string, to: string, rewriteFrontmatter = true) =>
  apiFetch("/api/tools/brain_rename_domain", {
    method: "POST",
    body: JSON.stringify({ from, to, rewrite_frontmatter: rewriteFrontmatter }),
  });

export const budgetOverride = (amountUsd: number, durationHours = 24) =>
  apiFetch("/api/tools/brain_budget_override", {
    method: "POST",
    body: JSON.stringify({ amount_usd: amountUsd, duration_hours: durationHours }),
  });
```

### WS events — typed discriminated union

```typescript
// apps/brain_web/src/lib/ws/events.ts
export const SCHEMA_VERSION = "2" as const;

// Server → client events (12 total after Task 5 adds doc_edit_proposed).
export type ServerEvent =
  | { type: "schema_version"; version: string }
  | { type: "thread_loaded"; thread_id: string; mode: string; turn_count: number }
  | { type: "turn_start"; turn_number: number }
  | { type: "delta"; text: string }
  | { type: "tool_call"; id: string; tool: string; arguments: Record<string, unknown> }
  | { type: "tool_result"; id: string; data: Record<string, unknown> }
  | { type: "cost_update"; tokens_in: number; tokens_out: number; cost_usd: number; cumulative_usd: number; cumulative_tokens_in: number }
  | { type: "patch_proposed"; patch_id: string; target_path: string; reason: string }
  | { type: "doc_edit_proposed"; edits: Array<{ op: "insert" | "delete" | "replace"; anchor: { kind: "line" | "text"; value: number | string }; text: string }> }
  | { type: "turn_end"; turn_number: number; title: string | null }
  | { type: "cancelled"; turn_number: number }
  | { type: "error"; code: string; message: string; recoverable: boolean };

// Client → server messages.
export type ClientMessage =
  | { type: "turn_start"; content: string; mode?: "ask" | "brainstorm" | "draft"; attached_sources?: string[] }
  | { type: "cancel_turn" }
  | { type: "switch_mode"; mode: "ask" | "brainstorm" | "draft" }
  | { type: "set_open_doc"; path: string | null };

export function parseServerEvent(raw: unknown): ServerEvent {
  if (typeof raw !== "object" || raw === null || !("type" in raw)) {
    throw new Error("WS event missing 'type' discriminator");
  }
  // Pass-through — trusting backend (Pydantic-validated on emit). Narrow via TypeScript.
  return raw as ServerEvent;
}
```

### WS client — connect + reconnect + schema v2 pin

```typescript
// apps/brain_web/src/lib/ws/client.ts
import { SCHEMA_VERSION, parseServerEvent, type ServerEvent, type ClientMessage } from "./events";

export interface WebSocketClientOptions {
  threadId: string;
  token: string;
  onEvent: (event: ServerEvent) => void;
  onClose?: (clean: boolean) => void;
  onOpen?: () => void;
  onSchemaVersionMismatch?: (received: string) => void;
  reconnectBaseMs?: number;
  reconnectMaxMs?: number;
}

export class BrainWebSocket {
  private ws: WebSocket | null = null;
  private opts: WebSocketClientOptions;
  private reconnectAttempt = 0;
  private manualClose = false;

  constructor(opts: WebSocketClientOptions) {
    this.opts = opts;
  }

  connect() {
    const url = `/api/proxy/ws/chat/${this.opts.threadId}?token=${encodeURIComponent(this.opts.token)}`;
    // Note: ws:// scheme converted by browser from the current page's scheme + host.
    // Next.js proxy route must handle WS upgrades — see route.ts variant for WS.
    const wsUrl = (window.location.protocol === "https:" ? "wss:" : "ws:") + "//" + window.location.host + url;

    this.ws = new WebSocket(wsUrl);
    this.ws.addEventListener("open", () => {
      this.reconnectAttempt = 0;
      this.opts.onOpen?.();
    });
    this.ws.addEventListener("message", (evt) => {
      let parsed: ServerEvent;
      try {
        parsed = parseServerEvent(JSON.parse(evt.data));
      } catch (err) {
        console.error("[brain-ws] failed to parse event", err, evt.data);
        return;
      }
      if (parsed.type === "schema_version" && parsed.version !== SCHEMA_VERSION) {
        console.warn(`[brain-ws] schema mismatch: expected ${SCHEMA_VERSION}, got ${parsed.version}`);
        this.opts.onSchemaVersionMismatch?.(parsed.version);
      }
      this.opts.onEvent(parsed);
    });
    this.ws.addEventListener("close", (evt) => {
      this.ws = null;
      this.opts.onClose?.(this.manualClose);
      if (!this.manualClose && evt.code !== 1008) {  // 1008 = policy violation (bad token)
        this.scheduleReconnect();
      }
    });
  }

  private scheduleReconnect() {
    const base = this.opts.reconnectBaseMs ?? 500;
    const max = this.opts.reconnectMaxMs ?? 30_000;
    const delay = Math.min(max, base * 2 ** this.reconnectAttempt);
    this.reconnectAttempt++;
    setTimeout(() => this.connect(), delay);
  }

  send(msg: ClientMessage) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn("[brain-ws] send called but socket not open");
      return;
    }
    this.ws.send(JSON.stringify(msg));
  }

  close() {
    this.manualClose = true;
    this.ws?.close(1000, "manual close");
    this.ws = null;
  }
}
```

**WS proxy via Next.js:** The catch-all `/api/proxy/[...path]` HTTP route from Task 8 does NOT handle WebSocket upgrades — Next.js Route Handlers can't natively proxy WS. Two options:

- **Option A (recommended):** frontend connects DIRECTLY to `ws://localhost:4317/ws/chat/<id>?token=<secret>`. The token is exposed to JS. Breaks the "browser never sees the token" property.
- **Option B:** custom Node server that handles WS upgrade. More work; breaks Next.js's default server.
- **Option C (best):** use Next.js middleware + an edge-function WS proxy. Complex; still needs a custom server.

**RESOLVED APPROACH:** read the token server-side in a Server Component, pass it to a Client Component as a prop ONLY for WS handshake. The token is transmitted over the Next.js SSR render (already same-origin), never exposed via a client-side `fetch`. The WS URL includes the token in the query param; WebSocket same-origin restrictions keep it loopback-only. On a token rotation (next `create_app()` call), the Next.js Server Component re-reads and the token refreshes.

This is a pragmatic compromise — the token leaks into JS memory (readable by the extension sandbox in the browser) but stays same-origin + loopback-only. Document as a known constraint; Plan 09 can tighten if needed.

### Step 1 — Failing tests

```typescript
// apps/brain_web/tests/unit/ws-events.test.ts
describe("parseServerEvent", () => {
  test("schema_version passes through", () => {
    const ev = parseServerEvent({ type: "schema_version", version: "2" });
    expect(ev.type).toBe("schema_version");
  });

  test("delta event has text", () => {
    const ev = parseServerEvent({ type: "delta", text: "hello" });
    if (ev.type !== "delta") throw new Error("wrong variant");
    expect(ev.text).toBe("hello");
  });

  // ... 4 more for tool_call, tool_result, cost_update w/ cumulative_tokens_in,
  //     patch_proposed, doc_edit_proposed, turn_end, cancelled, error ...
});
```

### Step 2 — Implement

All sketches above. WS client uses the exponential-backoff reconnect; bail on 1008 (auth failure) to avoid hammering bad-token connections.

### Step 3 — Run + commit

Expected: 15 new tests (5 api-client + 6 ws-events + 4 ws-client).

```bash
git commit -m "feat(web): plan 07 task 9 — typed API client + WS client (SCHEMA_VERSION=2 pin, reconnect)"
```

---

### Task 10 — Global shell + Zustand stores + routing

**Owning subagent:** brain-frontend-engineer

**Files:**
- Create: `apps/brain_web/src/lib/state/app-store.ts` — Zustand store (theme, mode, scope, view, rail, density)
- Create: `apps/brain_web/src/components/shell/topbar.tsx` — top bar (scope picker, mode switcher, cost meter, theme toggle, rail toggle, settings gear)
- Create: `apps/brain_web/src/components/shell/left-nav.tsx` — left nav (new chat, workspace nav, threads, settings)
- Create: `apps/brain_web/src/components/shell/right-rail.tsx` — right rail (context-sensitive content)
- Create: `apps/brain_web/src/components/shell/app-shell.tsx` — composition root (grid layout)
- Modify: `apps/brain_web/src/app/layout.tsx` — wrap children in `AppShell`
- Create: `apps/brain_web/src/app/{inbox,browse,pending,bulk,settings,setup}/page.tsx` — all placeholder pages
- Create: `apps/brain_web/tests/unit/app-store.test.ts` — 4 tests (defaults, theme persistence, scope toggle, invalid-state midturn)
- Create: `apps/brain_web/tests/unit/shell.test.tsx` — 5 tests (topbar renders, nav items clickable, rail toggles, mode switcher only on chat, scope picker opens)

**Context for the implementer:**

### Zustand store

```typescript
// apps/brain_web/src/lib/state/app-store.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ViewName = "chat" | "inbox" | "browse" | "pending" | "bulk" | "settings" | "setup";
export type ChatMode = "ask" | "brainstorm" | "draft";
export type Theme = "dark" | "light";
export type Density = "comfortable" | "compact";

interface AppState {
  theme: Theme;
  density: Density;
  mode: ChatMode;
  scope: string[];  // domain slugs
  view: ViewName;
  railOpen: boolean;
  activeThreadId: string | null;

  setTheme: (t: Theme) => void;
  setDensity: (d: Density) => void;
  setMode: (m: ChatMode) => void;
  setScope: (s: string[]) => void;
  toggleRail: () => void;
  setActiveThreadId: (id: string | null) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      theme: "dark",
      density: "comfortable",
      mode: "ask",
      scope: ["research", "work"],
      view: "chat",
      railOpen: true,
      activeThreadId: null,

      setTheme: (theme) => {
        document.documentElement.dataset.theme = theme;
        set({ theme });
      },
      setDensity: (density) => {
        document.documentElement.dataset.density = density;
        set({ density });
      },
      setMode: (mode) => set({ mode }),
      setScope: (scope) => set({ scope }),
      toggleRail: () => set((s) => ({ railOpen: !s.railOpen })),
      setActiveThreadId: (id) => set({ activeThreadId: id }),
    }),
    {
      name: "brain-app",
      partialize: (s) => ({
        theme: s.theme,
        density: s.density,
        mode: s.mode,
        scope: s.scope,
        railOpen: s.railOpen,
      }),  // DON'T persist `view` / `activeThreadId` — URL is source of truth
    },
  ),
);
```

### Shell composition

```tsx
// apps/brain_web/src/components/shell/app-shell.tsx
import { Topbar } from "./topbar";
import { LeftNav } from "./left-nav";
import { RightRail } from "./right-rail";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-grid">
      <Topbar />
      <LeftNav />
      <main className="main">{children}</main>
      <RightRail />
    </div>
  );
}
```

CSS grid in `globals.css`:

```css
.app-grid {
  display: grid;
  grid-template-rows: 48px 1fr;
  grid-template-columns: 240px 1fr 320px;
  grid-template-areas:
    "topbar topbar topbar"
    "leftnav main rail";
  height: 100vh;
}
.topbar { grid-area: topbar; }
.leftnav { grid-area: leftnav; }
.main { grid-area: main; overflow-y: auto; }
.rail { grid-area: rail; }
```

**Topbar** reads from `useAppStore` + calls `listDomains()` via React Query for the scope picker's available domains. **LeftNav** reads `view`; threads grouped by date come from `listThreads()` (new helper — TBD which tool backs it; Plan 04 doesn't expose a `list_threads` tool today — consider deriving from filesystem walk OR adding as a small Plan 07 task if needed). **RightRail** is context-sensitive; Task 16 fills in pending-patches for chat view, Task 18 fills in backlinks for browse view.

**Invalid-state mid-turn guards are a store concern:** when streaming is active (Task 15 wires this), `setMode` emits a `MidTurnToast` instead of changing mode.

```typescript
// Extended app-store:
setMode: (mode) => {
  if (get().streaming) {
    // Emit invalid-state-mode toast via a separate UI-toasts store.
    return;
  }
  set({ mode });
},
```

### Step 1 — Failing tests

Tests cover Zustand store defaults, theme application to `<html>`, and shell component rendering.

### Step 2 — Implement

Sketches above. Shell uses CSS grid (not Tailwind utility classes for the full app frame — semantic layout deserves dedicated CSS). Tailwind for component-level styling inside panels.

### Step 3 — Run + commit

Expected: 9 new tests (4 store + 5 shell). All 7 placeholder routes (`/chat`, `/inbox`, `/browse`, `/pending`, `/bulk`, `/settings`, `/setup`) navigate + render empty.

```bash
git commit -m "feat(web): plan 07 task 10 — global shell + Zustand stores + routing"
```

---

**Checkpoint 2 — pause for main-loop review.**

10 tasks landed. Frontend foundation:
- Next.js 15 package skeleton booted at `http://localhost:4316`
- TT design tokens + Roboto + dark/light theme + density
- shadcn/ui primitives generated (button, dialog, popover, select, tabs, input, textarea, checkbox, switch, separator, scroll-area, tooltip, dropdown-menu)
- Server-side auth proxy reads `.brain/run/api-secret.txt` and forwards REST calls; 503 on missing token
- WS client pinned to `SCHEMA_VERSION = "2"`, auto-reconnects, respects 1008 bail
- Typed API bindings for all 22 tools
- Zustand app store with persisted theme/mode/scope/density
- Global shell (topbar, left nav, right rail) + 7 routes navigable

Main loop reviews:

- Is `pnpm` the right package manager? The user's existing environment uses `uv` for Python; consistent with `pnpm` in the Node ecosystem. If npm is preferred, adapt task-6-time.
- WS token-in-URL compromise (see Task 9 context): acceptable? The token is same-origin + loopback-only in the browser; leaks to page-level JS. Browser extensions could theoretically read. The tradeoff is alternative requires a custom Next.js server which breaks the `next dev` and `next start` out-of-box flow. Track as Task 25 deferral or confirm now.
- Does `listThreads()` need a new backend tool, or is filesystem-walk `<vault>/<domain>/chats/*.md` enough? Plan 04 doesn't ship a list-threads tool. Consider adding to Task 4 or deferring to Plan 07 Group 4.
- The shell's CSS grid is fixed-width left nav (240px) + rail (320px). Does this adapt on 1024px minimum width? Probably tight — confirm via Playwright at 1024.
- Shadcn theme tokens vs TT custom tokens — any conflicts? Shadcn uses HSL variables by default; our tokens are hex. Both should coexist (shadcn variables have their `--background`, `--foreground`, etc. — we override in `tokens.css` to point at our surface palette).

Before Task 11, confirm the shell + auth + client + store are stable — Groups 3/4/5 all consume these primitives.

---

### Group 3 — Dialog system + setup wizard (Tasks 11–13)

**Pattern:** dialogs + system overlays are the connective tissue between screens. Group 3 lands them standalone so Groups 4/5 can compose without reinventing. Setup wizard lands here too because it's technically a full-screen "dialog" — a first-run takeover that uses the same modal primitive.

**Design reference:** the v3 design zip's `src/dialogs.jsx` + `src/dialogs-v3.jsx` + `src/screens.jsx` (SetupWizard) are the canonical implementations. Port them to TypeScript + shadcn/ui.

**Single mount point:** all system overlays (OfflineBanner, BudgetWall, MidTurnToast, DropOverlay, ConnectionIndicator, dialog host) mount once in `app/layout.tsx`. Trigger via Zustand store actions; render conditionally. Avoids "which component owns the modal?" confusion.

---

### Task 11 — Dialog primitives (Modal + Reject/Edit/TypedConfirm)

**Owning subagent:** brain-frontend-engineer

**Files:**
- Create: `apps/brain_web/src/lib/state/dialogs-store.ts` — Zustand store for dialog state
- Create: `apps/brain_web/src/components/dialogs/modal.tsx` — base Modal wrapping shadcn's `Dialog` with eyebrow + footer slots
- Create: `apps/brain_web/src/components/dialogs/reject-reason-dialog.tsx` — with preset chips + textarea
- Create: `apps/brain_web/src/components/dialogs/edit-approve-dialog.tsx` — side-by-side before/after editor
- Create: `apps/brain_web/src/components/dialogs/typed-confirm-dialog.tsx` — "type DELETE to confirm" pattern
- Create: `apps/brain_web/src/components/dialogs/dialog-host.tsx` — reads dialogs-store, renders active dialog
- Modify: `apps/brain_web/src/app/layout.tsx` — mount `<DialogHost />` inside `<AppShell>`
- Create: `apps/brain_web/tests/unit/modal.test.tsx` — 3 tests (open/close, escape key, backdrop click)
- Create: `apps/brain_web/tests/unit/reject-reason.test.tsx` — 3 tests (preset chip selection, textarea input, submit passes reason)
- Create: `apps/brain_web/tests/unit/typed-confirm.test.tsx` — 3 tests (disabled until exact match, case-sensitive match, submit fires onConfirm)
- Create: `apps/brain_web/tests/unit/dialog-store.test.ts` — 4 tests (open, close, switching active dialog, multiple modal stacking rejected)

**Context for the implementer:**

### Store shape

```typescript
// apps/brain_web/src/lib/state/dialogs-store.ts
import { create } from "zustand";

export type DialogKind =
  | { kind: "reject-reason"; patchId: string; targetPath: string; onConfirm: (reason: string) => void }
  | { kind: "edit-approve"; patchId: string; targetPath: string; before: string; after: string; onConfirm: (edited: string) => void }
  | { kind: "typed-confirm"; title: string; eyebrow?: string; body: string; word: string; danger?: boolean; onConfirm: () => void }
  | { kind: "file-to-wiki"; msg: { body: string; threadId: string }; onConfirm: (p: FileToWikiResult) => void }
  | { kind: "fork"; thread: ThreadMeta; turnIndex: number; onConfirm: (p: ForkResult) => void }
  | { kind: "rename-domain"; domain: DomainMeta; onConfirm: (from: string, to: string, rewrite: boolean) => void }
  | { kind: "doc-picker"; onPick: (path: string) => void; onNewBlank: () => void };

interface DialogsState {
  active: DialogKind | null;
  open: (d: DialogKind) => void;
  close: () => void;
}

export const useDialogsStore = create<DialogsState>((set) => ({
  active: null,
  open: (d) => set({ active: d }),
  close: () => set({ active: null }),
}));
```

**One-dialog-at-a-time rule.** No stacking. If a dialog is open and another `open()` is called, the first is replaced. (Stacking modals is confusing UX + keyboard-trap nightmare; if a flow needs two modals the second is a sub-step of the first and chained via `onConfirm`.)

### Base Modal

```tsx
// apps/brain_web/src/components/dialogs/modal.tsx
"use client";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { X } from "lucide-react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  eyebrow?: string;
  width?: number;
  footer?: React.ReactNode;
  children: React.ReactNode;
}

export function Modal({ open, onClose, title, eyebrow, width = 520, footer, children }: ModalProps) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent style={{ maxWidth: width }} className="modal-card">
        <DialogHeader>
          {eyebrow && <div className="eyebrow">{eyebrow}</div>}
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <div className="modal-body">{children}</div>
        {footer && <DialogFooter className="modal-foot">{footer}</DialogFooter>}
      </DialogContent>
    </Dialog>
  );
}
```

shadcn's `Dialog` handles: focus trap, escape-to-close, backdrop click, body-scroll-lock, ARIA labeling. We add eyebrow + footer slots to match the v3 design shape.

### Reject reason dialog

Presets from v3: `"Wrong domain"`, `"Already noted elsewhere"`, `"Source is unreliable"`, `"Too speculative"`, `"Formatting is off"`. Textarea for custom. Confirm button is `danger` variant.

Submit handler calls `brain_reject_patch(patchId, reason)` via the typed API client from Task 9, then closes.

### Edit-approve dialog

Two-column layout. Left: current file content (read-only, dim styling for "new file" case). Right: editable textarea initialized with `after`. Footer shows char count + Save/Cancel. On save: calls `brain_apply_patch(patchId)` — but the backend supports only single-patch-id apply, not "apply with edit." Two options:

**Option A — two-step:** user edits → dialog closes with the edited body → frontend calls `brain_reject_patch(patchId, "editing")` + `brain_propose_note(path, editedContent, "edited from patch")` → re-approves via `brain_apply_patch(newPatchId)`. Three round trips; clean semantics.

**Option B — extend `brain_apply_patch`:** add an optional `edited_body` kwarg. On receipt, rewrite the patch's NewFile/Edit content, then apply. Atomic; backend change.

**Recommendation: Option A.** No backend change, stays within the existing "all writes staged" invariant. Cost: three HTTP round-trips per edit-approve; cheap on localhost.

Document this in the dialog's `onConfirm` handler comment so the implementer doesn't accidentally reach for option B.

### Typed-confirm dialog

Exact-match requirement on a user-provided `word` (e.g., `"DELETE"`, `"UNINSTALL"`, `"RESTORE"`, or a domain name). Confirm button disabled until `input === word`. Case-sensitive. Matches v3 design's `TypedConfirmDialog`.

**Used by:** Settings → Domains → Delete; Settings → Backups → Restore; Settings → Integrations → Uninstall.

### DialogHost

```tsx
// apps/brain_web/src/components/dialogs/dialog-host.tsx
"use client";
import { useDialogsStore } from "@/lib/state/dialogs-store";
import { RejectReasonDialog } from "./reject-reason-dialog";
import { EditApproveDialog } from "./edit-approve-dialog";
import { TypedConfirmDialog } from "./typed-confirm-dialog";
// Task 20 adds: FileToWikiDialog, ForkDialog, RenameDomainDialog
// Task 19 adds: DocPickerDialog

export function DialogHost() {
  const active = useDialogsStore((s) => s.active);
  const close = useDialogsStore((s) => s.close);

  if (!active) return null;

  switch (active.kind) {
    case "reject-reason": return <RejectReasonDialog {...active} onClose={close} />;
    case "edit-approve": return <EditApproveDialog {...active} onClose={close} />;
    case "typed-confirm": return <TypedConfirmDialog {...active} onClose={close} />;
    // Task 19/20 cases filled in then.
    default: return null;
  }
}
```

### Step 1 — Failing tests

Cover each dialog's core interactions + the store's single-active contract.

### Step 2 — Implement

See sketches. Each dialog component accepts its own typed props + an `onClose` — the host coordinates.

### Step 3 — Run + commit

Expected: **~13 new tests** (3 + 3 + 3 + 4). Manual smoke: trigger each dialog via the store from a dev panel or console.

```bash
git commit -m "feat(web): plan 07 task 11 — dialog primitives (Modal + RejectReason + EditApprove + TypedConfirm)"
```

---

### Task 12 — System overlays (Offline + Budget + MidTurn + Drop + ConnectionIndicator)

**Owning subagent:** brain-frontend-engineer

**Files:**
- Create: `apps/brain_web/src/lib/state/system-store.ts` — Zustand for system UI state (connection, budget-wall-open, mid-turn-kind, dragging, toasts)
- Create: `apps/brain_web/src/components/system/offline-banner.tsx`
- Create: `apps/brain_web/src/components/system/budget-wall.tsx` — modal + session breakdown + model-switch hint
- Create: `apps/brain_web/src/components/system/mid-turn-toast.tsx` — 5 kinds (rate-limit, context-full, tool-failed, invalid-state-turn, invalid-state-mode)
- Create: `apps/brain_web/src/components/system/drop-overlay.tsx` — fullscreen drag-to-attach
- Create: `apps/brain_web/src/components/system/connection-indicator.tsx` — topbar pip
- Create: `apps/brain_web/src/components/system/system-overlays.tsx` — compositor that mounts all of the above
- Create: `apps/brain_web/src/components/system/toasts.tsx` — toast list with undo + countdown + auto-dismiss
- Modify: `apps/brain_web/src/app/layout.tsx` — mount `<SystemOverlays />` alongside `<DialogHost />`
- Modify: `apps/brain_web/src/components/shell/topbar.tsx` — include `<ConnectionIndicator />`
- Modify: `apps/brain_web/src/lib/ws/hooks.ts` — `useWebSocket(threadId)` drives `connection` state
- Create: `apps/brain_web/tests/unit/budget-wall.test.tsx` — 3 tests (renders cost breakdown, raise-cap button triggers `brain_budget_override`, close dismisses)
- Create: `apps/brain_web/tests/unit/mid-turn-toast.test.tsx` — 6 tests (one per kind + dismiss + retry)
- Create: `apps/brain_web/tests/unit/offline-banner.test.tsx` — 2 tests (offline copy, reconnecting copy)
- Create: `apps/brain_web/tests/unit/drop-overlay.test.tsx` — 2 tests (renders when dragging, hidden otherwise)
- Create: `apps/brain_web/tests/unit/system-store.test.ts` — 5 tests (dispatch actions, toast auto-dismiss timer, mid-turn kind switching, connection transitions, drag-enter/leave app-level handlers)

**Context for the implementer:**

### System store

```typescript
// apps/brain_web/src/lib/state/system-store.ts
import { create } from "zustand";

export type ConnectionState = "ok" | "reconnecting" | "offline";
export type MidTurnKind = "rate-limit" | "context-full" | "tool-failed" | "invalid-state-turn" | "invalid-state-mode";

export interface Toast {
  id: string;
  lead: string;
  msg: string;
  icon?: string;
  variant?: "default" | "success" | "warn" | "danger";
  countdown?: number;
  undo?: () => void;
}

interface SystemState {
  connection: ConnectionState;
  budgetWallOpen: boolean;
  midTurn: MidTurnKind | null;
  draggingFile: boolean;
  toasts: Toast[];

  setConnection: (s: ConnectionState) => void;
  openBudgetWall: () => void;
  closeBudgetWall: () => void;
  setMidTurn: (k: MidTurnKind | null) => void;
  setDragging: (v: boolean) => void;
  pushToast: (t: Omit<Toast, "id">) => void;
  dismissToast: (id: string) => void;
}

export const useSystemStore = create<SystemState>((set, get) => ({
  connection: "ok",
  budgetWallOpen: false,
  midTurn: null,
  draggingFile: false,
  toasts: [],

  setConnection: (connection) => set({ connection }),
  openBudgetWall: () => set({ budgetWallOpen: true }),
  closeBudgetWall: () => set({ budgetWallOpen: false }),
  setMidTurn: (midTurn) => set({ midTurn }),
  setDragging: (draggingFile) => set({ draggingFile }),
  pushToast: (t) => {
    const id = String(Date.now() + Math.random());
    set((s) => ({ toasts: [...s.toasts, { ...t, id }] }));
    // Auto-dismiss after 6s if no countdown was specified.
    if (!t.countdown) {
      setTimeout(() => get().dismissToast(id), 6000);
    }
  },
  dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));
```

### BudgetWall modal

Shows cost breakdown by mode (from `brain_cost_report` response — uses `by_mode` field added in Task 3). "Raise cap by $5 for today" button calls `brain_budget_override(5, 24)` (Task 4) → closes + `pushToast({lead: "Cap raised.", msg: "Today's cap is now $X.XX"})`.

Also shows the heaviest turn (derive from `brain_cost_report` history — future Plan 09 richer data) and a model-switch hint.

### MidTurnToast

Copy from delta-v2 §M3 + v3 design's 5-kind map:

```typescript
const COPY: Record<MidTurnKind, { lead: string; msg: string; icon: string; tone: "warn" | "danger" }> = {
  "rate-limit": { lead: "Rate limit.", msg: "Anthropic slowed us down. Retrying in 8s — or retry now.", icon: "alert", tone: "warn" },
  "context-full": { lead: "Context full.", msg: "Compact the thread to keep going, or start a fresh one.", icon: "layers", tone: "warn" },
  "tool-failed": { lead: "Tool failed.", msg: "A tool couldn't complete — the vault path may not be reachable.", icon: "x", tone: "danger" },
  "invalid-state-turn": { lead: "Finish this turn first.", msg: "Wait for it to complete, or cancel to start fresh.", icon: "clock", tone: "warn" },
  "invalid-state-mode": { lead: "Can't switch mid-turn.", msg: "Mode change takes effect on the next turn.", icon: "alert", tone: "warn" },
};
```

Non-blocking, auto-dismisses on next turn event (Task 15 wires this in the WS event handler).

### DropOverlay

Full-screen fixed overlay, pointer-events none until `draggingFile === true`. Centered card: "Drop to attach — brain will ingest and summarize before filing." File type chips (pdf, txt · md, eml, url) per v3 design.

Wire drag handlers at `<AppShell>` level:

```tsx
// app-shell.tsx
onDragEnter={(e) => {
  if (e.dataTransfer?.types?.includes("Files")) useSystemStore.getState().setDragging(true);
}}
onDragLeave={(e) => { if (e.relatedTarget === null) useSystemStore.getState().setDragging(false); }}
onDragOver={(e) => { if (e.dataTransfer?.types?.includes("Files")) e.preventDefault(); }}
onDrop={(e) => {
  e.preventDefault();
  useSystemStore.getState().setDragging(false);
  // Task 17 wires the actual ingest pipeline call.
}}
```

### ConnectionIndicator

Small pip in topbar. `ok` → hidden. `reconnecting` → yellow dot + "reconnecting…". `offline` → red dot + "offline". Reads `connection` from system-store.

### SystemOverlays compositor

```tsx
// components/system/system-overlays.tsx
"use client";
import { useSystemStore } from "@/lib/state/system-store";
import { OfflineBanner } from "./offline-banner";
import { BudgetWall } from "./budget-wall";
import { MidTurnToast } from "./mid-turn-toast";
import { DropOverlay } from "./drop-overlay";
import { Toasts } from "./toasts";

export function SystemOverlays() {
  const { connection, budgetWallOpen, midTurn, draggingFile, toasts, closeBudgetWall, setMidTurn, dismissToast } = useSystemStore();
  return (
    <>
      {connection !== "ok" && <OfflineBanner state={connection} />}
      <BudgetWall open={budgetWallOpen} onClose={closeBudgetWall} />
      {midTurn && <MidTurnToast kind={midTurn} onDismiss={() => setMidTurn(null)} />}
      <DropOverlay visible={draggingFile} />
      <Toasts toasts={toasts} dismiss={dismissToast} />
    </>
  );
}
```

### WS ↔ connection wiring

```typescript
// lib/ws/hooks.ts — useWebSocket hook
export function useWebSocket(threadId: string | null, token: string | null) {
  const setConnection = useSystemStore((s) => s.setConnection);
  // ...
  // On WS open: setConnection("ok")
  // On WS close (non-manual): setConnection("reconnecting")
  // On reconnect exhausted: setConnection("offline")
}
```

### Step 1 — Failing tests

### Step 2 — Implement

### Step 3 — Run + commit

Expected: **~18 new tests** (3 + 6 + 2 + 2 + 5). All dialogs + overlays render at the right times driven by store state.

```bash
git commit -m "feat(web): plan 07 task 12 — system overlays (OfflineBanner + BudgetWall + MidTurnToast + DropOverlay)"
```

---

### Task 13 — Setup wizard (6 steps + auto-detect first-run)

**Owning subagent:** brain-frontend-engineer

**Files:**
- Create: `apps/brain_web/src/app/setup/page.tsx` — full-screen wizard container
- Create: `apps/brain_web/src/components/setup/wizard.tsx` — stepper + navigation
- Create: `apps/brain_web/src/components/setup/steps/welcome.tsx`
- Create: `apps/brain_web/src/components/setup/steps/vault-location.tsx`
- Create: `apps/brain_web/src/components/setup/steps/api-key.tsx`
- Create: `apps/brain_web/src/components/setup/steps/starting-theme.tsx`
- Create: `apps/brain_web/src/components/setup/steps/brain-md.tsx`
- Create: `apps/brain_web/src/components/setup/steps/claude-desktop.tsx`
- Create: `apps/brain_web/src/lib/setup/detect.ts` — server-side first-run detection
- Modify: `apps/brain_web/src/app/page.tsx` — Server Component: read detect result, redirect to `/setup` if first-run
- Create: `apps/brain_web/tests/unit/setup-detect.test.ts` — 4 tests (missing BRAIN.md → true, exists → false, missing token → true, both present → false)
- Create: `apps/brain_web/tests/unit/wizard.test.tsx` — 5 tests (back/next navigation, step 1 skip link, final step closes wizard, step 2 vault validation, step 3 API key save)
- Create: `apps/brain_web/tests/e2e/setup-wizard.spec.ts` — Playwright (deferred to Task 23 actually but scaffolded here)

**Context for the implementer:**

### First-run detection

```typescript
// apps/brain_web/src/lib/setup/detect.ts
// Server-only — runs in Server Components.
import { access } from "node:fs/promises";
import { join } from "node:path";
import { homedir } from "node:os";
import { readToken } from "@/lib/auth/token";

export interface SetupStatus {
  isFirstRun: boolean;
  hasVault: boolean;
  hasToken: boolean;
  hasBrainMd: boolean;
  hasApiKey: boolean;
}

export async function detectSetupStatus(): Promise<SetupStatus> {
  const vaultRoot = process.env.BRAIN_VAULT_ROOT || join(homedir(), "Documents", "brain");

  const hasVault = await fileExists(vaultRoot);
  const hasToken = (await readToken()) !== null;
  const hasBrainMd = await fileExists(join(vaultRoot, "BRAIN.md"));
  // API key check — try a cheap brain_config_get roundtrip server-side
  const hasApiKey = hasToken ? await pingApi() : false;

  return {
    isFirstRun: !hasVault || !hasBrainMd || !hasApiKey,
    hasVault, hasToken, hasBrainMd, hasApiKey,
  };
}

async function fileExists(path: string): Promise<boolean> {
  try { await access(path); return true; } catch { return false; }
}

async function pingApi(): Promise<boolean> {
  // GET /healthz via the proxy; signal that backend is responsive.
  // Don't actually call brain_config_get here — keeps the detection cheap.
  // ...
}
```

### Root page → routing

```tsx
// apps/brain_web/src/app/page.tsx (SERVER COMPONENT)
import { redirect } from "next/navigation";
import { detectSetupStatus } from "@/lib/setup/detect";

export default async function RootPage() {
  const status = await detectSetupStatus();
  if (status.isFirstRun) {
    redirect("/setup");
  }
  redirect("/chat");
}
```

### Wizard structure

6 steps matching v3's `SetupWizard`:

1. **Welcome.** Copy: "A knowledge base that stays on your machine, run by an LLM you control. Nothing leaves this computer unless you tell it to." Skip link "Already set up → open app" (bottom-right).
2. **Vault location.** Default `~/Documents/brain`. Hint: "Your vault is a plain folder. Point Obsidian at it if you want."
3. **LLM provider.** Paste Anthropic API key. "Test" button pings. Link to "Get an API key →".
4. **Starting theme.** 4 cards — Research / Work / Personal / Blank. Picking one seeds `<vault>/<slug>/index.md` with a welcome note (patch staged via `brain_propose_note`).
5. **BRAIN.md.** Optional. Pre-filled template. Save triggers `brain_propose_note("BRAIN.md", content, "setup wizard seed")`.
6. **Claude Desktop integration.** Detect via `brain mcp status` (new helper tool wrapping Plan 04 integration module OR just checking the config file exists). Offer "Install MCP" button → calls `brain mcp install` equivalent (again, Plan 04 shipped this as a CLI verb; Plan 07 may need a `brain_mcp_install` tool that wraps `brain_core.integrations.claude_desktop.install`).

**Plan 04 MCP install integration note:** Plan 04 shipped `brain mcp install/uninstall/selftest/status` as CLI verbs. Plan 07's wizard needs to trigger these from the frontend — either:
- **Option X** — add new tools `brain_mcp_install`, `brain_mcp_uninstall`, `brain_mcp_status` to brain_core that wrap `brain_core.integrations.claude_desktop`. Clean; tool surface grows 22 → 25.
- **Option Y** — Next.js server-side route that execs `brain mcp install` as a subprocess. Ugly; couples frontend to CLI.

**Recommendation: Option X.** Add to Task 4 scope (tool surface growth was 18 → 22 with 4 tools; adding 3 more makes it 25). Document.

### Wizard state

Keep local to `<Wizard />` via `useState` — no need for Zustand persistence. Each step's form state lives in the step component. Next/Back buttons navigate. Final step "Start using brain" closes + sets localStorage flag `brain-setup-done=1` + redirects to `/chat`.

### Step 1 — Failing tests

Unit tests for detect + wizard. E2E scaffolded in Task 23.

### Step 2 — Implement

Port v3 design's `SetupWizard` to TypeScript. Each step is a separate component consuming form props + emitting to parent.

### Step 3 — Run + commit

Expected: **~9 new tests** (4 detect + 5 wizard).

```bash
git commit -m "feat(web): plan 07 task 13 — setup wizard (6 steps + first-run auto-detect)"
```

---

**Checkpoint 3 — pause for main-loop review.**

13 tasks landed. Dialog + setup infrastructure:
- Dialog host mounted once; store-driven single-active-dialog pattern
- 3 dialog primitives (RejectReason, EditApprove, TypedConfirm) — 4 more land in Group 5 (FileToWiki, Fork, RenameDomain, DocPicker)
- 5 system overlays (OfflineBanner, BudgetWall, MidTurnToast, DropOverlay, ConnectionIndicator)
- Toasts with undo + countdown
- 6-step setup wizard + first-run auto-detect via Server Component

Main loop reviews:

- **Edit-approve flow**: three round trips (reject old + propose new + apply new) per user edit. Acceptable for localhost; document in lessons.
- **MCP install from frontend**: recommended adding 3 new tools (`brain_mcp_install`/`uninstall`/`status`) to Task 4's scope. Retrocon Task 4 or add as a small Task 13a? Adding to Task 4 is cleaner — tool surface becomes **25 tools**. Confirm.
- **First-run detection**: uses `access()` + `readToken()` + `pingApi()`. Pinging API for every route hit is wasteful. Cache the status in a module-level variable? Invalidate on SIGHUP? Or accept that SSR re-runs are cheap enough?
- **Setup step 4 vault seeding**: pick-a-theme seeds index.md via `brain_propose_note`. This goes through the pending queue by default. Should the setup flow auto-apply (since the user just chose it) via `autonomous.ingest=true` temporarily? Or require explicit approval? (Explicit approval is an extra click on setup — friction — but matches the "every write staged" invariant. Lean toward auto-apply during setup, document as an exception.)

Before Task 14, confirm the dialog + system-overlay primitives + setup wizard are stable — Group 4 starts consuming them for Chat.

---
