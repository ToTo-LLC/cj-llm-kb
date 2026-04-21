import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import { TypedConfirmDialog } from "@/components/dialogs/typed-confirm-dialog";

/**
 * TypedConfirmDialog: destructive-confirm pattern. Confirm button is
 * disabled until `input === word` (case-sensitive match).
 */
describe("TypedConfirmDialog", () => {
  test("confirm button is disabled until the typed input exactly matches `word`", async () => {
    const user = userEvent.setup();
    render(
      <TypedConfirmDialog
        kind="typed-confirm"
        title="Delete domain"
        body="This deletes the domain and its files."
        word="DELETE"
        danger
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await screen.findByRole("dialog");
    const confirmBtn = screen.getByRole("button", { name: /delete permanently/i });
    expect(confirmBtn).toBeDisabled();

    const input = screen.getByPlaceholderText("DELETE") as HTMLInputElement;
    await user.type(input, "DELET"); // one short
    expect(confirmBtn).toBeDisabled();

    await user.type(input, "E"); // now matches "DELETE"
    expect(confirmBtn).toBeEnabled();
  });

  test("match is case-sensitive — lowercase `rejected` != `REJECTED`", async () => {
    const user = userEvent.setup();
    render(
      <TypedConfirmDialog
        kind="typed-confirm"
        title="Reject all"
        body="body"
        word="REJECTED"
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await screen.findByRole("dialog");
    const input = screen.getByPlaceholderText("REJECTED") as HTMLInputElement;
    // danger defaults to false -> button reads "Confirm"
    const confirmBtn = screen.getByRole("button", { name: /^confirm$/i });
    await user.type(input, "rejected");
    expect(confirmBtn).toBeDisabled();
    // Now actually match:
    await user.clear(input);
    await user.type(input, "REJECTED");
    expect(confirmBtn).toBeEnabled();
  });

  test("submit fires onConfirm once, then onClose", async () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <TypedConfirmDialog
        kind="typed-confirm"
        title="Wipe backups"
        body="Gone forever."
        word="WIPE"
        danger
        onConfirm={onConfirm}
        onClose={onClose}
      />,
    );
    await screen.findByRole("dialog");
    await user.type(screen.getByPlaceholderText("WIPE"), "WIPE");
    await user.click(screen.getByRole("button", { name: /delete permanently/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
