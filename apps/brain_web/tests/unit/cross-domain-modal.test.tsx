import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * Plan 12 Task 9 — CrossDomainModal + trigger gate + Settings toggle.
 *
 * The 6 spec bullets are covered across three describe-blocks:
 *
 *   1. Trigger logic table (parametrized — `shouldFireCrossDomainModal`).
 *   2. Modal interaction surface (Continue with/without ack, Cancel).
 *   3. Trigger-gate-respects-acknowledged short-circuit.
 *   4. Settings toggle inverse mapping (UI ON ⇄ acknowledged=false).
 *
 * All API helpers are mocked; the modal + helpers are pure render +
 * pure functions, so we exercise them directly without standing up the
 * full ChatScreen. The toggle test mirrors the existing
 * ``settings-active-domain.test.tsx`` mock-store pattern.
 */

// ---------- Trigger gate (pure function) ----------

import {
  CrossDomainModal,
  computeRailedSlugsInScope,
  joinSlugs,
  shouldFireCrossDomainModal,
} from "@/components/dialogs/cross-domain-modal";

describe("shouldFireCrossDomainModal — Plan 12 D7 trigger logic table", () => {
  const railed = ["personal", "journal"];

  test.each([
    // [scope, ack, expected, label]
    [["research", "personal"], false, true, "cross-domain into railed"],
    [["research", "work"], false, false, "cross-domain without railed"],
    [["personal"], false, false, "single-domain railed (consent implicit)"],
    [["research"], false, false, "single-domain non-railed"],
    [[], false, false, "empty scope"],
    [["personal", "journal"], false, true, "two railed slugs"],
    [
      ["research", "work", "personal"],
      false,
      true,
      "≥3 domains with one railed",
    ],
  ])(
    "scope=%j ack=%j → fires=%j (%s)",
    (scope, ack, expected) => {
      expect(
        shouldFireCrossDomainModal(
          scope as readonly string[],
          railed,
          ack as boolean,
        ),
      ).toBe(expected);
    },
  );

  test("acknowledged=true short-circuits even when trigger condition would otherwise match", () => {
    expect(
      shouldFireCrossDomainModal(["research", "personal"], railed, true),
    ).toBe(false);
  });

  test("computeRailedSlugsInScope returns scope ∩ privacyRailed in scope order", () => {
    expect(computeRailedSlugsInScope(["research", "personal"], railed)).toEqual([
      "personal",
    ]);
    expect(
      computeRailedSlugsInScope(["personal", "research", "journal"], railed),
    ).toEqual(["personal", "journal"]);
    expect(computeRailedSlugsInScope(["research", "work"], railed)).toEqual([]);
  });
});

describe("joinSlugs — Plan 12 Task 7 microcopy join rule", () => {
  test("0 slugs renders empty", () => {
    expect(joinSlugs([])).toBe("");
  });
  test("1 slug renders bare", () => {
    expect(joinSlugs(["personal"])).toBe("personal");
  });
  test("2 slugs join with ' and '", () => {
    expect(joinSlugs(["personal", "journal"])).toBe("personal and journal");
  });
  test("≥3 slugs join with comma + ' and ' (no Oxford comma)", () => {
    expect(joinSlugs(["personal", "journal", "finance"])).toBe(
      "personal, journal and finance",
    );
  });
});

// ---------- Modal interaction surface ----------

describe("CrossDomainModal — interaction surface", () => {
  beforeEach(() => {
    // Each test gets a fresh DOM mount.
  });

  test("renders title, eyebrow, body with railed + other slugs in bold", async () => {
    render(
      <CrossDomainModal
        open
        scope={["research", "personal"]}
        railedSlugsInScope={["personal"]}
        onContinue={() => {}}
        onCancel={() => {}}
      />,
    );

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveAccessibleName("Including a private domain in this chat");
    expect(screen.getByText("Confirm scope")).toBeInTheDocument();
    // Body prose includes "alongside" + the explanatory sentence.
    expect(
      screen.getByText(/for this chat's scope/i, { exact: false }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/kept private by default/i, { exact: false }),
    ).toBeInTheDocument();
    // BRAIN.md callout in the second paragraph.
    expect(screen.getByText("BRAIN.md")).toBeInTheDocument();
  });

  test("singular grammar: 1 railed slug uses 'is' / 'it'", async () => {
    render(
      <CrossDomainModal
        open
        scope={["research", "personal"]}
        railedSlugsInScope={["personal"]}
        onContinue={() => {}}
        onCancel={() => {}}
      />,
    );
    // Radix portals DialogContent — query via the dialog role so we
    // pick up the portal-rendered content rather than the (empty)
    // test container.
    const dialog = await screen.findByRole("dialog");
    const text = dialog.textContent ?? "";
    expect(text).toMatch(/personal\s+is kept private/i);
    expect(text).toMatch(/explicitly include it/i);
  });

  test("plural grammar: 2 railed slugs uses 'are' / 'them'", async () => {
    render(
      <CrossDomainModal
        open
        scope={["research", "work", "personal", "journal"]}
        railedSlugsInScope={["personal", "journal"]}
        onContinue={() => {}}
        onCancel={() => {}}
      />,
    );
    const dialog = await screen.findByRole("dialog");
    const text = dialog.textContent ?? "";
    expect(text).toMatch(/personal and journal\s+are kept private/i);
    expect(text).toMatch(/explicitly include them/i);
  });

  test("≥3 railed slugs render with 'A, B and C' join", async () => {
    render(
      <CrossDomainModal
        open
        scope={["personal", "journal", "finance", "research"]}
        railedSlugsInScope={["personal", "journal", "finance"]}
        onContinue={() => {}}
        onCancel={() => {}}
      />,
    );
    const dialog = await screen.findByRole("dialog");
    const text = dialog.textContent ?? "";
    expect(text).toMatch(/personal, journal and finance/);
  });

  test("onContinue(false) fires with alsoAcknowledge=false when checkbox unchecked", async () => {
    const onContinue = vi.fn();
    const user = userEvent.setup();
    render(
      <CrossDomainModal
        open
        scope={["research", "personal"]}
        railedSlugsInScope={["personal"]}
        onContinue={onContinue}
        onCancel={() => {}}
      />,
    );
    const continueBtn = await screen.findByTestId(
      "cross-domain-continue-button",
    );
    await user.click(continueBtn);
    expect(onContinue).toHaveBeenCalledWith(false);
  });

  test("onContinue(true) fires with alsoAcknowledge=true when checkbox checked", async () => {
    const onContinue = vi.fn();
    const user = userEvent.setup();
    render(
      <CrossDomainModal
        open
        scope={["research", "personal"]}
        railedSlugsInScope={["personal"]}
        onContinue={onContinue}
        onCancel={() => {}}
      />,
    );

    const checkbox = await screen.findByTestId(
      "cross-domain-dont-show-checkbox",
    );
    await user.click(checkbox);

    const continueBtn = screen.getByTestId("cross-domain-continue-button");
    await user.click(continueBtn);
    expect(onContinue).toHaveBeenCalledWith(true);
  });

  test("onCancel fires when 'Back to scope' clicked; onContinue NOT called", async () => {
    const onCancel = vi.fn();
    const onContinue = vi.fn();
    const user = userEvent.setup();
    render(
      <CrossDomainModal
        open
        scope={["research", "personal"]}
        railedSlugsInScope={["personal"]}
        onContinue={onContinue}
        onCancel={onCancel}
      />,
    );

    const backBtn = await screen.findByTestId("cross-domain-back-button");
    await user.click(backBtn);
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onContinue).not.toHaveBeenCalled();
  });

  test("Esc dispatches onCancel (Modal/Radix built-in)", async () => {
    const onCancel = vi.fn();
    const user = userEvent.setup();
    render(
      <CrossDomainModal
        open
        scope={["research", "personal"]}
        railedSlugsInScope={["personal"]}
        onContinue={() => {}}
        onCancel={onCancel}
      />,
    );
    await screen.findByRole("dialog");
    await user.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalled();
  });

  test("checkbox state resets when modal re-opens", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <CrossDomainModal
        open
        scope={["research", "personal"]}
        railedSlugsInScope={["personal"]}
        onContinue={() => {}}
        onCancel={() => {}}
      />,
    );

    let checkbox = await screen.findByTestId("cross-domain-dont-show-checkbox");
    await user.click(checkbox);
    expect(checkbox).toHaveAttribute("data-state", "checked");

    // Close and re-open.
    rerender(
      <CrossDomainModal
        open={false}
        scope={["research", "personal"]}
        railedSlugsInScope={["personal"]}
        onContinue={() => {}}
        onCancel={() => {}}
      />,
    );
    rerender(
      <CrossDomainModal
        open
        scope={["research", "personal"]}
        railedSlugsInScope={["personal"]}
        onContinue={() => {}}
        onCancel={() => {}}
      />,
    );

    checkbox = await screen.findByTestId("cross-domain-dont-show-checkbox");
    expect(checkbox).toHaveAttribute("data-state", "unchecked");
  });
});

// ---------- Settings toggle (PanelDomains "Show cross-domain warning") ----------

const {
  listDomainsMock,
  setActiveDomainMock,
  configGetMock,
  setPrivacyRailedMock,
  setCrossDomainWarningAcknowledgedMock,
  brainDeleteDomainMock,
} = vi.hoisted(() => ({
  listDomainsMock: vi.fn(),
  setActiveDomainMock: vi.fn(),
  configGetMock: vi.fn(),
  setPrivacyRailedMock: vi.fn(),
  setCrossDomainWarningAcknowledgedMock: vi.fn(),
  brainDeleteDomainMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  listDomains: listDomainsMock,
  setActiveDomain: setActiveDomainMock,
  configGet: configGetMock,
  setPrivacyRailed: setPrivacyRailedMock,
  setCrossDomainWarningAcknowledged: setCrossDomainWarningAcknowledgedMock,
  brainDeleteDomain: brainDeleteDomainMock,
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
    (selector: (s: { pushToast: typeof pushToastStub }) => unknown) =>
      selector({ pushToast: pushToastStub }),
    { getState: () => ({ pushToast: pushToastStub }) },
  ),
}));

import { PanelDomains } from "@/components/settings/panel-domains";
import { _setDomainsCacheForTesting } from "@/lib/hooks/use-domains";

describe("PanelDomains → CrossDomainWarningToggle (Plan 12 D8 / Task 9)", () => {
  beforeEach(() => {
    listDomainsMock.mockReset();
    setActiveDomainMock.mockReset();
    configGetMock.mockReset();
    setPrivacyRailedMock.mockReset();
    setCrossDomainWarningAcknowledgedMock.mockReset();
    brainDeleteDomainMock.mockReset();
    openDialogMock.mockReset();
    pushToastStub.mockReset();

    _setDomainsCacheForTesting(
      [
        { slug: "research", label: "Research", accent: "var(--dom-research)", configured: true, on_disk: true },
        { slug: "work", label: "Work", accent: "var(--dom-work)", configured: true, on_disk: true },
        { slug: "personal", label: "Personal", accent: "var(--dom-personal)", configured: true, on_disk: true },
      ],
      "research",
    );

    listDomainsMock.mockResolvedValue({
      text: "",
      data: {
        domains: ["research", "work", "personal"],
        active_domain: "research",
      },
    });

    // Default: privacy_railed=["personal"], domain_overrides={},
    // cross_domain_warning_acknowledged=false (toggle ON).
    configGetMock.mockImplementation((args: { key: string }) => {
      if (args.key === "privacy_railed") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: ["personal"] },
        });
      }
      if (args.key === "domain_overrides") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: {} },
        });
      }
      if (args.key === "cross_domain_warning_acknowledged") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: false },
        });
      }
      return Promise.resolve({ text: "", data: { key: args.key, value: null } });
    });

    setActiveDomainMock.mockResolvedValue({
      text: "",
      data: { key: "active_domain", value: "research" },
    });

    setCrossDomainWarningAcknowledgedMock.mockImplementation(
      (value: boolean) =>
        Promise.resolve({
          text: "",
          data: { key: "cross_domain_warning_acknowledged", value },
        }),
    );
  });

  test("renders toggle ON when acknowledged=false (modal will fire)", async () => {
    render(<PanelDomains />);
    const toggle = await screen.findByTestId("cross-domain-warning-toggle");
    await waitFor(() => {
      expect(toggle).toHaveAttribute("data-state", "checked");
    });
    // Helper text matches the ON variant.
    expect(
      screen.getByText(/brain will ask you to confirm/i),
    ).toBeInTheDocument();
  });

  test("renders toggle OFF when acknowledged=true (modal suppressed)", async () => {
    configGetMock.mockImplementation((args: { key: string }) => {
      if (args.key === "cross_domain_warning_acknowledged") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: true },
        });
      }
      if (args.key === "privacy_railed") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: ["personal"] },
        });
      }
      if (args.key === "domain_overrides") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: {} },
        });
      }
      return Promise.resolve({ text: "", data: { key: args.key, value: null } });
    });

    render(<PanelDomains />);
    const toggle = await screen.findByTestId("cross-domain-warning-toggle");
    await waitFor(() => {
      expect(toggle).toHaveAttribute("data-state", "unchecked");
    });
    expect(
      screen.getByText(/confirmation is off/i),
    ).toBeInTheDocument();
  });

  test("toggling OFF (UI) calls setCrossDomainWarningAcknowledged(true)", async () => {
    const user = userEvent.setup();
    render(<PanelDomains />);

    const toggle = await screen.findByTestId("cross-domain-warning-toggle");
    await waitFor(() => {
      expect(toggle).toHaveAttribute("data-state", "checked");
    });

    await user.click(toggle);

    await waitFor(() => {
      expect(setCrossDomainWarningAcknowledgedMock).toHaveBeenCalledWith(true);
    });
  });

  test("toggling ON (UI) calls setCrossDomainWarningAcknowledged(false)", async () => {
    // Seed acknowledged=true so the toggle starts OFF.
    configGetMock.mockImplementation((args: { key: string }) => {
      if (args.key === "cross_domain_warning_acknowledged") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: true },
        });
      }
      if (args.key === "privacy_railed") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: ["personal"] },
        });
      }
      if (args.key === "domain_overrides") {
        return Promise.resolve({
          text: "",
          data: { key: args.key, value: {} },
        });
      }
      return Promise.resolve({ text: "", data: { key: args.key, value: null } });
    });

    const user = userEvent.setup();
    render(<PanelDomains />);

    const toggle = await screen.findByTestId("cross-domain-warning-toggle");
    await waitFor(() => {
      expect(toggle).toHaveAttribute("data-state", "unchecked");
    });

    await user.click(toggle);

    await waitFor(() => {
      expect(setCrossDomainWarningAcknowledgedMock).toHaveBeenCalledWith(false);
    });
  });

  test("API failure reverts the toggle and surfaces a danger toast", async () => {
    setCrossDomainWarningAcknowledgedMock.mockRejectedValueOnce(
      new Error("disk write failed"),
    );

    const user = userEvent.setup();
    render(<PanelDomains />);

    const toggle = await screen.findByTestId("cross-domain-warning-toggle");
    await waitFor(() => {
      expect(toggle).toHaveAttribute("data-state", "checked");
    });

    await user.click(toggle);

    // After the failed API resolves, the toggle reverts to its
    // previous state (still checked = ON = warning active).
    await waitFor(() => {
      expect(toggle).toHaveAttribute("data-state", "checked");
    });

    const dangerToast = pushToastStub.mock.calls.find(
      (c) => (c[0] as { variant?: string }).variant === "danger",
    );
    expect(dangerToast).toBeDefined();
    const payload = dangerToast![0] as { lead: string; msg: string };
    expect(payload.lead).toMatch(/couldn't update cross-domain warning/i);
    expect(payload.msg).toMatch(/disk write failed/);
  });
});
