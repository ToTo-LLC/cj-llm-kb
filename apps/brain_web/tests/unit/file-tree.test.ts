import { describe, expect, test, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";
import * as React from "react";

/**
 * Shell-less next/navigation mock — FileTree links navigate via
 * ``<Link>`` which we render as anchors, and opens search via a
 * prop callback.
 */
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
}));

import { FileTree, type FileTreeNote } from "@/components/browse/file-tree";

const NOTES: FileTreeNote[] = [
  {
    path: "research/concepts/conflict-avoidance-tells.md",
    title: "conflict-avoidance-tells",
    domain: "research",
    folder: "concepts",
  },
  {
    path: "research/notes/fisher-ury-interests.md",
    title: "fisher-ury-interests",
    domain: "research",
    folder: "notes",
  },
  {
    path: "work/entities/helios-account.md",
    title: "helios-account",
    domain: "work",
    folder: "entities",
  },
  {
    path: "personal/notes/private-thoughts.md",
    title: "private-thoughts",
    domain: "personal",
    folder: "notes",
  },
];

describe("FileTree", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("groups notes by domain under a domain header", () => {
    render(
      React.createElement(FileTree, {
        notes: NOTES,
        scope: ["research", "work"],
        activePath: null,
        onOpenSearch: vi.fn(),
      }),
    );
    // Each scoped domain has a header.
    expect(screen.getByTestId("domain-header-research")).toBeInTheDocument();
    expect(screen.getByTestId("domain-header-work")).toBeInTheDocument();
    // All notes under research are rendered.
    expect(screen.getByText("conflict-avoidance-tells")).toBeInTheDocument();
    expect(screen.getByText("fisher-ury-interests")).toBeInTheDocument();
    // Note under work.
    expect(screen.getByText("helios-account")).toBeInTheDocument();
  });

  test("clicking a folder toggles (collapses) its children", async () => {
    const user = userEvent.setup();
    render(
      React.createElement(FileTree, {
        notes: NOTES,
        scope: ["research", "work"],
        activePath: null,
        onOpenSearch: vi.fn(),
      }),
    );
    const folderButton = screen.getByRole("button", {
      name: /concepts folder/i,
    });
    // Child visible initially.
    expect(screen.getByText("conflict-avoidance-tells")).toBeInTheDocument();
    await user.click(folderButton);
    // After collapse, the child is gone from the DOM.
    expect(screen.queryByText("conflict-avoidance-tells")).not.toBeInTheDocument();
    // Re-expand restores it.
    await user.click(folderButton);
    expect(screen.getByText("conflict-avoidance-tells")).toBeInTheDocument();
  });

  test("active node gets data-active='true'", () => {
    render(
      React.createElement(FileTree, {
        notes: NOTES,
        scope: ["research", "work"],
        activePath: "research/notes/fisher-ury-interests.md",
        onOpenSearch: vi.fn(),
      }),
    );
    const active = screen.getByTestId(
      "tree-node-research/notes/fisher-ury-interests.md",
    );
    expect(active).toHaveAttribute("data-active", "true");
    // A non-active sibling is not active.
    const other = screen.getByTestId(
      "tree-node-research/concepts/conflict-avoidance-tells.md",
    );
    expect(other).toHaveAttribute("data-active", "false");
  });

  test("personal domain shows lock + hidden-by-default label when scope excludes it", () => {
    render(
      React.createElement(FileTree, {
        notes: NOTES,
        scope: ["research", "work"],
        activePath: null,
        onOpenSearch: vi.fn(),
      }),
    );
    // Personal domain header still appears so the user knows the domain exists,
    // but its notes are hidden and a dim "hidden by default" label is shown.
    const personalHeader = screen.getByTestId("domain-header-personal");
    expect(personalHeader).toBeInTheDocument();
    // The note under personal is NOT rendered because scope excludes it.
    expect(screen.queryByText("private-thoughts")).not.toBeInTheDocument();
    // Placeholder label visible.
    expect(screen.getByText(/hidden by default/i)).toBeInTheDocument();
  });
});
