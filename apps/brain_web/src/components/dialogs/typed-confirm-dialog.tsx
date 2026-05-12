"use client";

import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "./modal";

/**
 * TypedConfirmDialog — "type DELETE to confirm" pattern. Used by Settings
 * flows that are destructive or hard to undo: delete domain, restore
 * backup, uninstall, orphan delete (Plan 22 T15).
 *
 * The confirm button is disabled until the user's input is EXACTLY equal to
 * `word`. Case-sensitive on purpose — the typed phrase should be hard to
 * fat-finger past.
 *
 * Plan 22 T15: extended with an optional ``headerSlot`` prop so callers
 * can render a per-note card (or per-batch summary card) ABOVE the body
 * paragraph. The slot is rendered between the description and the body
 * paragraph — matches the mockup at ``docs/design/plan-22/modal-orphan-delete.md``
 * where the warn-icon + filename card sits above the explanatory body.
 * Backward-compatible (no slot → identical layout to pre-T15).
 */

export interface TypedConfirmDialogProps {
  kind: "typed-confirm";
  title: string;
  eyebrow?: string;
  body: string;
  word: string;
  /** Flips the confirm button to the danger variant + destructive copy. */
  danger?: boolean;
  /**
   * Optional content rendered ABOVE the body paragraph. Plan 22 T15 added
   * this so the orphan-delete modal can render a warn-icon note card
   * (single mode) or a batch summary card (bulk mode) without duplicating
   * the input-state + typed-confirm logic. Use ``role="group"`` +
   * ``aria-label`` on the slot's root for screen reader semantics — see
   * ``orphan-delete-modal.tsx``'s ``buildHeaderSlot`` for the canonical
   * example. Stays ``undefined`` for the original delete-domain / backup-
   * restore / uninstall callers.
   */
  headerSlot?: React.ReactNode;
  onConfirm: () => void;
  onClose: () => void;
}

export function TypedConfirmDialog({
  title,
  eyebrow,
  body,
  word,
  danger = false,
  headerSlot,
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
      {headerSlot ? <div className="mb-3">{headerSlot}</div> : null}
      <p className="mb-3 text-muted-foreground">{body}</p>
      <label className="mb-1.5 block text-xs uppercase tracking-wider text-muted-foreground">
        Type{" "}
        <code className="text-[var(--tt-cyan)]">{word}</code>
        {" "}to confirm
      </label>
      {/*
        Plan 14 Task 3 a11y populated-state fix: was ``text-destructive``
        (= ``--brand-ember`` = ``#C64B2E``). On ``--surface-1`` (#0d0d0c
        dark mode) the contrast is 4.11:1, failing WCAG 2.2 AA 4.5:1 for
        small (12px) text. ``--tt-cyan`` is theme-aware (dark = #E06A4A
        bright, light = #C64B2E ember) and was nudged in Plan 13 Task 6
        to clear AA on both surfaces. Same single-source-of-truth pattern
        Plan 14 Task 5 (#C3) applies to ``.prose a``.
      */}
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
