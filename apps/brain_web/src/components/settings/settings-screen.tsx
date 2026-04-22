"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Archive,
  BookOpen,
  Bot,
  DollarSign,
  Folder,
  Plug,
  Settings as SettingsIcon,
  Shuffle,
} from "lucide-react";

import { PanelAutonomous } from "./panel-autonomous";
import { PanelBackups } from "./panel-backups";
import { PanelBrainMd } from "./panel-brain-md";
import { PanelBudget } from "./panel-budget";
import { PanelDomains } from "./panel-domains";
import { PanelGeneral } from "./panel-general";
import { PanelIntegrations } from "./panel-integrations";
import { PanelProviders } from "./panel-providers";
import { cn } from "@/lib/utils";

/**
 * SettingsScreen (Plan 07 Task 22).
 *
 * Two-column layout: left sidebar with 8 tabs, right content. The
 * active tab is driven by the ``/settings/<tab>`` URL segment so
 * deep-linking + back/forward both work. Unknown tab → redirect to
 * general.
 */

export interface SettingsScreenProps {
  activeTab: string;
}

interface TabDef {
  id: SettingsTabId;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

export type SettingsTabId =
  | "general"
  | "providers"
  | "budget"
  | "autonomous"
  | "integrations"
  | "domains"
  | "brain-md"
  | "backups";

const TABS: readonly TabDef[] = [
  { id: "general", label: "General", icon: SettingsIcon },
  { id: "providers", label: "LLM providers", icon: Plug },
  { id: "budget", label: "Budget", icon: DollarSign },
  { id: "autonomous", label: "Autonomous", icon: Bot },
  { id: "integrations", label: "Integrations", icon: Shuffle },
  { id: "domains", label: "Domains", icon: Folder },
  { id: "brain-md", label: "BRAIN.md", icon: BookOpen },
  { id: "backups", label: "Backups", icon: Archive },
];

const VALID_TABS = new Set<string>(TABS.map((t) => t.id));

function renderPanel(tab: SettingsTabId): React.ReactElement {
  switch (tab) {
    case "general":
      return <PanelGeneral />;
    case "providers":
      return <PanelProviders />;
    case "budget":
      return <PanelBudget />;
    case "autonomous":
      return <PanelAutonomous />;
    case "integrations":
      return <PanelIntegrations />;
    case "domains":
      return <PanelDomains />;
    case "brain-md":
      return <PanelBrainMd />;
    case "backups":
      return <PanelBackups />;
    default: {
      // Exhaustiveness check — adding a tab id must widen the switch.
      const _exhaustive: never = tab;
      void _exhaustive;
      return <PanelGeneral />;
    }
  }
}

export function SettingsScreen({
  activeTab,
}: SettingsScreenProps): React.ReactElement {
  const router = useRouter();

  React.useEffect(() => {
    if (!VALID_TABS.has(activeTab)) {
      router.replace("/settings/general");
    }
  }, [activeTab, router]);

  const safeTab: SettingsTabId = VALID_TABS.has(activeTab)
    ? (activeTab as SettingsTabId)
    : "general";

  return (
    <div className="settings-screen flex h-full overflow-hidden">
      <nav
        aria-label="Settings sections"
        className="flex w-56 flex-col gap-0.5 border-r border-[var(--hairline)] bg-[var(--surface-1)] p-3"
      >
        <div className="mb-3 px-2">
          <div className="text-[10px] uppercase tracking-wider text-[var(--text-dim)]">
            Settings
          </div>
          <h1 className="text-sm font-semibold text-[var(--text)]">
            Configure brain
          </h1>
        </div>

        <ul role="list" className="flex flex-col gap-0.5">
          {TABS.map((tab) => {
            const active = tab.id === safeTab;
            const Icon = tab.icon;
            return (
              <li key={tab.id}>
                <Link
                  href={`/settings/${tab.id}`}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs",
                    active
                      ? "bg-[var(--surface-3)] text-[var(--text)]"
                      : "text-[var(--text-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]",
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {tab.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-3xl">{renderPanel(safeTab)}</div>
      </div>
    </div>
  );
}
