/**
 * Shared deterministic-wait helpers for brain e2e specs.
 *
 * Plan 16 Task 19 (D19) — replace non-deterministic ``waitForTimeout(N)``
 * sleep beats with positive-signal waits (response, visibility, focus).
 * Lesson 343 production-shape replacement: every wait must be tied to a
 * real condition, not "pause N ms". Sleep beats hide races on slow CI
 * runners and pass on fast laptops; positive waits surface the same race
 * as a clear timeout failure with a stack trace pointing at the missing
 * signal.
 *
 * This file is the canonical home for cross-spec helpers. One-off
 * spec-local helpers (e.g. seedBrainMd, callTool) stay in their owning
 * spec until a second caller appears.
 */
import { type Page } from "@playwright/test";

/**
 * Deterministic wait for the first ``/api/tools/<toolName>`` response
 * after the call site. Drop-in replacement for the historical
 * ``waitForTimeout(N)`` beat used to ride out a mount-time tool fetch
 * race (Settings panels' ``configGet`` on mount, Browse's ``recent``,
 * etc.).
 *
 * Usage:
 *   const responsePromise = waitForToolResponse(page, "brain_config_get");
 *   await page.goto("/settings/general/");
 *   await responsePromise;
 *   // ... now safe to assert against fully-hydrated state
 *
 * Subscribe BEFORE triggering the action (``page.goto`` / click /
 * keystroke) — ``waitForResponse`` only matches responses received after
 * the wait Promise is registered.
 *
 * URL match is intentionally substring-based (no status filter): the
 * helper signals "the panel issued its mount-time fetch" rather than
 * "the fetch succeeded". Some legitimate flows return 404 for unset
 * config keys (the UI wraps the call in try/catch and treats missing
 * keys as default-empty); a status filter would silently miss those and
 * time out. A genuine auth / 5xx failure surfaces in axe results
 * downstream — we don't need the wait helper to gate on it.
 */
export async function waitForToolResponse(
  page: Page,
  toolName: string,
): Promise<void> {
  await page.waitForResponse((resp) =>
    resp.url().includes(`/api/tools/${toolName}`),
  );
}

/**
 * Deterministic wait for every CSS / Web-Animations animation on the
 * given element (and its descendants) to reach the ``finished`` state.
 *
 * Replaces the historical ``waitForTimeout(200)`` cushion used after a
 * Radix dialog/popover/overlay mount: the 200ms beat was load-bearing
 * because axe-core's color-contrast rule scans computed opacity, and
 * mid-animation an element can fail contrast even when its final state
 * passes (a fade-in transitions through low-opacity intermediate styles
 * that look "muddy" against the background).
 *
 * Implementation walks ``element.getAnimations({subtree: true})`` and
 * awaits ``Promise.all(animations.map(a => a.finished))``. The
 * ``Animation.finished`` Promise is the canonical "animation done"
 * signal in the Web Animations API; resolving it means every keyframe
 * timing has elapsed and the element is in its declared final style.
 *
 * Usage:
 *   await expect(dialog).toBeVisible();
 *   await waitForAnimationsToFinish(page, "[role=dialog]");
 *   await checkA11y(page, "dialog:foo");
 *
 * Selector form (rather than a Locator) keeps the helper trivial — we
 * resolve the element inside ``page.evaluate`` and don't have to round-
 * trip Locator handles across the wire.
 */
export async function waitForAnimationsToFinish(
  page: Page,
  selector: string,
): Promise<void> {
  await page.waitForFunction((sel: string) => {
    const el = document.querySelector(sel);
    if (!el) return false;
    const anims = (el as Element & {
      getAnimations?: (opts?: { subtree?: boolean }) => Animation[];
    }).getAnimations?.({ subtree: true });
    if (!anims || anims.length === 0) return true;
    // ``Animation.playState === "finished"`` is the synchronous
    // equivalent of ``await animation.finished`` and is poll-friendly.
    return anims.every((a) => a.playState === "finished");
  }, selector);
}
