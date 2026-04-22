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

/**
 * Full-note renderer used by the Browse reader. Unlike
 * ``renderBody`` (chat-stream paragraphs only), this pass handles
 * block-level markdown brain writes to the vault: ``#`` / ``##`` /
 * ``###`` headings, ``> `` blockquotes, ``- `` bullet lists, and
 * ``code fences``. Inline tokenisation reuses ``renderInline``.
 *
 * Kept deliberately small — the vault stays simple enough that we
 * don't need a full CommonMark parser yet. Anything more exotic
 * (tables, nested lists) falls through as a plain paragraph.
 *
 * ``key`` prefixes guarantee stable React keys across line-level
 * branches (heading vs list vs fence) so re-renders don't thrash
 * the DOM.
 */
export function renderNote(body: string): React.ReactNode {
  const lines = body.split("\n");
  const out: React.ReactNode[] = [];
  let listItems: React.ReactNode[] | null = null;
  let inFence = false;
  let fenceLines: string[] = [];

  const flushList = () => {
    if (listItems) {
      out.push(
        React.createElement("ul", { key: `ul-${out.length}` }, listItems),
      );
      listItems = null;
    }
  };
  const flushFence = () => {
    if (fenceLines.length > 0 || inFence) {
      out.push(
        React.createElement(
          "pre",
          { key: `pre-${out.length}` },
          React.createElement("code", null, fenceLines.join("\n")),
        ),
      );
      fenceLines = [];
    }
  };

  lines.forEach((raw, i) => {
    if (raw.startsWith("```")) {
      if (inFence) {
        flushFence();
        inFence = false;
      } else {
        flushList();
        inFence = true;
      }
      return;
    }
    if (inFence) {
      fenceLines.push(raw);
      return;
    }
    if (raw.startsWith("### ")) {
      flushList();
      out.push(
        React.createElement("h3", { key: `h3-${i}` }, renderInline(raw.slice(4), i * 100)),
      );
      return;
    }
    if (raw.startsWith("## ")) {
      flushList();
      out.push(
        React.createElement("h2", { key: `h2-${i}` }, renderInline(raw.slice(3), i * 100)),
      );
      return;
    }
    if (raw.startsWith("# ")) {
      flushList();
      out.push(
        React.createElement("h1", { key: `h1-${i}` }, renderInline(raw.slice(2), i * 100)),
      );
      return;
    }
    if (raw.startsWith("> ")) {
      flushList();
      out.push(
        React.createElement(
          "blockquote",
          { key: `bq-${i}` },
          renderInline(raw.slice(2), i * 100),
        ),
      );
      return;
    }
    if (raw.startsWith("- ")) {
      listItems = listItems ?? [];
      listItems.push(
        React.createElement("li", { key: `li-${i}` }, renderInline(raw.slice(2), i * 100)),
      );
      return;
    }
    if (raw.trim() === "") {
      flushList();
      return;
    }
    flushList();
    out.push(React.createElement("p", { key: `p-${i}` }, renderInline(raw, i * 100)));
  });

  flushList();
  if (inFence) flushFence();
  return out;
}
