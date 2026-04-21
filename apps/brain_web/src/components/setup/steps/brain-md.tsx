"use client";

import { Textarea } from "@/components/ui/textarea";

export const DEFAULT_BRAIN_MD = `# My brain

A knowledge base maintained by an LLM. Built for research, writing, and
thinking out loud.

Everything lives in plain Markdown. Nothing leaves this machine unless I
tell it to.
`;

export interface BrainMdStepProps {
  value: string;
  onChange: (value: string) => void;
}

/**
 * BRAIN.md step (5 / 6). Pre-filled with `DEFAULT_BRAIN_MD` — the user can
 * edit or leave as-is. Saving is auto-applied (see `Wizard.handleNext`)
 * because skipping the approval queue keeps setup linear.
 */
export function BrainMdStep({ value, onChange }: BrainMdStepProps) {
  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-medium tracking-tight">
        Tell brain about you.
      </h1>
      <p className="text-base leading-relaxed text-muted-foreground">
        Optional. This becomes your <code className="rounded bg-muted px-1">BRAIN.md</code> —
        the voice brain uses when talking to you.
      </p>
      <div className="space-y-2">
        <label
          htmlFor="brain-md"
          className="text-sm font-medium text-foreground"
        >
          BRAIN.md content
        </label>
        <Textarea
          id="brain-md"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={8}
          className="font-mono text-xs leading-relaxed"
        />
        <p className="text-xs text-muted-foreground">
          You can edit this anytime from Settings → Profile.
        </p>
      </div>
    </div>
  );
}
