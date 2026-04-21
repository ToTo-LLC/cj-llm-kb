"use client";

import { useAppStore } from "@/lib/state/app-store";

/**
 * Context-sensitive right rail. Task 16 fills in pending-patches content for
 * chat view; Task 18 fills in backlinks for browse view. For now it is a
 * placeholder with a visible label.
 */
export function RightRail() {
  const railOpen = useAppStore((s) => s.railOpen);

  return (
    <aside
      aria-label="Context rail"
      aria-hidden={!railOpen}
      className="rail border-l border-[var(--hairline)] bg-[var(--surface-1)] text-[var(--text)]"
      data-open={railOpen ? "true" : "false"}
    >
      {railOpen && (
        <div className="flex h-full flex-col p-3">
          <div className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
            Context rail
          </div>
          <div className="mt-2 text-xs text-[var(--text-dim)]">
            Context-sensitive panel. Task 16 / Task 18 fill this in.
          </div>
        </div>
      )}
    </aside>
  );
}
