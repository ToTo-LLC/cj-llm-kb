import { beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

// Hoisted tool mocks — wizard's starting-theme + BRAIN.md steps call
// proposeNote + applyPatch via @/lib/api/tools. Mocks return canned envelopes.
const { proposeNoteMock, applyPatchMock } = vi.hoisted(() => ({
  proposeNoteMock: vi.fn(),
  applyPatchMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  proposeNote: proposeNoteMock,
  applyPatch: applyPatchMock,
}));

import { Wizard } from "@/components/setup/wizard";

describe("Wizard", () => {
  beforeEach(() => {
    proposeNoteMock.mockReset();
    applyPatchMock.mockReset();
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
