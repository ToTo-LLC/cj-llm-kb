"use client";

import * as React from "react";
import { Edit3, File as FileIcon, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAppStore } from "@/lib/state/app-store";
import { useDialogsStore } from "@/lib/state/dialogs-store";
import { useDraftStore } from "@/lib/state/draft-store";

/**
 * DraftEmpty (Plan 07 Task 19).
 *
 * Rendered in the transcript container when ``mode === "draft"`` and no
 * document is open yet. Two actions:
 *   - Open from vault → pops ``DocPickerDialog``
 *   - New blank doc   → creates a scratch doc under
 *                       ``<scope[0]>/scratch/<yyyy-mm-dd>-untitled.md``
 *
 * Both paths end by calling ``useDraftStore.openDoc(...)`` which flips
 * the chat-screen into split view.
 */

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function makeScratchDoc(domain: string) {
  const t = today();
  return {
    path: `${domain}/scratch/${t}-untitled.md`,
    domain,
    frontmatter: `---\ntype: scratch\ndomain: ${domain}\ncreated: ${t}\n---`,
    body: "# Untitled\n\nStart drafting\u2026",
    pendingEdits: [],
  };
}

export function DraftEmpty(): React.ReactElement {
  const scope = useAppStore((s) => s.scope);
  const openDialog = useDialogsStore((s) => s.open);
  const openDoc = useDraftStore((s) => s.openDoc);

  // scope[0] is the destination for scratch docs per the plan. Fall
  // back to "work" so we never produce a path-less scratch even on a
  // pathological empty scope.
  const defaultDomain = scope[0] ?? "work";

  const handlePickFromVault = React.useCallback(() => {
    openDialog({
      kind: "doc-picker",
      onPick: (path: string) => {
        // For now DraftEmpty can only stage the skeleton doc — the
        // hydrated body / frontmatter come via brain_read_note in a
        // follow-up once the picker wires that call. Task 25 sweeps
        // the full hydration path.
        const domain = path.split("/")[0] ?? defaultDomain;
        openDoc({
          path,
          domain,
          frontmatter: "",
          body: "",
          pendingEdits: [],
        });
      },
      onNewBlank: (path: string) => {
        const domain = path.split("/")[0] ?? defaultDomain;
        openDoc(makeScratchDoc(domain));
      },
    });
  }, [openDialog, openDoc, defaultDomain]);

  const handleNewBlank = React.useCallback(() => {
    openDoc(makeScratchDoc(defaultDomain));
  }, [openDoc, defaultDomain]);

  return (
    <section
      className="mx-auto flex max-w-xl flex-col items-center gap-4 py-12 text-center"
      aria-label="Draft mode empty state"
    >
      <div
        className="flex h-12 w-12 items-center justify-center rounded-full border border-[var(--hairline)] bg-[var(--surface-1)] text-[var(--tt-sage)]"
        aria-hidden="true"
      >
        <Edit3 className="h-6 w-6" />
      </div>
      <h2 className="text-lg font-semibold text-foreground">
        Pick a document to draft on.
      </h2>
      <p className="max-w-md text-sm text-text-muted">
        Draft mode works against one open doc. brain proposes inline edits you
        review before they touch disk \u2014 wikilinks and frontmatter stay
        intact.
      </p>
      <div className="flex flex-wrap justify-center gap-2">
        <Button onClick={handlePickFromVault} className="gap-2">
          <FileIcon className="h-3.5 w-3.5" /> Open from vault
        </Button>
        <Button variant="ghost" onClick={handleNewBlank} className="gap-2">
          <Plus className="h-3.5 w-3.5" /> New blank doc
        </Button>
      </div>
    </section>
  );
}
