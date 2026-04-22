"use client";

import * as React from "react";
import { usePathname, useRouter } from "next/navigation";

import { Topbar } from "./topbar";
import { LeftNav } from "./left-nav";
import { RightRail } from "./right-rail";
import { DialogHost } from "@/components/dialogs/dialog-host";
import { SystemOverlays } from "@/components/system/system-overlays";
import { uploadFile } from "@/lib/ingest/upload";
import {
  installPasteListener,
  triggerIngest,
} from "@/lib/ingest/url-paste";
import { useAppStore } from "@/lib/state/app-store";
import { useChatStore } from "@/lib/state/chat-store";
import { useInboxStore } from "@/lib/state/inbox-store";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * AppShell (Plan 07 Task 12 + Task 17).
 *
 * Task 12 wired the drag-to-attach overlay. Task 17 extends both:
 *
 *   * ``onDrop`` routes the dropped file to the right pipeline —
 *     drops on ``/chat*`` attach the ingest result to the next turn
 *     (``chat-store.pendingAttachedSources``); drops anywhere else
 *     route to the inbox and switch view to ``/inbox``.
 *   * ``installPasteListener`` fires whenever the user pastes outside
 *     a composer input — short text is ignored, URLs / long text are
 *     ingested and added to the inbox list.
 *
 * Cross-task note: the overlay itself is the Task 12 ``<DropOverlay />``
 * rendered from ``<SystemOverlays />``. This component just keeps the
 * ``draggingFile`` flag in sync and handles the drop action.
 */
export function AppShell({
  children,
}: {
  children: React.ReactNode;
}): React.ReactElement {
  const railOpen = useAppStore((s) => s.railOpen);
  const pathname = usePathname();
  const router = useRouter();
  const pathRef = React.useRef(pathname);
  pathRef.current = pathname;

  // Paste listener — document-level, installed once per mount.
  React.useEffect(() => {
    const handlePaste = (payload: { text: string; isUrl: boolean }) => {
      const text = payload.text;
      const title = payload.isUrl
        ? (() => {
            try {
              const u = new URL(text);
              return u.hostname + u.pathname;
            } catch {
              return text.slice(0, 80);
            }
          })()
        : text.slice(0, 80);
      const id = `paste-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const inbox = useInboxStore.getState();
      inbox.addOptimistic({
        id,
        source: text,
        title,
        type: payload.isUrl ? "url" : "text",
      });
      triggerIngest(text)
        .then((res) => {
          const data = res.data as {
            patch_id?: string | null;
            domain?: string | null;
          } | null;
          inbox.updateStatus(id, {
            status: "done",
            progress: 100,
            domain: data?.domain ?? null,
          });
          useSystemStore.getState().pushToast({
            lead: "Pasted.",
            msg: `Ingested ${payload.isUrl ? "URL" : "text snippet"} into inbox.`,
            variant: "success",
          });
        })
        .catch((err) => {
          const message =
            err instanceof Error ? err.message : "Ingest failed.";
          inbox.updateStatus(id, { status: "failed", error: message });
          useSystemStore.getState().pushToast({
            lead: "Paste ingest failed.",
            msg: message,
            variant: "danger",
          });
        });
    };
    return installPasteListener(handlePaste);
  }, []);

  /**
   * Drag-to-attach handlers (Plan 07 Task 12 + Task 17).
   *
   * Attached at the outermost grid div so any drop target inside the app
   * fires the overlay once.
   *   - ``dragenter`` with ``Files`` in ``dataTransfer.types`` enters drag mode.
   *   - ``dragleave`` is noisy (fires on every inner element boundary), so
   *     we only clear when ``relatedTarget === null`` — i.e. the cursor
   *     actually left the window.
   *   - ``dragover`` MUST preventDefault to opt in as a drop target.
   *   - ``drop`` clears the flag and routes:
   *       - on ``/chat*`` — ingest via upload and stash the resulting
   *         ``patch_id`` on ``chat-store.pendingAttachedSources``; show a
   *         "Attached to next turn" toast.
   *       - elsewhere — ingest into the inbox list and navigate to
   *         ``/inbox`` with the In progress tab active.
   *
   * Only the first file is handled today; multi-file drop is a Task 25
   * sweep item.
   */
  const handleDrop = React.useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      useSystemStore.getState().setDragging(false);
      const files = Array.from(e.dataTransfer?.files ?? []);
      if (files.length === 0) return;
      const file = files[0];
      const id = `drop-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const onChatRoute = (pathRef.current ?? "").startsWith("/chat");

      const inbox = useInboxStore.getState();
      inbox.addOptimistic({
        id,
        source: file.name,
        title: file.name,
        type: "file",
      });

      if (!onChatRoute) {
        inbox.setTab("progress");
        // Navigate to inbox so the user sees their new row land.
        if (pathRef.current !== "/inbox") {
          router.push("/inbox");
        }
      }

      uploadFile(file)
        .then((res) => {
          inbox.updateStatus(id, {
            status: "done",
            progress: 100,
            domain: res.domain ?? null,
          });
          if (onChatRoute && res.patch_id) {
            useChatStore.getState().addAttachedSource(res.patch_id);
            useSystemStore.getState().pushToast({
              lead: "Attached to next turn.",
              msg: `${file.name} will be sent with your next message.`,
              variant: "success",
            });
          }
        })
        .catch((err) => {
          const message =
            err instanceof Error ? err.message : "Upload failed.";
          inbox.updateStatus(id, { status: "failed", error: message });
          const code = (err as { code?: string } | undefined)?.code;
          if (code === "unsupported_media_type") {
            useSystemStore.getState().pushToast({
              lead: "PDFs coming soon.",
              msg: "For now, upload text-based files (md, txt, json, yaml).",
              variant: "warn",
            });
            return;
          }
          useSystemStore.getState().pushToast({
            lead: "Upload failed.",
            msg: message,
            variant: "danger",
          });
        });
    },
    [router],
  );

  return (
    <>
      <div
        className="app-grid"
        data-rail-open={railOpen ? "true" : "false"}
        onDragEnter={(e) => {
          if (e.dataTransfer?.types?.includes("Files")) {
            useSystemStore.getState().setDragging(true);
          }
        }}
        onDragLeave={(e) => {
          if (e.relatedTarget === null) {
            useSystemStore.getState().setDragging(false);
          }
        }}
        onDragOver={(e) => {
          if (e.dataTransfer?.types?.includes("Files")) {
            e.preventDefault();
          }
        }}
        onDrop={handleDrop}
      >
        <Topbar />
        <LeftNav />
        <main className="main">{children}</main>
        <RightRail />
      </div>
      {/* App-global surfaces rendered outside the grid. Both inherit the
          theme + store providers because they're still inside AppShell. */}
      <DialogHost />
      <SystemOverlays />
    </>
  );
}
