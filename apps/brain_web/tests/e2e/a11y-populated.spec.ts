/**
 * Plan 14 Task 3 — populated-state a11y dialog sweep (C2.a).
 *
 * The empty-state ``a11y.spec.ts`` only loads top-level routes against a
 * vault seeded with BRAIN.md and a welcome note; axe-core only flags
 * what's actually rendered, so dialogs (which mount conditionally) never
 * came under scan. Plan 13 Task 6 review #2 + #7 surfaced the gap —
 * Plan 14 D5 + D6 + D9 (locked 2026-04-29) close it by adding a
 * dedicated populated-state spec that opens each dialog in turn and runs
 * the same hard-fail axe sweep the empty-state spec runs.
 *
 * Dialog inventory (Task 3 dispatch text, 8 nominal cases):
 *
 *   ✅ rename-domain dialog          (Settings → Domains → Rename)
 *   ✅ delete-domain dialog          (Settings → Domains → Delete; typed-confirm)
 *   ✅ fork-thread dialog            (Chat sub-header → Fork)
 *   ⏭ repair-config dialog          NOT IMPLEMENTED — no UI surface today;
 *                                    deferred to Plan 15 candidate scope.
 *                                    grep "repair_config|repairConfig" in
 *                                    apps/brain_web/src/ returns empty.
 *   ✅ backup-restore dialog        (Settings → Backups → Restore; typed-confirm)
 *   ✅ cross-domain modal           (chat send with scope=[research, personal])
 *   ✅ patch-card edit dialog       (Pending → select patch → "Edit, then approve")
 *   ⏭ autonomy modal               NOT IMPLEMENTED — autonomy surfaces are
 *                                    Switch toggles (inbox + pending screens),
 *                                    no modal exists today. Deferred to Plan 15.
 *
 * Six implementable cases land here. The two deferrals are filed as
 * Plan 15 candidates per the per-task review escalation policy: "if a
 * dialog doesn't have a UI surface, file as Plan 15 candidate; reduce
 * to 7 or fewer cases."
 *
 * **Hard-fail discipline.** ``DISABLED_RULES = []`` (mirrored from
 * fixtures.ts); ``checkA11y()`` asserts ``violations.toEqual([])`` with
 * no ``expect.soft``. Same gate as ``a11y.spec.ts``.
 *
 * **Lifecycle gotchas.**
 * - The dialog mount is portal-rooted (Radix); we wait on the dialog's
 *   testid / button to be visible BEFORE running axe to avoid scanning
 *   a half-mounted tree.
 * - Backups + patches are seeded via the same per-run-token API path
 *   ``patch-approval.spec.ts`` uses — the FakeLLMProvider is canned so
 *   no LLM round-trip is required.
 * - The fork case goes through ``/chat/<threadId>`` directly so the
 *   chat-sub-header Fork button is enabled (depends on
 *   ``activeThreadId`` being set, which the URL effect handles).
 * - The cross-domain case mirrors ``cross-domain-modal.spec.ts``'s
 *   localStorage-seeded scope pattern.
 */
import { type Page } from "@playwright/test";

import { expect, test } from "./fixtures";

/** Read the per-run brain_api token from disk. Same pattern as
 *  patch-approval.spec.ts. */
async function readApiToken(seedPath: string): Promise<string> {
  const fs = await import("node:fs/promises");
  const path = await import("node:path");
  const tokenPath = path.join(seedPath, ".brain", "run", "api-secret.txt");
  return (await fs.readFile(tokenPath, "utf-8")).trim();
}

/** POST to a brain_api tool endpoint with the per-run token. */
async function callTool(
  page: Page,
  token: string,
  tool: string,
  body: Record<string, unknown>,
): Promise<unknown> {
  const res = await page.request.post(
    `http://127.0.0.1:4317/api/tools/${tool}`,
    {
      headers: {
        "X-Brain-Token": token,
        "Content-Type": "application/json",
        Origin: "http://127.0.0.1:4317",
      },
      data: body,
    },
  );
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json();
}

/** Seed BRAIN.md so the root redirect doesn't bounce to /setup — same
 *  pattern as a11y.spec.ts + chat-turn.spec.ts. */
async function seedBrainMd(seedPath: string): Promise<void> {
  const fs = await import("node:fs/promises");
  const path = await import("node:path");
  await fs.writeFile(
    path.join(seedPath, "BRAIN.md"),
    "# BRAIN\n\nYou are brain. Maintain this vault carefully.\n",
    "utf-8",
  );
}

/** Pre-seed the persisted scope so /chat renders against a chosen
 *  scope on first paint (cross-domain modal trigger requires this). */
async function seedScope(page: Page, scope: string[]): Promise<void> {
  await page.addInitScript((s: string[]) => {
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

/** Mark scope as initialized so the topbar hydration effect skips on
 *  first mount and the persisted scope is what the chat screen renders
 *  against. Same pattern as cross-domain-modal.spec.ts. */
async function seedScopeInitialized(page: Page, vaultPath: string): Promise<void> {
  await page.addInitScript((p: string) => {
    window.localStorage.setItem(`brain.scopeInitialized.${p}`, "true");
  }, vaultPath);
}

test.describe("a11y — populated-state dialog sweep", () => {
  test.beforeEach(async ({ seedPath }) => {
    await seedBrainMd(seedPath);
  });

  // ----------------------------------------------------------------
  // Case 1: rename-domain dialog
  //
  // Settings → Domains → Rename row button → modal mounts.
  // ``research`` is one of the two BRAIN_ALLOWED_DOMAINS the e2e
  // backend seeds; the rename button is rendered for every non-
  // protected domain. ``personal`` is delete-protected upstream so we
  // pick research for rename.
  // ----------------------------------------------------------------
  test("rename-domain dialog has 0 violations", async ({ page, checkA11y }) => {
    await page.goto("/settings/domains/");
    await page.waitForLoadState("networkidle");

    const renameButton = page.getByRole("button", { name: /^Rename research$/i });
    await expect(renameButton).toBeVisible();
    await renameButton.click();

    // Modal renders the heading "Rename and rewrite references." per
    // rename-domain-dialog.tsx.
    await expect(
      page.getByRole("heading", { name: /Rename and rewrite references/i }),
    ).toBeVisible();
    // Wait one extra beat so the modal's autofocus + transition settle
    // before axe scans (otherwise focus-related rules can flake).
    await page.waitForTimeout(200);

    await checkA11y(page, "dialog:rename-domain");
  });

  // ----------------------------------------------------------------
  // Case 2: delete-domain (typed-confirm) dialog
  //
  // Settings → Domains → Delete row button → typed-confirm modal.
  // ``work`` is delete-eligible (not in PROTECTED_DOMAINS); the
  // confirm word is the slug itself per panel-domains.tsx.
  // ----------------------------------------------------------------
  test("delete-domain (typed-confirm) dialog has 0 violations", async ({
    page,
    checkA11y,
  }) => {
    await page.goto("/settings/domains/");
    await page.waitForLoadState("networkidle");

    const deleteButton = page.getByRole("button", { name: /^Delete work$/i });
    await expect(deleteButton).toBeVisible();
    await deleteButton.click();

    // Typed-confirm modal heading is the dialog title — "Delete work?"
    // for this domain.
    await expect(
      page.getByRole("heading", { name: /Delete work\?/i }),
    ).toBeVisible();
    await page.waitForTimeout(200);

    await checkA11y(page, "dialog:delete-domain-typed-confirm");
  });

  // ----------------------------------------------------------------
  // Case 3: fork-thread dialog
  //
  // Drive a real chat turn first so a thread exists server-side, then
  // click the Fork button in chat-sub-header. ``activeThreadId`` is
  // populated by the /chat/<id> URL effect, so the Fork button is
  // enabled even before the FakeLLM round-trip completes.
  // ----------------------------------------------------------------
  test("fork-thread dialog has 0 violations", async ({ page, checkA11y }) => {
    const threadId = `e2e-a11y-fork-${Date.now()}`;
    await page.goto(`/chat/${threadId}`);
    await page.waitForLoadState("networkidle");

    // Send a turn so the thread is persisted server-side; Fork would
    // otherwise no-op silently if the thread didn't exist (the dialog
    // itself opens fine, but driving a real turn matches production
    // shape — populated state, not just a URL).
    await page.getByRole("textbox", { name: "Message brain" }).fill("hello brain");
    await page.getByRole("button", { name: "Send" }).click();
    // Wait for the FakeLLM canned reply to render (chat-turn.spec.ts
    // shape — using 'data-role=brain' as the marker).
    await expect(page.locator('[data-role="brain"]').first()).toContainText(
      "Hello from FakeLLM",
      { timeout: 20_000 },
    );

    // Now open the Fork dialog from the sub-header. Disambiguate from
    // the per-message Fork button (msg-actions.tsx) which uses the same
    // label — target by the sub-header's ``title="Fork"`` attribute via
    // its enclosing button. The chat sub-header's button has both
    // aria-label="Fork" AND title="Fork"; we use ``getByTitle`` to pick
    // exactly that one (msg-actions has no title attribute).
    await page.getByTitle("Fork", { exact: true }).click();

    // The fork dialog heading is "Start a fresh thread from this point."
    await expect(
      page.getByRole("heading", { name: /Start a fresh thread/i }),
    ).toBeVisible();
    await page.waitForTimeout(200);

    await checkA11y(page, "dialog:fork-thread");
  });

  // ----------------------------------------------------------------
  // Case 4: backup-restore (typed-confirm) dialog
  //
  // Seed a backup via the brain_backup_create tool, then navigate to
  // /settings/backups and click Restore on the listed row. The
  // typed-confirm word is "RESTORE".
  // ----------------------------------------------------------------
  test("backup-restore (typed-confirm) dialog has 0 violations", async ({
    page,
    seedPath,
    checkA11y,
  }) => {
    const token = await readApiToken(seedPath);
    const created = (await callTool(page, token, "brain_backup_create", {
      trigger: "manual",
    })) as { data?: { backup_id?: string } };
    const backupId = created.data?.backup_id;
    expect(backupId).toBeTruthy();

    await page.goto("/settings/backups/");
    await page.waitForLoadState("networkidle");

    // Restore button is per-row aria-label="Restore <backup_id>".
    const restoreButton = page.getByRole("button", {
      name: new RegExp(`^Restore ${backupId}$`, "i"),
    });
    await expect(restoreButton).toBeVisible();
    await restoreButton.click();

    // Typed-confirm modal heading is "Restore backup <id>?".
    await expect(
      page.getByRole("heading", { name: /Restore backup .+\?/i }),
    ).toBeVisible();
    await page.waitForTimeout(200);

    await checkA11y(page, "dialog:backup-restore-typed-confirm");
  });

  // ----------------------------------------------------------------
  // Case 5: cross-domain modal
  //
  // Mirror cross-domain-modal.spec.ts Gate 6a: scope=[research,
  // personal] + send → modal fires. Personal is in Config.privacy_railed
  // by default, so the rail check + 2-domain-scope condition both light
  // up. The modal is the Plan 12 Task 9 component; testid =
  // "cross-domain-continue-button".
  // ----------------------------------------------------------------
  test("cross-domain modal has 0 violations", async ({
    page,
    seedPath,
    checkA11y,
  }) => {
    await seedScope(page, ["research", "personal"]);
    await seedScopeInitialized(page, seedPath);
    await page.goto("/chat");
    await page.waitForLoadState("networkidle");

    const composer = page.getByRole("textbox", { name: "Message brain" });
    await expect(composer).toBeVisible();
    await composer.fill("a11y populated-state cross-domain trigger");
    await page.getByRole("button", { name: "Send" }).click();

    await expect(
      page.getByTestId("cross-domain-continue-button"),
    ).toBeVisible({ timeout: 5_000 });
    await page.waitForTimeout(200);

    await checkA11y(page, "dialog:cross-domain-modal");
  });

  // ----------------------------------------------------------------
  // Case 6: patch-card edit (edit-approve) dialog
  //
  // Seed a pending patch via brain_propose_note, navigate to /pending,
  // select it, then click the detail-pane "Edit, then approve" button
  // which routes through dialogs-store with kind="edit-approve". The
  // inline patch-card "Edit" button just selects the row — the actual
  // dialog opens from PatchDetail. (See patch-detail.tsx:263.)
  // ----------------------------------------------------------------
  test("patch-card edit (edit-approve) dialog has 0 violations", async ({
    page,
    seedPath,
    checkA11y,
  }) => {
    const token = await readApiToken(seedPath);
    const stamp = Date.now();
    const targetPath = `work/notes/a11y-edit-${stamp}.md`;
    const seed = (await callTool(page, token, "brain_propose_note", {
      path: targetPath,
      content: `# A11y populated-state edit\n\nSeeded at ${stamp}.\n`,
      reason: "plan 14 task 3 a11y populated-state — edit dialog",
    })) as { data?: { patch_id?: string } };
    const patchId = seed.data?.patch_id;
    expect(patchId).toBeTruthy();

    await page.goto("/pending");
    await page.waitForLoadState("networkidle");

    // Select the seeded card so PatchDetail mounts.
    const card = page.locator(`#patch-card-${patchId}`);
    await expect(card).toBeVisible();
    await card.click();

    // The detail-pane "Edit, then approve" button opens the
    // edit-approve modal.
    const editButton = page.getByRole("button", { name: /Edit, then approve/i });
    await expect(editButton).toBeVisible();
    await editButton.click();

    // Edit-approve dialog footer renders "Save & approve" — wait on
    // that as the stable mount marker. Use a regex to tolerate the
    // ampersand-vs-amp HTML decode boundary across browsers.
    await expect(
      page.getByRole("button", { name: /Save .* approve/i }),
    ).toBeVisible();
    await page.waitForTimeout(200);

    await checkA11y(page, "dialog:patch-card-edit-approve");

    // Cleanup: reject the seeded patch so it doesn't pollute /pending
    // for the empty-state ``a11y.spec.ts`` cases (which run after this
    // file alphabetically and would otherwise see leftover patch-card
    // markup with the nested-interactive Approve/Edit/Reject buttons).
    // Plan 14 D9 task review: "Anti-regression. Confirm all existing
    // a11y.spec.ts cases still pass (no shared-state pollution)."
    await callTool(page, token, "brain_reject_patch", {
      patch_id: patchId,
      reason: "a11y populated-state spec cleanup",
    });
  });
});
