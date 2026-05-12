"use client";

import * as React from "react";
import { AlertTriangle, FolderSearch, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  watchFolder,
  type WatchFolderCostEstimate,
  type WatchFolderData,
} from "@/lib/api/tools";
import { useDomains } from "@/lib/hooks/use-domains";
import { useSystemStore } from "@/lib/state/system-store";
import { useWatchedFoldersStore } from "@/lib/state/watched-folders-store";
import { Modal } from "./modal";

/**
 * WatchEnableModal (Plan 22 T15).
 *
 * Implements per ``docs/design/plan-22/modal-watch-enable.md``. The user
 * is opting their vault into the source-canonical contract (D1): the
 * source file is the source of truth, and vault edits to watched-source
 * notes are overwritten on the next source change. The D1 callout
 * paragraph is the load-bearing UX moment — its prose ships VERBATIM
 * from the mockup so the contract is unambiguous when the user clicks
 * "Watch and sync now".
 *
 * Two entry points (D6):
 *   1. Settings → Watched folders → "Watch a new folder" — modal opens
 *      with the folder input empty.
 *   2. Bulk Import success screen → "Watch this folder for changes" —
 *      modal opens with ``prefilledFolder`` + ``prefilledDomain`` props
 *      so the user lands on a ready-to-confirm screen.
 *
 * Cost-estimate panel (Q3=3.A) consumes ``brain_watch_folder`` with
 * ``dry_run=true`` — fires on open AND on input changes (folder /
 * domain / include_subdirs) so the panel always reflects the
 * about-to-fire args. Errors are non-blocking per mockup §"State 4":
 * the user can still confirm.
 *
 * On confirm, fires ``brain_watch_folder`` with ``dry_run=false``.
 * Success → toast + refresh ``useWatchedFoldersStore`` + close modal.
 * Failure → danger toast + modal stays open.
 *
 * Microcopy strings come verbatim from the mockup's "Microcopy" section
 * (lines 142-170). Do NOT paraphrase — Plan 22 D9 lints for drift.
 */

// ---------- Props ----------

export interface WatchEnableModalProps {
  /** Optional pre-filled folder path. Bulk Import bridge passes the
   *  just-imported folder here so the user lands on a ready-to-confirm
   *  screen (D6). When set, the folder input renders read-only and
   *  the eyebrow / title shift to the "BULK IMPORT → WATCH" variant. */
  prefilledFolder?: string;
  /** Optional pre-filled domain slug. Bulk Import bridge passes the
   *  domain the user picked for the bulk import here so the modal
   *  doesn't ask twice. When omitted, the modal defaults to the user's
   *  active domain (or first available). */
  prefilledDomain?: string;
  /** Fired when the user dismisses (Cancel / Esc / backdrop / success). */
  onClose: () => void;
}

// ---------- Helpers ----------

/** Basename helper — extract folder leaf for the success toast lead. */
function basenameOf(folderPath: string): string {
  return folderPath.split(/[/\\]/).filter(Boolean).pop() ?? folderPath;
}

/** Format the cost-estimate body line per mockup §microcopy line 160. */
function formatCostBody(estimate: WatchFolderCostEstimate): string {
  const usd =
    estimate.estimated_usd === null
      ? "n/a (no pricing entry)"
      : `~$${estimate.estimated_usd.toFixed(2)}`;
  return `${estimate.file_count} files found · estimated cost ${usd}`;
}

// ---------- Component ----------

export function WatchEnableModal({
  prefilledFolder,
  prefilledDomain,
  onClose,
}: WatchEnableModalProps): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const { domains, activeDomain } = useDomains();
  const isPrefilled = Boolean(prefilledFolder);

  // Form state. ``folder`` may be the empty string (Settings entry,
  // empty placeholder per mockup §"State 1") or a path (Bulk Import
  // entry per mockup §"State 5"). The Choose-folder button is a
  // placeholder — the OS folder-picker shim ships in Plan 23 (see
  // mockup §"Implementation guidance"); the user can paste a path
  // into the input directly in v1.
  const [folder, setFolder] = React.useState<string>(prefilledFolder ?? "");
  const [domain, setDomain] = React.useState<string>(() => {
    if (prefilledDomain) return prefilledDomain;
    // Plan 23 T2.a — default to ``Config.active_domain`` so the modal
    // pre-fills the dropdown to match the scope chip in the topbar.
    // Pre-T2.a this defaulted to ``domains[0]`` which is typically
    // ``"personal"`` (alphabetical-ish ordering), so a user with
    // ``active_domain="research"`` would land on a personal-domain
    // selection unless they manually changed it — a footgun for the
    // privacy-railed personal scope.
    //
    // Defensive fallbacks: ``activeDomain`` is empty string until the
    // domains store first ``refresh()`` resolves (and may be empty
    // forever against a backend that pre-dates Plan 11 T6). Tests may
    // pre-seed ``domains`` without ``activeDomain``, so the ``domains[0]``
    // fallback preserves existing happy-path behavior. The final
    // ``"research"`` literal is the last-resort default that matches
    // the Plan 22 setup wizard's default domain.
    if (activeDomain) return activeDomain;
    return domains[0]?.slug ?? "research";
  });
  const [includeSubdirs, setIncludeSubdirs] = React.useState<boolean>(true);

  // Cost-estimate state.
  const [estimate, setEstimate] =
    React.useState<WatchFolderCostEstimate | null>(null);
  const [estimating, setEstimating] = React.useState<boolean>(false);
  const [estimateError, setEstimateError] = React.useState<string | null>(null);

  // Already-watched validation surface (mockup §"State 6"). Distinct
  // from estimate error because the user needs a specific recovery
  // path (choose a different folder).
  const [alreadyWatched, setAlreadyWatched] = React.useState<boolean>(false);

  // Confirm in-flight.
  const [confirming, setConfirming] = React.useState<boolean>(false);

  // Update domain default when domains list resolves AFTER first mount
  // (the store's auto-refresh may land after the modal opens). Plan 23
  // T2.a: prefer ``activeDomain`` over ``domains[0]`` so the post-
  // resolve hydration matches the synchronous initial-value path.
  React.useEffect(() => {
    if (!prefilledDomain && domains.length > 0 && !domain) {
      setDomain(activeDomain || domains[0]!.slug);
    }
  }, [activeDomain, domain, domains, prefilledDomain]);

  // Cost-estimate fetch. Fires on mount when ``folder`` is non-empty
  // AND on every input change (folder / domain / include_subdirs).
  // Cancel via AbortController-like flag so a stale response from a
  // prior call doesn't overwrite a fresh one (mockup §"Interaction":
  // "the cost-estimate fetch should be cancelable").
  const fetchEstimate = React.useCallback(
    async (signal: { cancelled: boolean }) => {
      if (!folder) {
        setEstimate(null);
        setEstimating(false);
        setEstimateError(null);
        setAlreadyWatched(false);
        return;
      }
      setEstimating(true);
      setEstimateError(null);
      setAlreadyWatched(false);
      try {
        const response = await watchFolder({
          folder,
          domain,
          include_subdirs: includeSubdirs,
          initial_sync: true,
          dry_run: true,
        });
        if (signal.cancelled) return;
        const data = response.data;
        if (!data) {
          setEstimateError(
            "Couldn't estimate cost. You can still watch this folder; sync will run with normal budget caps.",
          );
          setEstimate(null);
          setEstimating(false);
          return;
        }
        if (data.status === "already_watched") {
          // Mockup §"State 6": validation error inline.
          setAlreadyWatched(true);
          setEstimate(null);
          setEstimating(false);
          return;
        }
        // dry_run branch returns cost_estimate or null (initial_sync=false).
        setEstimate(data.cost_estimate ?? null);
        setEstimating(false);
      } catch (err) {
        if (signal.cancelled) return;
        const msg =
          err instanceof Error ? err.message : "Unknown error.";
        // Mockup §"State 4": non-blocking — user can still confirm.
        setEstimateError(msg);
        setEstimate(null);
        setEstimating(false);
      }
    },
    [folder, domain, includeSubdirs],
  );

  // Re-fire the estimate whenever inputs change. Cleanup flag prevents
  // a stale Promise from overwriting state when the user changes input
  // mid-flight.
  React.useEffect(() => {
    const signal = { cancelled: false };
    void fetchEstimate(signal);
    return () => {
      signal.cancelled = true;
    };
  }, [fetchEstimate]);

  // Confirm — fires the real-run brain_watch_folder.
  const handleConfirm = React.useCallback(async () => {
    if (!folder || alreadyWatched) return;
    setConfirming(true);
    try {
      const response = await watchFolder({
        folder,
        domain,
        include_subdirs: includeSubdirs,
        initial_sync: true,
        dry_run: false,
      });
      const data = response.data;
      const fileCount =
        (data as WatchFolderData | undefined)?.cost_estimate?.file_count ??
        estimate?.file_count ??
        0;
      pushToast({
        lead: `Watching ${basenameOf(folder)}.`,
        msg: `Initial sync running — ${fileCount} files. Track progress in Settings → Watched folders.`,
        variant: "success",
      });
      // Refresh the watched-folders store so the panel + topbar
      // indicator pick up the new row.
      void useWatchedFoldersStore.getState().refresh();
      onClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error.";
      pushToast({
        lead: "Couldn't watch folder.",
        msg,
        variant: "danger",
      });
      setConfirming(false);
    }
  }, [
    alreadyWatched,
    domain,
    estimate,
    folder,
    includeSubdirs,
    onClose,
    pushToast,
  ]);

  const isPersonalDomain = domain === "personal";
  const canConfirm =
    Boolean(folder) && !alreadyWatched && !confirming && !estimating;

  // Confirm button label per mockup §microcopy lines 165-167.
  const confirmLabel = confirming
    ? "Setting up watch…"
    : estimating
      ? "Estimating…"
      : "Watch and sync now";

  // Eyebrow + title swap for Bulk Import entry (mockup §"State 5").
  const eyebrow = isPrefilled ? "BULK IMPORT → WATCH" : "WATCHED FOLDERS";
  const title = isPrefilled
    ? "Watch this folder for ongoing changes"
    : "Watch this folder for changes";

  return (
    <Modal
      open
      onClose={onClose}
      eyebrow={eyebrow}
      title={title}
      description="Brain will mirror this folder's files into your knowledge base and keep them in sync automatically."
      width={560}
      footer={
        <>
          <Button
            variant="ghost"
            onClick={onClose}
            data-testid="watch-enable-cancel"
          >
            Cancel
          </Button>
          <Button
            variant="default"
            disabled={!canConfirm}
            aria-busy={confirming || estimating}
            onClick={() => void handleConfirm()}
            data-testid="watch-enable-confirm"
          >
            {(confirming || estimating) && (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            )}
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Form: Folder + Domain + Include-subfolders */}
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="watch-enable-folder"
            className="text-xs font-medium text-[var(--text)]"
          >
            Folder
          </label>
          <div className="flex items-stretch gap-2">
            <Input
              id="watch-enable-folder"
              value={folder}
              onChange={(e) => setFolder(e.target.value)}
              placeholder="Choose a folder to watch…"
              readOnly={isPrefilled}
              data-testid="watch-enable-folder-input"
              aria-label="Folder to watch"
              className="flex-1 font-mono text-xs"
            />
            {/* Placeholder choose-folder affordance. v1 lets the user
                paste a path; the OS-native folder picker ships in
                Plan 23 (mockup §"Implementation guidance" defers it). */}
            {!isPrefilled && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  // Browser-only: trigger a hidden directory-picker
                  // input. Webkit-only attribute; falls back to manual
                  // path entry in non-supporting browsers (Safari has
                  // partial support). Wrapping in try/catch keeps the
                  // modal stable if the input click is blocked.
                  try {
                    const input = document.createElement("input");
                    input.type = "file";
                    // The `webkitdirectory` attribute is not in the
                    // standard typing; cast through ``unknown`` so the
                    // assignment is type-safe without ``any``.
                    (input as unknown as { webkitdirectory: boolean }).webkitdirectory =
                      true;
                    input.onchange = () => {
                      const first = input.files?.[0];
                      if (first) {
                        // ``webkitRelativePath`` carries the directory
                        // root as the first segment; we use the
                        // browser-supplied root + the parent of the
                        // first file as a best-effort folder path.
                        const rel = first.webkitRelativePath ?? "";
                        const root = rel.split("/")[0] ?? "";
                        if (root) setFolder(root);
                      }
                    };
                    input.click();
                  } catch {
                    // Picker unavailable — user can paste a path.
                  }
                }}
                aria-label="Choose a folder to watch"
                aria-haspopup="dialog"
                data-testid="watch-enable-choose-folder"
                className="gap-1.5"
              >
                <FolderSearch className="h-3.5 w-3.5" aria-hidden="true" />
                Choose folder
              </Button>
            )}
          </div>
          {alreadyWatched && (
            <p
              role="alert"
              data-testid="watch-enable-already-watched"
              className="text-[11px] text-[var(--danger,_#FF4503)]"
            >
              <AlertTriangle
                className="mr-1 inline h-3 w-3"
                aria-hidden="true"
              />
              This folder is already being watched. Choose a different
              folder or manage it in Settings → Watched folders.
            </p>
          )}
        </div>

        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="watch-enable-domain"
            className="text-xs font-medium text-[var(--text)]"
          >
            Domain
          </label>
          <Select value={domain} onValueChange={(v) => setDomain(v)}>
            <SelectTrigger
              id="watch-enable-domain"
              aria-label="Choose the domain for notes from this folder"
              aria-required="true"
              data-testid="watch-enable-domain-select"
              className="h-9 w-full"
            >
              <SelectValue placeholder="Select domain" />
            </SelectTrigger>
            <SelectContent>
              {domains.length === 0 ? (
                // Fallback if the domains store hasn't hydrated yet.
                <SelectItem value="research">research</SelectItem>
              ) : (
                domains.map((d) => (
                  <SelectItem key={d.slug} value={d.slug}>
                    {d.slug}
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
          {isPersonalDomain && (
            <p
              className="text-[11px] text-[var(--text-muted)]"
              data-testid="watch-enable-personal-rail-note"
            >
              <span aria-hidden="true">{"ⓘ "}</span>
              This folder will sync into your personal domain (privacy-railed by
              default — these notes won&rsquo;t appear in default chat scope).
            </p>
          )}
        </div>

        <div className="flex items-start gap-2">
          <Checkbox
            id="watch-enable-include-subdirs"
            checked={includeSubdirs}
            onCheckedChange={(checked) => setIncludeSubdirs(checked === true)}
            aria-label="Include subfolders"
            data-testid="watch-enable-include-subdirs"
            className="mt-0.5"
          />
          <div className="flex flex-col gap-0.5">
            <label
              htmlFor="watch-enable-include-subdirs"
              className="text-xs text-[var(--text)]"
            >
              Include subfolders
            </label>
            <p className="text-[10px] text-[var(--text-dim)]">
              Also watches every folder inside this one.
            </p>
          </div>
        </div>

        {/* D1 callout — the load-bearing UX moment. Prose VERBATIM
            from mockup §"D1 contract paragraph — final agreed wording"
            (lines 172-176). DO NOT paraphrase. */}
        <div
          role="note"
          aria-labelledby="watch-enable-d1-sr"
          data-testid="watch-enable-d1-callout"
          className="rounded-md border-l-[3px] border-[var(--warn,_#E0A03A)] bg-[var(--surface-2)] p-3"
        >
          <span id="watch-enable-d1-sr" className="sr-only">
            Important: overwrite contract
          </span>
          <p className="flex items-start gap-2 text-xs text-[var(--text)]">
            <AlertTriangle
              className="mt-0.5 h-4 w-4 shrink-0"
              style={{ color: "var(--warn, #E0A03A)" }}
              aria-hidden="true"
            />
            <span>
              <strong>Heads-up:</strong> the source file is the source of
              truth. If you edit a note from this folder inside your
              vault, your edits will be overwritten the next time the
              source file changes.
            </span>
          </p>
          <p className="mt-2 pl-6 text-xs text-[var(--text)]">
            Deleting a source file marks its note as an orphan in your
            vault (it <em>isn&rsquo;t deleted</em>). You can review orphans
            in Settings → Orphans.
          </p>
        </div>

        {/* Cost-estimate panel. Renders only when a folder is chosen.
            Mockup §"State 2" / "State 3" / "State 4" — all three
            sub-states share the same container; the inner body swaps. */}
        {folder && !alreadyWatched && (
          <div
            role="status"
            aria-live="polite"
            data-testid="watch-enable-cost-panel"
            className="rounded-md border border-[var(--hairline)] bg-[var(--surface-2)] p-3"
          >
            <div className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
              Initial sync
            </div>
            {estimating && (
              <p
                className="mt-1 flex items-center gap-1.5 text-xs text-[var(--text-muted)]"
                data-testid="watch-enable-cost-loading"
              >
                <Loader2
                  className="h-3 w-3 animate-spin"
                  aria-hidden="true"
                />
                Estimating cost…
              </p>
            )}
            {!estimating && estimateError && (
              <div
                role="alert"
                data-testid="watch-enable-cost-error"
                className="mt-1 text-xs text-[var(--text)]"
              >
                <span aria-hidden="true">{"⚠ "}</span>
                Couldn&rsquo;t estimate cost. You can still watch this folder;
                sync will run with normal budget caps.{" "}
                <button
                  type="button"
                  onClick={() => {
                    const signal = { cancelled: false };
                    void fetchEstimate(signal);
                  }}
                  data-testid="watch-enable-cost-retry"
                  className="underline-offset-2 text-[var(--tt-cyan)] hover:underline"
                >
                  Try again
                </button>
              </div>
            )}
            {!estimating && !estimateError && estimate && (
              <>
                <p
                  className="mt-1 text-xs text-[var(--text)]"
                  data-testid="watch-enable-cost-body"
                >
                  {formatCostBody(estimate)}
                </p>
                {isPrefilled ? (
                  <p className="mt-1 text-[10px] text-[var(--text-dim)]">
                    <span aria-hidden="true">{"ⓘ "}</span>
                    Your initial import already covered these files. Watching
                    means future changes sync automatically.
                  </p>
                ) : (
                  <p className="mt-1 text-[10px] text-[var(--text-dim)]">
                    <span aria-hidden="true">{"ⓘ "}</span>
                    Pulls in all .md / .pdf / .docx files now.
                  </p>
                )}
              </>
            )}
            {!estimating && !estimateError && !estimate && (
              <p className="mt-1 text-xs text-[var(--text-muted)]">
                No estimate available.
              </p>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}
