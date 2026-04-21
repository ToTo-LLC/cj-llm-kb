import { describe, expect, test } from "vitest";

import { parseServerEvent, SCHEMA_VERSION } from "@/lib/ws/events";

describe("SCHEMA_VERSION", () => {
  test('is pinned to "2" post Plan 07 Task 5', () => {
    expect(SCHEMA_VERSION).toBe("2");
  });
});

describe("parseServerEvent", () => {
  test("schema_version + thread_loaded + turn_start pass through", () => {
    const v = parseServerEvent({ type: "schema_version", version: "2" });
    expect(v.type).toBe("schema_version");
    if (v.type === "schema_version") {
      expect(v.version).toBe("2");
    }

    const loaded = parseServerEvent({
      type: "thread_loaded",
      thread_id: "t1",
      mode: "ask",
      turn_count: 3,
    });
    if (loaded.type !== "thread_loaded") {
      throw new Error("wrong variant");
    }
    expect(loaded.thread_id).toBe("t1");
    expect(loaded.turn_count).toBe(3);

    const start = parseServerEvent({ type: "turn_start", turn_number: 1 });
    if (start.type !== "turn_start") throw new Error("wrong variant");
    expect(start.turn_number).toBe(1);
  });

  test("delta + tool_call + tool_result narrow correctly", () => {
    const d = parseServerEvent({ type: "delta", text: "hello" });
    if (d.type !== "delta") throw new Error("wrong variant");
    expect(d.text).toBe("hello");

    const tc = parseServerEvent({
      type: "tool_call",
      id: "tc-1",
      tool: "brain_search",
      arguments: { query: "foo" },
    });
    if (tc.type !== "tool_call") throw new Error("wrong variant");
    expect(tc.tool).toBe("brain_search");
    expect(tc.arguments).toEqual({ query: "foo" });

    const tr = parseServerEvent({
      type: "tool_result",
      id: "tc-1",
      data: { hits: [] },
    });
    if (tr.type !== "tool_result") throw new Error("wrong variant");
    expect(tr.id).toBe("tc-1");
    expect(tr.data).toEqual({ hits: [] });
  });

  test("cost_update carries cumulative_tokens_in (Plan 07 Task 3)", () => {
    const c = parseServerEvent({
      type: "cost_update",
      tokens_in: 10,
      tokens_out: 20,
      cost_usd: 0.001,
      cumulative_usd: 0.05,
      cumulative_tokens_in: 1234,
    });
    if (c.type !== "cost_update") throw new Error("wrong variant");
    expect(c.cumulative_tokens_in).toBe(1234);
    expect(c.cumulative_usd).toBeCloseTo(0.05);
  });

  test("patch_proposed + doc_edit_proposed (Plan 07 Task 5) narrow correctly", () => {
    const p = parseServerEvent({
      type: "patch_proposed",
      patch_id: "p-1",
      target_path: "research/notes/foo.md",
      reason: "new note",
    });
    if (p.type !== "patch_proposed") throw new Error("wrong variant");
    expect(p.patch_id).toBe("p-1");

    const e = parseServerEvent({
      type: "doc_edit_proposed",
      edits: [
        {
          op: "insert",
          anchor: { kind: "line", value: 12 },
          text: "new text",
        },
      ],
    });
    if (e.type !== "doc_edit_proposed") throw new Error("wrong variant");
    expect(e.edits).toHaveLength(1);
    expect(e.edits[0]?.op).toBe("insert");
    expect(e.edits[0]?.anchor.kind).toBe("line");
  });

  test("turn_end + cancelled + error narrow correctly", () => {
    const end = parseServerEvent({
      type: "turn_end",
      turn_number: 2,
      title: "Greetings",
    });
    if (end.type !== "turn_end") throw new Error("wrong variant");
    expect(end.title).toBe("Greetings");

    const endNull = parseServerEvent({
      type: "turn_end",
      turn_number: 3,
      title: null,
    });
    if (endNull.type !== "turn_end") throw new Error("wrong variant");
    expect(endNull.title).toBeNull();

    const cancelled = parseServerEvent({ type: "cancelled", turn_number: 2 });
    if (cancelled.type !== "cancelled") throw new Error("wrong variant");
    expect(cancelled.turn_number).toBe(2);

    const err = parseServerEvent({
      type: "error",
      code: "budget_exceeded",
      message: "no more spend",
      recoverable: false,
    });
    if (err.type !== "error") throw new Error("wrong variant");
    expect(err.recoverable).toBe(false);
  });

  test("rejects missing type, non-string type, and unknown type values", () => {
    expect(() => parseServerEvent({})).toThrow(/missing 'type'/);
    expect(() => parseServerEvent(null)).toThrow(/missing 'type'/);
    expect(() => parseServerEvent({ type: 42 })).toThrow(/must be a string/);
    expect(() => parseServerEvent({ type: "brand_new_event" })).toThrow(
      /unknown WS event type: brand_new_event/,
    );
  });
});
