/**
 * Chat turn e2e — end-to-end WS round-trip via the composer.
 *
 * DEFERRED TO PLAN 07 TASK 25 SWEEP.
 *
 * Rationale: the chat pipeline requires a primed FakeLLMProvider queue
 * before the turn begins. In unit tests we queue a response on the
 * in-process ``ctx.llm`` directly; across a subprocess boundary there is
 * no HTTP endpoint to queue into, and ``FakeLLMProvider`` currently
 * raises ``RuntimeError`` the moment a turn starts against an empty
 * queue. Options we rejected for Task 23:
 *
 *   1. Add a ``POST /api/testing/queue_llm`` backdoor to brain_api —
 *      violates CLAUDE.md principle 1 (no surface only tests use).
 *   2. Monkey-patch FakeLLMProvider to return a canned "hello" for any
 *      unqueued request — changes production semantics (currently
 *      "empty queue = programmer error, raise loudly").
 *   3. Launch a dedicated e2e flavor of brain_api that auto-queues — too
 *      much infra for one test.
 *
 * Correct move: Task 25 sweep adds a queue-priming helper behind an
 * ``BRAIN_E2E_MODE=1`` env flag (gated, not a tool). Until then, this
 * flow is covered by the ChatSession unit + integration tests in
 * ``packages/brain_api/tests/test_ws_chat_*.py`` (16 tests) and the
 * ``useChatWs`` hook unit tests.
 */
import { test } from "./fixtures";

test.describe.skip("chat turn", () => {
  test("composer → turn_start → delta* → turn_end renders message", async () => {
    // TODO(plan-07 task 25): wire FakeLLM queue priming via BRAIN_E2E_MODE.
  });

  test("second turn auto-titles the thread", async () => {
    // TODO(plan-07 task 25): depends on queue priming above.
  });
});
