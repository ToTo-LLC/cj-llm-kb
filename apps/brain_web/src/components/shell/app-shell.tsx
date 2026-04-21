"use client";

import { Topbar } from "./topbar";
import { LeftNav } from "./left-nav";
import { RightRail } from "./right-rail";
import { DialogHost } from "@/components/dialogs/dialog-host";
import { useAppStore } from "@/lib/state/app-store";

export function AppShell({ children }: { children: React.ReactNode }) {
  const railOpen = useAppStore((s) => s.railOpen);

  return (
    <>
      <div className="app-grid" data-rail-open={railOpen ? "true" : "false"}>
        <Topbar />
        <LeftNav />
        <main className="main">{children}</main>
        <RightRail />
      </div>
      {/* App-global dialogs portal outside the grid via Radix; keep mount
          inside AppShell so they inherit theme + store providers. */}
      <DialogHost />
    </>
  );
}
