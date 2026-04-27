"use client";

import * as React from "react";
import { AlertTriangle, Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Modal } from "./modal";
import { renameDomain } from "@/lib/api/tools";
import { kebabCoerce } from "@/lib/vault/path-builder";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * RenameDomainDialog (Plan 07 Task 20).
 *
 * Collects a new slug for the domain, an opt-out checkbox for rewriting
 * wikilinks / frontmatter, and a warning block with the current file count.
 *
 * Copy correction (plan line 3606): the v3 draft said the rename is staged
 * as a patch. It isn't — per D2a the backend does the rename atomically via
 * UndoLog. The warning now reads:
 *   "brain renames the folder and rewrites references atomically. The
 *    operation is reversible via Undo last."
 *
 * Submit → ``brain_rename_domain({from, to, rewrite_frontmatter})``.
 */

export interface RenameDomainDialogProps {
  kind: "rename-domain";
  domain: { id: string; name: string; count: number };
  /** Plan 10 Task 6: invoked after a successful rename so the host can
   *  refresh its list. The dialog still calls ``onClose`` afterwards. */
  onRenamed?: () => void;
  onClose: () => void;
}

// Plan 10 D2 client-side regex — matches the backend's
// ``brain_core.config.schema._validate_domain_slug`` so the user gets
// immediate feedback rather than a round-trip rejection.
const D2_SLUG_RE = /^[a-z][a-z0-9_-]{0,30}$/;

function isValidRenameSlug(s: string, currentSlug: string): boolean {
  if (s === currentSlug) return false;
  if (!D2_SLUG_RE.test(s)) return false;
  if (s.endsWith("_") || s.endsWith("-")) return false;
  if (s.includes("/") || s.includes("\\")) return false;
  // Plan 10 D5: ``personal`` is the privacy-railed slug; renaming TO
  // it is refused server-side, gate client-side too.
  if (s === "personal") return false;
  return true;
}

export function RenameDomainDialog({
  domain,
  onRenamed,
  onClose,
}: RenameDomainDialogProps) {
  const [newSlug, setNewSlug] = React.useState<string>(domain.id);
  const [rewrite, setRewrite] = React.useState<boolean>(true);
  const [submitting, setSubmitting] = React.useState(false);

  const valid = isValidRenameSlug(newSlug, domain.id);

  const handleSubmit = React.useCallback(async () => {
    if (!valid || submitting) return;
    setSubmitting(true);
    try {
      const resp = await renameDomain({
        from: domain.id,
        to: newSlug,
        rewrite_frontmatter: rewrite,
      });
      const files = resp.data?.files_updated ?? 0;
      useSystemStore.getState().pushToast({
        lead: "Domain renamed.",
        msg: `${files} file${files === 1 ? "" : "s"} updated. Undo via Undo last.`,
        variant: "success",
      });
      onRenamed?.();
      onClose();
    } catch (err) {
      useSystemStore.getState().pushToast({
        lead: "Couldn't rename domain.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
      setSubmitting(false);
    }
  }, [valid, submitting, domain.id, newSlug, rewrite, onRenamed, onClose]);

  return (
    <Modal
      open
      onClose={onClose}
      eyebrow={`Rename domain · ${domain.name}`}
      title="Rename and rewrite references."
      description="Pick a new slug. brain rewrites the folder and every wikilink that points into it."
      width={520}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!valid || submitting}
            className="gap-2"
          >
            <Check className="h-3.5 w-3.5" /> Rename domain
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div>
          <label
            htmlFor="rename-new-slug"
            className="mb-1.5 block text-xs uppercase tracking-wider text-muted-foreground"
          >
            New slug
          </label>
          <Input
            id="rename-new-slug"
            value={newSlug}
            onChange={(e) => setNewSlug(kebabCoerce(e.target.value))}
            className="font-mono"
            spellCheck={false}
            autoFocus
          />
          <p className="mt-1 text-[11px] text-muted-foreground">
            Lowercase, hyphen-separated. Becomes the folder name.
          </p>
        </div>

        <label className="flex cursor-pointer items-start gap-3">
          <Checkbox
            checked={rewrite}
            onCheckedChange={(next) => setRewrite(next === true)}
            aria-label="Rewrite wikilinks and frontmatter"
            className="mt-0.5"
          />
          <div>
            <div className="text-sm">
              Rewrite{" "}
              <code className="font-mono text-xs">[[wikilinks]]</code> and
              frontmatter
            </div>
            <div className="mt-0.5 text-[11px] text-muted-foreground">
              Every note that links into{" "}
              <code className="font-mono text-xs">{domain.id}/</code> or tags it
              in frontmatter gets updated to the new slug.
            </div>
          </div>
        </label>

        <div
          data-testid="rename-warn"
          className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-100"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
          <div>
            This affects <strong>{domain.count}</strong> file
            {domain.count === 1 ? "" : "s"} and every{" "}
            <code className="font-mono">[[wikilink]]</code> that points into{" "}
            <code className="font-mono">{domain.id}/</code>. brain renames the
            folder and rewrites references atomically. The operation is
            reversible via <strong>Undo last</strong>.
          </div>
        </div>
      </div>
    </Modal>
  );
}
