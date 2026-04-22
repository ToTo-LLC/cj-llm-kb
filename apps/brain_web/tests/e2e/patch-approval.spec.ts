/**
 * Patch approval e2e — seeded patch → approve button → list empties.
 *
 * Plan 07 Task 25C: unskipped. The previous skip rationale (per-spec
 * vault isolation) is mitigated by this spec seeding a patch that is
 * unique per test run (patch_id + target path include a timestamp) and
 * leaving approved patches on disk — Playwright runs single-worker with
 * ``fullyParallel: false`` so no other spec races for the same file.
 *
 * Flow:
 *   1. Seed a pending patch via ``POST /api/tools/brain_propose_note``
 *      using the per-run token read from ``.brain/run/api-secret.txt``.
 *   2. Navigate to ``/pending``; assert the card renders.
 *   3. Click the card's inline Approve button.
 *   4. Assert the success toast ("Approved.") fires and the card
 *      disappears from the list.
 */
import { expect, test } from "./fixtures";

test.describe("patch approval", () => {
  // BRAIN.md seed so root doesn't redirect to /setup (which would
  // fight the a11y sweep on shared workers). Same pattern as chat-turn.
  test.beforeEach(async ({ seedPath }) => {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    await fs.writeFile(
      path.join(seedPath, "BRAIN.md"),
      "# BRAIN\n\nYou are brain. Maintain this vault carefully.\n",
      "utf-8",
    );
  });

  test("seeded patch → approve → toast → card gone", async ({
    page,
    seedPath,
  }) => {
    // Read the per-run token straight from disk — the brain_api token
    // file is the same one Next.js's readToken() consumes, so using it
    // in tests keeps the auth flow identical to production.
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const tokenPath = path.join(seedPath, ".brain", "run", "api-secret.txt");
    const token = (await fs.readFile(tokenPath, "utf-8")).trim();

    // Stamp a unique path so the seeded patch can't collide with leftover
    // state from a previous run (Plan 07 demo scripts + prior spec runs
    // may share the temp vault across sessions). Host: localhost header
    // is required by OriginHostMiddleware.
    const stamp = Date.now();
    const targetPath = `work/notes/approval-e2e-${stamp}.md`;
    const seed = await page.request.post(
      "http://127.0.0.1:4317/api/tools/brain_propose_note",
      {
        headers: {
          "X-Brain-Token": token,
          "Content-Type": "application/json",
          Origin: "http://127.0.0.1:4317",
        },
        data: {
          path: targetPath,
          content: `# Approval e2e\n\nSeeded at ${stamp}.\n`,
          reason: "plan 07 task 25 e2e — approve from list",
        },
      },
    );
    expect(seed.ok(), await seed.text()).toBeTruthy();
    const seedBody = (await seed.json()) as {
      data?: { patch_id?: string };
    };
    const patchId = seedBody.data?.patch_id;
    expect(patchId).toBeTruthy();

    await page.goto("/pending");
    await page.waitForLoadState("networkidle");

    const card = page.locator(`#patch-card-${patchId}`);
    await expect(card).toBeVisible();

    // Click the inline Approve button inside this specific card.
    await card.getByRole("button", { name: /^Approve$/ }).click();

    // The approve flow (a) removes the card optimistically, (b) shows a
    // "Approved." toast. We assert both so a silent failure (toast
    // fires but the card sticks around) still fails the test.
    await expect(card).toHaveCount(0, { timeout: 10_000 });
    // System-store toast rendered inside a role=status live region.
    await expect(page.getByText("Approved.")).toBeVisible({
      timeout: 5_000,
    });

    // The target file should have landed on disk.
    const stat = await fs
      .stat(path.join(seedPath, targetPath))
      .then(() => true)
      .catch(() => false);
    expect(stat).toBe(true);
  });
});
