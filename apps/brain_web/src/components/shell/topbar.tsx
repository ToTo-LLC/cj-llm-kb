"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";
import { Sun, Moon, PanelRight, Settings as SettingsIcon, Star } from "lucide-react";

import {
  useAppStore,
  readScopeInitialized,
  type ChatMode,
} from "@/lib/state/app-store";
import { useDomains } from "@/lib/hooks/use-domains";
import { useDomainsStore } from "@/lib/state/domains-store";
import { useSystemStore } from "@/lib/state/system-store";
import { setActiveDomain } from "@/lib/api/tools";
import { useBootstrap } from "@/lib/bootstrap/bootstrap-context";
import { Button } from "@/components/ui/button";
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/components/ui/toggle-group";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { ConnectionIndicator } from "@/components/system/connection-indicator";

// Version surfaced in the topbar's brand chip. Sourced verbatim from the
// monorepo's shipped tag (``v0.1.0``); update when cutting a new release.
const APP_VERSION = "0.1.0";

function pathToView(pathname: string | null): string {
  if (!pathname) return "chat";
  const seg = pathname.split("/").filter(Boolean)[0] ?? "chat";
  return seg;
}

export function Topbar() {
  const pathname = usePathname();
  const view = pathToView(pathname);
  const showModeSwitch = view === "chat";

  const theme = useAppStore((s) => s.theme);
  const setTheme = useAppStore((s) => s.setTheme);
  const mode = useAppStore((s) => s.mode);
  const setMode = useAppStore((s) => s.setMode);
  const scope = useAppStore((s) => s.scope);
  const setScope = useAppStore((s) => s.setScope);
  const toggleRail = useAppStore((s) => s.toggleRail);
  const scopeInitialized = useAppStore((s) => s.scopeInitialized);
  const markScopeInitialized = useAppStore((s) => s.markScopeInitialized);
  const loadScopeInitializedFor = useAppStore(
    (s) => s.loadScopeInitializedFor,
  );

  const [scopeOpen, setScopeOpen] = React.useState(false);

  // Plan 10 Task 7: live domain list (Config.domains ∪ on-disk).
  // Renders as `[]` while the first fetch is in-flight; the topbar's
  // dot row stays empty until the response lands rather than
  // briefly painting the v0.1 stub triple. Plan 11 Task 8 added
  // ``activeDomain`` here for the first-mount scope hydration below.
  const { domains: liveDomains, activeDomain } = useDomains();

  // Plan 11 Task 8 — bootstrap context exposes the resolved vault path,
  // which keys the per-vault ``brain.scopeInitialized.<vault>``
  // localStorage flag. Topbar may render before the bootstrap fetch
  // finishes (vaultPath === null) — guard the hydration effect on a
  // truthy path so we never persist a flag against the empty key.
  const { vaultPath } = useBootstrap();

  // Plan 11 Task 8 — rehydrate the in-memory ``scopeInitialized``
  // mirror from the per-vault localStorage flag once the vault path is
  // known. Lives in its own effect so the hydration effect below can
  // bail purely on the in-memory mirror without touching localStorage
  // every render. Re-runs when ``vaultPath`` changes (different vault
  // → different key → different stored value).
  React.useEffect(() => {
    if (!vaultPath) return;
    loadScopeInitializedFor(vaultPath);
  }, [vaultPath, loadScopeInitializedFor]);

  // Plan 11 Task 8 / D8 — first-mount scope hydration.
  //
  // On a fresh localStorage (``scopeInitialized=false``) AND a resolved
  // domain list, hydrate ``scope = [activeDomain]`` then flip the flag.
  // Subsequent mounts skip this branch and read scope from app-store as
  // today. Effect is idempotent: once ``markScopeInitialized()`` flips
  // the flag, the early-return gate keeps it from re-firing even though
  // ``setScope`` is in the dep list (which would otherwise cycle since
  // a new scope value invalidates the closure).
  //
  // Fallback path: if ``activeDomain`` isn't in the live domain list
  // (rare race — user changed ``active_domain`` in another window then
  // deleted that domain before this mount finished hydrating), fall
  // back to the first non-``personal`` slug, or the first slug overall
  // if every slug is privacy-railed (theoretically impossible per
  // Config validators, but the fallback keeps the UI from rendering
  // an empty scope on the edge case).
  React.useEffect(() => {
    if (scopeInitialized) return;
    if (!vaultPath) return;
    if (liveDomains.length === 0) return;
    if (!activeDomain) return;
    // Cross-effect race guard: the sibling ``loadScopeInitializedFor``
    // effect runs in the same commit cycle as this one. If the
    // durable per-vault flag is set, that effect WILL flip the mirror
    // — but its store ``set()`` hasn't propagated to the closure
    // ``scopeInitialized`` here yet. Read the durable flag directly
    // to short-circuit before clobbering the user's persisted scope
    // on a vault that's already been hydrated. (Matches the ``D8``
    // guarantee: each vault hydrates exactly once.)
    if (readScopeInitialized(vaultPath)) return;

    const inLive = liveDomains.some((d) => d.slug === activeDomain);
    const target = inLive
      ? activeDomain
      : (liveDomains.find((d) => d.slug !== "personal")?.slug ??
          liveDomains[0]!.slug);

    if (!inLive) {
      // eslint-disable-next-line no-console -- diagnostic for the rare
      // race where active_domain isn't in the live list. Surfacing this
      // helps the user (or the devtools console) see why scope didn't
      // match their settings choice.
      console.warn(
        `[brain] active_domain "${activeDomain}" not in live domain list; falling back to "${target}"`,
      );
    }

    setScope([target]);
    markScopeInitialized(vaultPath);
  }, [
    scopeInitialized,
    liveDomains,
    activeDomain,
    vaultPath,
    setScope,
    markScopeInitialized,
  ]);

  // Plan 10 Task 7 prune: drop persisted scope slugs that aren't in
  // the live list anymore. Without this, deleting a domain in
  // settings would leave a dangling chip in the scope picker that
  // toggles a slug the rest of the app no longer routes to.
  //
  // Plan 11 Task 8 caveat: skip the prune until first-mount hydration
  // has run. Otherwise the prune sees ``scope === []`` and is a no-op,
  // but worse, on a vault-switch the prune could fire before hydration
  // and leave the scope empty even though the new vault has a valid
  // ``active_domain``. The hydration effect above is the single source
  // of truth for the post-hydration scope baseline.
  React.useEffect(() => {
    if (!scopeInitialized) return;
    if (liveDomains.length === 0) return;
    const liveSet = new Set(liveDomains.map((d) => d.slug));
    const pruned = scope.filter((s) => liveSet.has(s));
    if (pruned.length !== scope.length) {
      setScope(pruned);
    }
  }, [scopeInitialized, liveDomains, scope, setScope]);

  const scopeLabel =
    scope.length === 0
      ? "No domain"
      : scope.length === liveDomains.length && liveDomains.length > 0
        ? "All domains"
        : scope.length === 1
          ? (liveDomains.find((d) => d.slug === scope[0])?.label ?? scope[0])
          : `${scope.length} domains`;

  function toggleDomain(slug: string) {
    if (scope.includes(slug)) setScope(scope.filter((x) => x !== slug));
    else setScope([...scope, slug]);
  }

  // Plan 16 Task 42 — "Set as default" per-row action.
  //
  // Mirrors the optimistic-update + revert-on-failure shape from
  // ``settings/panel-domains-active.tsx``: the topbar surfaces the
  // same ``Config.active_domain`` mutation, just from the chrome
  // instead of the Settings panel. Calling
  // ``useDomainsStore.setActiveDomainOptimistic`` ensures peer
  // consumers (the Settings dropdown, future surfaces) re-render
  // immediately rather than waiting for a ``refresh()``.
  //
  // Errors revert to the previous slug + emit a danger toast. We
  // don't classify the error here (validator vs. transport) the
  // way panel-domains-active does — the topbar's available
  // domains are exactly what the dropdown shows, so a 400 from
  // the cross-field validator is a near-impossible cross-tab race
  // and the simpler copy ("Could not set default") suffices.
  async function handleSetDefault(slug: string): Promise<void> {
    if (slug === activeDomain) return;
    const previous = activeDomain;
    useDomainsStore.getState().setActiveDomainOptimistic(slug);
    try {
      await setActiveDomain(slug);
      useSystemStore.getState().pushToast({
        lead: "Default updated.",
        msg: `Default domain set to ${slug}.`,
        variant: "success",
      });
    } catch {
      useDomainsStore.getState().setActiveDomainOptimistic(previous);
      useSystemStore.getState().pushToast({
        lead: "Couldn't update default.",
        msg: `Could not set default to ${slug}. Try again.`,
        variant: "danger",
      });
    }
  }

  return (
    <header
      className="topbar flex items-center gap-3 border-b border-[var(--hairline)] bg-[var(--surface-1)] px-4 text-[var(--text)]"
      data-view={view}
    >
      {/* Brand block — v4 brand-mark (outline circle + ember dot + connector
          line) plus serif italic ``brain.`` wordmark with ember period and a
          mono version chip. Class names match the brand-skin.css selectors
          (.topbar .brand, .brand-mark, .brand .name .wm, .brand .name .ver,
          .brand .name .wm .dot) so the v4 typography + ember accent flow
          through the skin layer. */}
      <div className="brand">
        <svg
          className="brand-mark"
          viewBox="0 0 120 120"
          fill="none"
          stroke="currentColor"
          aria-hidden="true"
        >
          <circle cx="36" cy="60" r="20" strokeWidth="6" />
          <circle
            cx="84"
            cy="60"
            r="10"
            fill="var(--brand-ember)"
            stroke="none"
          />
          <line
            x1="56"
            y1="60"
            x2="74"
            y2="60"
            strokeWidth="6"
            strokeLinecap="round"
          />
        </svg>
        <div className="name">
          <span className="wm">
            brain<span className="dot">.</span>
          </span>
          <span className="ver">v{APP_VERSION}</span>
        </div>
      </div>

      <div aria-hidden className="h-5 w-px bg-[var(--hairline)]" />

      {/* Scope picker */}
      <Popover open={scopeOpen} onOpenChange={setScopeOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            aria-label={`Scope: ${scopeLabel}`}
            className="h-7 gap-2 text-xs"
          >
            <span aria-hidden className="flex items-center gap-0.5">
              {liveDomains.map((d) => (
                <span
                  key={d.slug}
                  className="h-1.5 w-1.5 rounded-full"
                  style={{
                    background: d.accent,
                    opacity: scope.includes(d.slug) ? 1 : 0.25,
                  }}
                />
              ))}
            </span>
            <span>{scopeLabel}</span>
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-64 p-2">
          <div className="mb-1 px-2 text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
            Visible domains
          </div>
          {liveDomains.length === 0 ? (
            <div className="px-2 py-1.5 text-xs text-[var(--text-dim)]">
              Loading domains…
            </div>
          ) : (
            <ul className="flex flex-col">
              {liveDomains.map((d) => {
                const checked = scope.includes(d.slug);
                const isDefault = d.slug === activeDomain;
                return (
                  <li key={d.slug}>
                    <label className="group flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-[var(--surface-3)]">
                      <Checkbox
                        aria-label={d.label}
                        checked={checked}
                        onCheckedChange={() => toggleDomain(d.slug)}
                      />
                      <span
                        aria-hidden
                        className="h-2 w-2 rounded-full"
                        style={{ background: d.accent }}
                      />
                      <span className="flex-1">{d.label}</span>
                      {/* Plan 16 Task 42 — per-row "Set as default"
                          action. The active row shows a static filled
                          star + "Default" SR-only label. Other rows
                          show a hover-revealed outline-star button that
                          promotes the domain to ``Config.active_domain``.
                          The wrapping <span> stops both
                          ``onClick`` and ``onPointerDown`` from
                          reaching the parent <label>; without
                          ``onPointerDown`` Radix's checkbox would
                          still toggle on the pointer-down phase even
                          though the click handler bails. */}
                      {isDefault ? (
                        <span
                          className="text-[var(--brand-ember)]"
                          title="Default domain"
                        >
                          <Star
                            aria-hidden
                            className="h-3.5 w-3.5 fill-current"
                          />
                          <span className="sr-only">Default</span>
                        </span>
                      ) : (
                        <span
                          onClick={(e) => e.stopPropagation()}
                          onPointerDown={(e) => e.stopPropagation()}
                        >
                          <button
                            type="button"
                            aria-label={`Set ${d.label} as default`}
                            title={`Set ${d.label} as default`}
                            onClick={() => void handleSetDefault(d.slug)}
                            className="rounded-sm p-0.5 text-[var(--text-muted)] opacity-0 transition-opacity hover:text-[var(--brand-ember)] focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--ring,_currentColor)] group-hover:opacity-100"
                          >
                            <Star className="h-3.5 w-3.5" />
                          </button>
                        </span>
                      )}
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
        </PopoverContent>
      </Popover>

      {/* Mode switcher (chat view only) */}
      {showModeSwitch && (
        <>
          <div aria-hidden className="h-5 w-px bg-[var(--hairline)]" />
          <ToggleGroup
            type="single"
            value={mode}
            onValueChange={(v) => {
              if (v) setMode(v as ChatMode);
            }}
            aria-label="Chat mode"
            size="sm"
          >
            <ToggleGroupItem value="ask" className="h-7 px-3 text-xs">
              Ask
            </ToggleGroupItem>
            <ToggleGroupItem value="brainstorm" className="h-7 px-3 text-xs">
              Brainstorm
            </ToggleGroupItem>
            <ToggleGroupItem value="draft" className="h-7 px-3 text-xs">
              Draft
            </ToggleGroupItem>
          </ToggleGroup>
        </>
      )}

      <div className="flex-1" />

      {/* Connection pip — hidden when WS is "ok" (Plan 07 Task 12). */}
      <ConnectionIndicator />

      {/* Theme / Rail / Settings — iconified per the v4 mockup. Sun
          shown when theme is dark (click → light), Moon when light
          (click → dark). PanelRight icon toggles the right-rail open
          state. SettingsIcon (gear) deep-links to /settings. The
          aria-label keeps the action discoverable for screen readers
          and keyboard nav even with the text-free chrome. */}
      <Button
        type="button"
        variant="ghost"
        size="sm"
        aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
        title={theme === "dark" ? "Light" : "Dark"}
        className="h-7 w-7 p-0"
        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      >
        {theme === "dark" ? (
          <Sun className="h-4 w-4" aria-hidden="true" />
        ) : (
          <Moon className="h-4 w-4" aria-hidden="true" />
        )}
      </Button>

      <Button
        type="button"
        variant="ghost"
        size="sm"
        aria-label="Toggle right rail"
        title="Right rail"
        className="h-7 w-7 p-0"
        onClick={toggleRail}
      >
        <PanelRight className="h-4 w-4" aria-hidden="true" />
      </Button>

      <Button asChild variant="ghost" size="sm" className="h-7 w-7 p-0">
        <Link href="/settings" aria-label="Settings" title="Settings">
          <SettingsIcon className="h-4 w-4" aria-hidden="true" />
        </Link>
      </Button>
    </header>
  );
}
