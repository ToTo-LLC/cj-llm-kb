// Wikilink helpers used by the Browse view (Plan 07 Task 18).
//
// Two pure helpers:
//
//   - ``extractWikilinks(body)`` — pulls every ``[[slug]]`` label out
//     of a note body and de-duplicates them in order of first
//     occurrence. Used by the linked-rail to render "outlinks" for
//     the current note.
//
//   - ``resolveLink(label, index)`` — maps a wikilink label to the
//     vault-relative path it resolves to using a caller-provided
//     ``{[slug]: path}`` index. Returns ``null`` when the slug is
//     absent. Resolution is strictly index-driven so the frontend
//     stays decoupled from the BROKEN_WIKILINKS set in
//     ``@/lib/chat/rendering`` (that set is a rendering hint, not a
//     resolution source — see Task 25 sweep note on Plan 09's
//     ``brain_wikilink_status`` tool).

const WIKILINK_RE = /\[\[([^\]]+)\]\]/g;

/**
 * Return a de-duplicated list of wikilink labels, in first-seen
 * order. Whitespace is preserved inside labels so readers who use
 * human-readable wikilinks (``[[Helios Account]]``) can still
 * survive the extractor — resolution is then the caller's job.
 */
export function extractWikilinks(body: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  WIKILINK_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = WIKILINK_RE.exec(body)) !== null) {
    const label = m[1];
    if (!seen.has(label)) {
      seen.add(label);
      out.push(label);
    }
  }
  return out;
}

/**
 * Resolve a wikilink label to its vault-relative path via the
 * provided ``{[slug]: path}`` index. Returns ``null`` when the slug
 * is missing — the caller paints it as ``.broken``.
 */
export function resolveLink(
  label: string,
  index: Record<string, string>,
): string | null {
  const hit = index[label];
  return typeof hit === "string" ? hit : null;
}
