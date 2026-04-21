"use client";

import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "./modal";

/**
 * TypedConfirmDialog — "type DELETE to confirm" pattern. Used by Settings
 * flows that are destructive or hard to undo: delete domain, restore
 * backup, uninstall.
 *
 * The confirm button is disabled until the user's input is EXACTLY equal to
 * `word`. Case-sensitive on purpose — the typed phrase should be hard to
 * fat-finger past.
 */

export interface TypedConfirmDialogProps {
  kind: "typed-confirm";
  title: string;
  eyebrow?: string;
  body: string;
  word: string;
  /** Flips the confirm button to the danger variant + destructive copy. */
  danger?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

export function TypedConfirmDialog({
  title,
  eyebrow,
  body,
  word,
  danger = false,
  onConfirm,
  onClose,
}: TypedConfirmDialogProps) {
  const [text, setText] = React.useState("");
  const ok = text === word;

  const handleConfirm = () => {
    onConfirm();
    onClose();
  };

  return (
    <Modal
      open
      onClose={onClose}
      eyebrow={eyebrow}
      title={title}
      description={body}
      width={460}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant={danger ? "destructive" : "default"}
            disabled={!ok}
            onClick={handleConfirm}
          >
            {danger ? "Delete permanently" : "Confirm"}
          </Button>
        </>
      }
    >
      <p className="mb-3 text-muted-foreground">{body}</p>
      <label className="mb-1.5 block text-xs uppercase tracking-wider text-muted-foreground">
        Type <code className="text-destructive">{word}</code> to confirm
      </label>
      <Input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={word}
        autoFocus
        className="tracking-wider"
      />
    </Modal>
  );
}
