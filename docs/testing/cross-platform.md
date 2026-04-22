# Cross-platform test notes

First-class targets: **macOS 13+** and **Windows 11**. Linux falls out
for free but is not a day-one target. CI enforces both via a GitHub
Actions matrix. A green Mac run alone does not unblock a merge.

This doc tracks platform-specific landmines we hit and the guardrails
that keep them from regressing. Each plan adds a section.

---

## Plan 04 — MCP server

(see `scripts/demo-plan-04.py` + `tasks/plans/04-mcp.md`)

* **Subprocess spawn** — `brain mcp selftest` uses
  `stdio_server_parameters(command, args, env)`. Resolve `sys.executable`
  at call time, never rely on PATH. `shell=False` everywhere.
* **Claude Desktop config path** —
  `brain_core.integrations.claude_desktop` uses
  `pathlib.Path.home()` + Windows `%APPDATA%` fallback. No literal
  backslashes or forward slashes in config-path construction.

## Plan 05 — brain_api

* **Token file permissions** — `api-secret.txt` written with mode 0600
  on POSIX; on Windows the chmod is a no-op and NTFS ACL enforcement is
  documented as best-effort. See
  `packages/brain_api/src/brain_api/auth.py::_write_token`.
* **Port binding** — 4317 bound to `127.0.0.1` only (never `0.0.0.0`).
  OriginHostMiddleware rejects any non-loopback Host.
* **WebSocket loopback** — `OriginHostMiddleware` accepts
  `localhost` and `127.0.0.1`; Windows sometimes adds `::1` via IPv6 in
  browser dev tools, which is already in `_LOOPBACK_HOSTS`.

## Plan 07 — Web frontend

Nine-point sweep from `tasks/plans/07-frontend.md` § Task 24. Each item
either has inline-fixed drift, a regression test, or a deferral with a
tracked owner.

### 1. Paths in Next.js server components

* `readToken()` uses `node:path.join()` + `os.homedir()` + env var
  (`BRAIN_VAULT_ROOT`). Never literal path separators.
* The Next.js server proxy reads the vault root from env, not from a
  hardcoded `~/...` (which would break on Windows).
* `apps/brain_web/scripts/e2e_backend.py` resolves the vault via
  `pathlib.Path(os.environ["BRAIN_VAULT_ROOT"])` — never
  `os.path.join`-style string concatenation.

### 2. Line endings LF on disk

* `tokens.css`, `globals.css`, all generated shadcn primitives — all
  committed with `eol=lf` in `.gitattributes`.
* `start-backend-for-e2e.ps1` normalizes CRLF→LF via
  `($welcome -replace "`r`n", "`n")` before writing seed files.
* `Prettier.endOfLine = "lf"` in the frontend config so devs on Windows
  don't re-save with CRLF.

### 3. HTML5 drag-drop (Mac + Windows parity)

* The drop handler in `app-shell.tsx` reads `dataTransfer.types` via
  `.includes("Files")`. Works identically on Mac + Windows Chromium.
* The `dragleave` noisy-fire workaround (`relatedTarget === null`
  check) is tested in `tests/unit/drop-zone.test.tsx`.
* Playwright e2e in `tests/e2e/ingest-drag-drop.spec.ts` exercises the
  full path on both CI matrix runners.

### 4. Monaco WebAssembly + worker loading on Windows

* `@monaco-editor/react` lazy-loads the editor bundle; we don't ship a
  custom webpack worker config.
* Verified in the manual QA checklist §11 (Monaco loads with no WASM
  errors on both OSes). The Playwright a11y sweep would surface a 500
  load error as a navigation failure.

### 5. Next.js production build on Windows

* `pnpm build` is the only supported production command. Dev mode has
  surfaced Windows-path webpack loader bugs historically; we avoid it
  for e2e.
* `playwright.config.ts` hard-codes `pnpm build && pnpm start` as the
  frontend webServer command — identical on both OSes.

### 6. `⌘K` (Mac) / `Ctrl+K` (Windows) shortcut

* Handler in `apps/brain_web/src/components/shell/app-shell.tsx` checks
  **both** `e.metaKey` and `e.ctrlKey` so the shortcut fires on Mac
  (Cmd) and Windows (Ctrl) without platform-detection branching.
* Guard ignores the shortcut when focus is inside an editable input so
  the browser's native "focus search bar" / composer bindings keep
  working.
* Regression test: `tests/unit/shortcut.test.ts` asserts both
  modifier paths open the search overlay, and that typing `K` without a
  modifier does nothing.

### 7. Font loading — local Roboto

* Fonts served from `apps/brain_web/public/fonts/` with `font-display:
  swap`. No external CDN so offline + locked-down corporate networks
  work.
* Manual QA §11 verifies via DevTools Computed tab that Roboto resolves
  (not a system-font fallback).

### 8. Subprocess spawning

* `scripts/demo-plan-07.py` uses `subprocess.Popen` with
  `shell=False` everywhere.
* `pnpm` resolved via `shutil.which("pnpm")` up front — no PATH lookup
  inside the Popen call, which on Windows can surface
  `FileNotFoundError` instead of a clear "pnpm not on PATH".
* Signal handling: SIGTERM on POSIX, `CTRL_BREAK_EVENT` on Windows
  (plus a `creationflags=CREATE_NEW_PROCESS_GROUP` pattern if needed —
  scaffold-level; Task 25 may tighten).

### 9. Token file permissions on Windows

* Plan 05 documented this as best-effort — no change required in Plan
  07. The Next.js proxy reads the file with stock `node:fs/promises`,
  which respects Windows ACLs when set.

---

## Sweep log

Each line records a finding + fix during a cross-platform audit pass.

| Plan | Finding | Fix | Regression |
|---|---|---|---|
| 07 / Task 24 | `⌘K` handler was correct but untested | (none — handler already uses `metaKey || ctrlKey`) | `tests/unit/shortcut.test.ts` |
| 07 / Task 24 | `/chat/page.tsx` was statically prerendered at `pnpm build` time. With no `BRAIN_VAULT_ROOT` in the build env, `readToken()` returned null and the route's output baked in `redirect("/setup")`. At runtime the cached redirect bounced every `router.push("/chat")` back to `/setup`, including the setup wizard's final click. Surfaced by `demo-plan-07.py` gate 2 failing intermittently. | `export const dynamic = "force-dynamic"` in `apps/brain_web/src/app/chat/page.tsx` — the route is now rendered per-request with the live token. | `scripts/demo-plan-07.py` gate 2 |

---

## Running the matrix locally

### Mac

```bash
cd /path/to/brain
uv run pytest                            # Python unit + integration
pnpm --dir apps/brain_web test -- --run  # frontend unit
pnpm --dir apps/brain_web e2e            # Playwright
uv run python scripts/demo-plan-07.py    # scaffold demo
```

### Windows

```powershell
cd C:\path\to\brain
uv run pytest
pnpm --dir apps\brain_web test -- --run
pnpm --dir apps\brain_web e2e
uv run python scripts\demo-plan-07.py
```

If any of these commands requires platform-specific branching, the
branching MUST live inside the script (`sys.platform` / `process.platform`
check), never in the invocation.
