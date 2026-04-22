import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * ProvidersPanel (Plan 07 Task 22 + Task 25B wiring).
 *
 * Panel layout:
 *   - API key input (type=password) + Save button (→ brain_set_api_key)
 *     + "Test connection" button (→ brain_ping_llm).
 *   - Model-per-stage table (6 rows: ask / brainstorm / draft / classify
 *     / summarize / integrate). Each row has a dropdown bound to the
 *     `<stage>_model` config key.
 *
 * Task 25B wires Save + Test connection to the 25A backend tools; the
 * success states mask the key + show a green pill for the ping. Error
 * states render inline error text.
 */

const {
  configSetMock,
  configGetMock,
  brainSetApiKeyMock,
  brainPingLlmMock,
} = vi.hoisted(() => ({
  configSetMock: vi.fn(),
  configGetMock: vi.fn(),
  brainSetApiKeyMock: vi.fn(),
  brainPingLlmMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  configGet: configGetMock,
  configSet: configSetMock,
  brainSetApiKey: brainSetApiKeyMock,
  brainPingLlm: brainPingLlmMock,
}));

const { pushToastStub } = vi.hoisted(() => ({ pushToastStub: vi.fn() }));

vi.mock("@/lib/state/system-store", () => ({
  useSystemStore: Object.assign(
    (selector: (s: { pushToast: () => void }) => unknown) =>
      selector({ pushToast: pushToastStub }),
    { getState: () => ({ pushToast: pushToastStub }) },
  ),
}));

import { PanelProviders } from "@/components/settings/panel-providers";

beforeEach(() => {
  configSetMock.mockReset();
  configGetMock.mockReset();
  brainSetApiKeyMock.mockReset();
  brainPingLlmMock.mockReset();
  configSetMock.mockResolvedValue({ text: "", data: { key: "x", value: "y" } });
  configGetMock.mockResolvedValue({
    text: "",
    data: { key: "x", value: "sonnet" },
  });
  brainSetApiKeyMock.mockResolvedValue({
    text: "saved",
    data: {
      status: "saved",
      provider: "anthropic",
      env_key: "ANTHROPIC_API_KEY",
      masked: "sk-ant-•••qXf2",
      path: "/vault/.brain/secrets.env",
    },
  });
  brainPingLlmMock.mockResolvedValue({
    text: "ok",
    data: {
      ok: true,
      provider: "anthropic",
      model: "claude-haiku-4-6",
      latency_ms: 420,
    },
  });
});

describe("PanelProviders", () => {
  test("API key input is type=password + masked placeholder after save", async () => {
    render(<PanelProviders />);
    const input = screen.getByLabelText(/api key/i) as HTMLInputElement;
    expect(input).toHaveAttribute("type", "password");
    expect(input.placeholder).toMatch(/sk-ant/i);
  });

  test("Save button calls brainSetApiKey and renders masked key on success", async () => {
    const user = userEvent.setup();
    render(<PanelProviders />);
    const input = screen.getByLabelText(/api key/i) as HTMLInputElement;
    await user.type(input, "sk-ant-test-abcdqXf2");
    const saveBtn = screen.getByRole("button", { name: /^save$/i });
    await user.click(saveBtn);

    await waitFor(() => {
      expect(brainSetApiKeyMock).toHaveBeenCalledWith({
        provider: "anthropic",
        api_key: "sk-ant-test-abcdqXf2",
      });
    });
    await waitFor(() => {
      expect(screen.getByTestId("api-key-masked")).toBeInTheDocument();
    });
  });

  test("Test connection calls brainPingLlm and renders a green ok pill on ok:true", async () => {
    const user = userEvent.setup();
    render(<PanelProviders />);
    const btn = screen.getByRole("button", { name: /test connection/i });
    await user.click(btn);
    await waitFor(() => {
      expect(brainPingLlmMock).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(screen.getByTestId("ping-ok-pill")).toBeInTheDocument();
    });
  });

  test("Test connection renders error state on ok:false", async () => {
    brainPingLlmMock.mockResolvedValueOnce({
      text: "ping_llm failed: timeout",
      data: {
        ok: false,
        error: "timeout",
        provider: "anthropic",
        model: "claude-haiku-4-6",
        latency_ms: 3000,
      },
    });
    const user = userEvent.setup();
    render(<PanelProviders />);
    const btn = screen.getByRole("button", { name: /test connection/i });
    await user.click(btn);
    await waitFor(() => {
      expect(screen.getByTestId("ping-err")).toBeInTheDocument();
    });
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
