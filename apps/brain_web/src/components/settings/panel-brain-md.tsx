"use client";

import * as React from "react";
import { BookOpen, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { VaultEditor } from "@/components/browse/monaco-editor";
import { proposeNote, readNote } from "@/lib/api/tools";
import { ApiError } from "@/lib/api/types";
import { useSystemStore } from "@/lib/state/system-store";

/**
 * PanelBrainMd (Plan 07 Task 22).
 *
 * Monaco editor bound to ``BRAIN.md`` at the vault root. Initial content
 * comes from ``readNote("BRAIN.md")``; a 404 is treated as "empty". Save
 * stages a patch via ``proposeNote`` — edits always route through the
 * approval queue (Principle 3: LLM writes are always staged; BRAIN.md
 * sits under the same safety rail).
 *
 * Stats at the bottom: line count + rough token estimate.
 */

export function PanelBrainMd(): React.ReactElement {
  const pushToast = useSystemStore((s) => s.pushToast);
  const [content, setContent] = React.useState<string>("");
  const [dirty, setDirty] = React.useState<boolean>(false);
  const [saving, setSaving] = React.useState<boolean>(false);
  const loadedRef = React.useRef<boolean>(false);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await readNote({ path: "BRAIN.md" });
        if (cancelled) return;
        setContent(r.data?.body ?? "");
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setContent("");
        } else {
          pushToast({
            lead: "Load failed.",
            msg: "Could not read BRAIN.md.",
            variant: "danger",
          });
        }
      } finally {
        loadedRef.current = true;
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pushToast]);

  const lines = content ? content.split("\n").length : 0;
  // Very rough — 1 token ≈ 4 chars of English. Good enough for a hint.
  const tokens = Math.ceil(content.length / 4);

  const save = async () => {
    setSaving(true);
    try {
      await proposeNote({
        path: "BRAIN.md",
        content,
        reason: "BRAIN.md edit from Settings",
      });
      pushToast({
        lead: "Edit staged.",
        msg: "Review the patch in Pending to apply.",
        variant: "success",
      });
      setDirty(false);
    } catch {
      pushToast({
        lead: "Save failed.",
        msg: "Could not stage BRAIN.md edit.",
        variant: "danger",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <header className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--text)]">
            <BookOpen className="h-3.5 w-3.5" />
            BRAIN.md
          </h2>
          <p className="mt-1 text-[11px] text-[var(--text-muted)]">
            The meta-index lives at your vault root. Edits go through the
            approval queue just like any other write.
          </p>
        </div>
        <Button
          onClick={() => void save()}
          disabled={!dirty || saving}
          className="gap-2"
        >
          <Save className="h-3.5 w-3.5" />
          {saving ? "Staging…" : "Save as patch"}
        </Button>
      </header>

      <div className="mb-2 min-h-[60vh] flex-1 overflow-hidden rounded-md border border-[var(--hairline)]">
        <VaultEditor
          value={content}
          onChange={(v) => {
            setContent(v);
            if (!dirty) setDirty(true);
          }}
        />
      </div>

      <footer className="flex items-center gap-3 text-[11px] text-[var(--text-dim)]">
        <span className="font-mono">{lines} lines</span>
        <span>·</span>
        <span className="font-mono">~{tokens} tokens</span>
        {dirty && (
          <span className="ml-auto text-amber-400">unsaved changes</span>
        )}
      </footer>
    </div>
  );
}
