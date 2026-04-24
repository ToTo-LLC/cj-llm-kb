"use client";

import * as React from "react";
import { Check, Copy, RefreshCw, Trash2, Wrench, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  brainMcpInstall,
  brainMcpSelftest,
  brainMcpStatus,
  brainMcpUninstall,
  configGet,
} from "@/lib/api/tools";
import { useDialogsStore } from "@/lib/state/dialogs-store";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * PanelIntegrations (Plan 07 Task 22 + Task 25B wiring).
 *
 * Two sections:
 *   1. Claude Desktop status card — wired to the Task 25A MCP tools
 *      (`brain_mcp_status` on mount + `brain_mcp_selftest` / `_install`
 *      / `_uninstall` behind buttons). Uninstall flows through a typed
 *      confirm dialog (word = "UNINSTALL").
 *   2. Other MCP clients snippet — a ready-to-paste JSON block with a
 *      Copy button (clipboard integration).
 */

// The default install command expected by the backend. Mirrors the CLI
// `brain mcp install` default — `python -m brain_mcp`. Callers can edit
// the Claude Desktop config manually if they need something different.
const DEFAULT_INSTALL_COMMAND = "python";
const DEFAULT_INSTALL_ARGS = ["-m", "brain_mcp"];

/**
 * Build the JSON snippet Cursor / Zed / Continue paste into their MCP config
 * file. Plan 09 Task 11 QA sweep caught that `~` does not expand inside
 * subprocess env vars — the tilde is passed literal to Python and
 * `Path("~/Documents/brain").exists()` returns False. We resolve the actual
 * vault path via `brain_config_get("vault_path")` on mount, then fall back
 * to the literal tilde with an explicit note so the user knows to swap it.
 */
const FALLBACK_VAULT_PATH = "~/Documents/brain";

function buildMcpSnippet(vaultPath: string): string {
  return `"brain": {
  "command": "python",
  "args": ["-m", "brain_mcp"],
  "env": {
    "BRAIN_VAULT_ROOT": "${vaultPath}",
    "BRAIN_ALLOWED_DOMAINS": "research,work"
  }
}`;
}

interface McpStatus {
  status: string;
  config_path: string;
  config_exists: boolean;
  entry_present: boolean;
  executable_resolves: boolean;
  command: string | null;
}

interface SelftestResult {
  ok: boolean;
  status: string;
  config_exists: boolean;
  entry_present: boolean;
  executable_resolves: boolean;
}

export function PanelIntegrations(): React.ReactElement {
  return (
    <div className="flex flex-col gap-6">
      <ClaudeDesktopCard />
      <OtherClientsCard />
    </div>
  );
}

function ClaudeDesktopCard(): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const openDialog = useDialogsStore((s) => s.open);

  const [status, setStatus] = React.useState<McpStatus | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [selftesting, setSelftesting] = React.useState(false);
  const [selftestResult, setSelftestResult] =
    React.useState<SelftestResult | null>(null);
  const [installing, setInstalling] = React.useState(false);

  const loadStatus = React.useCallback(async () => {
    try {
      const r = await brainMcpStatus();
      const d = r.data;
      if (d) {
        setStatus({
          status: d.status,
          config_path: d.config_path,
          config_exists: d.config_exists,
          entry_present: d.entry_present,
          executable_resolves: d.executable_resolves,
          command: d.command,
        });
      }
    } catch (err) {
      pushToast({
        lead: "Couldn't read MCP status.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    } finally {
      setLoading(false);
    }
    // pushToast stays out of the dep list — stable store ref. Reducing
    // effect churn avoids clobbering local state right after a user
    // action.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  React.useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const handleSelftest = async () => {
    if (selftesting) return;
    setSelftesting(true);
    setSelftestResult(null);
    try {
      const r = await brainMcpSelftest();
      const d = r.data;
      if (d) {
        setSelftestResult({
          ok: d.ok,
          status: d.status,
          config_exists: d.config_exists,
          entry_present: d.entry_present,
          executable_resolves: d.executable_resolves,
        });
      }
    } catch (err) {
      setSelftestResult({
        ok: false,
        status: "failed",
        config_exists: false,
        entry_present: false,
        executable_resolves: false,
      });
      pushToast({
        lead: "Self-test failed.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    } finally {
      setSelftesting(false);
    }
  };

  const handleRegenerate = async () => {
    if (installing) return;
    setInstalling(true);
    try {
      await brainMcpInstall({
        command: DEFAULT_INSTALL_COMMAND,
        args: DEFAULT_INSTALL_ARGS,
      });
      pushToast({
        lead: "MCP config regenerated.",
        msg: "Restart Claude Desktop to pick up the new entry.",
        variant: "success",
      });
      void loadStatus();
    } catch (err) {
      pushToast({
        lead: "Couldn't regenerate config.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    } finally {
      setInstalling(false);
    }
  };

  const handleUninstall = () => {
    openDialog({
      kind: "typed-confirm",
      title: "Uninstall brain from Claude Desktop?",
      body:
        "This removes the brain entry from Claude Desktop's config. A timestamped backup of the prior config is written — you can reinstall with Regenerate at any time.",
      word: "UNINSTALL",
      danger: true,
      onConfirm: async () => {
        try {
          await brainMcpUninstall();
          pushToast({
            lead: "Uninstalled.",
            msg: "Restart Claude Desktop to drop the brain entry.",
            variant: "success",
          });
          void loadStatus();
        } catch (err) {
          pushToast({
            lead: "Uninstall failed.",
            msg: err instanceof Error ? err.message : "Unknown error.",
            variant: "danger",
          });
        }
      },
    });
  };

  const pillColour =
    status?.status === "ok"
      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
      : "border-amber-500/40 bg-amber-500/10 text-amber-200";
  const pillLabel =
    status?.status === "ok" ? "Installed" : "Not installed";

  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
        Claude Desktop
      </h2>

      <div
        data-testid="claude-desktop-card"
        className="flex flex-col gap-3 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] p-4"
      >
        <div className="flex items-start gap-3">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-[var(--text)]">
                MCP status
              </span>
              <span
                data-testid="mcp-status-pill"
                className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${pillColour}`}
              >
                {loading ? "Checking…" : pillLabel}
              </span>
            </div>
            {status ? (
              <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[11px]">
                <dt className="text-[var(--text-dim)]">Config path</dt>
                <dd
                  className="truncate font-mono text-[var(--text-muted)]"
                  title={status.config_path}
                >
                  {status.config_path}
                </dd>
                <dt className="text-[var(--text-dim)]">Config exists</dt>
                <dd className="text-[var(--text-muted)]">
                  {status.config_exists ? "yes" : "no"}
                </dd>
                <dt className="text-[var(--text-dim)]">Entry present</dt>
                <dd className="text-[var(--text-muted)]">
                  {status.entry_present ? "yes" : "no"}
                </dd>
                <dt className="text-[var(--text-dim)]">Executable resolves</dt>
                <dd className="text-[var(--text-muted)]">
                  {status.executable_resolves ? "yes" : "no"}
                </dd>
                {status.command && (
                  <>
                    <dt className="text-[var(--text-dim)]">Command</dt>
                    <dd
                      className="truncate font-mono text-[var(--text-muted)]"
                      title={status.command}
                    >
                      {status.command}
                    </dd>
                  </>
                )}
              </dl>
            ) : (
              <p className="mt-1 text-[11px] text-[var(--text-muted)]">
                {loading
                  ? "Probing Claude Desktop config…"
                  : "Status unavailable."}
              </p>
            )}
          </div>
        </div>

        {selftestResult && (
          <div
            data-testid="selftest-result"
            className={`flex items-start gap-2 rounded border p-2 text-[11px] ${
              selftestResult.ok
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100"
                : "border-red-500/30 bg-red-500/10 text-red-200"
            }`}
          >
            {selftestResult.ok ? (
              <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
            ) : (
              <X className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" />
            )}
            <span>
              Self-test {selftestResult.ok ? "passed" : "failed"} — config
              exists: {selftestResult.config_exists ? "yes" : "no"}, entry
              present: {selftestResult.entry_present ? "yes" : "no"},
              executable resolves:{" "}
              {selftestResult.executable_resolves ? "yes" : "no"}.
            </span>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void handleSelftest()}
            disabled={selftesting}
            className="gap-1.5"
          >
            <Wrench className="h-3.5 w-3.5" />
            {selftesting ? "Running…" : "Run self-test"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void handleRegenerate()}
            disabled={installing}
            className="gap-1.5"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            {installing ? "Regenerating…" : "Regenerate config"}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleUninstall}
            className="gap-1.5 text-red-400 hover:text-red-300"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Uninstall
          </Button>
        </div>
      </div>
    </section>
  );
}

function OtherClientsCard(): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const [copied, setCopied] = React.useState(false);
  const [vaultPath, setVaultPath] = React.useState<string | null>(null);

  // Resolve the actual vault path on mount so the emitted snippet is
  // paste-ready (no tilde expansion trap for subprocess env vars).
  React.useEffect(() => {
    let cancelled = false;
    configGet({ key: "vault_path" })
      .then((r) => {
        if (!cancelled) {
          const v = r.data?.value;
          setVaultPath(typeof v === "string" ? v : null);
        }
      })
      .catch(() => {
        if (!cancelled) setVaultPath(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const resolvedPath = vaultPath ?? FALLBACK_VAULT_PATH;
  const snippet = buildMcpSnippet(resolvedPath);
  // Only warn about the tilde when we actually had to fall back to it.
  const showTildeWarning = vaultPath === null;

  const copy = async () => {
    try {
      if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
        await navigator.clipboard.writeText(snippet);
      } else {
        // Last-resort fallback for environments without the Clipboard API.
        const ta = document.createElement("textarea");
        ta.value = snippet;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setCopied(true);
      pushToast({
        lead: "Snippet copied.",
        msg: "Paste into your MCP client's config file.",
        variant: "success",
      });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      pushToast({
        lead: "Copy failed.",
        msg: "Your browser blocked clipboard access.",
        variant: "danger",
      });
    }
  };

  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
        Other MCP clients
      </h2>
      <p className="mb-3 text-[11px] text-[var(--text-muted)]">
        Cursor, Zed, Continue, and any other MCP-aware tool can reach
        this brain with the snippet below. Paste into the client&apos;s MCP
        config file.
      </p>

      <div className="relative rounded-md border border-[var(--hairline)] bg-[var(--surface-2)]">
        <pre
          data-testid="mcp-snippet"
          className="overflow-x-auto p-3 pr-12 font-mono text-[11px] text-[var(--text)]"
        >
          {snippet}
        </pre>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void copy()}
          className="absolute right-2 top-2 gap-1 text-[10px]"
          aria-label="Copy snippet"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3" /> Copied
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" /> Copy
            </>
          )}
        </Button>
      </div>

      {showTildeWarning && (
        <p
          data-testid="mcp-snippet-tilde-warning"
          className="mt-2 text-[10px] text-amber-500 dark:text-amber-300"
        >
          Replace <code className="font-mono">~/Documents/brain</code> with the
          absolute path shown in Settings → General if your vault is elsewhere
          (Python subprocesses don&apos;t expand <code className="font-mono">~</code>).
        </p>
      )}

      <p className="mt-2 text-[10px] text-[var(--text-dim)]">
        Tip: change <code className="font-mono">BRAIN_ALLOWED_DOMAINS</code>{" "}
        per-client to restrict what a given integration can read or write.
      </p>
    </section>
  );
}
