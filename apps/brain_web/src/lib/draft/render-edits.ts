import * as React from "react";

import type { DocEdit } from "@/lib/state/draft-store";

/**
 * Render a doc body + its pending edits as a flat array of React nodes.
 *
 * Emits:
 *   - insert  → ``<span class="pending-edit">{text}</span>`` appended to the body
 *   - delete  → ``<del>{matched text}</del>`` in place of the matched substring
 *   - replace → ``<span class="replace-with">{old} → <span class="pending-edit">{new}</span></span>``
 *               in place of the matched old substring
 *
 * Empty ``edits`` → the body passes through as a single string node.
 *
 * Anchor resolution note (Task 19 / Task 25 sweep). Both anchor kinds
 * (``line`` / ``text``) are honoured for ``delete`` and ``replace`` ops
 * via a substring search against ``edit.text`` (for delete) or the "old"
 * half of the ``\u0000``-separated payload (for replace). ``insert``
 * anchors are NOT used for positioning in Task 19 — inserts render at
 * the end of the body. Proper anchor resolution (line-number-aware
 * placement, overlapping edits, etc.) is the Task 25 sweep item; the
 * plan sketch is light on this and shipping the happy-path keeps the
 * surface visible without bleeding scope.
 */
export function renderWithEdits(
  body: string,
  edits: DocEdit[],
): React.ReactNode[] {
  if (edits.length === 0) return [body];

  // Walk the body once, handling delete + replace in the order they
  // appear in the body. Inserts are appended at the end.
  type Marker = {
    start: number;
    end: number;
    node: React.ReactNode;
  };

  const markers: Marker[] = [];

  let keySeed = 0;
  const nextKey = () => `edit-${keySeed++}`;

  for (const edit of edits) {
    if (edit.op === "delete") {
      const match = body.indexOf(edit.text);
      if (match === -1) continue;
      markers.push({
        start: match,
        end: match + edit.text.length,
        node: React.createElement("del", { key: nextKey() }, edit.text),
      });
    } else if (edit.op === "replace") {
      const sep = edit.text.indexOf("\u0000");
      if (sep === -1) continue;
      const oldText = edit.text.slice(0, sep);
      const newText = edit.text.slice(sep + 1);
      const match = body.indexOf(oldText);
      if (match === -1) continue;
      markers.push({
        start: match,
        end: match + oldText.length,
        node: React.createElement(
          "span",
          { key: nextKey(), className: "replace-with" },
          `${oldText} \u2192 `,
          React.createElement(
            "span",
            { key: `${nextKey()}-new`, className: "pending-edit" },
            newText,
          ),
        ),
      });
    }
  }

  // Sort markers by start position. Discard overlaps by keeping the
  // first marker that occupies a given range — overlap handling is a
  // Task 25 sweep item.
  markers.sort((a, b) => a.start - b.start);
  const kept: Marker[] = [];
  for (const m of markers) {
    const last = kept[kept.length - 1];
    if (!last || m.start >= last.end) {
      kept.push(m);
    }
  }

  const nodes: React.ReactNode[] = [];
  let cursor = 0;
  for (const m of kept) {
    if (m.start > cursor) {
      nodes.push(body.slice(cursor, m.start));
    }
    nodes.push(m.node);
    cursor = m.end;
  }
  if (cursor < body.length) {
    nodes.push(body.slice(cursor));
  }

  // Inserts render at the end of the body so the reader sees a visible
  // marker of new text without us having to resolve positional anchors.
  for (const edit of edits) {
    if (edit.op !== "insert") continue;
    nodes.push(
      React.createElement(
        "span",
        { key: nextKey(), className: "pending-edit" },
        edit.text,
      ),
    );
  }

  return nodes;
}
