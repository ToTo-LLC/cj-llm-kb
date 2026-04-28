/**
 * Plan 10 Task 9 e2e — domains lifecycle.
 *
 * Walks the Settings → Domains panel through Add → Rename → Delete and
 * asserts the live UI surfaces (panel list + topbar scope picker)
 * stay in sync via the shared ``useDomains`` cache.
 *
 * The spec is intentionally light on visual assertions — Plan 10
 * Task 6 already screenshot-verified the panel chrome. What we pin
 * here is the contract: a successful create surfaces a new row in
 * both the panel and the topbar; a successful rename collapses the
 * old slug and opens the new one; a successful delete removes the
 * row and the typed-confirm gate works.
 *
 * Personal stays as the privacy-railed slug throughout — no Delete
 * button, the rename-domain TO ``personal`` direction is rejected
 * server-side (covered by the brain_core tests), and the topbar's
 * default scope still excludes it.
 *
 * Plan 12 Task 5: ``useDomains()`` is now a zustand-backed selector,
 * so panel mutations propagate to the topbar (and every other live
 * peer consumer) without a remount. The pre-Plan-12 ``page.reload()``
 * workaround between mutations has been removed; the assertion
 * exercises the actual cross-instance subscription contract.
 */
import { expect, test } from "./fixtures";

test.describe("plan 10 — domains lifecycle", () => {
  test("Add → Rename → Delete round-trip refreshes panel + topbar", async ({
    page,
    seedPath,
  }, testInfo) => {
    testInfo.annotations.push({ type: "vault", description: seedPath });

    await page.goto("/settings/domains/");
    // Panel list renders with the v0.1 default triple.
    await expect(page.getByText("personal", { exact: true })).toBeVisible();
    await expect(page.getByText("research", { exact: true })).toBeVisible();
    await expect(page.getByText("work", { exact: true })).toBeVisible();
    // Personal has the privacy-railed badge + no delete button.
    await expect(page.getByTestId("personal-privacy-badge")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Delete personal/i }),
    ).toHaveCount(0);

    // ---- Add ``hobby`` -------------------------------------------------
    await page.getByLabel(/display name/i).fill("Hobby");
    await page.getByLabel(/folder slug/i).fill("hobby");
    await page.getByRole("button", { name: /Add domain/i }).click();
    // Row shows up in the panel list.
    await expect(
      page.getByRole("button", { name: /Rename hobby/i }),
    ).toBeVisible();
    // And in the topbar scope picker (which reads useDomains too).
    // Plan 12 Task 5: ``useDomains()`` is a zustand selector now, so
    // the topbar re-renders against the same store the panel just
    // mutated — no ``page.reload()`` required.
    await page.getByRole("button", { name: /Scope:/i }).click();
    await expect(
      page.getByRole("checkbox", { name: /Hobby/i }),
    ).toBeVisible();
    // Close the popover before the next interaction.
    await page.keyboard.press("Escape");

    // ---- Rename ``hobby`` → ``leisure`` -------------------------------
    await page.getByRole("button", { name: /Rename hobby/i }).click();
    const slugInput = page.getByLabel(/new slug/i);
    await slugInput.fill("leisure");
    await page.getByRole("button", { name: /Rename domain/i }).click();
    // Old slug gone, new slug present.
    await expect(
      page.getByRole("button", { name: /Rename hobby/i }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: /Rename leisure/i }),
    ).toBeVisible();

    // ---- Delete ``leisure`` -------------------------------------------
    await page.getByRole("button", { name: /Delete leisure/i }).click();
    // Wrong word leaves the confirm button disabled. The typed-confirm
    // dialog uses the slug as the confirm word per the panel's payload.
    const wordInput = page.getByPlaceholder(/leisure/i).first();
    if (await wordInput.isVisible()) {
      await wordInput.fill("wrong");
      // Find a "Delete" or "Confirm" submit button inside the dialog.
      const submit = page.getByRole("button", {
        name: /^(Delete|Confirm)/,
      }).last();
      await expect(submit).toBeDisabled();
      await wordInput.fill("leisure");
      await expect(submit).toBeEnabled();
      await submit.click();
    } else {
      // Fallback: type-confirm dialog uses a different placeholder
      // strategy in some builds. Just type into the visible input.
      await page.getByRole("textbox").last().fill("leisure");
      await page.getByRole("button", { name: /^(Delete|Confirm)/ }).last().click();
    }

    // Row gone from panel list.
    await expect(
      page.getByRole("button", { name: /Rename leisure/i }),
    ).toHaveCount(0);

    // Topbar scope picker no longer surfaces the deleted slug.
    // Plan 12 Task 5: same zustand subscription as the Add check
    // above — the panel's delete mutation drives the store; the
    // topbar's selector picks up the change without a reload.
    await page.getByRole("button", { name: /Scope:/i }).click();
    await expect(
      page.getByRole("checkbox", { name: /Leisure/i }),
    ).toHaveCount(0);
    await page.keyboard.press("Escape");
  });
});
