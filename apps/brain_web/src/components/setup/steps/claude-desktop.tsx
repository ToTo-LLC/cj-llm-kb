"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";

/**
 * Claude Desktop integration step (6 / 6).
 *
 * Checkpoint 3 decision (1) — MCP install from frontend is DEFERRED to a
 * later plan. This screen is informational only: we do NOT add
 * `brain_mcp_install` / `brain_mcp_uninstall` / `brain_mcp_status` tools in
 * Task 13. The tool surface stays at 22.
 *
 * TODO(plan-07 task 25 sweep): revisit. Either add the three MCP tools and
 * wire an "Install MCP" button here, or leave this as a link into Settings →
 * Integrations once that screen ships.
 */
export function ClaudeDesktopStep() {
  const [copied, setCopied] = useState(false);

  async function copyCommand() {
    try {
      await navigator.clipboard.writeText("brain mcp install");
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard may be unavailable (insecure context, etc.). The user
      // can select-and-copy the visible command manually — we surface the
      // fallback by not flipping `copied`.
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-medium tracking-tight">
        Talk to brain from Claude Desktop?
      </h1>
      <p className="text-base leading-relaxed text-muted-foreground">
        brain can expose your vault to Claude Desktop via MCP. You can install
        this later from Settings → Integrations.
      </p>
      <div className="rounded-lg border border-input bg-muted/30 p-4">
        <p className="mb-3 text-sm text-muted-foreground">
          Run this in a terminal whenever you&apos;re ready:
        </p>
        <code className="block rounded bg-background px-3 py-2 font-mono text-xs">
          brain mcp install
        </code>
        <div className="mt-3 flex items-center gap-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={copyCommand}
          >
            {copied ? "Copied!" : "Copy install command"}
          </Button>
          <span className="text-xs text-muted-foreground">
            I&apos;ll do this later
          </span>
        </div>
      </div>
    </div>
  );
}
