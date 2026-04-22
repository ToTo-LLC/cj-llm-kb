/**
 * Playwright global setup — Plan 08 Task 2.
 *
 * Single-port e2e setup: brain_api serves both the API + the static UI.
 * Before the backend boots, ensure the Next.js static bundle exists at
 * ``apps/brain_web/out/``. If the bundle is missing (clean checkout, fresh
 * clone) we run ``pnpm -F brain_web build`` once — subsequent runs are
 * fast (bundle is up-to-date or cached).
 *
 * ``BRAIN_WEB_OUT_DIR`` points the backend at the bundle so the static
 * mount in ``brain_api`` serves it from ``/``.
 */
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));

export default async function globalSetup(): Promise<void> {
  const webAppDir = resolve(__dirname, "..", "..");
  const outDir = join(webAppDir, "out");

  // Propagate the out dir to the backend via env (playwright.config.ts reads
  // process.env for webServer.env so subprocess inherits it).
  process.env.BRAIN_WEB_OUT_DIR = outDir;

  if (!existsSync(join(outDir, "index.html"))) {
    // Run the build from the monorepo root so pnpm filters ("-F brain_web")
    // resolve against the workspace. spawnSync inherits stdio so build
    // output streams to the Playwright log in real time — makes flakes
    // diagnosable without re-running.
    const repoRoot = resolve(webAppDir, "..", "..");
    const result = spawnSync("pnpm", ["-F", "brain_web", "build"], {
      cwd: repoRoot,
      stdio: "inherit",
      env: process.env,
    });
    if (result.status !== 0) {
      throw new Error(
        `[e2e globalSetup] pnpm -F brain_web build failed with exit code ${result.status}`,
      );
    }
  }
}
