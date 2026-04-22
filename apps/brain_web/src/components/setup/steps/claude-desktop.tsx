"use client";

import { useState } from "react";
import { Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { brainMcpInstall } from "@/lib/api/tools";

/**
 * Claude Desktop integration step (6 / 6).
 *
 * Plan 07 Task 25B wiring: the "Install MCP" button now calls
 * `brain_mcp_install` end-to-end. The backend writes the brain entry
 * into Claude Desktop's config with a timestamped backup of the prior
 * contents. Skip is still offered — the user can install later from
 * Settings → Integrations.
 *
 * The default install command mirrors the CLI: `python -m brain_mcp`.
 * The wizard does NOT prompt for a custom command here; Settings →
 * Integrations exposes Regenerate / Uninstall for fine-grained control
 * after install.
 */

const DEFAULT_COMMAND = "python";
const DEFAULT_ARGS = ["-m", "brain_mcp"];

type InstallState = "idle" | "installing" | "done" | "error";

export function ClaudeDesktopStep() {
  const [state, setState] = useState<InstallState>("idle");
  const [errorMsg, setErrorMsg] = useState<string>("");

  async function handleInstall() {
    if (state === "installing" || state === "done") return;
    setState("installing");
    setErrorMsg("");
    try {
      await brainMcpInstall({
        command: DEFAULT_COMMAND,
        args: DEFAULT_ARGS,
      });
      setState("done");
    } catch (err) {
      setState("error");
      setErrorMsg(err instanceof Error ? err.message : "Unknown error.");
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-medium tracking-tight">
        Talk to brain from Claude Desktop?
      </h1>
      <p className="text-base leading-relaxed text-muted-foreground">
        brain can expose your vault to Claude Desktop via MCP. We&apos;ll
        write the entry into Claude Desktop&apos;s config with a
        timestamped backup of the prior contents. You can always
        regenerate or remove it from Settings → Integrations.
      </p>
      <div className="rounded-lg border border-input bg-muted/30 p-4">
        <div className="flex items-center gap-3">
          {state === "done" ? (
            <div className="inline-flex items-center gap-2 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-sm font-medium text-emerald-200">
              <Check className="h-3.5 w-3.5" />
              Installed
            </div>
          ) : (
            <Button
              type="button"
              onClick={handleInstall}
              disabled={state === "installing"}
            >
              {state === "installing" ? "Installing…" : "Install MCP"}
            </Button>
          )}
          <span className="text-xs text-muted-foreground">
            I&apos;ll do this later
          </span>
        </div>

        {state === "error" && (
          <p
            data-testid="mcp-install-error"
            className="mt-3 text-xs text-red-400"
          >
            Install failed: {errorMsg || "unknown error"}. You can retry or
            install from Settings → Integrations.
          </p>
        )}
      </div>
    </div>
  );
}
