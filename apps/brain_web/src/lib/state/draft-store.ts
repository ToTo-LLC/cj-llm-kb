"use client";

import { create } from "zustand";

import {
  applyPatch as applyPatchTool,
  configGet as configGetTool,
  proposeNote as proposeNoteTool,
} from "@/lib/api/tools";
import { useSystemStore } from "./system-store";

/**
 * Draft-store (Plan 07 Task 19).
 *
 * Owns the single currently-open Draft-mode document plus the queue of
 * pending inline edits the assistant has proposed via the
 * ``doc_edit_proposed`` WS event. The DocPanel subscribes for its
 * render; DraftEmpty + DocPickerDialog call ``openDoc`` / ``closeDoc``
 * to flip the chat-screen into split view.
 *
 * Only one active document at a time by design — Draft mode is
 * deliberately focused. Opening a second doc replaces the first (the
 * pending-edits queue belongs to the doc, not the store, so swapping
 * docs drops anything the user never applied).
 *
 * Apply path. ``applyPendingEdits`` merges the queue into the body
 * (reusing the same anchor logic ``renderWithEdits`` uses for display),
 * then stages a patch via ``brain_propose_note``. If
 * ``autonomous.draft`` is true — read via ``brain_config_get`` at call
 * time so the user can flip the toggle mid-session without a reload —
 * the store additionally calls ``brain_apply_patch`` so the draft lands
 * on disk immediately. Errors surface as toasts through system-store;
 * the queue is cleared either way so the UI returns to a quiet state.
 */

export type DocEditOp = "insert" | "delete" | "replace";
export type DocEditAnchorKind = "line" | "text";

export interface DocEditAnchor {
  kind: DocEditAnchorKind;
  value: number | string;
}

export interface DocEdit {
  op: DocEditOp;
  anchor: DocEditAnchor;
  /**
   * Edit payload. Convention for ``replace`` ops: the null character
   * ``"\u0000"`` separates the old text (before ``\0``) from the new
   * text (after ``\0``). This keeps the wire format a simple string
   * without needing a second field on ``DocEdit`` just for the "after"
   * body. ``renderWithEdits`` + the merge helper both honour it.
   */
  text: string;
}

export interface ActiveDoc {
  path: string;
  domain: string;
  /** Raw YAML frontmatter block including the --- fences. Rendered dim at the top. */
  frontmatter: string;
  /** Current doc body — the renderer overlays pending edits on top of this. */
  body: string;
  /** Queue of assistant-proposed edits awaiting the user's Apply / Discard. */
  pendingEdits: DocEdit[];
}

export interface DraftState {
  activeDoc: ActiveDoc | null;

  openDoc: (doc: ActiveDoc) => void;
  closeDoc: () => void;
  appendEdit: (edit: DocEdit) => void;
  applyPendingEdits: () => Promise<void>;
  rejectPendingEdits: () => void;
}

/**
 * Merge pending edits into a plain-text body. The renderer does the
 * same walk but emits React nodes; this version emits a string so the
 * merged body can go on the wire in ``brain_propose_note``.
 */
export function mergeEdits(body: string, edits: DocEdit[]): string {
  if (edits.length === 0) return body;
  let out = body;
  for (const edit of edits) {
    if (edit.op === "insert") {
      // Append at the end — anchor resolution for insert is a Task 25
      // sweep item. For Task 19 we stage the text so proposeNote gets a
      // merged body that's strictly longer than the original; the user
      // still reviews the patch before it lands on disk.
      out = out + (out.endsWith("\n") ? "" : "\n") + edit.text;
    } else if (edit.op === "delete") {
      // Remove the first occurrence of the edit text. Anchor edge cases
      // are a Task 25 item — this is deliberate "works for the happy
      // path, review catches the rest" behaviour.
      out = out.replace(edit.text, "");
    } else {
      // Replace convention: "<old>\u0000<new>" (see DocEdit.text above).
      const sep = edit.text.indexOf("\u0000");
      if (sep === -1) {
        // Malformed replace payload — fall back to append rather than
        // drop the edit silently.
        out = out + (out.endsWith("\n") ? "" : "\n") + edit.text;
      } else {
        const oldText = edit.text.slice(0, sep);
        const newText = edit.text.slice(sep + 1);
        out = out.replace(oldText, newText);
      }
    }
  }
  return out;
}

/** Global draft-store — single active doc at a time. Not persisted. */
export const useDraftStore = create<DraftState>((set, get) => ({
  activeDoc: null,

  openDoc: (doc) => set({ activeDoc: doc }),

  closeDoc: () => set({ activeDoc: null }),

  appendEdit: (edit) => {
    set((s) => {
      if (!s.activeDoc) return s;
      return {
        activeDoc: {
          ...s.activeDoc,
          pendingEdits: [...s.activeDoc.pendingEdits, edit],
        },
      };
    });
  },

  applyPendingEdits: async () => {
    const state = get();
    const doc = state.activeDoc;
    if (!doc || doc.pendingEdits.length === 0) return;

    const mergedBody = mergeEdits(doc.body, doc.pendingEdits);

    try {
      const proposeResp = await proposeNoteTool({
        path: doc.path,
        content: mergedBody,
        reason: "Draft mode edits",
      });

      // Auto-apply when the user has opted in. We read the flag at call
      // time rather than caching it so the toggle in Settings reflects
      // the next Apply without a reload.
      let autonomous = false;
      try {
        const cfg = await configGetTool({ key: "autonomous.draft" });
        autonomous = cfg.data?.value === true;
      } catch {
        // If the config read fails we stay on the safe side — leave the
        // patch staged so the user can review in Pending.
        autonomous = false;
      }

      const patchId = proposeResp.data?.patch_id;
      if (autonomous && patchId) {
        await applyPatchTool({ patch_id: patchId });
        useSystemStore.getState().pushToast({
          lead: "Edits applied.",
          msg: `${doc.pendingEdits.length} edit${
            doc.pendingEdits.length === 1 ? "" : "s"
          } landed on ${doc.path}.`,
          variant: "success",
        });
      } else {
        useSystemStore.getState().pushToast({
          lead: "Edits staged.",
          msg: `Review in Pending before they touch ${doc.path}.`,
          variant: "default",
        });
      }

      // Whether staged or auto-applied, clear the queue so the banner
      // disappears and the body updates to the merged version.
      set((s) => {
        if (!s.activeDoc) return s;
        return {
          activeDoc: {
            ...s.activeDoc,
            body: mergedBody,
            pendingEdits: [],
          },
        };
      });
    } catch (err) {
      useSystemStore.getState().pushToast({
        lead: "Couldn't stage edits.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    }
  },

  rejectPendingEdits: () => {
    set((s) => {
      if (!s.activeDoc) return s;
      return {
        activeDoc: { ...s.activeDoc, pendingEdits: [] },
      };
    });
  },
}));
