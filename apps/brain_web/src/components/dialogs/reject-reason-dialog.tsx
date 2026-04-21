"use client";

import * as React from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { Modal } from "./modal";

/**
 * RejectReasonDialog — collects a short human-readable reason when a
 * pending patch is rejected. Five preset chips cover the common cases;
 * a textarea accepts anything else.
 *
 * The dialog is pure-presentational: `onConfirm(reason)` is wired by the
 * caller (DialogHost) to `rejectPatch({ patch_id, reason })` from the
 * typed tools API. Task 16 will wire that path end-to-end when the
 * pending-patches view ships.
 */

const PRESETS: readonly string[] = [
  "Wrong domain",
  "Already noted elsewhere",
  "Source is unreliable",
  "Too speculative",
  "Formatting is off",
];

export interface RejectReasonDialogProps {
  /** Discriminator so the host can spread the active union member in. */
  kind: "reject-reason";
  patchId: string;
  targetPath: string;
  onConfirm: (reason: string) => void;
  onClose: () => void;
}

export function RejectReasonDialog({
  targetPath,
  onConfirm,
  onClose,
}: RejectReasonDialogProps) {
  const [reason, setReason] = React.useState("");

  const handleConfirm = () => {
    onConfirm(reason);
    onClose();
  };

  return (
    <Modal
      open
      onClose={onClose}
      eyebrow={`Reject patch · ${targetPath}`}
      title="Tell brain why."
      description="Pick a preset reason or write your own, then confirm the rejection."
      width={540}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            className="gap-2"
          >
            <X className="h-3.5 w-3.5" /> Reject patch
          </Button>
        </>
      }
    >
      <p className="mb-3 text-muted-foreground">
        Optional, but the next turn uses your reason as feedback. One sentence
        is plenty.
      </p>
      <div className="mb-3 flex flex-wrap gap-2">
        {PRESETS.map((preset) => {
          const active = reason === preset;
          return (
            <button
              key={preset}
              type="button"
              onClick={() => setReason(preset)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs transition-colors",
                active
                  ? "border-primary bg-primary/20 text-foreground"
                  : "border-border bg-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {preset}
            </button>
          );
        })}
      </div>
      <Textarea
        className="h-28 resize-none"
        placeholder="Or in your own words…"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        autoFocus
      />
      <p className="mt-2 text-xs text-muted-foreground">
        Your reason is stored locally in the thread, not sent anywhere.
      </p>
    </Modal>
  );
}
