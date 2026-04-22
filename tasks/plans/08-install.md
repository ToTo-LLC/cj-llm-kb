# Plan 08 — Install + Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **DRAFT — pending section-by-section review. Task-level steps are intentionally unfilled below the outline until architecture / scope / decisions are approved.**

**Goal:** Ship a one-command install experience for Mac + Windows. After this plan, a user on a clean machine runs a single shell command, gets `brain` on PATH, double-clicks a launcher (or types `brain start`), sees the setup wizard in their browser, and completes first-ingest end-to-end. Uninstall is typed-confirmed and leaves the vault untouched by default.

**Architecture:**
Plan 08 makes one significant architectural pivot (Group 0) to simplify distribution: flip `brain_web` from Next.js's Node runtime (`next start`) to a static-exported SPA (`output: "export"`) served by `brain_api`. After Plan 08, the user's box runs **one** runtime — Python — and `brain start` supervises a single uvicorn process that serves both the REST/WS backend and the static UI. Node.js becomes a build-time-only dependency (install/upgrade need it; steady-state does not).

The distribution pipeline:

```
GitHub Release (per version)
  └── brain-vX.Y.Z.tar.gz
      ├── packages/       (Python source)
      ├── apps/brain_web/out/   (pre-built static UI — shipped, no Node needed)
      ├── scripts/install.sh
      ├── scripts/install.ps1
      ├── pyproject.toml + uv.lock
      └── README + LICENSE

install.sh / install.ps1
  1. Check OS / arch
  2. Install uv if missing (via GitHub releases — no sudo)
  3. Download & extract tarball to:
       Mac:     ~/Applications/brain/
       Windows: %LOCALAPPDATA%\brain\
  4. uv sync --all-packages (no dev deps — production only)
  5. Write shim wrapper:
       Mac:     ~/.local/bin/brain (+ optional .app wrapper)
       Windows: %LOCALAPPDATA%\Microsoft\WindowsApps\brain.cmd (+ Start Menu + desktop .cmd)
  6. PATH edit (if needed)
  7. Run `brain doctor` → plain-English status report
  8. Print: "brain installed. Run 'brain start' to begin."
```

At runtime:

```
brain start
  → uvicorn brain_api:app --port 4317 (fallback 4318..4330)
  → brain_api serves REST at /api/*, WS at /ws/*, static UI at /
  → writes PID to .brain/run/brain.pid
  → waits for /healthz
  → opens default browser at http://localhost:<port>/
```

**Tech choices (new runtime deps):**
- `psutil` — cross-platform process/PID management in brain_cli
- `requests` or stdlib `urllib` — upgrade check + tarball download (stdlib preferred to keep deps lean)
- No new Python deps beyond psutil. No new Node deps (Node itself becomes build-time only).

**Decisions pinned (D1–D3):**
- **D1a** — Distribution via per-version GitHub release tarballs.
- **D2b** — Static-export the web app; brain_api serves it. No Node runtime on user's box.
- **D3b** — `brain` CLI is a shim wrapper script (`brain.sh` / `brain.cmd`) that activates the app's venv and invokes the CLI module. No symlinks into system paths.

**Demo gate:** `uv run python scripts/demo-plan-08.py` runs end-to-end against a temp install dir + temp vault + FakeLLM:
1. Simulate a "fresh install" by extracting a built tarball into a temp dir (not the dev repo).
2. Run the install shim's first-boot sequence (sans tarball download — feed it a local tarball).
3. Verify `brain start` boots, `/healthz` returns OK, UI loads at localhost.
4. Open Playwright, drive setup wizard + one ingest.
5. Run `brain stop`. Verify no orphan processes.
6. Run `brain uninstall` with typed-confirm `UNINSTALL`. Verify install dir removed. Verify vault preserved.
7. Print `PLAN 08 DEMO OK`, exit 0.

Runs on Mac (local) + Windows (via GitHub Actions runner) as separate demo receipts.

**Owning subagents:**
- `brain-installer-engineer` — Groups 1, 2 primary; brain start/stop/status/upgrade/uninstall/doctor CLI; install.sh + install.ps1; launcher assets (Tasks 3–9).
- `brain-core-engineer` — Group 0 Task 1 (brain_api static serving + /api/setup-status + /api/upload).
- `brain-frontend-engineer` — Group 0 Task 2 (Next.js static export + server-component client-port).
- `brain-test-engineer` — Group 3 clean-VM dry runs, demo, close (Tasks 10–12).

**Pre-flight** (main loop, before Task 1):
- Confirm `plan-07-frontend` tag at `origin/main` (done).
- GitHub releases permissions confirmed on repo (for Task 7/8 tarball URL; placeholder URL is fine until first release is cut).
- Decide on P1–P4 below.

---

## Scope — in and out

**In scope for Plan 08:**
- Static-export pivot (Next.js `output: "export"` + brain_api static serving).
- `brain start / stop / status / doctor / upgrade / uninstall / backup` CLI verbs.
- `scripts/install.sh` (Mac; Linux-compatible best-effort) + `scripts/install.ps1` (Windows 11).
- Shim wrapper on PATH (`brain` resolves to a wrapper that activates the app's venv).
- Mac `.app` launcher wrapper (minimal — a directory wrapper around the shim, not a real code-signed app bundle).
- Windows Start Menu + desktop `.cmd` shortcuts.
- Upgrade path via tarball swap with rollback.
- Uninstall preserves vault by default (typed-confirm to delete).
- Clean-VM dry run on Mac + Windows 11.
- Demo script `scripts/demo-plan-08.py` with static-export + install + start/stop/uninstall round-trip.

**Out of scope (deferred to Plan 09 or later):**
- Code signing (Mac notarization, Windows signing).
- Native bundles (Electron / Tauri / py2app) — explicit roadmap item per spec.
- Auto-updates without user intervention (manual `brain upgrade` is it for day one).
- System service install (launchd / Windows Service) — `brain start` is user-invoked.
- Linux-first install (best-effort only via install.sh; not gate-tested).
- Migration adapters (Obsidian vault, Notion export) — separate plan.
- App-store distribution — roadmap item.
- Windows MSI packaging — use .cmd + shim for day one.
- Icon / launcher imagery polish — use placeholder `brain.png` from v3 design.

---

## Decisions — P1–P4 (pinned)

- **P1a** — install.sh/ps1 curl/iwr the official uv installer at install time (`astral.sh/uv/install.sh`). If astral.sh unreachability becomes a real complaint post-launch, revisit with P1b (bundled uv binary).
- **P2a + keep Node post-build** — install via fnm into `~/Applications/brain/tools/fnm/` (Mac) / `%LOCALAPPDATA%\brain\tools\fnm\` (Windows). Node 20 pinned. Kept under app tree after build so `brain upgrade` is fast; never on global PATH.
- **P3a** — all pages are Client Components. brain_api exposes `GET /api/setup-status` (Origin-gated, no token) + `GET /api/token` (Origin-gated, no token — same-origin loopback-only; threat model unchanged from Plan 07's WS URL token).
- **P4a** — probe ports 4317..4330, write chosen port to `.brain/run/brain.port`, auto-open browser at that URL on `brain start`. Shim prints `brain running at http://localhost:<port>/`.

---

## Group 0 — Static-export pivot (Tasks 1–2)

**Pattern:** two-task architectural shift that must land cleanly before supervisor + install work starts. Both tasks are substantial individually; keep them pure to this pivot so future tasks are drop-in shells.

**Hard property preserved:** `plan-07-frontend` demo-gate functionality continues to work after Group 0. Chat, ingest, pending, bulk, browse, settings, setup wizard — all identical behavior; the runtime plumbing underneath is different.

---

### Task 1 — brain_api static file serving + /api/setup-status + /api/token + /api/upload

**Owning subagent:** brain-core-engineer

**Goal:** brain_api gains four new capabilities to make it self-sufficient as both API host and UI host:
1. Serve `apps/brain_web/out/` (Next.js export output) under `/` with SPA-style fallback for client-side routes.
2. `GET /api/setup-status` → `{has_token, is_first_run, vault_exists, vault_path}` — Origin-gated, no token required.
3. `GET /api/token` → `{token}` — Origin-gated, no token required (same-origin loopback-only; returns the raw token for the browser to attach to subsequent X-Brain-Token headers).
4. `POST /api/upload` — X-Brain-Token required; multipart form with `file` field; forwards to `brain_ingest` internally; returns `{patch_id}`.

**Files:**
- Create: `packages/brain_api/src/brain_api/static_ui.py` — StaticFiles mount + SPA fallback handler
- Create: `packages/brain_api/src/brain_api/endpoints/setup_status.py` — GET /api/setup-status
- Create: `packages/brain_api/src/brain_api/endpoints/token.py` — GET /api/token
- Create: `packages/brain_api/src/brain_api/endpoints/upload.py` — POST /api/upload
- Modify: `packages/brain_api/src/brain_api/app.py` — register new endpoints + static mount (must be last so it doesn't swallow /api/*)
- Create: `packages/brain_api/tests/test_setup_status.py` — 4 tests (missing vault, missing token, first-run, fully set up)
- Create: `packages/brain_api/tests/test_token_endpoint.py` — 3 tests (same-origin returns token, cross-origin rejected, missing token returns 503 setup_required)
- Create: `packages/brain_api/tests/test_upload_endpoint.py` — 4 tests (happy path, missing token 401, cross-origin rejected, non-text/markdown file type 415)
- Create: `packages/brain_api/tests/test_static_ui.py` — 5 tests (serves /index.html, serves /_next/static/*.js, SPA fallback for /chat, SPA fallback for /chat/abc, 404 for unknown /api/foo)

**Context for the implementer:**
- `OUT_DIR` resolution priority: `BRAIN_WEB_OUT_DIR` env → `<install_dir>/web/out/` (via BRAIN_INSTALL_DIR env) → `<repo>/apps/brain_web/out/` dev fallback. Raise clear error at startup if none exists (Task 7 install script always sets BRAIN_INSTALL_DIR).
- StaticFiles mount ordering: API endpoints registered BEFORE static mount, so `/api/*` + `/ws/*` take precedence. Static mount is last: `app.mount("/", SPAStaticFiles(directory=OUT_DIR, html=True), name="ui")`. `SPAStaticFiles` is a `StaticFiles` subclass overriding `get_response` to return `index.html` on any 404 whose path doesn't start with `/api` or `/ws` or `/_next` — that's the SPA fallback.
- Origin gate: reuse the Plan 05 `OriginHostMiddleware` pattern. `/api/setup-status`, `/api/token`, `/api/upload` all require Origin in {`http://localhost:<port>`, `http://127.0.0.1:<port>`} where port matches the running server. Cross-origin → 403.
- Setup-status logic: `has_token = Path(.brain/run/api-secret.txt).exists()`; `vault_exists = vault_root.exists()`; `vault_path = str(vault_root)`; `is_first_run = not has_token or not vault_exists or not (vault_root / "BRAIN.md").exists()`. No LLM calls; pure filesystem.
- Token endpoint: returns the token as a JSON string for the browser to cache in a React context. Rotation: if the token file is rewritten (next `brain start` cycle), next `/api/token` fetch picks up the new value. Document that the response has `Cache-Control: no-store`.
- Upload endpoint: multipart form parsing via FastAPI's `UploadFile`; content-type whitelist `{text/plain, text/markdown, text/x-markdown, application/json}`; file size cap 10MB; read file text; call `brain_ingest` via the in-process tool dispatcher; return `{patch_id}` with 200 or `{error: "unsupported_media_type"}` with 415.

**Step 1 — Failing tests** (all 16 fail initially).

**Step 2 — Implement** endpoints + static mount.

**Step 3 — Run + commit**

Expected: Python **835+11** (818+11 baseline + 16 new + ~1 migration). No frontend change in this task.

```bash
git commit -m "feat(api): plan 08 task 1 — static UI mount + setup-status + token + upload endpoints"
```

### Task 2 — Next.js static export + client-port 8 server pages + bootstrap context

**Owning subagent:** brain-frontend-engineer

**Goal:** flip `next.config.mjs` to `output: "export"`. Port every server component to a client component that calls brain_api directly. Add a bootstrap React context that wraps the app shell, fetches `/api/setup-status` + `/api/token` once on mount, and provides the token + setup state to every consumer.

**Files:**
- Modify: `apps/brain_web/next.config.mjs` — add `output: "export"`, `images: { unoptimized: true }`, `trailingSlash: true` (export mode prefers trailing slashes for directory-style routing)
- Create: `apps/brain_web/src/lib/bootstrap/bootstrap-context.tsx` — React context + provider. On mount: fetch `/api/setup-status` → if first_run, router.push("/setup/"); else fetch `/api/token` → store in context. Expose `useBootstrap()` → `{token, isFirstRun, vaultPath, loading, error}`.
- Create: `apps/brain_web/src/components/shell/boot-gate.tsx` — wraps children. While `loading`, renders "Starting brain…" skeleton. On error, renders "Can't reach brain — is it running? Try `brain start`."
- Modify: `apps/brain_web/src/lib/api/client.ts` — `apiFetch<T>` reads token from `useBootstrap()` via a module-level accessor (Zustand-backed `useTokenStore` set from the bootstrap effect to avoid prop-drilling). Target URL becomes `/api/<path>` (relative — same origin).
- Modify: `apps/brain_web/src/lib/ws/client.ts` — WS URL becomes `ws://${location.host}/ws/chat/<id>?token=<token>` — port read from `location.host`.
- Delete: `apps/brain_web/src/app/api/proxy/[...path]/route.ts`
- Delete: `apps/brain_web/src/app/api/proxy/upload/route.ts`
- Modify all 8 Server Components to Client Components (drop `readToken()`, rely on BootGate + useBootstrap):
  - `apps/brain_web/src/app/page.tsx` — client; on mount, router.push based on bootstrap result
  - `apps/brain_web/src/app/setup/page.tsx`
  - `apps/brain_web/src/app/chat/page.tsx` + `apps/brain_web/src/app/chat/[thread_id]/page.tsx`
  - `apps/brain_web/src/app/pending/page.tsx`, `inbox/page.tsx`, `browse/page.tsx`, `browse/[...path]/page.tsx`
  - `apps/brain_web/src/app/bulk/page.tsx`, `settings/page.tsx`, `settings/[tab]/page.tsx`
- Modify: `apps/brain_web/src/app/layout.tsx` — mount `<BootstrapProvider>` + `<BootGate>` outside `<AppShell>`
- Modify: `apps/brain_web/tests/e2e/fixtures.ts` — playwright baseURL `http://localhost:4317/`. Remove Next.js dev-server spawn from webServer config; keep only the backend spawn (which now serves the UI).
- Delete: `apps/brain_web/scripts/start-backend-for-e2e.sh/.ps1` wiring that set BRAIN_WEB_OUT_DIR — move to being set by Task 7/8 install script. For e2e, the fixture sets BRAIN_WEB_OUT_DIR to the repo's `apps/brain_web/out/` after running `pnpm build`.
- Modify: `apps/brain_web/src/lib/auth/token.ts` — DELETE (server-only token reader is no longer needed). Update tests that referenced it.
- Create: `apps/brain_web/tests/unit/bootstrap-context.test.tsx` — 5 tests (loading state, first-run triggers router.push, token fetched + exposed, error state renders boot-gate error, cross-origin bootstrap path)
- Modify: every unit test that mocked `@/lib/auth/token` now mocks `useBootstrap` instead (estimate ~12 tests affected)
- Modify: `apps/brain_web/package.json` — add `"export:check": "test -d out"` to `"build"` as `&& test -d out`

**Context for the implementer:**
- Static export produces `apps/brain_web/out/` with HTML per route. Dynamic segments (`chat/[thread_id]`, `browse/[...path]`, `settings/[tab]`) require `generateStaticParams()` returning an empty array — this tells Next.js to generate a catch-all that the SPA fallback on brain_api handles. Alternatively, `export const dynamic = "error"` + rely on brain_api's SPA fallback — clean because it means the client-router does ALL routing post-hydration.
- Token context: must be Zustand-backed (not just React context) because module-level `apiFetch` needs to read it. Pattern: `useTokenStore` exports `getToken(): string | null` for modules and `useToken()` for components. Bootstrap effect sets it via `setToken(token)`.
- WebSocket URL simplification: since we're same-origin, WS URL is `ws://${location.host}/ws/...` — no hardcoded port needed.
- E2E: the backend spawn script must now run `pnpm -F brain_web build` before spawning uvicorn, OR the fixture does the build once + caches. Prefer: one-time build per test run in a global setup (`playwright.config.ts` globalSetup option).
- Hard rule: NO server-side rendering logic anywhere in `apps/brain_web/`. If a test discovers a file using `async export default` without `"use client"`, that's a bug.

**Step 1 — Failing tests**

Write the bootstrap tests + update existing tests to mock `useBootstrap` instead of `@/lib/auth/token`.

**Step 2 — Implement**

- next.config.mjs flip
- Bootstrap context + boot-gate + token store
- apiFetch + WS URL path rewrites
- Delete `/api/proxy/*`
- Port all 8 pages
- Update layout.tsx
- Run `pnpm -F brain_web build` — must produce `apps/brain_web/out/` with HTML files per route

**Step 3 — Run + commit**

Expected: **229+ frontend unit tests** (may dip by a few if proxy-route tests are retired; net roughly stable). **14/14 e2e** pass against the new single-port setup. `apps/brain_web/out/` exists with ≥11 HTML pages.

```bash
cd apps/brain_web && pnpm build && ls out/
pnpm test --run
pnpm exec playwright test
```

```bash
git commit -m "feat(web): plan 08 task 2 — Next.js static export + client-port 8 pages + bootstrap context"
```

**Checkpoint 0 — pause for main-loop review.**
Group 0 lands cleanly when:
- `pnpm -F brain_web build` produces `apps/brain_web/out/` with all 8+ routes as HTML.
- `uvicorn brain_api:app` (with BRAIN_WEB_OUT_DIR set) serves full UI at `/` + API at `/api/*`.
- All frontend unit tests pass (net roughly equal to Plan 07 close).
- All 14 e2e gates still pass on the single-port setup.
- Python test count is **~835+11** (Task 1 added ~16 tests; Task 2 may retire ~1-2 brain_api tests that tested the old proxy expectations, net positive).
- 14-gate demo script passes with updated playwright baseURL.

**Checkpoint 0 — pause for main-loop review.**
Group 0 lands cleanly when:
- `pnpm -F brain_web build` produces `apps/brain_web/out/` with all 8+ routes pre-rendered as HTML.
- `uvicorn brain_api:app` (with BRAIN_WEB_OUT_DIR set) serves the full UI at `/` and API at `/api/*`.
- All 229 frontend unit tests still pass (with updated fixtures — may drop by ~10-15 tests that tested Next.js API routes; those tests move to brain_api integration tests).
- All 14 e2e gates still pass. 14-gate demo still prints `PLAN 07 DEMO OK` when run against the new single-port setup.
- Python 818 + ~15 new tests (+ tests for setup-status, upload, static serve, SPA fallback).

Before Task 3, confirm the static-export flow is stable — supervisor work (Group 1) assumes one-port one-process reality.

---

## Group 1 — CLI supervisors (Tasks 3–6)

**Pattern:** brain_cli grows from a 3-command (chat / mcp / patches) surface to a 10-command surface. Each new verb is its own module under `packages/brain_cli/src/brain_cli/commands/`. Shared runtime helpers (PID management, port probing, browser open, tarball download, migration runner) go under a new `packages/brain_cli/src/brain_cli/runtime/` subpackage.

### Task 3 — brain start / stop / status

**Owning subagent:** brain-installer-engineer

**Goal:** process-group supervisor for the single brain_api process that now serves both API and UI.

**Files:**
- Create: `packages/brain_cli/src/brain_cli/runtime/__init__.py`
- Create: `packages/brain_cli/src/brain_cli/runtime/pidfile.py` — read/write/validate PID file with psutil cross-platform liveness check
- Create: `packages/brain_cli/src/brain_cli/runtime/portprobe.py` — `find_free_port(start=4317, end=4330) -> int`
- Create: `packages/brain_cli/src/brain_cli/runtime/supervisor.py` — `start_brain_api(port, install_dir) -> Process`, `stop_brain_api(pid)`, `wait_for_healthz(port, timeout_s=10)`
- Create: `packages/brain_cli/src/brain_cli/runtime/browser.py` — `open_browser(url)` via stdlib `webbrowser` with Windows fallback
- Create: `packages/brain_cli/src/brain_cli/commands/start.py`, `stop.py`, `status.py`
- Modify: `packages/brain_cli/src/brain_cli/main.py` — register the three commands
- Add psutil to `packages/brain_cli/pyproject.toml`: `psutil>=5.9`
- Create: `packages/brain_cli/tests/runtime/test_pidfile.py` — 4 tests (write+read+validate+stale)
- Create: `packages/brain_cli/tests/runtime/test_portprobe.py` — 3 tests (finds 4317 when free, skips to 4318 when 4317 bound, raises when all busy)
- Create: `packages/brain_cli/tests/runtime/test_supervisor.py` — 4 tests (starts + pid file present, stop kills + pid gone, wait_for_healthz timeout, wait_for_healthz success)
- Create: `packages/brain_cli/tests/commands/test_start_stop_status.py` — 5 tests (start writes pid+port, status reads pid+port, status says "not running" when no pid, stop removes files, double-start idempotent)

**Context for the implementer:**
- `brain start` flow:
  1. Resolve install dir: `BRAIN_INSTALL_DIR` env → `~/Applications/brain/` (Mac) → `%LOCALAPPDATA%\brain\` (Windows) → repo root (dev fallback).
  2. Resolve vault root: `BRAIN_VAULT_ROOT` env → `~/Documents/brain/`.
  3. Read existing PID file at `<vault>/.brain/run/brain.pid`. If present AND psutil says process is alive AND the process is `brain_api` (check cmdline), print "already running at http://localhost:<port>/" and exit 0. If stale, delete pid file + continue.
  4. Probe ports 4317..4330. First free one wins. Write `<vault>/.brain/run/brain.port` with the port as a string.
  5. Set env for child: `BRAIN_WEB_OUT_DIR=<install>/web/out`, `BRAIN_VAULT_ROOT=<vault>`, `BRAIN_API_PORT=<port>`, `BRAIN_ALLOWED_DOMAINS=research,work,personal` (or read from config.json).
  6. Spawn uvicorn subprocess: `uv run --project <install> python -m brain_api`. On Windows, use `CREATE_NEW_PROCESS_GROUP` so Ctrl+C in the parent shell doesn't cascade. Detach stdout/stderr to `<vault>/.brain/logs/brain-api.log` (rotating).
  7. Write `<vault>/.brain/run/brain.pid` with child PID.
  8. Wait for `http://localhost:<port>/healthz` → 200 (max 10s, 200ms poll). If timeout: kill subprocess, print error, exit 1.
  9. `open_browser(f"http://localhost:{port}/")`. Print `brain running at http://localhost:<port>/`.
- `brain stop`: read pid file, SIGTERM via psutil (cross-platform), wait 5s, SIGKILL if still alive, delete pid + port files.
- `brain status`: read pid file → if alive, print `running · pid <pid> · http://localhost:<port>/ · uptime <dur>`; else `not running`.
- Tests use `pytest`'s `monkeypatch` + `tmp_path` heavily. Don't spawn real uvicorn — mock `subprocess.Popen` + `psutil.Process`. There's one integration test that DOES spawn real uvicorn for the healthz wait — guard with `@pytest.mark.slow` or skip in CI if flaky.

**Step 1 — Failing tests** (16 tests across the 4 test files).

**Step 2 — Implement** runtime + commands.

**Step 3 — Run + commit**

```bash
git commit -m "feat(cli): plan 08 task 3 — brain start/stop/status supervisor"
```

### Task 4 — brain doctor

**Owning subagent:** brain-installer-engineer

**Goal:** cross-platform `brain doctor` diagnostic with plain-English PASS/WARN/FAIL output + actionable next-steps per finding.

**Files:**
- Create: `packages/brain_cli/src/brain_cli/commands/doctor.py`
- Create: `packages/brain_cli/src/brain_cli/runtime/checks.py` — 10 check functions, each returns `CheckResult(name, status, message, fix_hint)`
- Create: `packages/brain_cli/tests/commands/test_doctor.py` — 12 tests (one per check's PASS + FAIL path)

**Checks (in order):**
1. `uv` on PATH + version ≥ 0.4.0 (fix: curl install.sh).
2. Install dir exists + has `.venv/` (fix: reinstall).
3. `.venv/` imports brain_core (fix: `uv sync`).
4. Node not required at runtime (informational: print "Node 20 found at <path>" if present, "not found (not required after install)" otherwise).
5. Ports 4317..4330: at least one free (fix: check for rogue servers).
6. Vault root exists + writable (fix: create or chmod).
7. `<vault>/.brain/run/api-secret.txt` exists + 0600 on Unix (fix: `brain setup` to regenerate).
8. `<vault>/.brain/config.json` valid JSON + conforms to ConfigSchema (fix: `brain config reset` or edit).
9. SQLite files (`state.sqlite`, `costs.sqlite`) openable + no corruption (fix: `brain doctor --rebuild-cache`).
10. `<install>/web/out/index.html` exists (fix: rerun install or `brain upgrade`).

**Output format:**
```
brain doctor  · 2026-04-22 11:30

[PASS] uv 0.8.12
[PASS] install dir: /Users/cj/Applications/brain/
[PASS] venv: 217 packages installed
[INFO] Node 20.13.1 found (not required at runtime)
[PASS] ports: 4317-4330 range has 14/14 free
[PASS] vault: /Users/cj/Documents/brain/ writable, 12 domains
[PASS] token file: 0600, 32 bytes
[PASS] config: valid, 8 keys
[PASS] sqlite: state.sqlite (2.4MB), costs.sqlite (18KB) — readable
[PASS] UI bundle: /Users/cj/Applications/brain/web/out/index.html — present

10/10 checks passed · you're good to go.
Run `brain start` to launch.
```

On failures:
```
[FAIL] token file: missing at /Users/cj/Documents/brain/.brain/run/api-secret.txt
       Fix: run `brain setup` to regenerate the token.
```

**Step 1 — Failing tests** (12).

**Step 2 — Implement** checks + doctor command.

**Step 3 — Run + commit**

```bash
git commit -m "feat(cli): plan 08 task 4 — brain doctor (10 diagnostic checks)"
```

### Task 5 — brain upgrade

**Owning subagent:** brain-installer-engineer

**Goal:** `brain upgrade` checks GitHub releases for a newer version, downloads tarball, stages in `<install>-staging/`, runs `uv sync` + DB migrations in staging, swaps install dir atomically, restarts. Rollback on any failure.

**Files:**
- Create: `packages/brain_cli/src/brain_cli/commands/upgrade.py`
- Create: `packages/brain_cli/src/brain_cli/runtime/release.py` — `check_latest_release() -> ReleaseInfo` (queries GitHub API with opt-out), `download_release(url, dest) -> Path`
- Create: `packages/brain_cli/src/brain_cli/runtime/migrator.py` — runs Alembic or yoyo migrations against state.sqlite (reuse Plan 01 migration infra)
- Create: `packages/brain_cli/src/brain_cli/runtime/swap.py` — `stage_upgrade(install_dir, tarball) -> staging_dir`, `swap_in(staging_dir, install_dir)` — atomic rename with rollback
- Create: `packages/brain_cli/tests/commands/test_upgrade.py` — 6 tests (check latest happy path, no update available, download hash verification, stage fails → no-op on install, swap fails → rollback, migration fails → rollback)

**Context for the implementer:**
- Current version: read from `<install>/VERSION` (written by install.sh; fallback to `brain_core.__version__`).
- Check latest: `GET https://api.github.com/repos/ToTo-LLC/cj-llm-kb/releases/latest`; compare `tag_name` (strip leading `v`). Opt-out env `BRAIN_NO_UPDATE_CHECK=1`.
- Download: tarball URL from release assets; verify SHA256 against release body (ship SHA in release description).
- Swap: rename `<install>` → `<install>-prev-<timestamp>`, rename `<install>-staging` → `<install>`. If restart fails, reverse the renames + print recovery instructions.
- Do NOT upgrade across minor-version migrations without user confirmation (if state.sqlite migrations change schema, show "migration plan: N up-migrations" + confirm). Non-interactive mode requires `--yes` flag.
- `brain upgrade` stops the running daemon via `brain stop` equivalent before swapping, starts it again after.

**Step 1 — Failing tests** (6).

**Step 2 — Implement.** Mock the network calls + tarball I/O in tests; integration in Task 10/11.

**Step 3 — Run + commit**

```bash
git commit -m "feat(cli): plan 08 task 5 — brain upgrade (tarball + atomic swap + rollback)"
```

### Task 6 — brain uninstall

**Owning subagent:** brain-installer-engineer

**Goal:** spec §9 §Uninstall flow. 4 prompts. Vault sacred. Typed-confirm `UNINSTALL` for code removal; typed-confirm `DELETE-VAULT` for vault removal (non-default).

**Files:**
- Create: `packages/brain_cli/src/brain_cli/commands/uninstall.py`
- Create: `packages/brain_cli/tests/commands/test_uninstall.py` — 7 tests (happy path code+mcp, keep vault default path, delete vault typed-confirm, wrong-word aborts, non-interactive mode requires --yes, MCP not installed skips prompt, partial failure leaves partial state documented)

**Context for the implementer:**
- Prompts (typed-confirm pattern — case-sensitive input match):
  1. "Remove brain code at `<install>`? Type `UNINSTALL` to confirm (or press Enter to cancel)."
  2. "Remove Claude Desktop MCP config entry? [Y/n]" (only if `brain_mcp_status` says installed)
  3. "Keep vault at `<vault>`? [Y/n]" (default Y)
  4. If 3 was N: "Type `DELETE-VAULT` to permanently remove all your notes at `<vault>`."
  5. "Remove backups at `<vault>/.brain/backups/`? [Y/n]" (only if vault preserved — backups die with vault otherwise)
- `brain stop` first (no running daemon during uninstall).
- Removal order: Claude Desktop MCP entry → backups (if opted in) → code dir → (optionally) vault.
- On partial failure: print exactly what's left + manual cleanup instructions. Don't swallow errors.
- Non-interactive mode: `brain uninstall --yes --delete-vault` skips prompts but still requires `--delete-vault` flag for vault removal (belt and suspenders).
- Shim cleanup: also remove the `brain` shim from PATH (`~/.local/bin/brain` / `%LOCALAPPDATA%\Microsoft\WindowsApps\brain.cmd`).

**Step 1 — Failing tests** (7).

**Step 2 — Implement** command + typed-confirm helpers.

**Step 3 — Run + commit**

```bash
git commit -m "feat(cli): plan 08 task 6 — brain uninstall (4 typed-confirm prompts; vault sacred)"
```

**Checkpoint 1 — pause for main-loop review.** 10 CLI verbs operational: `start`, `stop`, `status`, `doctor`, `upgrade`, `uninstall` + Plan 04's `mcp`, `chat`, `patches` + Task 9's `backup`.

---

## Group 2 — Install scripts + launchers (Tasks 7–9)

**Pattern:** two parallel scripts (sh + ps1) that bootstrap identical end states. Share a post-install verification Python one-liner (`brain doctor`) that both scripts invoke as their last step. Launcher assets land together with the `brain backup` CLI verb since they're both small and thematically adjacent.

### Task 7 — scripts/install.sh (Mac primary, Linux best-effort)

**Owning subagent:** brain-installer-engineer

**Goal:** single-command bootstrap on a fresh Mac 14 box. `curl -fsSL <url>/install.sh | bash` → brain installed + doctor says PASS.

**Files:**
- Create: `scripts/install.sh` — top-level idempotent bash script
- Create: `scripts/install_lib/fetch_tarball.sh` — helper: download GH release tarball + verify SHA256
- Create: `scripts/install_lib/fnm_setup.sh` — helper: install fnm into `<install>/tools/fnm/`, install Node 20, expose `PATH` only during build
- Create: `scripts/install_lib/write_shim.sh` — helper: write `~/.local/bin/brain` + make executable + PATH hint if missing
- Create: `scripts/install_lib/make_app_bundle.sh` — helper: create `~/Applications/brain.app/Contents/MacOS/brain` directory wrapper for Launchpad + Dock drag
- Create: `scripts/tests/test_install_sh.py` — Python integration tests driving install.sh in a temp HOME env (5 tests — happy path, uv already present, repeat idempotency, corrupt tarball SHA abort, missing curl falls back to wget)

**Script flow (idempotent — re-run is safe):**
```bash
# 0. Detect OS + arch (macOS + darwin-arm64 / darwin-x86_64; fail on Linux with "best-effort, contact us" message if not linux-x86_64)
# 1. Check + install uv if missing: curl -LsSf https://astral.sh/uv/install.sh | sh
#    Source the shell hook so the current script sees uv. Idempotent: if already installed, skip.
# 2. Choose install dir: ~/Applications/brain/ (Mac) / ~/.local/share/brain/ (Linux fallback)
# 3. Download tarball: BRAIN_RELEASE_URL (env override) OR https://github.com/ToTo-LLC/cj-llm-kb/releases/latest/download/brain-<version>-<arch>.tar.gz
#    Verify SHA256 against published hash. Fail with plain-English error on mismatch.
# 4. Extract into install dir. If existing install present: move to <install>-prev-<timestamp>/ for rollback.
# 5. Install Node 20 via fnm into <install>/tools/fnm/ (build-only, no global PATH pollution)
# 6. uv sync --all-packages --no-dev inside <install>
# 7. Install pnpm into <install>/tools/ (via `corepack enable && corepack prepare pnpm@9 --activate` using the fnm Node)
# 8. pnpm -F brain_web install && pnpm -F brain_web build
#    Verify <install>/apps/brain_web/out/ exists + has index.html
# 9. Optionally delete node_modules + pnpm-lock cache to reclaim ~400MB (prompt: "Keep Node for faster upgrades? [Y/n]"; default Y per P2 sub-decision)
# 10. Write shim: ~/.local/bin/brain → exec uv run --project <install> brain "$@"
# 11. chmod +x shim; prepend ~/.local/bin to PATH in ~/.zshrc / ~/.bashrc if not present (with clear "PATH edit applied" / "please reopen shell" message)
# 12. Create ~/Applications/brain.app/ directory-wrapper (Info.plist + MacOS/brain shim) for Launchpad/Dock
# 13. Run: uv run --project <install> brain doctor
# 14. Print: "brain installed. Run 'brain start' to begin. Documentation: <url>."
```

**Context for the implementer:**
- Bash 3.2 compatible (macOS ships bash 3.2 at /bin/bash). Avoid bash 4+ features (associative arrays, `[[ -v ]]`, etc.). If writing anything complex, test with `/bin/bash` explicitly.
- `curl -fsSL` preferred; `wget -qO-` fallback. Fail with next-action message if neither present.
- Tarball URL needs a version — since releases don't exist yet, use `BRAIN_RELEASE_URL` env var as override + print "no release URL configured; run with BRAIN_RELEASE_URL=... to use a local tarball" by default. Task 12 will add a real release creation step.
- Logging: every step writes a one-line status to stdout; errors prefix with `error:` + next-action.
- Exit codes: 0 on success, 1 on recoverable failure (network, disk), 2 on prerequisite failure (OS/arch mismatch).

**Step 1 — Failing tests** (5 Python integration tests).

**Step 2 — Implement** install.sh + helpers.

**Step 3 — Run + commit**

Local verification: run `BRAIN_RELEASE_URL=file://$(pwd)/brain-dev.tar.gz bash scripts/install.sh` against a locally-built tarball (`git archive HEAD | gzip > brain-dev.tar.gz`). Should complete in <60s on a warm cache.

```bash
git commit -m "feat(install): plan 08 task 7 — install.sh for Mac (uv+fnm+tarball+shim+.app wrapper)"
```

### Task 8 — scripts/install.ps1 (Windows 11)

**Owning subagent:** brain-installer-engineer

**Goal:** Windows PowerShell equivalent. `irm <url>/install.ps1 | iex` → brain installed + doctor passes. No admin required.

**Files:**
- Create: `scripts/install.ps1` — top-level idempotent PS1 script
- Create: `scripts/install_lib/fetch_tarball.ps1` — download + SHA256 verify
- Create: `scripts/install_lib/fnm_setup.ps1`
- Create: `scripts/install_lib/write_shim.ps1` — write `%LOCALAPPDATA%\Microsoft\WindowsApps\brain.cmd` (on PATH by default)
- Create: `scripts/install_lib/make_start_menu.ps1` — Start Menu shortcut + optional desktop .cmd
- Create: `scripts/tests/test_install_ps1.py` — Python integration tests (5 tests; skip on non-Windows unless running under Windows CI/VM)

**Script flow:**
```powershell
# 0. Detect OS (require Windows 10 build 19041+ / Windows 11) + arch (x64 or arm64)
# 1. Check + install uv: irm https://astral.sh/uv/install.ps1 | iex
# 2. Install dir: $env:LOCALAPPDATA\brain\
# 3. Download tarball: $env:BRAIN_RELEASE_URL or GitHub latest; verify SHA256
# 4. Expand-Archive (or tar.exe which ships in Windows 10+)
# 5. fnm install 20 into <install>\tools\fnm\
# 6. uv sync --all-packages --no-dev
# 7. Corepack pnpm; build
# 8. Shim: <install>\tools\brain.cmd + copy to %LOCALAPPDATA%\Microsoft\WindowsApps\brain.cmd (on PATH by default in Win10+)
# 9. Start Menu: New-Item $env:APPDATA\Microsoft\Windows\Start Menu\Programs\brain.lnk (WScript.Shell COM for .lnk creation)
# 10. Optional desktop .cmd shortcut (prompt)
# 11. brain doctor
```

**Context for the implementer:**
- PowerShell 5.1 compatible (ships in Win10). No PS7-only syntax (`??`, `Where -Object { }` with ternary, `-notin` works in 5.1).
- `Expand-Archive` for tar.gz: PS can't natively; use `tar.exe` (bsdtar, ships in Windows 10 build 17063+).
- Execution policy: assume RemoteSigned at minimum; if stricter, print clear "run in an elevated PowerShell: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned" message.
- Path separator: use `Join-Path` everywhere. No forward slashes.
- SHA256: `Get-FileHash -Algorithm SHA256`.
- Shim as `brain.cmd`: `@echo off\nuv run --project %LOCALAPPDATA%\brain brain %*`.
- `%LOCALAPPDATA%\Microsoft\WindowsApps\` is on PATH by default since Windows 10 1709 — no PATH edit needed.
- `.lnk` creation: Windows-standard COM `WScript.Shell` object; icon path to `<install>\assets\brain.ico`.

**Step 1 — Failing tests** (5, skipped on non-Windows).

**Step 2 — Implement.**

**Step 3 — Run + commit**

```bash
git commit -m "feat(install): plan 08 task 8 — install.ps1 for Windows 11 (uv+fnm+tarball+shim+StartMenu)"
```

### Task 9 — brain backup + launcher assets

**Owning subagent:** brain-installer-engineer

**Goal:** `brain backup` CLI verb (manual snapshot trigger) + minimal launcher visual assets (brain.icns for Mac, brain.ico for Windows, brain.png for Linux desktop files).

**Files:**
- Create: `packages/brain_cli/src/brain_cli/commands/backup.py` — calls `brain_backup_create` tool (Task 25A) with trigger="manual"; prints path + size
- Create: `packages/brain_cli/tests/commands/test_backup_command.py` — 3 tests (happy path, no vault error, backup failure surfaced)
- Create: `assets/brain.icns` — Mac app icon (placeholder — derive from v3 design's `brain-glyph.svg` via `iconutil` or png2icns)
- Create: `assets/brain.ico` — Windows icon (multi-resolution 16/32/48/256)
- Create: `assets/brain.png` — 512x512 PNG for Linux desktop files + fallback
- Create: `assets/README.md` — document icon origins + licenses + regeneration commands
- Modify: `scripts/install.sh` — copy `assets/brain.icns` into `~/Applications/brain.app/Contents/Resources/`
- Modify: `scripts/install.ps1` — copy `assets/brain.ico` into `<install>\assets\` and reference from .lnk

**Context for the implementer:**
- `brain_core` spec already said "The vault is sacred; backups are non-destructive tarballs." The `brain_backup_create` tool (Task 25A, commit `3c228a3`) already implements the logic. Task 9's CLI verb is a thin wrapper.
- Icons: the v3 design zip at `/tmp/brain-design-v3/` includes a brain-glyph SVG. Rasterize to PNG at 1024x1024 then:
  - Mac: use `iconutil` to produce `.icns` (script: create `brain.iconset/` with sized PNGs, `iconutil -c icns brain.iconset`)
  - Windows: use ImageMagick or `icotool`: `magick convert -resize 256x256 brain.png -define icon:auto-resize=16,32,48,256 brain.ico`
- Commit all three binaries + document the regeneration command in `assets/README.md`.

**Step 1 — Failing tests** (3).

**Step 2 — Implement.**

**Step 3 — Run + commit**

```bash
git commit -m "feat(cli): plan 08 task 9 — brain backup command + launcher icons"
```

**Checkpoint 2 — pause for main-loop review.** install.sh + install.ps1 run end-to-end against a local tarball on the developer's machine; `brain doctor` reports all PASS post-install.

---

## Group 3 — QA + demo + close (Tasks 10–12)

### Task 10 — Clean-Mac VM dry run

**Owning subagent:** brain-test-engineer

**Goal:** provision a fresh macOS 14 VM (Tart or UTM), run install.sh from a local tarball (served via `python -m http.server`), walk the setup wizard, ingest one URL end-to-end. Capture receipt + screenshots.

**Files:**
- Create: `docs/testing/clean-mac-vm-receipt.md` — written output of the dry run: commands + exit codes + timings + screenshots + deviations
- Create: `scripts/cut-local-tarball.sh` — helper that git-archives HEAD into `brain-dev-<sha>.tar.gz` with SHA256 published
- Create: `scripts/serve-local-tarball.py` — tiny http.server wrapper on port 9000 so the VM can curl it over the host-only network
- Modify: `docs/testing/manual-qa.md` — add VM-specific notes discovered during the run

**Process:**
1. Boot a fresh macOS 14 VM (Tart: `tart clone ghcr.io/cirruslabs/macos-sonoma-base:latest brain-mac-vm && tart run brain-mac-vm`).
2. On host: `scripts/cut-local-tarball.sh` + `uv run python scripts/serve-local-tarball.py` (listening on host LAN).
3. In VM: `curl -fsSL http://<host-ip>:9000/install.sh | bash` (install.sh pulls tarball from the same host).
4. Watch install complete. Capture timing. Screenshot `brain doctor` output.
5. `brain start`. Browser opens. Walk setup wizard: vault path default, API key (use a FakeLLM override: `BRAIN_LLM_PROVIDER=fake brain start`). Land on /chat.
6. `brain add https://en.wikipedia.org/wiki/Second_brain` (or the CLI ingest command). Watch patch_proposed. Approve from Pending. Verify file on disk.
7. `brain stop`. Verify no orphan processes.
8. `brain uninstall` with `UNINSTALL` typed-confirm; keep vault default. Verify `~/Applications/brain/` gone, `~/Documents/brain/` preserved.
9. Write findings to `docs/testing/clean-mac-vm-receipt.md`.

**Report format:**
- Timing per step (target: total install ≤ 90s on a warm network; first `brain start` ≤ 5s).
- Deviations (any prompts that required explaining; any failures; any copy that confused the tester).
- Screenshot gallery (install complete, doctor green, wizard step 1, chat with first response, pending list, uninstall complete).

### Task 11 — Clean-Windows VM dry run

**Owning subagent:** brain-test-engineer

**Goal:** same as Task 10 but on Windows 11. Verify install.ps1 flow, shim on PATH, Start Menu entry, same ingest round-trip.

**Files:**
- Create: `docs/testing/clean-windows-vm-receipt.md`
- Reuse: `scripts/serve-local-tarball.py` from Task 10

**Process:**
1. Boot fresh Windows 11 VM (UTM or Parallels).
2. Open PowerShell 7 (not Windows PowerShell 5.1 — but the install.ps1 must still be compatible with 5.1; flag any PS7-only syntax found).
3. Run `irm http://<host-ip>:9000/install.ps1 | iex`.
4. Same happy-path ingest as Task 10.
5. Verify: Start Menu has "brain" entry, desktop .cmd works (if opted in), double-click launches browser.
6. `brain stop` + `brain uninstall` + verify cleanup.
7. Write findings.

**Cross-platform findings to watch for:**
- Path separators in log file locations
- SQLite file locking (Windows can hold locks longer)
- Browser launch (Edge vs Chrome default)
- fnm on Windows: potential PATH issue for the build step
- UAC prompts: there should be zero
- Defender SmartScreen: unsigned scripts may warn; document acceptable UX

### Task 12 — scripts/demo-plan-08.py + lessons + tag

**Owning subagent:** brain-test-engineer + main loop

**Goal:** self-contained demo script that simulates a fresh install in a temp dir on the developer's machine. 11-gate end-to-end run. Updates all close docs. Tag `plan-08-install`.

**Files:**
- Create: `scripts/demo-plan-08.py`
- Modify: `tasks/todo.md` — mark Plan 08 ✅
- Modify: `tasks/lessons.md` — append `### Plan 08 — Install + Packaging` section
- Modify: `tasks/plans/08-install.md` — append `## Review` section with demo receipt + stats

**11 gates:**
1. git-archive + SHA256 → brain-dev.tar.gz
2. install.sh runs in a temp HOME dir (dockerized or chroot-ish) and completes with `brain doctor` green
3. `brain start` → /healthz OK, port 4317 bound, browser URL printed
4. Playwright hits `http://localhost:<port>/` → setup wizard loads
5. Walk wizard 6 steps to /chat
6. Ingest one text source via REST; patch_proposed event received
7. Approve the patch via REST; file appears on disk
8. `brain stop` cleans up (no orphan uvicorn)
9. Start + stop a second time — idempotent, no state corruption
10. `brain uninstall` with typed-confirm removes code; vault preserved
11. Second `brain doctor` reports install missing (correct "not installed" state)

**Demo ends with `PLAN 08 DEMO OK` + exit 0.**

**Close docs:**

`tasks/todo.md` row update:
```
| 08 | [Install + Packaging](./plans/08-install.md) | ✅ Complete (2026-MM-DD, tag `plan-08-install`) | One-command install on clean Mac + Windows VMs; static-exported UI served by brain_api; brain start/stop/status/doctor/upgrade/uninstall/backup CLI; 11-gate demo passing (`PLAN 08 DEMO OK`) | brain-installer-engineer, brain-core-engineer, brain-frontend-engineer, brain-test-engineer |
```

`tasks/lessons.md` appends `### Plan 08 — Install + Packaging` with: dates, test counts, static-export pivot retrospective (what broke, what held), fnm cross-platform gotchas, clean-VM dry-run findings, handoff to Plan 09 (final ship: versioning, release notes, manual QA sweep on real user's primary machine).

`tasks/plans/08-install.md` appends `## Review` per the Plan 07 template: tag, completion date, task count, commits since plan-07-frontend, test counts per package, coverage stats, gates, demo receipt paste, handoff to Plan 09.

**Tag + close commit:**
```bash
git tag plan-08-install
git add tasks/todo.md tasks/lessons.md tasks/plans/08-install.md
git commit -m "docs: close plan 08 (install + packaging) — tag plan-08-install"
```

Main loop pushes main + tag after review.

---

## Review

_To be appended by Task 12._
