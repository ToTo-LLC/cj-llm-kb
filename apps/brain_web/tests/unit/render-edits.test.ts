import { describe, expect, test } from "vitest";
import { render } from "@testing-library/react";
import * as React from "react";
import "@testing-library/jest-dom/vitest";

import { renderWithEdits } from "@/lib/draft/render-edits";
import type { DocEdit } from "@/lib/state/draft-store";

/**
 * renderWithEdits — pure function that turns doc body + pending edits
 * into a flat array of React nodes. The DocPanel calls this per
 * paragraph in its reading view. Three ops matter:
 *   - insert  → ``<span class="pending-edit">new</span>``
 *   - delete  → ``<del>old</del>``
 *   - replace → ``<span class="replace-with">old → <span class="pending-edit">new</span></span>``
 *
 * An empty edits array returns the body unchanged (single-string node).
 */

describe("renderWithEdits", () => {
  test("insert edit renders the new text wrapped in span.pending-edit", () => {
    const edits: DocEdit[] = [
      {
        op: "insert",
        anchor: { kind: "text", value: "body" },
        text: "inserted phrase",
      },
    ];
    const { container } = render(
      React.createElement(
        React.Fragment,
        null,
        ...renderWithEdits("some body text", edits),
      ),
    );
    const ins = container.querySelector("span.pending-edit");
    expect(ins).not.toBeNull();
    expect(ins?.textContent).toBe("inserted phrase");
  });

  test("delete edit renders the old text wrapped in <del>", () => {
    const edits: DocEdit[] = [
      {
        op: "delete",
        anchor: { kind: "text", value: "doomed" },
        text: "doomed",
      },
    ];
    const { container } = render(
      React.createElement(
        React.Fragment,
        null,
        ...renderWithEdits("keep the doomed text please", edits),
      ),
    );
    const del = container.querySelector("del");
    expect(del).not.toBeNull();
    expect(del?.textContent).toBe("doomed");
  });

  test("replace edit renders span.replace-with + nested span.pending-edit", () => {
    const edits: DocEdit[] = [
      {
        op: "replace",
        anchor: { kind: "text", value: "old phrase" },
        text: "old phrase\u0000new phrase",
      },
    ];
    const { container } = render(
      React.createElement(
        React.Fragment,
        null,
        ...renderWithEdits("start old phrase end", edits),
      ),
    );
    const outer = container.querySelector("span.replace-with");
    expect(outer).not.toBeNull();
    const inner = outer?.querySelector("span.pending-edit");
    expect(inner).not.toBeNull();
    expect(inner?.textContent).toBe("new phrase");
    // The old text still shows up inside the replace-with span, so the
    // reader can see what's being swapped.
    expect(outer?.textContent).toContain("old phrase");
  });

  test("empty edits array returns the body unchanged (no edit spans)", () => {
    const { container } = render(
      React.createElement(
        React.Fragment,
        null,
        ...renderWithEdits("untouched body text", []),
      ),
    );
    expect(container.textContent).toBe("untouched body text");
    expect(container.querySelector("span.pending-edit")).toBeNull();
    expect(container.querySelector("del")).toBeNull();
    expect(container.querySelector("span.replace-with")).toBeNull();
  });
});
