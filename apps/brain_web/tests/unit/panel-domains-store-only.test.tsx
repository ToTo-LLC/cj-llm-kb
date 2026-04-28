/**
 * Plan 13 Task 2 (D2) — PanelDomains store-only read.
 *
 * Pins the contract that ``panel-domains.tsx`` no longer maintains a
 * parallel local ``domains: string[]`` state hydrated from a separate
 * ``listDomains()`` call. The component reads the domain list directly
 * off ``useDomainsStore`` (via the Plan 12 Task 5 ``useDomains()``
 * selector); peer-consumer mutations (other tabs, the topbar, the
 * active-domain dropdown) propagate through the zustand subscription
 * model without remount.
 *
 * Plan 12 Task 5 + Task 8 reviews flagged the parallel state as
 * drift-prone — both read paths landed at the same backend so they
 * stayed coincidentally aligned, but a future code path that diverged
 * either fetch (caching, server-side filtering, etc.) would surface
 * silent inconsistency. Plan 13 closes that seam.
 *
 * This test does NOT cover full PanelDomains behaviour (delete,
 * rename, privacy-rail toggle, active-domain dropdown) — those have
 * their own dedicated specs. The pin assertion here is narrow:
 *
 *   1. Rendered ``[data-testid="domain-row"]`` count equals
 *      ``useDomainsStore.getState().domains.length`` — ie. the row
 *      list IS the store list, not a snapshot of it.
 *   2. Mutating the store mid-test re-renders the panel with the new
 *      list within the same React tick (cross-instance pubsub).
 *   3. The component does not call ``listDomains`` itself — every
 *      list fetch routes through the store's ``refresh()`` action.
 */

import { describe, expect, test, beforeEach, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
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
  // ``createDomain`` referenced via ``DomainForm`` — stub.
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
  // Defaults: privacy_railed=["personal"], not acknowledged, no
  // overrides. Returning structured payloads keeps the panel from
  // toasting "load failed" mid-test.
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

  // The store's auto-refresh effect calls ``listDomains``; provide a
  // canonical response so the store hydrates deterministically.
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

  // Reset the singleton store between tests so the previous case's
  // state doesn't leak in.
  useDomainsStore.getState()._resetForTesting();
});

describe("PanelDomains — Plan 13 Task 2 (D2): store-only domain list", () => {
  test("rendered domain-row count equals store.domains.length (no parallel local state)", async () => {
    render(<PanelDomains />);

    // Wait for the store hydration + initial paint.
    await waitFor(() => {
      expect(screen.queryAllByTestId("domain-row").length).toBeGreaterThan(0);
    });

    const rendered = screen.queryAllByTestId("domain-row");
    const storeDomains = useDomainsStore.getState().domains;
    // The pin assertion the plan calls out by name: rendered row count
    // tracks ``useDomainsStore.getState().domains.length`` exactly.
    // If a parallel local ``domains: string[]`` state were
    // re-introduced, it could drift away from the store's count and
    // this assertion would fail.
    expect(rendered.length).toBe(storeDomains.length);
    expect(rendered.length).toBe(3);
  });

  test("mutating the store mid-test re-renders the panel with the new list", async () => {
    render(<PanelDomains />);

    // Initial: 3 rows after store hydration.
    await waitFor(() => {
      expect(screen.queryAllByTestId("domain-row").length).toBe(3);
    });

    // Simulate a peer consumer (another tab, the topbar, etc.)
    // mutating the store directly. This is the exact cross-instance
    // pubsub scenario Plan 12 Task 5 fixed for ``useDomains()`` — and
    // Plan 13 Task 2 extends to ``PanelDomains`` by routing its read
    // path through the same selector.
    act(() => {
      useDomainsStore.setState({
        domains: [
          {
            slug: "research",
            label: "Research",
            accent: "var(--dom-research)",
            configured: true,
            on_disk: true,
          },
          {
            slug: "personal",
            label: "Personal",
            accent: "var(--dom-personal)",
            configured: true,
            on_disk: true,
          },
          // "work" deleted; "consulting" added by the peer.
          {
            slug: "consulting",
            label: "Consulting",
            accent: "#bb88ff",
            configured: true,
            on_disk: true,
          },
        ],
      });
    });

    // The panel re-renders WITHOUT remount or page reload — the row
    // count tracks the store, and the new slug is in the DOM.
    const rendered = screen.queryAllByTestId("domain-row");
    expect(rendered.length).toBe(3);
    expect(screen.getByText("consulting", { ignore: "option" })).toBeInTheDocument();
    expect(
      screen.queryByText("work", { ignore: "option" }),
    ).not.toBeInTheDocument();
    // Pin: post-mutation, the rendered count still matches the store.
    expect(rendered.length).toBe(useDomainsStore.getState().domains.length);
  });

  test("setting the store to an empty list clears all rows", async () => {
    render(<PanelDomains />);

    await waitFor(() => {
      expect(screen.queryAllByTestId("domain-row").length).toBe(3);
    });

    act(() => {
      useDomainsStore.setState({ domains: [] });
    });

    expect(screen.queryAllByTestId("domain-row").length).toBe(0);
    expect(useDomainsStore.getState().domains.length).toBe(0);
  });

  test("PanelDomains does not import ``listDomains`` directly — every fetch routes through the store", async () => {
    // The store's ``refresh()`` action calls ``listDomains``; the
    // panel itself does not. This pin assertion guards against
    // accidentally re-introducing a direct ``listDomains()`` call in
    // ``panel-domains.tsx`` (which would re-create the parallel
    // fetch path Plan 13 Task 2 dropped).
    //
    // We can't introspect imports at runtime, but we CAN assert the
    // call counts: a single render should produce exactly ONE
    // ``listDomains`` call (the store's auto-refresh on cold cache).
    // A panel-side ``listDomains()`` call would push the count to 2.
    render(<PanelDomains />);

    await waitFor(() => {
      expect(useDomainsStore.getState().domainsLoaded).toBe(true);
    });

    // The panel's mount-effect refresh and the store's first-mount
    // auto-refresh share the same in-flight Promise (Plan 12 Task 5
    // contract — concurrent ``refresh()`` calls de-dupe), so the
    // network is hit exactly once.
    expect(listDomainsMock).toHaveBeenCalledTimes(1);
  });
});
