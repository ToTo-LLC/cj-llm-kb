"use client";

import { usePathname } from "next/navigation";

import { PendingRail } from "@/components/pending/pending-rail";
import { useAppStore } from "@/lib/state/app-store";

/**
 * Context-sensitive right rail.
 *
 * Plan 07 Task 16 wires the compact `<PendingRail />` in for every
 * ``/chat*`` route so the user sees proposed patches alongside the
 * conversation. Other routes (``/browse``, ``/inbox``, etc.) fall
 * through to the default placeholder until Task 18 fills in the
 * browse-view backlinks surface.
 */
export function RightRail() {
  const railOpen = useAppStore((s) => s.railOpen);
  const pathname = usePathname();
  const isChat = typeof pathname === "string" && pathname.startsWith("/chat");

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
          ) : (
            <div className="flex h-full flex-col p-3">
              <div className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
                Context rail
              </div>
              <div className="mt-2 text-xs text-[var(--text-dim)]">
                Context-sensitive panel. Task 18 fills this in for browse.
              </div>
            </div>
          )}
        </>
      )}
    </aside>
  );
}
