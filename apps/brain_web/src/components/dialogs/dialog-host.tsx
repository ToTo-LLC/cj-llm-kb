"use client";

import { useDialogsStore } from "@/lib/state/dialogs-store";

import { EditApproveDialog } from "./edit-approve-dialog";
import { RejectReasonDialog } from "./reject-reason-dialog";
import { TypedConfirmDialog } from "./typed-confirm-dialog";

/**
 * DialogHost — single mount point for app-level dialogs. Lives inside
 * `<AppShell />` so dialogs inherit the theme + app providers, but sits
 * outside route content so dialogs survive navigation.
 *
 * Task 11 implements three kinds: `reject-reason`, `edit-approve`,
 * `typed-confirm`. The remaining four kinds in `DialogKind` are TS-only
 * stubs today — they fall through to `default: return null` until Task 19
 * (`doc-picker`) and Task 20 (`file-to-wiki`, `fork`, `rename-domain`)
 * fill them in.
 */
export function DialogHost() {
  const active = useDialogsStore((s) => s.active);
  const close = useDialogsStore((s) => s.close);

  if (!active) return null;

  switch (active.kind) {
    case "reject-reason":
      return <RejectReasonDialog {...active} onClose={close} />;
    case "edit-approve":
      return <EditApproveDialog {...active} onClose={close} />;
    case "typed-confirm":
      return <TypedConfirmDialog {...active} onClose={close} />;
    // Tasks 19/20 implement file-to-wiki, fork, rename-domain, doc-picker.
    default:
      return null;
  }
}
