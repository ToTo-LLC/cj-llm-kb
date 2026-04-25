"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAppStore, type ChatMode } from "@/lib/state/app-store";
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

// Stub domains; Task 14 replaces this with a live `listDomains()` query.
const STUB_DOMAINS = [
  { id: "research", label: "Research" },
  { id: "work", label: "Work" },
  { id: "personal", label: "Personal" },
];

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

  const [scopeOpen, setScopeOpen] = useState(false);

  const scopeLabel =
    scope.length === 0
      ? "No domain"
      : scope.length === STUB_DOMAINS.length
        ? "All domains"
        : scope.length === 1
          ? (STUB_DOMAINS.find((d) => d.id === scope[0])?.label ?? scope[0])
          : `${scope.length} domains`;

  function toggleDomain(id: string) {
    if (scope.includes(id)) setScope(scope.filter((x) => x !== id));
    else setScope([...scope, id]);
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
              {STUB_DOMAINS.map((d) => (
                <span
                  key={d.id}
                  className="h-1.5 w-1.5 rounded-full"
                  style={{
                    background: `var(--dom-${d.id})`,
                    opacity: scope.includes(d.id) ? 1 : 0.25,
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
          <ul className="flex flex-col">
            {STUB_DOMAINS.map((d) => {
              const checked = scope.includes(d.id);
              return (
                <li key={d.id}>
                  <label className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-[var(--surface-3)]">
                    <Checkbox
                      aria-label={d.label}
                      checked={checked}
                      onCheckedChange={() => toggleDomain(d.id)}
                    />
                    <span
                      aria-hidden
                      className="h-2 w-2 rounded-full"
                      style={{ background: `var(--dom-${d.id})` }}
                    />
                    <span>{d.label}</span>
                  </label>
                </li>
              );
            })}
          </ul>
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

      {/* Theme toggle */}
      <Button
        type="button"
        variant="ghost"
        size="sm"
        aria-label="Toggle theme"
        className="h-7 px-2 text-xs"
        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      >
        {theme === "dark" ? "Light" : "Dark"}
      </Button>

      {/* Rail toggle */}
      <Button
        type="button"
        variant="ghost"
        size="sm"
        aria-label="Toggle rail"
        className="h-7 px-2 text-xs"
        onClick={toggleRail}
      >
        Rail
      </Button>

      {/* Settings gear */}
      <Button asChild variant="ghost" size="sm" className="h-7 px-2 text-xs">
        <Link href="/settings" aria-label="Settings">
          Settings
        </Link>
      </Button>
    </header>
  );
}
