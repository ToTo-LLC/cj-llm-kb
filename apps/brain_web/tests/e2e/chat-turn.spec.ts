/**
 * Chat turn e2e — end-to-end WS round-trip via the composer.
 *
 * Plan 07 Task 25C: unskipped. The backend now runs with
 * ``BRAIN_E2E_MODE=1`` (set by ``start-backend-for-e2e.sh``) which makes
 * FakeLLMProvider return a canned chat response when the queue is empty.
 * We can therefore drive a turn from the browser without reaching into
 * the subprocess's LLM instance.
 *
 * We land the thread by navigating to ``/chat/e2e-chat-<id>`` so the WS
 * hook opens immediately (``/chat`` keeps the socket closed until a
 * thread exists). The FakeLLM greeting "Hello from FakeLLM. (E2E mode
 * default reply.)" streams as deltas and is asserted on the transcript.
 */
import { expect, test } from "./fixtures";

const FAKE_LLM_REPLY = "Hello from FakeLLM. (E2E mode default reply.)";

test.describe("chat turn", () => {
  // Seed BRAIN.md directly on disk so the root redirect doesn't bounce
  // a thread-route fetch through the setup wizard. Each spec is its own
  // file on disk; writing here idempotently is safe.
  test.beforeEach(async ({ seedPath }) => {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    await fs.writeFile(
      path.join(seedPath, "BRAIN.md"),
      "# BRAIN\n\nYou are brain. Maintain this vault carefully.\n",
      "utf-8",
    );
  });

  test("composer → turn_start → delta → turn_end renders assistant reply", async ({
    page,
  }) => {
    const threadId = `e2e-chat-${Date.now()}`;
    await page.goto(`/chat/${threadId}`);
    await page.waitForLoadState("networkidle");

    const composer = page.getByRole("textbox", { name: "Message brain" });
    await expect(composer).toBeVisible();
    await composer.fill("hello brain");

    const send = page.getByRole("button", { name: "Send" });
    await send.click();

    // The user turn appears optimistically first, then the assistant
    // streaming placeholder, then the canned reply streams in char by
    // char. We wait on the final accumulated text matching the FakeLLM
    // canned reply — whichever element carries the body.
    const assistant = page.locator('[data-role="brain"]').first();
    await expect(assistant).toContainText(FAKE_LLM_REPLY, {
      timeout: 20_000,
    });

    // User message is also in the transcript.
    const user = page.locator('[data-role="user"]').first();
    await expect(user).toContainText("hello brain");
  });
});
