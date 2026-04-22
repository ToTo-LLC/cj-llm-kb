/**
 * Ingest drag-drop e2e — upload file → classify → patch appears.
 *
 * DEFERRED TO PLAN 07 TASK 25 SWEEP.
 *
 * Rationale: the ingest pipeline calls FakeLLMProvider for classification
 * + summarization. Same queue-priming blocker as chat-turn.spec.ts — no
 * way to seed the queue from the Playwright process today. Task 25 ships
 * a BRAIN_E2E_MODE helper that can queue a canned classification for the
 * next ingest call.
 *
 * Coverage today: ingest tool unit tests in
 * ``packages/brain_core/tests/ingest/`` + the ``InboxScreen`` +
 * ``DropZone`` component tests in
 * ``apps/brain_web/tests/unit/source-row.test.tsx`` and friends.
 */
import { test } from "./fixtures";

test.describe.skip("ingest drag-drop", () => {
  test("drop file → In progress → done → patch in /pending", async () => {
    // TODO(plan-07 task 25): FakeLLM queue priming for classify + summarize.
  });
});
