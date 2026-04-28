import { describe, expect, test, beforeEach, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

/**
 * Plan 12 Task 8 — ActiveDomainSelector inside PanelDomains.
 *
 * Spec bullets pinned by the plan:
 *
 *   1. Renders the dropdown with current ``activeDomain`` selected;
 *      options match the ``domains`` list from the zustand store.
 *   2. Selecting a different domain calls ``setActiveDomain(slug)``
 *      with the new value.
 *   3. After the API helper resolves, the dropdown selection reflects
 *      the new value (driven by the store update from
 *      ``setActiveDomainOptimistic``).
 *   4. API failure: dropdown reverts to the original ``activeDomain``;
 *      a danger-variant toast appears with the error message.
 *   5. Domain-list mutation (peer consumer adds/removes a slug) — the
 *      dropdown's options update without re-mount. This is the key
 *      Plan 12 Task 5 zustand-cross-instance assertion in this
 *      consumer's context: prove the dropdown re-renders when the
 *      shared store mutates.
 *
 * Implementation notes:
 *   - We mock ``@/lib/api/tools`` so ``listDomains`` and
 *     ``setActiveDomain`` are vi.fn()s — keeps tests deterministic
 *     and avoids the network entirely.
 *   - ``useSystemStore.pushToast`` is stubbed via Object.assign so
 *     we can assert on toast payloads. Same pattern as
 *     ``settings-domains.test.tsx``.
 *   - We also stub ``useDialogsStore.open`` because PanelDomains
 *     renders dialog-triggering buttons (rename/delete) that import
 *     it — keeping them no-ops avoids cross-test interference.
 *   - We use ``_setDomainsCacheForTesting`` to seed the store with a
 *     known starting point. Tests that need to mutate the list at
 *     runtime call ``useDomainsStore.setState`` directly.
 */

const {
  listDomainsMock,
  setActiveDomainMock,
  configGetMock,
  setPrivacyRailedMock,
  brainDeleteDomainMock,
} = vi.hoisted(() => ({
  listDomainsMock: vi.fn(),
  setActiveDomainMock: vi.fn(),
  configGetMock: vi.fn(),
  setPrivacyRailedMock: vi.fn(),
  brainDeleteDomainMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  listDomains: listDomainsMock,
  setActiveDomain: setActiveDomainMock,
  configGet: configGetMock,
  setPrivacyRailed: setPrivacyRailedMock,
  brainDeleteDomain: brainDeleteDomainMock,
  // ``createDomain`` referenced indirectly via DomainForm — stub.
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
import { _setDomainsCacheForTesting } from "@/lib/hooks/use-domains";

beforeEach(() => {
  listDomainsMock.mockReset();
  setActiveDomainMock.mockReset();
  configGetMock.mockReset();
  setPrivacyRailedMock.mockReset();
  brainDeleteDomainMock.mockReset();
  openDialogMock.mockReset();
  pushToastStub.mockReset();

  // Seed the zustand store with a known starting point — the
  // dropdown reads ``domains`` + ``activeDomain`` directly off the
  // store. ``_setDomainsCacheForTesting`` flips ``domainsLoaded=true``
  // so the hook's first-mount auto-refresh is suppressed.
  _setDomainsCacheForTesting(
    [
      { slug: "research", label: "Research", accent: "var(--dom-research)", configured: true, on_disk: true },
      { slug: "work", label: "Work", accent: "var(--dom-work)", configured: true, on_disk: true },
      { slug: "personal", label: "Personal", accent: "var(--dom-personal)", configured: true, on_disk: true },
    ],
    "research",
  );

  // ``listDomains`` is called by PanelDomains's local ``refresh()``
  // on mount (Plan 11 D14 per-row state) AND ALSO by the store via
  // ``invalidateDomainsCache → useDomainsStore.refresh`` (Plan 12
  // Task 5 alias). Including ``active_domain`` keeps the post-fetch
  // store state aligned with the test's seeded ``activeDomain`` so
  // the dropdown's controlled value doesn't snap back to "" when the
  // panel's mount-effect refresh lands.
  listDomainsMock.mockResolvedValue({
    text: "",
    data: {
      domains: ["research", "work", "personal"],
      active_domain: "research",
    },
  });

  // ``configGet`` is called for ``privacy_railed`` and
  // ``domain_overrides`` by the existing PanelDomains plumbing.
  // Defaults: privacy_railed=["personal"], no overrides.
  configGetMock.mockImplementation((args: { key: string }) => {
    if (args.key === "privacy_railed") {
      return Promise.resolve({
        text: "",
        data: { key: args.key, value: ["personal"] },
      });
    }
    if (args.key === "domain_overrides") {
      return Promise.resolve({ text: "", data: { key: args.key, value: {} } });
    }
    return Promise.resolve({ text: "", data: { key: args.key, value: null } });
  });

  setActiveDomainMock.mockResolvedValue({
    text: "",
    data: { key: "active_domain", value: "work" },
  });
});

describe("ActiveDomainSelector — Plan 12 Task 8", () => {
  test("renders the dropdown with current activeDomain selected; options match the store's domains list", async () => {
    render(<PanelDomains />);

    const select = (await screen.findByTestId(
      "active-domain-selector",
    )) as HTMLSelectElement;

    // Current ``activeDomain`` is pre-selected.
    expect(select.value).toBe("research");

    // Every store-domain shows up as an <option>.
    const optionValues = Array.from(select.querySelectorAll("option"))
      .map((o) => o.value)
      .filter((v) => v !== ""); // ignore the placeholder if present
    expect(optionValues).toEqual(["research", "work", "personal"]);

    // Label is associated with the select (a11y).
    const label = screen.getByText("Active domain");
    expect(label.tagName.toLowerCase()).toBe("label");
    expect(label.getAttribute("for")).toBe("active-domain-selector");
  });

  test("selecting a different domain calls setActiveDomain(slug) with the new value", async () => {
    const user = userEvent.setup();
    render(<PanelDomains />);

    const select = (await screen.findByTestId(
      "active-domain-selector",
    )) as HTMLSelectElement;

    await user.selectOptions(select, "work");

    await waitFor(() => {
      expect(setActiveDomainMock).toHaveBeenCalledWith("work");
    });
  });

  test("after the API helper resolves, the dropdown selection reflects the new value (driven by the store)", async () => {
    const user = userEvent.setup();
    render(<PanelDomains />);

    const select = (await screen.findByTestId(
      "active-domain-selector",
    )) as HTMLSelectElement;
    expect(select.value).toBe("research");

    await user.selectOptions(select, "work");

    // The optimistic-update path calls setActiveDomainOptimistic
    // BEFORE awaiting the API; the store update is therefore
    // synchronous-ish from the dropdown's perspective. After the
    // API resolves, the value is still "work".
    await waitFor(() => {
      expect(setActiveDomainMock).toHaveBeenCalled();
    });
    expect(select.value).toBe("work");
    expect(useDomainsStore.getState().activeDomain).toBe("work");
  });

  test("API failure: dropdown reverts to the original activeDomain and a danger-variant toast appears", async () => {
    const user = userEvent.setup();
    setActiveDomainMock.mockRejectedValueOnce(
      new Error("active_domain 'work' not in Config.domains [..]"),
    );

    render(<PanelDomains />);
    const select = (await screen.findByTestId(
      "active-domain-selector",
    )) as HTMLSelectElement;
    expect(select.value).toBe("research");

    await user.selectOptions(select, "work");

    // After the failed API resolves, the optimistic update is
    // reverted and the store + DOM both go back to "research".
    await waitFor(() => {
      expect(useDomainsStore.getState().activeDomain).toBe("research");
    });
    expect(select.value).toBe("research");

    // A danger-variant toast was pushed with the structured error
    // message + a "Pick a different domain" CTA.
    const dangerToast = pushToastStub.mock.calls.find(
      (c) => (c[0] as { variant?: string }).variant === "danger",
    );
    expect(dangerToast).toBeDefined();
    const payload = dangerToast![0] as { lead: string; msg: string };
    expect(payload.lead).toMatch(/couldn't update active domain/i);
    expect(payload.msg).toMatch(/Pick a different domain/i);
    expect(payload.msg).toMatch(/not in Config\.domains/);
  });

  test("domain-list mutation: dropdown options update without re-mount (Task 5 zustand cross-instance assertion)", async () => {
    render(<PanelDomains />);

    const select = (await screen.findByTestId(
      "active-domain-selector",
    )) as HTMLSelectElement;

    // Initial: 3 domains.
    let opts = Array.from(select.querySelectorAll("option"))
      .map((o) => o.value)
      .filter((v) => v !== "");
    expect(opts).toEqual(["research", "work", "personal"]);

    // Simulate a peer consumer (e.g., another tab's PanelDomains
    // delete flow, or the topbar after a rename) mutating the
    // shared store directly. The dropdown — which subscribes to
    // ``useDomainsStore`` — must re-render with the new list
    // WITHOUT being unmounted/re-mounted. This is the load-bearing
    // Plan 12 Task 5 contract this consumer relies on.
    act(() => {
      useDomainsStore.setState({
        domains: [
          { slug: "research", label: "Research", accent: "var(--dom-research)", configured: true, on_disk: true },
          { slug: "personal", label: "Personal", accent: "var(--dom-personal)", configured: true, on_disk: true },
          // "work" deleted; "consulting" added.
          { slug: "consulting", label: "Consulting", accent: "#bb88ff", configured: true, on_disk: true },
        ],
      });
    });

    opts = Array.from(select.querySelectorAll("option"))
      .map((o) => o.value)
      .filter((v) => v !== "");
    expect(opts).toEqual(["research", "personal", "consulting"]);
  });

  test("optimistic update fires BEFORE the API resolves (snappy UI)", async () => {
    // Hold the API promise until we explicitly resolve so we can
    // assert the store updated *before* the resolution.
    let resolveApi: (val: unknown) => void = () => {};
    setActiveDomainMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveApi = resolve;
        }),
    );

    const user = userEvent.setup();
    render(<PanelDomains />);
    const select = (await screen.findByTestId(
      "active-domain-selector",
    )) as HTMLSelectElement;

    await user.selectOptions(select, "work");

    // API still pending; store is already updated optimistically.
    expect(setActiveDomainMock).toHaveBeenCalled();
    expect(useDomainsStore.getState().activeDomain).toBe("work");
    expect(select.value).toBe("work");

    // Resolve the API; final state stays "work".
    await act(async () => {
      resolveApi({ text: "", data: { key: "active_domain", value: "work" } });
    });
    expect(useDomainsStore.getState().activeDomain).toBe("work");
  });
});
