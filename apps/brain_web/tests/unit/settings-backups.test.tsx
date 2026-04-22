import { describe, expect, test, beforeEach, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * BackupsPanel (Plan 07 Task 22 + Task 25B wiring).
 *
 * - On mount, calls `brainBackupList` and renders a row per snapshot
 *   (date + size + trigger).
 * - "Back up now" button calls `brainBackupCreate({trigger: "manual"})`
 *   and prepends the new snapshot row.
 * - "Restore" action on a row opens typed-confirm (word = "RESTORE")
 *   + on confirm calls `brainBackupRestore({backup_id, typed_confirm: true})`
 *   + surfaces a toast.
 * - "Reveal" links to `file://<backup_path>` (best-effort — clicking the
 *   link does not throw; the exact path is rendered in the DOM).
 */

const {
  brainBackupListMock,
  brainBackupCreateMock,
  brainBackupRestoreMock,
  pushToastStub,
  openDialogMock,
} = vi.hoisted(() => ({
  brainBackupListMock: vi.fn(),
  brainBackupCreateMock: vi.fn(),
  brainBackupRestoreMock: vi.fn(),
  pushToastStub: vi.fn(),
  openDialogMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  brainBackupList: brainBackupListMock,
  brainBackupCreate: brainBackupCreateMock,
  brainBackupRestore: brainBackupRestoreMock,
}));

vi.mock("@/lib/state/system-store", () => ({
  useSystemStore: Object.assign(
    (selector: (s: { pushToast: () => void }) => unknown) =>
      selector({ pushToast: pushToastStub }),
    { getState: () => ({ pushToast: pushToastStub }) },
  ),
}));

vi.mock("@/lib/state/dialogs-store", () => ({
  useDialogsStore: Object.assign(
    (selector: (s: { open: typeof openDialogMock }) => unknown) =>
      selector({ open: openDialogMock }),
    { getState: () => ({ open: openDialogMock }) },
  ),
}));

import { PanelBackups } from "@/components/settings/panel-backups";

beforeEach(() => {
  brainBackupListMock.mockReset();
  brainBackupCreateMock.mockReset();
  brainBackupRestoreMock.mockReset();
  pushToastStub.mockReset();
  openDialogMock.mockReset();
  brainBackupListMock.mockResolvedValue({
    text: "",
    data: {
      backups: [
        {
          backup_id: "20260421-090000-manual",
          path: "/vault/.brain/backups/20260421-090000-manual.tar.gz",
          trigger: "manual",
          created_at: "2026-04-21T09:00:00+00:00",
          size_bytes: 1_234_567,
          file_count: 42,
        },
        {
          backup_id: "20260420-030000-daily",
          path: "/vault/.brain/backups/20260420-030000-daily.tar.gz",
          trigger: "daily",
          created_at: "2026-04-20T03:00:00+00:00",
          size_bytes: 1_100_000,
          file_count: 40,
        },
      ],
    },
  });
  brainBackupCreateMock.mockResolvedValue({
    text: "",
    data: {
      status: "created",
      backup_id: "20260421-210000-manual",
      path: "/vault/.brain/backups/20260421-210000-manual.tar.gz",
      trigger: "manual",
      created_at: "2026-04-21T21:00:00+00:00",
      size_bytes: 1_240_000,
      file_count: 42,
    },
  });
  brainBackupRestoreMock.mockResolvedValue({
    text: "",
    data: {
      status: "restored",
      backup_id: "20260420-030000-daily",
      trash_path: "/vault-pre-restore-20260421-210100",
    },
  });
});

describe("PanelBackups", () => {
  test("renders backup rows on mount from brainBackupList", async () => {
    render(<PanelBackups />);
    await waitFor(() => {
      expect(brainBackupListMock).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(screen.getByText(/20260421-090000-manual/)).toBeInTheDocument();
    });
    expect(screen.getByText(/20260420-030000-daily/)).toBeInTheDocument();
  });

  test('"Back up now" button calls brainBackupCreate({trigger: "manual"}) and prepends a row', async () => {
    const user = userEvent.setup();
    render(<PanelBackups />);
    await waitFor(() => {
      expect(screen.getByText(/20260421-090000-manual/)).toBeInTheDocument();
    });
    const btn = screen.getByRole("button", { name: /back up now/i });
    expect(btn).not.toBeDisabled();
    await user.click(btn);
    await waitFor(() => {
      expect(brainBackupCreateMock).toHaveBeenCalledWith({ trigger: "manual" });
    });
    await waitFor(() => {
      expect(screen.getByText(/20260421-210000-manual/)).toBeInTheDocument();
    });
  });

  test('Restore action opens typed-confirm with word "RESTORE" then calls brainBackupRestore', async () => {
    const user = userEvent.setup();
    render(<PanelBackups />);
    await waitFor(() => {
      expect(screen.getByText(/20260420-030000-daily/)).toBeInTheDocument();
    });
    const restoreBtns = screen.getAllByRole("button", { name: /restore/i });
    // Restore the second row (the daily backup).
    await user.click(restoreBtns[1]!);
    expect(openDialogMock).toHaveBeenCalled();
    const payload = openDialogMock.mock.calls[0]![0] as {
      kind: string;
      word: string;
      onConfirm: () => void;
    };
    expect(payload.kind).toBe("typed-confirm");
    expect(payload.word).toBe("RESTORE");

    await act(async () => {
      await payload.onConfirm();
    });
    expect(brainBackupRestoreMock).toHaveBeenCalledWith({
      backup_id: "20260420-030000-daily",
      typed_confirm: true,
    });
    expect(pushToastStub).toHaveBeenCalled();
  });

  test("Reveal button renders as a file:// link", async () => {
    render(<PanelBackups />);
    await waitFor(() => {
      expect(screen.getByText(/20260421-090000-manual/)).toBeInTheDocument();
    });
    const revealLinks = screen.getAllByRole("link", { name: /reveal/i });
    expect(revealLinks.length).toBeGreaterThan(0);
    expect(revealLinks[0]).toHaveAttribute(
      "href",
      expect.stringMatching(/^file:\/\//),
    );
  });
});
