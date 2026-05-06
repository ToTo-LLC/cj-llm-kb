/**
 * Plan 16 Task 5 (D5) — cross-domain-gate-store error banner in panel-domains.
 *
 * Pins the contract that ``panel-domains.tsx`` renders an inline error
 * banner above the privacy-rail toggle list whenever
 * ``useCrossDomainGateStore.error`` is non-null. The store fails open
 * (defaults to ``privacyRailed=["personal"]`` + ``acknowledged=false``)
 * on a backend hiccup so the modal-skip path is safe — but without a
 * surfaced banner the user never knows the privacy-rail state failed
 * to load and is being read off fallback defaults.
 *
 * Mirrors the Task 4 (D4) ``useDomainsStore.error`` banner — same
 * shape, same tokens, same ``role="alert"`` for screen-reader
 * announcement, distinct ``data-testid`` so e2e tests can target it.
 */

import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

const {
  listDomainsMock,
  configGetMock,
  setActiveDomainMock,
  setPrivacyRailedMock,
  brainDeleteDomainMock,
  setCrossDomainWarningAcknowledgedMock,
} = vi.hoisted(() => ({
  listDomainsMock: vi.fn(),
  configGetMock: vi.fn(),
  setActiveDomainMock: vi.fn(),
  setPrivacyRailedMock: vi.fn(),
  brainDeleteDomainMock: vi.fn(),
  setCrossDomainWarningAcknowledgedMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  listDomains: listDomainsMock,
  configGet: configGetMock,
  setActiveDomain: setActiveDomainMock,
  setPrivacyRailed: setPrivacyRailedMock,
  brainDeleteDomain: brainDeleteDomainMock,
  setCrossDomainWarningAcknowledged: setCrossDomainWarningAcknowledgedMock,
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
import { useDomainsStore } from "@/lib/state/domains-store";
import { useCrossDomainGateStore } from "@/lib/state/cross-domain-gate-store";

beforeEach(() => {
  listDomainsMock.mockReset();
  configGetMock.mockReset();
  setActiveDomainMock.mockReset();
  setPrivacyRailedMock.mockReset();
  brainDeleteDomainMock.mockReset();
  setCrossDomainWarningAcknowledgedMock.mockReset();
  openDialogMock.mockReset();
  pushToastStub.mockReset();

  // ``configGet`` is consulted for ``privacy_railed``,
  // ``cross_domain_warning_acknowledged``, and ``domain_overrides``.
  configGetMock.mockImplementation((args: { key: string }) => {
    if (args.key === "privacy_railed") {
      return Promise.resolve({
        text: "",
        data: { key: args.key, value: ["personal"] },
      });
    }
    if (args.key === "cross_domain_warning_acknowledged") {
      return Promise.resolve({
        text: "",
        data: { key: args.key, value: false },
      });
    }
    if (args.key === "domain_overrides") {
      return Promise.resolve({ text: "", data: { key: args.key, value: {} } });
    }
    return Promise.resolve({ text: "", data: { key: args.key, value: null } });
  });

  listDomainsMock.mockResolvedValue({
    text: "",
    data: {
      domains: ["research", "work", "personal"],
      entries: [
        { slug: "research", configured: true, on_disk: true },
        { slug: "work", configured: true, on_disk: true },
        { slug: "personal", configured: true, on_disk: true },
      ],
      active_domain: "research",
    },
  });

  // Reset both singleton stores between tests so prior case state
  // doesn't leak into the next render.
  useDomainsStore.getState()._resetForTesting();
  useCrossDomainGateStore.getState()._resetForTesting();
});

describe("PanelDomains — Plan 16 Task 5 (D5): cross-domain-gate-store error banner", () => {
  test("does NOT render the banner when gate store error is null", async () => {
    render(<PanelDomains />);

    await waitFor(() => {
      expect(screen.queryAllByTestId("domain-row").length).toBe(3);
    });

    // Happy path — gate store hydrated cleanly, no error banner.
    expect(
      screen.queryByTestId("cross-domain-gate-error-banner"),
    ).not.toBeInTheDocument();
  });

  test("renders the banner with role='alert' when gate store error is set", async () => {
    render(<PanelDomains />);

    await waitFor(() => {
      expect(screen.queryAllByTestId("domain-row").length).toBe(3);
    });

    // Simulate a peer ``refresh()`` failure landing on the gate store.
    // The store's resolve-always semantics record the error in state
    // so subscribed consumers (this panel) re-render with the banner.
    act(() => {
      useCrossDomainGateStore.setState({
        error: new Error("backend exploded"),
      });
    });

    const banner = screen.getByTestId("cross-domain-gate-error-banner");
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveAttribute("role", "alert");
    expect(banner.textContent).toContain("Couldn");
    expect(banner.textContent).toContain("load privacy-rail state");
    expect(banner.textContent).toContain("backend exploded");
  });

  test("the gate-error banner is independent of the domains-store error banner", async () => {
    render(<PanelDomains />);

    await waitFor(() => {
      expect(screen.queryAllByTestId("domain-row").length).toBe(3);
    });

    // Only the gate store has an error — domains store is fine. The
    // domains-store banner must not appear.
    act(() => {
      useCrossDomainGateStore.setState({
        error: new Error("gate-only failure"),
      });
    });

    expect(
      screen.getByTestId("cross-domain-gate-error-banner"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("domains-error-banner"),
    ).not.toBeInTheDocument();
  });
});
