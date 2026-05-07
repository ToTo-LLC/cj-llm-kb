/**
 * Plan 16 Task 8 (D8) — PanelDomainsRow tests.
 *
 * Pins the contract that the per-row editor (factored out of
 * ``panel-domains.tsx`` as part of the orchestrator + 3-children
 * split) owns no mutation logic of its own — every user action
 * bubbles to the orchestrator via a typed callback. This keeps the
 * row a pure-presentation component: no API calls, no store reads,
 * no side effects beyond calling props.
 *
 * Coverage:
 *   1. Rename — clicking the rename button invokes ``onRename(slug)``.
 *   2. Delete — clicking the delete button invokes ``onDelete(slug)``.
 *   3. Privacy-rail toggle — clicking the checkbox invokes
 *      ``onTogglePrivacyRail(slug, nextValue)``.
 *   4. Expand toggle — clicking the chevron invokes
 *      ``onToggleExpanded(slug)``.
 *   5. Override change — saving inside the expanded
 *      ``<DomainOverrideForm>`` propagates to ``onOverrideChanged(slug)``.
 *      (Tested by mocking the override form so we can fire the
 *      ``onChanged`` prop directly without round-tripping configSet.)
 *   6. Personal protection — the ``personal`` slug renders no delete
 *      button and the privacy-rail checkbox is disabled.
 *
 * The row receives a fully-formed ``DomainEntry`` from the orchestrator;
 * we don't test the entry-builder here (that's the domains-store's
 * job). The row's only structural assumption is ``domain.slug``.
 */

import { describe, expect, test, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

// Mock the override form so we don't need to mount its internals or
// stub configSet — we only care that ``onChanged`` propagates upward.
const { domainOverrideFormMock } = vi.hoisted(() => ({
  domainOverrideFormMock: vi.fn(),
}));

vi.mock("@/components/settings/domain-override-form", () => ({
  DomainOverrideForm: (props: {
    slug: string;
    onChanged: () => void;
  }) => {
    domainOverrideFormMock(props);
    return (
      <button
        type="button"
        data-testid={`mock-override-save-${props.slug}`}
        onClick={() => props.onChanged()}
      >
        save override
      </button>
    );
  },
}));

// Plan 16 Task 29 / D26 step 4 of 4: mock the budget API binding so we
// can assert the exact (slug, cap) payload the row emits on blur.
// ``configGet`` powers the lazy hydrate-on-mount fetch; default it to
// "no entry" so the inputs start empty unless a test overrides.
//
// Plan 16 Task 32 / D27 step 3 of 3: add the rate-limit binding mock so
// the rate-limit subsection can be exercised the same way. The
// rate-limit subsection reads ``providers`` (not ``budget.per_domain``)
// for hydration, but the budget subsection always mounts alongside it
// — both fire ``configGet`` on first mount, with different keys. The
// default mock returns the SAME shape regardless of ``key`` (an empty
// object) so each subsection's hydration sees "no entry"; tests that
// need a populated state use ``mockResolvedValueOnce`` per call site
// or differentiate by key.
const { setDomainBudgetMock, setDomainRateLimitMock, configGetMock } = vi.hoisted(
  () => ({
    setDomainBudgetMock: vi.fn(),
    setDomainRateLimitMock: vi.fn(),
    configGetMock: vi.fn(),
  }),
);

vi.mock("@/lib/api/tools", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/tools")>(
    "@/lib/api/tools",
  );
  return {
    ...actual,
    setDomainBudget: (...args: unknown[]) => setDomainBudgetMock(...args),
    setDomainRateLimit: (...args: unknown[]) => setDomainRateLimitMock(...args),
    configGet: (...args: unknown[]) => configGetMock(...args),
  };
});

// Pull pushToast onto a spy so we can assert toast emission without
// also pulling in the system store's actual implementation surface.
const { pushToastMock } = vi.hoisted(() => ({ pushToastMock: vi.fn() }));

vi.mock("@/lib/state/system-store", () => ({
  useSystemStore: (selector: (state: unknown) => unknown) =>
    selector({ pushToast: pushToastMock }),
}));

import { PanelDomainsRow } from "@/components/settings/panel-domains-row";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { DomainEntry } from "@/lib/state/domains-store";
import type { DomainOverrideValues } from "@/components/settings/domain-override-form";

const WORK_DOMAIN: DomainEntry = {
  slug: "work",
  label: "Work",
  accent: "var(--dom-work)",
  configured: true,
  on_disk: true,
};

const PERSONAL_DOMAIN: DomainEntry = {
  slug: "personal",
  label: "Personal",
  accent: "var(--dom-personal)",
  configured: true,
  on_disk: true,
};

const EMPTY_OVERRIDE: DomainOverrideValues = {
  classify_model: null,
  default_model: null,
  temperature: null,
  max_output_tokens: null,
  autonomous_mode: null,
};

interface RowProps {
  domain?: DomainEntry;
  accent?: string;
  isExpanded?: boolean;
  isRailed?: boolean;
  overrideValues?: DomainOverrideValues;
  onToggleExpanded?: ReturnType<typeof vi.fn>;
  onTogglePrivacyRail?: ReturnType<typeof vi.fn>;
  onRename?: ReturnType<typeof vi.fn>;
  onDelete?: ReturnType<typeof vi.fn>;
  onOverrideChanged?: ReturnType<typeof vi.fn>;
}

/** Render the row inside a ``TooltipProvider`` so the personal-domain
 *  tooltip variant doesn't blow up Radix's invariant check. */
function renderRow(overrides: RowProps = {}) {
  const props = {
    domain: overrides.domain ?? WORK_DOMAIN,
    accent: overrides.accent ?? "var(--dom-work)",
    isExpanded: overrides.isExpanded ?? false,
    isRailed: overrides.isRailed ?? false,
    overrideValues: overrides.overrideValues ?? EMPTY_OVERRIDE,
    onToggleExpanded: overrides.onToggleExpanded ?? vi.fn(),
    onTogglePrivacyRail: overrides.onTogglePrivacyRail ?? vi.fn(),
    onRename: overrides.onRename ?? vi.fn(),
    onDelete: overrides.onDelete ?? vi.fn(),
    onOverrideChanged: overrides.onOverrideChanged ?? vi.fn(),
  };
  return {
    ...render(
      <TooltipProvider>
        <ul>
          <PanelDomainsRow {...props} />
        </ul>
      </TooltipProvider>,
    ),
    props,
  };
}

beforeEach(() => {
  domainOverrideFormMock.mockReset();
  setDomainBudgetMock.mockReset();
  setDomainBudgetMock.mockResolvedValue(undefined);
  setDomainRateLimitMock.mockReset();
  setDomainRateLimitMock.mockResolvedValue(undefined);
  configGetMock.mockReset();
  // Default: no per-domain budget OR rate-limit entry exists. Tests
  // that need a populated slug override this per-test before render.
  // Both subsections hydrate from this mock with different keys
  // (``budget.per_domain`` vs. ``providers``); the empty ``{}`` shape
  // is correct for both.
  configGetMock.mockResolvedValue({ data: { value: {} } });
  pushToastMock.mockReset();
});

describe("PanelDomainsRow — Plan 16 Task 8 (D8)", () => {
  test("rename button invokes onRename(slug)", async () => {
    const user = userEvent.setup();
    const onRename = vi.fn();
    renderRow({ onRename });

    await user.click(screen.getByRole("button", { name: /rename work/i }));

    expect(onRename).toHaveBeenCalledTimes(1);
    expect(onRename).toHaveBeenCalledWith("work");
  });

  test("delete button invokes onDelete(slug)", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    renderRow({ onDelete });

    await user.click(screen.getByRole("button", { name: /delete work/i }));

    expect(onDelete).toHaveBeenCalledTimes(1);
    expect(onDelete).toHaveBeenCalledWith("work");
  });

  test("privacy-rail checkbox invokes onTogglePrivacyRail(slug, true) when unchecked → checked", async () => {
    const user = userEvent.setup();
    const onTogglePrivacyRail = vi.fn();
    renderRow({ isRailed: false, onTogglePrivacyRail });

    await user.click(screen.getByTestId("privacy-rail-checkbox-work"));

    expect(onTogglePrivacyRail).toHaveBeenCalledTimes(1);
    expect(onTogglePrivacyRail).toHaveBeenCalledWith("work", true);
  });

  test("expand button invokes onToggleExpanded(slug)", async () => {
    const user = userEvent.setup();
    const onToggleExpanded = vi.fn();
    renderRow({ isExpanded: false, onToggleExpanded });

    await user.click(
      screen.getByRole("button", { name: /expand work overrides/i }),
    );

    expect(onToggleExpanded).toHaveBeenCalledTimes(1);
    expect(onToggleExpanded).toHaveBeenCalledWith("work");
  });

  test("when expanded, override-form save invokes onOverrideChanged(slug)", async () => {
    const user = userEvent.setup();
    const onOverrideChanged = vi.fn();
    renderRow({ isExpanded: true, onOverrideChanged });

    // Plan 16 Task 29 + Task 32: wait for the budget AND rate-limit
    // subsections' lazy hydrate fetches to settle before exercising
    // the override-form save, so the unrelated state updates don't
    // leak act warnings into this test's run.
    await screen.findByTestId("budget-caps-subsection-work");
    await screen.findByTestId("rate-limit-subsection-work");

    // The mocked override form exposes a button that fires its
    // ``onChanged`` prop. Clicking it simulates a successful save.
    await user.click(screen.getByTestId("mock-override-save-work"));

    expect(onOverrideChanged).toHaveBeenCalledTimes(1);
    expect(onOverrideChanged).toHaveBeenCalledWith("work");

    // Pin: the override form was rendered with the row's slug + values.
    expect(domainOverrideFormMock).toHaveBeenCalled();
    const call = domainOverrideFormMock.mock.calls[0]![0] as {
      slug: string;
      initialValues: DomainOverrideValues;
    };
    expect(call.slug).toBe("work");
    expect(call.initialValues).toEqual(EMPTY_OVERRIDE);
  });

  test("personal: no delete button + privacy-rail checkbox disabled-and-checked", () => {
    renderRow({ domain: PERSONAL_DOMAIN, isRailed: true });

    // No delete button exists for personal — the row gates this on the
    // PROTECTED_DOMAINS set.
    expect(
      screen.queryByRole("button", { name: /delete personal/i }),
    ).not.toBeInTheDocument();

    // Privacy-rail badge is shown.
    expect(screen.getByTestId("personal-privacy-badge")).toBeInTheDocument();

    // The checkbox is disabled-and-checked.
    const checkbox = screen.getByTestId("privacy-rail-checkbox-personal");
    expect(checkbox).toBeDisabled();
    // Radix's ``Checkbox`` renders ``data-state="checked"`` when checked.
    expect(checkbox).toHaveAttribute("data-state", "checked");
  });

  test("when collapsed, override form is NOT rendered (lazy mount)", () => {
    renderRow({ isExpanded: false });

    // The mocked save button only renders inside the expanded panel.
    expect(
      screen.queryByTestId("mock-override-save-work"),
    ).not.toBeInTheDocument();
    // And the mock factory was never called either.
    expect(domainOverrideFormMock).not.toHaveBeenCalled();
  });

  describe("budget caps subsection (Plan 16 Task 29 / D26 step 4 of 4)", () => {
    test("not rendered when row collapsed", () => {
      renderRow({ isExpanded: false });
      expect(
        screen.queryByTestId("budget-caps-subsection-work"),
      ).not.toBeInTheDocument();
    });

    test("rendered when row expanded; both inputs hydrate empty for a slug with no entry", async () => {
      renderRow({ isExpanded: true });

      expect(
        await screen.findByTestId("budget-caps-subsection-work"),
      ).toBeInTheDocument();
      const daily = screen.getByTestId("budget-cap-daily-work") as HTMLInputElement;
      const monthly = screen.getByTestId(
        "budget-cap-monthly-work",
      ) as HTMLInputElement;
      // configGet's default mock returns ``{}`` so neither cap is set.
      expect(daily.value).toBe("");
      expect(monthly.value).toBe("");
      // The hydrate fetch reads the per_domain dict.
      expect(configGetMock).toHaveBeenCalledWith({ key: "budget.per_domain" });
    });

    test("hydrates inputs from the persisted per_domain entry for this slug", async () => {
      configGetMock.mockResolvedValueOnce({
        data: {
          value: {
            work: { daily_cap_usd: 1.5, monthly_cap_usd: 30 },
          },
        },
      });
      renderRow({ isExpanded: true });

      const daily = (await screen.findByTestId(
        "budget-cap-daily-work",
      )) as HTMLInputElement;
      const monthly = screen.getByTestId(
        "budget-cap-monthly-work",
      ) as HTMLInputElement;
      // useEffect hydration happens after the first render's commit;
      // ``findByTestId`` already retried once but the value flips on a
      // subsequent commit — wait for it explicitly.
      await vi.waitFor(() => expect(daily.value).toBe("1.5"));
      expect(monthly.value).toBe("30");
    });

    test("typing a monthly cap then blurring calls setDomainBudget with both caps", async () => {
      const user = userEvent.setup();
      renderRow({ isExpanded: true });

      const monthly = await screen.findByTestId("budget-cap-monthly-work");
      await user.type(monthly, "10");
      await user.tab(); // blur

      expect(setDomainBudgetMock).toHaveBeenCalledTimes(1);
      expect(setDomainBudgetMock).toHaveBeenCalledWith("work", {
        daily_cap_usd: null,
        monthly_cap_usd: 10,
      });
    });

    test("typing a daily cap then blurring calls setDomainBudget with both caps", async () => {
      const user = userEvent.setup();
      renderRow({ isExpanded: true });

      const daily = await screen.findByTestId("budget-cap-daily-work");
      await user.type(daily, "2.5");
      await user.tab();

      expect(setDomainBudgetMock).toHaveBeenCalledTimes(1);
      expect(setDomainBudgetMock).toHaveBeenCalledWith("work", {
        daily_cap_usd: 2.5,
        monthly_cap_usd: null,
      });
    });

    test("typing zero shows red border and blocks the save", async () => {
      const user = userEvent.setup();
      renderRow({ isExpanded: true });

      const daily = (await screen.findByTestId(
        "budget-cap-daily-work",
      )) as HTMLInputElement;
      await user.type(daily, "0");
      await user.tab();

      expect(daily).toHaveAttribute("aria-invalid", "true");
      expect(setDomainBudgetMock).not.toHaveBeenCalled();
      // The hint text mentions the validation rule.
      expect(
        screen.getByText(/positive number/i),
      ).toBeInTheDocument();
    });

    test("typing a negative cap shows red border and blocks the save", async () => {
      const user = userEvent.setup();
      renderRow({ isExpanded: true });

      const monthly = (await screen.findByTestId(
        "budget-cap-monthly-work",
      )) as HTMLInputElement;
      await user.type(monthly, "-5");
      await user.tab();

      expect(monthly).toHaveAttribute("aria-invalid", "true");
      expect(setDomainBudgetMock).not.toHaveBeenCalled();
    });

    test("clearing a previously-set cap saves with that field as null", async () => {
      // Slug has a daily cap of 2.0 already.
      configGetMock.mockResolvedValueOnce({
        data: {
          value: {
            work: { daily_cap_usd: 2.0, monthly_cap_usd: null },
          },
        },
      });
      const user = userEvent.setup();
      renderRow({ isExpanded: true });

      const daily = (await screen.findByTestId(
        "budget-cap-daily-work",
      )) as HTMLInputElement;
      await vi.waitFor(() => expect(daily.value).toBe("2"));

      await user.clear(daily);
      await user.tab();

      expect(setDomainBudgetMock).toHaveBeenCalledTimes(1);
      expect(setDomainBudgetMock).toHaveBeenCalledWith("work", {
        daily_cap_usd: null,
        monthly_cap_usd: null,
      });
    });

    test("blur with unchanged value does NOT trigger a save", async () => {
      configGetMock.mockResolvedValueOnce({
        data: { value: { work: { daily_cap_usd: 1.0 } } },
      });
      const user = userEvent.setup();
      renderRow({ isExpanded: true });

      const daily = (await screen.findByTestId(
        "budget-cap-daily-work",
      )) as HTMLInputElement;
      await vi.waitFor(() => expect(daily.value).toBe("1"));

      // Blur without changing the value.
      await user.click(daily);
      await user.tab();

      expect(setDomainBudgetMock).not.toHaveBeenCalled();
    });

    test("successful save fires a success toast", async () => {
      const user = userEvent.setup();
      renderRow({ isExpanded: true });

      const monthly = await screen.findByTestId("budget-cap-monthly-work");
      await user.type(monthly, "10");
      await user.tab();

      await vi.waitFor(() =>
        expect(pushToastMock).toHaveBeenCalledWith(
          expect.objectContaining({
            variant: "success",
            lead: expect.stringMatching(/budget caps saved/i),
          }),
        ),
      );
    });

    test("failed save fires a danger toast and does not update internal state", async () => {
      setDomainBudgetMock.mockRejectedValueOnce(new Error("boom"));
      const user = userEvent.setup();
      renderRow({ isExpanded: true });

      const daily = await screen.findByTestId("budget-cap-daily-work");
      await user.type(daily, "1.5");
      await user.tab();

      await vi.waitFor(() =>
        expect(pushToastMock).toHaveBeenCalledWith(
          expect.objectContaining({
            variant: "danger",
            lead: expect.stringMatching(/couldn['']t save/i),
            msg: expect.stringContaining("boom"),
          }),
        ),
      );
    });
  });

  describe("rate limit subsection (Plan 16 Task 32 / D27 step 3 of 3)", () => {
    test("not rendered when row collapsed", () => {
      renderRow({ isExpanded: false });
      expect(
        screen.queryByTestId("rate-limit-subsection-work"),
      ).not.toBeInTheDocument();
    });

    test("rendered when row expanded; input hydrates empty for a slug with no entry", async () => {
      renderRow({ isExpanded: true });

      expect(
        await screen.findByTestId("rate-limit-subsection-work"),
      ).toBeInTheDocument();
      const rpm = screen.getByTestId("rate-limit-rpm-work") as HTMLInputElement;
      // configGet's default mock returns ``{}`` so no override exists.
      expect(rpm.value).toBe("");
      // The hydrate fetch reads the providers map (not budget.per_domain) —
      // pin the exact key so a future refactor that breaks the wire shape
      // shows up here.
      expect(configGetMock).toHaveBeenCalledWith({ key: "providers" });
    });

    test("hydrates input from the persisted providers entry for this slug", async () => {
      // configGet is called twice on mount (budget + rate-limit
      // subsections). Differentiate by key so the rate-limit hydrate
      // sees a populated payload while the budget hydrate sees the
      // default empty entry.
      configGetMock.mockImplementation(async (args: { key: string }) => {
        if (args.key === "providers") {
          return {
            data: {
              value: {
                anthropic: {
                  rate_limit_per_domain: {
                    work: { requests_per_minute: 45 },
                  },
                },
              },
            },
          };
        }
        return { data: { value: {} } };
      });
      renderRow({ isExpanded: true });

      const rpm = (await screen.findByTestId(
        "rate-limit-rpm-work",
      )) as HTMLInputElement;
      // useEffect hydration runs after the first commit; wait for
      // the value to flip on the subsequent commit.
      await vi.waitFor(() => expect(rpm.value).toBe("45"));
    });

    test("typing an rpm then blurring calls setDomainRateLimit with the whole payload", async () => {
      const user = userEvent.setup();
      renderRow({ isExpanded: true });

      const rpm = await screen.findByTestId("rate-limit-rpm-work");
      await user.type(rpm, "30");
      await user.tab(); // blur

      expect(setDomainRateLimitMock).toHaveBeenCalledTimes(1);
      expect(setDomainRateLimitMock).toHaveBeenCalledWith("work", {
        requests_per_minute: 30,
      });
    });

    test("typing zero shows red border and blocks the save", async () => {
      const user = userEvent.setup();
      renderRow({ isExpanded: true });

      const rpm = (await screen.findByTestId(
        "rate-limit-rpm-work",
      )) as HTMLInputElement;
      await user.type(rpm, "0");
      await user.tab();

      expect(rpm).toHaveAttribute("aria-invalid", "true");
      expect(setDomainRateLimitMock).not.toHaveBeenCalled();
      // The hint text mentions the validation rule.
      expect(
        screen.getByText(/positive integer/i),
      ).toBeInTheDocument();
    });

    test("typing a negative rpm shows red border and blocks the save", async () => {
      const user = userEvent.setup();
      renderRow({ isExpanded: true });

      const rpm = (await screen.findByTestId(
        "rate-limit-rpm-work",
      )) as HTMLInputElement;
      await user.type(rpm, "-5");
      await user.tab();

      expect(rpm).toHaveAttribute("aria-invalid", "true");
      expect(setDomainRateLimitMock).not.toHaveBeenCalled();
    });

    test("typing a non-integer rpm shows red border and blocks the save", async () => {
      const user = userEvent.setup();
      renderRow({ isExpanded: true });

      const rpm = (await screen.findByTestId(
        "rate-limit-rpm-work",
      )) as HTMLInputElement;
      // 1.5 requests/minute is meaningless — RateLimitOverride enforces
      // ``int`` and Pydantic would reject this on the wire. Catch it
      // client-side before the round trip.
      await user.type(rpm, "1.5");
      await user.tab();

      expect(rpm).toHaveAttribute("aria-invalid", "true");
      expect(setDomainRateLimitMock).not.toHaveBeenCalled();
    });

    test("clearing a previously-set rpm saves with requests_per_minute=null", async () => {
      configGetMock.mockImplementation(async (args: { key: string }) => {
        if (args.key === "providers") {
          return {
            data: {
              value: {
                anthropic: {
                  rate_limit_per_domain: {
                    work: { requests_per_minute: 60 },
                  },
                },
              },
            },
          };
        }
        return { data: { value: {} } };
      });
      const user = userEvent.setup();
      renderRow({ isExpanded: true });

      const rpm = (await screen.findByTestId(
        "rate-limit-rpm-work",
      )) as HTMLInputElement;
      await vi.waitFor(() => expect(rpm.value).toBe("60"));

      await user.clear(rpm);
      await user.tab();

      expect(setDomainRateLimitMock).toHaveBeenCalledTimes(1);
      expect(setDomainRateLimitMock).toHaveBeenCalledWith("work", {
        requests_per_minute: null,
      });
    });

    test("blur with unchanged value does NOT trigger a save", async () => {
      configGetMock.mockImplementation(async (args: { key: string }) => {
        if (args.key === "providers") {
          return {
            data: {
              value: {
                anthropic: {
                  rate_limit_per_domain: {
                    work: { requests_per_minute: 30 },
                  },
                },
              },
            },
          };
        }
        return { data: { value: {} } };
      });
      const user = userEvent.setup();
      renderRow({ isExpanded: true });

      const rpm = (await screen.findByTestId(
        "rate-limit-rpm-work",
      )) as HTMLInputElement;
      await vi.waitFor(() => expect(rpm.value).toBe("30"));

      // Blur without changing the value.
      await user.click(rpm);
      await user.tab();

      expect(setDomainRateLimitMock).not.toHaveBeenCalled();
    });

    test("successful save fires a success toast", async () => {
      const user = userEvent.setup();
      renderRow({ isExpanded: true });

      const rpm = await screen.findByTestId("rate-limit-rpm-work");
      await user.type(rpm, "30");
      await user.tab();

      await vi.waitFor(() =>
        expect(pushToastMock).toHaveBeenCalledWith(
          expect.objectContaining({
            variant: "success",
            lead: expect.stringMatching(/rate limit saved/i),
          }),
        ),
      );
    });

    test("failed save fires a danger toast", async () => {
      setDomainRateLimitMock.mockRejectedValueOnce(new Error("kaboom"));
      const user = userEvent.setup();
      renderRow({ isExpanded: true });

      const rpm = await screen.findByTestId("rate-limit-rpm-work");
      await user.type(rpm, "45");
      await user.tab();

      await vi.waitFor(() =>
        expect(pushToastMock).toHaveBeenCalledWith(
          expect.objectContaining({
            variant: "danger",
            lead: expect.stringMatching(/couldn['']t save/i),
            msg: expect.stringContaining("kaboom"),
          }),
        ),
      );
    });
  });

  test("expand button has aria-expanded that mirrors isExpanded prop", async () => {
    const { rerender } = renderRow({ isExpanded: false });

    let expandBtn = screen.getByRole("button", {
      name: /expand work overrides/i,
    });
    expect(expandBtn).toHaveAttribute("aria-expanded", "false");
    expect(expandBtn).toHaveAttribute("aria-controls", "override-panel-work");

    // Re-render expanded — the label flips and aria-expanded follows.
    const noopProps: RowProps = {
      isExpanded: true,
      onToggleExpanded: vi.fn(),
      onTogglePrivacyRail: vi.fn(),
      onRename: vi.fn(),
      onDelete: vi.fn(),
      onOverrideChanged: vi.fn(),
    };
    rerender(
      <TooltipProvider>
        <ul>
          <PanelDomainsRow
            domain={WORK_DOMAIN}
            accent="var(--dom-work)"
            isExpanded={noopProps.isExpanded!}
            isRailed={false}
            overrideValues={EMPTY_OVERRIDE}
            onToggleExpanded={noopProps.onToggleExpanded!}
            onTogglePrivacyRail={noopProps.onTogglePrivacyRail!}
            onRename={noopProps.onRename!}
            onDelete={noopProps.onDelete!}
            onOverrideChanged={noopProps.onOverrideChanged!}
          />
        </ul>
      </TooltipProvider>,
    );
    expandBtn = screen.getByRole("button", {
      name: /collapse work overrides/i,
    });
    expect(expandBtn).toHaveAttribute("aria-expanded", "true");

    // Plan 16 Task 29 + Task 32: re-rendering the row expanded mounts
    // the ``BudgetCapsSubsection`` AND the ``RateLimitSubsection``,
    // both of which fire lazy ``configGet`` calls. Wait for both
    // fetches to settle so this test doesn't leak an act warning into
    // the next test's run via an unsettled state update.
    await screen.findByTestId("budget-caps-subsection-work");
    await screen.findByTestId("rate-limit-subsection-work");
  });
});
