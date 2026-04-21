"use client";

import * as React from "react";

import { Button } from "@/components/ui/button";
import { Modal } from "@/components/dialogs/modal";
import { budgetOverride } from "@/lib/api/tools";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * BudgetWall — blocking modal the chat pipeline pops when a daily LLM spend
 * cap is hit. Shows:
 *   - Today's spend versus the cap (title).
 *   - By-mode breakdown (Ask / Brainstorm / Draft / Ingest).
 *   - Heaviest turn hint (title + tool-calls + tokens + cost).
 *   - Cheaper-model hint (Sonnet vs Haiku).
 *
 * Footer:
 *   - "Wait it out" → `onClose`.
 *   - "Raise cap by $5 for today" → calls `budgetOverride({amount_usd: 5,
 *     duration_hours: 24})`, pushes a `Cap raised.` toast, then closes.
 *
 * ## Data source
 *
 * Cost data flows in via `data` (typed `BudgetWallData`). For Plan 07 Task
 * 12 we do NOT wire React Query — Task 16/21 will. Until then callers can
 * either pass `data` explicitly or rely on the bundled `MOCK_DATA` fallback
 * so tests + storybook render without a query client.
 */

export interface BudgetWallData {
  costToday: number;
  budget: number;
  byMode: {
    ask: number;
    brainstorm: number;
    draft: number;
    ingest: number;
  };
  heaviestTurn: {
    title: string;
    toolCalls: number;
    tokens: number;
    cost: number;
  };
}

const MOCK_DATA: BudgetWallData = {
  costToday: 2.82,
  budget: 3.0,
  byMode: {
    ask: 1.04,
    brainstorm: 0.38,
    draft: 0.92,
    ingest: 0.48,
  },
  heaviestTurn: {
    title: "Cross-link April stall-pattern calls",
    toolCalls: 12,
    tokens: 48_000,
    cost: 0.31,
  },
};

export interface BudgetWallProps {
  open: boolean;
  onClose: () => void;
  /** Defaults to `MOCK_DATA` — see module docstring. */
  data?: BudgetWallData;
}

function formatUsd(n: number): string {
  return `$${n.toFixed(2)}`;
}

function formatTokens(n: number): string {
  return n >= 1000 ? `${Math.round(n / 1000)}k tokens` : `${n} tokens`;
}

export function BudgetWall({ open, onClose, data = MOCK_DATA }: BudgetWallProps) {
  const pushToast = useSystemStore((s) => s.pushToast);
  const [raising, setRaising] = React.useState(false);

  const handleRaise = async () => {
    setRaising(true);
    try {
      const res = await budgetOverride({ amount_usd: 5, duration_hours: 24 });
      const newCap = res?.data?.amount_usd ?? data.budget + 5;
      pushToast({
        lead: "Cap raised.",
        msg: `Today's cap is now ${formatUsd(newCap)}`,
        variant: "success",
      });
      onClose();
    } catch (err) {
      pushToast({
        lead: "Couldn't raise cap.",
        msg: err instanceof Error ? err.message : "Unknown error — try again.",
        variant: "danger",
      });
    } finally {
      setRaising(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      eyebrow="Daily spend cap hit"
      title={`${formatUsd(data.costToday)} used of ${formatUsd(data.budget)}.`}
      description="brain paused all LLM calls. Raise the cap, wait for the day to roll over, or switch models."
      width={600}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Wait it out
          </Button>
          <Button onClick={handleRaise} disabled={raising}>
            {raising ? "Raising…" : "Raise cap by $5 for today"}
          </Button>
        </>
      }
    >
      <p className="mb-4 text-[var(--text-muted,inherit)]">
        brain paused all LLM calls because you hit the hard cap you set.
        Everything you&apos;ve already written is safe. You can raise the cap
        (one-off, resets tomorrow), wait for the clock to roll over, or switch
        to a cheaper model.
      </p>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div>
          <div className="mb-2 text-xs uppercase tracking-wider text-[var(--text-muted,inherit)]">
            This session
          </div>
          <ul className="flex flex-col gap-1 text-sm">
            <li className="flex items-center justify-between border-b border-[var(--hairline,currentColor)]/40 py-1">
              <span>Ask turns</span>
              <span className="tabular-nums">{formatUsd(data.byMode.ask)}</span>
            </li>
            <li className="flex items-center justify-between border-b border-[var(--hairline,currentColor)]/40 py-1">
              <span>Brainstorm turns</span>
              <span className="tabular-nums">{formatUsd(data.byMode.brainstorm)}</span>
            </li>
            <li className="flex items-center justify-between border-b border-[var(--hairline,currentColor)]/40 py-1">
              <span>Draft turns</span>
              <span className="tabular-nums">{formatUsd(data.byMode.draft)}</span>
            </li>
            <li className="flex items-center justify-between py-1">
              <span>Ingest</span>
              <span className="tabular-nums">{formatUsd(data.byMode.ingest)}</span>
            </li>
          </ul>
        </div>

        <div>
          <div className="mb-2 text-xs uppercase tracking-wider text-[var(--text-muted,inherit)]">
            Heaviest turn
          </div>
          <div className="rounded-md border border-[var(--hairline,currentColor)]/40 p-3">
            <div className="font-medium">&quot;{data.heaviestTurn.title}&quot;</div>
            <div className="mt-1 text-xs text-[var(--text-muted,inherit)]">
              {data.heaviestTurn.toolCalls} tool calls ·{" "}
              {formatTokens(data.heaviestTurn.tokens)} ·{" "}
              {formatUsd(data.heaviestTurn.cost)}
            </div>
          </div>

          <div className="mt-4 mb-2 text-xs uppercase tracking-wider text-[var(--text-muted,inherit)]">
            Switch model
          </div>
          <div className="flex flex-col gap-1 text-sm">
            <div className="rounded-md border border-[var(--hairline,currentColor)] bg-[var(--surface-2,transparent)] px-3 py-2">
              Claude Sonnet 4.5{" "}
              <span className="text-xs text-[var(--text-muted,inherit)]">· current</span>
            </div>
            <div className="rounded-md border border-[var(--hairline,currentColor)]/40 px-3 py-2">
              Haiku 4.5{" "}
              <span className="text-xs text-[var(--text-muted,inherit)]">· ~8× cheaper</span>
            </div>
          </div>
        </div>
      </div>
    </Modal>
  );
}
