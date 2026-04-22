"use client";

import { useDialogsStore } from "@/lib/state/dialogs-store";

import { DocPickerDialog } from "@/components/draft/doc-picker-dialog";
import { EditApproveDialog } from "./edit-approve-dialog";
import { RejectReasonDialog } from "./reject-reason-dialog";
import { TypedConfirmDialog } from "./typed-confirm-dialog";

/**
 * DialogHost — single mount point for app-level dialogs. Lives inside
 * `<AppShell />` so dialogs inherit the theme + app providers, but sits
 * outside route content so dialogs survive navigation.
 *
 * Task 11 implements three kinds: `reject-reason`, `edit-approve`,
 * `typed-confirm`. Task 19 adds `doc-picker`. Task 20 will add the
 * remaining `file-to-wiki`, `fork`, `rename-domain` kinds — they fall
 * through to `default: return null` until then.
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
    case "doc-picker":
      return <DocPickerDialog {...active} onClose={close} />;
    // Task 20 implements file-to-wiki, fork, rename-domain.
    default:
      return null;
  }
}
