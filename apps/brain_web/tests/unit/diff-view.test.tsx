import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { DiffView } from "@/components/pending/diff-view";
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
