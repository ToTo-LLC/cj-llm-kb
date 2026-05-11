import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * DomainOverrideForm (Plan 17 Task 5) — domain-overrides-store migration.
 *
 * Pins five behaviours after the refactor that routes the four LLM
 * override fields through ``useDomainOverridesStore.getState().setOverrideField``
 * while keeping ``autonomous_mode`` writes via ``configSet`` directly
 * (``autonomous_mode`` is intentionally excluded from ``DomainOverrideEntry``).
 *
 *   1. LLM field save calls ``setOverrideField`` — blurring classify_model
 *      with a new value calls the store mutator, not configSet.
 *   2. ``autonomous_mode`` toggle calls ``configSet`` — the store path is
 *      NOT taken for this field.
 *   3. Reset (null) for a LLM field calls ``setOverrideField(slug, field, null)``.
 *   4. Success toast shown after a successful save.
 *   5. Error toast shown when ``setOverrideField`` throws.
 *
 * Mocks: ``useDomainOverridesStore`` + ``configSet`` (for autonomous_mode).
 * The system-store is NOT mocked — its ``toasts`` array is read directly
 * (matches the pattern in ``panel-budget.test.tsx``).
 */

// ---- Hoisted mock factories ----

const { setOverrideFieldMock, configSetMock } = vi.hoisted(() => ({
  setOverrideFieldMock: vi.fn(),
  configSetMock: vi.fn(),
}));

vi.mock("@/lib/state/domain-overrides-store", () => ({
  useDomainOverridesStore: Object.assign(
    // Selector calls (the component uses pushToast from system-store;
    // no selector reads from this store in the component body, only
    // the static getState() write path).
    vi.fn(),
    {
      getState: vi.fn(() => ({
        setOverrideField: setOverrideFieldMock,
      })),
    },
  ),
}));

vi.mock("@/lib/api/tools", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/tools")>(
    "@/lib/api/tools",
  );
  return {
    ...actual,
    configSet: (...args: unknown[]) => configSetMock(...args),
  };
});

// ---- Imports (after mocks) ----

import {
  DomainOverrideForm,
  type DomainOverrideValues,
} from "@/components/settings/domain-override-form";
import { useSystemStore } from "@/lib/state/system-store";

// ---- Helpers ----

const TEST_SLUG = "research";

const EMPTY_OVERRIDE: DomainOverrideValues = {
  classify_model: null,
  default_model: null,
  temperature: null,
  max_output_tokens: null,
  autonomous_mode: null,
};

function resetSystemStore() {
  useSystemStore.setState({
    connection: "ok",
    budgetWallOpen: false,
    midTurn: null,
    draggingFile: false,
    toasts: [],
  });
}

function renderForm(
  initialValues: Partial<DomainOverrideValues> = {},
  onChanged?: () => void,
) {
  const values: DomainOverrideValues = { ...EMPTY_OVERRIDE, ...initialValues };
  return render(
    <DomainOverrideForm
      slug={TEST_SLUG}
      initialValues={values}
      onChanged={onChanged}
    />,
  );
}

// ---- Tests ----

beforeEach(() => {
  setOverrideFieldMock.mockReset();
  configSetMock.mockReset();
  resetSystemStore();
});

describe("DomainOverrideForm — LLM field routes to setOverrideField", () => {
  test("blurring classify_model with a new value calls setOverrideField", async () => {
    const user = userEvent.setup();
    setOverrideFieldMock.mockResolvedValue(undefined);

    renderForm({ classify_model: null });

    const input = screen.getByRole("textbox", {
      name: /classify model/i,
    }) as HTMLInputElement;

    await user.click(input);
    await user.type(input, "claude-3-haiku");
    await user.tab(); // blur

    await waitFor(() => {
      expect(setOverrideFieldMock).toHaveBeenCalledTimes(1);
      expect(setOverrideFieldMock).toHaveBeenCalledWith(
        TEST_SLUG,
        "classify_model",
        "claude-3-haiku",
      );
    });
    // configSet must NOT be called for LLM fields.
    expect(configSetMock).not.toHaveBeenCalled();
  });

  test("blurring default_model with a new value calls setOverrideField", async () => {
    const user = userEvent.setup();
    setOverrideFieldMock.mockResolvedValue(undefined);

    renderForm({ default_model: null });

    const input = screen.getByRole("textbox", {
      name: /default model/i,
    }) as HTMLInputElement;

    await user.click(input);
    await user.type(input, "claude-opus-4");
    await user.tab();

    await waitFor(() => {
      expect(setOverrideFieldMock).toHaveBeenCalledTimes(1);
      expect(setOverrideFieldMock).toHaveBeenCalledWith(
        TEST_SLUG,
        "default_model",
        "claude-opus-4",
      );
    });
    expect(configSetMock).not.toHaveBeenCalled();
  });

  test("blurring temperature with a new value calls setOverrideField with a number", async () => {
    const user = userEvent.setup();
    setOverrideFieldMock.mockResolvedValue(undefined);

    const { container } = renderForm({ temperature: null });

    // Temperature and max_output_tokens inputs have no accessible label
    // (they use aria-describedby for the hint only). Select by id attribute.
    const input = container.querySelector(
      `#override-${TEST_SLUG}-temperature`,
    ) as HTMLInputElement;
    expect(input).not.toBeNull();

    await user.click(input);
    await user.type(input, "0.7");
    await user.tab();

    await waitFor(() => {
      expect(setOverrideFieldMock).toHaveBeenCalledTimes(1);
      expect(setOverrideFieldMock).toHaveBeenCalledWith(
        TEST_SLUG,
        "temperature",
        0.7,
      );
    });
    expect(configSetMock).not.toHaveBeenCalled();
  });

  test("blurring max_output_tokens with a new value calls setOverrideField with a number", async () => {
    const user = userEvent.setup();
    setOverrideFieldMock.mockResolvedValue(undefined);

    const { container } = renderForm({ max_output_tokens: null });

    const input = container.querySelector(
      `#override-${TEST_SLUG}-max-output-tokens`,
    ) as HTMLInputElement;
    expect(input).not.toBeNull();

    await user.click(input);
    await user.type(input, "4096");
    await user.tab();

    await waitFor(() => {
      expect(setOverrideFieldMock).toHaveBeenCalledTimes(1);
      expect(setOverrideFieldMock).toHaveBeenCalledWith(
        TEST_SLUG,
        "max_output_tokens",
        4096,
      );
    });
    expect(configSetMock).not.toHaveBeenCalled();
  });
});

describe("DomainOverrideForm — autonomous_mode routes to configSet", () => {
  test("toggling the autonomous switch calls configSet, not setOverrideField", async () => {
    const user = userEvent.setup();
    configSetMock.mockResolvedValue(undefined);

    renderForm({ autonomous_mode: false });

    // The Switch renders as role="switch".
    const sw = screen.getByRole("switch", {
      name: /autonomous mode/i,
    });

    await user.click(sw);

    await waitFor(() => {
      expect(configSetMock).toHaveBeenCalledTimes(1);
      expect(configSetMock).toHaveBeenCalledWith({
        key: `domain_overrides.${TEST_SLUG}.autonomous_mode`,
        value: true,
      });
    });
    // The store write path must NOT fire for autonomous_mode.
    expect(setOverrideFieldMock).not.toHaveBeenCalled();
  });

  test("toggling autonomous switch OFF calls configSet with false", async () => {
    const user = userEvent.setup();
    configSetMock.mockResolvedValue(undefined);

    // Start with autonomous_mode: true → clicking turns it off.
    renderForm({ autonomous_mode: true });

    const sw = screen.getByRole("switch", {
      name: /autonomous mode/i,
    });

    await user.click(sw);

    await waitFor(() => {
      expect(configSetMock).toHaveBeenCalledTimes(1);
      expect(configSetMock).toHaveBeenCalledWith({
        key: `domain_overrides.${TEST_SLUG}.autonomous_mode`,
        value: false,
      });
    });
    expect(setOverrideFieldMock).not.toHaveBeenCalled();
  });
});

describe("DomainOverrideForm — reset (null) for LLM fields", () => {
  test("clicking Reset to global for classify_model calls setOverrideField with null", async () => {
    const user = userEvent.setup();
    setOverrideFieldMock.mockResolvedValue(undefined);

    // Set a non-null value so the Reset button renders.
    renderForm({ classify_model: "claude-3-haiku" });

    const resetBtn = screen.getByRole("button", {
      name: /reset classify model to global/i,
    });

    await user.click(resetBtn);

    await waitFor(() => {
      expect(setOverrideFieldMock).toHaveBeenCalledTimes(1);
      expect(setOverrideFieldMock).toHaveBeenCalledWith(
        TEST_SLUG,
        "classify_model",
        null,
      );
    });
    expect(configSetMock).not.toHaveBeenCalled();
  });

  test("clicking Reset to global for temperature calls setOverrideField with null", async () => {
    const user = userEvent.setup();
    setOverrideFieldMock.mockResolvedValue(undefined);

    renderForm({ temperature: 0.8 });

    const resetBtn = screen.getByRole("button", {
      name: /reset temperature to global/i,
    });

    await user.click(resetBtn);

    await waitFor(() => {
      expect(setOverrideFieldMock).toHaveBeenCalledTimes(1);
      expect(setOverrideFieldMock).toHaveBeenCalledWith(
        TEST_SLUG,
        "temperature",
        null,
      );
    });
    expect(configSetMock).not.toHaveBeenCalled();
  });
});

describe("DomainOverrideForm — toast feedback", () => {
  test("shows a success toast after a successful LLM field save", async () => {
    const user = userEvent.setup();
    setOverrideFieldMock.mockResolvedValue(undefined);

    renderForm({ classify_model: null });

    const input = screen.getByRole("textbox", {
      name: /classify model/i,
    });
    await user.click(input);
    await user.type(input, "test-model");
    await user.tab();

    await waitFor(() => {
      const toasts = useSystemStore.getState().toasts;
      expect(toasts.length).toBeGreaterThanOrEqual(1);
      const latest = toasts[toasts.length - 1]!;
      expect(latest.variant).toBe("success");
      expect(latest.lead).toMatch(/override saved/i);
    });
  });

  test("shows a success toast with 'Reset to global' lead when value is null", async () => {
    const user = userEvent.setup();
    setOverrideFieldMock.mockResolvedValue(undefined);

    renderForm({ classify_model: "some-model" });

    const resetBtn = screen.getByRole("button", {
      name: /reset classify model to global/i,
    });
    await user.click(resetBtn);

    await waitFor(() => {
      const toasts = useSystemStore.getState().toasts;
      expect(toasts.length).toBeGreaterThanOrEqual(1);
      const latest = toasts[toasts.length - 1]!;
      expect(latest.variant).toBe("success");
      expect(latest.lead).toMatch(/reset to global/i);
    });
  });

  test("shows a danger toast when setOverrideField throws", async () => {
    const user = userEvent.setup();
    setOverrideFieldMock.mockRejectedValueOnce(new Error("network timeout"));

    renderForm({ classify_model: null });

    const input = screen.getByRole("textbox", {
      name: /classify model/i,
    });
    await user.click(input);
    await user.type(input, "bad-model");
    await user.tab();

    await waitFor(() => {
      const toasts = useSystemStore.getState().toasts;
      expect(toasts.length).toBeGreaterThanOrEqual(1);
      const latest = toasts[toasts.length - 1]!;
      expect(latest.variant).toBe("danger");
      expect(latest.lead).toMatch(/couldn't save override/i);
      expect(latest.msg).toContain("network timeout");
    });
  });

  test("shows a danger toast when configSet throws for autonomous_mode", async () => {
    const user = userEvent.setup();
    configSetMock.mockRejectedValueOnce(new Error("configSet boom"));

    renderForm({ autonomous_mode: false });

    const sw = screen.getByRole("switch", {
      name: /autonomous mode/i,
    });
    await user.click(sw);

    await waitFor(() => {
      const toasts = useSystemStore.getState().toasts;
      expect(toasts.length).toBeGreaterThanOrEqual(1);
      const latest = toasts[toasts.length - 1]!;
      expect(latest.variant).toBe("danger");
      expect(latest.lead).toMatch(/couldn't save override/i);
      expect(latest.msg).toContain("configSet boom");
    });
  });
});

describe("DomainOverrideForm — onChanged callback", () => {
  test("onChanged is called after a successful LLM field save", async () => {
    const user = userEvent.setup();
    const onChanged = vi.fn();
    setOverrideFieldMock.mockResolvedValue(undefined);

    renderForm({ classify_model: null }, onChanged);

    const input = screen.getByRole("textbox", {
      name: /classify model/i,
    });
    await user.click(input);
    await user.type(input, "some-model");
    await user.tab();

    await waitFor(() => {
      expect(onChanged).toHaveBeenCalledTimes(1);
    });
  });

  test("onChanged is NOT called when setOverrideField throws", async () => {
    const user = userEvent.setup();
    const onChanged = vi.fn();
    setOverrideFieldMock.mockRejectedValueOnce(new Error("oops"));

    renderForm({ classify_model: null }, onChanged);

    const input = screen.getByRole("textbox", {
      name: /classify model/i,
    });
    await user.click(input);
    await user.type(input, "bad-model");
    await user.tab();

    // Wait for the error toast so the async path resolves.
    await waitFor(() => {
      const toasts = useSystemStore.getState().toasts;
      expect(toasts.length).toBeGreaterThanOrEqual(1);
    });

    expect(onChanged).not.toHaveBeenCalled();
  });
});
