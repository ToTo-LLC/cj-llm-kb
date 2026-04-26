"use client";

import * as React from "react";
import dynamic from "next/dynamic";

import { useAppStore } from "@/lib/state/app-store";

/**
 * Monaco wrapper (Plan 07 Task 18 + issue #13).
 *
 * Lazy-loaded via ``next/dynamic({ssr:false})`` — Monaco pulls a ~2 MB
 * chunk, so keeping it out of the initial bundle is a hard
 * requirement. Editor flips into view only when the user clicks
 * "Edit" in the meta-strip.
 *
 * Issue #13: ``prefetchMonaco`` lets a sibling component (e.g. the
 * Edit button in MetaStrip) trigger the dynamic import on hover so
 * the chunk is in the browser cache by the time the user actually
 * clicks. Reduces first-open jank from "Loading editor…" placeholder
 * to instant. Idempotent — repeated calls are deduped via
 * ``monacoPrefetchPromise``.
 *
 * Theme mirrors the app-store theme so toggling light/dark in the
 * topbar flips Monaco too.
 */
const MonacoEditor = dynamic(
  () => import("@monaco-editor/react").then((m) => m.default),
  { ssr: false, loading: () => <EditorLoading /> },
);

let monacoPrefetchPromise: Promise<unknown> | null = null;

/** Prefetch the Monaco chunk. Safe to call from any event handler;
 *  subsequent calls return the cached promise so we never double-fetch.
 *  No-op on the server (the import factory just resolves the dynamic
 *  React component; the actual chunk download happens client-side). */
export function prefetchMonaco(): void {
  if (monacoPrefetchPromise !== null) return;
  if (typeof window === "undefined") return;
  monacoPrefetchPromise = import("@monaco-editor/react").catch(() => {
    // Reset on failure so a future hover can retry. The chunk loader
    // will produce its own error UI when the user actually clicks Edit.
    monacoPrefetchPromise = null;
  });
}

function EditorLoading(): React.ReactElement {
  return (
    <div
      aria-hidden="true"
      className="flex h-full min-h-[60vh] w-full items-center justify-center bg-[var(--surface-2)] text-xs text-[var(--text-dim)]"
    >
      Loading editor…
    </div>
  );
}

export interface VaultEditorProps {
  value: string;
  onChange: (next: string) => void;
}

export function VaultEditor({
  value,
  onChange,
}: VaultEditorProps): React.ReactElement {
  const theme = useAppStore((s) => s.theme);
  return (
    <div className="monaco-shell h-full min-h-[60vh] w-full">
      <MonacoEditor
        value={value}
        onChange={(v) => onChange(v ?? "")}
        language="markdown"
        theme={theme === "dark" ? "vs-dark" : "vs"}
        options={{
          fontSize: 13,
          wordWrap: "on",
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          lineNumbers: "on",
        }}
      />
    </div>
  );
}
