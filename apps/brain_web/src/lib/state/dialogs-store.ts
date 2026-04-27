"use client";

import { create } from "zustand";

/**
 * Dialog state lives in one Zustand store so any component can pop a dialog
 * without threading props through the shell. Plan 07 Task 11 introduces the
 * first three dialog kinds implemented in `<DialogHost />`: `reject-reason`,
 * `edit-approve`, `typed-confirm`. Task 19 adds `doc-picker`. Task 20 adds
 * `file-to-wiki`, `fork`, `rename-domain` with full typed payloads.
 *
 * One-dialog-at-a-time invariant: a second `open()` replaces the active
 * dialog rather than stacking. Stacking modals is confusing UX and a
 * keyboard-trap hazard — chain sub-flows via `onConfirm` instead.
 */

// ---------- Shared payload types ----------

/** FileToWiki submit callback payload. */
export interface FileToWikiResult {
  path: string;
  domain: string;
  type: string;
  frontmatter: string;
  body: string;
}

/** Domain metadata used by the RenameDomain dialog. */
export interface DomainMeta {
  id: string;
  name: string;
  count: number;
}

// ---------- Active-dialog union ----------

export type DialogKind =
  | {
      kind: "reject-reason";
      patchId: string;
      targetPath: string;
      onConfirm: (reason: string) => void;
    }
  | {
      kind: "edit-approve";
      patchId: string;
      targetPath: string;
      before: string;
      after: string;
      onConfirm: (edited: string) => void;
    }
  | {
      kind: "typed-confirm";
      title: string;
      eyebrow?: string;
      body: string;
      word: string;
      danger?: boolean;
      onConfirm: () => void;
    }
  | {
      kind: "file-to-wiki";
      /** Chat message being filed — body is the raw markdown, threadId is
       *  the source thread so frontmatter can stamp ``source_thread:``. */
      msg: { body: string; threadId: string };
      /** Source thread id (dialog prefers this if set, else falls back to
       *  ``msg.threadId``). */
      threadId?: string;
      /** Primary domain of the source thread — seeds the domain selector. */
      defaultDomain?: string;
      /** Optional — fires after ``proposeNote`` succeeds. */
      onConfirm?: (p: FileToWikiResult) => void;
    }
  | {
      kind: "fork";
      /** Source thread id — passed straight through to ``brain_fork_thread``. */
      threadId: string;
      /** 0-based turn index to fork from. */
      turnIndex: number;
      /** Short prose summary of the last turn, purely for dialog context. */
      summary?: string;
    }
  | {
      kind: "rename-domain";
      domain: DomainMeta;
      /** Plan 10 Task 6: invoked after a successful rename so the host
       *  list (Settings → Domains, topbar scope picker) can refresh. */
      onRenamed?: () => void;
    }
  | {
      kind: "doc-picker";
      /** Invoked when the user picks a vault document from the list. */
      onPick: (path: string) => void;
      /**
       * Invoked when the user chooses the "start a blank scratch doc"
       * option. The picker itself generates the path (using the active
       * scope + today's date); the caller only needs to read it back
       * here and hand it to ``draft-store.openDoc``.
       */
      onNewBlank: (path: string) => void;
    };

export interface DialogsState {
  active: DialogKind | null;
  /** Replaces any currently-active dialog (one-at-a-time rule). */
  open: (d: DialogKind) => void;
  /** Clears the active dialog. Safe to call when nothing is open. */
  close: () => void;
}

export const useDialogsStore = create<DialogsState>((set) => ({
  active: null,
  open: (d) => set({ active: d }),
  close: () => set({ active: null }),
}));
