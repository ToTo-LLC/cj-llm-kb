/**
 * Patch approval e2e — list → detail → approve → undo.
 *
 * DEFERRED TO PLAN 07 TASK 25 SWEEP.
 *
 * Rationale: approving a patch triggers a real vault mutation through
 * ``VaultWriter``. The seeded temp vault is shared across the Playwright
 * run (see playwright.config.ts), so a successful approve here persists
 * into the a11y sweep and the setup-wizard spec, making the suite
 * order-dependent. Task 25 will either (a) per-spec vault seeds via a
 * before-hook restart of brain_api, or (b) a ``brain_admin_reset`` gated
 * on ``BRAIN_E2E_MODE=1``.
 *
 * Coverage today: PendingPatchStore has 100% unit coverage in
 * ``packages/brain_core/tests/chat/test_pending.py`` and the HTTP surface
 * is exercised by ``packages/brain_api/tests/test_patches_*.py``.
 */
import { test } from "./fixtures";

test.describe.skip("patch approval", () => {
  test("seeded patch → approve → toast → undo", async () => {
    // TODO(plan-07 task 25): per-spec vault isolation.
  });
});
