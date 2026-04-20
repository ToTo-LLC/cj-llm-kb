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

*Intentionally unfilled. After the outline, decisions, and file structure are approved, I will fill in per-task bite-sized steps (test-first, exact code, exact commands, expected output) group-by-group following Plans 03/04's rhythm.*
