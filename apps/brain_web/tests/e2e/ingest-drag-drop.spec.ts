/**
 * Ingest drag-drop e2e — upload text file → classify → done state.
 *
 * Plan 07 Task 25C: unskipped. FakeLLMProvider now returns canned
 * classify + summarize + integrate JSON when ``BRAIN_E2E_MODE=1`` is
 * set, so the entire ingest pipeline can run against an empty queue.
 *
 * Flow:
 *   1. Navigate to ``/inbox``.
 *   2. Use Playwright's ``setInputFiles`` to feed the hidden file input
 *      that backs the "Browse files" affordance — identical code path
 *      to a real drag-drop because DropZone delegates to the same
 *      ``handleFile`` callback for both.
 *   3. Wait for the optimistic source row to appear.
 *   4. Wait for the row to transition to ``done`` once the ingest
 *      promise resolves.
 */
import { expect, test } from "./fixtures";

test.describe("ingest drag-drop", () => {
  test.beforeEach(async ({ seedPath }) => {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    await fs.writeFile(
      path.join(seedPath, "BRAIN.md"),
      "# BRAIN\n\nYou are brain. Maintain this vault carefully.\n",
      "utf-8",
    );
  });

  test("upload .md file → source row → done", async ({ page }) => {
    await page.goto("/inbox");
    await page.waitForLoadState("networkidle");

    const drop = page.getByTestId("drop-zone");
    await expect(drop).toBeVisible();

    // The hidden <input type="file"> inside DropZone is the production
    // upload path (the "Browse files" button clicks it). Setting files
    // on that input fires the same onChange handler the file picker
    // does — there's no dedicated test seam.
    const fileInput = drop.locator('input[type="file"]');

    // Tiny synthetic source — enough bytes for FakeLLM's canned
    // summarize to return a structured body.
    const stamp = Date.now();
    await fileInput.setInputFiles({
      name: `e2e-ingest-${stamp}.md`,
      mimeType: "text/markdown",
      buffer: Buffer.from(
        `# E2E ingest ${stamp}\n\nThis note was uploaded via the ingest e2e spec.\n`,
      ),
    });

    // A row appears immediately (inbox-store.addOptimistic) in the
    // "In progress" tab. Once ingest completes it moves to the
    // "Recent" tab (see ``inbox/tabs.tsx``). We wait for the Recent
    // tab's counter to tick to 1 — that's the done signal.
    const recentTab = page.getByRole("tab", { name: /Recent/i });
    await expect(recentTab).toContainText("1", { timeout: 30_000 });

    // Switch to Recent to confirm the row is there with the right name.
    await recentTab.click();
    await expect(
      page.getByText(`e2e-ingest-${stamp}.md`, { exact: false }).first(),
    ).toBeVisible({ timeout: 5_000 });
  });
});
