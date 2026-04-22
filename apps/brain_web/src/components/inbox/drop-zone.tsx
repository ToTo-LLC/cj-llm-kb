"use client";

import * as React from "react";

import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import { uploadFile } from "@/lib/ingest/upload";
import { triggerIngest } from "@/lib/ingest/url-paste";
import { useInboxStore } from "@/lib/state/inbox-store";
import { useSystemStore } from "@/lib/state/system-store";
import { cn } from "@/lib/utils";

/**
 * DropZone (Plan 07 Task 17) — the big ingest target at the top of the
 * inbox screen.
 *
 * Three states, per the approved mockup:
 *   * idle — centred orb, "Drop anything worth remembering." copy,
 *     "Browse files" + "Paste a URL" buttons, ⌘V hint.
 *   * drag-over — highlighted border and subtle scale. Driven by the
 *     ``drag-over`` suffix class; the test asserts on its presence.
 *   * active-upload — not rendered today (the row is inserted into the
 *     inbox list via ``addOptimistic`` so the progress reveals there).
 *
 * The component itself owns the hidden ``<input type="file">`` that
 * powers the "Browse files" affordance and the inline URL-paste popover.
 */

function optimisticIdFor(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function DropZone(): React.ReactElement {
  const [dragOver, setDragOver] = React.useState(false);
  const [urlOpen, setUrlOpen] = React.useState(false);
  const [urlValue, setUrlValue] = React.useState("");
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);
  const addOptimistic = useInboxStore((s) => s.addOptimistic);
  const updateStatus = useInboxStore((s) => s.updateStatus);
  const pushToast = useSystemStore((s) => s.pushToast);

  const handleFile = React.useCallback(
    (file: File) => {
      const id = optimisticIdFor("upload");
      addOptimistic({
        id,
        source: file.name,
        title: file.name,
        type: "file",
      });
      // Fire-and-forget — the row lives in the inbox list, which is
      // where the UI surfaces progress. Failures flip the row to
      // ``failed`` so the Needs-attention tab surfaces them.
      uploadFile(file)
        .then((res) => {
          updateStatus(id, {
            status: "done",
            progress: 100,
            domain: res.domain,
          });
        })
        .catch((err) => {
          const message =
            err instanceof Error
              ? err.message
              : "Upload failed. Try again in a moment.";
          updateStatus(id, { status: "failed", error: message });
          // Binary files surface a dedicated copy — the proxy returns
          // 415 with ``error: "unsupported_media_type"``.
          const code = (err as { code?: string } | undefined)?.code;
          if (code === "unsupported_media_type") {
            pushToast({
              lead: "PDFs coming soon.",
              msg: "For now, upload text-based files (md, txt, json, yaml).",
              variant: "warn",
            });
            return;
          }
          pushToast({
            lead: "Upload failed.",
            msg: message,
            variant: "danger",
          });
        });
    },
    [addOptimistic, updateStatus, pushToast],
  );

  const onDragEnter: React.DragEventHandler<HTMLDivElement> = (e) => {
    if (e.dataTransfer?.types?.includes("Files")) {
      setDragOver(true);
    }
  };

  const onDragOver: React.DragEventHandler<HTMLDivElement> = (e) => {
    if (e.dataTransfer?.types?.includes("Files")) {
      e.preventDefault();
    }
  };

  const onDragLeave: React.DragEventHandler<HTMLDivElement> = () => {
    setDragOver(false);
  };

  const onDrop: React.DragEventHandler<HTMLDivElement> = (e) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer?.files ?? []);
    if (files.length === 0) return;
    // Day-one: handle one file at a time. Drag-multi support is a Task
    // 25 sweep item.
    handleFile(files[0]);
  };

  const onBrowse = () => {
    fileInputRef.current?.click();
  };

  const onFilePicked: React.ChangeEventHandler<HTMLInputElement> = (e) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    // Clear so the same file can be re-selected.
    e.target.value = "";
  };

  const submitUrl = async () => {
    const text = urlValue.trim();
    if (!text) return;
    const id = optimisticIdFor("paste");
    addOptimistic({
      id,
      source: text,
      title: text,
      type: "url",
    });
    setUrlOpen(false);
    setUrlValue("");
    try {
      const res = await triggerIngest(text);
      const data = res.data as {
        patch_id?: string | null;
        domain?: string | null;
      } | null;
      updateStatus(id, {
        status: "done",
        progress: 100,
        domain: data?.domain ?? null,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ingest failed.";
      updateStatus(id, { status: "failed", error: message });
      pushToast({
        lead: "Ingest failed.",
        msg: message,
        variant: "danger",
      });
    }
  };

  return (
    <div
      data-testid="drop-zone"
      role="group"
      aria-label="Drop zone"
      className={cn(
        "relative flex flex-col items-center gap-3 rounded-2xl border border-dashed border-[var(--hairline)] bg-[var(--surface-1)] px-8 py-12 text-center transition-all",
        dragOver && "drag-over border-[var(--accent)] bg-[var(--accent)]/10 scale-[1.01]",
      )}
      onDragEnter={onDragEnter}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <div
        aria-hidden="true"
        className={cn(
          "h-14 w-14 rounded-full bg-gradient-to-br from-[var(--accent)] to-transparent opacity-70",
          dragOver && "opacity-100",
        )}
      />
      <h2 className="text-xl font-light text-[var(--text)]">
        Drop anything worth remembering.
      </h2>
      <p className="max-w-md text-sm text-[var(--text-muted)]">
        PDFs, URLs, transcripts, tweets, emails. brain classifies and files
        them for you.
      </p>
      <div className="flex items-center gap-2">
        <Button size="lg" onClick={onBrowse}>
          Browse files
        </Button>
        <Popover open={urlOpen} onOpenChange={setUrlOpen}>
          <PopoverTrigger asChild>
            <Button size="lg" variant="outline">
              Paste a URL
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[360px]">
            <div className="flex flex-col gap-2">
              <label
                htmlFor="paste-url-input"
                className="text-[11px] font-medium uppercase tracking-wide text-[var(--text-dim)]"
              >
                URL to ingest
              </label>
              <Input
                id="paste-url-input"
                autoFocus
                placeholder="https://…"
                value={urlValue}
                onChange={(e) => setUrlValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    void submitUrl();
                  }
                }}
              />
              <div className="flex justify-end gap-2">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setUrlOpen(false)}
                >
                  Cancel
                </Button>
                <Button size="sm" onClick={() => void submitUrl()}>
                  Ingest
                </Button>
              </div>
            </div>
          </PopoverContent>
        </Popover>
      </div>
      <div className="text-[11px] text-[var(--text-dim)]">
        or{" "}
        <kbd className="rounded border border-[var(--hairline)] bg-[var(--surface-2)] px-1.5 py-0.5 text-[10px]">
          ⌘
        </kbd>
        <kbd className="rounded border border-[var(--hairline)] bg-[var(--surface-2)] px-1.5 py-0.5 text-[10px]">
          V
        </kbd>{" "}
        anywhere to paste text or a link
      </div>
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        aria-hidden="true"
        onChange={onFilePicked}
      />
    </div>
  );
}
