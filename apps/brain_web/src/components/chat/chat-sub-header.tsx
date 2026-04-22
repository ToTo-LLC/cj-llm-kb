"use client";

import * as React from "react";
import {
  GitFork,
  MessageSquare,
  Plus,
  Upload,
} from "lucide-react";

/**
 * ChatSubHeader (Plan 07 Task 15).
 *
 * Renders the slim row above the transcript: title + turn/cost status
 * on the left, Export + Fork buttons on the right.
 *
 * Active thread → "{title} · N turns · $X.XXX".
 * New thread → "New thread · untitled · brain will name it after your
 * first message".
 *
 * Export and Fork dialogs land in Task 20 — for now Fork logs a TODO so
 * the wiring is visible in the devtools while the dialog is being
 * implemented.
 */

export interface ChatSubHeaderThread {
  title: string;
  turns: number;
  cost: number;
}

export interface ChatSubHeaderProps {
  /** Thread metadata; ``null`` renders the new-thread variant. */
  thread: ChatSubHeaderThread | null;
}

function formatCost(cost: number): string {
  return `$${cost.toFixed(3)}`;
}

export function ChatSubHeader({
  thread,
}: ChatSubHeaderProps): React.ReactElement {
  const handleExport = React.useCallback(() => {
    // eslint-disable-next-line no-console
    console.log("TODO Task 20 — export thread");
  }, []);

  const handleFork = React.useCallback(() => {
    // eslint-disable-next-line no-console
    console.log("TODO Task 20 — open Fork dialog");
  }, []);

  return (
    <div className="flex items-center gap-2 border-b border-hairline bg-surface-0 px-4 py-2 text-sm">
      {thread ? (
        <>
          <MessageSquare
            className="h-4 w-4 text-text-muted"
            aria-hidden="true"
          />
          <span className="font-medium text-foreground">{thread.title}</span>
          <span className="text-text-muted">·</span>
          <span className="text-text-muted">
            {thread.turns} turns · {formatCost(thread.cost)}
          </span>
        </>
      ) : (
        <>
          <Plus className="h-4 w-4 text-text-muted" aria-hidden="true" />
          <span className="text-text-muted">New thread · untitled</span>
          <span className="text-text-muted">·</span>
          <span className="text-text-dim">
            brain will name it after your first message
          </span>
        </>
      )}

      <div className="flex-1" />

      <button
        type="button"
        onClick={handleExport}
        className="inline-flex h-7 w-7 items-center justify-center rounded-md text-text-muted hover:bg-surface-2 hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        aria-label="Export"
        title="Export"
      >
        <Upload className="h-4 w-4" aria-hidden="true" />
      </button>
      <button
        type="button"
        onClick={handleFork}
        className="inline-flex h-7 w-7 items-center justify-center rounded-md text-text-muted hover:bg-surface-2 hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        aria-label="Fork"
        title="Fork"
      >
        <GitFork className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}
