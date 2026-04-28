"use client";

import * as React from "react";
import { RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { configSet } from "@/lib/api/tools";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * DomainOverrideForm (Plan 11 Task 7).
 *
 * Per-domain LLM/autonomy override editor surfaced in
 * Settings → Domains. Five optional fields (each maps 1:1 to a field
 * on :class:`brain_core.config.schema.DomainOverride`):
 *
 *   - classify_model        — string (any model name; no enum)
 *   - default_model         — string
 *   - temperature           — float, 0.0..1.5 (mirrors LLMConfig bounds)
 *   - max_output_tokens     — int, > 0
 *   - autonomous_mode       — bool
 *
 * Each field is independent. "Reset to global" sends ``null`` for that
 * field; the backend's ``_apply_domain_override`` interprets ``None``
 * as "clear this override" and prunes the whole slug entry once every
 * field is back to global.
 *
 * Persistence: every field write goes through ``brain_config_set`` with
 * the dotted key ``domain_overrides.<slug>.<field>``. Plan 11 Task 7's
 * dict-walk extension makes that path resolve through ``Config``'s
 * ``dict[str, DomainOverride]``.
 *
 * Caller provides the current override values (read from
 * ``Config.domain_overrides[slug]`` via ``brain_config_get``); after
 * each successful save the parent invokes ``onChanged`` so the cache
 * + this form's local state can refresh.
 */

export interface DomainOverrideValues {
  classify_model: string | null;
  default_model: string | null;
  temperature: number | null;
  max_output_tokens: number | null;
  autonomous_mode: boolean | null;
}

const EMPTY: DomainOverrideValues = {
  classify_model: null,
  default_model: null,
  temperature: null,
  max_output_tokens: null,
  autonomous_mode: null,
};

export interface DomainOverrideFormProps {
  slug: string;
  initialValues?: DomainOverrideValues;
  /** Invalidate caches / re-fetch override state — called after each
   *  successful field save. */
  onChanged?: () => void;
}

/** Validate temperature within the LLMConfig bounds (0..1.5). */
function isValidTemperature(s: string): boolean {
  if (s.trim() === "") return true; // empty = no override
  const n = Number(s);
  return Number.isFinite(n) && n >= 0 && n <= 1.5;
}

/** Validate max_output_tokens > 0 (mirrors LLMConfig.gt=0). */
function isValidMaxTokens(s: string): boolean {
  if (s.trim() === "") return true;
  const n = Number(s);
  return Number.isFinite(n) && Number.isInteger(n) && n > 0;
}

export function DomainOverrideForm({
  slug,
  initialValues,
  onChanged,
}: DomainOverrideFormProps): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const seed = initialValues ?? EMPTY;

  // Each text field tracks the in-progress edit value; the committed
  // value lives in ``initialValues`` (re-read from props on every
  // refresh). String-typed because the inputs are <input type="text">
  // — we coerce on save.
  const [classifyModel, setClassifyModel] = React.useState<string>(
    seed.classify_model ?? "",
  );
  const [defaultModel, setDefaultModel] = React.useState<string>(
    seed.default_model ?? "",
  );
  const [temperature, setTemperature] = React.useState<string>(
    seed.temperature !== null ? String(seed.temperature) : "",
  );
  const [maxTokens, setMaxTokens] = React.useState<string>(
    seed.max_output_tokens !== null ? String(seed.max_output_tokens) : "",
  );

  // Keep local state in sync if parent re-fetches and passes new
  // values in. ``initialValues`` is a stable reference per render so
  // a deep-equal compare isn't needed — useEffect dep array on the
  // five primitives is enough.
  React.useEffect(() => {
    setClassifyModel(seed.classify_model ?? "");
    setDefaultModel(seed.default_model ?? "");
    setTemperature(seed.temperature !== null ? String(seed.temperature) : "");
    setMaxTokens(
      seed.max_output_tokens !== null ? String(seed.max_output_tokens) : "",
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    seed.classify_model,
    seed.default_model,
    seed.temperature,
    seed.max_output_tokens,
    seed.autonomous_mode,
  ]);

  const tempValid = isValidTemperature(temperature);
  const maxTokensValid = isValidMaxTokens(maxTokens);

  const saveField = async (
    field: keyof DomainOverrideValues,
    value: string | number | boolean | null,
  ) => {
    try {
      await configSet({
        key: `domain_overrides.${slug}.${field}`,
        value,
      });
      pushToast({
        lead: value === null ? "Reset to global." : "Override saved.",
        msg: `domain_overrides.${slug}.${field} → ${
          value === null ? "global" : JSON.stringify(value)
        }`,
        variant: "success",
      });
      onChanged?.();
    } catch (err) {
      pushToast({
        lead: "Couldn't save override.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    }
  };

  const resetField = (field: keyof DomainOverrideValues) => {
    void saveField(field, null);
  };

  const saveText = (field: "classify_model" | "default_model", raw: string) => {
    const trimmed = raw.trim();
    void saveField(field, trimmed === "" ? null : trimmed);
  };

  const saveTemperature = () => {
    if (!tempValid) return;
    const trimmed = temperature.trim();
    void saveField("temperature", trimmed === "" ? null : Number(trimmed));
  };

  const saveMaxTokens = () => {
    if (!maxTokensValid) return;
    const trimmed = maxTokens.trim();
    void saveField(
      "max_output_tokens",
      trimmed === "" ? null : Number(trimmed),
    );
  };

  return (
    <div
      className="flex flex-col gap-3 rounded-md border border-[var(--hairline)] bg-[var(--surface-2)] p-3"
      data-testid={`domain-override-form-${slug}`}
      role="group"
      aria-label={`Override settings for ${slug}`}
    >
      <p className="text-[11px] text-[var(--text-muted)]">
        Per-domain overrides take precedence over global settings when
        the active scope matches{" "}
        <span className="font-mono">{slug}</span>. Empty = uses global.
      </p>

      {/* classify_model */}
      <FieldRow
        id={`override-${slug}-classify-model`}
        label="Classify model"
        hint="Model used for the routing/classification step."
        hasOverride={seed.classify_model !== null}
        onReset={() => resetField("classify_model")}
      >
        <Input
          id={`override-${slug}-classify-model`}
          value={classifyModel}
          onChange={(e) => setClassifyModel(e.target.value)}
          onBlur={() => {
            const next = classifyModel.trim() === "" ? null : classifyModel.trim();
            if (next !== seed.classify_model) saveText("classify_model", classifyModel);
          }}
          placeholder="uses global"
          className="font-mono"
          spellCheck={false}
        />
      </FieldRow>

      {/* default_model */}
      <FieldRow
        id={`override-${slug}-default-model`}
        label="Default model"
        hint="Model used for non-classify operations (chat, draft, brainstorm)."
        hasOverride={seed.default_model !== null}
        onReset={() => resetField("default_model")}
      >
        <Input
          id={`override-${slug}-default-model`}
          value={defaultModel}
          onChange={(e) => setDefaultModel(e.target.value)}
          onBlur={() => {
            const next = defaultModel.trim() === "" ? null : defaultModel.trim();
            if (next !== seed.default_model) saveText("default_model", defaultModel);
          }}
          placeholder="uses global"
          className="font-mono"
          spellCheck={false}
        />
      </FieldRow>

      {/* temperature */}
      <FieldRow
        id={`override-${slug}-temperature`}
        label="Temperature"
        hint="0.0..1.5 — lower = more deterministic, higher = more creative."
        hasOverride={seed.temperature !== null}
        onReset={() => resetField("temperature")}
      >
        <Input
          id={`override-${slug}-temperature`}
          value={temperature}
          onChange={(e) => setTemperature(e.target.value)}
          onBlur={() => {
            if (!tempValid) return;
            const trimmed = temperature.trim();
            const next = trimmed === "" ? null : Number(trimmed);
            if (next !== seed.temperature) saveTemperature();
          }}
          placeholder="uses global"
          aria-invalid={!tempValid}
          aria-describedby={`override-${slug}-temperature-hint`}
          inputMode="decimal"
        />
        {!tempValid && (
          <p
            id={`override-${slug}-temperature-hint`}
            className="mt-1 text-[11px] text-red-400"
          >
            Must be a number between 0 and 1.5.
          </p>
        )}
      </FieldRow>

      {/* max_output_tokens */}
      <FieldRow
        id={`override-${slug}-max-output-tokens`}
        label="Max output tokens"
        hint="Positive integer; caps response length."
        hasOverride={seed.max_output_tokens !== null}
        onReset={() => resetField("max_output_tokens")}
      >
        <Input
          id={`override-${slug}-max-output-tokens`}
          value={maxTokens}
          onChange={(e) => setMaxTokens(e.target.value)}
          onBlur={() => {
            if (!maxTokensValid) return;
            const trimmed = maxTokens.trim();
            const next = trimmed === "" ? null : Number(trimmed);
            if (next !== seed.max_output_tokens) saveMaxTokens();
          }}
          placeholder="uses global"
          aria-invalid={!maxTokensValid}
          aria-describedby={`override-${slug}-max-output-tokens-hint`}
          inputMode="numeric"
        />
        {!maxTokensValid && (
          <p
            id={`override-${slug}-max-output-tokens-hint`}
            className="mt-1 text-[11px] text-red-400"
          >
            Must be a positive integer.
          </p>
        )}
      </FieldRow>

      {/* autonomous_mode */}
      <div
        data-testid={`override-row-autonomous-${slug}`}
        className="flex items-center gap-3 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] px-3 py-2"
      >
        <Switch
          checked={seed.autonomous_mode === true}
          onCheckedChange={(v) => {
            // Tri-state in storage (null/true/false) collapses to a
            // 2-state UI here — toggling on or off ALWAYS writes the
            // bool (override present); use the explicit "Reset to
            // global" button to clear the override entirely.
            void saveField("autonomous_mode", Boolean(v));
          }}
          aria-labelledby={`override-${slug}-autonomous-label`}
          aria-describedby={`override-${slug}-autonomous-desc`}
          disabled={false}
        />
        <div className="flex flex-1 flex-col">
          <span
            id={`override-${slug}-autonomous-label`}
            className="text-sm font-medium text-[var(--text)]"
          >
            Autonomous mode
          </span>
          <span
            id={`override-${slug}-autonomous-desc`}
            className="text-[11px] text-[var(--text-muted)]"
          >
            Override the global autonomous toggle for this domain.{" "}
            {seed.autonomous_mode === null
              ? "Currently uses global."
              : `Currently overrides global to ${seed.autonomous_mode}.`}
          </span>
        </div>
        {seed.autonomous_mode !== null && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => resetField("autonomous_mode")}
            aria-label={`Reset autonomous_mode override for ${slug}`}
            className="h-7 gap-1 px-2 text-xs"
          >
            <RotateCcw className="h-3 w-3" />
            Reset
          </Button>
        )}
      </div>
    </div>
  );
}

/* ----------------------- Internal field row ----------------------- */

interface FieldRowProps {
  id: string;
  label: string;
  hint: string;
  hasOverride: boolean;
  onReset: () => void;
  children: React.ReactNode;
}

function FieldRow({
  id,
  label,
  hint,
  hasOverride,
  onReset,
  children,
}: FieldRowProps): React.ReactElement {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <label
          htmlFor={id}
          className="block text-[11px] uppercase tracking-wider text-[var(--text-dim)]"
        >
          {label}
        </label>
        {hasOverride && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onReset}
            aria-label={`Reset ${label} to global`}
            className="h-6 gap-1 px-2 text-[11px]"
          >
            <RotateCcw className="h-3 w-3" />
            Reset to global
          </Button>
        )}
      </div>
      {children}
      <p className="text-[11px] text-[var(--text-dim)]">{hint}</p>
    </div>
  );
}
