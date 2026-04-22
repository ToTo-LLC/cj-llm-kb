/**
 * URL / paste ingest helpers (Plan 07 Task 17).
 *
 * Two pure pieces + one listener installer:
 *   1. ``shouldIngest(text)`` — the noise filter. Accept any URL; accept
 *      plain text over 50 chars. Reject everything shorter (tiny
 *      fragments are usually accidental copy-paste noise).
 *   2. ``triggerIngest(text)`` — the action. Forwards the text to
 *      ``brain_ingest`` via the typed tool binding. Never throws in
 *      practice — errors are bubbled to the caller (AppShell) so they
 *      can render a toast.
 *   3. ``installPasteListener(handler)`` — registers a document-level
 *      ``paste`` listener; returns the matching unregister function.
 *      The paste listener itself stays thin (DOM reads only) so the
 *      interesting logic lives in the two pure helpers above and can be
 *      tested without a real DOM event. Playwright (Task 23) covers the
 *      glue.
 */

import { ingest } from "@/lib/api/tools";

/** Minimum char count required to treat a plain-text paste as ingestible. */
export const MIN_INGEST_TEXT_LENGTH = 50;

const URL_RE = /^https?:\/\/\S+/i;

export function isUrl(text: string): boolean {
  return URL_RE.test(text.trim());
}

/**
 * Return true iff the pasted text is worth sending to the ingest
 * pipeline. URLs always qualify; plain text has to clear
 * ``MIN_INGEST_TEXT_LENGTH`` — shorter snippets are assumed accidental.
 */
export function shouldIngest(text: string): boolean {
  if (typeof text !== "string") return false;
  const trimmed = text.trim();
  if (!trimmed) return false;
  if (isUrl(trimmed)) return true;
  return trimmed.length > MIN_INGEST_TEXT_LENGTH;
}

/**
 * Fire-and-forget call into ``brain_ingest`` with the pasted text as
 * the source. The promise resolves with the typed tool response so the
 * caller can, e.g., attach the returned ``patch_id`` to a chat turn.
 */
export async function triggerIngest(
  text: string,
): ReturnType<typeof ingest> {
  return ingest({ source: text.trim() });
}

/** Payload handed to the paste-listener callback. */
export interface PasteDetection {
  /** The trimmed pasted text. */
  text: string;
  /** True when the text matched the URL pattern. */
  isUrl: boolean;
}

/**
 * Register a document-level ``paste`` listener on the current tab.
 *
 * The listener:
 *   - ignores paste events originating inside a ``<textarea>`` or
 *     ``<input>`` (those are composer inputs — default paste wins);
 *   - calls ``shouldIngest`` to filter noise;
 *   - invokes ``handler`` with the detection payload when accepted.
 *
 * Returns a cleanup function suitable for ``useEffect`` teardown. The
 * listener itself stays off the unit-test path per the plan's testing
 * note — Playwright covers it in Task 23.
 */
export function installPasteListener(
  handler: (p: PasteDetection) => void,
): () => void {
  if (typeof document === "undefined") return () => undefined;
  const onPaste = (ev: ClipboardEvent) => {
    const active = document.activeElement;
    const tag = active?.tagName;
    if (tag === "TEXTAREA" || tag === "INPUT") return;
    const text = ev.clipboardData?.getData("text/plain") ?? "";
    if (!shouldIngest(text)) return;
    handler({ text: text.trim(), isUrl: isUrl(text) });
  };
  document.addEventListener("paste", onPaste);
  return () => document.removeEventListener("paste", onPaste);
}
