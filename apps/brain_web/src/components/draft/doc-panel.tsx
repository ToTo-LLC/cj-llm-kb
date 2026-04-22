"use client";

import * as React from "react";
import { File as FileIcon, GitCompare, Link as LinkIcon, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useDraftStore } from "@/lib/state/draft-store";
import { useDialogsStore } from "@/lib/state/dialogs-store";
import { renderWithEdits } from "@/lib/draft/render-edits";
import { cn } from "@/lib/utils";

/**
 * DocPanel (Plan 07 Task 19).
 *
 * Right-side panel the chat screen renders when Draft mode has an
 * ``activeDoc``. Layout:
 *   - head:     close + breadcrumb (click = reopen picker) + Obsidian link
 *   - banner:   pending-edits count + Discard / Apply when queue non-empty
 *   - toolbar:  Reading / Outline segmented control + word count
 *   - body:     frontmatter block + rendered paragraphs (with pending edits)
 *   - foot:     saved stat + Change-doc
 *
 * Task 25 sweep: wire the Obsidian link to ``buildObsidianUri`` (needs a
 * reliable vault-name source), and flesh out the Outline view beyond
 * the heading extraction.
 */

type View = "reading" | "outline";

export function DocPanel(): React.ReactElement | null {
  const doc = useDraftStore((s) => s.activeDoc);
  const closeDoc = useDraftStore((s) => s.closeDoc);
  const applyPendingEdits = useDraftStore((s) => s.applyPendingEdits);
  const rejectPendingEdits = useDraftStore((s) => s.rejectPendingEdits);
  const openDialog = useDialogsStore((s) => s.open);
  const openDocStore = useDraftStore((s) => s.openDoc);

  const [view, setView] = React.useState<View>("reading");

  if (!doc) return null;

  const hasPending = doc.pendingEdits.length > 0;
  const words = doc.body.trim().split(/\s+/).filter(Boolean).length;
  const slug = doc.path.split("/").pop() ?? doc.path;
  const dir = doc.path.split("/").slice(0, -1).join("/");

  const paragraphs = doc.body.split(/\n\n+/).filter(Boolean);

  const openPicker = () => {
    openDialog({
      kind: "doc-picker",
      onPick: (path: string) => {
        const domain = path.split("/")[0] ?? doc.domain;
        openDocStore({
          path,
          domain,
          frontmatter: "",
          body: "",
          pendingEdits: [],
        });
      },
      onNewBlank: (path: string) => {
        const domain = path.split("/")[0] ?? doc.domain;
        openDocStore({
          path,
          domain,
          frontmatter: `---\ntype: scratch\ndomain: ${domain}\n---`,
          body: "# Untitled\n\nStart drafting\u2026",
          pendingEdits: [],
        });
      },
    });
  };

  return (
    <aside
      aria-label="Active document"
      className="flex h-full flex-col border-l border-[var(--hairline)] bg-[var(--surface-1)]"
    >
      <div className="flex items-center gap-2 border-b border-[var(--hairline)] px-3 py-2">
        <button
          type="button"
          onClick={closeDoc}
          aria-label="Close document"
          className="rounded p-1 text-[var(--text-muted)] hover:text-[var(--text)]"
        >
          <X className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={openPicker}
          className="flex min-w-0 flex-1 items-center gap-1 truncate text-xs text-[var(--text-muted)] hover:text-[var(--text)]"
          title="Change document"
        >
          <FileIcon className="h-3 w-3" />
          <span className="text-[var(--text-dim)]">{dir}/</span>
          <span className="text-[var(--text)]">{slug}</span>
        </button>
        <button
          type="button"
          aria-label="Open in Obsidian"
          className="rounded p-1 text-[var(--text-muted)] hover:text-[var(--text)]"
        >
          <LinkIcon className="h-3.5 w-3.5" />
        </button>
      </div>

      {hasPending && (
        <div className="flex items-center gap-2 border-b border-[var(--hairline)] bg-[var(--surface-2)] px-3 py-2 text-xs">
          <GitCompare
            className="h-3.5 w-3.5"
            style={{ color: "var(--tt-sage)" }}
          />
          <span className="font-medium text-[var(--text)]">
            {doc.pendingEdits.length} pending edit
            {doc.pendingEdits.length === 1 ? "" : "s"}
          </span>
          <span className="text-[var(--text-muted)]">
            Review inline, then apply to the file.
          </span>
          <div className="ml-auto flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={rejectPendingEdits}
            >
              Discard
            </Button>
            <Button
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => {
                void applyPendingEdits();
              }}
            >
              Apply
            </Button>
          </div>
        </div>
      )}

      <div className="flex items-center gap-2 border-b border-[var(--hairline)] px-3 py-1.5 text-xs">
        <div className="flex overflow-hidden rounded-md border border-[var(--hairline)]">
          <button
            type="button"
            onClick={() => setView("reading")}
            className={cn(
              "px-2 py-1 text-[11px]",
              view === "reading"
                ? "bg-[var(--surface-2)] text-[var(--text)]"
                : "text-[var(--text-muted)]",
            )}
          >
            Reading
          </button>
          <button
            type="button"
            onClick={() => setView("outline")}
            className={cn(
              "px-2 py-1 text-[11px]",
              view === "outline"
                ? "bg-[var(--surface-2)] text-[var(--text)]"
                : "text-[var(--text-muted)]",
            )}
          >
            Outline
          </button>
        </div>
        <div className="flex-1" />
        <span className="font-mono text-[10px] text-[var(--text-dim)]">
          {words}w
        </span>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 text-sm text-[var(--text)]">
        {doc.frontmatter ? (
          <pre className="mb-3 whitespace-pre-wrap rounded bg-[var(--surface-2)] p-2 font-mono text-[10px] text-[var(--text-dim)]">
            {doc.frontmatter}
          </pre>
        ) : null}
        {view === "reading" ? (
          paragraphs.map((p, i) => {
            if (p.startsWith("# ")) {
              return (
                <h1 key={i} className="mb-3 text-lg font-semibold">
                  {p.slice(2)}
                </h1>
              );
            }
            if (p.startsWith("## ")) {
              return (
                <h2 key={i} className="mb-2 text-base font-semibold">
                  {p.slice(3)}
                </h2>
              );
            }
            // Only the last paragraph receives the pending-edit overlay;
            // render-edits appends inserts at paragraph end, which reads
            // naturally in the last block. Non-last paragraphs still
            // show delete + replace markers since those search the
            // whole body text.
            const isLast = i === paragraphs.length - 1;
            const edits = isLast ? doc.pendingEdits : [];
            return (
              <p key={i} className="mb-3 leading-relaxed">
                {renderWithEdits(p, edits)}
              </p>
            );
          })
        ) : (
          <ul className="list-disc pl-4 text-xs">
            {paragraphs
              .filter((p) => p.startsWith("#"))
              .map((p, i) => (
                <li
                  key={i}
                  className={cn(
                    "my-1",
                    p.startsWith("## ")
                      ? "text-[var(--text-dim)]"
                      : "text-[var(--text)]",
                  )}
                >
                  {p.replace(/^#+\s*/, "").split("\n")[0]}
                </li>
              ))}
          </ul>
        )}
      </div>

      <div className="flex items-center justify-between border-t border-[var(--hairline)] px-3 py-1.5 text-[11px] text-[var(--text-dim)]">
        <span>saved \u00b7 {slug}</span>
        <button
          type="button"
          onClick={openPicker}
          className="flex items-center gap-1 hover:text-[var(--text)]"
        >
          <FileIcon className="h-3 w-3" /> Change doc
        </button>
      </div>
    </aside>
  );
}
