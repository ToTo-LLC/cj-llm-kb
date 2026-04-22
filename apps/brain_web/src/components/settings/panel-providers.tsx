"use client";

import * as React from "react";
import { Check, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  brainPingLlm,
  brainSetApiKey,
  configGet,
  configSet,
} from "@/lib/api/tools";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * PanelProviders (Plan 07 Task 22 + Task 25B wiring).
 *
 * Top: Anthropic API key input + Save (→ brain_set_api_key) + Test
 * connection (→ brain_ping_llm). On save success, masks the input and
 * surfaces the masked suffix the backend returns (the plaintext is
 * never echoed back). Test connection renders a green ok pill on
 * ok:true, or inline error text on ok:false / thrown.
 *
 * Bottom: 6-row model-per-stage table. Each row owns a native `<select>`
 * (intentionally simple — shadcn's Radix Select renders through a
 * portal which jsdom doesn't fully model, so keeping this native keeps
 * tests reliable and saves a dependency surface).
 */

interface Stage {
  id: string;
  label: string;
  configKey: string;
  hint: string;
}

const STAGES: readonly Stage[] = [
  { id: "ask", label: "Ask", configKey: "ask_model", hint: "Read-only chat" },
  {
    id: "brainstorm",
    label: "Brainstorm",
    configKey: "brainstorm_model",
    hint: "Ideation + search",
  },
  { id: "draft", label: "Draft", configKey: "draft_model", hint: "Inline doc edits" },
  {
    id: "classify",
    label: "Classify",
    configKey: "classify_model",
    hint: "Domain + type routing",
  },
  {
    id: "summarize",
    label: "Summarize",
    configKey: "summarize_model",
    hint: "Source → notes",
  },
  {
    id: "integrate",
    label: "Integrate",
    configKey: "integrate_model",
    hint: "Merge into vault",
  },
];

const MODEL_OPTIONS: readonly { value: string; label: string }[] = [
  { value: "claude-haiku-4-6", label: "Haiku — cheapest" },
  { value: "claude-sonnet-4-6", label: "Sonnet — balanced" },
  { value: "claude-opus-4-6", label: "Opus — strongest" },
];

export function PanelProviders(): React.ReactElement {
  return (
    <div className="flex flex-col gap-8">
      <ApiKeySection />
      <ModelsSection />
    </div>
  );
}

interface PingResult {
  ok: boolean;
  provider: string | null;
  model: string | null;
  latency_ms: number;
  error?: string;
}

function ApiKeySection(): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const [input, setInput] = React.useState<string>("");
  const [masked, setMasked] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [pinging, setPinging] = React.useState(false);
  const [ping, setPing] = React.useState<PingResult | null>(null);

  const handleSave = async () => {
    if (!input || saving) return;
    setSaving(true);
    try {
      const res = await brainSetApiKey({
        provider: "anthropic",
        api_key: input,
      });
      const maskedVal = res.data?.masked ?? null;
      setMasked(maskedVal);
      setInput("");
      pushToast({
        lead: "API key saved.",
        msg: "Stored in <vault>/.brain/secrets.env.",
        variant: "success",
      });
    } catch (err) {
      pushToast({
        lead: "Couldn't save API key.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (pinging) return;
    setPinging(true);
    setPing(null);
    try {
      const res = await brainPingLlm();
      const data = res.data;
      if (data) {
        setPing({
          ok: data.ok,
          provider: data.provider,
          model: data.model,
          latency_ms: data.latency_ms,
          error: data.error,
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
      setPinging(false);
    }
  };

  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
        Anthropic API
      </h2>

      <label
        htmlFor="api-key"
        className="mb-1.5 block text-[11px] uppercase tracking-wider text-[var(--text-dim)]"
      >
        API key
      </label>
      <div className="flex gap-2">
        <Input
          id="api-key"
          type="password"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={masked ?? "sk-ant-**************qXf2"}
          className="font-mono"
          autoComplete="off"
          spellCheck={false}
        />
        <Button
          variant="default"
          onClick={() => void handleSave()}
          disabled={!input || saving}
        >
          {saving ? "Saving…" : "Save"}
        </Button>
        <Button
          variant="outline"
          onClick={() => void handleTest()}
          disabled={pinging}
        >
          <Check className="h-3.5 w-3.5" />
          {pinging ? "Testing…" : "Test connection"}
        </Button>
      </div>

      {masked && (
        <div
          data-testid="api-key-masked"
          className="mt-3 flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100"
        >
          <Check className="h-3.5 w-3.5 text-emerald-400" />
          <span>
            Saved:{" "}
            <code className="font-mono text-emerald-200">{masked}</code>
          </span>
        </div>
      )}

      {ping && ping.ok && (
        <div
          data-testid="ping-ok-pill"
          className="mt-3 inline-flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-[11px] font-medium text-emerald-200"
        >
          <Check className="h-3 w-3 text-emerald-400" />
          <span>
            Connected — {ping.provider ?? "provider"} / {ping.model ?? "model"}{" "}
            ({ping.latency_ms}ms)
          </span>
        </div>
      )}

      {ping && !ping.ok && (
        <div
          data-testid="ping-err"
          className="mt-3 flex items-start gap-2 rounded-md border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-200"
        >
          <X className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" />
          <span>
            Connection failed{ping.error ? ` — ${ping.error}` : "."}
          </span>
        </div>
      )}
    </section>
  );
}

function ModelsSection(): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const [values, setValues] = React.useState<Record<string, string>>({});

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      const next: Record<string, string> = {};
      for (const stage of STAGES) {
        try {
          const r = await configGet({ key: stage.configKey });
          const v = r.data?.value;
          if (typeof v === "string") next[stage.configKey] = v;
        } catch {
          /* ignore — leave stage empty (defaults fall through). */
        }
      }
      if (!cancelled) setValues((prev) => ({ ...next, ...prev }));
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onChange = React.useCallback(
    async (stage: Stage, next: string) => {
      setValues((s) => ({ ...s, [stage.configKey]: next }));
      try {
        await configSet({ key: stage.configKey, value: next });
        pushToast({
          lead: "Model saved.",
          msg: `${stage.label} → ${next}`,
          variant: "success",
        });
      } catch {
        pushToast({
          lead: "Failed to save.",
          msg: `Could not update ${stage.configKey}.`,
          variant: "danger",
        });
      }
    },
    [pushToast],
  );

  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
        Model per stage
      </h2>
      <p className="mb-3 text-[11px] text-[var(--text-muted)]">
        Tune cost vs. quality per pipeline stage. Higher-tier models cost
        more per call but produce better output.
      </p>

      <div className="overflow-hidden rounded-md border border-[var(--hairline)]">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-[var(--hairline)] bg-[var(--surface-1)] text-[10px] uppercase tracking-wider text-[var(--text-dim)]">
              <th className="px-3 py-2 text-left">Stage</th>
              <th className="px-3 py-2 text-left">Model</th>
              <th className="px-3 py-2 text-left">Hint</th>
            </tr>
          </thead>
          <tbody>
            {STAGES.map((stage) => {
              const selectId = `model-${stage.id}`;
              const current = values[stage.configKey] ?? "";
              return (
                <tr
                  key={stage.id}
                  className="border-b border-[var(--hairline)] last:border-0"
                  data-testid={`stage-row-${stage.id}`}
                >
                  <td className="px-3 py-2">
                    <label
                      htmlFor={selectId}
                      className="text-[var(--text)]"
                    >
                      {stage.label}
                    </label>
                  </td>
                  <td className="px-3 py-2">
                    <select
                      id={selectId}
                      aria-label={`${stage.label} model`}
                      value={current}
                      onChange={(e) => void onChange(stage, e.target.value)}
                      className="h-8 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] px-2 text-xs text-[var(--text)]"
                    >
                      <option value="" disabled>
                        Select…
                      </option>
                      {MODEL_OPTIONS.map((m) => (
                        <option key={m.value} value={m.value}>
                          {m.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-3 py-2 text-[11px] text-[var(--text-muted)]">
                    {stage.hint}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
