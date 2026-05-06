"use client";

import * as React from "react";
import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Modal } from "./modal";

/**
 * FilePreviewOverlay (Plan 16 Task 11).
 *
 * Per Plan 16 D11, Browse needs a populated-state overlay surface that
 * axe-core can scan. Today the populated-state is an inline split-pane
 * (Reader + MetaStrip on the right of FileTree); the empty-state is the
 * "Select a note to read." placeholder. Plan 14 Task 4 papered over the
 * gap by scanning ``<SearchOverlay />`` (⌘K) as the closest analogue.
 *
 * This overlay is the dedicated surface promised in Plan 16 D11. It is
 * a read-only quick-preview launched from the FileTree click target —
 * the inline split-pane is still wired for the deep "select-and-read"
 * flow. The overlay surface is the "populated-state" by virtue of being
 * a Radix Dialog (modal-shape, ``role="dialog"`` + ``aria-modal``);
 * the split-pane stays as the inline default.
 *
 * Microcopy:
 *   - Title:       file path (e.g. ``research/notes/foo.md``)
 *   - Description: "Quick preview from Browse — opens read-only."
 *   - Body:        first 1k chars of the note content rendered as
 *                  monospace (no markdown re-render — this is a
 *                  preview, not a Reader). Trailing "…" when truncated.
 *   - Footer:      Open in Browse (deep-link via ``onOpenFull``) +
 *                  Close.
 *
 * Per Task 9 review lesson the description prop and body content are
 * DISTINCT — description states the high-level purpose; body is the
 * actual file content.
 *
 * Local-state ``isOpen`` / ``onClose`` (rather than ``dialogs-store``)
 * is intentional. Browse-scoped overlay; routing it through the global
 * dialogs store would buy nothing and add a discriminated-union case
 * the Plan 16 scaffold doesn't need yet — same reasoning as
 * ``RepairConfigDialog`` and ``AutonomyModal``.
 */

const PREVIEW_MAX_CHARS = 1000;

export interface FilePreviewOverlayProps {
  isOpen: boolean;
  onClose: () => void;
  /** Vault-relative path. Renders as the dialog title. */
  path: string;
  /** Raw note body (post-frontmatter). May be empty. */
  body: string;
  /**
   * Optional handler for "Open in Browse" — wires the overlay's
   * footer button to a parent-controlled deep-link / route push. If
   * omitted, the button is hidden. The overlay's primary value is the
   * preview; jumping to the full Reader is a convenience.
   */
  onOpenFull?: (path: string) => void;
}

export function FilePreviewOverlay({
  isOpen,
  onClose,
  path,
  body,
  onOpenFull,
}: FilePreviewOverlayProps): React.ReactElement {
  const truncated = body.length > PREVIEW_MAX_CHARS;
  const preview = truncated ? body.slice(0, PREVIEW_MAX_CHARS) : body;

  const handleOpenFull = React.useCallback(() => {
    if (onOpenFull) onOpenFull(path);
    onClose();
  }, [onOpenFull, onClose, path]);

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title={path}
      description="Quick preview from Browse — opens read-only."
      width={680}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          {onOpenFull ? (
            <Button onClick={handleOpenFull} className="gap-2">
              <ExternalLink className="h-3.5 w-3.5" /> Open in Browse
            </Button>
          ) : null}
        </>
      }
    >
      {body.trim().length === 0 ? (
        <p className="text-muted-foreground">
          This note is empty.
        </p>
      ) : (
        <pre
          className="max-h-[60vh] overflow-y-auto whitespace-pre-wrap rounded-md border border-[var(--hairline)] bg-[var(--surface-2)] p-3 font-mono text-[12px] text-[var(--text)]"
          aria-label={`Preview of ${path}`}
        >
          {preview}
          {truncated ? "\n\n…" : ""}
        </pre>
      )}
    </Modal>
  );
}
