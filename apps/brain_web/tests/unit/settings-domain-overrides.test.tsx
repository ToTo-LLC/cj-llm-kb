import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * DomainOverrideForm + PanelDomains expand/collapse (Plan 11 Task 7).
 *
 * Surfaces tested:
 *  - Form for a domain with NO overrides shows placeholder = "uses
 *    global" and no Reset buttons.
 *  - Setting classify_model and committing (blur) calls
 *    ``brain_config_set`` with key
 *    ``domain_overrides.<slug>.classify_model`` and the typed value.
 *  - "Reset to global" buttons send ``null`` for that field.
 *  - Out-of-range temperature surfaces a validation error and the
 *    save call is suppressed.
 *  - Expand caret toggles the form's visibility and triggers a
 *    ``configGet`` read for the slug's overrides.
 *  - After every successful save the parent re-fetches override
 *    state via configGet (cache-fan-out per Plan 10 lessons).
 */

const {
  listDomainsMock,
  configGetMock,
  configSetMock,
  brainDeleteDomainMock,
  setPrivacyRailedMock,
} = vi.hoisted(() => ({
  listDomainsMock: vi.fn(),
  configGetMock: vi.fn(),
  configSetMock: vi.fn(),
  brainDeleteDomainMock: vi.fn(),
  setPrivacyRailedMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  listDomains: listDomainsMock,
  configGet: configGetMock,
  configSet: configSetMock,
  brainDeleteDomain: brainDeleteDomainMock,
  setPrivacyRailed: setPrivacyRailedMock,
  // ``createDomain`` is referenced by ``DomainForm`` even though we
  // don't exercise it here — supply a stub so the component module
  // doesn't fail to mock-resolve.
  createDomain: vi.fn(),
}));

const { openDialogMock } = vi.hoisted(() => ({ openDialogMock: vi.fn() }));

vi.mock("@/lib/state/dialogs-store", () => ({
  useDialogsStore: Object.assign(
    (selector: (s: { open: typeof openDialogMock }) => unknown) =>
      selector({ open: openDialogMock }),
    { getState: () => ({ open: openDialogMock }) },
  ),
}));

const { pushToastStub } = vi.hoisted(() => ({ pushToastStub: vi.fn() }));

vi.mock("@/lib/state/system-store", () => ({
  useSystemStore: Object.assign(
    (selector: (s: { pushToast: () => void }) => unknown) =>
      selector({ pushToast: pushToastStub }),
    { getState: () => ({ pushToast: pushToastStub }) },
  ),
}));

import { PanelDomains } from "@/components/settings/panel-domains";

beforeEach(() => {
  listDomainsMock.mockReset();
  configGetMock.mockReset();
  configSetMock.mockReset();
  brainDeleteDomainMock.mockReset();
  setPrivacyRailedMock.mockReset();
  openDialogMock.mockReset();
  pushToastStub.mockReset();

  listDomainsMock.mockResolvedValue({
    text: "",
    data: { domains: ["research", "work", "personal", "hobby"] },
  });
  // Default: no overrides, default privacy-rail (personal only).
  configGetMock.mockImplementation((args: { key: string }) => {
    if (args.key === "domain_overrides") {
      return Promise.resolve({ text: "", data: { key: args.key, value: {} } });
    }
    if (args.key === "privacy_railed") {
      return Promise.resolve({
        text: "",
        data: { key: args.key, value: ["personal"] },
      });
    }
    return Promise.resolve({ text: "", data: { key: args.key, value: null } });
  });
  configSetMock.mockResolvedValue({ text: "", data: {} });
  setPrivacyRailedMock.mockResolvedValue({ text: "", data: {} });
});

describe("PanelDomains — domain overrides (Plan 11 Task 7)", () => {
  test("expand caret toggles the override form and triggers configGet for the slug", async () => {
    const user = userEvent.setup();
    render(<PanelDomains />);
    await waitFor(() =>
      expect(screen.getByText("hobby")).toBeInTheDocument(),
    );

    const caret = screen.getByRole("button", {
      name: /expand hobby overrides/i,
    });
    expect(caret).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.queryByTestId("domain-override-form-hobby"),
    ).not.toBeInTheDocument();

    await user.click(caret);

    await waitFor(() =>
      expect(
        screen.getByTestId("domain-override-form-hobby"),
      ).toBeInTheDocument(),
    );
    // configGet was called for domain_overrides on first expand.
    const overrideCalls = configGetMock.mock.calls.filter(
      (c) => (c[0] as { key: string }).key === "domain_overrides",
    );
    expect(overrideCalls.length).toBeGreaterThan(0);
  });

  test("form for a domain with no overrides shows placeholder 'uses global' and no Reset buttons", async () => {
    const user = userEvent.setup();
    render(<PanelDomains />);
    await waitFor(() =>
      expect(screen.getByText("hobby")).toBeInTheDocument(),
    );
    await user.click(
      screen.getByRole("button", { name: /expand hobby overrides/i }),
    );
    await waitFor(() =>
      expect(
        screen.getByTestId("domain-override-form-hobby"),
      ).toBeInTheDocument(),
    );

    // Each of classify_model / default_model / temperature /
    // max_output_tokens uses placeholder "uses global".
    const placeholders = screen.getAllByPlaceholderText(/uses global/i);
    expect(placeholders.length).toBe(4);

    // No Reset buttons until at least one field has an override set.
    expect(
      screen.queryByRole("button", { name: /reset .* to global/i }),
    ).not.toBeInTheDocument();
  });

  test("setting classify_model and blurring calls configSet with the dotted key + value", async () => {
    const user = userEvent.setup();
    render(<PanelDomains />);
    await waitFor(() =>
      expect(screen.getByText("hobby")).toBeInTheDocument(),
    );
    await user.click(
      screen.getByRole("button", { name: /expand hobby overrides/i }),
    );
    await waitFor(() =>
      expect(
        screen.getByTestId("domain-override-form-hobby"),
      ).toBeInTheDocument(),
    );

    const input = screen.getByLabelText(/classify model/i);
    await user.click(input);
    await user.type(input, "claude-haiku-4-5-20251001");
    // Blur commits the change.
    await user.tab();

    await waitFor(() => {
      expect(configSetMock).toHaveBeenCalled();
    });
    const call = configSetMock.mock.calls.find(
      (c) =>
        (c[0] as { key: string }).key === "domain_overrides.hobby.classify_model",
    );
    expect(call).toBeDefined();
    expect((call![0] as { value: unknown }).value).toBe(
      "claude-haiku-4-5-20251001",
    );
  });

  test("'Reset to global' button sends null for that field", async () => {
    const user = userEvent.setup();
    // Prime the override read with an existing classify_model override
    // so the Reset button is visible.
    configGetMock.mockImplementation((args: { key: string }) => {
      if (args.key === "domain_overrides") {
        return Promise.resolve({
          text: "",
          data: {
            key: args.key,
            value: { hobby: { classify_model: "haiku-X" } },
          },
        });
      }
      if (args.key === "privacy_railed") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: ["personal"] },
        });
      }
      return Promise.resolve({ text: "", data: { key: args.key, value: null } });
    });

    render(<PanelDomains />);
    await waitFor(() =>
      expect(screen.getByText("hobby")).toBeInTheDocument(),
    );
    await user.click(
      screen.getByRole("button", { name: /expand hobby overrides/i }),
    );
    // Wait for the override-bearing form to render (the value is read
    // async after expand). Query by role "textbox" + name to scope
    // past the per-field "Reset … to global" buttons whose aria-label
    // also contains the field title (and would otherwise collide with
    // a plain ``getByLabelText`` query).
    await waitFor(() => {
      const input = screen.getByRole("textbox", {
        name: /classify model/i,
      }) as HTMLInputElement;
      expect(input.value).toBe("haiku-X");
    });

    const resetBtn = screen.getByRole("button", {
      name: /reset classify model to global/i,
    });
    await user.click(resetBtn);

    await waitFor(() => {
      expect(configSetMock).toHaveBeenCalled();
    });
    const call = configSetMock.mock.calls.find(
      (c) =>
        (c[0] as { key: string }).key === "domain_overrides.hobby.classify_model",
    );
    expect(call).toBeDefined();
    expect((call![0] as { value: unknown }).value).toBeNull();
  });

  test("out-of-range temperature surfaces inline validation and suppresses save", async () => {
    const user = userEvent.setup();
    render(<PanelDomains />);
    await waitFor(() =>
      expect(screen.getByText("hobby")).toBeInTheDocument(),
    );
    await user.click(
      screen.getByRole("button", { name: /expand hobby overrides/i }),
    );
    await waitFor(() =>
      expect(
        screen.getByTestId("domain-override-form-hobby"),
      ).toBeInTheDocument(),
    );

    const tempInput = screen.getByLabelText(/temperature/i);
    await user.click(tempInput);
    await user.type(tempInput, "5.0"); // out of range (0..1.5)
    expect(tempInput).toHaveAttribute("aria-invalid", "true");
    // Validation message is rendered.
    expect(
      screen.getByText(/must be a number between 0 and 1\.5/i),
    ).toBeInTheDocument();

    // Blurring with an invalid value should NOT call configSet for
    // temperature.
    await user.tab();
    const tempCalls = configSetMock.mock.calls.filter((c) =>
      (c[0] as { key: string }).key.endsWith(".temperature"),
    );
    expect(tempCalls.length).toBe(0);
  });

  test("max_output_tokens validation rejects negative + non-integer values", async () => {
    const user = userEvent.setup();
    render(<PanelDomains />);
    await waitFor(() =>
      expect(screen.getByText("hobby")).toBeInTheDocument(),
    );
    await user.click(
      screen.getByRole("button", { name: /expand hobby overrides/i }),
    );
    await waitFor(() =>
      expect(
        screen.getByTestId("domain-override-form-hobby"),
      ).toBeInTheDocument(),
    );

    const maxInput = screen.getByLabelText(/max output tokens/i);
    // Non-integer.
    await user.click(maxInput);
    await user.type(maxInput, "1.5");
    expect(maxInput).toHaveAttribute("aria-invalid", "true");

    // Negative.
    await user.clear(maxInput);
    await user.type(maxInput, "-100");
    expect(maxInput).toHaveAttribute("aria-invalid", "true");

    // Valid positive integer clears the error.
    await user.clear(maxInput);
    await user.type(maxInput, "2048");
    expect(maxInput).toHaveAttribute("aria-invalid", "false");
  });

  test("autonomous_mode toggle calls configSet with bool, Reset clears with null", async () => {
    const user = userEvent.setup();
    // Prime with an existing autonomous override so the Reset button
    // is visible and the toggle starts checked.
    configGetMock.mockImplementation((args: { key: string }) => {
      if (args.key === "domain_overrides") {
        return Promise.resolve({
          text: "",
          data: {
            key: args.key,
            value: { hobby: { autonomous_mode: true } },
          },
        });
      }
      if (args.key === "privacy_railed") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: ["personal"] },
        });
      }
      return Promise.resolve({ text: "", data: { key: args.key, value: null } });
    });

    render(<PanelDomains />);
    await waitFor(() =>
      expect(screen.getByText("hobby")).toBeInTheDocument(),
    );
    await user.click(
      screen.getByRole("button", { name: /expand hobby overrides/i }),
    );
    await waitFor(() => {
      const row = screen.getByTestId("override-row-autonomous-hobby");
      const sw = row.querySelector('[role="switch"]') as HTMLElement | null;
      expect(sw).toBeTruthy();
      // The override was true on initial read.
      expect(sw!.getAttribute("aria-checked")).toBe("true");
    });

    // Reset to global clears the override.
    const resetBtn = screen.getByRole("button", {
      name: /reset autonomous_mode override for hobby/i,
    });
    await user.click(resetBtn);
    await waitFor(() => {
      const call = configSetMock.mock.calls.find(
        (c) =>
          (c[0] as { key: string }).key ===
          "domain_overrides.hobby.autonomous_mode",
      );
      expect(call).toBeDefined();
      expect((call![0] as { value: unknown }).value).toBeNull();
    });
  });

  test("after a successful save the parent re-fetches the override state", async () => {
    const user = userEvent.setup();
    render(<PanelDomains />);
    await waitFor(() =>
      expect(screen.getByText("hobby")).toBeInTheDocument(),
    );
    await user.click(
      screen.getByRole("button", { name: /expand hobby overrides/i }),
    );
    await waitFor(() =>
      expect(
        screen.getByTestId("domain-override-form-hobby"),
      ).toBeInTheDocument(),
    );

    // Count how many domain_overrides reads ran on initial expand.
    const initialReads = configGetMock.mock.calls.filter(
      (c) => (c[0] as { key: string }).key === "domain_overrides",
    ).length;

    const input = screen.getByLabelText(/classify model/i);
    await user.click(input);
    await user.type(input, "haiku-Y");
    await user.tab();

    await waitFor(() => {
      const finalReads = configGetMock.mock.calls.filter(
        (c) => (c[0] as { key: string }).key === "domain_overrides",
      ).length;
      // At least one extra read fired post-save (cache fan-out per
      // Plan 10 lessons).
      expect(finalReads).toBeGreaterThan(initialReads);
    });
  });
});
