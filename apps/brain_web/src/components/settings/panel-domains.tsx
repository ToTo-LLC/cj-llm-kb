"use client";

import * as React from "react";
import { Edit2, Lock, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { brainDeleteDomain, createDomain, listDomains } from "@/lib/api/tools";
import { useDialogsStore } from "@/lib/state/dialogs-store";
import { useSystemStore } from "@/lib/state/system-store";
import { kebabCoerce } from "@/lib/vault/path-builder";

/**
 * PanelDomains (Plan 07 Task 22).
 *
 * - List renders from ``listDomains``. Each row shows a colour swatch,
 *   the slug, and (when tooling catches up) a file count. Rename opens
 *   the existing RenameDomainDialog via dialogs-store. Delete opens
 *   TypedConfirmDialog with a stubbed onConfirm until Task 25 ships
 *   ``brain_delete_domain``.
 *
 * - Personal shows a Lock-icon "Privacy-railed" badge and has NO delete
 *   button. This mirrors Principle 2 (scope guard): ``personal`` never
 *   leaks into default queries and should never be deleteable from a
 *   casual UI click.
 *
 * - Add form (bottom): name + slug + accent colour → ``createDomain``.
 */

const PROTECTED_DOMAINS = new Set<string>(["personal"]);

// Curated accent defaults drawn from the v4 brand palette plus two
// complementary warm tones. Aligning with the brand keeps user-created
// domains visually cohesive with the built-in research/work/personal
// dots (which use sky/sage/ember). Stored verbatim as the colour the
// backend gets; users can still swap via the CLI for anything outside
// this set.
//
// Source: docs/design/CJ Knowledge LLM v4/brand/brain-brand.html
//   sky / sage / wheat / ember / dusk / wine.
const ACCENT_SWATCHES = [
  "#6A8CAA", // sky    — same family as the built-in research dot
  "#6E7F5B", // sage   — same family as the built-in work dot
  "#D6A34E", // wheat  — warn / signal
  "#C64B2E", // ember  — same family as the built-in personal dot
  "#4C5872", // dusk   — informational / threads
  "#7A2E3B", // wine   — rejected / dangerous
] as const;

export function PanelDomains(): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const openDialog = useDialogsStore((s) => s.open);

  const [domains, setDomains] = React.useState<string[]>([]);
  const [loading, setLoading] = React.useState(true);

  const refresh = React.useCallback(async () => {
    try {
      const r = await listDomains();
      setDomains(r.data?.domains ?? []);
    } catch {
      pushToast({
        lead: "Load failed.",
        msg: "Could not list domains.",
        variant: "danger",
      });
    } finally {
      setLoading(false);
    }
  }, [pushToast]);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleRename = (slug: string) => {
    openDialog({
      kind: "rename-domain",
      domain: { id: slug, name: slug, count: 0 },
    });
  };

  const handleDelete = (slug: string) => {
    openDialog({
      kind: "typed-confirm",
      title: `Delete ${slug}?`,
      body: `This moves the ${slug}/ folder to .brain/trash/. Backups (if enabled) retain a copy; brain_undo_last fully reverses the move.`,
      word: slug, // per plan: typed-match on the slug itself
      danger: true,
      onConfirm: async () => {
        try {
          const res = await brainDeleteDomain({ slug, typed_confirm: true });
          setDomains((prev) => prev.filter((s) => s !== slug));
          const moved = res.data?.files_moved ?? 0;
          pushToast({
            lead: "Domain deleted.",
            msg: `${slug}/ moved to trash (${moved} files). Undo via brain_undo_last.`,
            variant: "success",
          });
        } catch (err) {
          pushToast({
            lead: "Couldn't delete domain.",
            msg: err instanceof Error ? err.message : "Unknown error.",
            variant: "danger",
          });
        }
      },
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <section>
        <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
          Domains
        </h2>
        <p className="mb-3 text-[11px] text-[var(--text-muted)]">
          Each domain is a top-level folder in your vault. The scope
          selector + every ingest call targets a single domain. Personal
          is privacy-railed — it never appears in default queries and
          can&apos;t be deleted from this UI.
        </p>

        {loading ? (
          <div className="rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] p-4 text-xs text-[var(--text-dim)]">
            Loading domains…
          </div>
        ) : (
          <ul
            className="flex flex-col gap-1 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)]"
            role="list"
          >
            {domains.map((slug, idx) => {
              const protectedDomain = PROTECTED_DOMAINS.has(slug);
              const accent =
                ACCENT_SWATCHES[idx % ACCENT_SWATCHES.length] ?? "#6A8CAA";
              return (
                <li
                  key={slug}
                  className="flex items-center gap-3 border-b border-[var(--hairline)] px-3 py-2 last:border-0"
                >
                  <span
                    aria-hidden="true"
                    className="h-4 w-4 rounded-full border border-[var(--hairline)]"
                    style={{ background: accent }}
                  />
                  <span className="font-mono text-sm text-[var(--text)]">
                    {slug}
                  </span>

                  {protectedDomain && (
                    <span
                      data-testid="personal-privacy-badge"
                      className="inline-flex items-center gap-1 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-medium text-indigo-300"
                    >
                      <Lock className="h-2.5 w-2.5" />
                      Privacy-railed
                    </span>
                  )}

                  <div className="ml-auto flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRename(slug)}
                      aria-label={`Rename ${slug}`}
                      className="h-7 gap-1 px-2 text-xs"
                    >
                      <Edit2 className="h-3 w-3" />
                      Rename
                    </Button>
                    {!protectedDomain && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(slug)}
                        aria-label={`Delete ${slug}`}
                        className="h-7 gap-1 px-2 text-xs text-red-400 hover:text-red-300"
                      >
                        <Trash2 className="h-3 w-3" />
                        Delete
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <AddDomainForm onAdded={() => void refresh()} />
    </div>
  );
}

function AddDomainForm({
  onAdded,
}: {
  onAdded: () => void;
}): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const [name, setName] = React.useState("");
  const [slug, setSlug] = React.useState("");
  const [accent, setAccent] = React.useState<string>(ACCENT_SWATCHES[0]!);
  const [submitting, setSubmitting] = React.useState(false);

  const valid = name.trim().length > 0 && /^[a-z][a-z0-9-]{1,24}$/.test(slug);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid || submitting) return;
    setSubmitting(true);
    try {
      await createDomain({
        slug,
        name: name.trim(),
        accent_color: accent,
      });
      pushToast({
        lead: "Domain added.",
        msg: `${slug}/ is ready for content.`,
        variant: "success",
      });
      setName("");
      setSlug("");
      onAdded();
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
    <section>
      <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
        Add domain
      </h2>

      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
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
            />
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
    </section>
  );
}
