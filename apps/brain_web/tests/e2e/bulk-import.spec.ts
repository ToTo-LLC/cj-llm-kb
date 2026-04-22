/**
 * Bulk import e2e — 4-step dry-run + apply.
 *
 * DEFERRED TO PLAN 07 TASK 25 SWEEP.
 *
 * Rationale: bulk import loops over the classification + ingestion path
 * per file, which hits FakeLLM N times. Same queue-priming blocker as
 * chat + ingest; compounded by the 4-step flow's state transitions which
 * are sensitive to race conditions between steps.
 *
 * Coverage today: bulk store unit tests
 * (``apps/brain_web/tests/unit/bulk-apply.test.ts``,
 * ``bulk-approve.test.ts``, ``bulk-store.test.ts``,
 * ``dry-run-table.test.tsx``) exercise the same state machine minus the
 * real HTTP round-trip.
 */
import { test } from "./fixtures";

test.describe.skip("bulk import", () => {
  test("pick folder → dry-run 5 rows → apply → summary", async () => {
    // TODO(plan-07 task 25): FakeLLM queue priming + a seeded 5-file folder.
  });
});
