import { describe, expect, test } from "vitest";

import {
  extractWikilinks,
  resolveLink,
} from "@/lib/vault/wikilinks";
import { BROKEN_WIKILINKS } from "@/lib/chat/rendering";

/**
 * Plan 07 Task 18 — wikilink helpers used by the browse reader,
 * linked-rail outlinks, and wikilink-hover.
 *
 * - ``extractWikilinks(body)`` returns a de-duplicated list of the
 *   ``[[label]]`` slugs that appear in a note body.
 * - ``resolveLink(label, index)`` maps a wikilink label to a vault
 *   path via a provided ``{[slug]: path}`` index. Returns ``null``
 *   for a slug missing from the index (broken link).
 * - ``BROKEN_WIKILINKS`` (imported from Task 14's renderer module)
 *   is the Set the renderer consults when deciding whether to paint
 *   a wikilink with the ``.broken`` class. For Task 18 we assert
 *   the Set exists and ``resolveLink`` returns ``null`` for any
 *   slug not in the provided index — Plan 09's
 *   ``brain_wikilink_status`` tool will populate the Set proper.
 */
describe("extractWikilinks", () => {
  test("returns labels for every [[...]] in the body", () => {
    const body =
      "See [[fisher-ury-interests]] and also [[silent-buyer-synthesis]] for more.";
    expect(extractWikilinks(body)).toEqual([
      "fisher-ury-interests",
      "silent-buyer-synthesis",
    ]);
  });

  test("de-duplicates repeated wikilinks to the same slug (first-match order)", () => {
    const body =
      "[[fisher-ury-interests]] appears twice — also see [[silent-buyer-synthesis]] then [[fisher-ury-interests]] again.";
    expect(extractWikilinks(body)).toEqual([
      "fisher-ury-interests",
      "silent-buyer-synthesis",
    ]);
  });
});

describe("resolveLink", () => {
  const INDEX: Record<string, string> = {
    "fisher-ury-interests": "research/notes/fisher-ury-interests.md",
    "silent-buyer-synthesis": "research/synthesis/silent-buyer-synthesis.md",
  };

  test("maps a known slug to its vault path", () => {
    expect(resolveLink("fisher-ury-interests", INDEX)).toBe(
      "research/notes/fisher-ury-interests.md",
    );
  });

  test("returns null for an unresolved slug (broken wikilink)", () => {
    expect(resolveLink("future-work", INDEX)).toBeNull();
  });

  test("BROKEN_WIKILINKS Set exists; resolveLink is index-driven, not set-driven", () => {
    // Task 14 ships BROKEN_WIKILINKS empty; Plan 09 populates it.
    // Task 18 only asserts the Set exists and that resolveLink stays
    // index-driven — membership in BROKEN_WIKILINKS does not force a
    // non-null resolution, and non-membership does not override an
    // index miss.
    expect(BROKEN_WIKILINKS).toBeInstanceOf(Set);
    BROKEN_WIKILINKS.add("future-work");
    try {
      expect(resolveLink("future-work", INDEX)).toBeNull();
    } finally {
      BROKEN_WIKILINKS.delete("future-work");
    }
  });
});
