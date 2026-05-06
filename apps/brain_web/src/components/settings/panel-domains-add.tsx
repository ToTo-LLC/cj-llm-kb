"use client";

import * as React from "react";

import { DomainForm } from "@/components/settings/domain-form";

/**
 * PanelDomainsAdd (Plan 16 Task 8 / D8).
 *
 * Add-domain affordance — the "Add domain" section heading + the
 * extracted ``<DomainForm>`` (Plan 10 Task 6) wrapper. Factored out of
 * ``panel-domains.tsx`` into its own file as part of the orchestrator
 * + 3-children split.
 *
 * Props are minimal: ``onAdded`` is forwarded to ``DomainForm`` so the
 * orchestrator can refresh whatever list it renders after a successful
 * create. The form itself owns input state, slug validation, accent
 * selection, and the ``brain_create_domain`` round-trip; this wrapper
 * is just section chrome around it.
 */
interface PanelDomainsAddProps {
  /** Callback after a successful ``brain_create_domain``. The
   *  orchestrator routes this to ``refresh()`` (zustand store +
   *  privacy-rail re-fetch). */
  onAdded: () => void;
}

export function PanelDomainsAdd({ onAdded }: PanelDomainsAddProps): React.ReactElement {
  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
        Add domain
      </h2>
      <DomainForm onAdded={onAdded} />
    </section>
  );
}
