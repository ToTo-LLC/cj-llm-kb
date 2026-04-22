import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * ForkDialog (Plan 07 Task 20).
 *
 * Forks a thread at a specific turn into a new thread. The dialog collects:
 *   - carry mode: summary | full | none
 *   - mode: ask | brainstorm | draft
 *   - title hint: optional string
 *
 * On submit, ``forkThread({source_thread_id, turn_index, carry, mode,
 * title_hint})`` is called; the returned ``new_thread_id`` drives a
 * ``router.push("/chat/" + id)``.
 */

const { forkThreadMock, routerPushMock, pushToastMock } = vi.hoisted(() => ({
  forkThreadMock: vi.fn(),
  routerPushMock: vi.fn(),
  pushToastMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  forkThread: forkThreadMock,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPushMock }),
}));

vi.mock("@/lib/state/system-store", () => ({
  useSystemStore: Object.assign(
    (selector: (s: { pushToast: typeof pushToastMock }) => unknown) =>
      selector({ pushToast: pushToastMock }),
    { getState: () => ({ pushToast: pushToastMock }) },
  ),
}));

import { ForkDialog } from "@/components/dialogs/fork-dialog";

beforeEach(() => {
  forkThreadMock.mockReset();
  routerPushMock.mockReset();
  pushToastMock.mockReset();
  forkThreadMock.mockResolvedValue({
    text: "",
    data: { new_thread_id: "t-new-42" },
  });
});

describe("ForkDialog", () => {
  test("carry mode picker toggles between summary / full / none", async () => {
    const user = userEvent.setup();
    render(
      <ForkDialog
        kind="fork"
        threadId="t-src"
        turnIndex={2}
        summary="A short recap of the thread so far."
        onClose={vi.fn()}
      />,
    );
    // Carry radios live inside the "Carry context" radiogroup.
    const carryGroup = screen.getByRole("radiogroup", {
      name: /carry context/i,
    });
    const summaryBtn = screen.getByRole("radio", {
      name: /summary/i,
      hidden: false,
    }) as HTMLElement;
    const fullBtn = screen.getByRole("radio", { name: /full/i });
    const noneBtn = screen.getByRole("radio", { name: /fresh start/i });

    expect(carryGroup).toBeInTheDocument();
    expect(summaryBtn).toHaveAttribute("aria-checked", "true");
    expect(fullBtn).toHaveAttribute("aria-checked", "false");

    await user.click(fullBtn);
    expect(fullBtn).toHaveAttribute("aria-checked", "true");
    expect(summaryBtn).toHaveAttribute("aria-checked", "false");

    await user.click(noneBtn);
    expect(noneBtn).toHaveAttribute("aria-checked", "true");
    expect(fullBtn).toHaveAttribute("aria-checked", "false");
  });

  test("mode picker changes the selected chat mode", async () => {
    const user = userEvent.setup();
    render(
      <ForkDialog
        kind="fork"
        threadId="t-src"
        turnIndex={0}
        summary="s"
        onClose={vi.fn()}
      />,
    );

    const askBtn = screen.getByRole("radio", { name: /^ask$/i });
    const brainstormBtn = screen.getByRole("radio", {
      name: /^brainstorm$/i,
    });
    const draftBtn = screen.getByRole("radio", { name: /^draft$/i });

    // Default: "ask"
    expect(askBtn).toHaveAttribute("aria-checked", "true");

    await user.click(brainstormBtn);
    expect(brainstormBtn).toHaveAttribute("aria-checked", "true");
    expect(askBtn).toHaveAttribute("aria-checked", "false");

    await user.click(draftBtn);
    expect(draftBtn).toHaveAttribute("aria-checked", "true");
  });

  test("title hint input accepts free text", async () => {
    const user = userEvent.setup();
    render(
      <ForkDialog
        kind="fork"
        threadId="t-src"
        turnIndex={0}
        summary="s"
        onClose={vi.fn()}
      />,
    );
    const titleInput = screen.getByLabelText(/title/i) as HTMLInputElement;
    await user.type(titleInput, "Pricing spin-off");
    expect(titleInput.value).toBe("Pricing spin-off");
  });

  test("submit calls forkThread with correct args", async () => {
    const user = userEvent.setup();
    render(
      <ForkDialog
        kind="fork"
        threadId="t-src"
        turnIndex={3}
        summary="recap"
        onClose={vi.fn()}
      />,
    );
    // Flip mode to brainstorm, carry to "full", type a title.
    await user.click(screen.getByRole("radio", { name: /^brainstorm$/i }));
    await user.click(screen.getByRole("radio", { name: /full/i }));
    const titleInput = screen.getByLabelText(/title/i);
    await user.type(titleInput, "My fork");

    await user.click(screen.getByRole("button", { name: /fork thread/i }));

    await waitFor(() => {
      expect(forkThreadMock).toHaveBeenCalledTimes(1);
    });
    const args = forkThreadMock.mock.calls[0]![0] as {
      source_thread_id: string;
      turn_index: number;
      carry: string;
      mode: string;
      title_hint?: string;
    };
    expect(args.source_thread_id).toBe("t-src");
    expect(args.turn_index).toBe(3);
    expect(args.carry).toBe("full");
    expect(args.mode).toBe("brainstorm");
    expect(args.title_hint).toBe("My fork");
  });

  test("submit navigates to /chat/<new_thread_id> and closes", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <ForkDialog
        kind="fork"
        threadId="t-src"
        turnIndex={0}
        summary="s"
        onClose={onClose}
      />,
    );
    await user.click(screen.getByRole("button", { name: /fork thread/i }));

    await waitFor(() => {
      expect(routerPushMock).toHaveBeenCalledWith("/chat/t-new-42");
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
