"use client";

import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

/**
 * Base Modal. Wraps shadcn's `Dialog` (Radix) with an eyebrow slot above
 * the title and a footer slot underneath the body. Everything shadcn/Radix
 * already handles — focus trap, Esc-to-close, backdrop click, body scroll
 * lock, ARIA — is deferred to the primitive; do NOT reimplement those here.
 *
 * The `open` / `onClose` pair is a thin bridge to Radix's controlled API:
 * `onOpenChange(false)` fires onClose. The wrapper exists so per-dialog
 * components don't each repeat the eyebrow + footer layout.
 */
export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  eyebrow?: string;
  /**
   * Short sentence describing what the dialog does. Always set in real
   * callers — Radix emits an a11y warning when `aria-describedby` is
   * missing. Rendered visually-hidden so we don't redesign every dialog
   * just to satisfy the hint.
   */
  description?: string;
  /** Max-width in px. Defaults to 520 — matches v3 design reject-reason size. */
  width?: number;
  footer?: React.ReactNode;
  children: React.ReactNode;
  /** Optional extra class applied to DialogContent for per-dialog layout. */
  className?: string;
}

export function Modal({
  open,
  onClose,
  title,
  eyebrow,
  description,
  width = 520,
  footer,
  children,
  className,
}: ModalProps) {
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent
        style={{ maxWidth: width }}
        className={cn("gap-3", className)}
      >
        <DialogHeader>
          {eyebrow ? (
            <div className="text-xs uppercase tracking-wider text-muted-foreground">
              {eyebrow}
            </div>
          ) : null}
          <DialogTitle>{title}</DialogTitle>
          {/* Always emit a DialogDescription so Radix's a11y warning stays
              silent. Visually hidden when the caller doesn't provide one. */}
          <DialogDescription className={description ? undefined : "sr-only"}>
            {description ?? title}
          </DialogDescription>
        </DialogHeader>
        <div className="text-sm leading-relaxed">{children}</div>
        {footer ? <DialogFooter>{footer}</DialogFooter> : null}
      </DialogContent>
    </Dialog>
  );
}
