"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface VaultLocationStepProps {
  value: string;
  onChange: (value: string) => void;
}

/**
 * Vault-location step (2 / 6). Controlled via parent state so the Continue
 * button can gate on empty paths. The "Browse…" button is a no-op for now —
 * a native file picker needs a server-side handler (platform-conditional) we
 * don't ship in Task 13.
 */
export function VaultLocationStep({ value, onChange }: VaultLocationStepProps) {
  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-medium tracking-tight">
        Where should your vault live?
      </h1>
      <p className="text-base leading-relaxed text-muted-foreground">
        brain writes Markdown files to this folder. It&apos;s a normal folder —
        Obsidian, Finder, git all still work.
      </p>
      <div className="space-y-2">
        <label
          htmlFor="vault-folder"
          className="text-sm font-medium text-foreground"
        >
          Vault folder
        </label>
        <div className="flex gap-2">
          <Input
            id="vault-folder"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="~/Documents/brain"
          />
          <Button
            type="button"
            variant="outline"
            disabled
            title="Folder picker coming soon"
          >
            Browse…
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Your vault is a plain folder. Point Obsidian at it if you want.
        </p>
      </div>
    </div>
  );
}
