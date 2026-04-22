/**
 * axe-core accessibility sweep — every top-level route gets loaded, given
 * a beat to settle, and run through axe with WCAG 2.2 AA filters. Any
 * violation fails the suite; this is the hard a11y gate for Plan 07.
 *
 * We run this AFTER a BRAIN.md seed so the setup-wizard redirect does not
 * hijack the navigation. Seeding is direct on-disk — BRAIN.md lives at
 * the vault root (no domain), so the ``proposeNote`` path rejects it
 * (scope guard demands a domain). Tools-surface seeding for BRAIN.md is
 * handled specially by the setup wizard itself; for test infra we just
 * write the file.
 *
 * Pages covered (8):
 *   /chat, /inbox, /browse, /pending, /bulk,
 *   /settings/general, /settings/providers, /settings/domains
 *
 * /setup lives in a separate spec because its flow mutates BRAIN.md and
 * we don't want the a11y sweep fighting with the wizard spec for state.
 */
import { test } from "./fixtures";

const PAGES = [
  "/chat",
  "/inbox",
  "/browse",
  "/pending",
  "/bulk",
  "/settings/general",
  "/settings/providers",
  "/settings/domains",
] as const;

test.describe("a11y — WCAG 2.2 AA sweep", () => {
  // Seed BRAIN.md directly on disk so the root redirect lands on /chat
  // (not /setup). Disk I/O is safe because the vault is a temp dir minted
  // per run; no production data at risk. The setup-wizard spec removes
  // this same file in its beforeEach and re-drives the wizard flow.
  test.beforeAll(async ({ seedPath }) => {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    await fs.writeFile(
      path.join(seedPath, "BRAIN.md"),
      "# BRAIN\n\nYou are brain. Maintain this vault carefully.\n",
      "utf-8",
    );
  });

  for (const path of PAGES) {
    test(`${path} has 0 violations`, async ({ page, checkA11y }) => {
      await page.goto(path);
      // ``networkidle`` waits for outstanding fetches (including the
      // ``brain_list_pending`` / ``brain_list_sources`` bootstraps) to
      // drain — without it axe can run against a skeleton state that
      // doesn't reflect real content.
      await page.waitForLoadState("networkidle");
      await checkA11y(page, path);
    });
  }
});
