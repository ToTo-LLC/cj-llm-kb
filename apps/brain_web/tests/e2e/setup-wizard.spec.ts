/**
 * Setup wizard e2e — on a fresh vault (no BRAIN.md), the root route
 * redirects to ``/setup``. We walk through the 6 steps using the "Skip
 * this" escape hatch for the theme + BRAIN.md + Claude Desktop steps so
 * we don't need real disk state beyond the token file the backend writes
 * at boot.
 *
 * Why skip steps 4 + 5 + 6? They mutate BRAIN.md + a domain index via
 * real ``proposeNote`` calls. We don't need to prove the seed path here
 * — ``a11y.spec.ts`` exercises the same round-trip via its
 * ``seedBrainMdIfMissing`` helper. What we DO prove: the 6-step progress
 * meter advances, Back / Continue nav works, the final "Start using
 * brain" button routes to ``/chat``, and axe-core clears every step.
 */
import { expect, test } from "./fixtures";

test.describe("setup wizard", () => {
  // Guard: if a prior spec already seeded BRAIN.md (a11y.spec.ts runs
  // alphabetically before this file), the root redirect lands on /chat
  // instead of /setup. Delete BRAIN.md + clear localStorage first so this
  // spec is self-contained.
  test.beforeEach(async ({ page, seedPath }, testInfo) => {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const brainMd = path.join(seedPath, "BRAIN.md");
    await fs.rm(brainMd, { force: true });
    // localStorage flag is per-origin and persists across navigations —
    // must clear so /setup redirect fires on the next page.goto("/").
    await page.context().clearCookies();
    testInfo.annotations.push({ type: "vault", description: seedPath });
  });

  test("first-run → walks 6 steps → lands on /chat", async ({
    page,
    checkA11y,
  }) => {
    // Step 0: root redirects to /setup because BRAIN.md is missing.
    await page.goto("/");
    await page.waitForURL("**/setup");
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
    await page.waitForURL("**/chat");
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
