import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * RenameDomainDialog (Plan 07 Task 20).
 *
 * Collects:
 *   - new slug (kebab-validated on input)
 *   - rewrite-wikilinks checkbox (default checked)
 *   - confirmation warning block with file count + atomic-via-UndoLog copy.
 *
 * Submit calls renameDomain({from, to, rewrite_wikilinks}).
 *
 * Copy correction (plan line 3606): atomic + undoable, not a staged patch.
 */

const { renameDomainMock, pushToastMock } = vi.hoisted(() => ({
  renameDomainMock: vi.fn(),
  pushToastMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  renameDomain: renameDomainMock,
}));

vi.mock("@/lib/state/system-store", () => ({
  useSystemStore: Object.assign(
    (selector: (s: { pushToast: typeof pushToastMock }) => unknown) =>
      selector({ pushToast: pushToastMock }),
    { getState: () => ({ pushToast: pushToastMock }) },
  ),
}));

import { RenameDomainDialog } from "@/components/dialogs/rename-domain-dialog";

beforeEach(() => {
  renameDomainMock.mockReset();
  pushToastMock.mockReset();
  renameDomainMock.mockResolvedValue({
    text: "",
    data: { from: "work", to: "work2", files_updated: 42 },
  });
});

describe("RenameDomainDialog", () => {
  test("slug input rejects spaces and capital letters (kebab-coerced)", async () => {
    const user = userEvent.setup();
    render(
      <RenameDomainDialog
        kind="rename-domain"
        domain={{ id: "work", name: "Work", count: 42 }}
        onClose={vi.fn()}
      />,
    );
    const input = document.getElementById(
      "rename-new-slug",
    ) as HTMLInputElement;
    await user.clear(input);
    await user.type(input, "New Work Stuff!");
    // Coerced: lowercase, spaces→hyphens, punctuation stripped.
    expect(input.value).toMatch(/^[a-z0-9-]*$/);
    expect(input.value).not.toMatch(/[A-Z ]/);
  });

  test("rewrite-wikilinks checkbox is default-checked", () => {
    render(
      <RenameDomainDialog
        kind="rename-domain"
        domain={{ id: "work", name: "Work", count: 42 }}
        onClose={vi.fn()}
      />,
    );
    const checkbox = screen.getByRole("checkbox", {
      name: /rewrite.*wikilinks/i,
    });
    expect(checkbox).toHaveAttribute("data-state", "checked");
  });

  test("warn block renders the file count and atomic-via-Undo copy", () => {
    render(
      <RenameDomainDialog
        kind="rename-domain"
        domain={{ id: "work", name: "Work", count: 42 }}
        onClose={vi.fn()}
      />,
    );
    const warn = screen.getByTestId("rename-warn");
    expect(warn).toHaveTextContent(/42/);
    // Corrected copy per plan line 3606.
    expect(warn).toHaveTextContent(/atomically/i);
    expect(warn).toHaveTextContent(/undo/i);
  });

  test("submit calls renameDomain({from, to, rewrite_wikilinks})", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <RenameDomainDialog
        kind="rename-domain"
        domain={{ id: "work", name: "Work", count: 42 }}
        onClose={onClose}
      />,
    );

    const input = document.getElementById(
      "rename-new-slug",
    ) as HTMLInputElement;
    await user.clear(input);
    await user.type(input, "work2");

    await user.click(screen.getByRole("button", { name: /rename domain/i }));

    await waitFor(() => {
      expect(renameDomainMock).toHaveBeenCalledTimes(1);
    });
    const args = renameDomainMock.mock.calls[0]![0] as {
      from: string;
      to: string;
      rewrite_frontmatter?: boolean;
    };
    expect(args.from).toBe("work");
    expect(args.to).toBe("work2");
    // Checkbox default-checked → rewrite flag true.
    expect(args.rewrite_frontmatter).toBe(true);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
