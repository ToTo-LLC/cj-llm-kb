"use client";

import * as React from "react";

import { useBrowseStore } from "@/lib/state/browse-store";

import { LinkedRail } from "./linked-rail";

/**
 * Thin bridge between the ``<RightRail />`` (which lives inside
 * ``<AppShell />`` at the layout level) and the active
 * ``<BrowseScreen />`` — the rail reads the current note from
 * ``browse-store`` and renders ``<LinkedRail />`` once a note is
 * active. Plan 07 Task 18.
 */
export function BrowseRailBridge(): React.ReactElement {
  const currentPath = useBrowseStore((s) => s.currentPath);
  const currentBody = useBrowseStore((s) => s.currentBody);
  const slugIndex = useBrowseStore((s) => s.slugIndex);

  if (!currentPath) {
    return (
      <div className="flex h-full flex-col p-3 text-xs text-[var(--text-dim)]">
        <div className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
          Context rail
        </div>
        <div className="mt-2">Select a note to see backlinks.</div>
      </div>
    );
  }

  return (
    <LinkedRail
      currentPath={currentPath}
      currentBody={currentBody}
      slugIndex={slugIndex}
    />
  );
}
