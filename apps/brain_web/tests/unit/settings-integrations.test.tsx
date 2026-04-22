import { describe, expect, test, beforeEach, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * IntegrationsPanel (Plan 07 Task 22 + Task 25B wiring).
 *
 * Claude Desktop card:
 *   - On mount → brainMcpStatus() populates detected config path +
 *     status pill.
 *   - "Run self-test" → brainMcpSelftest() → success / fail state.
 *   - "Regenerate config" → brainMcpInstall().
 *   - "Uninstall" → opens typed-confirm (word = "UNINSTALL") →
 *     brainMcpUninstall() on confirm.
 *
 * Other-clients card is unchanged snippet-copy UI, already covered by
 * the Task 22 render coverage.
 */

const {
  brainMcpStatusMock,
  brainMcpSelftestMock,
  brainMcpInstallMock,
  brainMcpUninstallMock,
  pushToastStub,
  openDialogMock,
} = vi.hoisted(() => ({
  brainMcpStatusMock: vi.fn(),
  brainMcpSelftestMock: vi.fn(),
  brainMcpInstallMock: vi.fn(),
  brainMcpUninstallMock: vi.fn(),
  pushToastStub: vi.fn(),
  openDialogMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  brainMcpStatus: brainMcpStatusMock,
  brainMcpSelftest: brainMcpSelftestMock,
  brainMcpInstall: brainMcpInstallMock,
  brainMcpUninstall: brainMcpUninstallMock,
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

import { PanelIntegrations } from "@/components/settings/panel-integrations";

beforeEach(() => {
  brainMcpStatusMock.mockReset();
  brainMcpSelftestMock.mockReset();
  brainMcpInstallMock.mockReset();
  brainMcpUninstallMock.mockReset();
  pushToastStub.mockReset();
  openDialogMock.mockReset();
  brainMcpStatusMock.mockResolvedValue({
    text: "",
    data: {
      status: "ok",
      config_path: "/Users/x/Library/Application Support/Claude/claude_desktop_config.json",
      config_exists: true,
      entry_present: true,
      executable_resolves: true,
      command: "python",
      server_name: "brain",
    },
  });
  brainMcpSelftestMock.mockResolvedValue({
    text: "",
    data: {
      status: "passed",
      ok: true,
      config_exists: true,
      entry_present: true,
      executable_resolves: true,
      command: "python",
      config_path: "/path/to/config.json",
      server_name: "brain",
    },
  });
  brainMcpInstallMock.mockResolvedValue({
    text: "",
    data: {
      status: "installed",
      config_path: "/path/to/config.json",
      backup_path: "/path/to/config.json.bak-20260421",
      server_name: "brain",
    },
  });
  brainMcpUninstallMock.mockResolvedValue({
    text: "",
    data: {
      status: "uninstalled",
      config_path: "/path/to/config.json",
      backup_path: "/path/to/config.json.bak-20260421",
      server_name: "brain",
    },
  });
});

describe("PanelIntegrations", () => {
  test("renders Claude Desktop status from brainMcpStatus on mount", async () => {
    render(<PanelIntegrations />);
    await waitFor(() => {
      expect(brainMcpStatusMock).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(
        screen.getByText(/claude_desktop_config\.json/i),
      ).toBeInTheDocument();
    });
    expect(screen.getByTestId("mcp-status-pill")).toBeInTheDocument();
  });

  test('"Run self-test" calls brainMcpSelftest and shows pass/fail state', async () => {
    const user = userEvent.setup();
    render(<PanelIntegrations />);
    await waitFor(() => expect(brainMcpStatusMock).toHaveBeenCalled());

    const btn = screen.getByRole("button", { name: /run self-test/i });
    await user.click(btn);
    await waitFor(() => {
      expect(brainMcpSelftestMock).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(screen.getByTestId("selftest-result")).toBeInTheDocument();
    });
  });

  test('"Regenerate config" calls brainMcpInstall', async () => {
    const user = userEvent.setup();
    render(<PanelIntegrations />);
    await waitFor(() => expect(brainMcpStatusMock).toHaveBeenCalled());

    const btn = screen.getByRole("button", { name: /regenerate config/i });
    await user.click(btn);
    await waitFor(() => {
      expect(brainMcpInstallMock).toHaveBeenCalled();
    });
    expect(pushToastStub).toHaveBeenCalled();
  });

  test('"Uninstall" opens typed-confirm (word "UNINSTALL") and calls brainMcpUninstall on confirm', async () => {
    const user = userEvent.setup();
    render(<PanelIntegrations />);
    await waitFor(() => expect(brainMcpStatusMock).toHaveBeenCalled());

    const btn = screen.getByRole("button", { name: /^uninstall$/i });
    await user.click(btn);
    expect(openDialogMock).toHaveBeenCalled();
    const payload = openDialogMock.mock.calls[0]![0] as {
      kind: string;
      word: string;
      onConfirm: () => void;
    };
    expect(payload.kind).toBe("typed-confirm");
    expect(payload.word).toBe("UNINSTALL");

    await act(async () => {
      await payload.onConfirm();
    });
    expect(brainMcpUninstallMock).toHaveBeenCalled();
  });
});
