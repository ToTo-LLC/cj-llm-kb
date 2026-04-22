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
    await waitFor(() => {
      expect(screen.getByText("research")).toBeInTheDocument();
    });
    expect(screen.getByText("work")).toBeInTheDocument();
    expect(screen.getByText("personal")).toBeInTheDocument();
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
      expect(screen.queryByText("work")).not.toBeInTheDocument();
    });
  });

  test("rename button opens rename-domain dialog via dialogs-store", async () => {
    const user = userEvent.setup();
    render(<PanelDomains />);
    await waitFor(() => expect(screen.getByText("work")).toBeInTheDocument());

    const renameBtn = screen.getByRole("button", { name: /rename work/i });
    await user.click(renameBtn);
    expect(openDialogMock).toHaveBeenCalled();
    const payload = openDialogMock.mock.calls[0]![0] as { kind: string };
    expect(payload.kind).toBe("rename-domain");
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
