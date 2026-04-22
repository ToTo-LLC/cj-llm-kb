/**
 * Vault path-builder helpers (Plan 07 Task 20).
 *
 * Pure utilities used by the FileToWiki dialog to materialise a vault path
 * from a {domain, note-type, slug} triple, plus a 404-tolerant collision
 * check against the ``brain_read_note`` tool.
 *
 * Note-type taxonomy (delta-v2 V1: "person" → "entity" to match vault
 * convention of an ``entities/`` subdir):
 *
 *   source    → dated → ``<domain>/sources/<YYYY-MM-DD>-<slug>.md``
 *   concept   →       → ``<domain>/concepts/<slug>.md``
 *   entity    →       → ``<domain>/entities/<slug>.md``
 *   synthesis → dated → ``<domain>/synthesis/<YYYY-MM-DD>-<slug>.md``
 *
 * Only two types carry a date prefix (sources get intake-dated, synthesis
 * gets written-dated); concepts + entities live at stable slugs so
 * wikilinks can resolve without version churn.
 */

import { readNote } from "@/lib/api/tools";
import { ApiError } from "@/lib/api/types";

export type VaultNoteType = "source" | "concept" | "entity" | "synthesis";

/** Subdir each note-type lands in, relative to its domain folder. */
export const SUBDIR_BY_TYPE: Record<VaultNoteType, string> = {
  source: "sources",
  concept: "concepts",
  entity: "entities",
  synthesis: "synthesis",
};

/** Types whose paths get a ``YYYY-MM-DD-`` prefix in front of the slug. */
export const DATE_PREFIXED_TYPES: ReadonlySet<VaultNoteType> = new Set<VaultNoteType>([
  "source",
  "synthesis",
]);

/** ISO-8601 date string for today (no time). */
function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Build a vault-relative path for a filed note.
 *
 * The caller owns kebab-coercion of the slug — ``buildVaultPath`` does not
 * re-sanitise it, because doing so here would hide "why is my slug
 * different" confusion from the path-input UI.
 */
export function buildVaultPath(
  domain: string,
  noteType: VaultNoteType,
  slug: string,
): string {
  const subdir = SUBDIR_BY_TYPE[noteType];
  const prefixed = DATE_PREFIXED_TYPES.has(noteType)
    ? `${todayStr()}-${slug}`
    : slug;
  return `${domain}/${subdir}/${prefixed}.md`;
}

/**
 * Coerce a free-text string into a kebab-case slug.
 *
 * Rules (simple, no i18n folding — vault filenames stick to ASCII):
 *   - lowercase
 *   - spaces → hyphens
 *   - strip anything that isn't ``[a-z0-9-]``
 */
export function kebabCoerce(s: string): string {
  return s
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "");
}

/**
 * Hit ``brain_read_note(path)`` and report whether the note already exists.
 *
 * 404 from the API → no collision → returns ``false``. Any other error is
 * re-thrown so the caller can surface it (we don't want a 5xx to masquerade
 * as "no collision" and let the user overwrite something by accident).
 */
export async function checkCollision(path: string): Promise<boolean> {
  try {
    await readNote({ path });
    return true;
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return false;
    throw err;
  }
}
