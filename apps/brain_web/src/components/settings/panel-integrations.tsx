"use client";

import * as React from "react";
import { AlertTriangle, Check, Copy } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * PanelIntegrations (Plan 07 Task 22).
 *
 * Two sections:
 *   1. Claude Desktop status card — stubbed until Task 25 adds the
 *      `brain_mcp_status` / `_install` / `_uninstall` / `_selftest` tools.
 *   2. Other MCP clients snippet — a ready-to-paste JSON block with a
 *      Copy button (clipboard integration).
 */

const MCP_SNIPPET = `"brain": {
  "command": "python",
  "args": ["-m", "brain_mcp"],
  "env": {
    "BRAIN_VAULT_ROOT": "~/Documents/brain",
    "BRAIN_ALLOWED_DOMAINS": "research,work"
  }
}`;

export function PanelIntegrations(): React.ReactElement {
  return (
    <div className="flex flex-col gap-6">
      <ClaudeDesktopCard />
      <OtherClientsCard />
    </div>
  );
}

function ClaudeDesktopCard(): React.ReactElement {
  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
        Claude Desktop
      </h2>

      <div
        data-testid="claude-desktop-stub"
        className="flex flex-col gap-3 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] p-4"
      >
        <div className="flex items-start gap-3">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-[var(--text)]">
                MCP status
              </span>
              <span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-300">
                Stubbed
              </span>
            </div>
            <p className="mt-1 text-[11px] text-[var(--text-muted)]">
              Detection + install / uninstall / self-test land in the Task
              25 sweep (new tools: <code className="font-mono">brain_mcp_status</code>,{" "}
              <code className="font-mono">brain_mcp_install</code>,{" "}
              <code className="font-mono">brain_mcp_uninstall</code>,{" "}
              <code className="font-mono">brain_mcp_selftest</code>).
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" disabled title="Pending brain_mcp_selftest">
            Run self-test
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled
            title="Pending brain_mcp_install"
          >
            Regenerate config
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled
            title="Pending brain_mcp_uninstall"
          >
            Uninstall
          </Button>
        </div>

        <div className="flex items-start gap-2 rounded border border-amber-500/20 bg-amber-500/5 p-2 text-[11px] text-amber-100">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />
          <span>
            Once the MCP tools ship, this card will surface the detected
            app version + config path + a live status pill.
          </span>
        </div>
      </div>
    </section>
  );
}

function OtherClientsCard(): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const [copied, setCopied] = React.useState(false);

  const copy = async () => {
    try {
      if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
        await navigator.clipboard.writeText(MCP_SNIPPET);
      } else {
        // Last-resort fallback for environments without the Clipboard API.
        const ta = document.createElement("textarea");
        ta.value = MCP_SNIPPET;
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
          {MCP_SNIPPET}
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

      <p className="mt-2 text-[10px] text-[var(--text-dim)]">
        Tip: change <code className="font-mono">BRAIN_ALLOWED_DOMAINS</code>{" "}
        per-client to restrict what a given integration can read or write.
      </p>
    </section>
  );
}
