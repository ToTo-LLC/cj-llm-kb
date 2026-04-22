"use client";

import * as React from "react";

import { renderNote } from "@/lib/chat/rendering";
import { BROKEN_WIKILINKS } from "@/lib/chat/rendering";

/**
 * Reader (Plan 07 Task 18).
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
  const handleMouseOver = React.useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const target = e.target as HTMLElement;
      if (target.tagName === "A" && target.classList.contains("wikilink")) {
        const anchor = target as HTMLAnchorElement;
        const label = anchor.textContent ?? "";
        if (!BROKEN_WIKILINKS.has(label)) {
          onWikilinkEnter?.(label, anchor);
        }
      }
    },
    [onWikilinkEnter],
  );

  const handleMouseOut = React.useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const target = e.target as HTMLElement;
      if (target.tagName === "A" && target.classList.contains("wikilink")) {
        onWikilinkLeave?.();
      }
    },
    [onWikilinkLeave],
  );

  return (
    <article
      className="reader prose prose-invert flex min-w-0 flex-col gap-3 px-8 py-6 text-[var(--text)]"
      onMouseOver={handleMouseOver}
      onMouseOut={handleMouseOut}
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
