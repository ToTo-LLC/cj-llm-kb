"use client";

import { useDialogsStore } from "@/lib/state/dialogs-store";

import { DocPickerDialog } from "@/components/draft/doc-picker-dialog";
import { EditApproveDialog } from "./edit-approve-dialog";
import { FileToWikiDialog } from "./file-to-wiki-dialog";
import { ForkDialog } from "./fork-dialog";
import { RejectReasonDialog } from "./reject-reason-dialog";
import { RenameDomainDialog } from "./rename-domain-dialog";
import { TypedConfirmDialog } from "./typed-confirm-dialog";

/**
 * DialogHost — single mount point for app-level dialogs. Lives inside
 * `<AppShell />` so dialogs inherit the theme + app providers, but sits
 * outside route content so dialogs survive navigation.
 *
 * Task 11 landed `reject-reason`, `edit-approve`, `typed-confirm`.
 * Task 19 wired `doc-picker`. Task 20 completes the set with
 * `file-to-wiki`, `fork`, `rename-domain`.
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
    case "file-to-wiki":
      return <FileToWikiDialog {...active} onClose={close} />;
    case "fork":
      return <ForkDialog {...active} onClose={close} />;
    case "rename-domain":
      return <RenameDomainDialog {...active} onClose={close} />;
    default: {
      // Exhaustiveness check — adding a new dialog kind must widen the
      // switch. Without this assignment TypeScript won't flag stale
      // renderer.
      const _exhaustive: never = active;
      void _exhaustive;
      return null;
    }
  }
}
