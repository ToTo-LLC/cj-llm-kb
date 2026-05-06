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

  test("expand button has aria-expanded that mirrors isExpanded prop", () => {
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
  });
});
