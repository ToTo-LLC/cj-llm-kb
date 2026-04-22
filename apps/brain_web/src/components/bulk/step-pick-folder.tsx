"use client";

/**
 * Step 1 — Pick folder (Plan 07 Task 21).
 *
 * Two entry points:
 *   (a) "Use a path" text input — the canonical Task 21 flow. The user
 *       types a filesystem path the backend can read (localhost + vault
 *       tooling run on the same host). We kick ``brain_bulk_import`` in
 *       dry-run mode, hydrate the store with the returned plan items,
 *       and advance to step 2.
 *   (b) In-browser folder picker (``<input webkitdirectory>``) — a
 *       convenience that reads a folder's metadata (names + sizes) locally
 *       so the user gets instant feedback. The true filesystem scan still
 *       happens server-side via the derived path, which in a browser
 *       context we can only approximate as the folder's ``webkitRelativePath``
 *       prefix. Documented limitation: a full desktop folder-picker
 *       requires the Electron wrap tracked in Plan 08 (Task 25 sweep).
 */

import * as React from "react";
import { Folder, Shield, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { bulkImport } from "@/lib/api/tools";
import {
  useBulkStore,
  type BulkFile,
} from "@/lib/state/bulk-store";
import { useSystemStore } from "@/lib/state/system-store";

function detectType(name: string): BulkFile["type"] {
  const lower = name.toLowerCase();
  if (lower.endsWith(".pdf")) return "pdf";
  if (lower.endsWith(".docx") || lower.endsWith(".doc")) return "doc";
  if (
    lower.endsWith(".png") ||
    lower.endsWith(".jpg") ||
    lower.endsWith(".jpeg") ||
    lower.endsWith(".gif") ||
    lower.endsWith(".webp")
  )
    return "img";
  if (lower.endsWith(".eml") || lower.endsWith(".msg")) return "email";
  if (lower.endsWith(".url")) return "url";
  if (lower === ".ds_store" || lower.endsWith(".sys")) return "sys";
  return "text";
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function planToFiles(plan: Array<Record<string, unknown>>): BulkFile[] {
  return plan.map((item, i) => {
    const name =
      (typeof item.source === "string" && item.source) ||
      (typeof item.path === "string" && item.path) ||
      `file-${i + 1}`;
    const classified =
      typeof item.classified === "string"
        ? (item.classified as string)
        : typeof item.domain === "string"
          ? (item.domain as string)
          : null;
    const confidence =
      typeof item.confidence === "number" ? (item.confidence as number) : null;
    const duplicate = item.duplicate === true;
    const skipRaw = typeof item.skip === "string" ? (item.skip as string) : undefined;
    const size =
      typeof item.size === "string"
        ? (item.size as string)
        : typeof item.size === "number"
          ? formatSize(item.size as number)
          : "";
    const uncertain = confidence != null && confidence < 0.7;
    return {
      id: i + 1,
      name: name.split("/").pop() ?? name,
      type: detectType(name),
      size,
      classified,
      confidence,
      include: !skipRaw,
      duplicate,
      uncertain: uncertain || undefined,
      flagged: classified === "personal" ? ("personal" as const) : undefined,
      skip: skipRaw,
    };
  });
}

function inputToFiles(files: FileList): BulkFile[] {
  const out: BulkFile[] = [];
  for (let i = 0; i < files.length; i++) {
    const f = files.item(i);
    if (!f) continue;
    out.push({
      id: i + 1,
      name: f.name,
      type: detectType(f.name),
      size: formatSize(f.size),
      classified: null,
      confidence: null,
      include: true,
    });
  }
  return out;
}

export function StepPickFolder(): React.ReactElement {
  const pickFolder = useBulkStore((s) => s.pickFolder);
  const pushToast = useSystemStore((s) => s.pushToast);
  const [path, setPath] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  const runDryRun = React.useCallback(
    async (folderPath: string) => {
      setLoading(true);
      try {
        const res = await bulkImport({ folder: folderPath, dry_run: true });
        const plan =
          (res.data?.plan as Array<Record<string, unknown>> | undefined) ?? [];
        pickFolder(folderPath, planToFiles(plan));
      } catch (err) {
        pushToast({
          lead: "Dry-run failed.",
          msg: err instanceof Error ? err.message : "Unknown error.",
          variant: "danger",
        });
      } finally {
        setLoading(false);
      }
    },
    [pickFolder, pushToast],
  );

  const onFolderPick = async (ev: React.ChangeEvent<HTMLInputElement>) => {
    const list = ev.target.files;
    if (!list || list.length === 0) return;
    // Derive folder label from the first file's relative path.
    const first = list.item(0);
    const rel =
      first && "webkitRelativePath" in first
        ? (first as File & { webkitRelativePath: string }).webkitRelativePath
        : "";
    const folderName = rel.split("/")[0] || "(browser folder)";
    pickFolder(folderName, inputToFiles(list));
    // Clear the input so picking the same folder again still fires change.
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const onSubmitPath = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!path.trim()) return;
    await runDryRun(path.trim());
  };

  return (
    <div className="mx-auto flex max-w-xl flex-col items-center text-center">
      <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-[var(--surface-subtle)] text-[var(--text-muted)]">
        <Upload className="h-8 w-8" />
      </div>
      <h1 className="text-2xl font-semibold text-[var(--text)]">
        Import a folder of sources.
      </h1>
      <p className="mt-2 text-sm text-[var(--text-muted)]">
        Point brain at a year of meeting notes, a reading archive, or an old
        Obsidian vault. It runs a dry-run first so nothing lands in your vault
        without review.
      </p>

      <div className="mt-7 flex flex-wrap justify-center gap-3">
        <Button
          size="lg"
          disabled={loading}
          onClick={() => fileInputRef.current?.click()}
          data-testid="pick-folder-btn"
        >
          <Folder className="mr-2 h-4 w-4" /> Pick a folder
        </Button>
        <form onSubmit={onSubmitPath} className="flex items-center gap-2">
          <Input
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="~/Archive/old-vault"
            aria-label="Folder path"
            className="w-[280px]"
            data-testid="path-input"
            disabled={loading}
          />
          <Button
            type="submit"
            variant="secondary"
            size="lg"
            disabled={loading || !path.trim()}
            data-testid="use-path-btn"
          >
            Use a path
          </Button>
        </form>
      </div>

      {/* Hidden input backing the folder-pick button.
          ``webkitdirectory``/``directory`` are non-standard attributes
          (Chrome/Edge/Safari) and not in React's typings, so we spread them
          through a cast rather than tagging the element with @ts-expect-error. */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={onFolderPick}
        data-testid="folder-input"
        {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
      />

      <div className="mt-6 flex items-center gap-2 text-xs text-[var(--text-dim)]">
        <Shield className="h-3 w-3" />
        Files are read from disk — nothing is uploaded to the API until you
        approve.
      </div>
      <p className="mt-4 max-w-md text-[11px] text-[var(--text-dim)]">
        The folder-pick button works for previewing file names locally. For a
        real bulk import, paste the folder&apos;s path in the box above — the
        backend reads files directly from disk. A true desktop folder-picker
        arrives with the Electron wrap in Plan 08.
      </p>
    </div>
  );
}
