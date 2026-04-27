"use client";

import { cn } from "@/lib/utils";

export type ThemeKey = "research" | "work" | "personal" | "blank";

export interface ThemeOption {
  key: ThemeKey;
  label: string;
  desc: string;
  swatch: string; // Tailwind background class (theme token-derived).
}

/** Ordered list — also drives the tab-order for keyboard navigation. */
export const THEME_OPTIONS: ThemeOption[] = [
  {
    key: "research",
    label: "Research",
    desc: "reading · papers",
    swatch: "bg-cyan-400",
  },
  {
    key: "work",
    label: "Work",
    desc: "calls · deals",
    swatch: "bg-emerald-400",
  },
  {
    key: "personal",
    label: "Personal",
    desc: "journal · ideas",
    swatch: "bg-orange-400",
  },
  {
    key: "blank",
    label: "Blank",
    desc: "start empty",
    swatch: "bg-muted-foreground",
  },
];

export interface StartingThemeStepProps {
  pick: ThemeKey;
  onPick: (key: ThemeKey) => void;
}

/**
 * Starting-theme step (4 / 6). Four picker cards — one auto-applies a
 * `<slug>/index.md` welcome note when the user advances (see `Wizard`
 * `handleNext`). "Blank" skips the seed entirely.
 */
export function StartingThemeStep({ pick, onPick }: StartingThemeStepProps) {
  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-medium tracking-tight">
        Pick a starting theme.
      </h1>
      <p className="text-base leading-relaxed text-muted-foreground">
        We&apos;ll seed your first domain with a welcome note. You can add
        more anytime.
      </p>
      <div
        role="radiogroup"
        aria-label="Starting theme"
        className="grid grid-cols-2 gap-3 pt-2 sm:grid-cols-4"
      >
        {THEME_OPTIONS.map((opt) => {
          const selected = pick === opt.key;
          // Issue #42: split the accessible name from the description.
          // Plan-09 QA sweep flagged that screen readers announced this
          // card as ``"Research reading · papers"`` because all three
          // text spans concatenated into the computed accessible name.
          // The fix is the standard WAI-ARIA "card as button" pattern:
          // ``aria-labelledby`` points at the title span (the most
          // distinguishing identifier) and ``aria-describedby`` points
          // at the description span. Result: ``"Research, radio,
          // checked, reading · papers"``.
          const labelId = `theme-label-${opt.key}`;
          const descId = `theme-desc-${opt.key}`;
          return (
            <button
              key={opt.key}
              type="button"
              role="radio"
              aria-checked={selected}
              aria-labelledby={labelId}
              aria-describedby={descId}
              onClick={() => onPick(opt.key)}
              className={cn(
                "flex flex-col items-start gap-2 rounded-lg border bg-background p-4 text-left transition-colors",
                "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                selected
                  ? "border-primary ring-1 ring-primary"
                  : "border-input hover:border-muted-foreground",
              )}
            >
              <span
                aria-hidden="true"
                className={cn(
                  "inline-block h-4 w-4 rounded-full opacity-85",
                  opt.swatch,
                )}
              />
              <span id={labelId} className="text-sm font-medium">
                {opt.label}
              </span>
              <span id={descId} className="text-xs text-muted-foreground">
                {opt.desc}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
