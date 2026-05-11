"use client";

import * as React from "react";
import { ChevronDown, ChevronRight, Edit2, Lock, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DomainOverrideForm,
  type DomainOverrideValues,
} from "@/components/settings/domain-override-form";
import { configGet, setDomainRateLimit } from "@/lib/api/tools";
import { useBudgetStore } from "@/lib/state/budget-store";
import type { DomainEntry } from "@/lib/state/domains-store";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * PanelDomainsRow (Plan 16 Task 8 / D8).
 *
 * Per-domain row inside the Settings → Domains list. Factored out of
 * ``panel-domains.tsx`` as part of the orchestrator + 3-children split.
 *
 * Owns the row's visual chrome only — the chevron + accent dot + slug
 * label, the privacy-railed badge for ``personal``, the privacy-rail
 * checkbox (or its disabled-and-checked tooltip variant for
 * ``personal``), the rename + delete buttons, and the expanded
 * ``<DomainOverrideForm>`` panel. All state mutations bubble up to the
 * orchestrator via callbacks; the row holds NO local state of its own.
 *
 * Visual + accessibility identity: the rendered DOM, ARIA attributes,
 * data-testids, and keyboard behaviour are byte-identical to the
 * pre-split inline implementation. Tests written against the
 * orchestrator (slug labels, ``data-testid="domain-row"``, the
 * ``personal-privacy-badge``, ``privacy-rail-checkbox-{slug}``,
 * ``rename-{slug}`` / ``delete-{slug}`` buttons) all continue to pass.
 */

const PROTECTED_DOMAINS = new Set<string>(["personal"]);

interface PanelDomainsRowProps {
  /** The domain to render. */
  domain: DomainEntry;
  /** The accent color for this row's swatch dot. Built-ins resolve
   *  via ``--dom-{slug}`` CSS variables; user-added domains rotate
   *  through ``ACCENT_SWATCHES``. The orchestrator computes this
   *  (uses the row's index) and passes it in. */
  accent: string;
  /** Whether this row's override panel is currently expanded. */
  isExpanded: boolean;
  /** Whether this domain is currently in the privacy rail. */
  isRailed: boolean;
  /** The override values to seed ``<DomainOverrideForm>`` with on
   *  expand. Falsy when not yet fetched — orchestrator owns the
   *  lazy-fetch on first expand. */
  overrideValues: DomainOverrideValues;
  /** Toggle the expanded state for this row. */
  onToggleExpanded: (slug: string) => void;
  /** Add or remove the slug from the privacy rail. */
  onTogglePrivacyRail: (slug: string, checked: boolean) => void;
  /** Open the rename dialog for this slug. */
  onRename: (slug: string) => void;
  /** Open the typed-confirm dialog for deleting this slug. The row
   *  itself never destroys data — the orchestrator owns the API call
   *  inside ``onConfirm`` so the optimistic store + reconciliation
   *  flow stays in one place. */
  onDelete: (slug: string) => void;
  /** Called after each ``DomainOverrideForm`` save so the orchestrator
   *  can re-fetch the override snapshot from the backend. */
  onOverrideChanged: (slug: string) => void;
}

export function PanelDomainsRow({
  domain,
  accent,
  isExpanded,
  isRailed,
  overrideValues,
  onToggleExpanded,
  onTogglePrivacyRail,
  onRename,
  onDelete,
  onOverrideChanged,
}: PanelDomainsRowProps): React.ReactElement {
  const slug = domain.slug;
  const protectedDomain = PROTECTED_DOMAINS.has(slug);
  const railCheckboxId = `privacy-rail-${slug}`;

  return (
    <li
      data-testid="domain-row"
      className="flex flex-col border-b border-[var(--hairline)] last:border-0"
    >
      <div className="flex items-center gap-3 px-3 py-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => onToggleExpanded(slug)}
          aria-label={
            isExpanded
              ? `Collapse ${slug} overrides`
              : `Expand ${slug} overrides`
          }
          aria-expanded={isExpanded}
          aria-controls={`override-panel-${slug}`}
          className="h-7 w-7 p-0"
        >
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </Button>
        <span
          aria-hidden="true"
          className="h-4 w-4 rounded-full border border-[var(--hairline)]"
          style={{ background: accent }}
        />
        <span className="font-mono text-sm text-[var(--text)]">{slug}</span>

        {protectedDomain && (
          <span
            data-testid="personal-privacy-badge"
            className="inline-flex items-center gap-1 rounded-full border border-[var(--hairline-strong)] px-2 py-0.5 text-[10px] font-medium"
            style={{
              background: "var(--dom-personal-soft)",
              color: "var(--dom-personal)",
            }}
          >
            <Lock className="h-2.5 w-2.5" />
            Privacy-railed
          </span>
        )}

        <div className="ml-auto flex items-center gap-3">
          {/* Privacy-rail checkbox per row. Personal is
              disabled-and-checked; tooltip explains why. */}
          {protectedDomain ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="inline-flex items-center gap-1.5">
                  <Checkbox
                    id={railCheckboxId}
                    checked={true}
                    disabled={true}
                    data-testid={`privacy-rail-checkbox-${slug}`}
                    aria-labelledby={`privacy-rail-label-${slug}`}
                  />
                  <label
                    id={`privacy-rail-label-${slug}`}
                    htmlFor={railCheckboxId}
                    className="text-[11px] text-[var(--text-muted)]"
                  >
                    Privacy-railed
                  </label>
                </span>
              </TooltipTrigger>
              <TooltipContent>
                personal is required and cannot be un-railed.
              </TooltipContent>
            </Tooltip>
          ) : (
            <span className="inline-flex items-center gap-1.5">
              <Checkbox
                id={railCheckboxId}
                checked={isRailed}
                onCheckedChange={(v) => onTogglePrivacyRail(slug, Boolean(v))}
                data-testid={`privacy-rail-checkbox-${slug}`}
                aria-labelledby={`privacy-rail-label-${slug}`}
              />
              <label
                id={`privacy-rail-label-${slug}`}
                htmlFor={railCheckboxId}
                className="text-[11px] text-[var(--text-muted)]"
              >
                Privacy-railed
              </label>
            </span>
          )}

          <Button
            variant="ghost"
            size="sm"
            onClick={() => onRename(slug)}
            aria-label={`Rename ${slug}`}
            className="h-7 gap-1 px-2 text-xs"
          >
            <Edit2 className="h-3 w-3" />
            Rename
          </Button>
          {!protectedDomain && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onDelete(slug)}
              aria-label={`Delete ${slug}`}
              className="h-7 gap-1 px-2 text-xs text-red-400 hover:text-red-300"
            >
              <Trash2 className="h-3 w-3" />
              Delete
            </Button>
          )}
        </div>
      </div>

      {isExpanded && (
        <div
          id={`override-panel-${slug}`}
          className="flex flex-col gap-3 border-t border-[var(--hairline)] bg-[var(--surface-0)] px-3 py-3"
        >
          <DomainOverrideForm
            slug={slug}
            initialValues={overrideValues}
            onChanged={() => onOverrideChanged(slug)}
          />
          {/* Plan 16 Task 29 / D26 step 4 of 4: per-domain budget cap
              editor. Lives inside the same expanded panel as the
              override form so the user has one place to configure
              everything domain-specific. The subsection owns its own
              fetch + save (like ``DomainOverrideForm``) — the row
              itself stays a thin coordinator. */}
          <BudgetCapsSubsection slug={slug} />
          {/* Plan 16 Task 32 / D27 step 3 of 3: per-domain rate-limit
              editor. Mirrors ``BudgetCapsSubsection`` — same lazy
              hydrate + on-blur save + toast pattern, same role/aria
              shape. Lives below the budget caps so all per-domain
              spending controls (budget caps + rate limit) cluster
              together inside the expanded panel. */}
          <RateLimitSubsection slug={slug} />
        </div>
      )}
    </li>
  );
}

/* ---------------------- Budget caps subsection ---------------------- */

/**
 * Per-domain budget cap editor (Plan 16 Task 29 / D26 step 4 of 4;
 * migrated to budget-store in Plan 17 Task 4).
 *
 * Two optional inputs (daily, monthly cap, both in USD). Empty input =
 * no cap (= ``null`` on the wire). Save fires on blur — the field
 * compares current input against the last-known persisted value and
 * skips the API round-trip if nothing changed (mirrors the
 * ``DomainOverrideForm`` per-field blur pattern).
 *
 * Validation: positive numerics only. Zero / negative caps are rejected
 * client-side with a red border + a hint, AND server-side by the
 * :class:`BudgetOverride._validate_positive` validator (defense in
 * depth — the UI catches it first so the user never hits the round
 * trip). An empty input is valid (= null = "no cap").
 *
 * Hydration reads from the shared ``useBudgetStore`` snapshot (Plan 17
 * Task 4). The ``readBudgetCapsFor`` inline fetch is removed; the store
 * owns the fetch lifecycle and keeps peer tabs in sync via
 * BroadcastChannel.  Saves go through
 * ``useBudgetStore.getState().setDomainCap`` which applies the same
 * optimistic-revert pattern as the global budget caps.
 *
 * Wire contract: each save posts the WHOLE current pair (both caps)
 * to ``setDomainCap``. The backend prunes the entry when both caps are
 * null.
 */
interface BudgetCapsSubsectionProps {
  slug: string;
}

interface BudgetCapsState {
  daily_cap_usd: number | null;
  monthly_cap_usd: number | null;
}

const EMPTY_CAPS: BudgetCapsState = {
  daily_cap_usd: null,
  monthly_cap_usd: null,
};

/** Empty input = null = no cap; positive numeric = cap. Reject zero
 *  and negative; reject non-numeric.
 */
function isValidCap(s: string): boolean {
  if (s.trim() === "") return true;
  const n = Number(s);
  return Number.isFinite(n) && n > 0;
}

export function BudgetCapsSubsection({
  slug,
}: BudgetCapsSubsectionProps): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);

  // Last-known persisted state; updated after each successful save so
  // the blur-skip-if-unchanged check stays honest. Hydrated lazily on
  // first mount.
  const [persisted, setPersisted] = React.useState<BudgetCapsState>(EMPTY_CAPS);
  // In-progress edit values for each input (string-typed because the
  // inputs are <input>, coerced on save).
  const [dailyInput, setDailyInput] = React.useState<string>("");
  const [monthlyInput, setMonthlyInput] = React.useState<string>("");

  // Read from the shared budget store (Plan 17 Task 4). The store is
  // loaded by the parent layout; ``budgetLoaded`` gates the one-time
  // hydration of the edit buffers. We intentionally omit
  // ``perDomainCaps`` from the dependency array to avoid overwriting an
  // in-progress edit when a peer-tab broadcast updates the store.
  const perDomainCaps = useBudgetStore((s) => s.snapshot.per_domain);
  const budgetLoaded = useBudgetStore((s) => s.loaded);

  React.useEffect(() => {
    if (budgetLoaded) {
      const caps = perDomainCaps[slug] ?? EMPTY_CAPS;
      setDailyInput(caps.daily_cap_usd !== null ? String(caps.daily_cap_usd) : "");
      setMonthlyInput(
        caps.monthly_cap_usd !== null ? String(caps.monthly_cap_usd) : "",
      );
      setPersisted(caps);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [budgetLoaded, slug]); // `perDomainCaps` intentionally omitted to avoid mid-edit overwrite

  const dailyValid = isValidCap(dailyInput);
  const monthlyValid = isValidCap(monthlyInput);

  /** Save the whole pair (both caps). The backend's apply-helper
   *  prunes the entry when both are null, so we don't have to
   *  special-case "clear" here. Routes through the budget store so
   *  the optimistic update + peer-tab broadcast happen automatically. */
  const saveCaps = async (next: BudgetCapsState) => {
    try {
      await useBudgetStore.getState().setDomainCap(slug, next);
      setPersisted(next);
      pushToast({
        lead: "Budget caps saved.",
        msg: `Updated caps for ${slug}.`,
        variant: "success",
      });
    } catch (err) {
      pushToast({
        lead: "Couldn't save budget caps.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    }
  };

  const onBlurDaily = () => {
    if (!dailyValid) return;
    const trimmed = dailyInput.trim();
    const nextDaily = trimmed === "" ? null : Number(trimmed);
    if (nextDaily === persisted.daily_cap_usd) return;
    void saveCaps({
      daily_cap_usd: nextDaily,
      monthly_cap_usd: persisted.monthly_cap_usd,
    });
  };

  const onBlurMonthly = () => {
    if (!monthlyValid) return;
    const trimmed = monthlyInput.trim();
    const nextMonthly = trimmed === "" ? null : Number(trimmed);
    if (nextMonthly === persisted.monthly_cap_usd) return;
    void saveCaps({
      daily_cap_usd: persisted.daily_cap_usd,
      monthly_cap_usd: nextMonthly,
    });
  };

  const dailyId = `budget-cap-daily-${slug}`;
  const monthlyId = `budget-cap-monthly-${slug}`;

  return (
    <div
      className="flex flex-col gap-3 rounded-md border border-[var(--hairline)] bg-[var(--surface-2)] p-3"
      data-testid={`budget-caps-subsection-${slug}`}
      role="group"
      aria-label={`Budget caps for ${slug}`}
    >
      <div className="flex flex-col gap-1">
        <h3 className="text-xs font-semibold text-[var(--text)]">
          Budget caps
        </h3>
        <p className="text-[11px] text-[var(--text-muted)]">
          Optional per-domain spending limits (USD). Empty = no cap; the
          global daily and monthly limits still apply.
        </p>
      </div>

      <div className="flex flex-col gap-1">
        <label
          htmlFor={dailyId}
          className="block text-[11px] uppercase tracking-wider text-[var(--text-dim)]"
        >
          Daily cap (USD)
        </label>
        <Input
          id={dailyId}
          data-testid={`budget-cap-daily-${slug}`}
          value={dailyInput}
          onChange={(e) => setDailyInput(e.target.value)}
          onBlur={onBlurDaily}
          placeholder="no cap"
          aria-invalid={!dailyValid}
          aria-describedby={`${dailyId}-hint`}
          inputMode="decimal"
        />
        {!dailyValid && (
          <p
            id={`${dailyId}-hint`}
            className="mt-1 text-[11px] text-red-400"
          >
            Must be a positive number (or empty for no cap).
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <label
          htmlFor={monthlyId}
          className="block text-[11px] uppercase tracking-wider text-[var(--text-dim)]"
        >
          Monthly cap (USD)
        </label>
        <Input
          id={monthlyId}
          data-testid={`budget-cap-monthly-${slug}`}
          value={monthlyInput}
          onChange={(e) => setMonthlyInput(e.target.value)}
          onBlur={onBlurMonthly}
          placeholder="no cap"
          aria-invalid={!monthlyValid}
          aria-describedby={`${monthlyId}-hint`}
          inputMode="decimal"
        />
        {!monthlyValid && (
          <p
            id={`${monthlyId}-hint`}
            className="mt-1 text-[11px] text-red-400"
          >
            Must be a positive number (or empty for no cap).
          </p>
        )}
      </div>
    </div>
  );
}

/* ---------------------- Rate limit subsection ---------------------- */

/**
 * Per-domain rate-limit editor (Plan 16 Task 32 / D27 step 3 of 3).
 *
 * One optional input: requests-per-minute. Empty = no override (= ``null``
 * on the wire = "the provider bypasses rate-limit gating for this
 * domain"). Save fires on blur — the field compares current input
 * against the last-known persisted value and skips the API round-trip
 * if nothing changed (mirrors :func:`BudgetCapsSubsection`).
 *
 * Validation: positive integers only. Zero / negative / non-integer
 * values are rejected client-side with a red border + a hint, AND
 * server-side by the
 * :class:`RateLimitOverride._validate_positive` validator (defense in
 * depth — the UI catches it first so the user never hits the round
 * trip). An empty input is valid (= null = "no override").
 *
 * The component reads its own initial state from
 * ``brain_config_get`` because the parent orchestrator already does
 * the same dance for ``domain_overrides`` and budget caps; threading a
 * parallel cache for rate limits would add surface area for no win.
 *
 * Wire contract: each save posts the WHOLE current payload (one field
 * today; whole-payload contract future-proofs the shape) to
 * ``setDomainRateLimit``. The backend prunes the entry when every leaf
 * is null.
 *
 * Provider is hard-coded to ``"anthropic"`` because that's the only LLM
 * provider implementation today; the wire shape supports more
 * providers without a frontend change (see :func:`setDomainRateLimit`).
 */
interface RateLimitSubsectionProps {
  slug: string;
}

interface RateLimitState {
  requests_per_minute: number | null;
}

const EMPTY_RATE_LIMIT: RateLimitState = {
  requests_per_minute: null,
};

/** Empty input = null = no override; positive integer = cap. Reject
 *  zero, negative, and non-integer values.
 */
function isValidRateLimit(s: string): boolean {
  if (s.trim() === "") return true;
  const n = Number(s);
  return Number.isFinite(n) && Number.isInteger(n) && n > 0;
}

async function readRateLimitFor(slug: string): Promise<RateLimitState> {
  try {
    // Read the whole providers map and pick the anthropic entry — the
    // hydrate fetch is one-shot per mount, so the extra payload cost
    // (vs. a deep-keyed read) is negligible and we don't have to invent
    // a per-(provider,slug) configGet shape.
    const r = await configGet({ key: "providers" });
    const providers = (r.data?.value ?? {}) as Record<
      string,
      { rate_limit_per_domain?: Record<string, Partial<RateLimitState>> }
    >;
    const entry = providers.anthropic?.rate_limit_per_domain?.[slug] ?? {};
    return {
      requests_per_minute: entry.requests_per_minute ?? null,
    };
  } catch {
    return EMPTY_RATE_LIMIT;
  }
}

export function RateLimitSubsection({
  slug,
}: RateLimitSubsectionProps): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);

  const [persisted, setPersisted] =
    React.useState<RateLimitState>(EMPTY_RATE_LIMIT);
  const [rpmInput, setRpmInput] = React.useState<string>("");

  React.useEffect(() => {
    let cancelled = false;
    void (async () => {
      const rl = await readRateLimitFor(slug);
      if (cancelled) return;
      setPersisted(rl);
      setRpmInput(
        rl.requests_per_minute !== null ? String(rl.requests_per_minute) : "",
      );
    })();
    return () => {
      cancelled = true;
    };
  }, [slug]);

  const rpmValid = isValidRateLimit(rpmInput);

  const saveRateLimit = async (next: RateLimitState) => {
    try {
      await setDomainRateLimit(slug, next);
      setPersisted(next);
      pushToast({
        lead: "Rate limit saved.",
        msg: `Updated rate limit for ${slug}.`,
        variant: "success",
      });
    } catch (err) {
      pushToast({
        lead: "Couldn't save rate limit.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    }
  };

  const onBlurRpm = () => {
    if (!rpmValid) return;
    const trimmed = rpmInput.trim();
    const nextRpm = trimmed === "" ? null : Number(trimmed);
    if (nextRpm === persisted.requests_per_minute) return;
    void saveRateLimit({ requests_per_minute: nextRpm });
  };

  const rpmId = `rate-limit-rpm-${slug}`;

  return (
    <div
      className="flex flex-col gap-3 rounded-md border border-[var(--hairline)] bg-[var(--surface-2)] p-3"
      data-testid={`rate-limit-subsection-${slug}`}
      role="group"
      aria-label={`Rate limit for ${slug}`}
    >
      <div className="flex flex-col gap-1">
        <h3 className="text-xs font-semibold text-[var(--text)]">
          Rate limit
        </h3>
        <p className="text-[11px] text-[var(--text-muted)]">
          Optional per-domain request rate (per minute). Empty = no override;
          the provider bypasses rate-limit gating for this domain.
        </p>
      </div>

      <div className="flex flex-col gap-1">
        <label
          htmlFor={rpmId}
          className="block text-[11px] uppercase tracking-wider text-[var(--text-dim)]"
        >
          Requests per minute
        </label>
        <Input
          id={rpmId}
          data-testid={`rate-limit-rpm-${slug}`}
          type="number"
          min={1}
          step={1}
          value={rpmInput}
          onChange={(e) => setRpmInput(e.target.value)}
          onBlur={onBlurRpm}
          placeholder="no override"
          aria-invalid={!rpmValid}
          aria-describedby={`${rpmId}-hint`}
          inputMode="numeric"
        />
        {!rpmValid && (
          <p
            id={`${rpmId}-hint`}
            className="mt-1 text-[11px] text-red-400"
          >
            Must be a positive integer (or empty for no override).
          </p>
        )}
      </div>
    </div>
  );
}
