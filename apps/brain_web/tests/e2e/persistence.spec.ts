/**
 * Plan 11 Task 10 e2e — domain-override persistence to <vault>/.brain/config.json.
 *
 * The Plan 11 demo gate 8 spec walks the persistent-config story
 * end-to-end through the live UI:
 *
 *   1. **Round-trip a domain override to disk.** Open Settings → Domains,
 *      expand ``research``, set ``temperature = 0.9`` via the override form.
 *      The backend write path is ``brain_config_set`` →
 *      ``persist_config_or_revert`` → ``save_config()`` writing
 *      ``<vault>/.brain/config.json``. We pin the on-disk artifact via
 *      Node ``fs`` so a regression that loses the persisted bytes
 *      (e.g., the broken brain_api Config wiring Task 7 caught) fails
 *      this test.
 *
 *   2. **Persistence survives a full-page reload + cleared localStorage.**
 *      We clear localStorage between visits to mirror "fresh tab" /
 *      "browser restart" semantics, then re-read the on-disk
 *      ``config.json`` to confirm the override didn't get clobbered by
 *      lifecycle events (config_set called with stale state, lifespan
 *      overwrite, etc.). Toast text is ``Override saved.`` from
 *      ``domain-override-form.tsx::saveField``.
 *
 * Why we don't assert the FIELD VALUE re-renders post-reload: today's
 * ``brain_config_get`` snapshots ``Config()`` defaults rather than
 * reading ``ctx.config`` (Plan 11 lesson #6 in tasks/lessons.md;
 * filed for Plan 12 in tasks/todo.md). The Settings UI therefore
 * shows the empty default after a reload even though the disk file
 * still has the saved override. The write-path assertions below are
 * the load-bearing persistence guarantee Plan 11 ships; the read-path
 * UI fix lands in Plan 12.
 *
 * The spec runs against the same single-port brain_api + static UI bundle
 * as the rest of the e2e suite (see playwright.config.ts).
 * ``BRAIN_ALLOWED_DOMAINS`` is ``"research,work"`` so ``research`` is a
 * safe target slug.
 */
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "./fixtures";

test.describe("plan 11 — persistent config", () => {
  test("override on research persists across reload + lands in config.json", async ({
    page,
    seedPath,
  }, testInfo) => {
    testInfo.annotations.push({ type: "vault", description: seedPath });

    // ---- Visit Settings → Domains ------------------------------------
    await page.goto("/settings/domains/");
    // Wait for the panel to hydrate before interacting — without this
    // the rename-button locator below races the React mount.
    await expect(
      page.getByRole("button", { name: /Rename research/i }),
    ).toBeVisible();

    // Expand the research row to reveal the DomainOverrideForm.
    await page
      .getByRole("button", { name: /Expand research overrides/i })
      .click();
    const overrideForm = page.getByTestId("domain-override-form-research");
    await expect(overrideForm).toBeVisible();

    // ---- Edit temperature override ----------------------------------
    // The form id is ``override-${slug}-temperature`` — match by id
    // rather than label text because the form has multiple "Temperature"
    // labels on the page if the user expanded multiple rows. Filling
    // + blurring is what triggers the saveTemperature() round-trip in
    // ``domain-override-form.tsx``.
    const tempField = page.locator("#override-research-temperature");
    await expect(tempField).toBeVisible();
    await tempField.fill("0.9");
    // The save fires on blur — tab away from the field.
    await tempField.blur();

    // Wait for the success toast surfaced by ``configSet``'s catch /
    // pushToast path. ``Override saved.`` is the lead string from
    // domain-override-form.tsx::saveField.
    await expect(page.getByText("Override saved.").first()).toBeVisible({
      timeout: 5_000,
    });

    // ---- Pin on-disk persistence ------------------------------------
    // Read ``<vault>/.brain/config.json`` directly. Plan 11 D4
    // (persisted-field whitelist) means this file MUST exist after a
    // single mutation tool call; the Plan 11 Task 7 brain_api wiring
    // ensures the lifespan threads Config through so save_config()
    // actually fires. Failing this assertion is the reproducer the
    // browser-in-the-loop verification of Task 7 was designed to catch.
    const configPath = join(seedPath, ".brain", "config.json");
    expect(
      existsSync(configPath),
      `expected config.json to exist at ${configPath} after the override save`,
    ).toBe(true);
    const persisted = JSON.parse(readFileSync(configPath, "utf-8")) as {
      domain_overrides?: Record<string, { temperature?: number | null }>;
    };
    expect(persisted.domain_overrides).toBeDefined();
    expect(persisted.domain_overrides!.research).toMatchObject({
      temperature: 0.9,
    });

    // ---- Reload + assert disk persistence survives ------------------
    // Clear localStorage to simulate a fresh tab — this is the
    // restart-equivalent mentioned in the plan-11 demo gate. We re-read
    // the on-disk config.json after the reload to confirm the override
    // bytes are still present; the lifespan re-runs (load_config →
    // build_app_context with the same Config), and a regression that
    // overwrote the file on boot (e.g. lifespan calling save_config
    // with a fresh defaults Config) would surface here.
    await page.evaluate(() => window.localStorage.clear());
    await page.reload();
    await expect(
      page.getByRole("button", { name: /Rename research/i }),
    ).toBeVisible();

    expect(
      existsSync(configPath),
      `config.json went missing after reload at ${configPath}`,
    ).toBe(true);
    const reloaded = JSON.parse(readFileSync(configPath, "utf-8")) as {
      domain_overrides?: Record<string, { temperature?: number | null }>;
    };
    expect(reloaded.domain_overrides).toBeDefined();
    expect(reloaded.domain_overrides!.research).toMatchObject({
      temperature: 0.9,
    });

    // KNOWN LIMITATION (Plan 12 follow-up): ``brain_config_get`` snapshots
    // ``Config()`` defaults rather than reading the live ``ctx.config``,
    // so the temperature input renders empty on reload even though the
    // disk file is correct. The disk-state assertion above is the
    // load-bearing persistence guarantee Plan 11 ships; the UI re-hydration
    // is filed in tasks/todo.md as a Plan 12 candidate.
  });
});
