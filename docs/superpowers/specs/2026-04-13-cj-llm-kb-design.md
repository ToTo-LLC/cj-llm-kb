# brain — Design Specification

**Date**: 2026-04-13
**Status**: Draft, pending user approval
**Author**: Brainstormed with Claude (superpowers:brainstorming)

## 1. Overview

`brain` is a local, LLM-maintained personal knowledge base following Andrej Karpathy's "LLM Wiki" pattern. Instead of doing RAG over raw documents on every query, the system incrementally compiles raw material into a persistent, interlinked Markdown wiki that the LLM curates over time. The user curates sources and asks questions; the LLM handles the bookkeeping.

The project serves three overlapping domains in one vault: **research** (learning, papers, articles), **work** (professional notes, meetings, project context), and **personal** (life admin, decisions, references). Domains are separated at the folder level with a default scope-per-thread model and opt-in cross-domain brainstorming.

Two front doors share one core:

1. A **local web app** (Next.js) providing drag-and-drop ingestion, a chat UI with Ask / Brainstorm / Draft modes, a patch-approval queue, bulk import, and setup/settings.
2. A **Claude Desktop integration** via a local **MCP server** exposing the same capabilities as MCP tools.

Both target Mac 13+ and Windows 11 as first-class platforms.

## 2. Goals and non-goals

### Goals

- Compile personal knowledge into a persistent, Obsidian-compatible Markdown wiki curated by an LLM.
- Support ingestion on day one of: plain text / Markdown, web URLs, PDFs, pasted emails, meeting transcripts (`.txt` / `.vtt` / `.srt` / `.docx`), and single tweets via URL.
- Provide conversational access in three modes: stateless Q&A (Ask), exploratory thinking partner (Brainstorm), and document collaboration (Draft).
- Keep humans in the loop: every LLM-originated vault write is staged as a typed patch set and requires approval by default; an optional autonomous mode skips approval but never validation.
- Enforce domain-level privacy: `personal` content never appears in default or cross-domain queries without an explicit opt-in.
- Track and cap spend: every LLM call is logged; daily/monthly budgets are hard kill switches with pre-call estimates in the UI.
- Run non-technical users through a browser-based setup wizard; no terminal required for normal use.
- Cross-platform first: Mac 13+ and Windows 11, bootstrap installer on both.

### Non-goals (day one; revisit later)

- OCR for scanned PDFs.
- Images, screenshots, audio transcription (Whisper), Notion/Apple Notes/Day One live sync, code-repo ingestion.
- Mobile web or native mobile apps (desktop-first, 1024px minimum).
- Multi-user / shared vaults / cloud sync (fully local, single user).
- Embeddings-based retrieval (Karpathy's pattern uses `index.md` as the retrieval layer; embeddings are a roadmap item if quality suffers).
- Native Electron / Tauri bundling (bootstrap installer ships faster; native is a roadmap item).
- Linux official support (should fall out of Mac code path; community-supported only).

## 3. High-level architecture

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
                                           ┌──────────────┐
                                           │  brain_core  │
                                           └──────┬───────┘
                                                  │ reads/writes
                                                  ▼
                                     ~/Documents/brain/  (vault)
```

### Approach: Core library + thin wrappers

A pure Python `brain_core` package owns all business logic with zero web/MCP dependencies. Three thin wrappers import it: `brain_cli`, `brain_mcp`, `brain_api`. A separate Next.js app `brain_web` talks to `brain_api` over REST and WebSocket.

Rationale: the only approach in which "swap the LLM provider later" and "add a new frontend later" are both trivially true, and the cleanest way to keep OS-sensitive code in one tested place.

### Repo layout

```
cj-llm-kb/
├── CLAUDE.md
├── .claude/
│   └── agents/               # seven project subagents
├── packages/
│   ├── brain_core/           # pure Python, no web/MCP deps
│   │   ├── vault/            # read/write, VaultWriter, scope_guard, wikilinks, index/log
│   │   ├── ingest/           # dispatcher + per-source-type handlers + adapters
│   │   ├── llm/              # LLMProvider protocol + Anthropic impl + FakeLLMProvider
│   │   ├── chat/             # chat loop, modes, tool definitions
│   │   ├── lint/             # consistency checks
│   │   ├── cost/             # token/spend tracking in costs.sqlite
│   │   ├── config/           # layered config + secrets handling
│   │   ├── integrations/
│   │   │   └── claude_desktop/  # MCP config detect/install/uninstall
│   │   ├── prompts/          # summarize, integrate, classify, lint, chat modes
│   │   └── tests/
│   ├── brain_cli/            # Typer-based CLI, setup wizard launcher
│   ├── brain_mcp/            # MCP server (stdio) for Claude Desktop
│   └── brain_api/            # FastAPI REST + WebSocket backend
├── apps/
│   └── brain_web/            # Next.js 15 + React + TypeScript + Tailwind + shadcn
├── docs/
│   ├── design/               # tokens, wireframes, mockups, flows, a11y, copy
│   ├── superpowers/specs/    # this spec lives here
│   ├── user-guide/
│   ├── testing/manual-qa.md
│   └── BRAIN.md.template
├── scripts/
│   ├── install.sh
│   └── install.ps1
├── pyproject.toml            # uv workspace root
├── package.json              # pnpm workspace root
└── README.md
```

### Tooling

- **Python**: `uv` workspace, Python 3.12+, mypy strict on `brain_core`
- **Node**: `pnpm` workspace, Node 20+
- **Install bootstrap**: `uv` installs Python itself; `fnm` or existing Node for Node runtime
- **Cross-platform**: `pathlib`, `filelock`, `watchdog`, `structlog`; no `shell=True`; no POSIX-only APIs

## 4. Vault schema

The vault lives at `~/Documents/brain/` (Mac) or `%USERPROFILE%\Documents\brain\` (Windows). It is Obsidian-compatible and entirely independent of the code — deleting the repo does not affect the vault.

```
~/Documents/brain/
├── .brain/                          # system dir
│   ├── config.json                  # user settings
│   ├── costs.sqlite                 # per-operation token/cost ledger
│   ├── state.sqlite                 # chat session metadata, ingest queue, lint cache
│   ├── secrets.env                  # API keys (chmod 600 on *nix, ACL-restricted on Windows)
│   ├── run/                         # PID files
│   ├── logs/                        # structured logs, rotated
│   └── migrations/                  # dry-run migration plans
├── .obsidian/                       # Obsidian's own config, auto-created on first open
├── .gitignore                       # ignores .brain/secrets.env, logs, run, sqlite caches
│
├── research/                        # domain
│   ├── sources/                     # one .md per ingested source
│   ├── entities/                    # people, orgs, products
│   ├── concepts/                    # ideas, frameworks, theories
│   ├── synthesis/                   # cross-cutting analyses, filed-from-chat notes
│   ├── index.md                     # curated catalog, LLM reads first
│   └── log.md                       # append-only operation log
├── work/
│   └── (same five files)
├── personal/
│   └── (same five files)
│
├── chats/                           # chat threads as Markdown
│   ├── research/
│   ├── work/
│   └── personal/
│
├── raw/                             # ingest inbox + archive
│   ├── inbox/
│   ├── failed/
│   └── archive/
│
└── BRAIN.md                         # schema doc: conventions, taxonomy, prompts, rules
```

### Conventions

- Filenames: `kebab-case-title.md`; sources get a date prefix `YYYY-MM-DD-slug.md`
- Cross-references: `[[wikilinks]]`, Obsidian-native, resolved by `brain_core.vault.links`
- Frontmatter (YAML) on every LLM-maintained file:
  ```yaml
  ---
  title: string
  domain: research | work | personal
  type: source | entity | concept | synthesis | chat
  created: date
  updated: date
  source_type: text | url | pdf | email | transcript | tweet  # sources only
  source_url: string                                          # sources only
  tags: [string]
  ingested_by: brain v<x.y>
  content_hash: sha256                                        # for idempotency
  ---
  ```
- `index.md`: per-domain curated catalog with `## Sources`, `## Entities`, `## Concepts`, `## Synthesis`; each entry one line: `- [[note-name]] — one-line summary`. Maintained by the LLM on every ingest.
- `log.md`: append-only, parseable: `## [2026-04-13 14:22] ingest | source | [[slug]] | touched: index, concepts/x, synthesis/y`
- `BRAIN.md` at vault root: the user-editable schema doc describing taxonomy, naming rules, wikilink conventions, and the system prompts/mode prompts. Loaded by every operation.

### Domain separation — Hybrid scoped model

- Top-level folders provide soft separation.
- Every query/chat thread has an **active scope**: one domain, or `cross-domain` (requires a one-time confirmation warning about personal content).
- Cross-scope is always opt-in; default queries stay in one domain.
- Scope is fixed per thread; changing scope requires a new thread (prevents mid-conversation leakage).

### SQLite role

`state.sqlite` and `costs.sqlite` are **derived caches**, not sources of truth. They can be rebuilt from vault content alone via `brain doctor --rebuild-cache`. This keeps the Markdown vault authoritative and portable.

## 5. Ingestion pipeline

Universal pipeline: any source arriving through any entry point (file drop, web drop zone, paste, URL, CLI, MCP tool) flows through the same stages.

### Stages

1. **Classify** — detect type (text / url / pdf / email / transcript / tweet)
2. **Fetch** — per-type handler produces normalized `{raw_bytes, content_type, source_url}`
3. **Extract** — `ExtractedSource` dataclass: `title, author, published, source_url, source_type, body_text, archive_path, extras`
4. **Archive** — originals stashed under `raw/archive/<domain>/<yyyy>/<mm>/<slug>.<ext>`
5. **Route** — LLM classifier (or user-specified) picks domain; low-confidence items land in `raw/inbox/unrouted/` for user pick
6. **Summarize** — LLM produces source-note frontmatter + body
7. **Integrate** — LLM reads `index.md` + related pages and returns a typed JSON patch set:
   ```json
   {
     "new_files": [{"path": "...", "content": "..."}],
     "edits":     [{"path": "...", "old": "...", "new": "..."}],
     "index_entries": [{"section": "Sources", "line": "- [[...]] — ..."}],
     "log_entry": "## [timestamp] ingest | ..."
   }
   ```
8. **Apply** — `VaultWriter` validates, fixes wikilinks, runs lint pre-check, atomic write-and-rename, records undo entry. Approval-gated by default; autonomous mode still validates and logs.
9. **Log & cost** — append to `log.md`, write cost row to `costs.sqlite`

### Day-one handlers

| Type | Library | Notes |
|---|---|---|
| text / .md | stdlib | drop as-is |
| url | `httpx` + `trafilatura` (fallback `readability-lxml`) | stores final resolved URL |
| pdf | `pymupdf` | text only; scanned PDFs flagged `needs_ocr`, skipped |
| email (pasted) | stdlib `email.parser` heuristic | treat as text with metadata extraction |
| transcript .txt / .vtt / .srt / .docx | stdlib / `webvtt-py` / `python-docx` | strips timestamps, preserves speakers |
| tweet url | `httpx` against `https://cdn.syndication.twimg.com/tweet-result?id=<id>` | marked `fragile: true`; clear error path |

All handlers implement a `SourceHandler` Protocol (`classify / fetch / extract`) and are registered in `HANDLERS: dict[str, SourceHandler]`. Adding types later is one new file.

### Bulk import

`brain migrate <folder>` walks a folder recursively (Obsidian vault, Notion export, plain Markdown day one; other adapters roadmap), classifies each file, batches the Integrate step per-domain, and saves a **dry-run patch tree** to `.brain/migrations/<timestamp>/`. User reviews the plan as a diff tree in the web UI; `brain migrate --apply` (or the Apply button) commits.

Idempotency: each note stores a `content_hash` in frontmatter; re-ingesting an already-seen file is a no-op unless `--force`.

### Failure handling

- Any stage can fail per-source without blocking the batch.
- Failures land in `raw/inbox/failed/<slug>.error.json` with stage, exception, and a retry command.
- Extract stage validates minimum content length (e.g., <200 chars from a 5 MB PDF → `needs_ocr`, skip, no token spend).
- Cost ceiling: projected ingest cost > configurable limit (default $1) pauses before Summarize/Integrate.

## 6. Chat and brainstorm loop

One loop, three modes selected by system prompt + tool policy. Streaming tokens to the UI via WebSocket (web app) or stdio (MCP) or stdout (CLI).

### Modes

| Mode | Goal | Tools allowed | Temp |
|---|---|---|---|
| **Ask** | Answer from wiki with citations; refuse to speculate beyond sources | read tools | 0.2 |
| **Brainstorm** | Push back, propose alternatives, ask Socratic questions, speculate when marked as such | read tools + `propose_note` | 0.8 |
| **Draft** | Collaborate on an open doc with wiki as background | read tools + `edit_open_doc` | 0.4 |

Mode selector is a dropdown at the top of the chat pane; switching mid-thread is logged as a system message in the transcript.

### Tool surface (available to the model during chat)

- `search_vault(query, domains, top_k)` — hybrid BM25 + frontmatter/tag filter over active scope
- `read_note(path)` — full content; scope-enforced
- `list_index(domain)` — `index.md` content
- `list_chats(domain, query)` — recall prior threads
- `propose_note(path, content, reason)` — (Brainstorm/Draft) stages a patch; does NOT write
- `edit_open_doc(range, new_text)` — (Draft) stages an edit to the currently-open doc

All writes are staged regardless of autonomous mode; autonomous mode only auto-approves the queue.

### Context compilation per turn

Before each LLM call:

1. Load `BRAIN.md` + mode-specific prompt
2. Load `index.md` for every domain in scope
3. Load any notes explicitly read in prior turns
4. Append the new user message

Hard context cap (configurable, default 150K of 200K) with a context-used meter in the UI and oldest-turn trimming when hit. No vector DB — retrieval is a tool call.

### Thread persistence

- File: `chats/<domain>/<yyyy-mm-dd>-<slug>.md`
- Frontmatter: `mode, scope, model, created, updated, turns, cost_usd, files_touched, filed_to?`
- Body: alternating `## User` / `## Assistant` sections; tool calls as fenced blocks so the thread reads well in Obsidian
- `state.sqlite` caches thread metadata for fast listing; Markdown file is source of truth
- Auto-title: after turn 2, a cheap LLM call produces a 3–6 word title and renames the file

### File-to-wiki action

Chat-pane button that opens a dialog: pick domain (prefilled with scope), type (defaults `synthesis`), editable proposed path, LLM-distilled body (not raw transcript). Approve flow is the same patch-approval UI. On approve: new note written, `index.md` updated, `log.md` appended (`synthesize | from-chat | [[thread]] → [[note]]`), thread frontmatter gets `filed_to: [[note]]` for bidirectional traceability.

### Streaming events

`brain_api` WebSocket emits: `delta`, `tool_call`, `tool_result`, `cost_update`, `patch_proposed`, `error`. The web UI renders tokens as they arrive, tool calls as collapsible inline cards, patches as cards in the right-side Pending changes panel.

## 7. MCP server surface

`brain_mcp` runs over stdio, uses the official `mcp` Python SDK, and wraps `brain_core`. Every tool has a JSON schema, typed outputs, and enforces scope via `Path.resolve()` checks.

### Tools

**Read:**
`brain_list_domains`, `brain_get_index`, `brain_read_note`, `brain_search`, `brain_recent`, `brain_get_brain_md`

**Ingest:**
`brain_ingest` (returns patch set; `autonomous` flag), `brain_classify`, `brain_bulk_import` (`dry_run=true` default)

**Writes / patches:**
`brain_propose_note`, `brain_list_pending_patches`, `brain_apply_patch`, `brain_reject_patch`, `brain_undo_last`

**Maintenance:**
`brain_lint`, `brain_cost_report`, `brain_config_get`, `brain_config_set`

Chat is **not** an MCP tool — Claude Desktop is itself the chat. It uses the read tools directly.

### Resources

- `brain://BRAIN.md`
- `brain://<domain>/index.md`
- `brain://config/public`

### Security

- Refuse paths that resolve outside `~/Documents/brain/<domain>/`
- `personal` domain reads require explicit inclusion in the `domains` argument — never in wildcards
- Secrets are never returned by any tool
- Patches capped at 50 files / 500 KB default
- Per-session rate limit on patches/min and tokens/min

### Claude Desktop integration

Auto-install via `brain_core.integrations.claude_desktop`: OS-aware config path detection, timestamped backup, safe merge with existing entries, verification, clean uninstall. Exposed via:

- `brain mcp install | uninstall | selftest` CLI verbs
- Setup wizard "Connect to Claude Desktop" step
- Settings → Integrations page with status, regenerate, remove, test-connection, and copy-snippet for other MCP clients (Cursor, Zed, etc.)

## 8. Web UI

Next.js 15 + React + TypeScript + Tailwind + shadcn/ui. Runs at `http://localhost:4317`. No auth (localhost only). Desktop-first, 1024px minimum.

### Dedicated design phase

**Design precedes implementation.** The `brain-ui-designer` subagent produces, in order, and with user review gates:

1. Design system + tokens (`docs/design/tokens.md` + Tailwind config + shadcn theme)
2. IA & flows (`docs/design/flows/`)
3. Wireframes for all screens with empty / loading / populated / error states
4. High-fidelity mockups, light + dark, all interaction states
5. Component inventory (`docs/design/components.md`)
6. Accessibility plan (`docs/design/a11y.md`, WCAG 2.2 AA)
7. Microcopy (`docs/design/copy.md`, non-technical voice)

No `brain_web` code is written until mockups for the target screen are approved.

### Global layout

- **Top bar**: domain switcher, mode switcher (chat screens), live cost meter, settings gear
- **Left nav**: Chat, Inbox, Browse, Pending changes (with badge), Bulk import, Settings
- **Right panel**: context-sensitive (Pending changes in chat; metadata + backlinks in Browse)

### Screens

1. **Chat** — thread list, streaming transcript, mode selector, scope indicator, context-used bar, drop-drag-paste input, "File to wiki", fork, export
2. **Inbox** — prominent drop zone supporting drag-and-drop / paste (Cmd-V) / file picker; tabs for Pending, In progress, Failed, Recent; watches `raw/inbox/`
3. **Pending changes** — patch cards with side-by-side diff view (Monaco read-only); per-patch Approve / Approve-with-edits / Reject; bulk actions; the autonomous-mode toggle (canonical definition: §6 chat loop and §5 ingest — toggling it only changes auto-approval of the queue, never the tool surface or validation); 5-second undo banner per auto-applied patch
4. **Browse** — file tree of active domain; reader pane with rendered Markdown + metadata strip + backlinks; Monaco editor for manual edits; full-text search; "Open in Obsidian" link via `obsidian://` scheme
5. **Bulk import** — pick folder → target domain → dry-run table → review/edit assignments → apply with streaming progress, cancellable, recoverable
6. **Settings** — tabs: General, LLM providers, Budget & costs, Autonomous mode, Integrations (Claude Desktop + copy-snippet for other clients), Domains, BRAIN.md editor, Backups

### Setup wizard

Full-screen first-run takeover, six steps, all skippable where safe:

0. Prerequisites self-check (Python, Node, vault write permissions, outbound HTTPS, free port)
1. Vault path picker (default `~/Documents/brain/`)
2. Anthropic API key (validated with a 1-token live test)
3. Domains (prefilled `research / work / personal`, editable/reorderable)
4. Optional bulk import (dry-run first, review, apply)
5. Connect Claude Desktop (auto-merge / copy / skip)
6. Budget defaults

Lands on the Chat screen with an inline tip card pointing to the Inbox.

### Non-technical usability

- Drag-and-drop, paste, file picker wherever content can enter
- Every destructive action shows a specific-consequence confirmation
- Plain-English errors with next actions
- Keyboard shortcuts exist but are never required
- Dark mode default, follows OS preference

## 9. Config, setup, cross-platform install, migration

### Distribution (day one)

One-command bootstrap, not a native bundle. Native bundling is a roadmap item.

- Mac/Linux: `curl -fsSL <INSTALL_URL>/install.sh | bash`
- Windows: `irm <INSTALL_URL>/install.ps1 | iex`

*(The install URL is a placeholder pending a decision on where the scripts are hosted — likely GitHub raw URLs once the repo is public. Until then, local dev installs clone the repo and run `scripts/install.sh` or `scripts/install.ps1` directly.)*

Both scripts: check prerequisites, install `uv` if missing, install Node 20 via `fnm` if missing, clone repo into `~/Applications/brain/` (Mac) or `%LOCALAPPDATA%\brain\` (Windows), run `uv sync` and `pnpm install && pnpm build`, register a launcher (Mac `.app` directory wrapper, Windows Start Menu + desktop `.cmd`), and put `brain` on PATH.

No sudo. No admin. No system Python dependency.

### `brain` CLI

```
brain start | stop | status
brain setup
brain add <path|url>
brain chat [--mode ...] [--domain ...]
brain migrate <folder> [--apply]
brain lint [--fix]
brain mcp install | uninstall | selftest
brain backup
brain upgrade
brain doctor
brain config get | set
brain uninstall
```

### Process model

- `brain start`: launches `brain_api` (uvicorn) in background, writes PID to `.brain/run/`, finds free port (4317 default, fall back 4318..4330), waits for `/healthz`, opens default browser
- `brain stop`: SIGTERM + cleanup
- Logs to `.brain/logs/` with rotation
- MCP server spawned on-demand by Claude Desktop; no port management

### Config resolution order

1. CLI flags
2. Environment variables (`BRAIN_VAULT`, `BRAIN_LLM_PROVIDER`, etc.)
3. `~/Documents/brain/.brain/config.json` (managed via Settings UI)
4. Hard-coded defaults

Secrets live only in `~/Documents/brain/.brain/secrets.env` (chmod 600 *nix, ACL-restricted Windows). Never in `config.json`, never in logs, never round-tripped to the frontend.

### Migration

Same code path for install-time and ongoing bulk import. Dry-run by default, patch tree saved to `.brain/migrations/<timestamp>/`, reviewable as diff tree, apply is a separate action. Adapters for Obsidian vault, Notion export, plain Markdown (day one). Idempotent via content hash. Partial failures park in `.brain/migrations/<timestamp>/failed/` with retry.

### Upgrades

`brain upgrade`: `git pull` + `uv sync` + `pnpm build` + DB migrations (yoyo or Alembic) + restart. Vault schema is forward-compatible (additive frontmatter, defaults for new fields). Non-blocking update-check toast on `brain start`, opt-out.

### Uninstall

Prompts in order:
1. Remove code at `~/Applications/brain/`?
2. Remove Claude Desktop MCP config?
3. **Keep vault at `~/Documents/brain/`?** — defaults to KEEP, typed confirmation required to delete
4. Remove backups?

The vault is sacred.

## 10. Error handling, testing, and non-functional requirements

### Error philosophy

1. Fail loudly at the boundary, gracefully in the middle. User-facing errors are plain English with an action; internal errors have full traces in logs but never leak raw.
2. Never lose user content. Partial ingest, crashed LLM call, rejected patch — originals remain. Failures park in `raw/inbox/failed/` with the error attached.
3. Vault is the source of truth. All derived stores rebuildable.

### Error taxonomy

| Class | Handling |
|---|---|
| User input errors | Plain-English UI message; Failed row with Retry; no log noise |
| External service errors | Exponential backoff 3× with jitter; honor `retry-after`; budget-hit → specific "out of budget" message |
| LLM output errors | Schema validator rejects; one auto-retry with error fed back; then escalate with raw output visible |
| Filesystem errors | Atomic write-and-rename; collisions get `-2` suffix; Obsidian file locks retry briefly; disk-full is a hard stop |
| Config / state errors | Startup validator surfaces a "Repair config" screen; SQLite caches rebuildable via `brain doctor --rebuild-cache` |
| Concurrency errors | `filelock` per note; single-writer queueing; vault-wide lock only for destructive ops |
| Cross-platform quirks | Normalized once at `VaultWriter`: sanitized filenames, LF on disk, `\\?\` Windows long paths |

### Logging and observability

- `structlog` JSON logs under `.brain/logs/brain.log`, rotated
- Every LLM call logs: op, model, input/output tokens, cost, latency, domain, correlation ID
- LLM prompt/response bodies NOT logged unless `log_llm_payloads=true` (with warning)
- Every vault write logs op, path, before/after hash, correlation ID (undo log)
- `brain doctor` reads last N hours of logs and surfaces ERRORs with context
- Settings → Diagnostics "Copy logs for support" produces a redacted zip

### Safety rails

- Hard daily/monthly budget ceilings with pre-call estimates
- Write ceilings: 50 files / 500 KB per operation; per-hour applied-patches cap
- LLM rate limit: token-bucket per minute and per hour
- 24h undo window via undo log; older reverts still possible by hand via log
- Pre-operation hardlink snapshots for ops touching ≥10 files; 7-day retention
- Domain firewall: single `scope_guard(path, allowed_domains)` function; all vault I/O passes through it

### Testing strategy

1. **`brain_core` unit tests** — pytest, `FakeLLMProvider`, >85% coverage target, paranoid on safety rails
2. **Integration tests** — real filesystem / SQLite / FastAPI test client / MCP stdio; golden vault fixture; all end-to-end pipelines
3. **LLM contract tests** — VCR-style cassettes committed; `RUN_LIVE_LLM_TESTS=1` re-records; asserts schema, tokens, scope, wikilinks
4. **Frontend component tests** — Vitest + React Testing Library
5. **Playwright e2e** — setup wizard, ingest drag-drop, patch approval, chat turn, bulk import dry-run; axe-core gate; visual regression against mockup baselines
6. **Manual QA checklist** — `docs/testing/manual-qa.md`, run on clean Mac + Windows VMs before each tag

CI matrix: Mac AND Windows; green Mac alone does not unblock merges.

### Non-functional requirements

- **Performance targets** (soft; revisit post-dogfood):
  - Ingest one ≤10K-word article: <30s wall clock
  - Chat first token: <3s
  - Bulk import 500 Markdown files dry-run: <2 min
  - Web UI initial load: <1.5s on localhost
  - Search over 10K-note vault: <200ms BM25
- **Scale target**: correct up to ~50K notes / 500 MB vault; beyond → embeddings roadmap
- **Portability**: Mac 13+ (Intel + Apple Silicon) and Windows 11; Linux community-supported
- **Offline posture**: fully functional offline except LLM calls; immediate clear error on send with no network
- **Privacy posture**: zero telemetry / analytics / crash reporting; only non-LLM outbound call is opt-out version check
- **Licensing**: MIT code; user's content in vault is the user's

### Documentation

- `README.md` — install, quickstart, screenshots
- `docs/user-guide/` — non-technical manual per screen
- `docs/BRAIN.md.template` — annotated default schema doc
- `docs/superpowers/specs/` — this spec, evergreen
- `docs/contributing.md`
- In-app `?` icon on every screen linking to relevant user-guide section

## 11. Subagents (project-specific)

Seven subagents defined in `.claude/agents/` — each tightly scoped and enforcing the design principles above:

- `brain-core-engineer`
- `brain-mcp-engineer`
- `brain-frontend-engineer` (gated on approved mockups)
- `brain-ui-designer` (runs first)
- `brain-prompt-engineer`
- `brain-test-engineer`
- `brain-installer-engineer`

The implementation plan will route work to these specialists. See `CLAUDE.md` for the workflow rules.

## 12. Day-one scope summary

**In scope**: text / url / pdf / pasted email / .txt+.vtt+.srt+.docx transcripts / tweet-url ingestion; Ask+Brainstorm+Draft chat; patch-approval queue; autonomous-mode toggle; cost meter + budget caps; web UI with drag-drop; MCP server + Claude Desktop auto-install; setup wizard; bulk import with dry-run; BRAIN.md editor; `brain doctor`; cross-platform install; Obsidian compatibility; hybrid domain scoping.

**Out of scope (roadmap)**: OCR; images/screenshots; audio/Whisper; Notion/Apple Notes live sync; code-repo ingest; mobile; multi-user/cloud; embeddings retrieval; native app bundling; email inbound/IMAP; paid Twitter API.

## 13. Open questions

None blocking at spec time. Items to revisit after first real usage:
- BM25 retrieval quality at >5K notes — may trigger embeddings roadmap item
- Actual monthly API spend distribution — may trigger model-routing tweaks (cheap Haiku for classify, Sonnet for chat, etc.)
- Whether the patch-approval friction is too high for daily use — autonomous-mode is the escape hatch; may warrant a "trust specific operations" middle ground

---

**End of spec.**
