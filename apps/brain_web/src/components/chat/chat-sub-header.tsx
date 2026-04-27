"use client";

import * as React from "react";
import {
  GitFork,
  MessageSquare,
  Plus,
  Upload,
} from "lucide-react";

import { exportThread } from "@/lib/api/tools";
import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";
import { useDialogsStore } from "@/lib/state/dialogs-store";
import { useSystemStore } from "@/lib/state/system-store";

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
 * Issue #17 wired Export to ``brain_export_thread`` — fetches the
 * thread's markdown from the vault and triggers a browser download.
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
  const pushToast = useSystemStore((s) => s.pushToast);

  const handleExport = React.useCallback(async () => {
    if (!activeThreadId) {
      // No persisted thread yet (new chat that hasn't sent a turn) —
      // nothing to export. The button is disabled in this state below.
      return;
    }
    try {
      const res = await exportThread({ thread_id: activeThreadId });
      const data = res.data;
      if (!data || typeof data.markdown !== "string") {
        throw new Error("export returned no markdown");
      }
      // Trigger a browser download of the returned markdown. Using a
      // Blob + object URL lets us specify a filename via the anchor
      // ``download`` attribute, which the data: URL approach doesn't
      // honor consistently across browsers. Object URLs are revoked
      // after the click so we don't leak the blob in memory.
      const blob = new Blob([data.markdown], {
        type: "text/markdown;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);
      try {
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = data.filename ?? `${activeThreadId}.md`;
        anchor.rel = "noopener";
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
      } finally {
        URL.revokeObjectURL(url);
      }
      pushToast({
        lead: "Exported.",
        msg: `${data.filename} downloaded (${data.byte_length} bytes).`,
        variant: "default",
      });
    } catch (err) {
      pushToast({
        lead: "Export failed.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    }
  }, [activeThreadId, pushToast]);

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
        disabled={!activeThreadId}
        className="inline-flex h-7 w-7 items-center justify-center rounded-md text-text-muted hover:bg-surface-2 hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
        aria-label="Export thread"
        title={
          activeThreadId
            ? "Export thread as markdown"
            : "Send a message before exporting"
        }
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
