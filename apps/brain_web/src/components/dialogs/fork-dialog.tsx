"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { GitFork, Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { Modal } from "./modal";
import { forkThread } from "@/lib/api/tools";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * ForkDialog (Plan 07 Task 20).
 *
 * Forks a chat thread at a specific turn into a new thread. Per D3a the
 * dialog collects:
 *
 *   - carry mode: ``summary`` (default, Haiku-cheap recap), ``full``
 *     (verbatim), ``none`` (fresh start)
 *   - mode: ``ask`` / ``brainstorm`` / ``draft`` — often the whole reason
 *     someone forks
 *   - optional title hint
 *
 * Submit → ``brain_fork_thread({source_thread_id, turn_index, carry, mode,
 * title_hint})`` → navigate to ``/chat/<new_thread_id>``.
 *
 * Scope selection was in the v3 mockup but the backend ``fork_thread`` tool
 * inherits scope from the source thread — exposing it as a picker would be
 * misleading until Plan 09 wires a real scope-override. Deferred to Task 25.
 */

type CarryMode = "summary" | "full" | "none";
type ChatMode = "ask" | "brainstorm" | "draft";

const CARRY_OPTIONS: ReadonlyArray<{
  value: CarryMode;
  label: string;
  hint: string;
}> = [
  {
    value: "summary",
    label: "Summary",
    hint: "A ~400-token recap of the source thread is prepended — cheap, keeps continuity.",
  },
  {
    value: "full",
    label: "Full thread",
    hint: "Full transcript is copied. Costs more on the first turn; perfect recall.",
  },
  {
    value: "none",
    label: "Fresh start",
    hint: "Clean slate — only the mode carries over.",
  },
];

const MODE_OPTIONS: ReadonlyArray<{ value: ChatMode; label: string }> = [
  { value: "ask", label: "Ask" },
  { value: "brainstorm", label: "Brainstorm" },
  { value: "draft", label: "Draft" },
];

export interface ForkDialogProps {
  kind: "fork";
  /** Source thread id — passed straight through to ``brain_fork_thread``. */
  threadId: string;
  /** 0-based turn index to fork from. */
  turnIndex: number;
  /** Short prose summary of the last turn — purely for dialog context. */
  summary?: string;
  onClose: () => void;
}

function truncate(s: string, n: number): string {
  return (s || "").length > n ? (s || "").slice(0, n) + "…" : s || "";
}

export function ForkDialog({
  threadId,
  turnIndex,
  summary,
  onClose,
}: ForkDialogProps) {
  const router = useRouter();
  const [carry, setCarry] = React.useState<CarryMode>("summary");
  const [mode, setMode] = React.useState<ChatMode>("ask");
  const [title, setTitle] = React.useState<string>("");
  const [submitting, setSubmitting] = React.useState(false);

  const carryHint = React.useMemo(
    () => CARRY_OPTIONS.find((o) => o.value === carry)?.hint ?? "",
    [carry],
  );

  const handleSubmit = React.useCallback(async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      const resp = await forkThread({
        source_thread_id: threadId,
        turn_index: turnIndex,
        carry,
        mode,
        title_hint: title.trim() ? title.trim() : null,
      });
      const newId = resp.data?.new_thread_id;
      if (newId) {
        useSystemStore.getState().pushToast({
          lead: "Thread forked.",
          msg: `Jumping to the new thread.`,
          variant: "success",
        });
        router.push(`/chat/${newId}`);
      }
      onClose();
    } catch (err) {
      useSystemStore.getState().pushToast({
        lead: "Couldn't fork thread.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
      setSubmitting(false);
    }
  }, [submitting, threadId, turnIndex, carry, mode, title, router, onClose]);

  return (
    <Modal
      open
      onClose={onClose}
      eyebrow={`Fork from turn ${turnIndex + 1}`}
      title="Start a fresh thread from this point."
      description="Pick how much context carries over, which mode to start in, and an optional title."
      width={620}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={submitting}
            className="gap-2"
          >
            <GitFork className="h-3.5 w-3.5" /> Fork thread
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {summary ? (
          <div className="rounded-md border border-border bg-muted/40 p-3 text-xs">
            <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">
              Forking from
            </div>
            <div className="text-foreground">{truncate(summary, 220)}</div>
            <div className="mt-1.5 text-[10px] text-muted-foreground">
              turn {turnIndex + 1}
            </div>
          </div>
        ) : null}

        <div>
          <label className="mb-1.5 block text-xs uppercase tracking-wider text-muted-foreground">
            New mode
          </label>
          <div
            className="inline-flex gap-0 rounded-md border border-border p-0.5"
            role="radiogroup"
            aria-label="New mode"
          >
            {MODE_OPTIONS.map((m) => {
              const active = mode === m.value;
              return (
                <button
                  key={m.value}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => setMode(m.value)}
                  className={cn(
                    "rounded px-3 py-1 text-xs transition-colors",
                    active
                      ? "bg-primary/15 text-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {m.label}
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <label className="mb-1.5 block text-xs uppercase tracking-wider text-muted-foreground">
            Carry context
          </label>
          <div
            className="inline-flex gap-0 rounded-md border border-border p-0.5"
            role="radiogroup"
            aria-label="Carry context"
          >
            {CARRY_OPTIONS.map((o) => {
              const active = carry === o.value;
              return (
                <button
                  key={o.value}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => setCarry(o.value)}
                  className={cn(
                    "rounded px-3 py-1 text-xs transition-colors",
                    active
                      ? "bg-primary/15 text-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {o.label}
                </button>
              );
            })}
          </div>
          <div className="mt-2 flex items-start gap-2 text-[11px] text-muted-foreground">
            <Info className="mt-0.5 h-3 w-3 shrink-0" />
            <span>{carryHint}</span>
          </div>
        </div>

        <div>
          <label
            htmlFor="fork-title"
            className="mb-1.5 block text-xs uppercase tracking-wider text-muted-foreground"
          >
            Title
          </label>
          <Input
            id="fork-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="brain will name it after your first message if empty"
            autoFocus
          />
        </div>
      </div>
    </Modal>
  );
}
