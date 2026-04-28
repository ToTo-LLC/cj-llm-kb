/**
 * Plan 12 Task 10 e2e — cross-domain confirmation modal trigger + acknowledgment lifecycle.
 *
 * Walks the two new gates Plan 12 Task 9 ships:
 *
 * **Gate 6 — trigger (parametrized).** The modal fires only when the
 * scope contains ≥2 domains AND ≥1 of them is in
 * ``Config.privacy_railed`` (D7). Single-domain railed access does NOT
 * fire (Plan 11 D11 already requires explicit slug inclusion for
 * railed access; that opt-in IS the consent). Pure cross-domain
 * without rails does NOT fire either. Three sub-cases:
 *
 *   1. ``scope=[research, personal]`` — modal visible.
 *   2. ``scope=[research, work]`` — no modal.
 *   3. ``scope=[personal]`` — no modal.
 *
 * **Gate 7 — acknowledgment lifecycle.** Click "Continue" with "Don't
 * show this again" checked → reload → re-trigger same scope → no
 * modal (``Config.cross_domain_warning_acknowledged === true``).
 * Toggle "Show cross-domain warning" ON in Settings → Domains →
 * re-trigger → modal returns.
 *
 * The trigger surface is the chat composer's send: when ``threadId``
 * is ``null`` AND ``shouldFireCrossDomainModal(scope, privacyRailed,
 * acknowledged)`` returns true, the composer parks the message via
 * ``pendingSendRef`` and opens the modal. We drive scope via the
 * zustand-persist localStorage key (``brain-app``) so we don't have to
 * navigate the topbar's scope picker just to set up state — the
 * picker UI is exercised by the dedicated ``domains.spec.ts``.
 *
 * BRAIN_ALLOWED_DOMAINS for the e2e backend is ``research,work``, but
 * ``Config.domains`` defaults to ``["research", "work", "personal"]``
 * — the cross-domain modal trigger reads ``privacy_railed`` from
 * ``Config`` (default ``["personal"]``), so ``personal`` lights up
 * the rail check even though it's not in the allowed-domains env.
 */
import { expect, test, type Page } from "./fixtures";

/**
 * Set the persisted ``brain-app`` zustand-persist record so the chat
 * screen renders with the desired scope on the very first paint. The
 * record is written BEFORE ``page.goto`` so React's first render reads
 * the rehydrated values instead of the empty default.
 *
 * Other persisted fields (theme, density, mode, railOpen) get sane
 * defaults so the Settings → Domains and chat shells render without
 * surprises.
 */
async function seedScope(page: Page, scope: string[]): Promise<void> {
  await page.addInitScript((s) => {
    const payload = {
      state: {
        theme: "dark",
        density: "comfortable",
        mode: "ask",
        scope: s,
        railOpen: true,
      },
      version: 0,
    };
    window.localStorage.setItem("brain-app", JSON.stringify(payload));
  }, scope);
}

/** Seed a per-vault scopeInitialized flag. With this set, the topbar
 *  hydration effect skips on first mount and the persisted ``scope``
 *  in ``brain-app`` is what the chat screen renders against. We seed
 *  ``"true"`` per Plan 11 D9's serialization (any truthy stored
 *  value → flag is set). The vaultPath comes from
 *  ``readBootstrap()`` at runtime — read via /api/bootstrap, which
 *  returns the BRAIN_VAULT_ROOT we know already.
 */
async function seedScopeInitialized(page: Page, vaultPath: string): Promise<void> {
  await page.addInitScript((p) => {
    window.localStorage.setItem(`brain.scopeInitialized.${p}`, "true");
  }, vaultPath);
}

async function seedBrainMd(seedPath: string): Promise<void> {
  // Same shape as chat-turn.spec.ts — drop a BRAIN.md so the root
  // redirect doesn't bounce a thread-route fetch through the setup
  // wizard.
  const fs = await import("node:fs/promises");
  const path = await import("node:path");
  await fs.writeFile(
    path.join(seedPath, "BRAIN.md"),
    "# BRAIN\n\nYou are brain. Maintain this vault carefully.\n",
    "utf-8",
  );
}

async function attemptSend(page: Page, message: string): Promise<void> {
  const composer = page.getByRole("textbox", { name: "Message brain" });
  await expect(composer).toBeVisible();
  await composer.fill(message);
  await page.getByRole("button", { name: "Send" }).click();
}

test.describe("plan 12 — cross-domain confirmation modal", () => {
  test.beforeEach(async ({ seedPath }) => {
    await seedBrainMd(seedPath);
  });

  test("Gate 6a — scope=[research, personal] triggers the modal", async ({
    page,
    seedPath,
  }, testInfo) => {
    testInfo.annotations.push({ type: "vault", description: seedPath });

    await seedScope(page, ["research", "personal"]);
    await seedScopeInitialized(page, seedPath);
    await page.goto("/chat");
    await page.waitForLoadState("networkidle");

    await attemptSend(page, "test cross-domain message");

    // Modal fires — assert by the Continue button's testid.
    await expect(
      page.getByTestId("cross-domain-continue-button"),
    ).toBeVisible({ timeout: 5_000 });
  });

  test("Gate 6b — scope=[research, work] does NOT trigger the modal", async ({
    page,
    seedPath,
  }, testInfo) => {
    testInfo.annotations.push({ type: "vault", description: seedPath });

    await seedScope(page, ["research", "work"]);
    await seedScopeInitialized(page, seedPath);
    await page.goto("/chat");
    await page.waitForLoadState("networkidle");

    await attemptSend(page, "test cross-domain no-rail");

    // Wait a bit to give the trigger a fair chance to fire (it's
    // synchronous on send but we want to be sure no async render
    // surfaces it). Then assert the modal is absent.
    await page.waitForTimeout(500);
    await expect(
      page.getByTestId("cross-domain-continue-button"),
    ).toHaveCount(0);
  });

  test("Gate 6c — scope=[personal] (single-domain rail) does NOT trigger the modal", async ({
    page,
    seedPath,
  }, testInfo) => {
    testInfo.annotations.push({ type: "vault", description: seedPath });

    await seedScope(page, ["personal"]);
    await seedScopeInitialized(page, seedPath);
    await page.goto("/chat");
    await page.waitForLoadState("networkidle");

    await attemptSend(page, "test single-domain rail");

    await page.waitForTimeout(500);
    await expect(
      page.getByTestId("cross-domain-continue-button"),
    ).toHaveCount(0);
  });

  test("Gate 7 — Don't show again → reload skips modal; Settings toggle re-enables", async ({
    page,
    seedPath,
  }, testInfo) => {
    testInfo.annotations.push({ type: "vault", description: seedPath });

    // ---- Step 1: trigger the modal with Don't-show-again checked --
    await seedScope(page, ["research", "personal"]);
    await seedScopeInitialized(page, seedPath);
    await page.goto("/chat");
    await page.waitForLoadState("networkidle");

    await attemptSend(page, "first cross-domain message");
    await expect(
      page.getByTestId("cross-domain-continue-button"),
    ).toBeVisible({ timeout: 5_000 });

    // Tick "Don't show this again" + Continue.
    await page.getByTestId("cross-domain-dont-show-checkbox").click();
    await page.getByTestId("cross-domain-continue-button").click();

    // Modal closes after Continue.
    await expect(
      page.getByTestId("cross-domain-continue-button"),
    ).toHaveCount(0);

    // Wait briefly for the setCrossDomainWarningAcknowledged API call
    // to land on disk before navigating away — the chat-screen handler
    // awaits the persistence before dispatching the send.
    await page.waitForTimeout(500);

    // Confirm on disk that the ack flag landed (loadbearing for the
    // next reload path — without it, the ack hook would re-fire the
    // modal and Step 3 would fail for the wrong reason).
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const configPath = path.join(seedPath, ".brain", "config.json");
    const persisted = JSON.parse(
      await fs.readFile(configPath, "utf-8"),
    ) as { cross_domain_warning_acknowledged?: boolean };
    expect(persisted.cross_domain_warning_acknowledged).toBe(true);

    // ---- Step 2: reload + retry the same scope → modal absent ----
    // Re-seed ``brain-app`` (the URL navigation below clears it via
    // localStorage.clear()) and the per-vault scope-init flag so the
    // chat screen renders with scope=[research, personal] again on
    // the next visit.
    await page.evaluate(() => {
      window.localStorage.clear();
    });
    await seedScope(page, ["research", "personal"]);
    await seedScopeInitialized(page, seedPath);
    await page.goto("/chat");
    await page.waitForLoadState("networkidle");

    await attemptSend(page, "second cross-domain message — modal should be quiet");
    await page.waitForTimeout(500);
    await expect(
      page.getByTestId("cross-domain-continue-button"),
    ).toHaveCount(0);

    // ---- Step 3: toggle "Show cross-domain warning" ON in Settings,
    //              retry → modal returns ----
    await page.goto("/settings/domains/");
    await expect(
      page.getByRole("button", { name: /Rename research/i }),
    ).toBeVisible();

    // The toggle is a button-shaped Radix Switch; ``data-testid`` is
    // ``cross-domain-warning-toggle`` per panel-domains.tsx. UI
    // sense is INVERTED relative to the underlying field (toggle ON
    // = show warning = ack=false). After the previous step the
    // toggle is OFF (ack=true); clicking it flips to ON (ack=false).
    const warningToggle = page.getByTestId("cross-domain-warning-toggle");
    await expect(warningToggle).toBeVisible();
    await warningToggle.click();

    // Wait for the success toast that confirms the API round-trip
    // landed before reloading + retrying.
    await expect(
      page.getByText("Cross-domain warning on.").first(),
    ).toBeVisible({ timeout: 5_000 });

    // Confirm on disk that the ack flag flipped back to false.
    const persisted2 = JSON.parse(
      await fs.readFile(configPath, "utf-8"),
    ) as { cross_domain_warning_acknowledged?: boolean };
    expect(persisted2.cross_domain_warning_acknowledged).toBe(false);

    // Re-seed scope state + visit chat; modal should fire again.
    await page.evaluate(() => {
      window.localStorage.clear();
    });
    await seedScope(page, ["research", "personal"]);
    await seedScopeInitialized(page, seedPath);
    await page.goto("/chat");
    await page.waitForLoadState("networkidle");

    await attemptSend(page, "third cross-domain message — modal should fire again");
    await expect(
      page.getByTestId("cross-domain-continue-button"),
    ).toBeVisible({ timeout: 5_000 });
  });
});
