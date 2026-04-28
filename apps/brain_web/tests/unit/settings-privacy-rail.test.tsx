import { describe, expect, test, beforeEach, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * PanelDomains privacy-rail checkbox (Plan 11 Task 7).
 *
 *  - personal's checkbox is ``disabled={true}`` AND ``checked={true}``.
 *  - Other rows: checking calls ``setPrivacyRailed`` with the new list
 *    that includes the slug; unchecking calls it with the slug
 *    removed.
 *  - Optimistic UI: the checkbox flips immediately; on failure the
 *    state reverts and a danger toast fires.
 *  - Last-domain delete: deleting a railed domain removes it from the
 *    rail BEFORE invoking ``brain_delete_domain``, so the
 *    save_config validator never sees a railed-but-deleted slug.
 */

const {
  listDomainsMock,
  configGetMock,
  configSetMock,
  brainDeleteDomainMock,
  setPrivacyRailedMock,
} = vi.hoisted(() => ({
  listDomainsMock: vi.fn(),
  configGetMock: vi.fn(),
  configSetMock: vi.fn(),
  brainDeleteDomainMock: vi.fn(),
  setPrivacyRailedMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  listDomains: listDomainsMock,
  configGet: configGetMock,
  configSet: configSetMock,
  brainDeleteDomain: brainDeleteDomainMock,
  setPrivacyRailed: setPrivacyRailedMock,
  createDomain: vi.fn(),
}));

const { openDialogMock } = vi.hoisted(() => ({ openDialogMock: vi.fn() }));

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
  configGetMock.mockReset();
  configSetMock.mockReset();
  brainDeleteDomainMock.mockReset();
  setPrivacyRailedMock.mockReset();
  openDialogMock.mockReset();
  pushToastStub.mockReset();

  listDomainsMock.mockResolvedValue({
    text: "",
    data: { domains: ["research", "work", "personal", "journal"] },
  });
  configGetMock.mockImplementation((args: { key: string }) => {
    if (args.key === "privacy_railed") {
      return Promise.resolve({
        text: "",
        data: { key: args.key, value: ["personal"] },
      });
    }
    if (args.key === "domain_overrides") {
      return Promise.resolve({ text: "", data: { key: args.key, value: {} } });
    }
    return Promise.resolve({ text: "", data: { key: args.key, value: null } });
  });
  configSetMock.mockResolvedValue({ text: "", data: {} });
  setPrivacyRailedMock.mockResolvedValue({ text: "", data: {} });
  brainDeleteDomainMock.mockResolvedValue({
    text: "",
    data: {
      status: "deleted",
      slug: "journal",
      trash_path: "/vault/.brain/trash/journal-1",
      files_moved: 3,
      undo_id: "u-1",
    },
  });
});

describe("PanelDomains — privacy-rail checkbox (Plan 11 Task 7)", () => {
  test("personal's checkbox is disabled AND checked", async () => {
    render(<PanelDomains />);
    await waitFor(() =>
      expect(screen.getByText("personal")).toBeInTheDocument(),
    );

    const personalRailCheckbox = screen.getByTestId(
      "privacy-rail-checkbox-personal",
    );
    // Both HTML attributes verified — visual styling is not enough.
    expect(personalRailCheckbox).toBeDisabled();
    // Radix renders ``data-state="checked"`` when checked; assert
    // that and aria-checked together so a future implementation
    // change to a native input still satisfies one of the two.
    expect(personalRailCheckbox).toHaveAttribute("data-state", "checked");
    expect(personalRailCheckbox).toHaveAttribute("aria-checked", "true");
  });

  test("non-personal rows' checkboxes start unchecked when the slug isn't in the rail", async () => {
    render(<PanelDomains />);
    await waitFor(() =>
      expect(screen.getByText("journal")).toBeInTheDocument(),
    );

    const journalRailCheckbox = screen.getByTestId(
      "privacy-rail-checkbox-journal",
    );
    expect(journalRailCheckbox).not.toBeDisabled();
    expect(journalRailCheckbox).toHaveAttribute("aria-checked", "false");
  });

  test("checking a non-personal slug calls setPrivacyRailed with the new list", async () => {
    const user = userEvent.setup();
    render(<PanelDomains />);
    await waitFor(() =>
      expect(screen.getByText("journal")).toBeInTheDocument(),
    );

    const checkbox = screen.getByTestId("privacy-rail-checkbox-journal");
    await user.click(checkbox);

    await waitFor(() => {
      expect(setPrivacyRailedMock).toHaveBeenCalled();
    });
    const list = setPrivacyRailedMock.mock.calls[0]![0] as string[];
    // Order doesn't matter for the rail — assert membership.
    expect(list).toEqual(expect.arrayContaining(["personal", "journal"]));
    expect(list.length).toBe(2);
  });

  test("unchecking a railed slug calls setPrivacyRailed with the slug removed", async () => {
    // Start with journal already railed.
    configGetMock.mockImplementation((args: { key: string }) => {
      if (args.key === "privacy_railed") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: ["personal", "journal"] },
        });
      }
      if (args.key === "domain_overrides") {
        return Promise.resolve({ text: "", data: { key: args.key, value: {} } });
      }
      return Promise.resolve({ text: "", data: { key: args.key, value: null } });
    });
    const user = userEvent.setup();
    render(<PanelDomains />);
    await waitFor(() => {
      const cb = screen.getByTestId("privacy-rail-checkbox-journal");
      expect(cb).toHaveAttribute("aria-checked", "true");
    });

    const checkbox = screen.getByTestId("privacy-rail-checkbox-journal");
    await user.click(checkbox);

    await waitFor(() => {
      expect(setPrivacyRailedMock).toHaveBeenCalled();
    });
    const list = setPrivacyRailedMock.mock.calls[0]![0] as string[];
    expect(list).toEqual(["personal"]);
  });

  test("setPrivacyRailed failure reverts the checkbox state and pushes a danger toast", async () => {
    setPrivacyRailedMock.mockRejectedValueOnce(new Error("boom"));
    const user = userEvent.setup();
    render(<PanelDomains />);
    await waitFor(() =>
      expect(screen.getByText("journal")).toBeInTheDocument(),
    );

    const checkbox = screen.getByTestId("privacy-rail-checkbox-journal");
    await user.click(checkbox);

    await waitFor(() => {
      expect(setPrivacyRailedMock).toHaveBeenCalled();
    });
    // After the failure the checkbox should be unchecked again.
    await waitFor(() => {
      expect(
        screen.getByTestId("privacy-rail-checkbox-journal"),
      ).toHaveAttribute("aria-checked", "false");
    });
    // Danger toast was pushed.
    const toastCalls = pushToastStub.mock.calls.map(
      (c) => c[0] as { variant?: string; lead: string },
    );
    expect(
      toastCalls.some(
        (t) => t.variant === "danger" && /privacy rail/i.test(t.lead),
      ),
    ).toBe(true);
  });

  test("deleting a railed domain removes it from the rail before invoking brain_delete_domain", async () => {
    // Start with journal railed.
    configGetMock.mockImplementation((args: { key: string }) => {
      if (args.key === "privacy_railed") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: ["personal", "journal"] },
        });
      }
      if (args.key === "domain_overrides") {
        return Promise.resolve({ text: "", data: { key: args.key, value: {} } });
      }
      return Promise.resolve({ text: "", data: { key: args.key, value: null } });
    });

    const user = userEvent.setup();
    render(<PanelDomains />);
    await waitFor(() => {
      const cb = screen.getByTestId("privacy-rail-checkbox-journal");
      expect(cb).toHaveAttribute("aria-checked", "true");
    });

    const deleteBtn = screen.getByRole("button", { name: /delete journal/i });
    await user.click(deleteBtn);
    expect(openDialogMock).toHaveBeenCalled();
    const payload = openDialogMock.mock.calls[0]![0] as {
      kind: string;
      onConfirm: () => Promise<void> | void;
    };
    expect(payload.kind).toBe("typed-confirm");

    // Simulate the user typing the slug + hitting Confirm.
    await act(async () => {
      await payload.onConfirm();
    });

    // setPrivacyRailed was invoked with journal removed BEFORE
    // brain_delete_domain ran — pin order via call counts.
    expect(setPrivacyRailedMock).toHaveBeenCalled();
    const list = setPrivacyRailedMock.mock.calls[0]![0] as string[];
    expect(list).toEqual(["personal"]);
    expect(brainDeleteDomainMock).toHaveBeenCalledWith({
      slug: "journal",
      typed_confirm: true,
    });

    // setPrivacyRailed must have been invoked before brain_delete_domain.
    const railOrder = setPrivacyRailedMock.mock.invocationCallOrder[0]!;
    const deleteOrder = brainDeleteDomainMock.mock.invocationCallOrder[0]!;
    expect(railOrder).toBeLessThan(deleteOrder);
  });
});
