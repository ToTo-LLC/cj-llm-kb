"use client";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export interface ApiKeyStepProps {
  value: string;
  onChange: (value: string) => void;
}

/**
 * API-key step (3 / 6). Value passed up to parent — Task 13 does not wire
 * `configSet` because the typed-tools surface (Task 9) is frozen at 22 tools
 * and config-set already exists; we just log a TODO here because setup auth
 * bootstrap is its own dance (need a valid token before we can call
 * configSet). Parent captures the value so Task 25 can wire it.
 *
 * The "Test" button is disabled with a tooltip — a real ping needs a working
 * token roundtrip and is deferred to Task 25.
 */
export function ApiKeyStep({ value, onChange }: ApiKeyStepProps) {
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
            disabled
            title="Live key testing comes in a later update"
          >
            Test
          </Button>
        </div>
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
