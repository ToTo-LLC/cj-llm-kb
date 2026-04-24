import { beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

// Hoisted tool mocks — wizard's starting-theme + BRAIN.md steps call
// proposeNote + applyPatch; step 3 (api-key) calls brainSetApiKey + brainPingLlm
// via @/lib/api/tools. Mocks return canned envelopes.
const {
  proposeNoteMock,
  applyPatchMock,
  brainSetApiKeyMock,
  brainPingLlmMock,
} = vi.hoisted(() => ({
  proposeNoteMock: vi.fn(),
  applyPatchMock: vi.fn(),
  brainSetApiKeyMock: vi.fn(),
  brainPingLlmMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  proposeNote: proposeNoteMock,
  applyPatch: applyPatchMock,
  brainSetApiKey: brainSetApiKeyMock,
  brainPingLlm: brainPingLlmMock,
}));

import { Wizard } from "@/components/setup/wizard";

describe("Wizard", () => {
  beforeEach(() => {
    proposeNoteMock.mockReset();
    applyPatchMock.mockReset();
    brainSetApiKeyMock.mockReset();
    brainPingLlmMock.mockReset();
    proposeNoteMock.mockResolvedValue({
      text: "Staged",
      data: { patch_id: "p-1", target_path: "research/index.md" },
    });
    applyPatchMock.mockResolvedValue({
      text: "Applied",
      data: {
        patch_id: "p-1",
        undo_id: "u-1",
        applied_files: ["research/index.md"],
      },
    });
    brainSetApiKeyMock.mockResolvedValue({
      text: "Saved",
      data: {
        status: "ok",
        provider: "anthropic",
        env_key: "ANTHROPIC_API_KEY",
        masked: "sk-ant-***************abcd",
        path: "/fake/.brain/secrets.env",
      },
    });
    brainPingLlmMock.mockResolvedValue({
      text: "pong",
      data: {
        ok: true,
        provider: "anthropic",
        model: "claude-haiku-4-6",
        latency_ms: 42,
      },
    });
  });

  test("Back/Next navigation walks steps 1 → 2 → 1", async () => {
    const user = userEvent.setup();
    render(<Wizard onDone={vi.fn()} />);
    // Step 1 visible.
    expect(screen.getByText(/step 1 of 6/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /continue/i }));
    expect(screen.getByText(/step 2 of 6/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /back/i }));
    expect(screen.getByText(/step 1 of 6/i)).toBeInTheDocument();
  });

  test("step 1 'Already set up' link emits onDone", async () => {
    const onDone = vi.fn();
    const user = userEvent.setup();
    render(<Wizard onDone={onDone} />);
    await user.click(screen.getByRole("button", { name: /already set up/i }));
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  test("final step 'Start using brain' triggers onDone", async () => {
    const onDone = vi.fn();
    const user = userEvent.setup();
    render(<Wizard onDone={onDone} />);
    // Walk through all 6 steps via Continue. Vault is prefilled, theme
    // defaults to blank, api key is optional for navigation purposes.
    for (let i = 0; i < 5; i++) {
      await user.click(screen.getByRole("button", { name: /continue/i }));
    }
    expect(screen.getByText(/step 6 of 6/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /start using brain/i }));
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  test("step 2 vault path cannot be empty — Continue disabled", async () => {
    const user = userEvent.setup();
    render(<Wizard onDone={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /continue/i })); // step 2
    const input = screen.getByLabelText(/vault folder/i) as HTMLInputElement;
    await user.clear(input);
    const cont = screen.getByRole("button", { name: /continue/i });
    expect(cont).toBeDisabled();
    await user.type(input, "/my/vault");
    expect(cont).not.toBeDisabled();
  });

  test("step 3 Test button saves key + pings LLM, renders ok pill", async () => {
    const user = userEvent.setup();
    render(<Wizard onDone={vi.fn()} />);
    // Navigate to step 3.
    for (let i = 0; i < 2; i++) {
      await user.click(screen.getByRole("button", { name: /continue/i }));
    }
    expect(screen.getByText(/step 3 of 6/i)).toBeInTheDocument();
    // Paste a fake key.
    const keyInput = screen.getByLabelText(/anthropic api key/i);
    await user.type(keyInput, "sk-ant-test-123");
    // Click Test.
    await user.click(screen.getByTestId("wizard-api-key-test"));
    // Assert both calls fired, in order, with the right args.
    expect(brainSetApiKeyMock).toHaveBeenCalledWith({
      provider: "anthropic",
      api_key: "sk-ant-test-123",
    });
    expect(brainPingLlmMock).toHaveBeenCalledTimes(1);
    // OK pill renders.
    expect(await screen.findByTestId("wizard-ping-ok")).toBeInTheDocument();
  });

  test("step 3 Test button renders error state when ping fails", async () => {
    brainPingLlmMock.mockResolvedValueOnce({
      text: "err",
      data: {
        ok: false,
        provider: null,
        model: null,
        latency_ms: 0,
        error: "401 unauthorised",
      },
    });
    const user = userEvent.setup();
    render(<Wizard onDone={vi.fn()} />);
    for (let i = 0; i < 2; i++) {
      await user.click(screen.getByRole("button", { name: /continue/i }));
    }
    const keyInput = screen.getByLabelText(/anthropic api key/i);
    await user.type(keyInput, "sk-ant-bad");
    await user.click(screen.getByTestId("wizard-api-key-test"));
    const err = await screen.findByTestId("wizard-ping-err");
    expect(err).toHaveTextContent(/connection failed/i);
    expect(err).toHaveTextContent(/401 unauthorised/i);
  });

  test("step 4 theme pick triggers proposeNote + applyPatch (auto-apply)", async () => {
    const user = userEvent.setup();
    render(<Wizard onDone={vi.fn()} />);
    // Navigate to step 4.
    for (let i = 0; i < 3; i++) {
      await user.click(screen.getByRole("button", { name: /continue/i }));
    }
    expect(screen.getByText(/step 4 of 6/i)).toBeInTheDocument();
    // Pick the Research theme card (role="radio" in a radiogroup).
    await user.click(screen.getByRole("radio", { name: /research/i }));
    await user.click(screen.getByRole("button", { name: /continue/i }));
    expect(proposeNoteMock).toHaveBeenCalledTimes(1);
    expect(proposeNoteMock).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "research/index.md",
        reason: expect.stringContaining("setup"),
      }),
    );
    expect(applyPatchMock).toHaveBeenCalledWith({ patch_id: "p-1" });
  });
});
