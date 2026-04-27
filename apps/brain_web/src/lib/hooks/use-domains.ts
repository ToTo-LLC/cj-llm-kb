"use client";

import * as React from "react";

import { listDomains } from "@/lib/api/tools";
import { ACCENT_SWATCHES } from "@/components/settings/domain-form";

/**
 * useDomains (Plan 10 Task 7).
 *
 * Module-level singleton cache around the ``brain_list_domains`` tool
 * so the topbar scope picker, the Browse file tree, and any future
 * settings views all share one fetch per session. Subsequent mounts
 * resolve immediately from the in-memory cache; an explicit
 * ``refresh()`` (or ``invalidateDomainsCache()`` for module-scope
 * invalidation) re-issues the call after a mutation
 * (``brain_create_domain`` / ``brain_rename_domain`` /
 * ``brain_delete_domain``).
 *
 * The domain list returned here is the *union* of ``Config.domains``
 * + on-disk slugs (matching ``brain_list_domains``'s response). The
 * UI cares about the union: a configured-but-empty domain should
 * still surface so the user can ingest into it; a discovered-on-
 * disk domain that's not configured shows up with a hint so the
 * user can either add it to Config.domains or move the data.
 */

export interface DomainEntry {
  slug: string;
  /** Humanised name for chrome — Title Case with separators replaced. */
  label: string;
  /** CSS color value — built-ins use a ``--dom-{slug}`` variable, user-
   *  added domains rotate through ``ACCENT_SWATCHES``. */
  accent: string;
  /** Listed in ``Config.domains``. */
  configured: boolean;
  /** A folder by this slug exists at the vault root. */
  on_disk: boolean;
}

const BUILTIN_SLUGS = new Set(["research", "work", "personal"]);

export function humaniseDomain(slug: string): string {
  // Title-Case + replace `-`/`_` with spaces. Mirrors what the
  // settings panel already does inline so labels are stable across
  // surfaces.
  return slug
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part[0]!.toUpperCase() + part.slice(1))
    .join(" ");
}

function accentFor(slug: string, userIndex: number): string {
  if (BUILTIN_SLUGS.has(slug)) {
    return `var(--dom-${slug})`;
  }
  return ACCENT_SWATCHES[userIndex % ACCENT_SWATCHES.length] ?? "#6A8CAA";
}

interface RawListDomainsEntry {
  slug: string;
  configured: boolean;
  on_disk: boolean;
}

function entriesFromResponse(
  data: { domains?: string[]; entries?: RawListDomainsEntry[] } | null | undefined,
): DomainEntry[] {
  if (!data) return [];
  // Prefer the new ``entries`` array (Plan 10 Task 5) so we get the
  // configured/on_disk flags. Fall back to the legacy ``domains``
  // string-list if the backend is older — assumes both flags True.
  const raw: RawListDomainsEntry[] =
    data.entries && Array.isArray(data.entries)
      ? data.entries
      : (data.domains ?? []).map((slug) => ({
          slug,
          configured: true,
          on_disk: true,
        }));

  let userIdx = 0;
  return raw.map((r) => {
    const isBuiltin = BUILTIN_SLUGS.has(r.slug);
    const accent = accentFor(r.slug, isBuiltin ? 0 : userIdx);
    if (!isBuiltin) userIdx += 1;
    return {
      slug: r.slug,
      label: humaniseDomain(r.slug),
      accent,
      configured: r.configured,
      on_disk: r.on_disk,
    };
  });
}

let cachedPromise: Promise<DomainEntry[]> | null = null;

function fetchDomains(): Promise<DomainEntry[]> {
  if (cachedPromise) return cachedPromise;
  cachedPromise = listDomains()
    .then((r) => entriesFromResponse(r.data ?? null))
    .catch((err: unknown) => {
      // Drop the failed promise so the next subscriber retries.
      cachedPromise = null;
      throw err;
    });
  return cachedPromise;
}

/** Invalidate the module-level cache so the next call re-fetches.
 *  Use this after ``brain_create_domain`` / ``brain_rename_domain``
 *  / ``brain_delete_domain`` so other surfaces see the change. */
export function invalidateDomainsCache(): void {
  cachedPromise = null;
}

/** Reset the cache to the given entries. Used by tests. */
export function _setDomainsCacheForTesting(entries: DomainEntry[] | null): void {
  cachedPromise = entries === null ? null : Promise.resolve(entries);
}

export interface UseDomainsResult {
  domains: DomainEntry[];
  loading: boolean;
  error: Error | null;
  /** Force-refetch (also invalidates the module cache so peers re-read). */
  refresh: () => void;
}

export function useDomains(): UseDomainsResult {
  const [domains, setDomains] = React.useState<DomainEntry[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<Error | null>(null);
  // Bumping ``tick`` forces a re-fetch by triggering the effect
  // below. Used by ``refresh()``.
  const [tick, setTick] = React.useState(0);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchDomains()
      .then((entries) => {
        if (cancelled) return;
        setDomains(entries);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err : new Error(String(err)));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  const refresh = React.useCallback(() => {
    invalidateDomainsCache();
    setTick((t) => t + 1);
  }, []);

  return { domains, loading, error, refresh };
}
