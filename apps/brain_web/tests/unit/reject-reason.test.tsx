import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import { RejectReasonDialog } from "@/components/dialogs/reject-reason-dialog";

/**
 * RejectReasonDialog presents 5 preset chips + a free-form textarea. On
 * submit it invokes `onConfirm(reason)` with whatever the user picked /
 * typed, then closes.
 */
describe("RejectReasonDialog", () => {
  test("preset chip click populates the textarea / internal reason state", async () => {
    const user = userEvent.setup();
    render(
      <RejectReasonDialog
        kind="reject-reason"
        patchId="p-1"
        targetPath="research/foo.md"
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await screen.findByRole("dialog");
    const chip = screen.getByRole("button", { name: /wrong domain/i });
    await user.click(chip);
    const textarea = screen.getByPlaceholderText(/in your own words/i) as HTMLTextAreaElement;
    expect(textarea.value).toBe("Wrong domain");
  });

  test("user can type freeform text into the textarea", async () => {
    const user = userEvent.setup();
    render(
      <RejectReasonDialog
        kind="reject-reason"
        patchId="p-1"
        targetPath="research/foo.md"
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await screen.findByRole("dialog");
    const textarea = screen.getByPlaceholderText(/in your own words/i) as HTMLTextAreaElement;
    await user.clear(textarea);
    await user.type(textarea, "doesn't match vault style");
    expect(textarea.value).toBe("doesn't match vault style");
  });

  test("submit calls onConfirm(reason) and then onClose", async () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <RejectReasonDialog
        kind="reject-reason"
        patchId="p-1"
        targetPath="research/foo.md"
        onConfirm={onConfirm}
        onClose={onClose}
      />,
    );
    await screen.findByRole("dialog");
    await user.click(screen.getByRole("button", { name: /source is unreliable/i }));
    await user.click(screen.getByRole("button", { name: /reject patch/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onConfirm).toHaveBeenCalledWith("Source is unreliable");
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
