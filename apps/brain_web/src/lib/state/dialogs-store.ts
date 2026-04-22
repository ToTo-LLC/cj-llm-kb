"use client";

import { create } from "zustand";

/**
 * Dialog state lives in one Zustand store so any component can pop a dialog
 * without threading props through the shell. Plan 07 Task 11 introduces the
 * first three dialog kinds implemented in `<DialogHost />`: `reject-reason`,
 * `edit-approve`, `typed-confirm`.
 *
 * The other four kinds (`file-to-wiki`, `fork`, `rename-domain`, `doc-picker`)
 * are reserved here as TS-only stubs. Tasks 19 (doc-picker) and 20 (the rest)
 * will implement their components; the host's switch will grow default
 * branches until then.
 *
 * One-dialog-at-a-time invariant: a second `open()` replaces the active
 * dialog rather than stacking. Stacking modals is confusing UX and a
 * keyboard-trap hazard — chain sub-flows via `onConfirm` instead.
 */

// ---------- Reserved future payload types (Tasks 19/20) ----------
// These are named types so the discriminated union stays extensible and
// future tasks can import them rather than rewriting the union. Shapes are
// intentionally minimal; Tasks 19/20 will flesh them out.

export interface FileToWikiResult {
  path: string;
  domain: string;
  type: string;
  frontmatter: string;
  body: string;
}

export interface ThreadMeta {
  id: string;
  title: string;
}

export interface ForkResult {
  mode: string;
  carry: string;
}

export interface DomainMeta {
  slug: string;
  name: string;
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
  // ---- reserved (Tasks 19/20) ----
  | {
      kind: "file-to-wiki";
      msg: { body: string; threadId: string };
      onConfirm: (p: FileToWikiResult) => void;
    }
  | {
      kind: "fork";
      thread: ThreadMeta;
      turnIndex: number;
      onConfirm: (p: ForkResult) => void;
    }
  | {
      kind: "rename-domain";
      domain: DomainMeta;
      onConfirm: (from: string, to: string, rewrite: boolean) => void;
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
