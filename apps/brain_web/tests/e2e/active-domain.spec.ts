/**
 * Plan 12 Task 10 e2e — active_domain persists across reload (gate 5).
 *
 * Walks the UX completion the Plan 12 Task 8 dropdown ships:
 *
 *   1. Open Settings → Domains, pick ``work`` in the "Default active
 *      domain" dropdown. The select fires ``setActiveDomain("work")``
 *      which routes through ``brain_config_set`` → persistent
 *      ``<vault>/.brain/config.json``.
 *   2. Wait for the success toast (``"Active domain updated."``) so we
 *      know the API round-trip resolved before asserting on disk.
 *   3. Pin on-disk persistence — read ``<vault>/.brain/config.json``
 *      directly. Mirrors the Plan 11 ``persistence.spec.ts`` pattern.
 *      A regression where the dropdown calls the wrong tool (or skips
 *      the API call) fails this assertion.
 *   4. Clear localStorage's ``brain.scopeInitialized.<vault>`` flag
 *      (the per-vault scope-hydration marker Plan 11 D9 introduced)
 *      and reload. With the flag cleared, the topbar's first-mount
 *      hydration effect re-runs against the persisted ``active_domain``
 *      from disk, hydrating ``scope = ["work"]``.
 *   5. Assert the topbar scope chip shows ``"work"``. The chip's text
 *      comes from ``scopeLabel`` in ``topbar.tsx`` (single-domain
 *      branch returns the domain's ``label``, which is the humanised
 *      slug — ``"Work"``).
 *
 * Why we clear ``scopeInitialized`` rather than relying on a clean
 * tab: zustand's ``persist`` middleware writes the topbar's ``scope``
 * to ``brain-app`` localStorage. Without explicitly clearing the
 * per-vault scope-init flag, a re-mount with the existing
 * persisted ``scope=[research]`` would skip the first-mount
 * hydration effect (``scopeInitialized: true`` from the prior run).
 * Clearing the per-vault flag forces the hydration path to re-run and
 * reflect the new ``active_domain``. This is the same condition a
 * fresh-tab/clean-browser visit would land in.
 *
 * The active-domain dropdown sets `Config.active_domain`; the topbar
 * scope chip is per-session (Plan 11 D9 deliberately separated those
 * concepts), so the assertion path is "persist → clear → reload →
 * hydrate". Any future fix that makes the topbar live-bound to
 * ``active_domain`` would simplify this spec; until then this is the
 * canonical post-reload assertion.
 */
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "./fixtures";

test.describe("plan 12 — active_domain Settings UI", () => {
  test("pick work in dropdown → reload → topbar scope chip shows work", async ({
    page,
    seedPath,
  }, testInfo) => {
    testInfo.annotations.push({ type: "vault", description: seedPath });

    // ---- Visit Settings → Domains -------------------------------------
    await page.goto("/settings/domains/");
    // Wait for the panel to hydrate. Pinning on the Rename button proves
    // the per-domain rows have rendered, which means the
    // ``ActiveDomainSelector`` (top of the panel) has also rendered.
    await expect(
      page.getByRole("button", { name: /Rename research/i }),
    ).toBeVisible();

    // ---- Pick ``work`` in the active-domain dropdown -----------------
    // The selector has ``data-testid="active-domain-selector"`` per
    // panel-domains.tsx. ``selectOption`` fires ``onChange``, which
    // triggers ``setActiveDomain("work")`` → ``brain_config_set``.
    const dropdown = page.getByTestId("active-domain-selector");
    await expect(dropdown).toBeVisible();
    await dropdown.selectOption("work");

    // ---- Wait for the success toast ----------------------------------
    // ``"Active domain updated."`` is the lead string from
    // panel-domains.tsx's ``ActiveDomainSelector.onChange``. Toast
    // landing means the API round-trip resolved — disk write is now
    // safe to assert against.
    await expect(page.getByText("Active domain updated.").first()).toBeVisible({
      timeout: 5_000,
    });

    // ---- Pin on-disk persistence -------------------------------------
    const configPath = join(seedPath, ".brain", "config.json");
    expect(
      existsSync(configPath),
      `expected config.json to exist at ${configPath} after the active-domain save`,
    ).toBe(true);
    const persisted = JSON.parse(readFileSync(configPath, "utf-8")) as {
      active_domain?: string;
    };
    expect(persisted.active_domain).toBe("work");

    // ---- Clear scope-init flag + reload ------------------------------
    // The per-vault localStorage flag (``brain.scopeInitialized.<vault>``)
    // gates the topbar's first-mount hydration effect. Clearing it
    // forces a fresh hydration on the next render so the topbar reads
    // the persisted ``active_domain`` from
    // ``brain_list_domains.active_domain``. Equivalent to a clean tab.
    //
    // Also clear the ``brain-app`` zustand-persist record so the
    // previously persisted ``scope = ["research"]`` doesn't bleed in
    // before the hydration effect runs.
    await page.evaluate(() => {
      window.localStorage.clear();
    });
    await page.reload();

    // ---- Assert topbar scope chip shows ``Work`` ---------------------
    // ``scopeLabel`` returns the domain's ``label`` (the humanised
    // slug) when ``scope.length === 1``. Match the aria-label rather
    // than the inner text since the chip wraps the label in a span
    // alongside the icon — aria-label is the stable target.
    //
    // Use a generous timeout: first-mount hydration kicks off after
    // ``brain_list_domains`` lands AND ``vaultPath`` resolves from the
    // bootstrap fetch, both of which are network-bound on the e2e
    // backend.
    await expect(
      page.locator("[aria-label='Scope: Work']"),
    ).toBeVisible({ timeout: 10_000 });
  });
});
