import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * Dry-run review step (Plan 07 Task 21).
 *
 * Renders the per-file review table backing Step 3 of bulk import. Users
 * toggle include, re-route files to a different domain, and see
 * confidence bars + status notes (duplicate, uncertain, personal).
 *
 * Five exercises:
 *   1. Renders one row per file from the store.
 *   2. Toggling include updates the summary count.
 *   3. Route dropdown updates file.classified in the store.
 *   4. Skipped rows render dim (data attribute hook).
 *   5. Duplicate rows surface the "duplicate" warn chip.
 */

const { listDomainsMock } = vi.hoisted(() => ({
  listDomainsMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  listDomains: listDomainsMock,
  bulkImport: vi.fn(),
  ingest: vi.fn(),
}));

import { StepDryRun } from "@/components/bulk/step-dry-run";
import { useBulkStore, type BulkFile } from "@/lib/state/bulk-store";

function mkFile(id: number, extra: Partial<BulkFile> = {}): BulkFile {
  return {
    id,
    name: `file-${id}.md`,
    type: "text",
    size: "4.2 KB",
    classified: "research",
    confidence: 0.92,
    include: true,
    ...extra,
  };
}

function seedFiles(files: BulkFile[]) {
  useBulkStore.setState({
    step: 3,
    folder: {
      path: "~/Archive/x",
      fileCount: files.length,
      picked: "just now",
    },
    domain: "auto",
    cap: 20,
    files,
    applying: false,
    applyIdx: 0,
    cancelled: false,
    done: false,
    results: { applied: [], failed: [], quarantined: [] },
  });
}

beforeEach(() => {
  listDomainsMock.mockReset();
  useBulkStore.setState({
    step: 1,
    folder: null,
    domain: "auto",
    cap: 20,
    files: [],
    applying: false,
    applyIdx: 0,
    cancelled: false,
    done: false,
    results: { applied: [], failed: [], quarantined: [] },
  });
});

describe("StepDryRun", () => {
  test("renders one row per file", () => {
    seedFiles([mkFile(1), mkFile(2), mkFile(3)]);
    render(<StepDryRun domains={["research", "work", "personal"]} />);
    const rows = screen.getAllByTestId("dry-row");
    expect(rows).toHaveLength(3);
    expect(screen.getByText("file-1.md")).toBeInTheDocument();
    expect(screen.getByText("file-2.md")).toBeInTheDocument();
    expect(screen.getByText("file-3.md")).toBeInTheDocument();
  });

  test("unchecking a row drops it from the included-count header", async () => {
    const user = userEvent.setup();
    seedFiles([mkFile(1), mkFile(2), mkFile(3)]);
    render(<StepDryRun domains={["research", "work", "personal"]} />);
    // Initial count: 3 of 3
    expect(
      screen.getByTestId("included-count").textContent,
    ).toMatch(/3\s*of\s*3/);
    const rows = screen.getAllByTestId("dry-row");
    // First row has the checkbox that corresponds to file 1.
    const cb = within(rows[0]).getByRole("checkbox");
    await user.click(cb);
    expect(useBulkStore.getState().files[0].include).toBe(false);
    expect(
      screen.getByTestId("included-count").textContent,
    ).toMatch(/2\s*of\s*3/);
  });

  test("route dropdown updates file.classified in the store", async () => {
    const user = userEvent.setup();
    seedFiles([mkFile(1, { classified: "research" })]);
    render(<StepDryRun domains={["research", "work", "personal"]} />);
    const rows = screen.getAllByTestId("dry-row");
    const select = within(rows[0]).getByRole("combobox") as HTMLSelectElement;
    await user.selectOptions(select, "work");
    expect(useBulkStore.getState().files[0].classified).toBe("work");
  });

  test("skipped rows render with the skipped data-attribute", () => {
    seedFiles([
      mkFile(1),
      mkFile(2, {
        classified: null,
        confidence: null,
        include: false,
        skip: "System file — ignored.",
      }),
    ]);
    render(<StepDryRun domains={["research", "work", "personal"]} />);
    const rows = screen.getAllByTestId("dry-row");
    expect(rows[1]).toHaveAttribute("data-skipped", "true");
    expect(
      within(rows[1]).getByText(/System file/i),
    ).toBeInTheDocument();
  });

  test("duplicate rows render the duplicate warn chip", () => {
    seedFiles([
      mkFile(1),
      mkFile(2, { duplicate: true }),
    ]);
    render(<StepDryRun domains={["research", "work", "personal"]} />);
    const rows = screen.getAllByTestId("dry-row");
    expect(
      within(rows[1]).getByText(/duplicate/i),
    ).toBeInTheDocument();
  });
});
