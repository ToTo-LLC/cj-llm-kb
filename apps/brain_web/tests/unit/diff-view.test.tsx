import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { DiffView, lcsDiff, synthesizeDiff } from "@/components/pending/diff-view";
import type { DiffLine } from "@/components/pending/diff-view";

/**
 * DiffView (Plan 07 Task 16) — read-only line-diff renderer. The backend
 * PatchSet does not carry a precomputed unified diff on edits (it ships
 * ``{path, old, new}``), so the pending screen synthesizes the lines
 * elsewhere (see ``synthesizeDiff`` in ``diff-view.tsx``) and hands them
 * here as ``DiffLine[]`` for presentation. That separation is what these
 * tests pin down.
 *
 * Each line carries:
 *   type: "add" | "del" | "ctx"
 *   n: number (gutter line number, 1-indexed)
 *   code: string
 */

function lines(input: Array<[DiffLine["type"], number, string]>): DiffLine[] {
  return input.map(([type, n, code]) => ({ type, n, code }));
}

describe("DiffView", () => {
  test("add lines carry the diff-add class tag", () => {
    const { container } = render(
      <DiffView
        targetPath="research/notes/foo.md"
        lines={lines([
          ["add", 1, "# New note"],
          ["add", 2, "body"],
        ])}
      />,
    );
    const addRows = container.querySelectorAll(".diff-line.add");
    expect(addRows.length).toBe(2);
  });

  test("del lines carry the diff-del class tag", () => {
    const { container } = render(
      <DiffView
        targetPath="research/notes/foo.md"
        lines={lines([
          ["del", 1, "old line"],
          ["add", 1, "new line"],
        ])}
      />,
    );
    const delRows = container.querySelectorAll(".diff-line.del");
    expect(delRows.length).toBe(1);
  });

  test("ctx (context) lines carry the diff-ctx class tag", () => {
    const { container } = render(
      <DiffView
        targetPath="research/notes/foo.md"
        lines={lines([
          ["ctx", 1, "unchanged line"],
          ["add", 2, "added"],
        ])}
      />,
    );
    const ctxRows = container.querySelectorAll(".diff-line.ctx");
    expect(ctxRows.length).toBe(1);
  });

  test("gutter line numbers render on each row", () => {
    render(
      <DiffView
        targetPath="research/notes/foo.md"
        lines={lines([
          ["add", 1, "alpha"],
          ["add", 2, "beta"],
          ["add", 3, "gamma"],
        ])}
      />,
    );
    // The gutter is the line number rendered alongside the code. Each row
    // tags it with role="rowheader" so screen readers announce it.
    const gutterOnes = screen.getAllByText("1");
    const gutterTwos = screen.getAllByText("2");
    const gutterThrees = screen.getAllByText("3");
    expect(gutterOnes.length).toBeGreaterThanOrEqual(1);
    expect(gutterTwos.length).toBeGreaterThanOrEqual(1);
    expect(gutterThrees.length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// LCS diff (issue #15) — replaces the prior naive line-by-line zip that
// mislabeled mid-document insertions as "everything from here changed".
// ---------------------------------------------------------------------------

describe("lcsDiff (issue #15)", () => {
  test("identical sequences are all context", () => {
    const out = lcsDiff(["a", "b", "c"], ["a", "b", "c"]);
    expect(out).toEqual([
      { type: "ctx", n: 1, code: "a" },
      { type: "ctx", n: 2, code: "b" },
      { type: "ctx", n: 3, code: "c" },
    ]);
  });

  test("single-line insertion in the middle keeps surrounding ctx", () => {
    // OLD: a, b, c
    // NEW: a, X, b, c  → b and c stay as ctx; X is the only add.
    const out = lcsDiff(["a", "b", "c"], ["a", "X", "b", "c"]);
    expect(out).toEqual([
      { type: "ctx", n: 1, code: "a" },
      { type: "add", n: 2, code: "X" },
      { type: "ctx", n: 2, code: "b" },
      { type: "ctx", n: 3, code: "c" },
    ]);
  });

  test("single-line deletion in the middle keeps surrounding ctx", () => {
    // OLD: a, b, c
    // NEW: a, c        → b is the only del.
    const out = lcsDiff(["a", "b", "c"], ["a", "c"]);
    expect(out).toEqual([
      { type: "ctx", n: 1, code: "a" },
      { type: "del", n: 2, code: "b" },
      { type: "ctx", n: 3, code: "c" },
    ]);
  });

  test("replacement reads as del followed by add at the same gutter region", () => {
    // OLD: a, b, c
    // NEW: a, X, c     → b → X. Surrounding lines stay ctx.
    const out = lcsDiff(["a", "b", "c"], ["a", "X", "c"]);
    expect(out).toEqual([
      { type: "ctx", n: 1, code: "a" },
      { type: "del", n: 2, code: "b" },
      { type: "add", n: 2, code: "X" },
      { type: "ctx", n: 3, code: "c" },
    ]);
  });

  test("disjoint changes preserve ctx between them", () => {
    // OLD: a, b, c, d, e
    // NEW: a, X, c, Y, e   → two independent changes, three ctx lines.
    const out = lcsDiff(
      ["a", "b", "c", "d", "e"],
      ["a", "X", "c", "Y", "e"],
    );
    const ctxLines = out.filter((l) => l.type === "ctx").map((l) => l.code);
    expect(ctxLines).toEqual(["a", "c", "e"]);
    expect(out.filter((l) => l.type === "add").map((l) => l.code)).toEqual([
      "X",
      "Y",
    ]);
    expect(out.filter((l) => l.type === "del").map((l) => l.code)).toEqual([
      "b",
      "d",
    ]);
  });

  test("empty old produces all-add", () => {
    const out = lcsDiff([], ["a", "b"]);
    expect(out).toEqual([
      { type: "add", n: 1, code: "a" },
      { type: "add", n: 2, code: "b" },
    ]);
  });

  test("empty new produces all-del", () => {
    const out = lcsDiff(["a", "b"], []);
    expect(out).toEqual([
      { type: "del", n: 1, code: "a" },
      { type: "del", n: 2, code: "b" },
    ]);
  });

  test("synthesizeDiff routes edits through the LCS pass", () => {
    // The naive prior implementation would have marked b and c as both
    // ``del + add`` because it zipped index-by-index. LCS keeps c as ctx.
    const patchset = {
      edits: [
        {
          path: "research/notes/foo.md",
          old: "a\nb\nc",
          new: "a\nX\nc",
        },
      ],
    };
    const out = synthesizeDiff(patchset, "research/notes/foo.md");
    const ctxCodes = out
      .filter((l) => l.type === "ctx")
      .map((l) => l.code);
    expect(ctxCodes).toContain("a");
    expect(ctxCodes).toContain("c");
  });
});
