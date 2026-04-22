import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * ProvidersPanel (Plan 07 Task 22).
 *
 * Panel layout:
 *   - API key input (type=password) + save button + "Test" button
 *     (stubbed pending `brain_set_api_key` + `brain_ping_llm` in Task 25).
 *   - Model-per-stage table (6 rows: ask / brainstorm / draft / classify
 *     / summarize / integrate). Each row has a dropdown bound to the
 *     `<stage>_model` config key.
 *
 * The API key "Save" + "Test connection" actions are stubbed — they
 * render + respond to clicks but do not hit the backend (tools don't
 * exist yet). The model dropdowns wire through to `configSet`.
 */

const { configSetMock, configGetMock } = vi.hoisted(() => ({
  configSetMock: vi.fn(),
  configGetMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  configGet: configGetMock,
  configSet: configSetMock,
}));

vi.mock("@/lib/state/system-store", () => ({
  useSystemStore: Object.assign(
    (selector: (s: { pushToast: () => void }) => unknown) =>
      selector({ pushToast: vi.fn() }),
    { getState: () => ({ pushToast: vi.fn() }) },
  ),
}));

import { PanelProviders } from "@/components/settings/panel-providers";

beforeEach(() => {
  configSetMock.mockReset();
  configGetMock.mockReset();
  configSetMock.mockResolvedValue({ text: "", data: { key: "x", value: "y" } });
  configGetMock.mockResolvedValue({
    text: "",
    data: { key: "x", value: "sonnet" },
  });
});

describe("PanelProviders", () => {
  test("API key input is type=password + masked placeholder after save", async () => {
    render(<PanelProviders />);
    const input = screen.getByLabelText(/api key/i) as HTMLInputElement;
    expect(input).toHaveAttribute("type", "password");
    // Masked placeholder reads like a stored key — exact format flex.
    expect(input.placeholder).toMatch(/sk-ant/i);
  });

  test('"Test connection" button renders (stubbed, no-op click)', async () => {
    const user = userEvent.setup();
    render(<PanelProviders />);
    const btn = screen.getByRole("button", { name: /test connection/i });
    expect(btn).toBeInTheDocument();
    // Click shouldn't throw — stubbed action displays toast or TODO note.
    await user.click(btn);
  });

  test("model-per-stage renders 6 stage rows", () => {
    render(<PanelProviders />);
    const stages = ["Ask", "Brainstorm", "Draft", "Classify", "Summarize", "Integrate"];
    for (const s of stages) {
      expect(screen.getByText(new RegExp(`^${s}$`, "i"))).toBeInTheDocument();
    }
  });

  test("changing a model dropdown calls configSet with `<stage>_model`", async () => {
    const user = userEvent.setup();
    render(<PanelProviders />);
    // Native <select> fallback — panel uses a simple select for test-friendliness.
    const selects = screen.getAllByRole("combobox");
    expect(selects.length).toBeGreaterThanOrEqual(6);
    const askSelect = selects[0] as HTMLSelectElement;
    await user.selectOptions(askSelect, "claude-opus-4-6");
    await waitFor(() => {
      expect(configSetMock).toHaveBeenCalled();
    });
    const lastCall = configSetMock.mock.calls[configSetMock.mock.calls.length - 1]![0] as {
      key: string;
      value: unknown;
    };
    expect(lastCall.key).toMatch(/_model$/);
    expect(lastCall.value).toBe("claude-opus-4-6");
  });
});
