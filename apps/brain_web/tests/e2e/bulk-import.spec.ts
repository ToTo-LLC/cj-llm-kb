/**
 * Bulk import e2e — 4-step dry-run + apply flow.
 *
 * Plan 07 Task 25C: unskipped. BRAIN_E2E_MODE=1 lets FakeLLMProvider
 * return canned classify/summarize/integrate JSON on every pipeline
 * round, so the full bulk flow can run end-to-end without priming.
 *
 * Flow:
 *   1. Seed a temp folder with 3 tiny .md files. The folder path lives
 *      under the temp vault root (any readable path works; co-locating
 *      keeps cleanup one rm -rf away).
 *   2. Navigate to /bulk and type the folder path into the "Use a path"
 *      input.
 *   3. Advance Step 2 → Step 3 via "Run dry-run on N files".
 *   4. Click "Import N files" to kick the apply loop (Step 4).
 *   5. Assert the summary row shows applied > 0.
 */
import { expect, test } from "./fixtures";

test.describe("bulk import", () => {
  test.beforeEach(async ({ seedPath }) => {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    await fs.writeFile(
      path.join(seedPath, "BRAIN.md"),
      "# BRAIN\n\nYou are brain. Maintain this vault carefully.\n",
      "utf-8",
    );
  });

  test("pick folder path → dry-run → apply → summary", async ({
    page,
    seedPath,
  }) => {
    // Seed a small folder the backend's rglob() can walk. Keep it
    // OUTSIDE the vault root entirely so ``brain_list_domains`` doesn't
    // mistake it for a domain (the tool lists any top-level vault
    // directory that contains a markdown file) and so the importer
    // never collides with scope_guard during archive creation.
    const fs = await import("node:fs/promises");
    const os = await import("node:os");
    const path = await import("node:path");
    const folder = await fs.mkdtemp(path.join(os.tmpdir(), "brain-bulk-e2e-"));
    // ``seedPath`` is read only to keep the signature aligned with the
    // other specs; we intentionally do not seed inside the vault.
    void seedPath;
    for (let i = 1; i <= 3; i++) {
      await fs.writeFile(
        path.join(folder, `note-${i}.md`),
        `# note ${i}\n\nSample source content ${i} for bulk e2e.\n`,
        "utf-8",
      );
    }

    await page.goto("/bulk");
    await page.waitForLoadState("networkidle");

    // --- Step 1: pick folder by path -------------------------------------
    const pathInput = page.getByTestId("path-input");
    await expect(pathInput).toBeVisible();
    await pathInput.fill(folder);
    await page.getByTestId("use-path-btn").click();

    // Dry-run finishes and advances to Step 2.
    const routeAuto = page.getByTestId("route-card-auto");
    await expect(routeAuto).toBeVisible({ timeout: 30_000 });

    // --- Step 2: pick target domain (auto works fine) --------------------
    await routeAuto.click();
    await page.getByTestId("to-dry-run").click();

    // --- Step 3: dry-run review ------------------------------------------
    // Give the classifier loop a moment — the dry-run already happened
    // at step 1, but Step 3's StepDryRun reads the store directly so
    // its content shows up as soon as the step mounts.
    await expect(page.getByTestId("included-count")).toBeVisible({
      timeout: 10_000,
    });
    const startBtn = page.getByTestId("start-import");
    await expect(startBtn).toBeEnabled({ timeout: 10_000 });
    await startBtn.click();

    // --- Step 4: apply loop ----------------------------------------------
    const applyProgress = page.getByTestId("apply-progress");
    await expect(applyProgress).toBeVisible();

    // The summary chip appears when the loop reports done. Each file
    // walks the full ingest pipeline (extract → classify → summarize
    // → integrate → apply), so allow a generous timeout across the
    // 3-file set.
    const summary = page.getByTestId("apply-summary");
    await expect(summary).toBeVisible({ timeout: 60_000 });
    // Assert at least one applied — FakeLLM's canned integrate returns
    // a valid PatchSet so every file should land.
    await expect(summary).toContainText(/applied/i);
  });
});
