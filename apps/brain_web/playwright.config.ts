import { randomBytes } from "node:crypto";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright e2e configuration.
 *
 * Plan 07 Task 23 ships a pragmatic MVP bar: Chromium-only, single worker,
 * zero retries — flakes are bugs, not something to paper over. Cross-OS
 * coverage (macOS + Windows) is handled at the CI matrix level in Plan 08.
 *
 * ## Boot sequence
 *
 * Both child processes share one ``BRAIN_VAULT_ROOT`` computed here at
 * config-load time. Without a shared pre-computed path the two
 * ``webServer`` entries would each mint their own ``mktemp`` dir — the
 * backend would write the token to one path while the Next.js server read
 * from another, and every ``readToken()`` call would miss.
 *
 *   1. ``BRAIN_VAULT_ROOT`` → a fresh temp dir under ``os.tmpdir()``.
 *   2. Backend script seeds the vault + starts ``brain_api`` on 4317.
 *      ``brain_api`` writes ``<vault>/.brain/run/api-secret.txt``.
 *   3. Next.js starts on 4316 with the same ``BRAIN_VAULT_ROOT`` in its
 *      env; ``readToken()`` picks up the token and server-side proxying
 *      just works.
 *
 * ## Why not reuseExistingServer in CI?
 *
 * CI always wants a fresh vault per run (the setup-wizard spec mutates
 * the on-disk BRAIN.md). ``reuseExistingServer: !process.env.CI`` keeps
 * local iteration fast while forcing clean state in CI.
 */

// Pre-compute a shared vault root so both webServers agree on paths.
// Honor an inherited BRAIN_VAULT_ROOT when set (lets devs point the harness
// at a curated vault for debugging); otherwise mint a fresh temp dir.
const VAULT_ROOT =
  process.env.BRAIN_VAULT_ROOT ??
  mkdtempSync(join(tmpdir(), `brain-e2e-vault-${randomBytes(4).toString("hex")}-`));

// Propagate to the parent process so webServer.env inherits by default and
// any sub-process spawned by tests (if we ever need one) sees the same path.
process.env.BRAIN_VAULT_ROOT = VAULT_ROOT;

export default defineConfig({
  testDir: "./tests/e2e",
  // 60s per test — most specs finish in < 10s locally; the buffer covers
  // cold builds + slow CI runners without masking a genuine hang.
  timeout: 60_000,
  // Shared backend state (vault on disk, in-memory rate-limiter buckets,
  // BM25 index). Parallel runs would race each other and occasionally flake.
  fullyParallel: false,
  workers: 1,
  // Flakes are bugs. Don't retry them away — diagnose + fix + add a
  // regression test. If genuine non-determinism shows up (network, WS
  // timing), document it in tasks/lessons.md before bumping this.
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:4316",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    locale: "en-US",
    // Surface slow actions quickly — real users notice 5s clicks.
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  webServer: [
    {
      // Backend: brain_api on 4317 via uvicorn --factory.
      command: "./scripts/start-backend-for-e2e.sh",
      url: "http://127.0.0.1:4317/healthz",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        BRAIN_VAULT_ROOT: VAULT_ROOT,
        BRAIN_ALLOWED_DOMAINS: "research,work",
      },
    },
    {
      // Frontend: Next.js on 4316 via production build + start. Dev mode
      // would work functionally but SSR warm-up flakes on first navigation
      // and HMR logs pollute test output. ``reuseExistingServer`` lets
      // devs run ``pnpm start`` in one terminal + ``pnpm e2e`` in another
      // to skip the rebuild every iteration.
      command: "pnpm build && pnpm start",
      url: "http://localhost:4316",
      reuseExistingServer: !process.env.CI,
      timeout: 240_000,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        BRAIN_VAULT_ROOT: VAULT_ROOT,
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
