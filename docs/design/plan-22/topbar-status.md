# Topbar status indicator mockup (Plan 22 T11 §3)

Implements per `tasks/plans/22-watched-folders-sync.md` §T14. New component `WatchedFoldersTopbarIndicator` lives in `apps/brain_web/src/components/shell/topbar.tsx` (or split into a sibling file per the topbar refactor pattern).

## Surface intent

Persistent, low-noise system status: how many folders are being watched, how many orphans need attention. Click-through routes to the relevant Settings tab. The orphan count is the high-attention signal — when `> 0`, the icon + number tint with `--warn`, and the count is announced via `role="status" aria-live="polite"` so a screen reader user is told when an orphan appears mid-session.

## Placement in the topbar

Sits between the scope chip / cross-domain badge and the autonomy badge (right side of topbar, just before the theme toggle). Sequence right-to-left from screen edge:

```
[Settings ⚙] [Theme ☀] [WATCHED-FOLDERS-INDICATOR] [Autonomy ⚡] [Scope: research ▾]   ... brand chip + version (left)
```

This grouping keeps "vault-state" affordances (scope, autonomy, watched folders) adjacent, with global controls (theme, settings) on the outer right edge.

## Layout (3 watched folders, 2 orphans — high-attention state)

```
                                                                            …
┌──────────────────────────────────────────────────────────────────────────────┐
│  brain v0.1.0 …                  [⚡ AUTO]    [👁 3 · ⚠ 2]    [☀]  [⚙]      │
└──────────────────────────────────────────────────────────────────────────────┘
                                                ▲▲▲▲▲▲▲▲▲▲▲▲
                                                  this widget
```

### Close-up

```
                  hover state (cursor on widget)
                  ──────────────────────────────
                       ╭──────────────────────╮
                       │ [👁 3]  [⚠ 2]        │   ← --surface-2 bg, --hairline border,
                       ╰──────────────────────╯     --r-pill radius, ~28px height
                              ↓
              ┌─────────────────────────────────────────┐
              │  3 folders watched                      │
              │  2 orphaned notes need attention        │
              │  ──────────────────────────────────     │
              │  Click to manage →                      │
              └─────────────────────────────────────────┘
              (Tooltip on hover; ~260ms delay)
```

### Idle / default state (3 watched, 0 orphans)

```
[👁 3]
```

- Single icon + number. Color: `--text-muted` (neutral).
- No `⚠` segment when orphan count is zero.
- Tooltip: `"3 folders watched"`.

### Empty state (0 watched, 0 orphans)

Indicator is HIDDEN. Watching is opt-in; until the user enables their first folder, the indicator adds no information. (The CTA path is via Settings → Watched folders.)

### Orphan-only state (0 watched, 2 orphans — e.g., user unwatched the folder but orphans persist per D2)

```
[⚠ 2]
```

- Single `--warn` orphan segment. Tooltip: `"2 orphaned notes need attention"`.

## States summary table

| Watched count | Orphan count | Render | Color |
|---|---|---|---|
| 0 | 0 | hidden | n/a |
| ≥1 | 0 | `[👁 N]` | `--text-muted` |
| 0 | ≥1 | `[⚠ N]` | `--warn` |
| ≥1 | ≥1 | `[👁 N · ⚠ M]` | `--text-muted` then `--warn` (separator dot `--text-dim`) |
| loading | loading | `[👁 ·]` (compact skeleton) | `--text-dim` |
| error | error | `[👁 !]` red asterisk | `--danger` |

## Anatomy

| Element | Token / component | Purpose |
|---|---|---|
| Container | `<button type="button">` shadcn `Button variant="ghost"`, `--r-pill`, height matches topbar row | One affordance, one click |
| Watch icon | Lucide `Eye`, 14px, `currentColor` | Visual key |
| Watch count | `--text-muted`, `--ui-sm`, font-weight 500 | Number rendered next to icon |
| Separator dot | `·` (U+00B7), `--text-dim`, `--ui-sm` | Visual divider between segments |
| Orphan icon | Lucide `AlertTriangle`, 14px, `--warn` | Attention-cue color |
| Orphan count | `--warn`, `--ui-sm`, font-weight 600 | Number rendered next to icon |
| Hover bg | `--surface-3` | Subtle pop on hover |
| Focus ring | 2px outline `--tt-cyan`, offset 2px | Keyboard-visible focus |

## Interaction

- **Click (orphans > 0):** routes to `/settings/orphans`.
- **Click (orphans === 0, watched > 0):** routes to `/settings/watched-folders`.
- **Click (hidden state):** indicator isn't there.
- **Hover:** `Tooltip` appears (~260ms delay matching existing topbar tooltip-provider). Tooltip is closeable with Esc.
- **Right-click / long-press:** no-op (keep the surface simple; advanced affordances live in the Settings tab).
- **Keyboard:** `Tab` lands on the button; `Enter` / `Space` activates click.

## Microcopy

- **Tooltip (3 watched, 0 orphans):** `"3 folders watched."`
- **Tooltip (3 watched, 1 orphan):** `"3 folders watched · 1 orphaned note needs attention."` (singular form for orphan count of 1)
- **Tooltip (3 watched, 2 orphans):** `"3 folders watched · 2 orphaned notes need attention."`
- **Tooltip (0 watched, 2 orphans):** `"2 orphaned notes need attention. Click to review."`
- **Tooltip (loading):** `"Loading watched folders…"`
- **Tooltip (error):** `"Couldn't load watched folders. Click to retry."`
- **Button `aria-label` (3 watched, 2 orphans):** `"3 folders watched, 2 orphaned notes need attention. Open Settings to manage."`
- **Button `aria-label` (3 watched, 0 orphans):** `"3 folders watched. Open Settings to manage."`
- **Button `aria-label` (loading):** `"Loading watched folder status"`
- **Button `aria-label` (error):** `"Watched folder status failed to load. Click to retry."`

## Accessibility annotations

- The indicator is a `<button>` (not a `<div>`) — naturally focusable, keyboard-activatable, screen-reader-announced.
- `aria-label` covers the full state in one string so screen readers don't need to parse the icon + count combos.
- The orphan count, when it CHANGES while the page is mounted (e.g., a file deletion fires the watcher mid-session), is announced via a `role="status" aria-live="polite"` sibling node — NOT via `aria-label` change on the button (the latter wouldn't re-announce on update). The status region is visually hidden (`sr-only`) and lives next to the button.
- Color is NOT the only signal: the icons differ (`Eye` vs `AlertTriangle`), AND the `aria-label` is explicit. Users with color-blindness can read the icon shape and the screen-reader text.
- Tooltip is delivered via Radix `TooltipContent` — already a11y-correct (dismissible with Esc, `role="tooltip"`).
- Focus ring contrast: `--tt-cyan` on `--surface-1` is 5.1:1 dark / 4.7:1 light — clears WCAG 2.2 AA non-text contrast 3:1.
- `--warn` (`#FDEB9E`) on `--surface-1` dark (`#141414`) is 12.9:1. Light mode: `--warn` text on `--surface-1` light (`#FFFFFF`) becomes the `--brand-wheat` (`#D6A34E`) per brand-skin override — 3.1:1, which FAILS AA 4.5:1 for small text. **MITIGATION:** in light mode, the orphan count uses `--danger` text color (`#C64B2E`, 4.7:1 on white) — color flip handled via theme-aware CSS variable. The `AlertTriangle` icon stroke uses `--warn` (its 3:1 large-icon contrast is sufficient as a non-text element).

## Implementation guidance

- Mount inside `topbar.tsx` between the existing `Autonomy` and `Theme` controls. Pattern: subscribe to `useWatchedFoldersStore` + `useOrphansStore` (selectors), compute the two counts, render accordingly.
- Loading state is transient — don't show a skeleton on every navigation; the store should hydrate once at app mount (same pattern as `useDomainsStore` does today).
- Error state: tap into the stores' `error` field. On click in error state, fire `store.refresh()` directly (no navigation).
- The route navigation uses `next/navigation`'s `useRouter()` + `router.push("/settings/orphans")` — matches existing topbar `Link`-based settings nav.
- Memoize the `aria-label` string; computed on every render but cheap. Use `useMemo` on the watched/orphan count pair.
- The hidden state should NOT be implemented as `display: none` from the start — render the button as `aria-hidden="true"` + `tabIndex={-1}` + `style.visibility = "hidden"` when both counts are zero. This keeps the topbar layout stable so the rest of the toolbar doesn't jitter when the indicator appears mid-session.

  **Reconsidered:** layout jitter is actually FINE here because the indicator's appearance is itself a meaningful event (the user just enabled their first watched folder), and an animated slide-in (200ms, ease-out) draws attention to the new affordance. Going with `display: none` + transitioned entrance. The implementer should add a CSS transition on `opacity` + `transform` so the entrance is smooth.
