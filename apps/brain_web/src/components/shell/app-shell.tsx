"use client";

import { Topbar } from "./topbar";
import { LeftNav } from "./left-nav";
import { RightRail } from "./right-rail";
import { useAppStore } from "@/lib/state/app-store";

export function AppShell({ children }: { children: React.ReactNode }) {
  const railOpen = useAppStore((s) => s.railOpen);

  return (
    <div className="app-grid" data-rail-open={railOpen ? "true" : "false"}>
      <Topbar />
      <LeftNav />
      <main className="main">{children}</main>
      <RightRail />
    </div>
  );
}
