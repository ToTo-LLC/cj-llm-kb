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
import { ApiError } from "@/lib/api/types";

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

  test("validator-error path: 400 ApiError → CTA 'Pick a different domain' + dropdown reverts (Plan 15 Task 6 / D5)", async () => {
    // Backend cross-field validator (``_check_active_domain_membership``)
    // raises ``ValueError`` which brain_api's error layer renders as a
    // flat 400 envelope with code ``invalid_input``. apiFetch decodes
    // that into ``new ApiError(400, "invalid_input", null, message)``.
    // This is the realistic shape — the prior plain-``Error`` mock was
    // a fabrication that didn't exercise the discriminator.
    const user = userEvent.setup();
    setActiveDomainMock.mockRejectedValueOnce(
      new ApiError(
        400,
        "invalid_input",
        null,
        "active_domain 'work' not in Config.domains [..]",
      ),
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
    // message + the validator-branch "Pick a different domain" CTA.
    const dangerToast = pushToastStub.mock.calls.find(
      (c) => (c[0] as { variant?: string }).variant === "danger",
    );
    expect(dangerToast).toBeDefined();
    const payload = dangerToast![0] as { lead: string; msg: string };
    expect(payload.lead).toMatch(/couldn't update active domain/i);
    expect(payload.msg).toMatch(/Pick a different domain/i);
    expect(payload.msg).toMatch(/not in Config\.domains/);
    // Negative assertion: validator errors must NOT use the transport CTA.
    expect(payload.msg).not.toMatch(/Try again/i);
  });

  test("transport-error path: network failure → CTA 'Try again' (Plan 15 Task 6 / D5; Plan 12 Task 8 review I1)", async () => {
    // Transport errors surface as fetch reject (``TypeError("fetch
    // failed")`` in Node, ``TypeError("Failed to fetch")`` in the
    // browser) or as non-2xx responses without a 400 body (e.g. a 502
    // from an upstream proxy, surfaced as ``ApiError(502, ...)``). The
    // user's domain choice was fine — the wire blew up. The CTA must
    // be "Try again", not "Pick a different domain", because retrying
    // the same value is the right next step.
    const user = userEvent.setup();
    setActiveDomainMock.mockRejectedValueOnce(
      new TypeError("fetch failed"),
    );

    render(<PanelDomains />);
    const select = (await screen.findByTestId(
      "active-domain-selector",
    )) as HTMLSelectElement;
    expect(select.value).toBe("research");

    await user.selectOptions(select, "work");

    // Optimistic update reverts on transport error too.
    await waitFor(() => {
      expect(useDomainsStore.getState().activeDomain).toBe("research");
    });
    expect(select.value).toBe("research");

    const dangerToast = pushToastStub.mock.calls.find(
      (c) => (c[0] as { variant?: string }).variant === "danger",
    );
    expect(dangerToast).toBeDefined();
    const payload = dangerToast![0] as { lead: string; msg: string };
    expect(payload.lead).toMatch(/couldn't update active domain/i);
    expect(payload.msg).toMatch(/Try again/i);
    expect(payload.msg).toMatch(/fetch failed/i);
    // Negative assertion: transport errors must NOT misdirect the user
    // to picking a different domain.
    expect(payload.msg).not.toMatch(/Pick a different domain/i);
  });

  test("transport-error path: 5xx ApiError also routes to 'Try again' (non-400 status is transport, not validator)", async () => {
    // Belt-and-braces: a 502/503 from an upstream proxy is also a
    // transport error from the user's POV — same CTA as the network
    // failure. This pins the discriminator to ``status === 400`` and
    // not just "any Error".
    const user = userEvent.setup();
    setActiveDomainMock.mockRejectedValueOnce(
      new ApiError(502, "bad_gateway", null, "upstream timed out"),
    );

    render(<PanelDomains />);
    const select = (await screen.findByTestId(
      "active-domain-selector",
    )) as HTMLSelectElement;

    await user.selectOptions(select, "work");

    await waitFor(() => {
      expect(useDomainsStore.getState().activeDomain).toBe("research");
    });

    const dangerToast = pushToastStub.mock.calls.find(
      (c) => (c[0] as { variant?: string }).variant === "danger",
    );
    expect(dangerToast).toBeDefined();
    const payload = dangerToast![0] as { msg: string };
    expect(payload.msg).toMatch(/Try again/i);
    expect(payload.msg).not.toMatch(/Pick a different domain/i);
  });

  test("pushToast lives OUTSIDE the catch block: rollback happens BEFORE the toast dispatch (Plan 15 Task 6 / D5; Plan 12 Task 8 review I2)", async () => {
    // Defensive scoping: pushToast is a zustand setter and shouldn't
    // throw, but moving it out of the catch block means a hypothetical
    // bug there can't shadow the optimistic rollback. The cleanest
    // observable contract is the CALL ORDER — the optimistic rollback
    // (``setActiveDomainOptimistic(previous)``) must execute BEFORE
    // pushToast is called. We instrument both and assert the order.
    setActiveDomainMock.mockRejectedValueOnce(
      new ApiError(400, "invalid_input", null, "active_domain not in domains"),
    );

    // Spy on the store's optimistic action to capture invocation order.
    const realOptimistic =
      useDomainsStore.getState().setActiveDomainOptimistic;
    const calls: string[] = [];
    const spyOptimistic = vi.fn((slug: string) => {
      calls.push(`optimistic:${slug}`);
      realOptimistic(slug);
    });
    useDomainsStore.setState({ setActiveDomainOptimistic: spyOptimistic });

    pushToastStub.mockImplementation((payload: { variant?: string }) => {
      calls.push(`toast:${payload.variant ?? "default"}`);
    });

    const user = userEvent.setup();
    render(<PanelDomains />);
    const select = (await screen.findByTestId(
      "active-domain-selector",
    )) as HTMLSelectElement;
    expect(select.value).toBe("research");

    await user.selectOptions(select, "work");

    // Wait for the failed-API rejection + revert path to settle.
    await waitFor(() => {
      expect(useDomainsStore.getState().activeDomain).toBe("research");
    });

    // Restore the real action so other tests aren't affected.
    useDomainsStore.setState({ setActiveDomainOptimistic: realOptimistic });

    // Three calls, in this order:
    //   1. optimistic:work        — initial optimistic update
    //   2. optimistic:research    — rollback (INSIDE the catch block)
    //   3. toast:danger           — pushToast (OUTSIDE the catch block)
    //
    // If pushToast were still inside the catch block, observers
    // couldn't distinguish — but the ordering ``optimistic:research``
    // BEFORE ``toast:danger`` is the structural fingerprint of the
    // refactor. Specifically, the rollback runs and completes before
    // the toast dispatch is even queued.
    expect(calls).toEqual([
      "optimistic:work",
      "optimistic:research",
      "toast:danger",
    ]);
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
