import { describe, expect, test } from "vitest";

import { buildObsidianUri } from "@/lib/vault/obsidian-url";

/**
 * Plan 07 Task 18 — ``buildObsidianUri(vaultName, relativePath)``.
 *
 * Format: ``obsidian://open?vault=<vaultName>&file=<path>``. Both the
 * vault name and the file path are URL-encoded so whitespace and
 * punctuation survive handoff to Obsidian on both macOS and Windows
 * (where ``open --url`` / ``start`` differ on tolerance).
 */
describe("buildObsidianUri", () => {
  test("formats the URI with vault + file query params", () => {
    expect(
      buildObsidianUri("brain", "research/concepts/conflict-avoidance-tells.md"),
    ).toBe(
      "obsidian://open?vault=brain&file=research%2Fconcepts%2Fconflict-avoidance-tells.md",
    );
  });

  test("URL-encodes vault names with spaces", () => {
    expect(buildObsidianUri("my vault", "note.md")).toBe(
      "obsidian://open?vault=my%20vault&file=note.md",
    );
  });

  test("URL-encodes nested paths (forward slashes become %2F)", () => {
    expect(
      buildObsidianUri("brain", "work/entities/helios account.md"),
    ).toBe(
      "obsidian://open?vault=brain&file=work%2Fentities%2Fhelios%20account.md",
    );
  });
});
