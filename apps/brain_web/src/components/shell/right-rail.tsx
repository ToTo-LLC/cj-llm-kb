"use client";

import { usePathname } from "next/navigation";

import { PendingRail } from "@/components/pending/pending-rail";
import { BrowseRailBridge } from "@/components/browse/browse-rail-bridge";
import { useAppStore } from "@/lib/state/app-store";
import { useDraftStore } from "@/lib/state/draft-store";

/**
 * Context-sensitive right rail.
 *
 * Plan 07 Task 16 wired the compact `<PendingRail />` for every
 * ``/chat*`` route. Plan 07 Task 18 adds the ``<BrowseRailBridge />``
 * (a thin client bridge that reads the browse-screen's current
 * note from a shared store and mounts the LinkedRail) for every
 * ``/browse*`` route. Plan 07 Task 19 hides the rail on ``/chat*``
 * when Draft mode has an active document — the DocPanel occupies the
 * rail slot in that split-view layout.
 */
export function RightRail() {
  const railOpen = useAppStore((s) => s.railOpen);
  const pathname = usePathname();
  const isChat = typeof pathname === "string" && pathname.startsWith("/chat");
  const isBrowse =
    typeof pathname === "string" && pathname.startsWith("/browse");
  const activeDoc = useDraftStore((s) => s.activeDoc);

  // When Draft mode has an open doc on a chat route the split-view
  // inside ChatScreen already renders DocPanel — the app-shell rail
  // would duplicate it, so collapse the whole aside in that case.
  if (isChat && activeDoc !== null) return null;

  return (
    <aside
      aria-label="Context rail"
      aria-hidden={!railOpen}
      className="rail border-l border-[var(--hairline)] bg-[var(--surface-1)] text-[var(--text)]"
      data-open={railOpen ? "true" : "false"}
    >
      {railOpen && (
        <>
          {isChat ? (
            <PendingRail />
          ) : isBrowse ? (
            <BrowseRailBridge />
          ) : (
            <div className="flex h-full flex-col p-3">
              <div className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
                Context rail
              </div>
              <div className="mt-2 text-xs text-[var(--text-dim)]">
                Context-sensitive panel.
              </div>
            </div>
          )}
        </>
      )}
    </aside>
  );
}
