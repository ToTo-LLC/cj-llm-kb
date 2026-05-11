import { describe, expect, test, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import { RepairConfigDialog } from "@/components/dialogs/repair-config-dialog";

/**
 * RepairConfigDialog (Plan 16 Task 33 — full polish).
 *
 * Pins the post-Task-9 surface: Re-run repair / per-step results panel /
 * Re-apply button / Cancel button. Legacy Task 9 SCAFFOLD pins
 * (closed-state hidden, title + description visible, Cancel calls
 * onClose, Esc dismisses) are retained — the new dialog is
 * backward-compatible with the SCAFFOLD prop shape (``onRunRepair`` is
 * still accepted; it now fires on a successful Re-apply rather than on
 * the Re-run path).
 *
 * The API client is mocked at module level so each case can swap in the
 * payload it needs. Two functions are stubbed:
 *   - ``repairConfig()`` — returns a ``ToolResponse<RepairConfigData>``.
 *   - ``repairConfigApply(payload)`` — resolves on success / rejects on
 *     failure for the error-path test.
 */

vi.mock("@/lib/api/tools", () => ({
  repairConfig: vi.fn(),
  repairConfigApply: vi.fn(),
}));

import { repairConfig, repairConfigApply } from "@/lib/api/tools";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("RepairConfigDialog (closed)", () => {
  test("does not render dialog content when isOpen=false", () => {
    render(<RepairConfigDialog isOpen={false} onClose={vi.fn()} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /repair config/i }),
    ).not.toBeInTheDocument();
  });
});

describe("RepairConfigDialog (open — initial state)", () => {
  test("renders title, description, Re-run / Re-apply / Cancel buttons", async () => {
    render(<RepairConfigDialog isOpen onClose={vi.fn()} />);
    await screen.findByRole("dialog");

    expect(
      screen.getByRole("heading", { name: /repair config/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Running repair reloads .* will be discarded\./i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^Re-run repair$/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^Re-apply$/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^cancel$/i }),
    ).toBeInTheDocument();
  });

  test("Re-apply is disabled before any run", async () => {
    render(<RepairConfigDialog isOpen onClose={vi.fn()} />);
    await screen.findByRole("dialog");

    const reapply = screen.getByRole("button", { name: /^Re-apply$/i });
    expect(reapply).toBeDisabled();
  });

  test("Cancel button fires onClose", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<RepairConfigDialog isOpen onClose={onClose} />);
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: /^cancel$/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("Esc key dismisses the dialog (Radix wrapper behavior)", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<RepairConfigDialog isOpen onClose={onClose} />);
    await screen.findByRole("dialog");

    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("RepairConfigDialog — Re-run flow", () => {
  test("Re-run click invokes API + renders results", async () => {
    vi.mocked(repairConfig).mockResolvedValueOnce({
      text: "ok",
      data: {
        steps: [
          { step: "read_primary", status: "success", message: "Read OK" },
          {
            step: "validate_primary",
            status: "success",
            message: "Schema valid",
          },
        ],
        repair_changes_pending: false,
        repaired_config: { active_domain: "research" },
      },
    });

    const user = userEvent.setup();
    render(<RepairConfigDialog isOpen onClose={vi.fn()} />);
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: /^Re-run repair$/i }));

    await waitFor(() => {
      expect(repairConfig).toHaveBeenCalledTimes(1);
    });
    // Step rows render the canonical labels per STEP_LABELS.
    await waitFor(() => {
      expect(screen.getByText("Read config.json")).toBeInTheDocument();
    });
    expect(screen.getByText("Validate config.json")).toBeInTheDocument();
    // Re-apply stays disabled when nothing to apply.
    expect(screen.getByRole("button", { name: /^Re-apply$/i })).toBeDisabled();
    // The "nothing to apply" hint surfaces.
    expect(
      screen.getByText(/In-memory config matches the recovered config/i),
    ).toBeInTheDocument();
  });

  test("fallback-to-bak run enables Re-apply", async () => {
    vi.mocked(repairConfig).mockResolvedValueOnce({
      text: "ok",
      data: {
        steps: [
          {
            step: "read_primary",
            status: "warning",
            message: "config.json not found; falling back",
          },
          { step: "read_backup", status: "success", message: "Read OK from .bak" },
          {
            step: "validate_backup",
            status: "success",
            message: "Restored from backup",
          },
        ],
        repair_changes_pending: true,
        repaired_config: { active_domain: "work" },
      },
    });

    const user = userEvent.setup();
    render(<RepairConfigDialog isOpen onClose={vi.fn()} />);
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: /^Re-run repair$/i }));

    await waitFor(() => {
      expect(screen.getByText("Read config.json")).toBeInTheDocument();
    });
    expect(screen.getByText("Read config.json.bak")).toBeInTheDocument();
    expect(screen.getByText("Validate config.json.bak")).toBeInTheDocument();
    // Diff present → Re-apply enables.
    expect(screen.getByRole("button", { name: /^Re-apply$/i })).toBeEnabled();
  });

  test("Re-run failure surfaces inline error", async () => {
    vi.mocked(repairConfig).mockRejectedValueOnce(new Error("kaboom"));

    const user = userEvent.setup();
    render(<RepairConfigDialog isOpen onClose={vi.fn()} />);
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: /^Re-run repair$/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/kaboom/);
    });
    // Dialog stays open, Re-apply still disabled.
    expect(screen.getByRole("button", { name: /^Re-apply$/i })).toBeDisabled();
  });
});

describe("RepairConfigDialog — Re-apply flow", () => {
  test("Re-apply click writes payload then closes the dialog", async () => {
    vi.mocked(repairConfig).mockResolvedValueOnce({
      text: "ok",
      data: {
        steps: [
          { step: "read_backup", status: "success", message: "ok" },
          { step: "validate_backup", status: "success", message: "valid" },
        ],
        repair_changes_pending: true,
        repaired_config: { active_domain: "work", web_port: 5500 },
      },
    });
    vi.mocked(repairConfigApply).mockResolvedValueOnce({
      text: "applied",
      data: { status: "applied", path: "/x", config_version: 2 },
    });

    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<RepairConfigDialog isOpen onClose={onClose} />);
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: /^Re-run repair$/i }));
    // Wait for Re-apply to enable.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /^Re-apply$/i })).toBeEnabled(),
    );

    await user.click(screen.getByRole("button", { name: /^Re-apply$/i }));

    await waitFor(() => {
      expect(repairConfigApply).toHaveBeenCalledWith({
        active_domain: "work",
        web_port: 5500,
      });
    });
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });

  test("Re-apply failure renders inline error and keeps dialog open", async () => {
    vi.mocked(repairConfig).mockResolvedValueOnce({
      text: "ok",
      data: {
        steps: [{ step: "read_backup", status: "success", message: "ok" }],
        repair_changes_pending: true,
        repaired_config: { active_domain: "research" },
      },
    });
    vi.mocked(repairConfigApply).mockRejectedValueOnce(
      new Error("disk full"),
    );

    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<RepairConfigDialog isOpen onClose={onClose} />);
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: /^Re-run repair$/i }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /^Re-apply$/i })).toBeEnabled(),
    );

    await user.click(screen.getByRole("button", { name: /^Re-apply$/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/disk full/i),
    );
    // Dialog stays open.
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  test("legacy onRunRepair prop fires after a successful Re-apply", async () => {
    vi.mocked(repairConfig).mockResolvedValueOnce({
      text: "ok",
      data: {
        steps: [{ step: "read_backup", status: "success", message: "ok" }],
        repair_changes_pending: true,
        repaired_config: { active_domain: "research" },
      },
    });
    vi.mocked(repairConfigApply).mockResolvedValueOnce({
      text: "applied",
      data: { status: "applied", path: "/x", config_version: 1 },
    });

    const onClose = vi.fn();
    const onRunRepair = vi.fn();
    const user = userEvent.setup();
    render(
      <RepairConfigDialog
        isOpen
        onClose={onClose}
        onRunRepair={onRunRepair}
      />,
    );
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: /^Re-run repair$/i }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /^Re-apply$/i })).toBeEnabled(),
    );
    await user.click(screen.getByRole("button", { name: /^Re-apply$/i }));

    await waitFor(() => expect(onRunRepair).toHaveBeenCalledTimes(1));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("RepairConfigDialog — keyboard a11y", () => {
  test("Footer DOM order is Re-run → Re-apply → Cancel (Cancel last)", async () => {
    // Plan 17 T18: Cancel sits at the end of the tab cycle per the
    // escape-hatch convention. Step rows live in the body and tab
    // BEFORE the footer under Radix's DOM-order traversal, so the full
    // natural Tab order is: step rows → Re-run → Re-apply → Cancel.
    render(<RepairConfigDialog isOpen onClose={vi.fn()} />);
    await screen.findByRole("dialog");

    const dialog = screen.getByRole("dialog");
    const buttons = within(dialog)
      .getAllByRole("button")
      .filter((el) =>
        /^(re-run repair|re-apply|cancel)$/i.test(el.textContent ?? ""),
      );
    const names = buttons.map((b) => (b.textContent ?? "").trim());
    expect(names).toEqual(["Re-run repair", "Re-apply", "Cancel"]);
  });

  test("Tab walks step rows → Re-run → Re-apply → Cancel after a run", async () => {
    // Plan 17 T18: pin natural Tab order (DOM order under Radix). The
    // previous test only verified tabIndex=0 on step rows; this one
    // walks user.tab() through the cycle to catch any future reorder.
    vi.mocked(repairConfig).mockResolvedValueOnce({
      text: "ok",
      data: {
        steps: [
          { step: "read_primary", status: "success", message: "Read OK" },
          {
            step: "validate_primary",
            status: "success",
            message: "Schema valid",
          },
        ],
        repair_changes_pending: true,
        repaired_config: { active_domain: "research" },
      },
    });

    const user = userEvent.setup();
    render(<RepairConfigDialog isOpen onClose={vi.fn()} />);
    await screen.findByRole("dialog");

    const reRun = screen.getByRole("button", { name: /^Re-run repair$/i });
    await user.click(reRun);
    await waitFor(() =>
      expect(screen.getByText("Read config.json")).toBeInTheDocument(),
    );

    // Identify the expected tab targets in DOM order.
    const stepRows = screen
      .getAllByRole("listitem")
      .filter((el) => el.tagName === "LI");
    expect(stepRows).toHaveLength(2);
    for (const row of stepRows) {
      expect(row).toHaveAttribute("tabindex", "0");
    }
    const reApply = screen.getByRole("button", { name: /^Re-apply$/i });
    const cancel = screen.getByRole("button", { name: /^cancel$/i });

    // Walk from the start of the dialog. The Re-run button is
    // currently focused (post-click); reset focus to a stable starting
    // point by focusing the first step row.
    stepRows[0]!.focus();
    expect(document.activeElement).toBe(stepRows[0]);

    await user.tab();
    expect(document.activeElement).toBe(stepRows[1]);
    await user.tab();
    expect(document.activeElement).toBe(reRun);
    await user.tab();
    expect(document.activeElement).toBe(reApply);
    await user.tab();
    expect(document.activeElement).toBe(cancel);
  });
});

describe("RepairConfigDialog — design tokens (no hex literals)", () => {
  test("step row icon colors resolve via CSS vars (var(--ok|warn|danger))", async () => {
    // Plan 17 T18: ICON_BY_STATUS previously carried hex fallbacks
    // (e.g. ``var(--ok, #96B6A6)``); those JS-string hex literals
    // bypassed the Plan 16 T13 stylelint ``color-no-hex`` rule. Pin
    // the contract by asserting the inline ``color`` on each step's
    // icon contains the token reference with NO hex.
    vi.mocked(repairConfig).mockResolvedValueOnce({
      text: "ok",
      data: {
        steps: [
          { step: "read_primary", status: "success", message: "ok" },
          { step: "validate_primary", status: "warning", message: "warn" },
          { step: "apply_defaults", status: "error", message: "boom" },
        ],
        repair_changes_pending: false,
        repaired_config: {},
      },
    });

    const user = userEvent.setup();
    render(<RepairConfigDialog isOpen onClose={vi.fn()} />);
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: /^Re-run repair$/i }));
    await waitFor(() =>
      expect(screen.getByText("Read config.json")).toBeInTheDocument(),
    );

    const stepRows = screen
      .getAllByRole("listitem")
      .filter((el) => el.tagName === "LI");

    const inlineColors = stepRows.map((row) => {
      const icon = row.querySelector("svg");
      return (icon as SVGElement | null)?.style.color ?? "";
    });

    // Vitest's jsdom does not resolve ``var()`` against the cascade,
    // so the inline-style value stays as the literal string we set.
    expect(inlineColors[0]).toBe("var(--ok)");
    expect(inlineColors[1]).toBe("var(--warn)");
    expect(inlineColors[2]).toBe("var(--danger)");
    for (const c of inlineColors) {
      expect(c).not.toMatch(/#[0-9a-fA-F]{3,8}/);
    }
  });
});

describe("RepairConfigDialog — mountedRef guards async setState", () => {
  test("unmount during in-flight Re-run does not warn / error", async () => {
    // Plan 17 T18: simulate the dialog being closed mid-RPC. Before
    // the mountedRef guard, the post-await ``setState`` would log a
    // React warning ("Can't perform a React state update on an
    // unmounted component") on React 18 and is a hard error path on
    // React 19. Assert NO console.error is emitted between unmount
    // and the resolved promise.
    let resolveRepair!: (value: Awaited<ReturnType<typeof repairConfig>>) => void;
    vi.mocked(repairConfig).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveRepair = resolve;
        }),
    );

    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      const user = userEvent.setup();
      const { unmount } = render(
        <RepairConfigDialog isOpen onClose={vi.fn()} />,
      );
      await screen.findByRole("dialog");

      // Fire the async handler; do NOT await it yet.
      await user.click(screen.getByRole("button", { name: /^Re-run repair$/i }));

      // Unmount BEFORE the RPC resolves.
      unmount();

      // Now resolve the in-flight RPC — the post-await setState would
      // fire here without the mountedRef guard.
      resolveRepair({
        text: "ok",
        data: {
          steps: [{ step: "read_primary", status: "success", message: "ok" }],
          repair_changes_pending: false,
          repaired_config: {},
        },
      });

      // Yield two microtask ticks so the awaiting code path runs.
      await Promise.resolve();
      await Promise.resolve();

      // No "state update on unmounted component" (or any other) React
      // warning should have been emitted.
      const reactWarnings = errorSpy.mock.calls
        .map((args) => String(args[0] ?? ""))
        .filter((msg) =>
          /unmounted|memory leak|state update on an unmounted/i.test(msg),
        );
      expect(reactWarnings).toEqual([]);
    } finally {
      errorSpy.mockRestore();
    }
  });

  test("unmount during in-flight Re-apply does not warn / error", async () => {
    // Same shape as the Re-run case but for the apply path. The
    // failure mode would be setState inside the catch branch firing
    // post-unmount when the apply RPC rejects after close.
    vi.mocked(repairConfig).mockResolvedValueOnce({
      text: "ok",
      data: {
        steps: [{ step: "read_backup", status: "success", message: "ok" }],
        repair_changes_pending: true,
        repaired_config: { active_domain: "research" },
      },
    });
    let rejectApply!: (err: Error) => void;
    vi.mocked(repairConfigApply).mockImplementationOnce(
      () =>
        new Promise((_, reject) => {
          rejectApply = reject;
        }),
    );

    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      const user = userEvent.setup();
      const { unmount } = render(
        <RepairConfigDialog isOpen onClose={vi.fn()} />,
      );
      await screen.findByRole("dialog");

      await user.click(screen.getByRole("button", { name: /^Re-run repair$/i }));
      await waitFor(() =>
        expect(
          screen.getByRole("button", { name: /^Re-apply$/i }),
        ).toBeEnabled(),
      );

      await user.click(screen.getByRole("button", { name: /^Re-apply$/i }));

      // Unmount BEFORE the apply RPC rejects.
      unmount();

      rejectApply(new Error("disk full"));

      await Promise.resolve();
      await Promise.resolve();

      const reactWarnings = errorSpy.mock.calls
        .map((args) => String(args[0] ?? ""))
        .filter((msg) =>
          /unmounted|memory leak|state update on an unmounted/i.test(msg),
        );
      expect(reactWarnings).toEqual([]);
    } finally {
      errorSpy.mockRestore();
    }
  });
});
