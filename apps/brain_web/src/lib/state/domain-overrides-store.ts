"use client";

import { create } from "zustand";

import { configGet, configSet } from "@/lib/api/tools";
import { createChannelPubsub, type ChannelPubsub } from "./_broadcast";

/**
 * Domain-overrides store (Plan 16 Task 43 / D32(b)).
 *
 * Promotes the per-domain ``DomainOverride`` snapshot read shape that
 * ``panel-domains.tsx::readOverridesFor`` and ``domain-override-form.tsx``
 * used to scrape one ``configGet({key: "domain_overrides"})`` per
 * expand to a shared zustand store + selector. Mirrors the
 * ``domains-store.ts`` / ``cross-domain-gate-store.ts`` /
 * ``budget-store.ts`` shape exactly: ``refresh()`` is the single
 * fetch + update entry point, an optimistic mutator updates the store
 * before the API round-trip resolves, and a BroadcastChannel pubsub
 * layer keeps peer tabs in sync without a ``page.reload()``.
 *
 * Pre-Plan-16 each ``PanelDomains`` mount (and each per-row expand)
 * fired its own ``configGet`` for ``domain_overrides``; opening the
 * Settings tab in two browser windows and flipping
 * ``domain_overrides.research.classify_model`` from one left the other
 * showing the prior value until reload. Plan 16 Task 43 / D32(b)
 * closes the class by wiring both reads through this store.
 *
 * Shape mirrors ``Config.domain_overrides`` (a ``dict[str,
 * DomainOverride]``). The four DomainOverride leaf fields per slug
 * mirror :class:`brain_core.config.schema.DomainOverride` 1:1:
 *
 *   - classify_model     — string | null
 *   - default_model      — string | null
 *   - temperature        — number (0..1.5) | null
 *   - max_output_tokens  — int (>0)       | null
 *
 * Note ``autonomous_mode`` is INTENTIONALLY excluded from
 * ``DomainOverride`` itself (Plan 12 D1 dropped the autonomy field —
 * autonomy is governed by per-category flags on
 * :class:`AutonomyCategoryFlags`, keyed under ``Config.autonomous``,
 * not here). The ``DomainOverrideForm`` UI carries an
 * ``autonomous_mode`` field for legacy parity but writes via a
 * different config key (``autonomous`` map). The store's
 * ``DomainOverrideEntry`` type matches the schema, not the form.
 *
 * In-flight serialization is a Promise cache (not a flag). Concurrent
 * ``refresh()`` calls share one Promise.
 */

// ---------- Types ----------

/** One slug's override entry. Mirrors
 *  :class:`brain_core.config.schema.DomainOverride` 1:1. Every field
 *  is ``null`` when no override is set ("fall back to global"). */
export interface DomainOverrideEntry {
  classify_model: string | null;
  default_model: string | null;
  temperature: number | null;
  max_output_tokens: number | null;
}

export const EMPTY_DOMAIN_OVERRIDE_ENTRY: DomainOverrideEntry = {
  classify_model: null,
  default_model: null,
  temperature: null,
  max_output_tokens: null,
};

/** Field names settable via ``setOverrideField``. Matches the
 *  on-disk shape; mirrors :class:`brain_core.config.schema.DomainOverride`. */
export type DomainOverrideField =
  | "classify_model"
  | "default_model"
  | "temperature"
  | "max_output_tokens";

// ---------- Store shape ----------

export interface DomainOverridesStoreState {
  /** Most recent ``Config.domain_overrides`` snapshot, indexed by
   *  slug. Empty until the first ``refresh()`` resolves. Slugs with
   *  no overrides are NOT present in the map (the backend prunes
   *  empty entries); selectors that want a default must coalesce. */
  overrides: Record<string, DomainOverrideEntry>;
  /** ``true`` once a ``refresh()`` has resolved at least once. */
  loaded: boolean;
  /** Last error from ``refresh()`` (or from a write the store
   *  proxies). ``null`` on success. */
  error: Error | null;

  /** Fetch the full ``Config.domain_overrides`` map and update the
   *  snapshot. Concurrent calls share one in-flight Promise. Resolves
   *  cleanly on failure (errors land on ``error``). */
  refresh: () => Promise<void>;
  /** Persist a single override leaf. Optimistic update + revert on
   *  failure. ``null`` clears the field (= "fall back to global");
   *  the backend prunes the slug entry once every field is null. */
  setOverrideField: (
    slug: string,
    field: DomainOverrideField,
    value: string | number | null,
  ) => Promise<void>;
  /** Test-only: reset the store to initial state + clear in-flight. */
  _resetForTesting: () => void;
}

// ---------- In-flight serialization ----------

let inFlightPromise: Promise<void> | null = null;

// ---------- Cross-tab pubsub (Plan 16 Task 43 / D32(b)) ----------

interface DomainOverridesBroadcastPayload {
  overrides: Record<string, DomainOverrideEntry>;
}

export const DOMAIN_OVERRIDES_BROADCAST_CHANNEL = "brain-domain-overrides";

let _isInternalUpdate = false;
let _channel: ChannelPubsub<DomainOverridesBroadcastPayload> | null = null;

function ensureChannel(): ChannelPubsub<DomainOverridesBroadcastPayload> {
  if (_channel) return _channel;
  _channel = createChannelPubsub<DomainOverridesBroadcastPayload>(
    DOMAIN_OVERRIDES_BROADCAST_CHANNEL,
    (data) => {
      _internalSet(data);
    },
  );
  return _channel;
}

function post(data: DomainOverridesBroadcastPayload): void {
  if (_isInternalUpdate) return;
  ensureChannel().post(data);
}

function _internalSet(data: DomainOverridesBroadcastPayload): void {
  _isInternalUpdate = true;
  try {
    useDomainOverridesStore.setState({ overrides: data.overrides });
  } finally {
    _isInternalUpdate = false;
  }
}

// ---------- Helpers ----------

/** Normalize one slug's wire-shape entry to ``DomainOverrideEntry``,
 *  filling missing fields with ``null``. The backend may omit fields
 *  that fall back to global; this keeps consumer code free of
 *  optional-chaining noise. */
function normalizeEntry(
  raw: Partial<DomainOverrideEntry> | undefined,
): DomainOverrideEntry {
  if (!raw) return { ...EMPTY_DOMAIN_OVERRIDE_ENTRY };
  return {
    classify_model: raw.classify_model ?? null,
    default_model: raw.default_model ?? null,
    temperature: raw.temperature ?? null,
    max_output_tokens: raw.max_output_tokens ?? null,
  };
}

function readOverrides(value: unknown): Record<string, DomainOverrideEntry> {
  if (value === null || typeof value !== "object") return {};
  const raw = value as Record<string, Partial<DomainOverrideEntry>>;
  const out: Record<string, DomainOverrideEntry> = {};
  for (const [slug, entry] of Object.entries(raw)) {
    out[slug] = normalizeEntry(entry);
  }
  return out;
}

// ---------- Store ----------

export const useDomainOverridesStore = create<DomainOverridesStoreState>(
  (set, get) => ({
    overrides: {},
    loaded: false,
    error: null,

    refresh: () => {
      if (inFlightPromise) return inFlightPromise;
      inFlightPromise = (async () => {
        try {
          const r = await configGet({ key: "domain_overrides" });
          const next = readOverrides(r.data?.value);
          set({ overrides: next, loaded: true, error: null });
          post({ overrides: next });
        } catch (err) {
          const error = err instanceof Error ? err : new Error(String(err));
          set({ error });
        } finally {
          inFlightPromise = null;
        }
      })();
      return inFlightPromise;
    },

    setOverrideField: async (slug, field, value) => {
      const before = get().overrides;
      const beforeEntry = before[slug] ?? { ...EMPTY_DOMAIN_OVERRIDE_ENTRY };
      // Compose the optimistic next entry. ``null`` for a field clears
      // the override; the backend prunes the slug entry server-side
      // once every field is null but we don't pre-prune here — the
      // refresh after a successful save reconciles either way and the
      // panel doesn't care whether the entry shows up as
      // ``{all-nulls}`` or "absent".
      const nextEntry: DomainOverrideEntry = {
        ...beforeEntry,
        [field]: value,
      } as DomainOverrideEntry;
      const nextOverrides: Record<string, DomainOverrideEntry> = {
        ...before,
        [slug]: nextEntry,
      };
      set({ overrides: nextOverrides, error: null });
      post({ overrides: nextOverrides });
      try {
        await configSet({
          key: `domain_overrides.${slug}.${field}`,
          value,
        });
      } catch (err) {
        // Revert — push the prior map back through, including the
        // broadcast so peer tabs that saw the optimistic update also
        // revert.
        const error = err instanceof Error ? err : new Error(String(err));
        set({ overrides: before, error });
        post({ overrides: before });
        throw error;
      }
    },

    _resetForTesting: () => {
      inFlightPromise = null;
      if (_channel) {
        _channel.close();
        _channel = null;
      }
      _isInternalUpdate = false;
      set({
        overrides: {},
        loaded: false,
        error: null,
      });
      ensureChannel();
    },
  }),
);

// Eagerly construct the channel at module load so peer tabs can
// deliver inbound updates before this tab has called ``post()`` for
// the first time. SSR-safe via the helper's
// ``typeof BroadcastChannel === "undefined"`` guard.
ensureChannel();
