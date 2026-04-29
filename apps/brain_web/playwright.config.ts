import { randomBytes } from "node:crypto";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig, devices } from "@playwright/test";

// ESM equivalent of ``__dirname`` — package.json sets ``"type": "module"``.
const __dirname = dirname(fileURLToPath(import.meta.url));

/**
 * Playwright e2e configuration.
 *
 * Plan 08 Task 2 single-port pivot: brain_api serves both ``/api/*`` + the
 * static UI (built from ``apps/brain_web/out/``). No separate Next.js
 * server. That removes an entire class of "which port is on which origin"
 * flakes and makes the e2e setup one process.
 *
 * ## Boot sequence
 *
 *   1. ``BRAIN_VAULT_ROOT`` → a fresh temp dir under ``os.tmpdir()`` (or
 *      an inherited value for dev iteration).
 *   2. ``globalSetup`` ensures ``apps/brain_web/out/`` exists (builds if
 *      missing) and sets ``BRAIN_WEB_OUT_DIR`` for the backend.
 *   3. Backend script seeds the vault + starts ``brain_api`` on 4317.
 *      brain_api writes ``<vault>/.brain/run/api-secret.txt`` and mounts
 *      the static UI at ``/``.
 *   4. Playwright drives ``http://localhost:4317/`` — the same origin as
 *      the API, so no cross-origin proxy + no CORS detour.
 *
 * ## Why not reuseExistingServer in CI?
 *
 * CI always wants a fresh vault per run (setup-wizard spec mutates on-disk
 * BRAIN.md). ``reuseExistingServer: !process.env.CI`` keeps local iteration
 * fast while forcing clean state in CI.
 */

// Pre-compute a shared vault root. Honor an inherited BRAIN_VAULT_ROOT (dev
// debugging); otherwise mint a fresh temp dir.
const VAULT_ROOT =
  process.env.BRAIN_VAULT_ROOT ??
  mkdtempSync(join(tmpdir(), `brain-e2e-vault-${randomBytes(4).toString("hex")}-`));
process.env.BRAIN_VAULT_ROOT = VAULT_ROOT;

// Propagate the out-dir path now so webServer.env picks it up. globalSetup
// will validate/build the bundle before the backend spawns.
process.env.BRAIN_WEB_OUT_DIR =
  process.env.BRAIN_WEB_OUT_DIR ?? resolve(__dirname, "out");

export default defineConfig({
  testDir: "./tests/e2e",
  // 60s per test — most specs finish in < 10s locally; buffer covers cold
  // bundles + slow CI runners.
  timeout: 60_000,
  // Shared backend state (vault on disk, in-memory rate-limiter buckets, BM25
  // index). Parallel runs would race each other and occasionally flake.
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  globalSetup: resolve(__dirname, "./tests/e2e/global-setup.ts"),
  use: {
    // Plan 08 Task 2: single-port — app + API share origin on :4317.
    baseURL: "http://localhost:4317",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    locale: "en-US",
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  webServer: [
    {
      // Backend: brain_api on 4317 serves both /api/* and / (static UI).
      //
      // Plan 14 Task 8: branch on platform. Windows can't run a bash script
      // directly (Git Bash is installed on windows-2022 runners but invoking
      // `./scripts/start-backend-for-e2e.sh` relies on shebang interpretation
      // which doesn't work uniformly under PowerShell). The .ps1 sibling
      // mirrors the .sh seeding + uvicorn launch verbatim. ``pwsh`` is on
      // PATH on both windows-2022 and macOS-14 (Microsoft ships PowerShell 7
      // on macOS runners) so we use it explicitly to avoid Windows-PowerShell
      // 5.1 quirks (encoding, $ErrorActionPreference defaults).
      command:
        process.platform === "win32"
          ? "pwsh -NoProfile -ExecutionPolicy Bypass -File ./scripts/start-backend-for-e2e.ps1"
          : "./scripts/start-backend-for-e2e.sh",
      url: "http://127.0.0.1:4317/healthz",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        BRAIN_VAULT_ROOT: VAULT_ROOT,
        BRAIN_ALLOWED_DOMAINS: "research,work",
        BRAIN_WEB_OUT_DIR: process.env.BRAIN_WEB_OUT_DIR,
      },
    },
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
