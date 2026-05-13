import { describe, expect, test, beforeEach } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";

/**
 * Plan 26 T4 — per-file filename microcopy under the apply progress bar.
 *
 * The component reads ``currentFile`` from the bulk-store and renders
 * an ``apply-current-file`` ``<p>`` below the progress bar when the
 * value is non-null. Paths over 60 chars are truncated with a leading
 * ellipsis (inline duplicate of the walk-interstitial helper, per
 * D10 — rule-of-three not met yet).
 *
 * Three exercises:
 *   1. Non-null ``currentFile`` renders the microcopy element.
 *   2. Null ``currentFile`` omits the element entirely.
 *   3. A path > 60 chars renders truncated with the leading ellipsis +
 *      keeps the full path in the ``title`` attribute (hover tooltip).
 */

import { StepApply } from "@/components/bulk/step-apply";
import { useBulkStore } from "@/lib/state/bulk-store";
import type { BulkFile } from "@/lib/state/bulk-store";

const SAMPLE_FILE: BulkFile = {
  id: 1,
  name: "foo.md",
  type: "text",
  size: "1 KB",
  classified: null,
  confidence: null,
  include: true,
};

function resetStore(overrides: Partial<Parameters<typeof useBulkStore.setState>[0]> = {}): void {
  useBulkStore.setState({
    step: 4,
    folder: { path: "/tmp/foo", fileCount: 1, picked: "just now" },
    domain: "auto",
    cap: 20,
    files: [SAMPLE_FILE],
    applying: true,
    applyIdx: 0,
    cancelled: false,
    done: false,
    results: { applied: [], failed: [], quarantined: [] },
    phase: "applying",
    walkPath: null,
    walkStartedAt: null,
    applyStartedAt: Date.now(),
    currentFile: null,
    ...overrides,
  });
}

describe("step-apply per-file filename display (Plan 26 T4)", () => {
  beforeEach(() => {
    resetStore();
  });

  test("renders apply-current-file element when currentFile is non-null", () => {
    resetStore({ currentFile: "research/papers/foo.pdf" });

    render(<StepApply />);

    const el = screen.getByTestId("apply-current-file");
    expect(el).toBeInTheDocument();
    expect(el).toHaveTextContent("Current: research/papers/foo.pdf");
  });

  test("omits apply-current-file element entirely when currentFile is null", () => {
    resetStore({ currentFile: null });

    render(<StepApply />);

    expect(screen.queryByTestId("apply-current-file")).not.toBeInTheDocument();
  });

  test("truncates paths > 60 chars with leading ellipsis and preserves full path in title", () => {
    // 80 chars — definitively longer than the 60-char limit.
    const longPath =
      "a/very/deeply/nested/folder/structure/leading/to/an/eventually/important/file.pdf";
    expect(longPath.length).toBeGreaterThan(60);

    resetStore({ currentFile: longPath });

    render(<StepApply />);

    const el = screen.getByTestId("apply-current-file");
    // Leading ellipsis present.
    expect(el.textContent).toMatch(/^Current: …/);
    // The visible content keeps the last 59 chars of the path (60 total
    // including the ellipsis), so the leaf filename remains readable.
    expect(el.textContent).toContain("file.pdf");
    // The ``title`` attribute preserves the full path for hover/AT.
    expect(el).toHaveAttribute("title", longPath);
  });
});
