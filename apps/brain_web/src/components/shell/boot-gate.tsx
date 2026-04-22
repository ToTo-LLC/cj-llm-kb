"use client";

import * as React from "react";

import { useBootstrap } from "@/lib/bootstrap/bootstrap-context";

/**
 * BootGate (Plan 08 Task 2).
 *
 * Renders a neutral shell while the bootstrap effect fetches
 * ``/api/setup-status`` + ``/api/token``. Three observable states:
 *
 *   - ``loading`` — brief "Starting brain…" card.
 *   - ``error`` — retry card with the BootstrapContext's human-readable
 *     error string and a button that calls ``retry()``.
 *   - ready — forwards to ``children`` (the real app tree).
 *
 * First-run users never see the ready branch here — the bootstrap effect
 * calls ``router.push("/setup/")`` inside the "still loading" window and the
 * setup wizard's own render runs under the same BootGate, which at that
 * moment has ``isFirstRun=true`` + ``loading=false`` + ``token=null``. Setup
 * pages don't need a token, so we forward children through even when the
 * token is null — that's what unblocks the wizard from rendering.
 */
export function BootGate({
  children,
}: {
  children: React.ReactNode;
}): React.ReactElement {
  const { loading, error, retry } = useBootstrap();

  if (loading) {
    return (
      <div
        role="status"
        aria-live="polite"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
          padding: "var(--space-6, 24px)",
        }}
      >
        <div
          style={{
            fontSize: "var(--font-size-md, 14px)",
            color: "var(--color-text-muted, #888)",
          }}
        >
          Starting brain…
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        role="alert"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
          padding: "var(--space-6, 24px)",
        }}
      >
        <div
          style={{
            maxWidth: "420px",
            padding: "var(--space-6, 24px)",
            border: "1px solid var(--color-border, #333)",
            borderRadius: "var(--radius-lg, 8px)",
            background: "var(--color-surface, #1a1a1a)",
            color: "var(--color-text, #eee)",
            textAlign: "center",
          }}
        >
          <h1
            style={{
              fontSize: "var(--font-size-lg, 18px)",
              fontWeight: 600,
              marginBottom: "var(--space-3, 12px)",
            }}
          >
            {error}
          </h1>
          <p
            style={{
              fontSize: "var(--font-size-sm, 13px)",
              color: "var(--color-text-muted, #999)",
              marginBottom: "var(--space-5, 20px)",
            }}
          >
            Try running{" "}
            <code
              style={{
                padding: "2px 6px",
                background: "var(--color-surface-raised, #222)",
                borderRadius: "var(--radius-sm, 4px)",
              }}
            >
              brain start
            </code>
            {" "}in a terminal, then retry.
          </p>
          <button
            type="button"
            onClick={retry}
            style={{
              padding: "var(--space-2, 8px) var(--space-4, 16px)",
              border: "1px solid var(--color-border, #444)",
              borderRadius: "var(--radius-md, 6px)",
              background: "var(--color-surface-raised, #222)",
              color: "var(--color-text, #eee)",
              cursor: "pointer",
              fontSize: "var(--font-size-sm, 13px)",
            }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
