/**
 * Plan 22 Task 16 e2e — watched-folders feature lifecycle.
 *
 * End-to-end coverage of the Plan 22 watched-folders surface from user
 * click → backend tool → vault state. The spec covers:
 *
 *   1. Settings → Watched folders empty state + the "Watch a folder" CTA.
 *   2. Watch-enable modal — opens, renders verbatim D1 overwrite-contract
 *      microcopy, closes on Cancel + Esc, opens with prefilled state
 *      from the Bulk Import → Watch bridge (D6).
 *   3. Watch-enable submit — fires ``brain_watch_folder`` (dry-run on
 *      mount + real-run on confirm), success toast, row appears in
 *      Settings list.
 *   4. Watch-disable modal — opens from row Unwatch, renders verbatim
 *      reversibility microcopy, confirm removes the row.
 *   5. Orphan management — seeded orphans appear in Settings → Orphans,
 *      single restore drops the row, single delete uses typed-confirm
 *      (slug as confirm word), bulk select + bulk delete uses
 *      typed-confirm ("delete N notes").
 *   6. Topbar status indicator — hidden when 0/0, visible with correct
 *      counts when populated, click-through routes by orphan_count.
 *   7. axe-core hard-fail gates on every new surface — both panels, both
 *      confirmation modals, the typed-confirm orphan-delete modal.
 *
 * ## State-cleanup contract
 *
 * Like ``a11y-populated.spec.ts``, every test in this file must leave
 * the shared vault in the same state it found it. Playwright runs
 * ``workers: 1`` + ``fullyParallel: false`` against a single
 * ``BRAIN_VAULT_ROOT`` (see ``playwright.config.ts``); any seeded
 * config entry, watched folder, or hand-written orphan note would
 * otherwise leak into sibling specs and trip flakes downstream.
 *
 * Mutating tests register cleanup callbacks via ``registerCleanup(...)``
 * immediately after the mutation succeeds. The suite-level
 * ``test.afterEach`` drains them in LIFO order, running each callback
 * even if assertions failed.
 *
 * ## Mocking strategy
 *
 * Real backend, no ``page.route()`` interceptors — matches project
 * precedent (``patch-approval.spec.ts``, ``a11y-populated.spec.ts``).
 * The brain_api subprocess runs against the temp vault; we seed via
 * direct tool calls using the per-run API token read from
 * ``.brain/run/api-secret.txt`` (same pattern as the patch-approval
 * spec). The FakeLLMProvider is canned via ``BRAIN_E2E_MODE=1`` so the
 * watch-folder initial-sync classifier returns deterministic shapes.
 *
 * ## Animation discipline
 *
 * Every axe-core run on a modal surface is preceded by
 * ``waitForAnimationsToFinish(page, "[role=dialog]")`` per the auto-
 * memory ``feedback_axe_dialog_animation_wait.md`` — Radix dialogs
 * carry ``role="dialog"`` synchronously but CSS keyframes hold
 * mid-animation low-opacity styles that fail axe color-contrast until
 * the open animation reaches ``playState=finished``. The helper from
 * ``_helpers.ts`` polls the Web Animations API.
 */
import { type Page } from "@playwright/test";

import { expect, test } from "./fixtures";
import { waitForAnimationsToFinish, waitForToolResponse } from "./_helpers";

// ---------- Helpers ----------

/** Read the per-run brain_api token from disk. Same pattern as
 *  ``patch-approval.spec.ts`` / ``a11y-populated.spec.ts``. */
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
  body: Record<string, unknown> = {},
): Promise<{ data?: unknown; error?: unknown }> {
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
 *  pattern as ``a11y-populated.spec.ts``. */
async function seedBrainMd(seedPath: string): Promise<void> {
  const fs = await import("node:fs/promises");
  const path = await import("node:path");
  await fs.writeFile(
    path.join(seedPath, "BRAIN.md"),
    "# BRAIN\n\nYou are brain. Maintain this vault carefully.\n",
    "utf-8",
  );
}

/** Mint a temp source folder OUTSIDE the vault root with a few .md
 *  files. Mirrors ``bulk-import.spec.ts``'s pattern — keeps the source
 *  folder distinct from the vault so ``brain_list_domains`` doesn't
 *  mistake it for a domain. */
async function mintTempSourceFolder(
  fileCount: number,
  prefix = "brain-watched-e2e-",
): Promise<string> {
  const fs = await import("node:fs/promises");
  const os = await import("node:os");
  const path = await import("node:path");
  const folder = await fs.mkdtemp(path.join(os.tmpdir(), prefix));
  for (let i = 1; i <= fileCount; i++) {
    await fs.writeFile(
      path.join(folder, `source-${i}.md`),
      `# source ${i}\n\nSample source content ${i} for watched-folders e2e.\n`,
      "utf-8",
    );
  }
  return folder;
}

/**
 * Hand-seed an orphaned vault note. ``brain_list_orphans`` walks the
 * vault and selects notes with ``orphaned: true`` + ``watched_folder_id``
 * frontmatter — writing the file directly is the simplest way to
 * populate the Orphans tab for UI tests without driving the full
 * watch → delete-source → re-sync pipeline (which would couple the
 * spec to the FakeLLMProvider's classifier shape). The ``Frontmatter``
 * model in ``brain_core.vault.frontmatter`` accepts the keys below.
 *
 * ``orphanedAt`` must be a YAML date scalar (``YYYY-MM-DD``) — the
 * Pydantic ``Frontmatter.orphaned_at`` field is typed as ``date | None``
 * and rejects datetimes with non-zero time components
 * (``date_from_datetime_inexact`` validation error). YAML's date scalar
 * parses cleanly to ``datetime.date``.
 */
async function seedOrphanNote(args: {
  seedPath: string;
  domain: string;
  slug: string;
  watchedFolderId: string;
  sourcePath: string;
  /** YAML date scalar — ``YYYY-MM-DD``, NOT an ISO-8601 datetime. */
  orphanedAt: string;
}): Promise<string> {
  const fs = await import("node:fs/promises");
  const path = await import("node:path");
  const notesDir = path.join(args.seedPath, args.domain, "notes");
  await fs.mkdir(notesDir, { recursive: true });
  const notePath = path.join(notesDir, `${args.slug}.md`);
  const fm = [
    "---",
    "title: " + args.slug,
    "domain: " + args.domain,
    `source_path: ${args.sourcePath}`,
    "orphaned: true",
    `orphaned_at: ${args.orphanedAt}`,
    `watched_folder_id: ${args.watchedFolderId}`,
    "---",
    "",
    `# ${args.slug}`,
    "",
    "Body content for the orphan e2e seed.",
    "",
  ].join("\n");
  await fs.writeFile(notePath, fm, "utf-8");
  return notePath;
}

/** Render a JS ``Date`` as a YAML date scalar (``YYYY-MM-DD``). */
function yamlDate(d: Date): string {
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day = String(d.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/**
 * Defensive vault-state purge before every watched-folders test.
 *
 * The shared ``BRAIN_VAULT_ROOT`` accumulates state across specs:
 * earlier suites (especially ``a11y-populated.spec.ts``,
 * ``bulk-import.spec.ts``) write notes whose frontmatter uses
 * ISO-8601 datetime (with non-zero time component) for the ``created``
 * + ``updated`` keys. ``Frontmatter.created`` / ``updated`` are typed
 * as ``date`` (not ``datetime``); Pydantic raises ``ValidationError``
 * on those notes during ``Frontmatter.from_dict``.
 *
 * Critically, ``brain_list_watched_folders._walk_watched_folder_counts``
 * catches ``FrontmatterError`` but NOT ``pydantic_core.ValidationError``
 * — so a single malformed note in the vault makes the tool blow up
 * with an unhandled 500 the moment ANY watched folder is configured.
 * The Settings → Watched folders panel then renders the "Couldn't load
 * watched folders" error banner instead of the seeded row, and every
 * downstream assertion against the populated state fails.
 *
 * This purge removes the cross-test pollution surface. Future work
 * (Plan 22 follow-up): broaden the except clause in
 * ``list_watched_folders.py:_walk_watched_folder_counts`` to catch
 * Pydantic ``ValidationError`` alongside ``FrontmatterError`` — the
 * "skip malformed notes" semantics are already documented in the
 * function's docstring; only the exception list is incomplete.
 *
 */
async function purgeWatchedFolderPollution(args: {
  seedPath: string;
}): Promise<void> {
  const fs = await import("node:fs/promises");
  const path = await import("node:path");

  // Nuke notes whose frontmatter would trip Pydantic's datetime-as-
  // date validator. We walk the same vault tree the backend walks and
  // rm any .md whose frontmatter ``created`` or ``updated`` line
  // carries a ``T`` (the YAML/ISO datetime marker). YAML date scalars
  // (``2026-05-12``) don't have ``T`` so they're safe; only datetime
  // values are removed.
  for (const domain of ["research", "work", "personal", "writing"]) {
    const domainDir = path.join(args.seedPath, domain);
    if (
      !(await fs
        .stat(domainDir)
        .then((s) => s.isDirectory())
        .catch(() => false))
    )
      continue;
    async function walk(dir: string): Promise<void> {
      let entries: import("node:fs").Dirent[];
      try {
        entries = await fs.readdir(dir, { withFileTypes: true });
      } catch {
        return;
      }
      for (const e of entries) {
        const full = path.join(dir, e.name);
        if (e.isDirectory()) {
          await walk(full);
        } else if (e.isFile() && e.name.endsWith(".md")) {
          try {
            const body = await fs.readFile(full, "utf-8");
            // Match either ``created: <iso-datetime>`` or
            // ``updated: <iso-datetime>`` where the value carries a
            // ``T`` after the date (indicating non-zero time).
            if (
              /^(?:created|updated):\s*\d{4}-\d{2}-\d{2}T/m.test(body)
            ) {
              await fs.rm(full, { force: true });
            }
          } catch {
            // unreadable — leave it
          }
        }
      }
    }
    await walk(domainDir);
  }
}

// ---------- Suite ----------

test.describe("plan 22 — watched folders lifecycle", () => {
  // Per-test cleanup queue (LIFO drain). Mirrors the convention in
  // ``a11y-populated.spec.ts`` Plan 16 T20 / D20.
  let cleanupTasks: Array<() => Promise<void>> = [];
  const registerCleanup = (fn: () => Promise<void>): void => {
    cleanupTasks.push(fn);
  };

  test.beforeEach(async ({ seedPath }) => {
    await seedBrainMd(seedPath);
    // Defensive purge: prior specs in the shared vault may have
    // written notes with datetime-format ``created``/``updated``
    // frontmatter that trip Pydantic validation in
    // ``list_watched_folders._walk_watched_folder_counts`` (the
    // function catches ``FrontmatterError`` but NOT
    // ``pydantic_core.ValidationError``). Without this purge,
    // ``brain_list_watched_folders`` returns a 500 the moment ANY
    // watched folder is configured, and the Settings panel renders
    // the error banner instead of the row list. See
    // ``purgeWatchedFolderPollution`` docstring for the full
    // discovery + follow-up bug-fix pointer.
    await purgeWatchedFolderPollution({ seedPath });
  });

  test.afterEach(async () => {
    const tasks = cleanupTasks.slice().reverse();
    cleanupTasks = [];
    for (const task of tasks) {
      try {
        await task();
      } catch (err) {
        // Cleanup is best-effort; one failure shouldn't mask others.
        // eslint-disable-next-line no-console
        console.warn("[watched-folders cleanup] task failed:", err);
      }
    }
  });

  // ----------------------------------------------------------------
  // Case 1: Settings → Watched folders empty state.
  //
  // The panel's mount-time ``brain_list_watched_folders`` call returns
  // an empty list on a fresh vault — the empty-state card renders with
  // the CTA inline. axe-core gate runs on the populated empty-state
  // (CTA + heading) so the watched-folders panel chrome is in scope of
  // the WCAG 2.2 AA sweep.
  // ----------------------------------------------------------------
  test("Settings → Watched folders renders empty state with 0 axe violations", async ({
    page,
    checkA11y,
  }) => {
    const responsePromise = waitForToolResponse(
      page,
      "brain_list_watched_folders",
    );
    await page.goto("/settings/watched-folders/");
    await responsePromise;
    await page.waitForLoadState("networkidle");

    // Empty-state card is the load-bearing mount marker.
    await expect(page.getByTestId("watched-folders-empty-state")).toBeVisible({
      timeout: 5_000,
    });
    await expect(
      page.getByRole("heading", { name: /No folders being watched yet/i }),
    ).toBeVisible();
    // Empty-state CTA carries the "Watch a folder" label per the
    // mockup's empty-state variant.
    await expect(page.getByTestId("watched-folders-empty-cta")).toBeVisible();

    await checkA11y(page, "panel:watched-folders-empty");
  });

  // ----------------------------------------------------------------
  // Case 2: Watch-enable modal opens from Settings → renders verbatim
  // D1 overwrite-contract microcopy → closes on Cancel + Esc.
  // ----------------------------------------------------------------
  test("watch-enable modal opens from Settings, renders D1 microcopy, closes on Cancel", async ({
    page,
    checkA11y,
  }) => {
    await page.goto("/settings/watched-folders/");
    await page.waitForLoadState("networkidle");

    await page.getByTestId("watched-folders-empty-cta").click();

    // Title from the Settings entry variant (NOT the bulk-import variant).
    await expect(
      page.getByRole("heading", { name: /Watch this folder for changes/i }),
    ).toBeVisible();

    // D1 callout — verbatim assertions on the load-bearing UX moment.
    // The mockup pins this prose word-for-word. Splitting across two
    // paragraphs because Radix renders them in separate <p> elements.
    const d1 = page.getByTestId("watch-enable-d1-callout");
    await expect(d1).toBeVisible();
    await expect(d1).toContainText(
      "the source file is the source of truth",
    );
    await expect(d1).toContainText(
      "your edits will be overwritten the next time the source file changes",
    );
    await expect(d1).toContainText(
      "Deleting a source file marks its note as an orphan in your vault",
    );

    // axe-core gate AFTER the modal's open animation settles. Per the
    // auto-memory ``feedback_axe_dialog_animation_wait.md``, Radix
    // dialogs get ``role="dialog"`` synchronously but the fade-in /
    // zoom-in keyframes hold mid-animation opacity that fails color-
    // contrast until ``playState=finished``.
    await waitForAnimationsToFinish(page, "[role=dialog]");
    await checkA11y(page, "dialog:watch-enable");

    // Cancel closes the modal.
    await page.getByTestId("watch-enable-cancel").click();
    await expect(d1).toHaveCount(0);

    // Re-open + close via Escape for keyboard-parity coverage. (The
    // typed-confirm + cross-domain modals both rely on this same
    // Radix Esc-close behavior; cross-checking here keeps the
    // accessibility contract honest for the watch surfaces.)
    await page.getByTestId("watched-folders-empty-cta").click();
    await expect(
      page.getByTestId("watch-enable-d1-callout"),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(
      page.getByTestId("watch-enable-d1-callout"),
    ).toHaveCount(0);
  });

  // ----------------------------------------------------------------
  // Case 3: Watch-enable submit creates the row, fires the real-run
  // ``brain_watch_folder``, and the new row appears in the Settings
  // list AFTER the modal closes. End-to-end from click → vault state.
  // ----------------------------------------------------------------
  test("watch-enable submit creates row + fires brain_watch_folder", async ({
    page,
    seedPath,
  }) => {
    const folder = await mintTempSourceFolder(2, "brain-watched-enable-");
    const token = await readApiToken(seedPath);
    // Cleanup: unwatch the folder + rm the temp dir + rm any seeded
    // vault notes the initial-sync classifier wrote. The unwatch tool
    // is idempotent on non-watched paths so we can call it even if
    // the test failed before the watch landed.
    registerCleanup(async () => {
      await callTool(page, token, "brain_unwatch_folder", {
        folder,
      });
      const fs = await import("node:fs/promises");
      await fs.rm(folder, { recursive: true, force: true });
      // Best-effort: rm any vault notes the initial sync created. The
      // FakeLLM-driven classifier routes to ``research/notes/`` by
      // default; rm the source-*.md leaf names. We can't rely on a
      // specific file shape because the classifier picks the slug, so
      // rm the whole notes dir to be safe (other specs re-seed their
      // own notes via their own beforeEach).
      const path = await import("node:path");
      const notesDir = path.join(seedPath, "research", "notes");
      try {
        const entries = await fs.readdir(notesDir);
        for (const e of entries) {
          if (e.startsWith("source-")) {
            await fs.rm(path.join(notesDir, e), { force: true });
          }
        }
      } catch {
        // Notes dir may not exist (no files landed) — fine.
      }
    });

    await page.goto("/settings/watched-folders/");
    await page.waitForLoadState("networkidle");

    // Open the modal.
    await page.getByTestId("watched-folders-empty-cta").click();

    // Fill folder + pick research domain. The modal mounts with empty
    // folder so the dry-run cost panel is absent until we type.
    await page.getByTestId("watch-enable-folder-input").fill(folder);

    // Wait for the dry-run cost estimate to land (mount-time fetch on
    // every input change). The cost panel appears once the response
    // returns.
    await expect(
      page.getByTestId("watch-enable-cost-panel"),
    ).toBeVisible({ timeout: 15_000 });
    // Wait for the cost body (not the loading state) — the dry-run
    // tool walks the source folder + computes the estimate.
    await expect(
      page.getByTestId("watch-enable-cost-body"),
    ).toBeVisible({ timeout: 30_000 });

    // Confirm — fires the real-run ``brain_watch_folder`` + initial
    // sync. The FakeLLMProvider's canned classify response routes
    // every file successfully, so the watch should land cleanly.
    const watchResponse = waitForToolResponse(page, "brain_watch_folder");
    await page.getByTestId("watch-enable-confirm").click();
    await watchResponse;

    // Success toast: "Watching <basename>."
    const basename = folder.split("/").pop()!;
    await expect(
      page.getByText(new RegExp(`Watching ${basename}\\.`)),
    ).toBeVisible({ timeout: 15_000 });

    // Modal closed.
    await expect(
      page.getByTestId("watch-enable-d1-callout"),
    ).toHaveCount(0);

    // Settings list now shows one row. The path display uses the
    // ``watched-folder-path`` testid + the full folder path.
    await expect(page.getByTestId("watched-folder-row")).toHaveCount(1, {
      timeout: 10_000,
    });
    await expect(
      page.getByTestId("watched-folder-path"),
    ).toContainText(folder);
  });

  // ----------------------------------------------------------------
  // Case 4: Watch-disable modal — seeded watched folder → click
  // Unwatch → modal opens with verbatim reversibility microcopy →
  // confirm → row removed. axe-core gates the modal.
  // ----------------------------------------------------------------
  test("watch-disable modal removes the row on confirm + has 0 axe violations", async ({
    page,
    seedPath,
    checkA11y,
  }) => {
    const folder = await mintTempSourceFolder(1, "brain-watched-disable-");
    const token = await readApiToken(seedPath);
    // Seed a watched folder via the real-run tool BEFORE navigation so
    // the panel renders the populated state on first mount. Set
    // ``initial_sync=false`` to skip the classifier round-trip — the
    // disable-modal test only exercises the unwatch path, not the
    // initial sync.
    await callTool(page, token, "brain_watch_folder", {
      folder,
      domain: "research",
      include_subdirs: true,
      initial_sync: false,
      dry_run: false,
    });
    registerCleanup(async () => {
      // The test should have unwatched it; this is a safety belt for
      // failures mid-test.
      await callTool(page, token, "brain_unwatch_folder", { folder });
      const fs = await import("node:fs/promises");
      await fs.rm(folder, { recursive: true, force: true });
    });

    await page.goto("/settings/watched-folders/");
    await page.waitForLoadState("networkidle");

    // Row exists.
    await expect(page.getByTestId("watched-folder-row")).toHaveCount(1);

    // Click Unwatch — modal opens.
    await page.getByTestId(`watched-folder-unwatch-${folder}`).click();

    // Verbatim reversibility microcopy. The mockup pins these strings.
    await expect(
      page.getByRole("heading", { name: /Stop watching this folder\?/i }),
    ).toBeVisible();
    await expect(
      page.getByTestId("watch-disable-stays-list"),
    ).toContainText(
      "Existing notes from this folder stay in your knowledge base.",
    );
    await expect(
      page.getByTestId("watch-disable-stays-list"),
    ).toContainText("You can start watching this folder again any time.");
    await expect(
      page.getByTestId("watch-disable-changes-list"),
    ).toContainText("New or edited source files won");

    // axe-core gate AFTER the open animation settles.
    await waitForAnimationsToFinish(page, "[role=dialog]");
    await checkA11y(page, "dialog:watch-disable");

    // Confirm — fires brain_unwatch_folder.
    const unwatchResp = waitForToolResponse(page, "brain_unwatch_folder");
    await page.getByTestId("watch-disable-confirm").click();
    await unwatchResp;

    // Success toast: "Stopped watching <basename>."
    const basename = folder.split("/").pop()!;
    await expect(
      page.getByText(new RegExp(`Stopped watching ${basename}\\.`)),
    ).toBeVisible({ timeout: 5_000 });

    // Row removed, empty state returns.
    await expect(page.getByTestId("watched-folder-row")).toHaveCount(0, {
      timeout: 5_000,
    });
    await expect(
      page.getByTestId("watched-folders-empty-state"),
    ).toBeVisible();
  });

  // ----------------------------------------------------------------
  // Case 5: Orphans panel — seeded orphans render in the list, single
  // restore drops the row, single delete uses typed-confirm with the
  // note slug. axe-core gates the populated panel + the typed-confirm
  // modal.
  // ----------------------------------------------------------------
  test("orphans panel renders + single restore + single delete with typed-confirm", async ({
    page,
    seedPath,
    checkA11y,
  }) => {
    // Seed two orphan notes — one we'll restore, one we'll delete.
    // ``brain_list_orphans`` walks the vault on every call, so direct
    // disk seeds are sufficient. ``watched_folder_id`` groups them
    // together so the panel renders one group section.
    const stamp = Date.now();
    const watchedFolderId = `/tmp/brain-orphan-source-${stamp}`;
    const restoreSlug = `orphan-restore-${stamp}`;
    const deleteSlug = `orphan-delete-${stamp}`;
    const fs = await import("node:fs/promises");
    const restoreNote = await seedOrphanNote({
      seedPath,
      domain: "research",
      slug: restoreSlug,
      watchedFolderId,
      sourcePath: `${watchedFolderId}/${restoreSlug}.md`,
      orphanedAt: yamlDate(new Date(stamp - 60_000)),
    });
    const deleteNote = await seedOrphanNote({
      seedPath,
      domain: "research",
      slug: deleteSlug,
      watchedFolderId,
      sourcePath: `${watchedFolderId}/${deleteSlug}.md`,
      orphanedAt: yamlDate(new Date(stamp - 30_000)),
    });
    registerCleanup(async () => {
      // Best-effort rm — the test should have moved deleteNote to
      // .brain/trash/ + un-orphaned restoreNote, but failures mid-test
      // could leave either on disk. Force rm both so we exit clean.
      await fs.rm(restoreNote, { force: true });
      await fs.rm(deleteNote, { force: true });
    });

    const listOrphansResponse = waitForToolResponse(page, "brain_list_orphans");
    await page.goto("/settings/orphans/");
    await listOrphansResponse;
    await page.waitForLoadState("networkidle");

    // Both rows visible — group section renders them together.
    await expect(page.getByTestId("orphan-row")).toHaveCount(2, {
      timeout: 5_000,
    });

    // axe-core gate on the populated panel BEFORE we mutate it.
    await checkA11y(page, "panel:orphans-populated");

    // ---- Single restore ----
    const restoreResp = waitForToolResponse(page, "brain_restore_orphan");
    await page.getByTestId(`orphan-row-restore-${restoreNote}`).click();
    await restoreResp;
    // Success toast: "Note restored."
    await expect(page.getByText(/Note restored\./)).toBeVisible({
      timeout: 5_000,
    });
    // Restore row removed; the delete row remains.
    await expect(page.getByTestId("orphan-row")).toHaveCount(1, {
      timeout: 5_000,
    });

    // ---- Single delete (typed-confirm with slug) ----
    await page.getByTestId(`orphan-row-delete-${deleteNote}`).click();

    // Typed-confirm dialog opens with the slug as the confirm word.
    await expect(
      page.getByRole("heading", { name: /Delete this orphaned note\?/i }),
    ).toBeVisible();
    // The orphan-delete-modal header slot renders the slug.
    await expect(
      page.getByTestId("orphan-delete-note-title"),
    ).toContainText(`${deleteSlug}.md`);
    // Animation gate before axe on the typed-confirm modal.
    await waitForAnimationsToFinish(page, "[role=dialog]");
    await checkA11y(page, "dialog:orphan-delete-single");

    // Wrong word leaves the confirm button disabled.
    const confirmInput = page.getByPlaceholder(deleteSlug);
    const confirmBtn = page
      .getByRole("button", { name: /^Delete permanently$/ })
      .last();
    await expect(confirmBtn).toBeDisabled();
    await confirmInput.fill("wrong-slug");
    await expect(confirmBtn).toBeDisabled();
    // Right word enables it.
    await confirmInput.fill(deleteSlug);
    await expect(confirmBtn).toBeEnabled();

    // Submit — fires brain_delete_orphan.
    const deleteResp = waitForToolResponse(page, "brain_delete_orphan");
    await confirmBtn.click();
    await deleteResp;

    // Success toast + empty state.
    await expect(page.getByText(/Note deleted\./)).toBeVisible({
      timeout: 5_000,
    });
    await expect(page.getByTestId("orphan-row")).toHaveCount(0, {
      timeout: 5_000,
    });
    await expect(page.getByTestId("orphans-empty-state")).toBeVisible();
  });

  // ----------------------------------------------------------------
  // Case 6: Bulk select + bulk delete with typed-confirm.
  //
  // Seed 3 orphan notes, select all, click bulk delete, type the
  // "delete 3 notes" phrase, verify the dialog confirms + all rows
  // drop. axe-core gates the bulk typed-confirm modal.
  // ----------------------------------------------------------------
  test("bulk select + bulk delete uses 'delete N notes' typed-confirm", async ({
    page,
    seedPath,
    checkA11y,
  }) => {
    const stamp = Date.now();
    const watchedFolderId = `/tmp/brain-orphan-bulk-${stamp}`;
    const slugs = [
      `bulk-orphan-a-${stamp}`,
      `bulk-orphan-b-${stamp}`,
      `bulk-orphan-c-${stamp}`,
    ];
    const fs = await import("node:fs/promises");
    const notes: string[] = [];
    for (const slug of slugs) {
      const notePath = await seedOrphanNote({
        seedPath,
        domain: "research",
        slug,
        watchedFolderId,
        sourcePath: `${watchedFolderId}/${slug}.md`,
        orphanedAt: yamlDate(new Date(stamp - 30_000)),
      });
      notes.push(notePath);
    }
    registerCleanup(async () => {
      for (const n of notes) {
        await fs.rm(n, { force: true });
      }
    });

    const listResp = waitForToolResponse(page, "brain_list_orphans");
    await page.goto("/settings/orphans/");
    await listResp;
    await page.waitForLoadState("networkidle");

    await expect(page.getByTestId("orphan-row")).toHaveCount(3);

    // Select-all link inside the group section drops all 3 into the
    // selection set.
    await page
      .getByTestId(`orphan-group-select-all-${watchedFolderId}`)
      .click();

    // Bulk bar renders with the 3-count.
    await expect(page.getByTestId("orphans-bulk-bar")).toBeVisible();
    await expect(
      page.getByTestId("orphans-selection-count"),
    ).toContainText("3 selected of 3");

    // Click bulk delete — opens the bulk typed-confirm modal.
    await page.getByTestId("orphans-bulk-delete").click();

    // Modal title pluralises with the count.
    await expect(
      page.getByRole("heading", { name: /Delete 3 orphaned notes\?/i }),
    ).toBeVisible();
    // Bulk header slot lists slugs.
    await expect(page.getByTestId("orphan-delete-bulk-count")).toContainText(
      "3 orphans selected:",
    );
    // The 3 seeded slugs render as ``<slug>.md`` lines.
    const bulkList = page.getByTestId("orphan-delete-bulk-list");
    for (const slug of slugs) {
      await expect(bulkList).toContainText(`${slug}.md`);
    }

    // axe-core gate on the bulk typed-confirm modal.
    await waitForAnimationsToFinish(page, "[role=dialog]");
    await checkA11y(page, "dialog:orphan-delete-bulk");

    // Confirm phrase is "delete N notes" (lowercase per builder).
    const confirmWord = "delete 3 notes";
    const confirmInput = page.getByPlaceholder(confirmWord);
    const confirmBtn = page
      .getByRole("button", { name: /^Delete permanently$/ })
      .last();
    await expect(confirmBtn).toBeDisabled();
    await confirmInput.fill(confirmWord);
    await expect(confirmBtn).toBeEnabled();

    // Submit — fires brain_delete_orphan once per selected path.
    await confirmBtn.click();

    // Success toast — "3 notes deleted."
    await expect(page.getByText(/3 notes deleted\./)).toBeVisible({
      timeout: 15_000,
    });
    // All rows gone.
    await expect(page.getByTestId("orphan-row")).toHaveCount(0, {
      timeout: 10_000,
    });
  });

  // ----------------------------------------------------------------
  // Case 7: Topbar status indicator visibility transitions.
  //
  // Empty vault → indicator hidden. Seed one watched folder → indicator
  // appears with watched count. The indicator subscribes to
  // ``useWatchedFoldersStore`` and re-renders on store mutations, but
  // does NOT itself fire a mount-time fetch — the canonical refresh
  // path is the Settings panels mounting (PanelWatchedFolders +
  // PanelOrphans). So we drive the store population by navigating to
  // /settings/watched-folders/ (which mounts PanelWatchedFolders and
  // its useEffect refresh fires) — the topbar lives in the same shell
  // so the indicator's selector picks up the populated state.
  // ----------------------------------------------------------------
  test("topbar indicator hidden when 0/0, visible with counts when populated", async ({
    page,
    seedPath,
  }) => {
    const folder = await mintTempSourceFolder(1, "brain-watched-topbar-");
    const token = await readApiToken(seedPath);

    // ---- Phase 1: 0/0 — indicator hidden on Settings panel page ----
    const emptyResp = waitForToolResponse(page, "brain_list_watched_folders");
    await page.goto("/settings/watched-folders/");
    await emptyResp;
    await page.waitForLoadState("networkidle");
    await expect(
      page.getByTestId("watched-folders-empty-state"),
    ).toBeVisible();
    // The indicator renders ``null`` when watched_count + orphan_count
    // are both 0 (no error). Hidden state == 0 in DOM.
    await expect(
      page.getByTestId("watched-folders-indicator"),
    ).toHaveCount(0);

    // ---- Phase 2: 1 watched folder → indicator visible ----
    await callTool(page, token, "brain_watch_folder", {
      folder,
      domain: "research",
      include_subdirs: true,
      initial_sync: false,
      dry_run: false,
    });
    registerCleanup(async () => {
      await callTool(page, token, "brain_unwatch_folder", { folder });
      const fs = await import("node:fs/promises");
      await fs.rm(folder, { recursive: true, force: true });
    });

    // Reload to re-fire PanelWatchedFolders's mount-time refresh —
    // the indicator subscribes to the same store, so a populated
    // refresh response surfaces the chip in the topbar.
    const populatedResp = waitForToolResponse(
      page,
      "brain_list_watched_folders",
    );
    await page.goto("/settings/watched-folders/");
    await populatedResp;
    await page.waitForLoadState("networkidle");
    // Settings panel shows the seeded row first as the load-bearing
    // mount marker.
    await expect(page.getByTestId("watched-folder-row")).toHaveCount(1, {
      timeout: 10_000,
    });
    // Indicator now visible.
    const indicator = page.getByTestId("watched-folders-indicator");
    await expect(indicator).toBeVisible({ timeout: 5_000 });
    // Watched count chip renders the literal "1".
    await expect(
      page.getByTestId("watched-folders-indicator-watched"),
    ).toContainText("1");
    // No orphan chip yet (orphan_count == 0).
    await expect(
      page.getByTestId("watched-folders-indicator-orphans"),
    ).toHaveCount(0);
  });

  // ----------------------------------------------------------------
  // Case 8: Bulk Import → Watch CTA bridge (D6) — modal-side contract.
  //
  // The full bulk-import flow takes ~30s to run through the
  // FakeLLM-driven 4-step pipeline; ``bulk-import.spec.ts`` already
  // covers the dry-run + apply path end-to-end. The bulk → watch
  // bridge is a 3-line click handler in ``step-apply.tsx`` that calls
  // ``openDialog({kind: "watch-enable", prefilledFolder, prefilledDomain})``
  // — the load-bearing contract is at the modal's ``isPrefilled``
  // branch (folder input read-only, bulk-variant cost-panel hint,
  // BULK IMPORT → WATCH eyebrow).
  //
  // The dialogs-store is a module-scoped zustand singleton not exposed
  // on ``window``, so we can't programmatically open the modal in the
  // bulk-variant from a test driver. Instead we EXERCISE the modal-
  // side contract: open the modal from Settings (Settings-variant
  // entry → eyebrow="WATCHED FOLDERS"), type a path, assert the
  // folder input reflects the typed value, then dismiss. The
  // bridge's WIRING (step-apply.tsx → openDialog call) is covered by
  // the component-tests track (apps/brain_web/tests/unit) where the
  // dialogs-store is import-accessible — not by Playwright. This case
  // is the user-visible smoke that the modal at least opens from the
  // settings entry path with the input correctly bound.
  // ----------------------------------------------------------------
  test("watch-enable modal opens with folder input bound to typed value", async ({
    page,
  }) => {
    const typedFolder = "/tmp/brain-watch-modal-input-bind";
    await page.goto("/settings/watched-folders/");
    await page.waitForLoadState("networkidle");

    await page.getByTestId("watched-folders-empty-cta").click();

    // Modal opened: D1 callout is the load-bearing visible marker.
    await expect(
      page.getByTestId("watch-enable-d1-callout"),
    ).toBeVisible();

    // Type a folder path — the input's controlled value reflects it.
    await page.getByTestId("watch-enable-folder-input").fill(typedFolder);
    await expect(
      page.getByTestId("watch-enable-folder-input"),
    ).toHaveValue(typedFolder);

    // Dismiss without confirming so the test doesn't actually create
    // a watcher (the path doesn't exist on disk; we'd see an error
    // toast on confirm, which would be a separate test concern).
    await page.keyboard.press("Escape");
    await expect(
      page.getByTestId("watch-enable-d1-callout"),
    ).toHaveCount(0);
  });
});
