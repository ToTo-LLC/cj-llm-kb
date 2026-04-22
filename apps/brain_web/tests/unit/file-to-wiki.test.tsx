import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * FileToWikiDialog (Plan 07 Task 20).
 *
 * Promotes a chat assistant message into a curated vault note. Flow:
 *   1. Pick a note type (source / concept / entity / synthesis).
 *   2. Path auto-builds from domain + subdir + optional date prefix + slug.
 *   3. Collision detection via a mocked readNote (404-tolerant).
 *   4. Preview renders frontmatter + first 3 paragraphs of the msg body.
 *   5. Submit calls proposeNote with the built path.
 *
 * All external tool calls are mocked so the test drives the UI directly.
 */

const { proposeNoteMock, readNoteMock, listDomainsMock, pushToastMock } =
  vi.hoisted(() => ({
    proposeNoteMock: vi.fn(),
    readNoteMock: vi.fn(),
    listDomainsMock: vi.fn(),
    pushToastMock: vi.fn(),
  }));

vi.mock("@/lib/api/tools", () => ({
  proposeNote: proposeNoteMock,
  readNote: readNoteMock,
  listDomains: listDomainsMock,
}));

vi.mock("@/lib/state/system-store", () => ({
  useSystemStore: Object.assign(
    (selector: (s: { pushToast: typeof pushToastMock }) => unknown) =>
      selector({ pushToast: pushToastMock }),
    { getState: () => ({ pushToast: pushToastMock }) },
  ),
}));

import { ApiError } from "@/lib/api/types";
import { FileToWikiDialog } from "@/components/dialogs/file-to-wiki-dialog";

const MSG = {
  body: "First paragraph about the silent buyer pattern.\n\nSecond paragraph goes into specifics.\n\nThird paragraph wraps up with a [[link]].\n\nFourth paragraph gets trimmed from preview.",
  threadId: "t-1",
};

beforeEach(() => {
  proposeNoteMock.mockReset();
  readNoteMock.mockReset();
  listDomainsMock.mockReset();
  pushToastMock.mockReset();

  listDomainsMock.mockResolvedValue({
    text: "",
    data: { domains: ["research", "work", "personal"] },
  });
  // Default: collision-free.
  readNoteMock.mockRejectedValue(
    new ApiError(404, "not_found", null, "note not found"),
  );
  proposeNoteMock.mockResolvedValue({
    text: "staged",
    data: { patch_id: "p-new", target_path: "" },
  });
});

describe("FileToWikiDialog", () => {
  test("note-type switch swaps the subdir per SUBDIR_BY_TYPE", async () => {
    const user = userEvent.setup();
    render(
      <FileToWikiDialog
        kind="file-to-wiki"
        msg={MSG}
        threadId="t-1"
        defaultDomain="research"
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    // Wait for domains to load.
    await waitFor(() => expect(listDomainsMock).toHaveBeenCalled());

    // Default type is "synthesis" per the design — path contains /synthesis/.
    expect(await screen.findByTestId("ftw-path")).toHaveTextContent(
      /\/synthesis\//,
    );

    // Switch to "Concept".
    await user.click(screen.getByRole("radio", { name: /concept/i }));
    expect(screen.getByTestId("ftw-path")).toHaveTextContent(/\/concepts\//);

    // Switch to "Entity" (was "Person" in v3 — delta-v2 V1 fix).
    await user.click(screen.getByRole("radio", { name: /entity/i }));
    expect(screen.getByTestId("ftw-path")).toHaveTextContent(/\/entities\//);

    // Switch to "Source".
    await user.click(screen.getByRole("radio", { name: /source/i }));
    expect(screen.getByTestId("ftw-path")).toHaveTextContent(/\/sources\//);
  });

  test("slug input is kebab-coerced on change", async () => {
    const user = userEvent.setup();
    render(
      <FileToWikiDialog
        kind="file-to-wiki"
        msg={MSG}
        threadId="t-1"
        defaultDomain="research"
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() => expect(listDomainsMock).toHaveBeenCalled());

    const slugInput = screen.getByLabelText(/slug/i) as HTMLInputElement;
    await user.clear(slugInput);
    await user.type(slugInput, "Hello World Example!");

    // Should be coerced: lowercase, spaces→hyphens, punctuation stripped.
    expect(slugInput.value).toMatch(/^[a-z0-9-]+$/);
    expect(slugInput.value).toContain("hello");
    expect(slugInput.value).toContain("world");
  });

  test("collision warning surfaces when readNote returns 200", async () => {
    // Override default: readNote resolves → collision detected.
    readNoteMock.mockResolvedValue({
      text: "",
      data: { path: "x", frontmatter: {}, body: "existing" },
    });

    render(
      <FileToWikiDialog
        kind="file-to-wiki"
        msg={MSG}
        threadId="t-1"
        defaultDomain="research"
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() => expect(listDomainsMock).toHaveBeenCalled());

    await waitFor(() => {
      expect(screen.getByTestId("ftw-collision")).toBeInTheDocument();
    });
    expect(screen.getByTestId("ftw-collision")).toHaveTextContent(
      /already exists/i,
    );
  });

  test("preview renders frontmatter block + first 3 paragraphs of body", async () => {
    render(
      <FileToWikiDialog
        kind="file-to-wiki"
        msg={MSG}
        threadId="t-1"
        defaultDomain="research"
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() => expect(listDomainsMock).toHaveBeenCalled());

    const preview = await screen.findByTestId("ftw-preview");
    // Frontmatter markers.
    expect(preview).toHaveTextContent(/---/);
    expect(preview).toHaveTextContent(/type:/);
    expect(preview).toHaveTextContent(/domain:/);
    // Paragraphs 1-3 present, paragraph 4 trimmed.
    expect(preview).toHaveTextContent(/First paragraph/);
    expect(preview).toHaveTextContent(/Second paragraph/);
    expect(preview).toHaveTextContent(/Third paragraph/);
    expect(preview).not.toHaveTextContent(/Fourth paragraph gets trimmed/);
  });

  test("submit calls proposeNote with the built path and closes", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <FileToWikiDialog
        kind="file-to-wiki"
        msg={MSG}
        threadId="t-1"
        defaultDomain="research"
        onConfirm={vi.fn()}
        onClose={onClose}
      />,
    );
    await waitFor(() => expect(listDomainsMock).toHaveBeenCalled());

    // Slug defaults to something non-empty; just submit.
    await user.click(screen.getByRole("button", { name: /stage patch/i }));

    await waitFor(() => {
      expect(proposeNoteMock).toHaveBeenCalledTimes(1);
    });
    const args = proposeNoteMock.mock.calls[0]![0] as {
      path: string;
      content: string;
      reason: string;
    };
    expect(args.path).toMatch(/^research\/synthesis\/\d{4}-\d{2}-\d{2}-.+\.md$/);
    expect(args.content).toContain("---");
    expect(args.content).toContain("First paragraph");
    expect(args.reason).toBeTruthy();
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
