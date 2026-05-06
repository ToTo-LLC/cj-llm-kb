"use client";

import * as React from "react";
import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Modal } from "./modal";

/**
 * AutonomyModal (Plan 16 Task 10 — SCAFFOLD).
 *
 * Per Plan 16 D10, this modal collects the per-screen autonomy Switch
 * toggles (today scattered across Inbox + Pending) into a single dialog
 * with a global on/off PLUS three per-category overrides. The category
 * shape here — ``new_files`` / ``edits`` / ``index_entries`` — mirrors
 * the Plan 11 ``Config.autonomous`` 3-category surface called out in the
 * Task 10 spec; full per-domain category schema lands at Task 38 after
 * Task 37's brainstorm-and-lock, and the deep-config UI panel at Task 40
 * (``panel-autonomous.tsx``).
 *
 * SCAFFOLD only. ``onChange`` is a stub callback — Task 38 wires real
 * per-domain category state. Callers may pass nothing and the dialog
 * still mounts cleanly with all switches off (uncontrolled-ish shape;
 * internal toggling collapses to a no-op so axe-core can scan the
 * controls in both states).
 *
 * Microcopy is verbatim per the Task 10 spec / brain-ui-designer copy:
 *   - Title:       "Autonomy mode"
 *   - Description: "Let brain make changes without asking. Toggle each
 *                   category for fine-grained control."
 *   - Global row:  "Global autonomy"
 *   - Categories:  "New files" / "Edits to existing notes" / "Index entries"
 *   - Primary CTA: "Done"
 *
 * Per Task 9 review lesson: description prop and body content must be
 * DISTINCT — description states the high-level purpose; body shows the
 * actionable toggles. The body's leading paragraph adds context the
 * description deliberately omits, then yields to the Switch rows.
 *
 * Local-state (not ``dialogs-store``) is intentional. This is a
 * Settings-scoped dialog whose only entry is the General panel's
 * "Configure autonomy" button; routing it through the global store would
 * buy nothing and add a discriminated-union case the scaffold doesn't
 * need yet — same reasoning as Task 9's ``RepairConfigDialog``.
 */

export interface AutonomyValue {
  /** Master switch. When false, per-category switches are disabled. */
  global: boolean;
  /** Auto-apply patches that create new files. */
  newFiles: boolean;
  /** Auto-apply edits to existing notes. */
  edits: boolean;
  /** Auto-apply index-entry additions. */
  indexEntries: boolean;
}

const DEFAULT_VALUE: AutonomyValue = {
  global: false,
  newFiles: false,
  edits: false,
  indexEntries: false,
};

export interface AutonomyModalProps {
  isOpen: boolean;
  onClose: () => void;
  /**
   * Optional initial value. When omitted, all switches default to off.
   * Task 38 will replace this with a real per-domain category source.
   */
  value?: AutonomyValue;
  /**
   * Stub callback fired whenever any switch changes. Receives the next
   * full ``AutonomyValue``. If omitted, internal toggling still works
   * (the modal tracks state internally) but no caller is notified.
   */
  onChange?: (next: AutonomyValue) => void;
}

export function AutonomyModal({
  isOpen,
  onClose,
  value,
  onChange,
}: AutonomyModalProps): React.ReactElement {
  // Track state internally so the modal renders meaningfully when no
  // ``value`` is passed (scaffold callers won't wire it). When ``value``
  // is provided, mirror it in; once mounted, we treat the dialog as
  // controlled-ish — the prop seeds the initial state and ``onChange``
  // is the canonical observable.
  const [state, setState] = React.useState<AutonomyValue>(value ?? DEFAULT_VALUE);

  // Re-sync when ``value`` prop changes (e.g. parent re-fetched config).
  React.useEffect(() => {
    if (value) setState(value);
  }, [value]);

  const update = React.useCallback(
    (patch: Partial<AutonomyValue>) => {
      setState((prev) => {
        const next = { ...prev, ...patch };
        onChange?.(next);
        return next;
      });
    },
    [onChange],
  );

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title="Autonomy mode"
      description="Let brain make changes without asking. Toggle each category for fine-grained control."
      width={480}
      footer={
        <Button onClick={onClose} className="gap-2">
          <Sparkles className="h-3.5 w-3.5" /> Done
        </Button>
      }
    >
      {/* Body content is DISTINCT from the description (Task 9 lesson).
          The description sets the high-level frame; this paragraph
          calls out the safety rails that still apply, then the rows
          render the actual interactive surface. */}
      <p className="mb-4 text-muted-foreground">
        Scope, domain, and budget guards still enforce every patch — only
        the &ldquo;needs human review&rdquo; bit flips when a category is on.
      </p>
      <div className="space-y-3">
        <SwitchRow
          label="Global autonomy"
          hint="Master switch. Per-category controls below activate when this is on."
          checked={state.global}
          onCheckedChange={(g) => update({ global: g })}
        />
        <hr className="border-[var(--hairline)]" />
        <SwitchRow
          label="New files"
          hint="Auto-apply patches that create new notes."
          checked={state.newFiles}
          disabled={!state.global}
          onCheckedChange={(n) => update({ newFiles: n })}
        />
        <SwitchRow
          label="Edits to existing notes"
          hint="Auto-apply edits to notes already in your vault."
          checked={state.edits}
          disabled={!state.global}
          onCheckedChange={(e) => update({ edits: e })}
        />
        <SwitchRow
          label="Index entries"
          hint="Auto-apply additions to index files."
          checked={state.indexEntries}
          disabled={!state.global}
          onCheckedChange={(i) => update({ indexEntries: i })}
        />
      </div>
    </Modal>
  );
}

interface SwitchRowProps {
  label: string;
  hint: string;
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  disabled?: boolean;
}

function SwitchRow({
  label,
  hint,
  checked,
  onCheckedChange,
  disabled,
}: SwitchRowProps): React.ReactElement {
  // Plan 16 Task 10 a11y note: deliberately do NOT apply ``opacity-60`` (or
  // any wrapper opacity) to disabled rows. ``--text-dim`` is tuned in
  // tokens.css to exactly meet WCAG 2 AA 4.5:1 against ``--surface-1``
  // (Plan 07 Task 25C); multiplying that alpha by 0.6 drops contrast to
  // ~2.7:1 and trips axe-core's color-contrast rule. The Switch primitive
  // already conveys disabled state via its own ``disabled:opacity-50``
  // class on the toggle thumb, which is sufficient affordance — the row's
  // text stays high-contrast for screen-reader users walking the form.
  return (
    <label className="flex items-center gap-3 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] px-3 py-2 text-xs">
      <Switch
        checked={checked}
        onCheckedChange={(v) => onCheckedChange(Boolean(v))}
        disabled={disabled}
        aria-label={label}
      />
      <span className="flex flex-col">
        <span className="text-[12px] font-medium text-[var(--text)]">
          {label}
        </span>
        <span className="text-[11px] text-[var(--text-dim)]">{hint}</span>
      </span>
    </label>
  );
}
