/**
 * Plan 14 Task 3 + Task 4 — populated-state a11y sweep
 * (C2.a dialogs + C2.b menus + overlays).
 * Plan 16 Task 11 — populated-state additions (D11): file-preview
 * overlay, WikilinkHover tooltip, per-message Fork dialog.
 *
 * **State-cleanup contract (Plan 16 Task 20 / D20).** Every test in this
 * file MUST leave the vault in the same state it found it. Playwright runs
 * ``workers: 1`` + ``fullyParallel: false`` against a single shared
 * ``BRAIN_VAULT_ROOT`` (see ``playwright.config.ts``); any seeded patch,
 * created backup, persisted thread, or hand-written file would otherwise
 * leak into sibling specs (``a11y.spec.ts``, ``patch-approval.spec.ts``,
 * ``persistence.spec.ts``, etc.) that observe the vault inventory.
 *
 * Convention: state-mutating tests register a cleanup callback via
 * ``registerCleanup(...)`` immediately after the mutation succeeds.
 * The suite-level ``test.afterEach`` drains the queue in reverse order
 * (LIFO) and runs each callback even if the test body's assertions
 * failed — this is the load-bearing property the historical
 * "cleanup-at-end-of-test-body" idiom (e.g., the original Case 6
 * ``brain_reject_patch`` tail) silently failed to provide. Non-mutating
 * tests register nothing and pay zero cost.
 *
 * The empty-state ``a11y.spec.ts`` only loads top-level routes against a
 * vault seeded with BRAIN.md and a welcome note; axe-core only flags
 * what's actually rendered, so dialogs (which mount conditionally) never
 * came under scan. Plan 13 Task 6 review #2 + #7 surfaced the gap —
 * Plan 14 D5 + D6 + D9 (locked 2026-04-29) close it by adding a
 * dedicated populated-state spec that opens each dialog / menu / overlay
 * in turn and runs the same hard-fail axe sweep the empty-state spec
 * runs.
 *
 * Dialog inventory (Task 3 dispatch text, 8 nominal cases):
 *
 *   ✅ rename-domain dialog          (Settings → Domains → Rename)
 *   ✅ delete-domain dialog          (Settings → Domains → Delete; typed-confirm)
 *   ✅ fork-thread dialog            (Chat sub-header → Fork)
 *   ✅ repair-config dialog          (Settings → General → Repair config;
 *                                     SCAFFOLD per Plan 16 Task 9 / D9. Full
 *                                     UI lands at Plan 16 Task 33.)
 *   ✅ backup-restore dialog        (Settings → Backups → Restore; typed-confirm)
 *   ✅ cross-domain modal           (chat send with scope=[research, personal])
 *   ✅ patch-card edit dialog       (Pending → select patch → "Edit, then approve")
 *   ✅ autonomy modal               (Settings → General → Configure autonomy;
 *                                     SCAFFOLD per Plan 16 Task 10 / D10. Full
 *                                     per-domain UI lands at Plan 16 Task 40.)
 *   ✅ file-preview overlay         (Browse → per-row Quick preview;
 *                                     Plan 16 Task 11 / D11 — promotes the
 *                                     SearchOverlay deviation below to a
 *                                     dedicated populated-state surface.)
 *   ✅ WikilinkHover tooltip        (Browse → focus a wikilink in the
 *                                     Reader; Plan 16 Task 11 / D11 —
 *                                     ``role="tooltip"`` + stable id +
 *                                     ``aria-describedby`` on the trigger.)
 *   ✅ per-message Fork dialog      (Chat → assistant bubble → Fork
 *                                     from this message; Plan 16 Task 11
 *                                     / D11. Same ``<ForkDialog />`` as
 *                                     Case 3 — only the trigger point
 *                                     and aria-label differ.)
 *
 * Ten implementable dialog cases land here (six since Plan 14, plus the
 * Plan 16 Task 9 repair-config scaffold, plus Plan 16 Task 10 autonomy
 * scaffold, plus the Plan 16 Task 11 trio). The remaining deferral is
 * filed for follow-up plans per the per-task review escalation policy.
 *
 * Menu + overlay inventory (Task 4 dispatch text, 5 nominal cases):
 *
 *   ✅ topbar scope picker dropdown  (Topbar → click scope chip → Radix Popover)
 *   ✅ Settings tabs walk            (visit all 8 panels in one populated test)
 *   ✅ search overlay                (⌘K — historical "file-preview overlay"
 *                                     analogue. Plan 16 Task 11 / D11 lands
 *                                     a dedicated overlay; this case stays
 *                                     for ⌘K coverage on its own merits.)
 *   ✅ drop-zone overlay             (synthetic dragenter with Files-typed
 *                                     DataTransfer flips
 *                                     ``draggingFile`` → DropOverlay
 *                                     reveals)
 *   ✅ toast notifications           (Settings → Backups → "Back up now"
 *                                     fires a real success toast via
 *                                     ``pushToast``)
 *
 * Five Task 4 cases land here. No deferrals.
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
 * - The drop-overlay case dispatches a real ``dragenter`` with
 *   ``dataTransfer.types`` containing ``"Files"`` — production-shape
 *   per ``app-shell.tsx``'s ``onDragEnter`` handler.
 */
import { type Page } from "@playwright/test";

import { expect, test } from "./fixtures";
import { waitForAnimationsToFinish, waitForToolResponse } from "./_helpers";

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
  // Plan 16 Task 20 (D20): per-test cleanup queue. Mutating tests push a
  // callback here immediately after the mutation succeeds; afterEach
  // drains it in LIFO order so cleanup runs even if a later assertion
  // throws. The list is reset per test by afterEach itself; beforeEach
  // does not need to clear it because afterEach has the last word.
  let cleanupTasks: Array<() => Promise<void>> = [];
  const registerCleanup = (fn: () => Promise<void>): void => {
    cleanupTasks.push(fn);
  };

  test.beforeEach(async ({ seedPath }) => {
    await seedBrainMd(seedPath);
  });

  test.afterEach(async () => {
    // LIFO drain — cleans up the last mutation first. Errors are caught
    // and logged so one cleanup failure doesn't mask others or mark the
    // test as failed (the test's own assertions are the source of
    // truth; cleanup is best-effort housekeeping).
    const tasks = cleanupTasks.slice().reverse();
    cleanupTasks = [];
    for (const task of tasks) {
      try {
        await task();
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn("[a11y-populated cleanup] task failed:", err);
      }
    }
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
    // Plan 16 Task 19 (D19): wait for Radix's fade-in / zoom-in
    // animations to reach ``playState=finished`` rather than sleeping a
    // fixed 200ms. axe-core's color-contrast rule reads computed
    // opacity; mid-animation the dialog renders through low-opacity
    // intermediate styles that fail contrast, so the wait is
    // load-bearing — replacing the timeout with a positive-signal poll
    // on the Web Animations API.
    await waitForAnimationsToFinish(page, "[role=dialog]");

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
    // Plan 16 Task 19 (D19): wait for Radix's fade-in / zoom-in
    // animations to finish (Web Animations API ``playState=finished``)
    // instead of sleeping a fixed 200ms. axe-core's color-contrast rule
    // reads computed opacity, so axe must run AFTER the animation
    // settles or it can flake on mid-animation low-contrast frames.
    await waitForAnimationsToFinish(page, "[role=dialog]");

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
  test("fork-thread dialog has 0 violations", async ({
    page,
    seedPath,
    checkA11y,
  }) => {
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
    // Plan 16 Task 20 (D20): the chat send persists ``<active-domain>/chats/
    // <threadId>.md`` to the shared vault. Register cleanup now (before
    // the dialog open, so any later assertion failure still runs it).
    // ``brain_core.chat.persistence`` writes under ``config.domains[0]``;
    // the e2e backend's default scope places this under ``research/chats/``
    // (see persistence.write -> thread_path). Glob across the seeded
    // domain dirs to be robust to scope drift.
    registerCleanup(async () => {
      const fs = await import("node:fs/promises");
      const path = await import("node:path");
      for (const domain of ["research", "work", "personal", "writing"]) {
        const file = path.join(seedPath, domain, "chats", `${threadId}.md`);
        await fs.rm(file, { force: true });
      }
    });

    // Now open the Fork dialog from the sub-header. Plan 16 Task 11 set
    // the per-message Fork button's aria-label to "Fork from this
    // message" (msg-actions.tsx) — distinct from this sub-header's
    // aria-label="Fork". We pin against ``title="Fork"`` here for an
    // additional belt-and-braces guarantee (the sub-header has both
    // aria-label="Fork" AND title="Fork"; the per-message button has
    // neither title nor matching label). Either selector would work
    // post-Task 11; ``getByTitle`` pre-dates the rename and stays
    // correct.
    await page.getByTitle("Fork", { exact: true }).click();

    // The fork dialog heading is "Start a fresh thread from this point."
    await expect(
      page.getByRole("heading", { name: /Start a fresh thread/i }),
    ).toBeVisible();
    // Plan 16 Task 19 (D19): wait for Radix's fade-in / zoom-in
    // animations to finish (Web Animations API ``playState=finished``)
    // instead of sleeping a fixed 200ms. axe-core's color-contrast rule
    // reads computed opacity, so axe must run AFTER the animation
    // settles or it can flake on mid-animation low-contrast frames.
    await waitForAnimationsToFinish(page, "[role=dialog]");

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
    // Plan 16 Task 20 (D20): there's no ``brain_backup_delete`` tool, so
    // we rm the tarball directly. ``brain_core.backup`` writes to
    // ``<vault>/.brain/backups/<backup_id>.tar.gz``; the listing tool
    // skips malformed/missing files so removing the file is enough — no
    // SQLite row to clean.
    registerCleanup(async () => {
      const fs = await import("node:fs/promises");
      const path = await import("node:path");
      const tarball = path.join(
        seedPath,
        ".brain",
        "backups",
        `${backupId}.tar.gz`,
      );
      await fs.rm(tarball, { force: true });
    });

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
    // Plan 16 Task 19 (D19): wait for Radix's fade-in / zoom-in
    // animations to finish (Web Animations API ``playState=finished``)
    // instead of sleeping a fixed 200ms. axe-core's color-contrast rule
    // reads computed opacity, so axe must run AFTER the animation
    // settles or it can flake on mid-animation low-contrast frames.
    await waitForAnimationsToFinish(page, "[role=dialog]");

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
    // Plan 16 Task 19 (D19): wait for Radix's fade-in / zoom-in
    // animations to finish (Web Animations API ``playState=finished``)
    // instead of sleeping a fixed 200ms. axe-core's color-contrast rule
    // reads computed opacity, so axe must run AFTER the animation
    // settles or it can flake on mid-animation low-contrast frames.
    await waitForAnimationsToFinish(page, "[role=dialog]");

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
    // Plan 16 Task 20 (D20): reject the seeded patch so it doesn't
    // pollute /pending for the empty-state ``a11y.spec.ts`` cases (which
    // run after this file alphabetically and would otherwise see leftover
    // patch-card markup with the nested-interactive Approve/Edit/Reject
    // buttons). Plan 14 D9 task review noted: "Anti-regression. Confirm
    // all existing a11y.spec.ts cases still pass (no shared-state
    // pollution)." Lifting this into the afterEach queue means the
    // cleanup runs even if a later assertion fails — the original
    // end-of-body call had a silent leak path.
    registerCleanup(async () => {
      await callTool(page, token, "brain_reject_patch", {
        patch_id: patchId,
        reason: "a11y populated-state spec cleanup",
      });
    });

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
    // Plan 16 Task 19 (D19): wait for Radix's fade-in / zoom-in
    // animations to finish (Web Animations API ``playState=finished``)
    // instead of sleeping a fixed 200ms. axe-core's color-contrast rule
    // reads computed opacity, so axe must run AFTER the animation
    // settles or it can flake on mid-animation low-contrast frames.
    await waitForAnimationsToFinish(page, "[role=dialog]");

    await checkA11y(page, "dialog:patch-card-edit-approve");
    // Cleanup is registered above, before the dialog open — so it runs
    // even if a checkA11y assertion fails.
  });

  // ----------------------------------------------------------------
  // Case 6b: repair-config dialog (Plan 16 Task 33 — full polish)
  //
  // Plan 14 Task 3's deferral receipt asked for a UI surface so this
  // populated-state spec can scan it. Plan 16 Task 9 landed a scaffold;
  // Plan 16 Task 33 lands the full polish: Re-run repair (calls
  // ``brain_repair_config``), per-step results panel, Re-apply (calls
  // ``brain_repair_config_apply``), Cancel.
  //
  // Two-phase scan: empty-state (just opened) AND populated-state (after
  // Re-run reports per-step results). Both must pass axe-core's
  // hard-fail gate. The Re-run path goes through the real backend
  // dispatcher — the e2e vault has a clean config so the run reports a
  // "primary clean" 2-step success with ``repair_changes_pending=false``
  // (Re-apply stays disabled).
  // ----------------------------------------------------------------
  test("repair-config dialog has 0 violations", async ({ page, checkA11y }) => {
    await page.goto("/settings/general/");
    await page.waitForLoadState("networkidle");

    const repairButton = page.getByRole("button", { name: /^Repair config$/i });
    await expect(repairButton).toBeVisible();
    await repairButton.click();

    // Modal heading is "Repair config" per the Task 33 spec microcopy.
    await expect(
      page.getByRole("heading", { name: /^Repair config$/i }),
    ).toBeVisible();
    // Plan 16 Task 19 (D19): wait for Radix's fade-in / zoom-in
    // animations to finish (Web Animations API ``playState=finished``)
    // instead of sleeping a fixed 200ms. axe-core's color-contrast rule
    // reads computed opacity, so axe must run AFTER the animation
    // settles or it can flake on mid-animation low-contrast frames.
    await waitForAnimationsToFinish(page, "[role=dialog]");

    // Phase 1: empty state — Re-run / Re-apply / Cancel rendered, no
    // step rows yet.
    await checkA11y(page, "dialog:repair-config:empty");

    // Phase 2: populated state — click Re-run, wait for the
    // ``brain_repair_config`` response to land + step rows to mount, and
    // re-scan. The e2e vault has a clean config so the call returns a
    // 2-step success (read_primary + validate_primary). Re-apply stays
    // disabled because in-memory config matches what's on disk.
    const responsePromise = waitForToolResponse(page, "brain_repair_config");
    await page
      .getByRole("button", { name: /^Re-run repair$/i })
      .click();
    await responsePromise;

    // Wait for the canonical step row label to appear (load-bearing
    // mount signal — the panel is rendered conditionally on
    // ``hasRun && steps.length > 0``). Use exact match because the
    // backup row label ("Read config.json.bak") is a substring of the
    // primary row label and would trip strict-mode locator collision.
    await expect(
      page.getByText("Read config.json", { exact: true }),
    ).toBeVisible({ timeout: 10_000 });
    // Animations may fire on the new step rows — re-wait before axe.
    await waitForAnimationsToFinish(page, "[role=dialog]");

    await checkA11y(page, "dialog:repair-config:populated");

    // Cleanup: dismiss with Escape so the dialog doesn't bleed into
    // subsequent cases that share the page lifecycle.
    await page.keyboard.press("Escape");
  });

  // ----------------------------------------------------------------
  // Case 6c: autonomy modal (Plan 16 Task 10 SCAFFOLD)
  //
  // Plan 14 Task 3's deferral receipt left the autonomy modal as the
  // single not-implemented surface. Plan 16 Task 10 lands the scaffold:
  // Settings → General has a "Configure autonomy" button that opens a
  // minimal ``<AutonomyModal>`` (Modal + global Switch + 3 category
  // Switches + Done). Full per-domain category UI lands at Plan 16 Task
  // 40 once Task 38 reshapes ``Config.autonomous`` — that re-uses the
  // same component shape, so the a11y gate stays valid through the
  // upgrade.
  // ----------------------------------------------------------------
  test("autonomy modal has 0 violations", async ({ page, checkA11y }) => {
    await page.goto("/settings/general/");
    await page.waitForLoadState("networkidle");

    const autonomyButton = page.getByRole("button", {
      name: /^Configure autonomy$/i,
    });
    await expect(autonomyButton).toBeVisible();
    await autonomyButton.click();

    // Modal heading is "Autonomy mode" per the Task 10 spec microcopy.
    await expect(
      page.getByRole("heading", { name: /^Autonomy mode$/i }),
    ).toBeVisible();
    // Plan 16 Task 19 (D19): wait for Radix's fade-in / zoom-in
    // animations to finish (Web Animations API ``playState=finished``)
    // instead of sleeping a fixed 200ms. axe-core's color-contrast rule
    // reads computed opacity, so axe must run AFTER the animation
    // settles or it can flake on mid-animation low-contrast frames.
    await waitForAnimationsToFinish(page, "[role=dialog]");

    await checkA11y(page, "dialog:autonomy-modal");

    // Cleanup: dismiss with Escape so the dialog doesn't bleed into
    // subsequent cases that share the page lifecycle.
    await page.keyboard.press("Escape");
  });

  // ----------------------------------------------------------------
  // Case 6c-bis: Settings → Autonomy panel (populated) — Plan 16 Task 40
  //
  // Plan 16 Task 40 / D30 step 4 of 4: Settings → Autonomy gets the
  // per-domain × per-category grid surface (replaces the Plan 07
  // 5-row flat scaffold whose backing keys were dropped in Task 39).
  // The Settings tabs walk (Case 8 below) covers the EMPTY autonomy
  // grid; this case covers the POPULATED state (one slug with mixed-
  // value flags) so the Switch's ``data-state=checked`` color-contrast
  // path runs under axe-core's computed-style scan.
  //
  // The e2e backend's seeded scope is ``[research, work, personal]``
  // (BRAIN_ALLOWED_DOMAINS), all three are persisted in Config.domains,
  // so the panel renders 3 rows × 5 columns + 3 Reset buttons + 1
  // "Disable all autonomy" footer. We seed one slug's autonomy via the
  // per-run-token API path (mirrors Cases 4 + 6) so axe scans both
  // checked and unchecked Switch states + the populated row's accent
  // dot + the destructive footer button.
  // ----------------------------------------------------------------
  test("Settings → Autonomy panel (populated) has 0 violations", async ({
    page,
    seedPath,
    checkA11y,
  }) => {
    const token = await readApiToken(seedPath);
    // Seed two flags on ``research`` so the panel's populated row
    // exercises both checked + unchecked Switch states. The backend's
    // ``_apply_autonomous_per_domain`` apply-helper auto-creates the
    // per-slug entry on first set; subsequent sets mutate it via
    // ``setattr``.
    await callTool(page, token, "brain_config_set", {
      key: "autonomous.research.new_files",
      value: true,
    });
    await callTool(page, token, "brain_config_set", {
      key: "autonomous.research.edits",
      value: true,
    });
    // Plan 16 Task 20 (D20): clear the seeded autonomy flags so sibling
    // specs see a clean Config.autonomous snapshot. The backend prunes
    // the slug entry when every flag is False — set both back to False
    // and the entry vanishes from the persisted dict.
    registerCleanup(async () => {
      await callTool(page, token, "brain_config_set", {
        key: "autonomous.research.new_files",
        value: false,
      });
      await callTool(page, token, "brain_config_set", {
        key: "autonomous.research.edits",
        value: false,
      });
    });

    // Race-free fetch wait: the panel fires ``brain_config_get`` on
    // mount to hydrate its full ``Config.autonomous`` snapshot. Same
    // pattern as the Settings tabs walk (Case 8).
    const fetchWait = waitForToolResponse(page, "brain_config_get");
    await page.goto("/settings/autonomous/");
    await fetchWait;
    await page.waitForLoadState("networkidle");

    // Populated state mount marker — the grid only renders once
    // ``useDomains()`` hydrates with a non-empty list AND the
    // ``configGet`` snapshot lands in the store.
    await expect(page.getByTestId("autonomy-grid")).toBeVisible({
      timeout: 5_000,
    });
    // Switch initial states: research/new_files + research/edits are
    // ``checked`` per the seeded flags above; every other cell is
    // ``unchecked``. Pin against one of each so the assertions fail
    // loud if the hydrate path drifts.
    await expect(
      page.getByTestId("autonomy-switch-research-new_files"),
    ).toHaveAttribute("data-state", "checked");
    await expect(
      page.getByTestId("autonomy-switch-research-draft"),
    ).toHaveAttribute("data-state", "unchecked");

    await checkA11y(page, "panel:settings-autonomous-populated");
  });

  // ----------------------------------------------------------------
  // Case 6d: file-preview overlay (Plan 16 Task 11)
  //
  // Plan 14 Task 4 deferred a real "Browse → file → preview" overlay
  // because no such surface existed (the inline split-pane was the
  // closest analogue and the populated-state proxy was ⌘K's
  // ``<SearchOverlay />``). Plan 16 Task 11 lands the dedicated
  // overlay: each file row in the FileTree renders a per-row
  // "Quick preview" eye-icon button that opens
  // ``<FilePreviewOverlay />``. The split-pane stays as the inline
  // empty-state default; this overlay is the populated-state surface.
  //
  // Seed flow: write the note straight to disk under the test vault
  // ``seedPath`` (same pattern as ``seedBrainMd``). ``brain_recent``
  // walks the filesystem on the next call so the note appears in the
  // FileTree on Browse's mount effect. Reaching for an in-process disk
  // write here (rather than ``brain_propose_note`` + apply_patch) keeps
  // the test deterministic — Browse's mount effect runs once we hit
  // the route, no patch round-trip race to manage.
  // ----------------------------------------------------------------
  test("file-preview overlay has 0 violations", async ({
    page,
    seedPath,
    checkA11y,
  }) => {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const stamp = Date.now();
    const slug = `a11y-preview-${stamp}`;
    const targetPath = `research/notes/${slug}.md`;
    const onDisk = path.join(seedPath, "research", "notes", `${slug}.md`);

    await fs.mkdir(path.dirname(onDisk), { recursive: true });
    await fs.writeFile(
      onDisk,
      `# A11y file-preview overlay\n\nSeeded at ${stamp}.\n`,
      "utf-8",
    );
    // Plan 16 Task 20 (D20): rm the seeded file so /browse listings in
    // sibling specs don't see it (FileTree walks the disk on mount).
    registerCleanup(async () => {
      await fs.rm(onDisk, { force: true });
    });

    await page.goto("/browse/");
    await page.waitForLoadState("networkidle");

    // The seeded note's row in the FileTree exposes a Quick preview
    // button per Plan 16 Task 11. The aria-label is the canonical
    // selector (visible icon-only + sr-only text).
    const previewBtn = page.getByRole("button", {
      name: new RegExp(`^Quick preview ${slug}$`, "i"),
    });
    await expect(previewBtn).toBeVisible({ timeout: 10_000 });
    await previewBtn.click();

    // Modal heading is the file path (the overlay uses the path as its
    // title).
    await expect(
      page.getByRole("heading", { name: targetPath }),
    ).toBeVisible();
    // Plan 16 Task 19 (D19): wait for Radix's fade-in / zoom-in
    // animations to finish via the Web Animations API. The file-preview
    // overlay is a Radix Modal so it carries ``role="dialog"`` once
    // mounted; the same animation class set as the other modals applies.
    await waitForAnimationsToFinish(page, "[role=dialog]");

    await checkA11y(page, "overlay:file-preview");

    // Cleanup: dismiss with Escape so the overlay doesn't bleed into
    // subsequent cases that share the page lifecycle.
    await page.keyboard.press("Escape");
  });

  // ----------------------------------------------------------------
  // Case 6e: WikilinkHover tooltip (Plan 16 Task 11)
  //
  // Plan 14 Task 4 noted the wikilink hover is a tooltip (role=tooltip),
  // not a modal-shape overlay, and skipped it. Plan 16 D11 brings it
  // into populated-state coverage with a dedicated case.
  //
  // The wikilink anchor is a focusable ``<a>`` with class ``wikilink``
  // (see ``src/lib/chat/rendering.ts``); the Reader wires
  // ``onFocus`` → enterAnchor → stamps ``aria-describedby`` and shows
  // the tooltip. We seed two notes wired by a wikilink, navigate to
  // the source, focus the link via keyboard, axe-scan the rendered
  // tooltip, then move focus off to dismiss.
  // ----------------------------------------------------------------
  test("wikilink-hover tooltip has 0 violations", async ({
    page,
    seedPath,
    checkA11y,
  }) => {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const stamp = Date.now();
    const targetSlug = `target-${stamp}`;
    const sourceSlug = `source-${stamp}`;
    const sourcePath = `research/notes/${sourceSlug}.md`;
    const notesDir = path.join(seedPath, "research", "notes");

    await fs.mkdir(notesDir, { recursive: true });
    const targetOnDisk = path.join(notesDir, `${targetSlug}.md`);
    const sourceOnDisk = path.join(notesDir, `${sourceSlug}.md`);
    // Target note (so the wikilink resolves to a real file).
    await fs.writeFile(
      targetOnDisk,
      `# Target\n\nA short body.\n`,
      "utf-8",
    );
    // Source note contains a wikilink to the target.
    await fs.writeFile(
      sourceOnDisk,
      `# Source\n\nLink to [[${targetSlug}]] in this note.\n`,
      "utf-8",
    );
    // Plan 16 Task 20 (D20): rm both seeded notes so sibling specs
    // don't see them on /browse.
    registerCleanup(async () => {
      await fs.rm(sourceOnDisk, { force: true });
      await fs.rm(targetOnDisk, { force: true });
    });

    await page.goto(`/browse/${sourcePath}`);
    await page.waitForLoadState("networkidle");

    // Reader renders the wikilink as ``<a class="wikilink">`` whose
    // text content is the slug. Focus it via JS (wikilinks have
    // ``href="#"`` so they're tab-focusable; clicking the body and
    // tabbing would also work but is fragile to focusable-element
    // ordering — focus() is deterministic).
    const link = page.locator(`a.wikilink`, { hasText: targetSlug });
    await expect(link).toBeVisible({ timeout: 10_000 });
    await link.focus();

    // Reader's ``onFocus`` delegate stamps ``aria-describedby`` on the
    // anchor and shows the tooltip. The tooltip is the readNote async
    // round-trip; wait for it to mount (look for the canonical id).
    const tooltip = page.locator("#wikilink-hover-tooltip");
    await expect(tooltip).toBeVisible({ timeout: 10_000 });
    await expect(tooltip).toHaveAttribute("role", "tooltip");
    await expect(link).toHaveAttribute(
      "aria-describedby",
      "wikilink-hover-tooltip",
    );
    // Plan 16 Task 19 (D19): the tooltip-visible + role + aria-describedby
    // assertions above are themselves the deterministic mount signal — the
    // historical ``waitForTimeout(200)`` was a redundant cushion. No tool
    // round-trip remains in flight at this point (readNote already
    // resolved by the time the tooltip's body content renders), so no
    // ``waitForToolResponse`` substitute is needed.

    await checkA11y(page, "tooltip:wikilink-hover");

    // Cleanup: blur the link so the tooltip dismisses + the
    // aria-describedby comes off (otherwise stale ids could confuse
    // any subsequent focus walk).
    await page.evaluate(() => (document.activeElement as HTMLElement)?.blur());
  });

  // ----------------------------------------------------------------
  // Case 6f: per-message Fork dialog (Plan 16 Task 11)
  //
  // Plan 16 D11 adds a second Fork trigger on each assistant message
  // bubble (``MsgActions``); the chat-sub-header Fork (Case 3) already
  // exists. Both route through the same ``<ForkDialog />`` via
  // ``dialogs-store``; the per-message variant carries its row's
  // ``turnIndex`` so the user can fork at any prior turn.
  //
  // Disambiguation: the per-message button is ``aria-label="Fork from
  // this message"`` (Plan 16 Task 11); the sub-header is
  // ``aria-label="Fork"`` + ``title="Fork"`` (unchanged).
  //
  // Drive a real chat turn so the assistant message exists, hover the
  // assistant bubble to surface the actions row (also reachable via
  // keyboard focus per ``focus-within``), click the per-message Fork,
  // axe-scan the dialog, dismiss with Esc.
  // ----------------------------------------------------------------
  test("per-message Fork dialog has 0 violations", async ({
    page,
    seedPath,
    checkA11y,
  }) => {
    const threadId = `e2e-a11y-msg-fork-${Date.now()}`;
    await page.goto(`/chat/${threadId}`);
    await page.waitForLoadState("networkidle");

    // Send a turn so an assistant bubble exists (the per-message
    // actions row only renders for non-streaming assistant messages).
    await page
      .getByRole("textbox", { name: "Message brain" })
      .fill("hello brain — per-message fork");
    await page.getByRole("button", { name: "Send" }).click();
    await expect(page.locator('[data-role="brain"]').first()).toContainText(
      "Hello from FakeLLM",
      { timeout: 20_000 },
    );
    // Plan 16 Task 20 (D20): same persisted-thread cleanup as Case 3.
    // The send writes ``<active-domain>/chats/<threadId>.md``; rm it
    // across the candidate domain dirs.
    registerCleanup(async () => {
      const fs = await import("node:fs/promises");
      const path = await import("node:path");
      for (const domain of ["research", "work", "personal", "writing"]) {
        const file = path.join(seedPath, domain, "chats", `${threadId}.md`);
        await fs.rm(file, { force: true });
      }
    });

    // Hover the assistant bubble to surface the action row (the row
    // uses ``opacity-0`` + ``group-hover:opacity-100`` — also visible
    // on focus-within for keyboard users; hover is the production
    // mouse path).
    const bubble = page.locator('[data-role="brain"]').first();
    await bubble.hover();

    // Per Plan 16 Task 11 the per-message Fork's aria-label is "Fork
    // from this message" — disambiguates from the sub-header Fork
    // (aria-label="Fork").
    const perMsgFork = page.getByRole("button", {
      name: /^Fork from this message$/,
    });
    await expect(perMsgFork).toBeVisible();
    await perMsgFork.click();

    // Same ForkDialog as Case 3 — heading is "Start a fresh thread
    // from this point.".
    await expect(
      page.getByRole("heading", { name: /Start a fresh thread/i }),
    ).toBeVisible();
    // Plan 16 Task 19 (D19): wait for Radix's fade-in / zoom-in
    // animations to finish (Web Animations API ``playState=finished``)
    // instead of sleeping a fixed 200ms. axe-core's color-contrast rule
    // reads computed opacity, so axe must run AFTER the animation
    // settles or it can flake on mid-animation low-contrast frames.
    await waitForAnimationsToFinish(page, "[role=dialog]");

    await checkA11y(page, "dialog:per-message-fork");

    // Cleanup: dismiss with Escape so the dialog doesn't bleed into
    // subsequent cases.
    await page.keyboard.press("Escape");
  });

  // ================================================================
  // Plan 14 Task 4 — menus + overlays (C2.b)
  // ================================================================

  // ----------------------------------------------------------------
  // Case 7: topbar scope picker dropdown
  //
  // Topbar's scope chip is a Radix Popover (``<Popover />`` from
  // ui/popover.tsx, mounted in ``shell/topbar.tsx``). Click the
  // chip → PopoverContent renders the per-domain Checkbox list.
  // The ``aria-label="Scope: <label>"`` on the trigger keeps it
  // discoverable; the panel itself has no role on the wrapper but
  // exposes labelled checkboxes per domain.
  // ----------------------------------------------------------------
  test("topbar scope picker dropdown has 0 violations", async ({
    page,
    checkA11y,
  }) => {
    await page.goto("/chat");
    await page.waitForLoadState("networkidle");

    // The scope trigger's accessible name varies with how many domains
    // are selected — match any "Scope:" prefix to stay robust to the
    // first-mount hydration (Plan 11 Task 8) which seeds scope from
    // ``active_domain``.
    const scopeTrigger = page.getByRole("button", { name: /^Scope: / });
    await expect(scopeTrigger).toBeVisible();
    await scopeTrigger.click();

    // PopoverContent renders the literal string "Visible domains" as a
    // section header — wait on that as the stable mount marker. Radix
    // Popover portals into a sibling DOM node so we can't anchor on a
    // child of the trigger.
    await expect(page.getByText("Visible domains")).toBeVisible();
    // Plan 16 Task 19 (D19): wait for the popover's open animation to
    // settle. Radix Popover content uses the same fade-in / zoom-in /
    // slide-in keyframe set as the Dialog primitive (see
    // components/ui/popover.tsx: ``data-[state=open]:animate-in
    // data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95``). axe
    // can scan transient low-contrast frames mid-animation; waiting on
    // ``getAnimations({subtree: true}).every(playState=finished)`` is
    // the deterministic equivalent of the historical 200ms cushion.
    // Selector targets the popover's open-state content wrapper —
    // ``aria-haspopup="dialog"`` is a Radix convention for popovers.
    await waitForAnimationsToFinish(
      page,
      '[data-radix-popper-content-wrapper] [data-state="open"]',
    );

    await checkA11y(page, "menu:topbar-scope-picker");
  });

  // ----------------------------------------------------------------
  // Case 8: Settings tabs walk
  //
  // Per Plan 14 Task 4 dispatch text: "Settings tab navigation (each
  // tab in Settings — likely ~5 sub-cases or single multi-tab walk)".
  // Walk all 8 tabs in one test to keep run time bounded; axe-scan
  // each. The empty-state ``a11y.spec.ts`` covers ``general``,
  // ``providers``, and ``domains`` — this case extends to the
  // remaining 5 (``budget``, ``autonomous``, ``integrations``,
  // ``brain-md``, ``backups``) AND re-scans the Plan 13 trio under
  // the populated-state lifecycle (post-rename / post-create state
  // from Cases 1+2 mutates ``Config.domains``, which in turn changes
  // ``/settings/domains`` rendering).
  //
  // We run all 8 in sequence per single test rather than 8 separate
  // tests because each tab loads a fresh fetch + fixture cycle and
  // 8 separate ``test()`` calls would each pay the navigation cost.
  // axe-core itself runs against the live document each time so the
  // gate is identical.
  // ----------------------------------------------------------------
  test("Settings tabs (all 8) have 0 violations under populated state", async ({
    page,
    checkA11y,
  }) => {
    const tabs = [
      "general",
      "providers",
      "budget",
      "autonomous",
      "integrations",
      "domains",
      "brain-md",
      "backups",
    ] as const;

    // Plan 16 Task 19 (D19): per-panel deterministic mount signal. Most
    // settings panels fire ``brain_config_get`` on mount (panel-general,
    // panel-providers, panel-budget, panel-autonomous, panel-integrations,
    // panel-domains); panel-backups fires ``brain_backup_list``;
    // panel-brain-md DOES fire ``readNote("BRAIN.md")`` on mount but
    // does not block render on it (Monaco renders an empty editor and
    // hydrates the content asynchronously), so ``networkidle`` plus h2
    // visibility is a sufficient hydration signal for the brain-md tab —
    // we deliberately omit it from the strict tool-response map. The
    // mapping below tells us which response (if any) marks "panel
    // hydrated" — a strict upgrade over the historical
    // ``waitForTimeout(200)`` cushion which would silently pass on slow
    // CI runners that hadn't actually resolved their fetch yet.
    const tabFetchMap: Record<(typeof tabs)[number], string | null> = {
      general: "brain_config_get",
      providers: "brain_config_get",
      budget: "brain_config_get",
      autonomous: "brain_config_get",
      integrations: "brain_config_get",
      domains: "brain_config_get",
      "brain-md": null, // see comment above — readNote fires but is non-blocking
      backups: "brain_backup_list",
    };

    for (const tab of tabs) {
      const expectedTool = tabFetchMap[tab];
      // Race-free: register the response wait BEFORE navigation so the
      // Promise is in place when the panel mounts and its useEffect
      // fires the fetch. ``waitForLoadState("networkidle")`` is a fine
      // backstop for the no-fetch case (panel-brain-md) and for the
      // post-fetch React reconciliation tail.
      const fetchWait = expectedTool
        ? waitForToolResponse(page, expectedTool)
        : Promise.resolve();
      await page.goto(`/settings/${tab}/`);
      await fetchWait;
      await page.waitForLoadState("networkidle");
      // h2 visibility is the final deterministic "tree hydrated" signal —
      // every panel renders at least one h2 within ``<main>``.
      await expect(page.locator("main h2").first()).toBeVisible({
        timeout: 5_000,
      });
      await checkA11y(page, `menu:settings-tab:${tab}`);
    }
  });

  // ----------------------------------------------------------------
  // Case 9: search overlay (⌘K)
  //
  // The plan dispatch text calls out a "file-preview overlay (Browse →
  // file → preview)". The app does not have a dedicated file-preview
  // overlay today — Browse uses an inline split-pane (Reader vs
  // VaultEditor) and the only true "overlay" reachable from the Browse
  // route is ``<SearchOverlay />`` (cmd-K). It IS modal-shape (role=
  // dialog + aria-modal=true) and renders results from ``recent``;
  // covering it here is the closest match to the dispatch intent. The
  // WikilinkHover surface is a tooltip (role=tooltip), not a
  // modal-shape overlay, so it's not in scope for this case.
  //
  // Trigger via ⌘K — the global keydown lives in ``app-shell.tsx``.
  // ----------------------------------------------------------------
  test("search overlay has 0 violations", async ({ page, checkA11y }) => {
    await page.goto("/browse");
    await page.waitForLoadState("networkidle");

    // ⌘K on Mac, Ctrl+K elsewhere — Playwright's "Meta" maps to
    // either depending on platform. The handler in app-shell.tsx
    // accepts both.
    await page.keyboard.press("Meta+K");

    // Overlay's ``role="dialog"`` + ``aria-label="Search the vault"``
    // is the stable mount marker.
    const dialog = page.getByRole("dialog", { name: "Search the vault" });
    await expect(dialog).toBeVisible();
    // Plan 16 Task 19 (D19): wait for the dialog's open animation to
    // settle (same fade-in / zoom-in keyframes as the other modals).
    // Replaces the historical ``waitForTimeout(200)`` animation beat.
    await waitForAnimationsToFinish(page, "[role=dialog]");

    await checkA11y(page, "overlay:search");

    // Cleanup: dismiss so the overlay doesn't bleed into Case 10's
    // route navigation.
    await page.keyboard.press("Escape");
  });

  // ----------------------------------------------------------------
  // Case 10: drop-zone overlay (drag hover state)
  //
  // ``<DropOverlay />`` reveals when ``system-store.draggingFile`` is
  // true. ``app-shell.tsx``'s ``onDragEnter`` flips the flag to true
  // when ``e.dataTransfer.types`` contains ``"Files"``. Playwright's
  // ``page.dispatchEvent`` doesn't natively support setting
  // ``DataTransfer.types``, so we drop into the page context with
  // ``page.evaluate`` and dispatch a real DragEvent constructed via
  // the DataTransfer API. This is production-shape — same code path
  // a real OS drag fires.
  // ----------------------------------------------------------------
  test("drop-zone overlay has 0 violations", async ({ page, checkA11y }) => {
    await page.goto("/chat");
    await page.waitForLoadState("networkidle");

    // Dispatch a real dragenter with a Files-typed DataTransfer on the
    // outermost ``.app-grid`` (where AppShell hangs the drag handlers).
    // Constructing DataTransfer + dispatching DragEvent is the only
    // production-shape way to trip the ``"Files"``-types check; setting
    // ``draggingFile`` directly on the store would be a different code
    // path and miss any regression in the dragenter handler itself.
    await page.evaluate(() => {
      const grid = document.querySelector(".app-grid");
      if (!grid) throw new Error("app-grid not mounted");
      const dt = new DataTransfer();
      // ``items.add`` populates ``types`` so the production guard
      // ``e.dataTransfer.types.includes("Files")`` passes.
      const blob = new Blob(["dummy"], { type: "text/plain" });
      const file = new File([blob], "dummy.txt", { type: "text/plain" });
      dt.items.add(file);
      const ev = new DragEvent("dragenter", {
        bubbles: true,
        cancelable: true,
        dataTransfer: dt,
      });
      grid.dispatchEvent(ev);
    });

    // ``<DropOverlay />`` flips ``aria-hidden`` from "true" → "false"
    // when visible. Pin against that attribute rather than the testid
    // visibility because the overlay stays in the DOM in both states
    // (see drop-overlay.tsx docstring).
    const overlay = page.getByTestId("drop-overlay");
    await expect(overlay).toHaveAttribute("aria-hidden", "false");
    // Plan 16 Task 19 (D19): wait for the CSS transition-opacity to
    // settle. ``drop-overlay.tsx`` uses ``transition-opacity duration-150``
    // to fade the panel in; mid-transition opacity values cause axe-core
    // to compute color contrast against a partially-transparent surface
    // (the overlay stacks on the chat scroller's content, so a 50%-faded
    // panel reads as a blended fg/bg that fails 4.5:1). CSS transitions
    // are reported by ``getAnimations()`` on modern Chromium so the same
    // helper that gates Radix dialog animations applies here.
    await waitForAnimationsToFinish(page, '[data-testid="drop-overlay"]');

    await checkA11y(page, "overlay:drop-zone");

    // Cleanup: fire dragleave with relatedTarget=null so the handler
    // flips ``draggingFile`` back to false. Otherwise subsequent
    // navigations would carry the overlay's pointer-events-none
    // styling forward and could trip later interaction tests.
    await page.evaluate(() => {
      const grid = document.querySelector(".app-grid");
      if (!grid) return;
      const ev = new DragEvent("dragleave", {
        bubbles: true,
        cancelable: true,
      });
      // ``relatedTarget`` defaults to null — that's exactly what the
      // production handler treats as "cursor left the window".
      grid.dispatchEvent(ev);
    });
  });

  // ----------------------------------------------------------------
  // Case 11: toast notifications
  //
  // Toasts mount under ``<Toasts />`` (system-overlays.tsx). The
  // bottom-right stack uses ``role="status"`` per ``ToastItem``. To
  // trigger a real toast we click "Back up now" on Settings →
  // Backups, which fires ``brain_backup_create`` and renders a
  // success toast via ``pushToast()``. Production-shape: same code
  // path any toast in the app goes through.
  // ----------------------------------------------------------------
  test("toast notifications have 0 violations", async ({
    page,
    seedPath,
    checkA11y,
  }) => {
    // Plan 16 Task 20 (D20): snapshot the backups directory before the
    // click so we can rm only the tarballs created by THIS test (rather
    // than nuking the whole directory and breaking other suites that
    // may have seeded their own).
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const backupsDir = path.join(seedPath, ".brain", "backups");
    const before = new Set<string>(
      await fs.readdir(backupsDir).catch(() => [] as string[]),
    );
    registerCleanup(async () => {
      const after = await fs.readdir(backupsDir).catch(() => [] as string[]);
      for (const name of after) {
        if (!before.has(name)) {
          await fs.rm(path.join(backupsDir, name), { force: true });
        }
      }
    });

    await page.goto("/settings/backups/");
    await page.waitForLoadState("networkidle");

    const backupNow = page.getByRole("button", { name: /Back up now/i });
    await expect(backupNow).toBeVisible();
    await backupNow.click();

    // Toast message is "Backup created." with a success variant; wait
    // for it to be visible (the ``role="status"`` region is live, axe
    // will scan it during the assertion below).
    await expect(page.getByText("Backup created.")).toBeVisible({
      timeout: 15_000,
    });
    // Plan 16 Task 19 (D19): the toast-text-visible assertion above is
    // itself the deterministic mount signal — the historical
    // ``waitForTimeout(200)`` was a redundant cushion.

    await checkA11y(page, "overlay:toast-notifications");

    // Cleanup: dismiss so the toast doesn't linger into the next test
    // and trip a stale-content scan. The X button has aria-label
    // "Dismiss toast".
    const dismiss = page.getByRole("button", { name: "Dismiss toast" }).first();
    if (await dismiss.isVisible().catch(() => false)) {
      await dismiss.click();
    }
  });
});
