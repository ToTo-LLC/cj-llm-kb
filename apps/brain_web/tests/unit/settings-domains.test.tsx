import { describe, expect, test, beforeEach, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * DomainsPanel (Plan 07 Task 22 + Task 25B wiring).
 *
 * - List renders via `listDomains`.
 * - "Add domain" form calls `createDomain` with {slug, name, accent_color}.
 * - Delete button opens typed-confirm; on confirm → brainDeleteDomain({slug,
 *   typed_confirm: true}) → removes row + toasts.
 * - Rename button opens dialog via dialogs-store (kind = "rename-domain").
 * - Personal domain shows a privacy-railed badge + NO delete button.
 */

const { listDomainsMock, createDomainMock, brainDeleteDomainMock } = vi.hoisted(() => ({
  listDomainsMock: vi.fn(),
  createDomainMock: vi.fn(),
  brainDeleteDomainMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  listDomains: listDomainsMock,
  createDomain: createDomainMock,
  brainDeleteDomain: brainDeleteDomainMock,
}));

const { openDialogMock } = vi.hoisted(() => ({
  openDialogMock: vi.fn(),
}));

vi.mock("@/lib/state/dialogs-store", () => ({
  useDialogsStore: Object.assign(
    (selector: (s: { open: typeof openDialogMock }) => unknown) =>
      selector({ open: openDialogMock }),
    { getState: () => ({ open: openDialogMock }) },
  ),
}));

const { pushToastStub } = vi.hoisted(() => ({ pushToastStub: vi.fn() }));

vi.mock("@/lib/state/system-store", () => ({
  useSystemStore: Object.assign(
    (selector: (s: { pushToast: () => void }) => unknown) =>
      selector({ pushToast: pushToastStub }),
    { getState: () => ({ pushToast: pushToastStub }) },
  ),
}));

import { PanelDomains } from "@/components/settings/panel-domains";

beforeEach(() => {
  listDomainsMock.mockReset();
  createDomainMock.mockReset();
  brainDeleteDomainMock.mockReset();
  openDialogMock.mockReset();
  listDomainsMock.mockResolvedValue({
    text: "",
    data: { domains: ["research", "work", "personal"] },
  });
  createDomainMock.mockResolvedValue({
    text: "",
    data: { slug: "hobby", name: "Hobby", accent_color: "#6677ee" },
  });
  brainDeleteDomainMock.mockResolvedValue({
    text: "deleted",
    data: {
      status: "deleted",
      slug: "work",
      trash_path: "/vault/.brain/trash/work-1234",
      files_moved: 12,
      undo_id: "u-1",
    },
  });
});

describe("PanelDomains", () => {
  test("renders the domain list from listDomains", async () => {
    render(<PanelDomains />);
    // Plan 12 Task 8 added an <ActiveDomainSelector /> above the list,
    // so the slugs now appear inside both the per-row labels AND
    // <option> elements. Scope to non-option matches with the testing-
    // library ``ignore`` option so we assert on the row labels only.
    await waitFor(() => {
      expect(screen.getByText("research", { ignore: "option" })).toBeInTheDocument();
    });
    expect(screen.getByText("work", { ignore: "option" })).toBeInTheDocument();
    expect(screen.getByText("personal", { ignore: "option" })).toBeInTheDocument();
  });

  test("add form calls createDomain with name + slug + accent_color", async () => {
    const user = userEvent.setup();
    render(<PanelDomains />);
    await waitFor(() => expect(screen.getByText("research")).toBeInTheDocument());

    await user.type(screen.getByLabelText(/display name/i), "Hobby");
    await user.type(screen.getByLabelText(/folder slug/i), "hobby");
    await user.click(screen.getByRole("button", { name: /add domain/i }));

    await waitFor(() => {
      expect(createDomainMock).toHaveBeenCalled();
    });
    const args = createDomainMock.mock.calls[0]![0] as {
      name: string;
      slug: string;
      accent_color?: string;
    };
    expect(args.name).toBe("Hobby");
    expect(args.slug).toBe("hobby");
    expect(typeof args.accent_color === "string" || args.accent_color === undefined).toBe(true);
  });

  test("delete button opens typed-confirm with the slug as the confirm word", async () => {
    const user = userEvent.setup();
    render(<PanelDomains />);
    await waitFor(() => expect(screen.getByText("work")).toBeInTheDocument());

    const deleteBtn = screen.getByRole("button", { name: /delete work/i });
    await user.click(deleteBtn);
    expect(openDialogMock).toHaveBeenCalled();
    const payload = openDialogMock.mock.calls[0]![0] as {
      kind: string;
      word: string;
      onConfirm: () => void;
    };
    expect(payload.kind).toBe("typed-confirm");
    expect(payload.word).toBe("work"); // slug-as-word per plan
  });

  test("typed-confirm onConfirm calls brainDeleteDomain and removes the row", async () => {
    const user = userEvent.setup();
    render(<PanelDomains />);
    await waitFor(() => expect(screen.getByText("work")).toBeInTheDocument());

    const deleteBtn = screen.getByRole("button", { name: /delete work/i });
    await user.click(deleteBtn);
    const payload = openDialogMock.mock.calls[0]![0] as {
      kind: string;
      onConfirm: () => void;
    };
    // Simulate the user typing "work" + hitting Confirm.
    await act(async () => {
      await payload.onConfirm();
    });

    expect(brainDeleteDomainMock).toHaveBeenCalledWith({
      slug: "work",
      typed_confirm: true,
    });
    await waitFor(() => {
      // Plan 12 Task 8: the row label is gone after delete; the
      // active-domain dropdown's <option value="work"> may or may
      // not still be present (the panel keeps a local domains
      // state separate from the store; the dropdown reads the
      // store, which only updates after the next refresh). Scope
      // the assertion to non-option matches so this test pins the
      // per-row removal regardless of when the store refreshes.
      expect(screen.queryByText("work", { ignore: "option" })).not.toBeInTheDocument();
    });
  });

  test("rename button opens rename-domain dialog via dialogs-store", async () => {
    const user = userEvent.setup();
    render(<PanelDomains />);
    await waitFor(() => expect(screen.getByText("work")).toBeInTheDocument());

    const renameBtn = screen.getByRole("button", { name: /rename work/i });
    await user.click(renameBtn);
    expect(openDialogMock).toHaveBeenCalled();
    const payload = openDialogMock.mock.calls[0]![0] as {
      kind: string;
      onRenamed?: () => void;
    };
    expect(payload.kind).toBe("rename-domain");
    // Plan 10 Task 6: panel passes an ``onRenamed`` callback so the
    // list refreshes after the dialog commits.
    expect(typeof payload.onRenamed).toBe("function");
  });

  test("rename onRenamed callback re-fetches the domain list", async () => {
    const user = userEvent.setup();
    render(<PanelDomains />);
    await waitFor(() => expect(screen.getByText("work")).toBeInTheDocument());

    const initialCalls = listDomainsMock.mock.calls.length;
    const renameBtn = screen.getByRole("button", { name: /rename work/i });
    await user.click(renameBtn);
    const payload = openDialogMock.mock.calls[0]![0] as {
      onRenamed?: () => void;
    };
    expect(payload.onRenamed).toBeTypeOf("function");

    // Simulate dialog success → callback fires.
    listDomainsMock.mockResolvedValueOnce({
      text: "",
      data: { domains: ["consulting", "personal", "research"] },
    });
    await act(async () => {
      payload.onRenamed!();
    });
    await waitFor(() => {
      expect(listDomainsMock.mock.calls.length).toBeGreaterThan(initialCalls);
    });
  });

  test("D2 slug rule: underscore allowed, leading digit rejected, trailing dash rejected", async () => {
    const user = userEvent.setup();
    render(<PanelDomains />);
    await waitFor(() => expect(screen.getByText("research")).toBeInTheDocument());

    const nameInput = screen.getByLabelText(/display name/i);
    const slugInput = screen.getByLabelText(/folder slug/i);
    const submit = screen.getByRole("button", { name: /add domain/i });

    await user.type(nameInput, "Side Project");

    // Leading digit → invalid → submit disabled.
    await user.clear(slugInput);
    await user.type(slugInput, "1bad");
    expect(submit).toBeDisabled();

    // Trailing dash → invalid → submit disabled. ``kebabCoerce`` strips
    // some chars but the trailing-dash check happens client-side too.
    await user.clear(slugInput);
    await user.type(slugInput, "good-");
    expect(submit).toBeDisabled();

    // Underscore allowed (D2 expanded the regex to ``[a-z0-9_-]``).
    await user.clear(slugInput);
    await user.type(slugInput, "side_project");
    expect(submit).toBeEnabled();
  });

  test("personal shows privacy-railed badge + no delete button", async () => {
    render(<PanelDomains />);
    await waitFor(() => expect(screen.getByText("personal")).toBeInTheDocument());

    expect(screen.getByTestId("personal-privacy-badge")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /delete personal/i }),
    ).not.toBeInTheDocument();
  });
});
