/**
 * Plan 14 Task 3 + Task 4 — populated-state a11y sweep
 * (C2.a dialogs + C2.b menus + overlays).
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
 * Six implementable dialog cases land here. The two deferrals are filed
 * as Plan 15 candidates per the per-task review escalation policy: "if
 * a dialog doesn't have a UI surface, file as Plan 15 candidate; reduce
 * to 7 or fewer cases."
 *
 * Menu + overlay inventory (Task 4 dispatch text, 5 nominal cases):
 *
 *   ✅ topbar scope picker dropdown  (Topbar → click scope chip → Radix Popover)
 *   ✅ Settings tabs walk            (visit all 8 panels in one populated test)
 *   ✅ search overlay                (⌘K — closest "file-preview overlay"
 *                                     analogue; the app does not have a
 *                                     dedicated Browse → file → preview
 *                                     surface today, the closest live
 *                                     overlay reachable from Browse is
 *                                     ``<SearchOverlay />`` per
 *                                     ``system-overlays.tsx``. Documented
 *                                     deviation; Browse-side WikilinkHover
 *                                     is a tooltip, not a modal-shape
 *                                     overlay.)
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
    await page.waitForTimeout(200);

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

    for (const tab of tabs) {
      await page.goto(`/settings/${tab}/`);
      await page.waitForLoadState("networkidle");
      // Each panel renders an h2 within the content area; wait one
      // extra beat so any lazy fetch (configGet, brainBackupList,
      // etc.) settles before axe scans.
      await page.waitForTimeout(200);
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
    await page.waitForTimeout(200);

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
    await page.waitForTimeout(200);

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
  test("toast notifications have 0 violations", async ({ page, checkA11y }) => {
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
    await page.waitForTimeout(200);

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
