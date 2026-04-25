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

  // Tokens used here come from ``apps/brain_web/src/styles/tokens.css`` +
  // ``brand-skin.css``. The original Plan 08 BootGate used ``--color-*``
  // names that don't exist in the project, so every value fell back to a
  // hardcoded gray and the gate looked unbranded. Aligned 2026-04-24 to
  // the real token surface (``--surface-*``, ``--text*``, ``--hairline*``,
  // ``--r-*``).
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
          padding: 24,
          background: "var(--surface-0)",
        }}
      >
        <div
          style={{
            fontSize: 14,
            color: "var(--text-muted)",
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
          padding: 24,
          background: "var(--surface-0)",
        }}
      >
        <div
          style={{
            maxWidth: "420px",
            padding: 24,
            border: "1px solid var(--hairline-strong)",
            borderRadius: "var(--r-lg, 8px)",
            background: "var(--surface-2)",
            color: "var(--text)",
            textAlign: "center",
          }}
        >
          <h1
            style={{
              fontSize: 18,
              fontWeight: 600,
              marginBottom: 12,
            }}
          >
            {error}
          </h1>
          <p
            style={{
              fontSize: 13,
              color: "var(--text-muted)",
              marginBottom: 20,
            }}
          >
            Try running{" "}
            <code
              style={{
                padding: "2px 6px",
                background: "var(--surface-3)",
                borderRadius: "var(--r-sm, 4px)",
                fontFamily: "var(--font-mono)",
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
              padding: "8px 16px",
              border: "1px solid var(--hairline-strong)",
              borderRadius: "var(--r-md, 6px)",
              background: "var(--surface-3)",
              color: "var(--text)",
              cursor: "pointer",
              fontSize: 13,
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
