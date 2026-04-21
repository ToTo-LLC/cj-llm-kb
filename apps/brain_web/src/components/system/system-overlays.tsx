"use client";

import * as React from "react";

import { useSystemStore } from "@/lib/state/system-store";

import { BudgetWall } from "./budget-wall";
import { DropOverlay } from "./drop-overlay";
import { MidTurnToast } from "./mid-turn-toast";
import { OfflineBanner } from "./offline-banner";
import { Toasts } from "./toasts";

/**
 * SystemOverlays — single-mount compositor for every system-level overlay:
 *   - `<OfflineBanner />` above the grid while WS is disrupted.
 *   - `<BudgetWall />` blocking modal when the daily cap is hit.
 *   - `<MidTurnToast />` non-blocking banner for mid-turn issues.
 *   - `<DropOverlay />` full-screen drop target.
 *   - `<Toasts />` stacked notifications.
 *
 * Mounts as a SIBLING of `<DialogHost />` inside `<AppShell />` — so both
 * surfaces share the theme + state providers but live outside the app
 * grid's `<main>` content.
 *
 * Every overlay reads its visibility from `useSystemStore` — other
 * subsystems (WS events, cost events, chat pipeline) drive the store; this
 * component is intentionally a thin dispatcher.
 */
export function SystemOverlays() {
  const connection = useSystemStore((s) => s.connection);
  const budgetWallOpen = useSystemStore((s) => s.budgetWallOpen);
  const midTurn = useSystemStore((s) => s.midTurn);
  const draggingFile = useSystemStore((s) => s.draggingFile);
  const closeBudgetWall = useSystemStore((s) => s.closeBudgetWall);
  const setMidTurn = useSystemStore((s) => s.setMidTurn);

  return (
    <>
      {connection !== "ok" ? <OfflineBanner state={connection} /> : null}
      <BudgetWall open={budgetWallOpen} onClose={closeBudgetWall} />
      {midTurn ? (
        <MidTurnToast kind={midTurn} onDismiss={() => setMidTurn(null)} />
      ) : null}
      <DropOverlay visible={draggingFile} />
      <Toasts />
    </>
  );
}
