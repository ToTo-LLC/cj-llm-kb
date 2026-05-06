"use client";

import * as React from "react";
import { ChevronDown, ChevronRight, Edit2, Lock, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DomainOverrideForm,
  type DomainOverrideValues,
} from "@/components/settings/domain-override-form";
import type { DomainEntry } from "@/lib/state/domains-store";

/**
 * PanelDomainsRow (Plan 16 Task 8 / D8).
 *
 * Per-domain row inside the Settings → Domains list. Factored out of
 * ``panel-domains.tsx`` as part of the orchestrator + 3-children split.
 *
 * Owns the row's visual chrome only — the chevron + accent dot + slug
 * label, the privacy-railed badge for ``personal``, the privacy-rail
 * checkbox (or its disabled-and-checked tooltip variant for
 * ``personal``), the rename + delete buttons, and the expanded
 * ``<DomainOverrideForm>`` panel. All state mutations bubble up to the
 * orchestrator via callbacks; the row holds NO local state of its own.
 *
 * Visual + accessibility identity: the rendered DOM, ARIA attributes,
 * data-testids, and keyboard behaviour are byte-identical to the
 * pre-split inline implementation. Tests written against the
 * orchestrator (slug labels, ``data-testid="domain-row"``, the
 * ``personal-privacy-badge``, ``privacy-rail-checkbox-{slug}``,
 * ``rename-{slug}`` / ``delete-{slug}`` buttons) all continue to pass.
 */

const PROTECTED_DOMAINS = new Set<string>(["personal"]);

interface PanelDomainsRowProps {
  /** The domain to render. */
  domain: DomainEntry;
  /** The accent color for this row's swatch dot. Built-ins resolve
   *  via ``--dom-{slug}`` CSS variables; user-added domains rotate
   *  through ``ACCENT_SWATCHES``. The orchestrator computes this
   *  (uses the row's index) and passes it in. */
  accent: string;
  /** Whether this row's override panel is currently expanded. */
  isExpanded: boolean;
  /** Whether this domain is currently in the privacy rail. */
  isRailed: boolean;
  /** The override values to seed ``<DomainOverrideForm>`` with on
   *  expand. Falsy when not yet fetched — orchestrator owns the
   *  lazy-fetch on first expand. */
  overrideValues: DomainOverrideValues;
  /** Toggle the expanded state for this row. */
  onToggleExpanded: (slug: string) => void;
  /** Add or remove the slug from the privacy rail. */
  onTogglePrivacyRail: (slug: string, checked: boolean) => void;
  /** Open the rename dialog for this slug. */
  onRename: (slug: string) => void;
  /** Open the typed-confirm dialog for deleting this slug. The row
   *  itself never destroys data — the orchestrator owns the API call
   *  inside ``onConfirm`` so the optimistic store + reconciliation
   *  flow stays in one place. */
  onDelete: (slug: string) => void;
  /** Called after each ``DomainOverrideForm`` save so the orchestrator
   *  can re-fetch the override snapshot from the backend. */
  onOverrideChanged: (slug: string) => void;
}

export function PanelDomainsRow({
  domain,
  accent,
  isExpanded,
  isRailed,
  overrideValues,
  onToggleExpanded,
  onTogglePrivacyRail,
  onRename,
  onDelete,
  onOverrideChanged,
}: PanelDomainsRowProps): React.ReactElement {
  const slug = domain.slug;
  const protectedDomain = PROTECTED_DOMAINS.has(slug);
  const railCheckboxId = `privacy-rail-${slug}`;

  return (
    <li
      data-testid="domain-row"
      className="flex flex-col border-b border-[var(--hairline)] last:border-0"
    >
      <div className="flex items-center gap-3 px-3 py-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => onToggleExpanded(slug)}
          aria-label={
            isExpanded
              ? `Collapse ${slug} overrides`
              : `Expand ${slug} overrides`
          }
          aria-expanded={isExpanded}
          aria-controls={`override-panel-${slug}`}
          className="h-7 w-7 p-0"
        >
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </Button>
        <span
          aria-hidden="true"
          className="h-4 w-4 rounded-full border border-[var(--hairline)]"
          style={{ background: accent }}
        />
        <span className="font-mono text-sm text-[var(--text)]">{slug}</span>

        {protectedDomain && (
          <span
            data-testid="personal-privacy-badge"
            className="inline-flex items-center gap-1 rounded-full border border-[var(--hairline-strong)] px-2 py-0.5 text-[10px] font-medium"
            style={{
              background: "var(--dom-personal-soft)",
              color: "var(--dom-personal)",
            }}
          >
            <Lock className="h-2.5 w-2.5" />
            Privacy-railed
          </span>
        )}

        <div className="ml-auto flex items-center gap-3">
          {/* Privacy-rail checkbox per row. Personal is
              disabled-and-checked; tooltip explains why. */}
          {protectedDomain ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="inline-flex items-center gap-1.5">
                  <Checkbox
                    id={railCheckboxId}
                    checked={true}
                    disabled={true}
                    data-testid={`privacy-rail-checkbox-${slug}`}
                    aria-labelledby={`privacy-rail-label-${slug}`}
                  />
                  <label
                    id={`privacy-rail-label-${slug}`}
                    htmlFor={railCheckboxId}
                    className="text-[11px] text-[var(--text-muted)]"
                  >
                    Privacy-railed
                  </label>
                </span>
              </TooltipTrigger>
              <TooltipContent>
                personal is required and cannot be un-railed.
              </TooltipContent>
            </Tooltip>
          ) : (
            <span className="inline-flex items-center gap-1.5">
              <Checkbox
                id={railCheckboxId}
                checked={isRailed}
                onCheckedChange={(v) => onTogglePrivacyRail(slug, Boolean(v))}
                data-testid={`privacy-rail-checkbox-${slug}`}
                aria-labelledby={`privacy-rail-label-${slug}`}
              />
              <label
                id={`privacy-rail-label-${slug}`}
                htmlFor={railCheckboxId}
                className="text-[11px] text-[var(--text-muted)]"
              >
                Privacy-railed
              </label>
            </span>
          )}

          <Button
            variant="ghost"
            size="sm"
            onClick={() => onRename(slug)}
            aria-label={`Rename ${slug}`}
            className="h-7 gap-1 px-2 text-xs"
          >
            <Edit2 className="h-3 w-3" />
            Rename
          </Button>
          {!protectedDomain && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onDelete(slug)}
              aria-label={`Delete ${slug}`}
              className="h-7 gap-1 px-2 text-xs text-red-400 hover:text-red-300"
            >
              <Trash2 className="h-3 w-3" />
              Delete
            </Button>
          )}
        </div>
      </div>

      {isExpanded && (
        <div
          id={`override-panel-${slug}`}
          className="border-t border-[var(--hairline)] bg-[var(--surface-0)] px-3 py-3"
        >
          <DomainOverrideForm
            slug={slug}
            initialValues={overrideValues}
            onChanged={() => onOverrideChanged(slug)}
          />
        </div>
      )}
    </li>
  );
}
