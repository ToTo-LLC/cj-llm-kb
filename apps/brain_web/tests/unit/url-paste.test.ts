import { describe, expect, test, vi } from "vitest";

/**
 * URL / paste helpers (Plan 07 Task 17).
 *
 * Two pure helpers drive the global paste listener: ``shouldIngest`` is
 * the noise filter — accept URLs and plain text over 50 chars, reject
 * everything shorter. ``triggerIngest`` is the action — calls the typed
 * ``ingest`` tool with the pasted text as the source.
 *
 * Tests keep these as pure functions (no DOM events) per the plan's
 * testing note: the global ``document.addEventListener("paste", ...)``
 * registration is covered by Playwright (Task 23).
 */

const { ingestMock } = vi.hoisted(() => ({
  ingestMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  ingest: ingestMock,
}));

import { shouldIngest, triggerIngest } from "@/lib/ingest/url-paste";

describe("shouldIngest", () => {
  test("URL paste returns true", () => {
    expect(shouldIngest("https://example.com/article")).toBe(true);
    expect(shouldIngest("http://example.com")).toBe(true);
    // Surrounding whitespace doesn't defeat URL detection.
    expect(shouldIngest("  https://example.com/with-whitespace  ")).toBe(true);
  });

  test("plain text over 50 chars returns true (long-text ingest path)", () => {
    const long =
      "This is a sufficiently long pasted snippet of prose that should be treated as ingestible content worth remembering.";
    expect(long.length).toBeGreaterThan(50);
    expect(shouldIngest(long)).toBe(true);
  });

  test("short plain-text returns false (noise filter)", () => {
    expect(shouldIngest("")).toBe(false);
    expect(shouldIngest("hello world")).toBe(false);
    expect(shouldIngest("a short snippet under fifty chars")).toBe(false);
  });
});

describe("triggerIngest", () => {
  test("forwards the pasted text as ``source`` to the ingest tool", async () => {
    ingestMock.mockResolvedValue({ text: "", data: { patch_id: "p-9" } });
    await triggerIngest("https://example.com/article");
    expect(ingestMock).toHaveBeenCalledWith({
      source: "https://example.com/article",
    });
  });
});
