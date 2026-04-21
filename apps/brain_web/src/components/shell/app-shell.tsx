"use client";

import { Topbar } from "./topbar";
import { LeftNav } from "./left-nav";
import { RightRail } from "./right-rail";
import { DialogHost } from "@/components/dialogs/dialog-host";
import { SystemOverlays } from "@/components/system/system-overlays";
import { useAppStore } from "@/lib/state/app-store";
import { useSystemStore } from "@/lib/state/system-store";

export function AppShell({ children }: { children: React.ReactNode }) {
  const railOpen = useAppStore((s) => s.railOpen);

  /*
   * Drag-to-attach handlers (Plan 07 Task 12).
   *
   * Attached at the outermost grid div so any drop target inside the app
   * fires the overlay once. Task 17 wires the actual ingest pipeline
   * call on `onDrop`; today we only clear the dragging flag.
   *
   * - `dragenter` with `Files` in `dataTransfer.types` enters drag mode.
   * - `dragleave` is noisy (fires on every inner element boundary), so
   *   we only clear when `relatedTarget === null` — i.e. the cursor
   *   actually left the window.
   * - `dragover` MUST preventDefault to opt in as a drop target.
   * - `drop` always clears the flag so the overlay disappears.
   */
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
        onDrop={(e) => {
          e.preventDefault();
          useSystemStore.getState().setDragging(false);
          // TODO(Task 17): forward the dropped files to the ingest pipeline.
        }}
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
