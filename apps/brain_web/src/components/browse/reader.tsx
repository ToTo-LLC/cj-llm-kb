"use client";

import * as React from "react";

import { renderNote } from "@/lib/chat/rendering";
import { BROKEN_WIKILINKS } from "@/lib/chat/rendering";
import { WIKILINK_HOVER_ID } from "./wikilink-hover";

/**
 * Reader (Plan 07 Task 18; a11y-hardened in Plan 16 Task 11).
 *
 * Reads frontmatter + body pulled from ``brain_read_note`` and
 * renders:
 *   - A collapsed frontmatter strip at the top (``fm`` list of
 *     key / value rows, with wikilink rendering for ``links:``).
 *   - The full body via ``renderNote`` (block-level markdown).
 *
 * Keeps wikilink hover orthogonal — hover handlers come from a
 * parent via the ``onWikilinkEnter`` / ``onWikilinkLeave`` props.
 * The reader just forwards them to the rendered anchors via a
 * delegated mouseover.
 *
 * Plan 16 Task 11 (a11y): keyboard parity — focus/blur dispatch the
 * same enter/leave callbacks as mouseover, AND the trigger anchor
 * receives ``aria-describedby="wikilink-hover-tooltip"`` while the
 * pointer / focus is on it so screen readers tie the tooltip to the
 * link they're inspecting.
 */

export interface ReaderProps {
  title: string;
  frontmatter: Record<string, unknown>;
  body: string;
  onWikilinkEnter?: (label: string, anchor: HTMLAnchorElement) => void;
  onWikilinkLeave?: () => void;
}

export function Reader({
  title,
  frontmatter,
  body,
  onWikilinkEnter,
  onWikilinkLeave,
}: ReaderProps): React.ReactElement {
  const enterAnchor = React.useCallback(
    (anchor: HTMLAnchorElement) => {
      const label = anchor.textContent ?? "";
      if (BROKEN_WIKILINKS.has(label)) return;
      // Plan 16 Task 11 a11y: stamp ``aria-describedby`` so the tooltip
      // is announced as the description of the link the user is on.
      // Removed in ``leaveAnchor`` so stale ids don't accumulate.
      anchor.setAttribute("aria-describedby", WIKILINK_HOVER_ID);
      onWikilinkEnter?.(label, anchor);
    },
    [onWikilinkEnter],
  );

  const leaveAnchor = React.useCallback(
    (anchor: HTMLAnchorElement) => {
      anchor.removeAttribute("aria-describedby");
      onWikilinkLeave?.();
    },
    [onWikilinkLeave],
  );

  const handleMouseOver = React.useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const target = e.target as HTMLElement;
      if (target.tagName === "A" && target.classList.contains("wikilink")) {
        enterAnchor(target as HTMLAnchorElement);
      }
    },
    [enterAnchor],
  );

  const handleMouseOut = React.useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const target = e.target as HTMLElement;
      if (target.tagName === "A" && target.classList.contains("wikilink")) {
        leaveAnchor(target as HTMLAnchorElement);
      }
    },
    [leaveAnchor],
  );

  // Plan 16 Task 11 a11y: keyboard parity. ``focusin`` / ``focusout``
  // bubble (unlike ``focus`` / ``blur``), so the same delegation pattern
  // works without per-anchor wiring. React's ``onFocus`` / ``onBlur``
  // are equivalent to ``focusin`` / ``focusout`` so this stays
  // declarative.
  const handleFocus = React.useCallback(
    (e: React.FocusEvent<HTMLDivElement>) => {
      const target = e.target as HTMLElement;
      if (target.tagName === "A" && target.classList.contains("wikilink")) {
        enterAnchor(target as HTMLAnchorElement);
      }
    },
    [enterAnchor],
  );

  const handleBlur = React.useCallback(
    (e: React.FocusEvent<HTMLDivElement>) => {
      const target = e.target as HTMLElement;
      if (target.tagName === "A" && target.classList.contains("wikilink")) {
        leaveAnchor(target as HTMLAnchorElement);
      }
    },
    [leaveAnchor],
  );

  return (
    <article
      className="reader prose prose-invert flex min-w-0 flex-col gap-3 px-8 py-6 text-[var(--text)]"
      onMouseOver={handleMouseOver}
      onMouseOut={handleMouseOut}
      onFocus={handleFocus}
      onBlur={handleBlur}
    >
      <h1 className="text-2xl font-semibold">{title}</h1>
      {Object.keys(frontmatter).length > 0 && (
        <div className="fm flex flex-col gap-0.5 rounded-md border border-[var(--hairline)] bg-[var(--surface-2)] px-3 py-2 text-[11px] text-[var(--text-muted)]">
          {Object.entries(frontmatter).map(([k, v]) => (
            <div key={k}>
              <span className="k mr-1 text-[var(--text-dim)]">{k}:</span>
              {renderFrontmatterValue(v)}
            </div>
          ))}
        </div>
      )}
      <div className="reader-body leading-relaxed">{renderNote(body)}</div>
    </article>
  );
}

function renderFrontmatterValue(value: unknown): React.ReactNode {
  if (Array.isArray(value)) {
    return value.map((item, i) => (
      <React.Fragment key={i}>
        {i > 0 && ", "}
        {renderFrontmatterValue(item)}
      </React.Fragment>
    ));
  }
  if (typeof value === "string") {
    // Detect bare slug wikilinks ``[[slug]]`` inside frontmatter
    // (brain emits these for ``links:`` arrays). Plain strings
    // render as-is.
    const m = value.match(/^\[\[([^\]]+)\]\]$/);
    if (m) {
      const label = m[1];
      const broken = BROKEN_WIKILINKS.has(label);
      return (
        <a
          className={`wikilink${broken ? " broken" : ""}`}
          href="#"
        >{`[[${label}]]`}</a>
      );
    }
    return value;
  }
  return String(value);
}
