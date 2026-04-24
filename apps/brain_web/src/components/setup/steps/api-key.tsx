"use client";

import * as React from "react";
import { Check, X } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { brainPingLlm, brainSetApiKey } from "@/lib/api/tools";

export interface ApiKeyStepProps {
  value: string;
  onChange: (value: string) => void;
}

interface PingResult {
  ok: boolean;
  provider: string | null;
  model: string | null;
  latency_ms: number;
  error?: string;
}

/**
 * API-key step (3 / 6). Value passed up to parent — parent persists via the
 * setup bootstrap handshake (no token is required for `/api/token` after the
 * wizard finishes, but `brain_set_api_key` only resolves once the token
 * round-trip is live; the Test button here completes the save + ping in one
 * shot so the user gets a live validation signal before leaving the wizard).
 *
 * Plan 09 Task 11 QA sweep — the Test button now actually tests. Mirrors
 * the pattern in `settings/panel-providers.tsx` (commit `3c228a3` for the
 * underlying `brain_ping_llm` tool, commit Plan 07 Task 25B for the
 * providers panel wiring): save → ping → render ok/fail pill inline.
 */
export function ApiKeyStep({ value, onChange }: ApiKeyStepProps) {
  const [testing, setTesting] = React.useState(false);
  const [ping, setPing] = React.useState<PingResult | null>(null);

  const handleTest = async () => {
    if (!value || testing) return;
    setTesting(true);
    setPing(null);
    try {
      // Save the key first so `brain_ping_llm` can resolve it from
      // `<vault>/.brain/secrets.env`. The plaintext never echoes back —
      // `brain_set_api_key` returns a masked suffix.
      await brainSetApiKey({ provider: "anthropic", api_key: value });
      const res = await brainPingLlm();
      const d = res.data;
      if (d) {
        setPing({
          ok: d.ok,
          provider: d.provider,
          model: d.model,
          latency_ms: d.latency_ms,
          error: d.error,
        });
      }
    } catch (err) {
      setPing({
        ok: false,
        provider: null,
        model: null,
        latency_ms: 0,
        error: err instanceof Error ? err.message : "Unknown error.",
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-medium tracking-tight">Connect a model.</h1>
      <p className="text-base leading-relaxed text-muted-foreground">
        brain runs on Anthropic&apos;s Claude for now. Paste an API key —
        it&apos;s stored only on your machine.
      </p>
      <div className="space-y-2">
        <label
          htmlFor="api-key"
          className="text-sm font-medium text-foreground"
        >
          Anthropic API key
        </label>
        <div className="flex gap-2">
          <Input
            id="api-key"
            type="password"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="sk-ant-…"
          />
          <Button
            type="button"
            variant="outline"
            onClick={() => void handleTest()}
            disabled={!value || testing}
            data-testid="wizard-api-key-test"
          >
            {testing ? "Testing…" : "Test"}
          </Button>
        </div>
        {ping && ping.ok && (
          <div
            data-testid="wizard-ping-ok"
            className="mt-2 inline-flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-[11px] font-medium text-emerald-700 dark:text-emerald-200"
          >
            <Check className="h-3 w-3 text-emerald-500 dark:text-emerald-400" />
            <span>
              ok · {ping.latency_ms}ms
              {ping.model ? ` — ${ping.model}` : ""}
            </span>
          </div>
        )}
        {ping && !ping.ok && (
          <div
            data-testid="wizard-ping-err"
            className="mt-2 flex items-start gap-2 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-700 dark:text-red-200"
          >
            <X className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-500 dark:text-red-400" />
            <span>
              Connection failed{ping.error ? ` — ${ping.error}` : "."}
            </span>
          </div>
        )}
        <p className="text-xs text-muted-foreground">
          Don&apos;t have one?{" "}
          <a
            href="https://console.anthropic.com/account/keys"
            target="_blank"
            rel="noreferrer"
            className="text-primary underline-offset-4 hover:underline"
          >
            Get an API key →
          </a>
        </p>
      </div>
    </div>
  );
}
