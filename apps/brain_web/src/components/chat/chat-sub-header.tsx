"use client";

import * as React from "react";
import {
  GitFork,
  MessageSquare,
  Plus,
  Upload,
} from "lucide-react";

import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";
import { useDialogsStore } from "@/lib/state/dialogs-store";

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
 * Task 20 wired the Fork button into the ForkDialog via dialogs-store.
 * Export remains a Task 25 follow-up (no tool yet).
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
  const openDialog = useDialogsStore((s) => s.open);
  const activeThreadId = useAppStore((s) => s.activeThreadId);
  const transcriptLength = useChatStore((s) => s.transcript.length);

  const handleExport = React.useCallback(() => {
    // TODO(Task 25): wire thread export once a ``brain_export_thread`` tool
    // lands. Stubbed to a log for now so the affordance is visible in
    // devtools during manual QA.
    // eslint-disable-next-line no-console
    console.log("TODO Task 25 — export thread");
  }, []);

  const handleFork = React.useCallback(() => {
    if (!activeThreadId) return;
    openDialog({
      kind: "fork",
      threadId: activeThreadId,
      turnIndex: Math.max(0, transcriptLength - 1),
    });
  }, [openDialog, activeThreadId, transcriptLength]);

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
