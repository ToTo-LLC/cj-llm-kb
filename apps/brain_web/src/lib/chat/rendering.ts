// Inline-markdown parser for chat messages. Plan 07 Task 14.
//
// Ports the v3 design's inline tokenizer. Handles the four tokens the
// assistant emits:
//
//   - ``[[wikilink]]``   → <a class="wikilink"> (+ ``.broken`` if the
//                          label is in BROKEN_WIKILINKS — Plan 09 fills
//                          that set via brain_wikilink_status)
//   - ``**bold**``       → <strong>
//   - `` `code` ``       → <code>
//   - ``*italic*``       → <em>
//
// Deliberately small: we render streamed assistant output that the
// brain prompts keep ASCII-inline. Block-level markdown (headings,
// fences, lists) is NOT handled here — brain emits those as verbatim
// text and the user files them to wiki via the MsgActions.
//
// Matching order matters: the single regex alternates the four tokens
// so the longer tokens (``**`` / ``[[``) win over their single-char
// counterparts (``*``). Without that ordering ``**word**`` would be
// tokenised as two ``*word*`` italics.

import * as React from "react";

import { cn } from "@/lib/utils";

const INLINE_RE = /(\[\[[^\]]+\]\]|\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;

/**
 * Labels the UI should mark as broken wikilinks (render the ``.broken``
 * class). Empty for Task 14 — Plan 09's brain_wikilink_status tool
 * populates this set once the wiki-link index lands. Task 25 sweep
 * wires the source of truth; for now the set stays empty so all
 * wikilinks render as healthy.
 */
export const BROKEN_WIKILINKS = new Set<string>();

/**
 * Tokenise one string of inline assistant text into React nodes.
 *
 * ``key`` is a per-paragraph offset so neighbouring paragraphs don't
 * produce duplicate ``key`` values when the caller stitches them
 * together. Callers pass ``i * 100`` — 100 tokens per paragraph is
 * generous; if a single paragraph ever blows past that, the resulting
 * React warning is loud enough to catch.
 */
export function renderInline(
  text: string,
  key: number = 0,
): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  INLINE_RE.lastIndex = 0;
  while ((m = INLINE_RE.exec(text)) !== null) {
    if (m.index > last) {
      nodes.push(text.slice(last, m.index));
    }
    const tok = m[0];
    if (tok.startsWith("[[")) {
      const label = tok.slice(2, -2);
      const broken = BROKEN_WIKILINKS.has(label);
      nodes.push(
        React.createElement(
          "a",
          {
            key: `w${key++}`,
            className: cn("wikilink", broken && "broken"),
            href: "#",
          },
          label,
        ),
      );
    } else if (tok.startsWith("**")) {
      nodes.push(
        React.createElement("strong", { key: `b${key++}` }, tok.slice(2, -2)),
      );
    } else if (tok.startsWith("`")) {
      nodes.push(
        React.createElement("code", { key: `c${key++}` }, tok.slice(1, -1)),
      );
    } else if (tok.startsWith("*")) {
      nodes.push(
        React.createElement("em", { key: `i${key++}` }, tok.slice(1, -1)),
      );
    }
    last = m.index + tok.length;
  }
  if (last < text.length) {
    nodes.push(text.slice(last));
  }
  return nodes;
}

/**
 * Split on blank-line boundaries and render each paragraph as a ``<p>``
 * wrapping ``renderInline`` output. Empty body returns a single empty
 * ``<p>`` — that keeps the streaming skeleton non-collapsed so the
 * caret has somewhere to hang.
 */
export function renderBody(body: string): React.ReactNode {
  const paragraphs = body.split(/\n\n+/);
  return paragraphs.map((para, i) =>
    React.createElement("p", { key: i }, renderInline(para, i * 100)),
  );
}
