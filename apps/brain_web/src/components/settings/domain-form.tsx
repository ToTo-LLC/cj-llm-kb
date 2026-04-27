"use client";

import * as React from "react";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createDomain } from "@/lib/api/tools";
import { useSystemStore } from "@/lib/state/system-store";
import { kebabCoerce } from "@/lib/vault/path-builder";

/**
 * DomainForm (Plan 10 Task 6).
 *
 * Add-domain form extracted from ``panel-domains.tsx`` so the setup
 * wizard's "starting theme" step (Plan 10 Task 7 follow-up) can drop
 * it in next to the built-in domain previews. Submits via
 * ``brain_create_domain`` and calls ``onAdded`` after a successful
 * create so the host can refresh whatever list it renders.
 *
 * Slug validation now matches the Plan 10 D2 rules client-side:
 *
 *   ``^[a-z][a-z0-9_-]{0,30}$`` plus no trailing ``_`` / ``-`` and no
 *   path separators (``/`` / ``\``). The backend's
 *   ``_validate_domain_slug`` enforces the same regex; this client-
 *   side check just keeps the submit button disabled until the slug
 *   is plausibly valid so the user gets immediate feedback rather
 *   than a round-trip rejection.
 */

// Curated accent defaults drawn from the v4 brand palette plus two
// complementary warm tones (sky / sage / wheat / ember / dusk / wine).
// Keep this list in sync with the topbar / chat / settings dots so a
// user-created domain visually fits next to the built-in ones.
//
// Source: docs/design/CJ Knowledge LLM v4/brand/brain-brand.html
export const ACCENT_SWATCHES = [
  "#6A8CAA", // sky    — same family as the built-in research dot
  "#6E7F5B", // sage   — same family as the built-in work dot
  "#D6A34E", // wheat  — warn / signal
  "#C64B2E", // ember  — same family as the built-in personal dot
  "#4C5872", // dusk   — informational / threads
  "#7A2E3B", // wine   — rejected / dangerous
] as const;

const D2_SLUG_RE = /^[a-z][a-z0-9_-]{0,30}$/;

/**
 * Apply the Plan 10 D2 slug rules client-side. Mirrors
 * ``brain_core.config.schema._validate_domain_slug`` so the submit
 * button stays disabled until the slug is plausibly valid.
 */
export function isValidDomainSlug(slug: string): boolean {
  if (!D2_SLUG_RE.test(slug)) return false;
  if (slug.endsWith("_") || slug.endsWith("-")) return false;
  if (slug.includes("/") || slug.includes("\\")) return false;
  return true;
}

export interface DomainFormProps {
  /** Called after a successful create — the host typically refreshes its
   *  ``listDomains`` view here. */
  onAdded?: () => void;
  /** Optional submit-time hook — the setup wizard uses this to inject its
   *  own create flow (e.g. queue the slug for later instead of calling
   *  ``brain_create_domain`` immediately). When omitted, the form posts
   *  directly to ``brain_create_domain``. */
  onSubmit?: (args: {
    slug: string;
    name: string;
    accent_color: string;
  }) => Promise<void>;
}

export function DomainForm({
  onAdded,
  onSubmit,
}: DomainFormProps): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const [name, setName] = React.useState("");
  const [slug, setSlug] = React.useState("");
  const [accent, setAccent] = React.useState<string>(ACCENT_SWATCHES[0]!);
  const [submitting, setSubmitting] = React.useState(false);

  const valid = name.trim().length > 0 && isValidDomainSlug(slug);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid || submitting) return;
    setSubmitting(true);
    try {
      const args = { slug, name: name.trim(), accent_color: accent };
      if (onSubmit) {
        await onSubmit(args);
      } else {
        await createDomain(args);
      }
      pushToast({
        lead: "Domain added.",
        msg: `${slug}/ is ready for content.`,
        variant: "success",
      });
      setName("");
      setSlug("");
      onAdded?.();
    } catch (err) {
      pushToast({
        lead: "Couldn't add domain.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-3"
      aria-label="Add domain"
    >
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label
            htmlFor="new-domain-name"
            className="mb-1.5 block text-[11px] uppercase tracking-wider text-[var(--text-dim)]"
          >
            Display name
          </label>
          <Input
            id="new-domain-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Hobby"
          />
        </div>
        <div>
          <label
            htmlFor="new-domain-slug"
            className="mb-1.5 block text-[11px] uppercase tracking-wider text-[var(--text-dim)]"
          >
            Folder slug
          </label>
          <Input
            id="new-domain-slug"
            value={slug}
            onChange={(e) => setSlug(kebabCoerce(e.target.value))}
            placeholder="hobby"
            className="font-mono"
            spellCheck={false}
            aria-invalid={slug.length > 0 && !isValidDomainSlug(slug)}
            aria-describedby="new-domain-slug-hint"
          />
          <p
            id="new-domain-slug-hint"
            className="mt-1 text-[11px] text-[var(--text-dim)]"
          >
            Lowercase letters, digits, ``-`` or ``_``. Must start with a
            letter; can&apos;t end with ``-`` / ``_``.
          </p>
        </div>
      </div>

      <div>
        <label className="mb-1.5 block text-[11px] uppercase tracking-wider text-[var(--text-dim)]">
          Accent colour
        </label>
        <div className="flex items-center gap-2" role="radiogroup">
          {ACCENT_SWATCHES.map((c) => (
            <button
              key={c}
              type="button"
              role="radio"
              aria-checked={accent === c}
              aria-label={`Accent ${c}`}
              onClick={() => setAccent(c)}
              className={`h-6 w-6 rounded-full border transition-transform ${
                accent === c
                  ? "border-[var(--text)] scale-110"
                  : "border-[var(--hairline)]"
              }`}
              style={{ background: c }}
            />
          ))}
        </div>
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={!valid || submitting} className="gap-2">
          <Plus className="h-3.5 w-3.5" />
          {submitting ? "Adding…" : "Add domain"}
        </Button>
      </div>
    </form>
  );
}
