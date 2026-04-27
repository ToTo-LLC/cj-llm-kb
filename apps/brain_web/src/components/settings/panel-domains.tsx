"use client";

import * as React from "react";
import { Edit2, Lock, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ACCENT_SWATCHES, DomainForm } from "@/components/settings/domain-form";
import { invalidateDomainsCache } from "@/lib/hooks/use-domains";
import { brainDeleteDomain, listDomains } from "@/lib/api/tools";
import { useDialogsStore } from "@/lib/state/dialogs-store";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * PanelDomains (Plan 07 Task 22 → Plan 10 Task 6).
 *
 * - List renders from ``listDomains``. Each row shows a colour swatch,
 *   the slug, and (when tooling catches up) a file count. Rename opens
 *   the existing RenameDomainDialog via dialogs-store with an
 *   ``onRenamed`` callback wired back here so the list refreshes after
 *   a successful rename. Delete opens TypedConfirmDialog and on
 *   confirm calls ``brain_delete_domain``.
 *
 * - Personal shows a Lock-icon "Privacy-railed" badge and has NO delete
 *   button. This mirrors Principle 2 (scope guard) and Plan 10 D5: the
 *   ``personal`` slug is hardcoded as the privacy rail and must not be
 *   deleteable from a casual UI click.
 *
 * - Add form is the extracted ``DomainForm`` (Plan 10 Task 6) which
 *   the setup wizard reuses for the starting-theme step.
 */

const PROTECTED_DOMAINS = new Set<string>(["personal"]);

// Built-in domain dots use the brand-skin's semantic ``--dom-*`` tokens so
// the colors match the topbar's scope-picker dots, the chat pane's domain
// chips, and every other place these three domains surface. The values are
// CSS variable references (resolved by the active theme — light vs dark
// flips them automatically).
//
// User-created domains beyond these three pick from ACCENT_SWATCHES (kept
// in sync with the form's swatch list).
const BUILTIN_DOMAIN_ACCENT: Record<string, string> = {
  research: "var(--dom-research)",
  work: "var(--dom-work)",
  personal: "var(--dom-personal)",
};

export function PanelDomains(): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const openDialog = useDialogsStore((s) => s.open);

  const [domains, setDomains] = React.useState<string[]>([]);
  const [loading, setLoading] = React.useState(true);

  const refresh = React.useCallback(async () => {
    // Plan 10 Task 7: blow the module-level cache so other live
    // surfaces (topbar scope picker, Browse file tree) re-fetch on
    // their next mount. The list call below populates a fresh cache
    // for the panel itself.
    invalidateDomainsCache();
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
      // Plan 10 Task 6: refresh the panel list after the dialog
      // commits the rename. Without this hook the row would still
      // show the old slug until the user navigated away and back.
      onRenamed: () => {
        void refresh();
      },
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
          // Plan 10 Task 7: invalidate the cache so the topbar +
          // browse pick up the deletion on their next read.
          invalidateDomainsCache();
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
              const builtinAccent = BUILTIN_DOMAIN_ACCENT[slug];
              const accent =
                builtinAccent ??
                ACCENT_SWATCHES[idx % ACCENT_SWATCHES.length] ??
                "#6A8CAA";
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
                      className="inline-flex items-center gap-1 rounded-full border border-[var(--hairline-strong)] px-2 py-0.5 text-[10px] font-medium"
                      style={{
                        background: "var(--dom-personal-soft)",
                        color: "var(--dom-personal)",
                      }}
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

      <section>
        <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
          Add domain
        </h2>
        <DomainForm onAdded={() => void refresh()} />
      </section>
    </div>
  );
}
