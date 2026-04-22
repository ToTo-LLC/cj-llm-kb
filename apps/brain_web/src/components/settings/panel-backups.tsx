"use client";

import * as React from "react";
import { Archive, ExternalLink, RotateCcw, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  brainBackupCreate,
  brainBackupList,
  brainBackupRestore,
  type BackupEntry,
} from "@/lib/api/tools";
import { useDialogsStore } from "@/lib/state/dialogs-store";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * PanelBackups (Plan 07 Task 22 + Task 25B wiring).
 *
 * Fully wired against the Task 25A backend tools:
 *   - `brainBackupList` on mount → populates rows (date + size + trigger).
 *   - `brainBackupCreate({trigger: "manual"})` on "Back up now".
 *   - `brainBackupRestore({backup_id, typed_confirm: true})` on confirmed
 *     Restore (typed-confirm word = "RESTORE").
 *   - Reveal renders a `file://` link to the backup tarball. Clicking it
 *     asks the OS to open the file — on Windows the `file://` protocol
 *     works but some shells block the handler; we also show the full
 *     path inline so users can copy it manually as a fallback.
 */

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.valueOf())) return iso;
  return d.toLocaleString();
}

export function PanelBackups(): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const openDialog = useDialogsStore((s) => s.open);

  const [backups, setBackups] = React.useState<BackupEntry[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [creating, setCreating] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await brainBackupList();
        if (cancelled) return;
        setBackups(r.data?.backups ?? []);
      } catch (err) {
        if (cancelled) return;
        pushToast({
          lead: "Couldn't load backups.",
          msg: err instanceof Error ? err.message : "Unknown error.",
          variant: "danger",
        });
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // pushToast is intentionally omitted — a stable ref across renders
    // keeps the effect from re-firing and clobbering local state after a
    // Create / Restore action. The store is mounted for the page lifetime.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCreate = async () => {
    if (creating) return;
    setCreating(true);
    try {
      const res = await brainBackupCreate({ trigger: "manual" });
      const data = res.data;
      if (data) {
        const entry: BackupEntry = {
          backup_id: data.backup_id,
          path: data.path,
          trigger: data.trigger,
          created_at: data.created_at,
          size_bytes: data.size_bytes,
          file_count: data.file_count,
        };
        setBackups((prev) => [entry, ...prev]);
      }
      pushToast({
        lead: "Backup created.",
        msg: `Snapshot ${data?.backup_id ?? ""} ready.`,
        variant: "success",
      });
    } catch (err) {
      pushToast({
        lead: "Backup failed.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    } finally {
      setCreating(false);
    }
  };

  const handleRestore = (b: BackupEntry) => {
    openDialog({
      kind: "typed-confirm",
      title: `Restore backup ${b.backup_id}?`,
      body:
        "This replaces the current vault contents with the snapshot. Your current vault is moved to a timestamped trash directory rather than deleted — nothing is permanently lost.",
      word: "RESTORE",
      danger: true,
      onConfirm: async () => {
        try {
          await brainBackupRestore({
            backup_id: b.backup_id,
            typed_confirm: true,
          });
          pushToast({
            lead: "Vault restored.",
            msg: `Rewound to ${formatWhen(b.created_at)}.`,
            variant: "success",
          });
        } catch (err) {
          pushToast({
            lead: "Restore failed.",
            msg: err instanceof Error ? err.message : "Unknown error.",
            variant: "danger",
          });
        }
      },
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <section>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
              <Archive className="h-3.5 w-3.5" />
              Vault backups
            </h2>
            <p className="mt-1 text-[11px] text-[var(--text-muted)]">
              Scheduled snapshots of the vault, plus on-demand backups.
              Restore rewinds the vault to any listed point; the current
              contents are moved to trash rather than deleted.
            </p>
          </div>
          <Button
            onClick={() => void handleCreate()}
            disabled={creating}
            className="gap-2"
          >
            <Save className="h-3.5 w-3.5" />
            {creating ? "Backing up…" : "Back up now"}
          </Button>
        </div>

        {loading ? (
          <div
            data-testid="backups-loading"
            className="rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] p-4 text-xs text-[var(--text-dim)]"
          >
            Loading backups…
          </div>
        ) : backups.length === 0 ? (
          <div
            data-testid="backups-empty"
            className="rounded-md border border-dashed border-[var(--hairline)] bg-[var(--surface-1)] p-8 text-center"
          >
            <Archive
              aria-hidden="true"
              className="mx-auto mb-3 h-8 w-8 text-[var(--text-dim)]"
            />
            <h3 className="text-sm font-medium text-[var(--text)]">
              No backups yet.
            </h3>
            <p className="mt-1 text-[11px] text-[var(--text-muted)]">
              Click &ldquo;Back up now&rdquo; to capture a snapshot.
            </p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-md border border-[var(--hairline)]">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-[var(--hairline)] bg-[var(--surface-1)] text-[10px] uppercase tracking-wider text-[var(--text-dim)]">
                  <th className="px-3 py-2 text-left">Backup</th>
                  <th className="px-3 py-2 text-left">When</th>
                  <th className="px-3 py-2 text-left">Size</th>
                  <th className="px-3 py-2 text-left">Trigger</th>
                  <th className="px-3 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {backups.map((b) => (
                  <tr
                    key={b.backup_id}
                    className="border-b border-[var(--hairline)] last:border-0"
                    data-testid={`backup-row-${b.backup_id}`}
                  >
                    <td className="px-3 py-2 font-mono text-xs text-[var(--text)]">
                      {b.backup_id}
                    </td>
                    <td className="px-3 py-2 text-xs text-[var(--text-muted)]">
                      {formatWhen(b.created_at)}
                    </td>
                    <td className="px-3 py-2 text-xs text-[var(--text-muted)]">
                      {formatSize(b.size_bytes)}
                    </td>
                    <td className="px-3 py-2 text-xs text-[var(--text-muted)]">
                      {b.trigger}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <div className="inline-flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRestore(b)}
                          className="h-7 gap-1 px-2 text-xs"
                          aria-label={`Restore ${b.backup_id}`}
                        >
                          <RotateCcw className="h-3 w-3" />
                          Restore
                        </Button>
                        <a
                          href={`file://${b.path}`}
                          className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-xs text-[var(--text-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]"
                          aria-label={`Reveal ${b.backup_id}`}
                          title={b.path}
                        >
                          <ExternalLink className="h-3 w-3" />
                          Reveal
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
