/**
 * Setup wizard e2e — walk the 6-step wizard, assert the progress meter
 * advances, Back / Continue nav works, the final "Start using brain"
 * button routes to ``/chat``, and axe-core clears every step.
 *
 * Why skip steps 4 + 5 + 6? They mutate BRAIN.md + a domain index via
 * real ``proposeNote`` calls. We don't need to prove the seed path here
 * — ``a11y.spec.ts`` exercises the same round-trip via its
 * ``seedBrainMdIfMissing`` helper.
 *
 * Plan 09 Task 11 F5/F7 sweep note: the backend's ``is_first_run`` rule
 * is now ``!has_token OR !vault_exists`` — BRAIN.md presence is NOT part
 * of it. Playwright's BRAIN_VAULT_ROOT temp dir always has both by the
 * time the UI mounts (brain_api writes the token at boot), so the root
 * route lands on ``/chat`` rather than ``/setup``. This spec navigates
 * directly to ``/setup/`` to exercise the wizard without depending on
 * a first-run redirect that no longer fires for our fixture.
 */
import { expect, test } from "./fixtures";

test.describe("setup wizard", () => {
  // Guard: if a prior spec already seeded BRAIN.md (a11y.spec.ts runs
  // alphabetically before this file), navigating to /chat might succeed
  // from root; but we don't rely on the root redirect here — the wizard
  // is always reachable at /setup/ directly. Clear cookies + BRAIN.md to
  // keep the wizard's "seed later" step observable as a no-op.
  test.beforeEach(async ({ page, seedPath }, testInfo) => {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const brainMd = path.join(seedPath, "BRAIN.md");
    await fs.rm(brainMd, { force: true });
    await page.context().clearCookies();
    testInfo.annotations.push({ type: "vault", description: seedPath });
  });

  test("walks 6 steps → lands on /chat", async ({
    page,
    checkA11y,
  }) => {
    // Plan 08 Task 2 added ``trailingSlash: true``; landing page is
    // ``/setup/``. Navigate directly — see module docstring for why we
    // don't rely on a root redirect.
    await page.goto("/setup/");
    await page.waitForURL(/\/setup\/?$/);
    await expect(page.getByText("Welcome to")).toBeVisible();
    await expect(page.getByText("Step 1 of 6")).toBeVisible();
    await checkA11y(page, "setup-step-1-welcome");

    // Step 1 → 2: Welcome → Vault location.
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page.getByText("Step 2 of 6")).toBeVisible();
    await checkA11y(page, "setup-step-2-vault-location");

    // Step 2 → 3: Vault location → API key. VaultLocationStep requires a
    // non-empty path; the default ``~/Documents/brain`` is prefilled by
    // <Wizard> so Continue is enabled without further input.
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page.getByText("Step 3 of 6")).toBeVisible();
    await checkA11y(page, "setup-step-3-api-key");

    // Step 3 → 4: API key → Theme. API key is optional per the Wizard
    // canContinue logic (step 3 has no gating), so skip entering one.
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page.getByText("Step 4 of 6")).toBeVisible();
    await checkA11y(page, "setup-step-4-theme");

    // Step 4 → 5: Theme → BRAIN.md. Default pick is "blank" so no seed
    // is written — keeps this spec independent of pending-patch state.
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page.getByText("Step 5 of 6")).toBeVisible();
    await checkA11y(page, "setup-step-5-brain-md");

    // Step 5 → 6: BRAIN.md → Claude Desktop. "Skip this" keeps BRAIN.md
    // unseeded — same rationale as step 4. The real seed path is
    // exercised by a11y.spec.ts's beforeAll.
    await page.getByRole("button", { name: /Skip this/ }).click();
    await expect(page.getByText("Step 6 of 6")).toBeVisible();
    await checkA11y(page, "setup-step-6-claude-desktop");

    // Step 6 → done: "Start using brain" navigates to /chat.
    await page.getByRole("button", { name: /Start using brain/ }).click();
    await page.waitForURL(/\/chat\/?$/);
    // Empty-state copy from <NewThreadEmpty> confirms we landed on the
    // new-thread variant, not a populated thread.
    await expect(
      page.getByText(/What are we working on\??/i),
    ).toBeVisible();
  });

  test("back nav decrements step counter", async ({ page }) => {
    await page.goto("/setup");
    await expect(page.getByText("Step 1 of 6")).toBeVisible();

    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page.getByText("Step 2 of 6")).toBeVisible();

    await page.getByRole("button", { name: /Back/ }).click();
    await expect(page.getByText("Step 1 of 6")).toBeVisible();
  });
});
