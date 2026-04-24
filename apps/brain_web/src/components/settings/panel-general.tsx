"use client";

import * as React from "react";
import { Folder, Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";
import { configGet } from "@/lib/api/tools";
import { useAppStore, type Density, type Theme } from "@/lib/state/app-store";
import { cn } from "@/lib/utils";

/**
 * PanelGeneral (Plan 07 Task 22).
 *
 * Theme (dark/light), Density (comfortable/compact), Vault location
 * (read-only; fetched once via ``configGet("vault_path")``).
 *
 * Theme + density write to the app-store which applies dataset attrs on
 * <html> and persists to localStorage (app-store.partialize).
 */

export function PanelGeneral(): React.ReactElement {
  const theme = useAppStore((s) => s.theme);
  const density = useAppStore((s) => s.density);
  const setTheme = useAppStore((s) => s.setTheme);
  const setDensity = useAppStore((s) => s.setDensity);

  const [vaultPath, setVaultPath] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    configGet({ key: "vault_path" })
      .then((r) => {
        if (!cancelled) {
          const v = r.data?.value;
          setVaultPath(typeof v === "string" ? v : null);
        }
      })
      .catch(() => {
        if (!cancelled) setVaultPath(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <section>
        <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
          Appearance
        </h2>

        <div className="mb-4">
          <div className="mb-1.5 text-[11px] uppercase tracking-wider text-[var(--text-dim)]">
            Theme
          </div>
          <div className="flex gap-2">
            <ThemeChip
              value="dark"
              current={theme}
              onSelect={setTheme}
              icon={<Moon className="h-3.5 w-3.5" />}
              label="Dark"
            />
            <ThemeChip
              value="light"
              current={theme}
              onSelect={setTheme}
              icon={<Sun className="h-3.5 w-3.5" />}
              label="Light"
            />
          </div>
        </div>

        <div>
          <div className="mb-1.5 text-[11px] uppercase tracking-wider text-[var(--text-dim)]">
            Density
          </div>
          <div className="flex gap-2">
            <DensityChip
              value="comfortable"
              current={density}
              onSelect={setDensity}
              label="Comfortable"
            />
            <DensityChip
              value="compact"
              current={density}
              onSelect={setDensity}
              label="Compact"
            />
          </div>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
          Vault
        </h2>
        <label className="mb-1.5 block text-[11px] uppercase tracking-wider text-[var(--text-dim)]">
          Vault location
        </label>
        <div className="flex items-center gap-2 rounded-md border border-[var(--hairline)] bg-[var(--surface-1)] px-3 py-2 text-xs">
          <Folder className="h-3.5 w-3.5 text-[var(--text-dim)]" />
          <span className="font-mono text-[var(--text)]">
            {vaultPath ?? "~/Documents/brain"}
          </span>
          <span className="ml-auto text-[10px] text-[var(--text-dim)]">
            Read-only
          </span>
        </div>
        <p className="mt-2 text-[11px] text-[var(--text-muted)]">
          The vault path is fixed at install time. To move it, edit{" "}
          <code className="font-mono">&lt;vault&gt;/.brain/config.json</code> or
          re-install setting{" "}
          <code className="font-mono">BRAIN_VAULT_ROOT</code> to the new
          location. Not a click operation — content is sacred.
        </p>
      </section>
    </div>
  );
}

function ThemeChip({
  value,
  current,
  onSelect,
  icon,
  label,
}: {
  value: Theme;
  current: Theme;
  onSelect: (v: Theme) => void;
  icon: React.ReactNode;
  label: string;
}): React.ReactElement {
  const active = value === current;
  return (
    <Button
      type="button"
      variant={active ? "default" : "outline"}
      size="sm"
      className={cn("gap-2", active && "ring-1 ring-[var(--accent)]")}
      onClick={() => onSelect(value)}
      aria-pressed={active}
    >
      {icon}
      {label}
    </Button>
  );
}

function DensityChip({
  value,
  current,
  onSelect,
  label,
}: {
  value: Density;
  current: Density;
  onSelect: (v: Density) => void;
  label: string;
}): React.ReactElement {
  const active = value === current;
  return (
    <Button
      type="button"
      variant={active ? "default" : "outline"}
      size="sm"
      onClick={() => onSelect(value)}
      aria-pressed={active}
    >
      {label}
    </Button>
  );
}
