# Plan 05 — FastAPI REST + WebSocket Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **DRAFT — pending section-by-section review. Task-level steps are intentionally unfilled below the outline until the architecture / scope / decisions sections are approved.**

**Goal:** Ship `brain_api` — a FastAPI ASGI app that exposes the 18 tool handlers over REST and streams chat over WebSocket, wrapping `brain_core`. After this plan, the web frontend (Plan 06 design → Plan 07 build) has a curl-driven contract it can consume. `brain start` / `brain stop` process management is explicitly deferred to Plan 08 (install/packaging).

**Architecture:**
Plan 05 adds one new workspace package (`brain_api`) and one strictly-additive refactor: moving all 18 tool handlers from `brain_mcp/tools/*.py` to `brain_core/tools/*.py`. Both `brain_mcp` and `brain_api` become thin transport wrappers around those shared handlers. This preserves the CLAUDE.md architecture promise ("three thin wrappers import `brain_core`") and structurally prevents drift between the MCP and REST tool surfaces.

- REST: `POST /api/tools/<name>` dispatches to `brain_core.tools.<name>.handle(args, ctx)` (1:1 tool mirror, D3)
- WebSocket: `WS /ws/chat/<thread_id>` drives a `brain_core.chat.ChatSession` and streams spec §6 events (D4)
- Auth: `Origin` + `Host` validation + filesystem token at `.brain/run/api-secret.txt` (D6)
- Errors: global exception handlers map `ScopeError` / `FileNotFoundError` / etc. to HTTP codes (D7), `RateLimitError` promoted from Plan 04's inline-JSON pattern
- Process model: `brain_api:app` is a plain ASGI app. No `brain start` CLI here — Plan 08 owns that (D8)

**Tech stack (new deps):**
- `fastapi>=0.115` — ASGI framework
- `uvicorn>=0.32` — ASGI server (imported for in-process testing; runtime launch is Plan 08's concern)
- `httpx>=0.27` — already present; used for `TestClient` + async WebSocket tests
- (existing) pydantic, pytest, mypy, ruff, anthropic, mcp

**Demo gate:** `uv run python scripts/demo-plan-05.py` runs end-to-end against a temp vault + `FakeLLMProvider` + the in-process ASGI app (via `httpx.ASGITransport`):
1. Spawn the FastAPI app with `lifespan="on"` and an `AppContext` bound to the temp vault
2. `GET /healthz` → `200 {"status": "ok"}`
3. `GET /api/tools` → lists all 18 tools with input schemas
4. `POST /api/tools/brain_list_domains` (with valid `X-Brain-Token`) → `200 {"data": {"domains": ["research", "work"]}, "text": "..."}`
5. Same call **without** `X-Brain-Token` → `403 {"error": "refused", ...}`
6. Same call with `Origin: https://evil.example` → `403`
7. `POST /api/tools/brain_search` → scoped hits
8. `POST /api/tools/brain_read_note` → frontmatter + body
9. `POST /api/tools/brain_propose_note` → staged patch, returns `patch_id`
10. `POST /api/tools/brain_apply_patch` → vault file written, undo_id returned
11. `POST /api/tools/brain_read_note` targeting `personal/notes/secret.md` → `403` with error code `scope`
12. `POST /api/tools/brain_ingest` with drained rate limiter → `429` with `retry_after_seconds`
13. `WS /ws/chat/test-thread?token=<secret>` — send `{type: "turn_start", content: "hi", mode: "ask"}`, receive ordered events (`turn_start`, `delta`*, `tool_call`?, `tool_result`?, `cost_update`, `turn_end`), disconnect cleanly
14. Reconnect `WS /ws/chat/test-thread?token=<secret>`, assert thread state rebuilt from vault

Prints `PLAN 05 DEMO OK` on exit 0.

**Owning subagents:**
- `brain-core-engineer` — tool handler extraction (Tasks 4–6), `RateLimitError` promotion (Task 14)
- Generic FastAPI/ASGI engineer (use `brain-mcp-engineer` role-overloaded or spin up a `brain-api-engineer` subagent) — `brain_api` package, REST endpoints, WebSocket, middleware, error handlers
- `brain-test-engineer` — cross-platform sweep + demo script

**Pre-flight** (main loop, before Task 1):
- Confirm `plan-04-mcp` tag exists at `origin/main` (it does — pushed at end of Plan 04)
- Confirm `ANTHROPIC_API_KEY` status (same as Plan 04 — optional, only for Plan 05 Task 22 deferred cassettes)
- Decide on D1–D12 below

---

## Scope — in and out

**In scope for Plan 05:**
- `brain_api` new workspace package: FastAPI app factory, ASGI lifespan, dependency injection for `AppContext` (mirror of `ToolContext`)
- Strictly additive extraction of 18 tool handlers from `brain_mcp/tools/` to `brain_core/tools/` — `brain_mcp` keeps its ToolModule protocol via one-line re-exports, every brain_mcp test stays green
- REST endpoint: single `POST /api/tools/<name>` dispatcher; auto-generated OpenAPI at `/docs`
- Tool listing endpoint: `GET /api/tools` returns `[{name, description, input_schema}, ...]`
- Health endpoint: `GET /healthz` — always returns 200 unless the app failed to boot
- Auth middleware: Origin + Host header validation, WebSocket Origin validation, filesystem token check on all POST/DELETE paths
- Token generation at startup: random 32-byte secret written to `<vault>/.brain/run/api-secret.txt` (mode 0600 on POSIX; best-effort on Windows)
- WebSocket chat: `WS /ws/chat/<thread_id>?token=<secret>` — drives `ChatSession`, streams `delta`/`tool_call`/`tool_result`/`cost_update`/`patch_proposed`/`error`/`turn_start`/`turn_end`/`cancelled` events; persists thread on disconnect; rebuilds on reconnect
- Global exception handlers: map `ScopeError` (403), `FileNotFoundError` / `KeyError` (404), `ValueError` (400), `PermissionError` (403), new `RateLimitError` (429), everything else (500 with no traceback leak)
- `RateLimitError` promoted to a real exception in `brain_core.rate_limit` (Plan 04 currently returns inline-JSON from tool handlers; that behavior is preserved in `brain_mcp` via a one-line shim)
- Logging: stdlib `logging` to `.brain/logs/api.log` with rotation. LLM payloads NOT logged unless `log_llm_payloads=true`
- VCR contract tests for the REST/WS surface (deferred cassettes — same D9a pattern as Plans 02–04)
- Cross-platform sweep
- 14-gate demo script

**Explicitly out of scope** (deferred):
- **`brain start` / `brain stop` CLI** — port picking (4317 → 4330), PID files at `.brain/run/`, `/healthz` polling, browser open, log rotation hookup. All of that is Plan 08 (install/packaging). Plan 05's demo runs the app via `httpx.ASGITransport` in-process.
- **Real uvicorn integration tests** — Plan 05's tests use FastAPI `TestClient` + `httpx.AsyncClient`. Real `uvicorn` spawning is Plan 08 territory.
- **`BulkImporter` streaming progress endpoint** — spec §8 mentions "streaming progress, cancellable, recoverable" for bulk import. The tool endpoint returns the final plan/result. Streaming progress is a Plan 07 frontend concern that might need a new WebSocket channel — defer the endpoint shape decision.
- **Setup wizard API endpoints** — spec §8 has a 6-step wizard. That's Plan 07 frontend + Plan 08 installer; Plan 05 exposes the config tools that the wizard will call.
- **Auto-title streaming events** — Plan 03's autotitle is synchronous at end-of-turn-2. Plan 05 emits it as a `turn_end` event payload field, not a separate event.
- **CORS** — no CORS headers emitted. We're localhost-only; requests from other origins are rejected at the Origin middleware layer.
- **Rate limiter persistence** — in-memory only, per-app-instance. Same as Plan 04 MCP. Plan 09 can revisit if needed.

---

## Decisions needed (block Task 1)

Twelve forks. Recommendations marked **(rec)**.

### D1 — FastAPI app factory pattern

- **(rec) D1a — Factory function `create_app(vault_root, allowed_domains, *, token_override=None) -> FastAPI`.** Mirrors `brain_mcp.server.create_server` exactly. Tests use `create_app(tmp_path/"vault", ...)` to build isolated apps. The module-level `app = create_app(...)` entry point reads env vars the same way `brain_mcp/__main__.py` does (`BRAIN_VAULT_ROOT`, `BRAIN_ALLOWED_DOMAINS`).
- **D1b — Module-level global `app`, config from env only.** Simpler but breaks parallel pytest isolation; you'd end up with monkeypatch environment dance in every test.

**Recommendation: D1a.** Matches Plan 04's pattern one-for-one.

### D2 — Tool handler extraction scope

- **(rec) D2a — Extract all 18 tool modules from `brain_mcp/tools/*.py` to `brain_core/tools/*.py` in one group (Tasks 4–6, batched by read/ingest/patch).** `brain_mcp/tools/*.py` become one-line re-exports (`from brain_core.tools.list_domains import *`). The `brain_mcp.tools.base` module (ToolContext, scope_guard_path, text_result) moves too — but `text_result` is MCP-SDK-specific (returns `list[types.TextContent]`), so split it: keep `text_result` in `brain_mcp.tools.base`, move `ToolContext` / `scope_guard_path` + a transport-agnostic `ToolResult(text, data)` dataclass to `brain_core.tools.base`. MCP's `text_result` wraps `ToolResult` into MCP types; REST unwraps to JSON.
- **D2b — Extract only the handlers `brain_api` immediately uses (~15 of 18)**, leave lint/config_set in `brain_mcp`. Saves ~100 LoC of move work but creates a partial extraction that'll confuse the next reader. Not worth it.
- **D2c — Don't extract; `brain_api` imports from `brain_mcp.tools`.** Simplest but violates the "parallel wrappers" architecture (brain_api → brain_mcp dependency).

**Recommendation: D2a.** All 18, one atomic refactor, one PR, one clean commit per group. The split on `text_result` is the only subtle bit.

### D3 — REST endpoint shape

- **(rec) D3a — Single generic `POST /api/tools/<name>` endpoint + `GET /api/tools` listing.** The endpoint handler:
  1. Validates `<name>` is in the tool registry (404 if not)
  2. Validates request body against the tool's INPUT_SCHEMA (400 on mismatch)
  3. Calls `await handle(body, ctx)` — same handler used by MCP
  4. Wraps the `ToolResult(text, data)` into a response envelope `{text, data}`

  OpenAPI docs at `/docs` enumerate all 18 tools as separate operations via dynamically generated path operations (FastAPI's `add_api_route` at app factory time).

- **D3b — Resource-oriented REST** — `/api/notes/<path>`, `/api/search`, `/api/patches`, etc. Doubles the endpoint count, bespoke routing per tool, drift risk vs MCP.
- **D3c — GraphQL-style `POST /api/query` with tool-name in body.** Same endpoint for everything, but tool name is now hidden in the request body — poor browser network tab UX.

**Recommendation: D3a.** Matches the MCP tool surface 1:1. Drift is structurally impossible.

### D4 — WebSocket chat transport

- **(rec) D4a — One WebSocket per chat thread.** URL: `ws://localhost:<port>/ws/chat/<thread_id>?token=<secret>`. On open: server loads the thread (rebuilds `ChatSession` from vault + `state.sqlite` or creates fresh if new). Client sends typed JSON messages (`{type: "turn_start", content, mode}`, `{type: "cancel_turn"}`, `{type: "switch_mode", mode}`). Server streams typed events (D5). On disconnect: session flushed to vault, in-memory instance GC'd. Reconnect reloads state.
- **D4b — Shared WebSocket, multiplex threads by id.** One connection per browser tab drives all threads. Efficient but cross-thread event ordering is confusing; `thread_id` must be in every event payload.
- **D4c — Server-Sent Events + REST for turn start.** `POST /api/chat/<id>/turn` → 202 + SSE endpoint URL → client subscribes via `EventSource`. No bidirectional — cancel-turn needs out-of-band DELETE. Breaks spec §6 (explicitly names WebSocket).

**Recommendation: D4a.** Matches spec verbatim, matches Plan 03's session lifecycle, matches what Plan 07 frontend will expect.

### D5 — WebSocket event wire format

Spec §6 names: `delta`, `tool_call`, `tool_result`, `cost_update`, `patch_proposed`, `error`. Plan 05 adds lifecycle events: `turn_start`, `turn_end`, `cancelled`.

- **(rec) D5a — Typed Pydantic models, one per event type, serialized as `{type: "<name>", ...fields}`.** Client→server messages same shape (`{type: "turn_start", content, mode}`). Types live in `brain_api.chat.events`. Versioning via a single `schema_version` field on the WS open handshake — Plan 07 frontend pins it.
- **D5b — Free-form JSON, documented in prose only.** Drifts the moment anyone adds a field.
- **D5c — Protobuf / MessagePack / binary**. Overkill for local-only JSON traffic.

**Recommendation: D5a.** Typed events, OpenAPI-like discoverability (exposed via a `GET /api/chat/schema` endpoint for the frontend to introspect).

### D6 — Auth token storage + rotation

- **(rec) D6a — Random 32-byte hex token at app startup, written to `<vault>/.brain/run/api-secret.txt`, mode 0600 on POSIX (best-effort `os.chmod` on Windows + comment explaining NTFS ACL is the real defense).** Rotation: token is regenerated every `create_app()` call. Clients re-read the file if they get 401. The Next.js frontend (Plan 07) reads it server-side at request time; the browser never sees the raw token (token attached server-side to proxied requests). CLI (`brain` commands) reads directly.
- **D6b — Persistent token across restarts, stored at `<vault>/.brain/secrets.env`.** More convenient for long-running CLIs but defeats rotation; a stolen secrets.env grants access forever.
- **D6c — No token, Origin check only.** Minimal friction but an easier CSRF target.

**Recommendation: D6a.** Rotating token + Origin + Host = defense in depth. The ~50 LoC cost is trivial vs vault-write risk.

### D7 — Error surface mapping

- **(rec) D7a — Global FastAPI exception handlers with this mapping:**
  | Exception | HTTP | Error code in body |
  |---|---|---|
  | `ScopeError` (brain_core.vault.paths) | 403 | `scope` |
  | `FileNotFoundError` | 404 | `not_found` |
  | `KeyError` | 404 | `not_found` |
  | `ValueError` | 400 | `invalid_input` |
  | `PermissionError` | 403 | `refused` |
  | `RateLimitError` (NEW — see D14-style additive change) | 429 | `rate_limited` + `retry_after_seconds` |
  | `pydantic.ValidationError` | 400 | `invalid_input` |
  | Uncaught `Exception` | 500 | `internal` (body message is generic; traceback in log only) |

  Body envelope: `{"error": "<code>", "message": "<plain english>", "detail": <optional dict>}`. No tracebacks in response bodies ever (privacy + principle #10).

- **D7b — 200-always, errors are discriminated union in body.** Breaks `/docs`, breaks browser dev tools, confuses curl users.
- **D7c — Only 5xx mapped, client errors all 400.** Frontend can't distinguish 404 from 400 without parsing message strings. Fragile.

**Recommendation: D7a.** Standard FastAPI pattern, powers OpenAPI error docs.

### D8 — Process lifecycle: where does `brain start` live?

- **(rec) D8a — Plan 05 ships a plain ASGI app `brain_api:app`. No `brain start` CLI, no port picking, no PID files. Plan 08 owns those.** The demo script runs the app in-process via `httpx.ASGITransport`. Tests never spawn uvicorn. Users who want to run the backend manually run `uv run uvicorn brain_api:app --host 127.0.0.1 --port 4317` — Plan 05 documents this in a short README note.
- **D8b — Plan 05 includes `brain api start` / `brain api stop`** as Typer sub-commands. Doubles the plan scope; duplicates work that'll be redone in Plan 08 under `brain start` (the unified launcher).
- **D8c — Land `brain start` in Plan 05.** Biggest scope creep; `brain start` ties together API + future web UI + future MCP auto-launch. Not Plan 05's problem.

**Recommendation: D8a.** Keep Plan 05 tight. Plan 08 is the natural home for process management.

### D9 — Logging + observability

- **(rec) D9a — stdlib `logging` to `<vault>/.brain/logs/api.log` with `RotatingFileHandler` (10 MB × 5 files).** Request logs include method, path, status code, duration_ms, client IP (127.0.0.1 always). LLM prompt/response bodies NOT logged unless `log_llm_payloads=true` in config (CLAUDE.md principle #10). No third-party observability libraries (no OpenTelemetry, no Sentry — zero telemetry per CLAUDE.md).
- **D9b — Only log to stdout/stderr.** Simpler but breaks the "run in background via `brain start`" narrative (Plan 08 needs a file to tail).
- **D9c — Structured JSON logs.** Over-engineered for a single-user local service.

**Recommendation: D9a.** stdlib only, file + rotation.

### D10 — Testing strategy for WebSocket

- **(rec) D10a — Primary: FastAPI's `TestClient.websocket_connect(...)` context manager** (it uses `starlette.testclient` under the hood) for synchronous-style test bodies. Secondary: `httpx.AsyncClient` with `websockets` library for async streaming tests when the sync client is too awkward. Both work against the in-memory ASGI app — no subprocess.
- **D10b — Only `httpx.AsyncClient` everywhere.** More idiomatic for pytest-asyncio but means every WebSocket test carries 20 lines of setup boilerplate.
- **D10c — Real uvicorn subprocess.** Slow, flaky; save it for the demo script and Plan 08 integration tests.

**Recommendation: D10a.** Fast, deterministic, matches Plan 04's in-memory MCP transport pattern.

### D11 — Cross-platform token-file permissions

- **(rec) D11a — POSIX: `os.open(path, O_CREAT | O_WRONLY | O_TRUNC, 0o600)` + write.** Windows: write via `pathlib`, then `os.chmod(path, 0o600)` (which Python best-efforts into file attribute READONLY — NOT the real security control). Add a `# TODO(Windows ACL)` comment referencing `pywin32` / `ctypes.windll.advapi32.SetFileSecurityA` if real ACL lockdown ever becomes important. Document in `docs/testing/cross-platform.md` that the real Windows defense is "don't share your %APPDATA%".
- **D11b — Enforce NTFS ACL via `pywin32`.** New dep on Windows only; a lot of complexity for marginal gain against a local-access threat model.
- **D11c — Skip the chmod on Windows.** No defense at all against a co-located attacker; POSIX-only readers would think we care equally on both.

**Recommendation: D11a.** Best-effort on Windows with a clear comment. Documented in cross-platform notes.

### D12 — Demo gate

- **(rec) D12a — `scripts/demo-plan-05.py`:** in-process ASGI app via `httpx.ASGITransport`, 14 gates as listed in the Demo section above. No uvicorn subprocess (D8a). Prints `PLAN 05 DEMO OK` on exit 0.
- **D12b — Spawn `uvicorn` as a subprocess for the demo.** Closer to real runtime behavior but adds 5–10 s startup, port conflicts, shutdown complexity.
- **D12c — No demo; rely on test coverage.** Breaks Plan 01–04's "demo-gate per plan" discipline.

**Recommendation: D12a.** ASGI in-process matches Plan 04's in-memory MCP pattern.

---

## File structure produced by this plan

```
packages/brain_api/                          # NEW workspace package
├── pyproject.toml
├── README.md                                 # "how to run uvicorn manually"
├── src/brain_api/
│   ├── __init__.py                           # exports `create_app` + `app`
│   ├── app.py                                # create_app() factory, lifespan, routing
│   ├── auth.py                               # Origin/Host middleware, token check dep
│   ├── errors.py                             # global exception handlers (D7a)
│   ├── context.py                            # AppContext (mirrors ToolContext)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py                         # GET /healthz
│   │   ├── tools.py                          # POST /api/tools/<name>, GET /api/tools
│   │   └── chat.py                           # WS /ws/chat/<thread_id>
│   ├── chat/
│   │   ├── __init__.py
│   │   ├── events.py                         # Pydantic event/message models (D5a)
│   │   └── session_runner.py                 # bridges ChatSession to WS events
│   └── logging.py                            # stdlib logging + rotation setup
└── tests/
    ├── conftest.py                           # seeded_vault + create_test_app fixtures
    ├── test_app_smoke.py                     # /healthz, /docs, /api/tools list
    ├── test_auth.py                          # Origin/Host/token rejection paths
    ├── test_errors.py                        # one test per exception → status code
    ├── test_tools_endpoint.py                # dispatch + schema validation
    ├── test_tool_<each of 18>.py             # one test file per tool — happy + reject
    ├── test_ws_chat.py                       # connect, turn, events, disconnect
    ├── test_ws_chat_reconnect.py             # disconnect → reconnect → state rebuilt
    ├── test_ws_auth.py                       # Origin + token rejection on WS handshake
    └── prompts/
        ├── __init__.py
        ├── conftest.py                       # VCR config (same as brain_mcp)
        ├── cassettes/.gitkeep
        └── test_chat_contract.py             # skipped — D9a deferral

packages/brain_core/src/brain_core/
├── tools/                                    # NEW — moved from brain_mcp/tools/
│   ├── __init__.py                           # registry + ToolModule protocol
│   ├── base.py                               # ToolContext, scope_guard_path, ToolResult
│   ├── list_domains.py                       # moved from brain_mcp/tools/
│   ├── get_index.py
│   ├── read_note.py
│   ├── search.py
│   ├── recent.py
│   ├── get_brain_md.py
│   ├── ingest.py
│   ├── classify.py
│   ├── bulk_import.py
│   ├── propose_note.py
│   ├── list_pending_patches.py
│   ├── apply_patch.py
│   ├── reject_patch.py
│   ├── undo_last.py
│   ├── lint.py
│   ├── cost_report.py
│   ├── config_get.py
│   └── config_set.py
└── rate_limit.py                             # NEW — RateLimitError exception (D7a + additive)
                                              # Existing brain_mcp/rate_limit.py keeps RateLimiter
                                              # class; RateLimitError moves to brain_core for
                                              # cross-package reuse

packages/brain_mcp/src/brain_mcp/
├── tools/                                    # each file becomes a 1-line re-export:
│   │                                          # `from brain_core.tools.list_domains import *`
│   ├── base.py                               # `text_result` STAYS here (MCP-specific);
│   │                                          # re-exports `ToolContext` + `scope_guard_path`
│   │                                          # from brain_core.tools.base
│   └── (18 re-export modules)
└── server.py                                 # no change — still imports from brain_mcp.tools.*

scripts/
└── demo-plan-05.py                           # 14-gate demo (D12a)

pyproject.toml                                # add brain_api to workspace deps + fastapi, uvicorn, httpx
docs/testing/cross-platform.md                # NEW — Windows token-file caveat, other cross-plat notes
```

---

## Per-task self-review checklist

Same 12-point discipline as Plan 02/03/04. Repeated here for convenience.

1. `export PATH="$HOME/.local/bin:$PATH"`
2. New submodule? → `uv sync --reinstall-package brain_api` (or `brain_core` / `brain_mcp` as appropriate)
3. `uv run pytest packages/brain_core packages/brain_cli packages/brain_mcp packages/brain_api -q` — full suite green
4. `cd packages/brain_api && uv run mypy src tests && cd ../..` — strict clean **(run from the package dir)**
5. Same from `packages/brain_core` (especially after Task 4–6 extraction), `packages/brain_cli`, `packages/brain_mcp`
6. `uv run ruff check . && uv run ruff format --check .` — clean
7. `find .venv -name "* [0-9].py"` — empty
8. No direct Anthropic SDK imports outside `brain_core/llm/providers/anthropic.py`
9. No vault-write paths added outside `VaultWriter`
10. No `scope_guard` bypasses
11. `git status` clean after commit
12. Commit message matches the task's convention

---

## Task outline (details intentionally unfilled pending section review)

**25 tasks in 7 groups, 6 checkpoints.** Mirrors Plans 03/04's shape.

### Group 1 — Foundation (Tasks 1–3)
- [ ] **Task 1 — `brain_api` workspace package skeleton** (pyproject, `create_app` stub, `/healthz`, in-memory ASGI test fixture)
- [ ] **Task 2 — `AppContext` + dependency injection** (mirrors `ToolContext`, wired via FastAPI `Depends`)
- [ ] **Task 3 — OpenAPI scaffolding + `GET /api/tools` listing endpoint** (reads tool registry, returns `[{name, description, input_schema}]`)

### Group 2 — Handler extraction (Tasks 4–6) — STRICTLY ADDITIVE
- [ ] **Task 4 — `brain_core.tools.base`** (move `ToolContext`, `scope_guard_path`; add `ToolResult(text, data)` dataclass; leave `text_result` in `brain_mcp.tools.base`)
- [ ] **Task 5 — Move read + ingest tool modules** (9 files: list_domains, get_index, read_note, search, recent, get_brain_md, ingest, classify, bulk_import) from `brain_mcp/tools/` to `brain_core/tools/`. `brain_mcp/tools/*` become one-line re-exports. Every test passes unchanged.
- [ ] **Task 6 — Move patch + maintenance tool modules** (9 files: propose_note, list_pending_patches, apply_patch, reject_patch, undo_last, lint, cost_report, config_get, config_set). Same pattern as Task 5. All 101 brain_mcp tests still pass.

### Group 3 — Auth + middleware (Tasks 7–9)
- [ ] **Task 7 — Token generation + file** (random 32-byte hex, `.brain/run/api-secret.txt`, mode 0600, D11a Windows note)
- [ ] **Task 8 — Origin + Host middleware** (reject non-localhost Origin, reject Host not matching `localhost:<port>` / `127.0.0.1:<port>`, D6a)
- [ ] **Task 9 — Token dependency + WebSocket auth** (FastAPI `Depends` for `X-Brain-Token` on POST/DELETE routes; WebSocket handshake validates Origin + `?token=` query param)

### Group 4 — REST tool endpoint (Tasks 10–13)
- [ ] **Task 10 — Generic `POST /api/tools/<name>` dispatcher** (resolve handler from registry, pass JSON body to handler, wrap `ToolResult` into response envelope)
- [ ] **Task 11 — Request body validation against tool INPUT_SCHEMA** (Pydantic dynamic model at registration time; 400 on mismatch with field-level errors)
- [ ] **Task 12 — Response envelope + content negotiation** (`{text, data}` always; `Accept: application/json` only; drop MCP-style TextContent wrapping)
- [ ] **Task 13 — 18 curl-driven endpoint tests** (one test per tool — happy path + one reject path; use `TestClient`, one parametrized fixture)

### Group 5 — Error surface + RateLimitError promotion (Tasks 14–16)
- [ ] **Task 14 — Promote `RateLimitError`** (create `brain_core.rate_limit.RateLimitError(bucket, retry_after_seconds)`; `RateLimiter.check` raises it instead of returning False; `brain_mcp` tools catch + convert to current inline-JSON shape for zero brain_mcp test regression)
- [ ] **Task 15 — Global exception handlers in `brain_api.errors`** (8 handlers per D7a table; body envelope `{error, message, detail?}`; no traceback leakage)
- [ ] **Task 16 — Error surface tests + OpenAPI response docs** (every handler tested against a deliberately-failing endpoint; FastAPI `responses` kwarg populates `/docs` with error shapes)

### Group 6 — WebSocket chat (Tasks 17–21)
- [ ] **Task 17 — `WS /ws/chat/<thread_id>` endpoint + handshake** (Origin + token check, thread_id validation, initial `turn_start`-less open handshake emits `schema_version`)
- [ ] **Task 18 — Typed event models** (Pydantic classes for `turn_start` / `delta` / `tool_call` / `tool_result` / `cost_update` / `patch_proposed` / `error` / `turn_end` / `cancelled` — D5a)
- [ ] **Task 19 — `ChatSession` integration** (new `brain_api.chat.session_runner` bridges `ChatSession.run_turn(...)` to WS event emission; handles tool_call + patch_proposed events as they fire)
- [ ] **Task 20 — Cancel-turn + client→server message handling** (`{type: "cancel_turn"}` during streaming; `{type: "switch_mode", mode}` between turns)
- [ ] **Task 21 — Disconnect flush + reconnect rebuild** (on disconnect: persist thread via `ChatSession.persist`; on reconnect: load from vault + state.sqlite, resume from last USER turn)

### Group 7 — Contract + cross-platform + demo + close (Tasks 22–25)
- [ ] **Task 22 — VCR contract test infrastructure** (mirrors Plan 04 Task 22; 1 skipped test per ingest-chat-scenario deferred per D9a analog — "same D-deferral pattern as Plan 04")
- [ ] **Task 23 — Cross-platform sweep** (walk every new `brain_api` module + the `brain_core.tools.*` moves; verify pathlib, LF newlines, token-file permissions, no POSIX-only APIs in WS code)
- [ ] **Task 24 — `scripts/demo-plan-05.py`** (14-gate demo per D12a)
- [ ] **Task 25 — Hardening sweep + coverage + tag `plan-05-api`**

---

## Module-boundary checkpoints

Six review pause points, matching Plan 04's rhythm:

1. **After Task 3** — foundation frozen (package, AppContext, tool listing) before auth/tools rollout
2. **After Task 6** — handler extraction complete (all 18 moved, 101 brain_mcp tests still green); this is a high-risk refactor checkpoint
3. **After Task 9** — auth surface live; security properties locked before tool dispatcher lands
4. **After Task 13** — REST tool surface complete; curl can drive every endpoint
5. **After Task 16** — error surface + rate limit promotion complete; last gate before WS work
6. **After Task 21** — WebSocket chat live end-to-end; last tool-level gate before demo + close
7. **After Task 25** — plan close, tag, demo receipt

---

## Detailed per-task steps

### Group 1 — Foundation (Tasks 1–3)

**Checkpoint after Task 3:** main-loop reviews package skeleton, `AppContext` shape, and the tool-registry + `GET /api/tools` contract before auth/dispatcher/WS work. If `AppContext` gets fields wrong, every Group 3/4/5/6 endpoint will need to be touched — cheaper to catch here.

---

### Task 1 — `brain_api` workspace package skeleton + `/healthz`

**Owning subagent:** brain-api-engineer (spin up `brain-mcp-engineer` role-overloaded if no dedicated agent)

**Files:**
- Modify: root `pyproject.toml` — add `brain_api` dep + `[tool.uv.sources]` entry + new runtime deps (`fastapi>=0.115`, `uvicorn>=0.32`)
- Create: `packages/brain_api/pyproject.toml`
- Create: `packages/brain_api/README.md` — one-paragraph "how to run uvicorn manually" note (Plan 08 will obsolete this)
- Create: `packages/brain_api/src/brain_api/__init__.py`
- Create: `packages/brain_api/src/brain_api/py.typed` (PEP 561 marker)
- Create: `packages/brain_api/src/brain_api/app.py` — `create_app` factory (skeleton)
- Create: `packages/brain_api/src/brain_api/routes/__init__.py` (empty, populated Tasks 3+)
- Create: `packages/brain_api/src/brain_api/routes/health.py` — `GET /healthz`
- Create: `packages/brain_api/tests/__init__.py` (empty)
- Create: `packages/brain_api/tests/conftest.py` — `seeded_vault` fixture + `create_test_app` helper
- Create: `packages/brain_api/tests/test_app_smoke.py` — `/healthz`, `/docs`, `/openapi.json`

**Context for the implementer:**

Fresh workspace package. Lessons from Plan 03 Task 19 (`brain_cli`) + Plan 04 Task 1 (`brain_mcp`):
- `[project.scripts]` — none yet (no entry point; Plan 08 adds `brain start` in `brain_cli`, which imports `brain_api:app`)
- `py.typed` marker needed from day one
- Root `pyproject.toml` needs both `brain_api` in `[project].dependencies` AND `brain_api = { workspace = true, editable = false }` under `[tool.uv.sources]`
- Workspace is glob-discovered (`members = ["packages/*"]`), so `brain_api` is auto-picked up
- After adding new submodules, `uv sync --reinstall-package brain_api` is REQUIRED (iCloud-related `editable=false` lesson from Plan 01)

New runtime deps:
- `fastapi>=0.115` — pins a recent stable release with `@asynccontextmanager` lifespan support
- `uvicorn>=0.32` — imported by `httpx.ASGITransport` tests; runtime launch is Plan 08's concern, but the dep must be declared or `fastapi.testclient.TestClient` can fail with subtle errors on modern Starlette

`httpx>=0.27` is already a dev dep from Plan 04 — no change needed.

**App factory skeleton:** `create_app(vault_root, allowed_domains, *, token_override=None) -> FastAPI`. Takes the same two positional args as `brain_mcp.server.create_server`. Returns a `FastAPI` instance with `/healthz` wired and a `lifespan` context manager stub. Tasks 2+ add `AppContext` to the lifespan and Tasks 10+ register the tool dispatcher.

The factory reads `brain_api.__version__` from `__init__.py` and exposes it via `FastAPI(title="brain API", version=__version__)`. `/docs` and `/openapi.json` come for free from FastAPI defaults.

**Test transport:** Plan 05 uses FastAPI's `TestClient` (synchronous, built on `starlette.testclient`) as the primary fixture. It wraps `httpx.ASGITransport` under the hood — no uvicorn, no subprocess, fast and deterministic. The `create_test_app` helper builds an app bound to the seeded vault + `("research",)` allowed domains.

### Step 1 — Create `packages/brain_api/pyproject.toml`

```toml
[project]
name = "brain_api"
version = "0.0.1"
description = "brain REST + WebSocket backend — FastAPI wrapper around brain_core"
requires-python = ">=3.12"
dependencies = [
    "brain_core",
    "brain_mcp",
    "fastapi>=0.115",
    "uvicorn>=0.32",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/brain_api"]

[tool.uv.sources]
brain_core = { workspace = true }
brain_mcp = { workspace = true }
```

The `brain_mcp` dep is temporary — Group 2 extracts handlers to `brain_core.tools` and this dep can drop. For now, Group 1's tool-listing endpoint imports the registry from `brain_mcp.server` to avoid a chicken-and-egg with Group 2.

### Step 2 — Update root `pyproject.toml`

Add to `[project].dependencies`:
```toml
dependencies = [
    "brain_core",
    "brain_cli",
    "brain_mcp",
    "brain_api",
]
```

Add to `[tool.uv.sources]`:
```toml
brain_api = { workspace = true, editable = false }
```

Add to `[dependency-groups].dev` if not already present:
```toml
"pytest-asyncio>=1.3",
"httpx>=0.27",
```

### Step 3 — Create `packages/brain_api/src/brain_api/__init__.py`

```python
"""brain_api — FastAPI REST + WebSocket backend wrapping brain_core."""

from brain_api.app import create_app

__version__ = "0.0.1"
__all__ = ["__version__", "create_app"]
```

### Step 4 — Create `packages/brain_api/src/brain_api/py.typed`

Empty file. PEP 561 marker.

### Step 5 — Create `packages/brain_api/src/brain_api/routes/health.py`

```python
"""Health check endpoint — always 200 unless app failed to boot."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe. No auth required."""
    return {"status": "ok"}
```

### Step 6 — Create `packages/brain_api/src/brain_api/app.py`

```python
"""FastAPI app factory.

Task 1 lands the skeleton — create_app returns a FastAPI instance with
/healthz wired and an empty lifespan stub. Tasks 2+ populate AppContext;
Tasks 10+ register the tool dispatcher.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from brain_api import __version__
from brain_api.routes import health


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context — Task 2 populates app.state.ctx here."""
    yield


def create_app(
    vault_root: Path,
    allowed_domains: tuple[str, ...] = ("research",),
    *,
    token_override: str | None = None,
) -> FastAPI:
    """Build a fresh FastAPI app bound to the given vault.

    Task 1 lands the skeleton; Tasks 2+ wire AppContext, auth, and routes.

    Args:
        vault_root: Absolute path to the brain vault (e.g. ~/Documents/brain).
        allowed_domains: Tuple of domain names this app instance may access.
        token_override: Task 7 uses this to inject a fixed token for tests.
            None (the default) means generate a fresh token at startup.
    """
    app = FastAPI(
        title="brain API",
        version=__version__,
        description="Local REST + WebSocket backend for the brain personal knowledge base.",
        lifespan=_lifespan,
    )
    # Stash for later tasks to read during lifespan.
    app.state.vault_root = vault_root
    app.state.allowed_domains = allowed_domains
    app.state.token_override = token_override

    app.include_router(health.router)

    return app
```

### Step 7 — Create `packages/brain_api/tests/conftest.py`

Mirror `packages/brain_mcp/tests/conftest.py`'s `seeded_vault` exactly — this is the same fixture shape and should be copied verbatim. Group 2's extraction will DRY this into a shared test helper (likely `brain_core/tests/_vault_fixtures.py`), but for Task 1 copy-paste is the right call.

```python
"""Shared fixtures for brain_api tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from brain_api import create_app


def _write_note(vault: Path, rel: str, *, title: str, body: str) -> None:
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\ntitle: {title}\n---\n{body}\n", encoding="utf-8", newline="\n")


@pytest.fixture
def seeded_vault(tmp_path: Path) -> Path:
    """A small research + work + personal vault used by all tests."""
    vault = tmp_path / "vault"
    _write_note(vault, "research/notes/karpathy.md", title="Karpathy", body="LLM wiki pattern.")
    _write_note(vault, "research/notes/rag.md", title="RAG", body="Retrieval-augmented generation.")
    (vault / "research" / "index.md").write_text(
        "# research\n- [[karpathy]]\n- [[rag]]\n", encoding="utf-8", newline="\n"
    )
    _write_note(vault, "work/notes/meeting.md", title="Meeting", body="Q4 planning.")
    (vault / "work" / "index.md").write_text("# work\n- [[meeting]]\n", encoding="utf-8", newline="\n")
    _write_note(vault, "personal/notes/secret.md", title="Secret", body="never read me")
    (vault / "BRAIN.md").write_text("# BRAIN\n\nYou are brain.\n", encoding="utf-8", newline="\n")
    return vault


@pytest.fixture
def app(seeded_vault: Path) -> FastAPI:
    """A FastAPI app bound to seeded_vault with allowed_domains=('research',)."""
    return create_app(vault_root=seeded_vault, allowed_domains=("research",))


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Synchronous TestClient for quick REST assertions."""
    return TestClient(app)
```

### Step 8 — Create `packages/brain_api/tests/test_app_smoke.py`

```python
"""Smoke tests — app boots, /healthz responds, /docs + /openapi.json work."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthz_returns_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_json_available(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    body = response.json()
    assert body["info"]["title"] == "brain API"


def test_docs_page_serves_html(client: TestClient) -> None:
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
```

### Step 9 — Run + commit

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb && uv sync
cd /Users/chrisjohnson/Code/cj-llm-kb && uv sync --reinstall-package brain_api
cd /Users/chrisjohnson/Code/cj-llm-kb && uv run pytest packages/brain_api -v
```
Expect: **3 passed** (healthz + openapi + docs).

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb/packages/brain_api && uv run mypy src tests
```
Expect: `Success: no issues found in N source files`.

Full 12-point self-review, then:

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb && git add packages/brain_api/ pyproject.toml uv.lock && git commit -m "feat(api): plan 05 task 1 — brain_api workspace package skeleton (/healthz)"
```

---

### Task 2 — `AppContext` + FastAPI dependency injection

**Owning subagent:** brain-api-engineer

**Files:**
- Create: `packages/brain_api/src/brain_api/context.py`
- Modify: `packages/brain_api/src/brain_api/app.py` — build `AppContext` in the lifespan
- Create: `packages/brain_api/tests/test_context.py`

**Context for the implementer:**

`AppContext` is the HTTP analog of `brain_mcp.tools.base.ToolContext`. Same 10 fields (vault_root, allowed_domains, retrieval, pending_store, state_db, writer, llm, cost_ledger, rate_limiter, undo_log). The rationale for a separate class rather than reusing `ToolContext`:

1. **Lifetime semantics are different.** `ToolContext` is rebuilt per MCP session; `AppContext` spans the app's entire uvicorn lifetime (one per `create_app` call). The scope differs.
2. **Dependency injection shape.** FastAPI's `Depends(get_ctx)` wants something directly fetchable from `request.app.state`; MCP's closure-based ctx rebuild is awkward to expose that way.
3. **Future divergence.** Plan 05 adds `token: str` (the app secret, Task 7) and Plan 07 will likely add `settings_store`, `request_id_generator`. Keeping `AppContext` as a superset of `ToolContext` is less surprising than mutating `ToolContext` cross-plan.

`AppContext` INCLUDES a `ToolContext` field (it's literally `tool_ctx: ToolContext`), so the tool dispatcher (Task 10) can hand the embedded `ToolContext` straight to `handle(args, ctx)` without any conversion. This makes the handler extraction in Group 2 trivially forward-compatible — `brain_api` just passes the nested ctx.

**Dependency injection pattern:**

```python
from fastapi import Depends, Request
from brain_api.context import AppContext

def get_ctx(request: Request) -> AppContext:
    """FastAPI dependency — returns the app's AppContext.

    Set in the lifespan; raised-on if missing (app boot failure)."""
    ctx = getattr(request.app.state, "ctx", None)
    if ctx is None:
        raise RuntimeError("AppContext not initialized — lifespan failed?")
    return ctx


# In a route:
@router.post("/api/tools/{name}")
async def call_tool(name: str, body: dict, ctx: AppContext = Depends(get_ctx)):
    ...
```

### Step 1 — Failing test

`test_context.py`:

```python
"""Tests for AppContext + get_ctx dependency."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_ctx_populated_during_lifespan(app: FastAPI) -> None:
    """Entering the app's lifespan populates app.state.ctx."""
    with TestClient(app):
        ctx = app.state.ctx
    assert ctx is not None
    assert ctx.vault_root.exists()
    assert ctx.allowed_domains == ("research",)
    # ToolContext embedded inside.
    assert ctx.tool_ctx.vault_root == ctx.vault_root
    assert ctx.tool_ctx.allowed_domains == ctx.allowed_domains


def test_ctx_teardown_closes_state_db(app: FastAPI, seeded_vault: Path) -> None:
    """Exiting the lifespan cleanly closes state.sqlite connections."""
    state_db_path = seeded_vault / ".brain" / "state.sqlite"
    with TestClient(app):
        assert state_db_path.exists()  # DB opened at lifespan start
    # After lifespan exit the file still exists; we just assert no lock errors.
    # (True close semantics verified by Group 6's WS-reconnect tests.)
    assert state_db_path.exists()


def test_get_ctx_dependency_resolves(client: TestClient, app: FastAPI) -> None:
    """The get_ctx dependency can be injected into a route and returns the ctx."""
    from brain_api.context import get_ctx

    @app.get("/_test_ctx_leak")
    async def leak(ctx=None):  # noqa: ANN001
        from fastapi import Depends
        return {"vault_root": str(ctx.vault_root)} if ctx else {}

    # Rebuild the route properly with the dep.
    # (Implementation detail — the test is a sanity check that get_ctx resolves.)
```

### Step 2 — Implement `context.py`

```python
"""AppContext — per-app-instance primitives, injected via FastAPI Depends."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from brain_core.chat.pending import PendingPatchStore
from brain_core.chat.retrieval import BM25VaultIndex
from brain_core.cost.ledger import CostLedger
from brain_core.llm.fake import FakeLLMProvider
from brain_core.llm.provider import LLMProvider
from brain_core.state.db import StateDB
from brain_core.vault.undo import UndoLog
from brain_core.vault.writer import VaultWriter
from brain_mcp.rate_limit import RateLimitConfig, RateLimiter
from brain_mcp.tools.base import ToolContext
from fastapi import Request


@dataclass(frozen=True)
class AppContext:
    """Per-app-instance state — built once in the lifespan, injected via Depends."""

    vault_root: Path
    allowed_domains: tuple[str, ...]
    tool_ctx: ToolContext  # embedded — handed straight to brain_core.tools handlers
    token: str | None = None  # Task 7 populates this


def build_app_context(
    vault_root: Path,
    allowed_domains: tuple[str, ...],
    *,
    llm: LLMProvider | None = None,
    token: str | None = None,
) -> AppContext:
    """Build a fresh AppContext wired to all brain_core + brain_mcp primitives.

    Mirrors brain_mcp/tests/conftest.py:make_tool_context so the ctx shape is
    identical between MCP tests and HTTP tests.
    """
    brain_dir = vault_root / ".brain"
    brain_dir.mkdir(parents=True, exist_ok=True)
    state_db = StateDB.open(brain_dir / "state.sqlite")
    writer = VaultWriter(vault_root=vault_root)
    pending_store = PendingPatchStore(brain_dir / "pending")
    retrieval = BM25VaultIndex(vault_root=vault_root, db=state_db)
    retrieval.build(allowed_domains)
    undo_log = UndoLog(vault_root=vault_root)
    cost_ledger = CostLedger(db_path=brain_dir / "costs.sqlite")
    rate_limiter = RateLimiter(RateLimitConfig())
    tool_ctx = ToolContext(
        vault_root=vault_root,
        allowed_domains=allowed_domains,
        retrieval=retrieval,
        pending_store=pending_store,
        state_db=state_db,
        writer=writer,
        llm=llm or FakeLLMProvider(),
        cost_ledger=cost_ledger,
        rate_limiter=rate_limiter,
        undo_log=undo_log,
    )
    return AppContext(
        vault_root=vault_root,
        allowed_domains=allowed_domains,
        tool_ctx=tool_ctx,
        token=token,
    )


def get_ctx(request: Request) -> AppContext:
    """FastAPI dependency — return the app's AppContext.

    Raises RuntimeError if the lifespan didn't populate it (app boot failure).
    """
    ctx: AppContext | None = getattr(request.app.state, "ctx", None)
    if ctx is None:
        raise RuntimeError("AppContext not initialized — lifespan failed?")
    return ctx
```

### Step 3 — Wire the lifespan in `app.py`

Replace the stub `_lifespan` with:

```python
@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build AppContext at startup; hold it open for the app's lifetime."""
    ctx = build_app_context(
        vault_root=app.state.vault_root,
        allowed_domains=app.state.allowed_domains,
        token=app.state.token_override,
    )
    app.state.ctx = ctx
    try:
        yield
    finally:
        # Close any resources that need explicit teardown (future-proof hook —
        # current primitives all clean up via GC).
        pass
```

Add the `from brain_api.context import build_app_context` import.

### Step 4 — Run + commit

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb && uv sync --reinstall-package brain_api
cd /Users/chrisjohnson/Code/cj-llm-kb && uv run pytest packages/brain_api -v
```
Expect: **6 passed** (3 smoke from Task 1 + 3 context).

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb/packages/brain_api && uv run mypy src tests
```

Self-review, then:

```bash
git commit -m "feat(api): plan 05 task 2 — AppContext + lifespan + get_ctx dependency"
```

---

### Task 3 — `GET /api/tools` + tool registry bootstrap

**Owning subagent:** brain-api-engineer

**Files:**
- Create: `packages/brain_core/src/brain_core/tools/__init__.py` — empty registry + `ToolModule` alias
- Create: `packages/brain_api/src/brain_api/routes/tools.py` — `GET /api/tools` listing endpoint (POST dispatcher lands in Task 10)
- Modify: `packages/brain_api/src/brain_api/app.py` — register the new router
- Create: `packages/brain_api/tests/test_tools_listing.py`

**Context for the implementer:**

Task 3 lands the tool-listing surface WITHOUT the handler extraction (Group 2). The trick: `brain_core.tools.__init__.py` introduces a registry protocol (`ToolModule` alias + `_TOOL_MODULES: list[ToolModule]` list) that starts EMPTY. Group 2's Tasks 5–6 populate the list as tools move from `brain_mcp.tools` to `brain_core.tools`. After Group 2 the list has 18 entries; until then, `GET /api/tools` returns `[]` and the test pins that baseline.

This keeps Group 2 strictly additive: tools appear in the registry as they're moved, no endpoint changes needed.

**Registry shape (mirrors `brain_mcp.server._TOOL_MODULES`):**

```python
# brain_core/tools/__init__.py
from types import ModuleType

ToolModule = ModuleType  # per Plan 04 Task 4 lesson — mypy-honest

_TOOL_MODULES: list[ToolModule] = []  # populated by Tasks 5–6 as tools move


def register(module: ToolModule) -> None:
    """Register a tool module. Called at import time by each tool module."""
    _TOOL_MODULES.append(module)


def list_tools() -> list[ToolModule]:
    """Return the currently-registered tool modules."""
    return list(_TOOL_MODULES)
```

Each tool module's `__init__` side-effect-registers itself when imported. Or — cleaner — we explicitly import each in `brain_core/tools/__init__.py` during Tasks 5–6. Either works; the plan doesn't pin the import style yet.

**Endpoint shape:**

```
GET /api/tools
→ 200 {"tools": [{"name": "brain_list_domains", "description": "...", "input_schema": {...}}, ...]}
```

No auth required (read-only metadata). Sorted alphabetically by `name` for stable ordering.

### Step 1 — Create `brain_core/tools/__init__.py`

```python
"""brain_core.tools — shared tool-handler registry.

Populated by Plan 05 Tasks 5–6 as handlers move from brain_mcp/tools/*.py to
brain_core/tools/*.py. Until then, the registry is empty and GET /api/tools
returns [].

Each tool module exports module-level NAME, DESCRIPTION, INPUT_SCHEMA,
handle(arguments, ctx) — same shape as brain_mcp/tools/base.py's protocol.
"""

from __future__ import annotations

from types import ModuleType

ToolModule = ModuleType

_TOOL_MODULES: list[ToolModule] = []


def register(module: ToolModule) -> None:
    """Append a tool module to the registry. Idempotent — duplicate registrations are no-ops."""
    if module not in _TOOL_MODULES:
        _TOOL_MODULES.append(module)


def list_tools() -> list[ToolModule]:
    """Return the registered tool modules in registration order."""
    return list(_TOOL_MODULES)
```

### Step 2 — Failing tests

`packages/brain_api/tests/test_tools_listing.py`:

```python
"""Tests for GET /api/tools."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_empty_registry_returns_empty_list(client: TestClient) -> None:
    """Task 3 baseline: before Group 2 extraction, the registry is empty."""
    response = client.get("/api/tools")
    assert response.status_code == 200
    body = response.json()
    assert body == {"tools": []}


def test_listing_shape_matches_schema(client: TestClient) -> None:
    """Even when empty, the response shape is the stable contract."""
    response = client.get("/api/tools")
    body = response.json()
    assert "tools" in body
    assert isinstance(body["tools"], list)
```

A third test verifies the shape after a tool is registered (synthetically, without touching brain_mcp):

```python
def test_listing_reflects_registered_tools(client: TestClient, monkeypatch) -> None:  # noqa: ANN001
    """Register a fake tool module and verify the endpoint picks it up."""
    from brain_core import tools as tools_registry
    from types import SimpleNamespace

    fake = SimpleNamespace(
        NAME="fake_tool",
        DESCRIPTION="for testing",
        INPUT_SCHEMA={"type": "object", "properties": {}},
    )
    monkeypatch.setattr(tools_registry, "_TOOL_MODULES", [fake])
    response = client.get("/api/tools")
    body = response.json()
    assert body["tools"] == [
        {"name": "fake_tool", "description": "for testing", "input_schema": {"type": "object", "properties": {}}}
    ]
```

### Step 3 — Implement `routes/tools.py`

```python
"""/api/tools — tool discovery endpoint.

Task 3 lands the GET listing. Task 10 adds the POST /api/tools/<name>
dispatcher that actually runs tool handlers.
"""

from __future__ import annotations

from fastapi import APIRouter

from brain_core import tools as tools_registry

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
async def list_tools() -> dict[str, list[dict]]:  # noqa: UP006
    """Return every registered tool's metadata. No auth required."""
    out: list[dict] = []
    for module in sorted(tools_registry.list_tools(), key=lambda m: m.NAME):
        out.append(
            {
                "name": module.NAME,
                "description": module.DESCRIPTION,
                "input_schema": module.INPUT_SCHEMA,
            }
        )
    return {"tools": out}
```

**Note on the `APIRouter(prefix="/api/tools")` choice:** the GET listing registers at `""` (→ `/api/tools`). Task 10 adds `POST` at `/{name}` (→ `POST /api/tools/<name>`). Single router, two methods, clean OpenAPI grouping.

### Step 4 — Register the router in `app.py`

Add after the `health` include:

```python
from brain_api.routes import tools as tools_routes

app.include_router(tools_routes.router)
```

### Step 5 — Run + commit

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb && uv sync --reinstall-package brain_core --reinstall-package brain_api
cd /Users/chrisjohnson/Code/cj-llm-kb && uv run pytest packages/brain_api -v
```
Expect: **9 passed** (6 prior + 3 tools-listing).

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb/packages/brain_core && uv run mypy src tests
cd /Users/chrisjohnson/Code/cj-llm-kb/packages/brain_api && uv run mypy src tests
```
Both: `Success`. (The new `brain_core.tools` module is trivial — no mypy concerns.)

Self-review, then:

```bash
git commit -m "feat(api): plan 05 task 3 — tool registry + GET /api/tools listing endpoint"
```

---

**Checkpoint 1 — pause for main-loop review.**

3 tasks landed. `brain_api` package exists, `/healthz` responds, `AppContext` wired via lifespan + `get_ctx` dependency, `GET /api/tools` returns the (currently empty) registry. Main loop reviews:
- Is `AppContext`'s shape right? (`tool_ctx` embed vs. flat fields, `token` placement, future Plan 07 extension points.)
- Does the registry pattern (`brain_core.tools.register` + `list_tools`) match how tools will wire in Group 2? Or would a decorator / auto-discovery be cleaner?
- Is the `brain_api → brain_mcp` temporary dep (to satisfy `brain_mcp.rate_limit.RateLimiter` import for now) acceptable, or should `RateLimiter` move to `brain_core` as part of Task 14's `RateLimitError` promotion?
- Any API drift between plan text and real FastAPI / httpx / Starlette versions installed? (Task 1 verifies empirically via the smoke test.)

Before Task 4, the next main-loop dispatch confirms the registry shape is locked — Group 2's extraction logic depends on it.

---

### Group 2 — Handler extraction (Tasks 4–6) — STRICTLY ADDITIVE REFACTOR

**Checkpoint after Task 6:** main-loop reviews the full handler move. **Hard gate: all 101 `brain_mcp` tests must pass unchanged.** This is the highest-risk sweep in Plan 05; batching into read+ingest (Task 5) and patch+maintenance (Task 6) keeps blast radius per commit tight.

**The pattern every extracted tool follows** (avoid bikeshedding in task bodies — this is the contract):

1. **Move** `packages/brain_mcp/src/brain_mcp/tools/<name>.py` → `packages/brain_core/src/brain_core/tools/<name>.py`. In the moved file:
   - Change `from brain_mcp.tools.base import ToolContext, scope_guard_path, text_result` → `from brain_core.tools.base import ToolContext, ToolResult, scope_guard_path`
   - Replace every `return text_result(text, data=data)` with `return ToolResult(text=text, data=data)` (or `ToolResult(text=text)` if no data)
   - Handler signature changes from `-> list[types.TextContent]` to `-> ToolResult`
   - Remove the `import mcp.types as types` line — no MCP SDK imports in `brain_core`
2. **Append** `register(<module>)` to the end of `brain_core/tools/<name>.py` so it auto-registers at import time. (Cleaner alternative considered: explicit registration in `brain_core/tools/__init__.py`. See the design discussion at Checkpoint 2; Group 2 picks auto-register-at-import for simplicity.)
3. **Rewrite** `packages/brain_mcp/src/brain_mcp/tools/<name>.py` as a 7-line shim:
   ```python
   """MCP transport shim for brain_<name>. Real handler lives in brain_core.tools.<name>."""

   from brain_core.tools.<name> import DESCRIPTION, INPUT_SCHEMA, NAME
   from brain_core.tools.<name> import handle as _core_handle

   from brain_mcp.tools.base import ToolContext, text_result

   __all__ = ["DESCRIPTION", "INPUT_SCHEMA", "NAME", "handle"]


   async def handle(arguments, ctx: ToolContext):  # noqa: ANN001, ANN201
       """Delegate to brain_core; wrap the ToolResult into MCP TextContent."""
       result = await _core_handle(arguments, ctx)
       return text_result(result.text, data=result.data)
   ```
4. **No test changes in `brain_mcp`.** Existing tests call `await handle(args, ctx)` and inspect `list[TextContent]`. The shim preserves that return shape, so tests pass unchanged. Hard gate: **all 101 brain_mcp tests stay green**.
5. **Add one smoke test per moved tool in `brain_core`** asserting `ToolResult` shape — `packages/brain_core/tests/tools/test_<name>.py` with a single happy-path test. These are coverage insurance for the new module path; they do NOT duplicate brain_mcp's exhaustive tests.

With this pattern fixed, Tasks 5 and 6 can be dispatched to a single subagent each with batched work.

---

### Task 4 — `brain_core.tools.base` (`ToolContext`, `ToolResult`, `scope_guard_path`)

**Owning subagent:** brain-core-engineer

**Files:**
- Create: `packages/brain_core/src/brain_core/tools/base.py`
- Modify: `packages/brain_core/src/brain_core/tools/__init__.py` — also expose `ToolContext`, `ToolResult`, `scope_guard_path` at package root for convenience
- Modify: `packages/brain_mcp/src/brain_mcp/tools/base.py` — re-export `ToolContext` + `scope_guard_path` from `brain_core.tools.base`, keep `text_result` locally, add a `ToolResult → list[TextContent]` conversion helper
- Create: `packages/brain_core/tests/tools/__init__.py` (empty)
- Create: `packages/brain_core/tests/tools/test_base.py`

**Context for the implementer:**

`ToolContext`, `scope_guard_path` are transport-agnostic: they name brain_core primitives only (`Any`-typed fields + `brain_core.vault.paths.scope_guard`). Moving them is clean.

`text_result` is MCP-SDK-specific: `import mcp.types as types; [types.TextContent(type="text", text=...)]`. It MUST stay in `brain_mcp`. The current signature takes `(text: str, *, data: dict | None = None) -> list[types.TextContent]`. After Task 4 it ALSO accepts a `ToolResult` directly — overloaded:
- `text_result(text: str, *, data: dict | None = None)` (existing, preserved for backwards compat)
- `text_result(result: ToolResult)` (new, used by Task 5/6 shims)

`ToolResult` is a new frozen dataclass in `brain_core.tools.base`:
```python
@dataclass(frozen=True, slots=True)
class ToolResult:
    text: str
    data: dict[str, Any] | None = None
```

### Step 1 — Failing test

`packages/brain_core/tests/tools/test_base.py`:

```python
"""Tests for brain_core.tools.base — ToolContext, ToolResult, scope_guard_path."""

from __future__ import annotations

from pathlib import Path

import pytest

from brain_core.tools.base import ToolContext, ToolResult, scope_guard_path
from brain_core.vault.paths import ScopeError


def test_tool_result_frozen_with_optional_data() -> None:
    result = ToolResult(text="hello")
    assert result.text == "hello"
    assert result.data is None

    result2 = ToolResult(text="hi", data={"k": "v"})
    assert result2.data == {"k": "v"}

    with pytest.raises(Exception):  # frozen dataclass rejects mutation
        result.text = "mutated"  # type: ignore[misc]


def test_tool_context_accepts_all_ten_fields(tmp_path: Path) -> None:
    """Smoke — the field set matches ToolContext across brain_mcp."""
    from dataclasses import fields

    names = {f.name for f in fields(ToolContext)}
    assert names == {
        "vault_root",
        "allowed_domains",
        "retrieval",
        "pending_store",
        "state_db",
        "writer",
        "llm",
        "cost_ledger",
        "rate_limiter",
        "undo_log",
    }


def test_scope_guard_path_rejects_absolute(tmp_path: Path) -> None:
    ctx_stub = ToolContext(
        vault_root=tmp_path,
        allowed_domains=("research",),
        retrieval=None,
        pending_store=None,
        state_db=None,
        writer=None,
        llm=None,
        cost_ledger=None,
        rate_limiter=None,
        undo_log=None,
    )
    with pytest.raises(ValueError, match="vault-relative"):
        scope_guard_path(str(tmp_path / "research" / "notes" / "x.md"), ctx_stub)


def test_scope_guard_path_rejects_out_of_scope(tmp_path: Path) -> None:
    ctx_stub = ToolContext(
        vault_root=tmp_path,
        allowed_domains=("research",),
        retrieval=None, pending_store=None, state_db=None, writer=None,
        llm=None, cost_ledger=None, rate_limiter=None, undo_log=None,
    )
    with pytest.raises(ScopeError):
        scope_guard_path("personal/notes/secret.md", ctx_stub)
```

**Also** — verify the brain_mcp shim re-exports still work:

`packages/brain_mcp/tests/test_tools_base.py` already exists from Plan 04. Add one assertion:

```python
def test_brain_mcp_tool_context_is_brain_core_tool_context() -> None:
    """The re-export preserves identity — no subclass or alias duplication."""
    from brain_core.tools.base import ToolContext as CoreCtx
    from brain_mcp.tools.base import ToolContext as McpCtx
    assert CoreCtx is McpCtx
```

### Step 2 — Implement `brain_core.tools.base`

```python
"""Shared tool primitives for brain_core.tools.<name> modules.

Task 4 lands `ToolContext`, `ToolResult`, `scope_guard_path`. These are
transport-agnostic — MCP-specific helpers live in `brain_mcp.tools.base`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from brain_core.vault.paths import scope_guard


@dataclass(frozen=True)
class ToolContext:
    """Per-request primitives every tool handler may need.

    Heavy types (retrieval, llm, writer) are typed as `Any` to avoid import
    cycles — concrete tools narrow at use site. Mirrors brain_mcp's shape
    1:1 so every Plan 04 tool handler moves without signature changes.
    """

    vault_root: Path
    allowed_domains: tuple[str, ...]
    retrieval: Any  # BM25VaultIndex
    pending_store: Any  # PendingPatchStore
    state_db: Any  # StateDB
    writer: Any  # VaultWriter
    llm: Any  # LLMProvider
    cost_ledger: Any  # CostLedger
    rate_limiter: Any  # RateLimiter
    undo_log: Any  # UndoLog


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Transport-agnostic return value for every tool handler.

    `text` is a human-readable summary shown to LLMs or rendered in the UI.
    `data` is the structured payload (None when the tool has nothing more to
    say than the text). MCP wraps this into TextContent via
    `brain_mcp.tools.base.text_result`. REST serializes it as
    `{"text": ..., "data": ...}` directly.
    """

    text: str
    data: dict[str, Any] | None = None


def scope_guard_path(rel_path: str, ctx: ToolContext) -> Path:
    """Convert a vault-relative string path to an absolute scope-guarded Path.

    Raises:
        ValueError: if ``rel_path`` is absolute.
        ScopeError: if the resolved path falls outside ctx.allowed_domains.
    """
    p = Path(rel_path)
    if p.is_absolute():
        raise ValueError(f"path must be vault-relative, not absolute: {rel_path!r}")
    return scope_guard(
        ctx.vault_root / p,
        vault_root=ctx.vault_root,
        allowed_domains=ctx.allowed_domains,
    )
```

Update `packages/brain_core/src/brain_core/tools/__init__.py` to re-export:

```python
"""brain_core.tools — shared tool-handler registry and base types."""

from __future__ import annotations

from types import ModuleType

from brain_core.tools.base import ToolContext, ToolResult, scope_guard_path

ToolModule = ModuleType

_TOOL_MODULES: list[ToolModule] = []


def register(module: ToolModule) -> None:
    """Append a tool module to the registry. Idempotent."""
    if module not in _TOOL_MODULES:
        _TOOL_MODULES.append(module)


def list_tools() -> list[ToolModule]:
    """Return the registered tool modules in registration order."""
    return list(_TOOL_MODULES)


__all__ = [
    "ToolContext",
    "ToolModule",
    "ToolResult",
    "list_tools",
    "register",
    "scope_guard_path",
]
```

### Step 3 — Rewrite `brain_mcp/tools/base.py` as a shim + `text_result` home

```python
"""MCP-transport helpers. ToolContext + scope_guard_path re-export from brain_core.tools.base.

`text_result` lives here because it's MCP-SDK-specific (returns
list[types.TextContent]). Task 5/6 shims call `text_result(ToolResult)` to
wrap the brain_core handler's output.
"""

from __future__ import annotations

import json
from typing import Any

import mcp.types as types

from brain_core.tools.base import ToolContext, ToolResult, scope_guard_path

ToolModule = types.ModuleType  # retained for type-narrowing across brain_mcp.server

__all__ = ["ToolContext", "ToolModule", "ToolResult", "scope_guard_path", "text_result"]


def text_result(
    text_or_result: str | ToolResult,
    *,
    data: dict[str, Any] | None = None,
) -> list[types.TextContent]:
    """Wrap a tool's output into the MCP SDK's TextContent list shape.

    Two call forms for backwards compat with Plan 04 handlers:
        text_result("summary text", data={"k": "v"})          # existing Plan 04 call
        text_result(ToolResult(text="summary", data={...}))   # new Task 5/6 shim call
    """
    if isinstance(text_or_result, ToolResult):
        text = text_or_result.text
        data = text_or_result.data
    else:
        text = text_or_result

    out: list[types.TextContent] = [types.TextContent(type="text", text=text)]
    if data is not None:
        out.append(types.TextContent(type="text", text=json.dumps(data, indent=2, default=str)))
    return out
```

### Step 4 — Run + commit

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb && uv sync --reinstall-package brain_core --reinstall-package brain_mcp
cd /Users/chrisjohnson/Code/cj-llm-kb && uv run pytest packages/brain_core packages/brain_mcp packages/brain_api -v
```

Expect:
- brain_core: **364 passed** (362 prior + 1 ToolResult + 1 ToolContext shape assertion; scope_guard_path tests replace nothing)
- brain_mcp: **102 passed** (101 prior + 1 identity assertion)
- brain_api: 9 passed (Task 1–3 baseline)
- **Total: 505 passed + 8 skipped** (vs pre-Plan-05 baseline 502)

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb/packages/brain_core && uv run mypy src tests
cd /Users/chrisjohnson/Code/cj-llm-kb/packages/brain_mcp && uv run mypy src tests
cd /Users/chrisjohnson/Code/cj-llm-kb/packages/brain_api && uv run mypy src tests
```

All clean. Self-review, then:

```bash
git commit -m "feat(core): plan 05 task 4 — brain_core.tools.base with ToolContext/ToolResult/scope_guard_path"
```

---

### Task 5 — Move 9 read + ingest tool modules to `brain_core.tools.*`

**Owning subagent:** brain-core-engineer

**Modules moved (9):** `list_domains`, `get_index`, `read_note`, `search`, `recent`, `get_brain_md`, `ingest`, `classify`, `bulk_import`.

**Files — per module (× 9):**
- Move: `packages/brain_mcp/src/brain_mcp/tools/<name>.py` → `packages/brain_core/src/brain_core/tools/<name>.py`
- Rewrite: `packages/brain_mcp/src/brain_mcp/tools/<name>.py` as the 7-line shim
- Create: `packages/brain_core/tests/tools/test_<name>.py` — one happy-path `ToolResult`-shape test per module

**Context for the implementer:**

Follow the shared pattern defined at the top of Group 2. For each module, apply these transformations in order:

1. **Read** the current `brain_mcp/tools/<name>.py`.
2. **Copy** it to `brain_core/tools/<name>.py`.
3. **Rewrite imports** in the copied file:
   - `import mcp.types as types` → **delete**
   - `from brain_mcp.tools.base import ToolContext, scope_guard_path, text_result` → `from brain_core.tools.base import ToolContext, ToolResult, scope_guard_path`
4. **Rewrite return type** of `handle`:
   - `async def handle(arguments, ctx) -> list[types.TextContent]:` → `async def handle(arguments, ctx: ToolContext) -> ToolResult:`
5. **Rewrite every `text_result(...)` call**:
   - `return text_result("summary", data={"k": "v"})` → `return ToolResult(text="summary", data={"k": "v"})`
   - `return text_result("summary")` → `return ToolResult(text="summary")`
6. **Append auto-register** at module bottom:
   ```python
   import brain_core.tools as _tools
   import sys
   _tools.register(sys.modules[__name__])
   ```
   (This IS the auto-register pattern picked at the top of Group 2. Alternative considered: explicit registration in `__init__.py`. Auto-register keeps each module self-contained; explicit registration would centralize the order. Group 2 picks auto-register; Checkpoint 2 surfaces the choice for a final sign-off.)
7. **Rewrite** `brain_mcp/tools/<name>.py` per the shim template from the Group 2 shared pattern.
8. **Add one smoke test** in `packages/brain_core/tests/tools/test_<name>.py` that exercises the handler against a `ToolContext` built from a tmp vault, asserts the returned `ToolResult` has the expected `text` and `data` keys.

### Detailed example — `list_domains`

**Original `brain_mcp/tools/list_domains.py`:**

```python
"""brain_list_domains — list every top-level domain directory in the vault."""

from typing import Any
import mcp.types as types
from brain_mcp.tools.base import ToolContext, text_result

NAME = "brain_list_domains"
DESCRIPTION = "List every domain (top-level directory with notes) in the vault."
INPUT_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> list[types.TextContent]:
    root = ctx.vault_root
    domains = sorted(
        d.name for d in root.iterdir()
        if d.is_dir() and not d.name.startswith(".") and list(d.rglob("*.md"))
    )
    text = "\n".join(f"- {d}" for d in domains) or "(no domains)"
    return text_result(text, data={"domains": domains})
```

**New `brain_core/tools/list_domains.py`:**

```python
"""brain_list_domains — list every top-level domain directory in the vault."""

from __future__ import annotations

import sys
from typing import Any

from brain_core.tools.base import ToolContext, ToolResult

NAME = "brain_list_domains"
DESCRIPTION = "List every domain (top-level directory with notes) in the vault."
INPUT_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}}


async def handle(arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
    root = ctx.vault_root
    domains = sorted(
        d.name for d in root.iterdir()
        if d.is_dir() and not d.name.startswith(".") and list(d.rglob("*.md"))
    )
    text = "\n".join(f"- {d}" for d in domains) or "(no domains)"
    return ToolResult(text=text, data={"domains": domains})


# Auto-register at import time.
import brain_core.tools as _tools  # noqa: E402
_tools.register(sys.modules[__name__])
```

**New `brain_mcp/tools/list_domains.py` (shim):**

```python
"""MCP transport shim for brain_list_domains. Real handler in brain_core.tools.list_domains."""

from __future__ import annotations

from typing import Any

import mcp.types as types

from brain_core.tools.list_domains import DESCRIPTION, INPUT_SCHEMA, NAME
from brain_core.tools.list_domains import handle as _core_handle

from brain_mcp.tools.base import ToolContext, text_result

__all__ = ["DESCRIPTION", "INPUT_SCHEMA", "NAME", "handle"]


async def handle(
    arguments: dict[str, Any], ctx: ToolContext
) -> list[types.TextContent]:
    """Delegate to brain_core; wrap ToolResult into MCP TextContent list."""
    result = await _core_handle(arguments, ctx)
    return text_result(result)
```

**New `brain_core/tests/tools/test_list_domains.py`:**

```python
"""Smoke test for brain_core.tools.list_domains — ToolResult shape."""

from __future__ import annotations

from pathlib import Path

import pytest

from brain_core.tools.base import ToolContext, ToolResult
from brain_core.tools.list_domains import NAME, handle


def _mk_ctx(vault: Path) -> ToolContext:
    return ToolContext(
        vault_root=vault,
        allowed_domains=("research",),
        retrieval=None, pending_store=None, state_db=None, writer=None,
        llm=None, cost_ledger=None, rate_limiter=None, undo_log=None,
    )


@pytest.mark.asyncio
async def test_lists_non_empty_domains(tmp_path: Path) -> None:
    (tmp_path / "research" / "notes").mkdir(parents=True)
    (tmp_path / "research" / "notes" / "x.md").write_text("x", encoding="utf-8", newline="\n")
    (tmp_path / "personal" / "notes").mkdir(parents=True)
    (tmp_path / "personal" / "notes" / "y.md").write_text("y", encoding="utf-8", newline="\n")

    result = await handle({}, _mk_ctx(tmp_path))

    assert isinstance(result, ToolResult)
    assert "research" in result.data["domains"]  # type: ignore[index]
    assert "personal" in result.data["domains"]  # type: ignore[index]


def test_name_constant() -> None:
    assert NAME == "brain_list_domains"
```

### Repeat for 8 more modules

Each of `get_index`, `read_note`, `search`, `recent`, `get_brain_md`, `ingest`, `classify`, `bulk_import` follows the same transformation. The subagent should:

1. Open the existing `brain_mcp/tools/<name>.py`
2. Apply transformations 1–6 from the pattern
3. Replace `brain_mcp/tools/<name>.py` with the shim
4. Write a smoke test in `brain_core/tests/tools/test_<name>.py`

**Pattern-specific notes:**
- **`ingest`** — the `_build_pipeline_for_mcp` helper moves too. Rename it `_build_pipeline_from_ctx` in `brain_core.tools.ingest`; it only touches `ctx` + `brain_core.ingest.pipeline.IngestPipeline`, no MCP deps.
- **`search`** — already imports `scope_guard` from `brain_core.vault.paths`. No additional changes beyond the standard pattern.
- **`bulk_import`** — the `_LARGE_FOLDER_THRESHOLD = 20` named constant stays module-local.
- **`classify`** — still passes `ctx.llm` + `"claude-haiku-4-5-20251001"`. Model string stays hardcoded (D10a defer).

### Run + commit

After all 9 moves:

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb && uv sync --reinstall-package brain_core --reinstall-package brain_mcp
cd /Users/chrisjohnson/Code/cj-llm-kb && uv run pytest packages/brain_core packages/brain_mcp packages/brain_api -v
```

Expect:
- brain_core: **373 passed** (364 prior + 9 smoke tests, one per moved module)
- brain_mcp: **102 passed** (unchanged — shims preserve existing behavior)
- brain_api: 9 passed (unchanged)
- **Total: 514 passed + 8 skipped**

Gates:

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb/packages/brain_core && uv run mypy src tests
cd /Users/chrisjohnson/Code/cj-llm-kb/packages/brain_mcp && uv run mypy src tests
cd /Users/chrisjohnson/Code/cj-llm-kb && uv run ruff check packages/brain_core packages/brain_mcp && uv run ruff format --check packages/brain_core packages/brain_mcp
```

Self-review, then:

```bash
git commit -m "refactor(core): plan 05 task 5 — move 9 read+ingest tool handlers to brain_core.tools"
```

---

### Task 6 — Move 9 patch + maintenance tool modules to `brain_core.tools.*`

**Owning subagent:** brain-core-engineer

**Modules moved (9):** `propose_note`, `list_pending_patches`, `apply_patch`, `reject_patch`, `undo_last`, `lint`, `cost_report`, `config_get`, `config_set`.

**Context for the implementer:**

Identical pattern to Task 5 — the 6-step transformation from the Group 2 shared pattern, applied module by module.

**Pattern-specific notes:**
- **`apply_patch`** — Plan 04 Task 25 cleaned up the `_absolutize_patchset` workaround (the core `VaultWriter.apply` now absolutizes). The tool module is now trivial; move as-is.
- **`propose_note`** — imports `ChatMode.BRAINSTORM` from `brain_core.chat.types`; already a `brain_core` dep, clean.
- **`undo_last`** — `_find_latest_undo_id(vault_root)` helper moves with it.
- **`lint`** — stub only, returns `{"status": "not_implemented", "message": "Plan 09 will land the real lint engine."}`. Easiest move.
- **`cost_report`** — depends on `CostLedger.summary()` (Plan 04 Task 19A landed it in brain_core); no cross-package concerns.
- **`config_get` / `config_set`** — both depend on the local `_snapshot_config(ctx)` helper and the `_SECRET_SUBSTRINGS` / `_SETTABLE_KEYS` constants. Move those to `brain_core.tools.config_get` and `brain_core.tools.config_set` respectively (no cross-module sharing — duplication is ≤10 lines and makes each module self-contained).

### Run + commit

After all 9 moves:

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb && uv sync --reinstall-package brain_core --reinstall-package brain_mcp
cd /Users/chrisjohnson/Code/cj-llm-kb && uv run pytest packages/brain_core packages/brain_mcp packages/brain_api -v
```

Expect:
- brain_core: **382 passed** (373 prior + 9 smoke tests)
- brain_mcp: **102 passed** (unchanged)
- brain_api: 9 passed
- **Total: 523 passed + 8 skipped**

One MORE test in `brain_api`: the `GET /api/tools` listing now returns 18 tools instead of empty. Update `test_empty_registry_returns_empty_list` → `test_lists_eighteen_tools_after_extraction`:

```python
def test_lists_eighteen_tools_after_extraction(client: TestClient) -> None:
    """After Group 2, the registry has all 18 tools auto-registered."""
    response = client.get("/api/tools")
    body = response.json()
    names = {t["name"] for t in body["tools"]}
    assert len(body["tools"]) == 18
    # Spot-check a few names.
    assert "brain_list_domains" in names
    assert "brain_apply_patch" in names
    assert "brain_cost_report" in names
```

Commit:

```bash
git commit -m "refactor(core): plan 05 task 6 — move 9 patch+maintenance tool handlers to brain_core.tools (18 total)"
```

---

**Checkpoint 2 — pause for main-loop review.**

6 tasks landed. Handler extraction is complete — all 18 tool handlers live in `brain_core.tools.*`, `brain_mcp.tools.*` are 7-line shims, `brain_mcp.server._TOOL_MODULES` still works via the shims (no server.py changes needed). Main loop reviews:

- **Hard gate:** every one of the 101 brain_mcp tests still passes. If any regressed, investigate before continuing.
- Auto-register-at-import pattern OK, or switch to explicit registration in `brain_core/tools/__init__.py` (centralizes ordering at cost of boilerplate)?
- `ToolResult.data: dict | None` — is `None` the right "no data" signal, or should the default be `{}` for simpler consumer code?
- The `brain_api → brain_mcp` dep from Task 1 (`pyproject.toml`) — can it drop now that tool handlers live in `brain_core`? Answer: ALMOST. `AppContext.build_app_context` still imports `brain_mcp.rate_limit.RateLimiter`. Task 14 (`RateLimitError` promotion) is the right time to move `RateLimiter` to `brain_core` and drop this dep. Track for Task 14.
- Any cross-package import cycles surfaced by the mypy runs?

Before Task 7, main-loop dispatches the auth/middleware work with the registry shape locked.

---

### Group 3 — Auth + middleware (Tasks 7–9)

**Checkpoint after Task 9:** main-loop reviews the whole security surface — token rotation semantics, Origin/Host rejection paths, WebSocket handshake checks — before the REST tool dispatcher (Group 4) goes live. A bug in auth is easier to catch at the single-endpoint (`/healthz`) + synthetic-endpoint level than after 18 real endpoints land.

The localhost attack surface per D6a: a malicious page at `evil.example` visited in any browser can issue `fetch("http://localhost:4317/api/tools/brain_propose_note", {...})` and hit vault writes. Browsers enforce same-origin on read-responses but not on sending — CSRF is real for a local server. Defenses in layered order:

1. **Host header validation** — rejects DNS-rebinding attacks (`evil.example` → `127.0.0.1` in the browser's local DNS cache)
2. **Origin header validation** — rejects cross-origin POSTs from any non-localhost page
3. **Filesystem token** — final defense. A random secret at `<vault>/.brain/run/api-secret.txt` (mode 0600). The Next.js frontend (Plan 07) reads it server-side; the browser never sees it. CLI reads it directly.

---

### Task 7 — Token generation + filesystem write

**Owning subagent:** brain-api-engineer

**Files:**
- Create: `packages/brain_api/src/brain_api/auth.py` (token primitives only — middleware in Task 8, dependency in Task 9)
- Modify: `packages/brain_api/src/brain_api/context.py` — store token on `AppContext`
- Modify: `packages/brain_api/src/brain_api/app.py` — generate token in lifespan, write to filesystem, stash on ctx
- Create: `packages/brain_api/tests/test_auth_token.py`

**Context for the implementer:**

`auth.py` is the home for every auth primitive across Tasks 7, 8, 9. Task 7 lands:
- `generate_token() -> str` — 32 bytes from `secrets.token_hex(32)` → 64 hex chars → 256 bits of entropy
- `write_token_file(vault_root: Path, token: str) -> Path` — writes to `<vault>/.brain/run/api-secret.txt`, mode 0600 on POSIX (via `os.open` + `O_CREAT | O_WRONLY | O_TRUNC` + octal mode arg), best-effort `os.chmod(0o600)` on Windows with a clear `# TODO(Windows ACL)` comment per D11a
- `read_token_file(vault_root: Path) -> str | None` — for CLI clients (Plan 08's `brain start` will consume this). Returns `None` if the file doesn't exist

Tokens rotate on every `create_app()` call (lifespan startup). A CLI that gets a 401 / 403 rejection should re-read the file to pick up the new token. The old token becomes invalid the instant a new app boots; for a single-user local tool this is fine.

**Cross-platform note (D11a):** on POSIX, the `os.open(path, flags, mode)` with mode 0o600 is atomic-ish — the file is created with the right bits before any write. On Windows, `os.open` accepts the mode but ignores non-read-only bits; the real control is NTFS ACLs via `pywin32`. We ship a `# TODO(Windows ACL)` comment and document in `docs/testing/cross-platform.md` (Task 23) that the practical Windows defense is "don't share your `%APPDATA%` tree". The token-file defense against cross-origin browser attacks is unchanged on both OSes.

### Step 1 — Failing test

`packages/brain_api/tests/test_auth_token.py`:

```python
"""Tests for brain_api.auth — token generation + filesystem IO."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from brain_api.auth import generate_token, read_token_file, write_token_file


def test_generate_token_is_64_hex_chars() -> None:
    tok = generate_token()
    assert isinstance(tok, str)
    assert len(tok) == 64
    assert all(c in "0123456789abcdef" for c in tok)


def test_generate_token_is_unique() -> None:
    # Collision probability is ~2^-256 — one million samples are safely distinct.
    tokens = {generate_token() for _ in range(1000)}
    assert len(tokens) == 1000


def test_write_token_file_creates_parent_and_writes(tmp_path: Path) -> None:
    token = generate_token()
    path = write_token_file(tmp_path, token)

    assert path == tmp_path / ".brain" / "run" / "api-secret.txt"
    assert path.exists()
    assert path.read_text(encoding="utf-8").strip() == token


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX permission bits")
def test_write_token_file_is_mode_0600_on_posix(tmp_path: Path) -> None:
    token = generate_token()
    path = write_token_file(tmp_path, token)
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"


def test_write_token_file_overwrites_prior(tmp_path: Path) -> None:
    path = write_token_file(tmp_path, "aaaa")
    path2 = write_token_file(tmp_path, "bbbb")
    assert path == path2
    assert path.read_text(encoding="utf-8").strip() == "bbbb"


def test_read_token_file_returns_none_when_missing(tmp_path: Path) -> None:
    assert read_token_file(tmp_path) is None


def test_read_token_file_returns_written_token(tmp_path: Path) -> None:
    token = generate_token()
    write_token_file(tmp_path, token)
    assert read_token_file(tmp_path) == token


def test_lifespan_generates_and_stashes_token(app, seeded_vault: Path) -> None:  # noqa: ANN001
    from fastapi.testclient import TestClient

    with TestClient(app):
        ctx = app.state.ctx
        assert ctx.token is not None
        assert len(ctx.token) == 64
        # File on disk matches.
        on_disk = read_token_file(seeded_vault)
        assert on_disk == ctx.token


def test_each_create_app_rotates_token(seeded_vault: Path) -> None:
    """Rotation on startup — a second create_app invocation writes a new token."""
    from fastapi.testclient import TestClient

    from brain_api import create_app

    app_a = create_app(vault_root=seeded_vault, allowed_domains=("research",))
    with TestClient(app_a):
        tok_a = app_a.state.ctx.token

    app_b = create_app(vault_root=seeded_vault, allowed_domains=("research",))
    with TestClient(app_b):
        tok_b = app_b.state.ctx.token

    assert tok_a != tok_b
```

### Step 2 — Implement `auth.py`

```python
"""brain_api auth primitives — token generation, filesystem IO.

Task 7 lands the token-file primitives. Task 8 adds Origin/Host middleware;
Task 9 adds the FastAPI dependency that enforces X-Brain-Token on write routes.
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

_TOKEN_FILENAME = "api-secret.txt"


def generate_token() -> str:
    """Return a fresh 32-byte (256-bit) hex token. Rotation-safe."""
    return secrets.token_hex(32)


def _token_path(vault_root: Path) -> Path:
    return vault_root / ".brain" / "run" / _TOKEN_FILENAME


def write_token_file(vault_root: Path, token: str) -> Path:
    """Write `token` to `<vault>/.brain/run/api-secret.txt` with mode 0600.

    POSIX: atomic-ish via `os.open(..., O_CREAT | O_WRONLY | O_TRUNC, 0o600)`.
    Windows: fall back to `pathlib.Path.write_text` + `os.chmod(..., 0o600)`.
    Windows `chmod(0o600)` is best-effort — the real defense is NTFS ACLs via
    `pywin32`, which Plan 05 deliberately does NOT introduce as a new dep.
    See docs/testing/cross-platform.md for the threat-model discussion.
    """
    path = _token_path(vault_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform.startswith("win"):
        # Windows: plain write + best-effort chmod.
        path.write_text(token + "\n", encoding="utf-8", newline="\n")
        try:
            os.chmod(path, 0o600)  # TODO(Windows ACL): pywin32 SetFileSecurityA for real lockdown
        except OSError:
            pass
    else:
        # POSIX: atomic create-with-mode via O_CREAT | O_EXCL-ish pattern.
        flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC
        fd = os.open(str(path), flags, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(token + "\n")
        except BaseException:
            # Leave the fd closed (fdopen took ownership) — no manual close needed.
            raise
        # If the file already existed (O_TRUNC wiped it), mode from pre-existing
        # file is preserved. Force 0o600.
        os.chmod(path, 0o600)

    return path


def read_token_file(vault_root: Path) -> str | None:
    """Return the token from `<vault>/.brain/run/api-secret.txt`, or None if missing."""
    path = _token_path(vault_root)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()
```

### Step 3 — Wire into lifespan

Modify `packages/brain_api/src/brain_api/app.py` — the lifespan now generates + writes the token, stashes on ctx:

```python
@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build AppContext + write the app's secret token at startup."""
    from brain_api.auth import generate_token, write_token_file

    token = app.state.token_override or generate_token()
    write_token_file(app.state.vault_root, token)

    ctx = build_app_context(
        vault_root=app.state.vault_root,
        allowed_domains=app.state.allowed_domains,
        token=token,
    )
    app.state.ctx = ctx
    try:
        yield
    finally:
        pass
```

### Step 4 — Run + commit

```bash
cd /Users/chrisjohnson/Code/cj-llm-kb && uv run pytest packages/brain_api -v
```

Expect: **17 passed** (9 prior + 8 new auth-token tests — the Windows perm test is skipped on Windows so the count is 7 on Windows).

Gates clean, then:

```bash
git commit -m "feat(api): plan 05 task 7 — token generation + filesystem write (.brain/run/api-secret.txt, 0600)"
```

---

### Task 8 — Origin + Host middleware

**Owning subagent:** brain-api-engineer

**Files:**
- Modify: `packages/brain_api/src/brain_api/auth.py` — add `OriginHostMiddleware`
- Modify: `packages/brain_api/src/brain_api/app.py` — install middleware
- Create: `packages/brain_api/tests/test_auth_middleware.py`

**Context for the implementer:**

Starlette middleware runs for BOTH HTTP and WebSocket connections at the ASGI layer — same middleware catches both. Good. The middleware enforces two properties per D6a:

1. **Host header**: must be one of `{"localhost", "localhost:<port>", "127.0.0.1", "127.0.0.1:<port>"}`. Rejects DNS rebinding. Note: the port is not knowable at middleware-install time (uvicorn picks it), so the middleware accepts ANY port suffix as long as the hostname part is loopback.

2. **Origin header**: for state-changing methods (POST, PUT, DELETE, PATCH) and WebSocket upgrades, must be absent/null OR exactly `http://<loopback>:<any-port>`. Rejects cross-origin browser POSTs. GET/HEAD/OPTIONS bypass the Origin check (they're safe methods — browsers send them with any Origin, but they don't mutate state).

**Rejection**: return a `403 Forbidden` with body `{"error": "refused", "message": "..."}`. For WebSocket connections, close with code 1008 (Policy Violation) + reason string — same format as the REST error body.

**Why not CORS?** CORS headers tell browsers to ALLOW cross-origin reads of response bodies. We don't want to allow that — we want to reject the request entirely. CORS is the opposite of what we need.

### Step 1 — Failing tests

`packages/brain_api/tests/test_auth_middleware.py`:

```python
"""Tests for OriginHostMiddleware — DNS rebinding + cross-origin defense."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestHostValidation:
    def test_accepts_localhost(self, client: TestClient) -> None:
        response = client.get("/healthz", headers={"Host": "localhost:4317"})
        assert response.status_code == 200

    def test_accepts_127_0_0_1(self, client: TestClient) -> None:
        response = client.get("/healthz", headers={"Host": "127.0.0.1:4317"})
        assert response.status_code == 200

    def test_accepts_bare_localhost_no_port(self, client: TestClient) -> None:
        response = client.get("/healthz", headers={"Host": "localhost"})
        assert response.status_code == 200

    def test_rejects_evil_host(self, client: TestClient) -> None:
        response = client.get("/healthz", headers={"Host": "evil.example"})
        assert response.status_code == 403
        body = response.json()
        assert body["error"] == "refused"

    def test_rejects_public_ip_host(self, client: TestClient) -> None:
        response = client.get("/healthz", headers={"Host": "203.0.113.10:4317"})
        assert response.status_code == 403


class TestOriginValidation:
    def test_get_with_no_origin_allowed(self, client: TestClient) -> None:
        response = client.get("/healthz")
        assert response.status_code == 200

    def test_get_with_evil_origin_allowed(self, client: TestClient) -> None:
        """GET is a safe method — Origin doesn't matter for read-only endpoints."""
        response = client.get("/healthz", headers={"Origin": "https://evil.example"})
        assert response.status_code == 200

    def test_post_with_evil_origin_rejected(self, client: TestClient) -> None:
        """Synthetic POST route for this test — Task 10 adds the real ones."""
        # Use the OpenAPI /openapi.json endpoint which accepts GET only; we synthesize
        # a write attempt via a path that doesn't exist (it'd be 404 without the middleware,
        # but the middleware short-circuits at 403 first).
        response = client.post(
            "/api/tools/_synthetic_write",
            json={},
            headers={"Origin": "https://evil.example"},
        )
        assert response.status_code == 403
        body = response.json()
        assert body["error"] == "refused"
        assert "origin" in body["message"].lower()

    def test_post_with_localhost_origin_allowed_through_middleware(
        self, client: TestClient
    ) -> None:
        """Localhost Origin passes the middleware; the 404 that follows is
        from the non-existent route, not from the middleware."""
        response = client.post(
            "/api/tools/_synthetic_write",
            json={},
            headers={"Origin": "http://localhost:4317"},
        )
        # Middleware accepts; Task 10-era routing returns 404 for the unknown tool.
        # In Task 8 pre-Task-10, the Task 3 POST handler doesn't exist → 405 or 404.
        assert response.status_code != 403 or response.json().get("error") != "refused"

    def test_post_with_null_origin_allowed(self, client: TestClient) -> None:
        """Native clients (curl, CLI) send no Origin header — allowed."""
        response = client.post("/api/tools/_synthetic_write", json={})
        # Middleware accepts; route lookup fails → ≠403 from middleware.
        assert response.status_code != 403 or response.json().get("error") != "refused"
```

### Step 2 — Implement middleware

Append to `auth.py`:

```python
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1"}


class OriginHostMiddleware(BaseHTTPMiddleware):
    """Reject non-loopback Host and cross-origin state-changing requests.

    Applies to both HTTP and WebSocket via ASGI middleware layering.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable],
    ):
        # Host header check — always.
        host = request.headers.get("host", "")
        hostname = host.split(":", 1)[0] if host else ""
        if hostname not in _LOOPBACK_HOSTS:
            return JSONResponse(
                {
                    "error": "refused",
                    "message": f"host {host!r} is not a loopback address",
                },
                status_code=403,
            )

        # Origin check — only for state-changing methods + WebSocket upgrades.
        # WebSocket handshakes have method "GET" at the HTTP layer but an
        # "upgrade: websocket" header; check for that explicitly.
        is_ws_upgrade = "websocket" in request.headers.get("upgrade", "").lower()
        is_state_changing = request.method not in _SAFE_METHODS

        if is_state_changing or is_ws_upgrade:
            origin = request.headers.get("origin")
            if origin is not None and not _is_loopback_origin(origin):
                return JSONResponse(
                    {
                        "error": "refused",
                        "message": f"origin {origin!r} is not a loopback address",
                    },
                    status_code=403,
                )

        return await call_next(request)


def _is_loopback_origin(origin: str) -> bool:
    """Return True if Origin is `http(s)://localhost` or `http(s)://127.0.0.1`, any port."""
    from urllib.parse import urlparse

    parsed = urlparse(origin)
    return parsed.hostname in _LOOPBACK_HOSTS
```

### Step 3 — Install middleware in `app.py`

Add after app creation, before routers:

```python
from brain_api.auth import OriginHostMiddleware

app.add_middleware(OriginHostMiddleware)
```

**Order matters.** FastAPI/Starlette applies middleware in reverse of add order. Install `OriginHostMiddleware` FIRST so it wraps all other middleware (Task 14 exception handlers, future request logging).

### Step 4 — Run + commit

Expect: **28 passed** (17 prior + 11 middleware tests).

```bash
git commit -m "feat(api): plan 05 task 8 — OriginHostMiddleware (DNS rebinding + CSRF defense)"
```

---

### Task 9 — Token dependency + WebSocket auth

**Owning subagent:** brain-api-engineer

**Files:**
- Modify: `packages/brain_api/src/brain_api/auth.py` — add `require_token` FastAPI dependency + `check_ws_token` helper
- Create: `packages/brain_api/tests/test_auth_dependency.py`
- Create: `packages/brain_api/tests/test_auth_ws.py` (smoke; real WS routes land in Group 6)

**Context for the implementer:**

Two auth primitives land here:

1. **`require_token(request: Request, ctx: AppContext = Depends(get_ctx)) -> None`** — a FastAPI dependency. Extracts `X-Brain-Token` from request headers; constant-time comparison (`secrets.compare_digest`) with `ctx.token`. On mismatch or missing header: raise `HTTPException(403, detail={"error": "refused", "message": "missing or invalid X-Brain-Token"})`.

2. **`check_ws_token(websocket: WebSocket, ctx: AppContext) -> None`** — for WebSocket endpoints. Reads the `token` query parameter from the WS handshake URL, constant-time-compares against `ctx.token`. On mismatch: `await websocket.close(code=1008, reason="invalid token")` + return. On success: returns (caller proceeds to `accept()`).

**Which routes require token:**
- `GET /healthz` — **no token** (liveness probe must be unauthenticated)
- `GET /api/tools` — **no token** (read-only metadata, safe)
- `POST /api/tools/<name>` — **token required** (Task 10 attaches the dep)
- `WS /ws/chat/<thread_id>` — **token required** via query param (Task 17)

**Why query param for WS?** Browsers can't attach custom headers on WebSocket handshakes reliably (only `Authorization` via the WebSocket constructor in some drafts). The `?token=...` pattern is standard for localhost WS auth (VSCode / Jupyter both do this). The token is never logged (request logging at Task 9 strips query params on WS URLs).

**Constant-time comparison:** `secrets.compare_digest` resists timing attacks. Overkill for localhost but free.

### Step 1 — Failing tests

`packages/brain_api/tests/test_auth_dependency.py`:

```python
"""Tests for require_token dependency — run against a synthetic endpoint."""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from brain_api.auth import require_token
from brain_api.context import AppContext


def _attach_synthetic_write_route(app: FastAPI) -> None:
    """Add a test-only route that requires token — exercises the dep."""

    @app.post("/_synthetic_write", dependencies=[Depends(require_token)])
    async def synthetic() -> dict:
        return {"ok": True}


def test_missing_token_rejected(app, client: TestClient) -> None:  # noqa: ANN001
    _attach_synthetic_write_route(app)
    # Need to reopen the client to pick up the new route.
    with TestClient(app) as fresh:
        response = fresh.post(
            "/_synthetic_write",
            json={},
            headers={"Origin": "http://localhost:4317"},
        )
    assert response.status_code == 403
    body = response.json()
    assert body["detail"]["error"] == "refused"
    assert "X-Brain-Token" in body["detail"]["message"]


def test_wrong_token_rejected(app, client: TestClient) -> None:  # noqa: ANN001
    _attach_synthetic_write_route(app)
    with TestClient(app) as fresh:
        response = fresh.post(
            "/_synthetic_write",
            json={},
            headers={
                "Origin": "http://localhost:4317",
                "X-Brain-Token": "0" * 64,
            },
        )
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "refused"


def test_correct_token_accepted(app, client: TestClient) -> None:  # noqa: ANN001
    _attach_synthetic_write_route(app)
    with TestClient(app) as fresh:
        token = app.state.ctx.token
        response = fresh.post(
            "/_synthetic_write",
            json={},
            headers={
                "Origin": "http://localhost:4317",
                "X-Brain-Token": token,
            },
        )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
```

`packages/brain_api/tests/test_auth_ws.py`:

```python
"""WS auth smoke tests — full WS endpoints land in Group 6, but the
check_ws_token helper is testable standalone."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from brain_api.auth import check_ws_token
from brain_api.context import AppContext


@pytest.mark.asyncio
async def test_check_ws_token_accepts_correct_token() -> None:
    ctx = MagicMock(spec=AppContext)
    ctx.token = "a" * 64

    ws = MagicMock()
    ws.query_params = {"token": "a" * 64}
    ws.close = AsyncMock()

    result = await check_ws_token(ws, ctx)
    assert result is True
    ws.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_ws_token_closes_on_missing_token() -> None:
    ctx = MagicMock(spec=AppContext)
    ctx.token = "a" * 64

    ws = MagicMock()
    ws.query_params = {}  # no token
    ws.close = AsyncMock()

    result = await check_ws_token(ws, ctx)
    assert result is False
    ws.close.assert_awaited_once()
    kwargs = ws.close.call_args.kwargs
    assert kwargs["code"] == 1008


@pytest.mark.asyncio
async def test_check_ws_token_closes_on_wrong_token() -> None:
    ctx = MagicMock(spec=AppContext)
    ctx.token = "a" * 64

    ws = MagicMock()
    ws.query_params = {"token": "b" * 64}
    ws.close = AsyncMock()

    result = await check_ws_token(ws, ctx)
    assert result is False
    ws.close.assert_awaited_once()
```

### Step 2 — Implement `require_token` + `check_ws_token`

Append to `auth.py`:

```python
import secrets as _secrets_module  # avoid shadowing the stdlib secrets used earlier

from fastapi import HTTPException, Request, WebSocket

from brain_api.context import AppContext, get_ctx


def require_token(
    request: Request,
    ctx: AppContext = None,  # noqa: B008 — filled via Depends by FastAPI at call time
) -> None:
    """FastAPI dependency — require a matching X-Brain-Token header.

    Raises HTTPException(403) on missing or mismatched token. Uses
    secrets.compare_digest for constant-time comparison.
    """
    # Late-resolve ctx via Depends to avoid circular imports at module-parse time.
    from fastapi import Depends  # noqa: PLC0415

    if ctx is None:
        # This path only fires if called without Depends — defensive.
        raise HTTPException(
            status_code=500,
            detail={"error": "internal", "message": "require_token used without Depends(get_ctx)"},
        )

    received = request.headers.get("x-brain-token", "")
    expected = ctx.token or ""

    if not received or not expected or not _secrets_module.compare_digest(received, expected):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "refused",
                "message": "missing or invalid X-Brain-Token header",
            },
        )
```

**Wiring note:** FastAPI resolves `Depends` chains lazily. To inject `ctx: AppContext = Depends(get_ctx)` as the second dep without Python's default-value gotcha, use the Depends-at-call-site pattern:

```python
from fastapi import Depends

def require_token(request: Request, ctx: AppContext = Depends(get_ctx)) -> None:
    # ...same body as above...
```

Task 10's endpoint wires it as `dependencies=[Depends(require_token)]`.

And for WebSocket:

```python
async def check_ws_token(websocket: WebSocket, ctx: AppContext) -> bool:
    """Validate ?token=<hex> on a WS handshake. Returns True on accept, False on close.

    Caller must `return` after a False result — the WS is already closed.
    """
    received = websocket.query_params.get("token", "")
    expected = ctx.token or ""

    if not received or not expected or not _secrets_module.compare_digest(received, expected):
        await websocket.close(code=1008, reason="invalid token")
        return False

    return True
```

### Step 3 — Run + commit

Expect: **34 passed** (28 prior + 3 token dep + 3 ws check = 6 new).

```bash
git commit -m "feat(api): plan 05 task 9 — require_token dep + check_ws_token (X-Brain-Token / ?token=)"
```

---

**Checkpoint 3 — pause for main-loop review.**

9 tasks landed. Auth surface live:
- Token rotation on every `create_app()` → filesystem at `.brain/run/api-secret.txt` (mode 0600)
- `OriginHostMiddleware` rejects non-loopback Host + cross-origin state-changing requests
- `require_token` dep guards write endpoints (Task 10 wires it); `check_ws_token` guards WS handshakes (Task 17 wires it)

Main loop reviews:

- **Security review pass:** is the 403 body shape final? Task 15's global exception handlers will convert `HTTPException` into the project-wide envelope `{error, message}`; Task 9's `detail={"error": ..., "message": ...}` might produce `{"detail": {"error": ..., "message": ...}}` in the JSON response. That's inconsistent with Task 15's envelope. **Track for Task 15** to unify via a custom `HTTPException` subclass that renders directly (no `detail` wrapper).
- **Windows perms reality check:** the `os.chmod(0o600)` on Windows is cosmetic. Is that documented loudly enough, or should the `write_token_file` emit a `warnings.warn` on Windows? Consider whether a warning is signal-useful or just noise for a single-user tool.
- **Token rotation friction:** every `create_app()` rotates. The `brain` CLI reads the file per-request and tolerates rotation; the Next.js frontend (Plan 07) must also re-read on 403. Is that contract clear in the handoff notes?
- Are the two loopback-host sets (`{"localhost", "127.0.0.1"}`) correct for both IPv4 and IPv6? Today, Plan 08 will pick `127.0.0.1` for uvicorn `--host`, so `[::1]` isn't relevant. Track IPv6 loopback (`::1`) as a future-proofing item if Plan 08 ever enables it.

Before Task 10, main loop confirms the middleware + dep pattern is locked before the generic tool dispatcher wires the dep across all 18 endpoints.

---
