import { describe, expect, test, beforeEach } from "vitest";
import "@testing-library/jest-dom/vitest";

import { useChatStore } from "@/lib/state/chat-store";

/**
 * Chat-store reducers driven by WS events. Plan 07 Task 14.
 *
 * The store is NOT per-thread — ``clearTranscript()`` runs on every
 * thread switch, then WS events repopulate. One global shape; one
 * active thread at a time. See the plan's "Per-thread isolation" note.
 *
 * Each test resets the store via ``useChatStore.setState`` to the
 * known-initial shape so cross-test state doesn't leak (same pattern as
 * app-store / system-store tests).
 */

function resetStore() {
  useChatStore.setState({
    transcript: [],
    streaming: false,
    streamingText: "",
    currentTurn: 0,
    cumulativeTokensIn: 0,
  });
}

describe("useChatStore", () => {
  beforeEach(() => {
    resetStore();
  });

  test("onTurnStart appends a user msg and an empty-assistant msg; streaming flips on", () => {
    const { onTurnStart, sendUserMessage } = useChatStore.getState();
    // sendUserMessage is the optimistic local append (the WS send itself
    // lands in Task 15). Exercise it first so the user turn has a body.
    sendUserMessage("tell me about silent buyers");
    onTurnStart({ type: "turn_start", turn_number: 1 });

    const { transcript, streaming } = useChatStore.getState();
    // Two messages: user (from sendUserMessage) + empty assistant placeholder
    // created by onTurnStart. Order matters — user goes first.
    expect(transcript).toHaveLength(2);
    expect(transcript[0].role).toBe("user");
    expect(transcript[0].body).toBe("tell me about silent buyers");
    expect(transcript[1].role).toBe("brain");
    expect(transcript[1].body).toBe("");
    expect(transcript[1].isStreaming).toBe(true);
    expect(streaming).toBe(true);
  });

  test("onDelta accumulates into streamingText (does NOT touch assistant.body until turn_end)", () => {
    const { onTurnStart, onDelta } = useChatStore.getState();
    onTurnStart({ type: "turn_start", turn_number: 1 });
    onDelta({ type: "delta", text: "Hello " });
    onDelta({ type: "delta", text: "world" });
    onDelta({ type: "delta", text: "." });

    const { streamingText, transcript } = useChatStore.getState();
    expect(streamingText).toBe("Hello world.");
    // Body stays empty until turn_end commits it — keeps streaming render
    // cheap (we read streamingText for the last message during streaming).
    expect(transcript[transcript.length - 1].body).toBe("");
  });

  test("onToolCall appends the call to the assistant message's toolCalls array", () => {
    const { onTurnStart, onToolCall, onToolResult } = useChatStore.getState();
    onTurnStart({ type: "turn_start", turn_number: 1 });
    onToolCall({
      type: "tool_call",
      id: "tc-1",
      tool: "brain_search",
      arguments: { query: "silent-buyer" },
    });
    onToolResult({
      type: "tool_result",
      id: "tc-1",
      data: {
        hits: [
          { path: "research/buyers.md", snippet: "…", score: 0.87 },
        ],
      },
    });

    const assistant = useChatStore.getState().transcript.at(-1)!;
    expect(assistant.toolCalls).toHaveLength(1);
    expect(assistant.toolCalls![0].tool).toBe("brain_search");
    expect(assistant.toolCalls![0].args).toEqual({ query: "silent-buyer" });
    // result merged by id
    const hits = (assistant.toolCalls![0].result as { hits: unknown[] }).hits;
    expect(hits).toHaveLength(1);
  });

  test("onPatchProposed sets proposedPatch on the current assistant msg", () => {
    const { onTurnStart, onPatchProposed } = useChatStore.getState();
    onTurnStart({ type: "turn_start", turn_number: 1 });
    onPatchProposed({
      type: "patch_proposed",
      patch_id: "p-99",
      target_path: "research/notes/silent-buyer.md",
      reason: "new synthesis",
    });

    const assistant = useChatStore.getState().transcript.at(-1)!;
    expect(assistant.proposedPatch).toBeDefined();
    expect(assistant.proposedPatch!.patchId).toBe("p-99");
    expect(assistant.proposedPatch!.target).toBe(
      "research/notes/silent-buyer.md",
    );
  });

  test("onTurnEnd commits streamingText to assistant.body and flips streaming=false", () => {
    const { onTurnStart, onDelta, onTurnEnd } = useChatStore.getState();
    onTurnStart({ type: "turn_start", turn_number: 1 });
    onDelta({ type: "delta", text: "Here is a full answer." });
    onTurnEnd({ type: "turn_end", turn_number: 1, title: "first-thread" });

    const state = useChatStore.getState();
    expect(state.streaming).toBe(false);
    const assistant = state.transcript.at(-1)!;
    expect(assistant.body).toBe("Here is a full answer.");
    expect(assistant.isStreaming).toBe(false);
    // streamingText is reset so the next turn starts clean.
    expect(state.streamingText).toBe("");
  });
});
