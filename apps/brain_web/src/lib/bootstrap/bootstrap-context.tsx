// Bootstrap context — Plan 08 Task 2.
//
// First browser handshake with brain_api. Because brain_web is statically
// exported (``output: "export"``) and brain_api serves the static bundle at
// ``/``, we can't rely on Next.js server components to read the per-run token
// from disk — the bundle runs entirely in the browser. Instead, on mount the
// provider does two same-origin GETs:
//
//   1. ``/api/setup-status`` → ``{has_token, is_first_run, vault_exists, vault_path}``
//      (Origin-gated, no token required). If ``is_first_run`` is true we
//      ``router.push("/setup/")`` and short-circuit — every other route
//      depends on a live token.
//   2. ``/api/token`` → ``{token}`` (Origin-gated, no token). Cached in the
//      ``useTokenStore`` Zustand slice so module-level code (``apiFetch`` + WS
//      client) can read it synchronously.
//
// The provider exposes ``useBootstrap()`` → ``{token, isFirstRun, vaultPath,
// loading, error}``. The ``BootGate`` component reads that to decide whether
// to render a "Starting brain…" skeleton, a "Can't reach brain" retry card,
// or the real app tree.
//
// ## Error surfaces
//
// Two classes of failure:
//   - Network failure / TypeError / offline → ``error =
//     "Can't reach brain — is it running?"``. The BootGate renders a retry
//     button that calls ``retry()`` to re-run the bootstrap effect.
//   - Backend 503 ``setup_required`` → ``error = "Setup required"``. In
//     practice the 503 only fires on ``/api/token`` after ``/api/setup-status``
//     said ``is_first_run=false`` but the token file vanished between the two
//     calls. Extremely unlikely but the branch is there for completeness.

"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { useTokenStore } from "@/lib/state/token-store";

export interface BootstrapValue {
  /** Per-run API token. ``null`` while loading, or if first-run / error. */
  token: string | null;
  /** ``true`` on a fresh vault (no BRAIN.md) or missing token file. */
  isFirstRun: boolean | null;
  /** Absolute vault root path reported by the backend. */
  vaultPath: string | null;
  /** ``true`` while the mount-time GETs are in flight. */
  loading: boolean;
  /** Human-readable error surfaced to ``<BootGate />`` — ``null`` when healthy. */
  error: string | null;
  /** Re-run the bootstrap effect (exposed to the retry button). */
  retry: () => void;
}

const BootstrapContext = createContext<BootstrapValue | null>(null);

/** Consume the bootstrap state. Must be called under ``<BootstrapProvider>``. */
export function useBootstrap(): BootstrapValue {
  const ctx = useContext(BootstrapContext);
  if (!ctx) {
    throw new Error(
      "useBootstrap must be called within a <BootstrapProvider>",
    );
  }
  return ctx;
}

interface SetupStatusBody {
  has_token: boolean;
  is_first_run: boolean;
  vault_exists: boolean;
  vault_path: string;
}

interface TokenBody {
  token: string;
}

export function BootstrapProvider({
  children,
}: {
  children: ReactNode;
}): React.ReactElement {
  const router = useRouter();
  const setToken = useTokenStore((s) => s.setToken);

  const [token, setLocalToken] = useState<string | null>(null);
  const [isFirstRun, setIsFirstRun] = useState<boolean | null>(null);
  const [vaultPath, setVaultPath] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  // Bump to re-run the bootstrap effect — lets the retry button re-enter the
  // effect without tearing down the provider (which would unmount every
  // consumer underneath).
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => {
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap(): Promise<void> {
      setLoading(true);
      setError(null);

      // Step 1 — setup-status.
      let statusBody: SetupStatusBody;
      try {
        const statusRes = await fetch("/api/setup-status");
        if (!statusRes.ok) {
          // Backend reports not-yet-set-up. Rare (setup-status doesn't gate
          // on the token), but if it surfaces we map it to a user-friendly
          // "setup required" message so BootGate can render a hint.
          if (cancelled) return;
          setError("Setup required");
          setLoading(false);
          return;
        }
        statusBody = (await statusRes.json()) as SetupStatusBody;
      } catch {
        if (cancelled) return;
        setError("Can't reach brain — is it running?");
        setLoading(false);
        return;
      }

      if (cancelled) return;
      setIsFirstRun(statusBody.is_first_run);
      setVaultPath(statusBody.vault_path);

      if (statusBody.is_first_run) {
        // First-run → push to the setup wizard. We intentionally don't fetch
        // /api/token yet — on a fresh vault it 503s (setup_required) and
        // only confuses the user. The wizard itself triggers a re-bootstrap
        // when it finishes by navigating to /chat/, which remounts the
        // provider hierarchy with a now-valid token file on disk.
        router.push("/setup/");
        setLoading(false);
        return;
      }

      // Step 2 — token.
      try {
        const tokenRes = await fetch("/api/token");
        if (!tokenRes.ok) {
          if (cancelled) return;
          // 503 here = token file vanished between the two calls. Treat as
          // setup-required; the user will land back on /setup/ after retry.
          setError("Setup required");
          setLoading(false);
          return;
        }
        const tokenBody = (await tokenRes.json()) as TokenBody;
        if (cancelled) return;
        setLocalToken(tokenBody.token);
        setToken(tokenBody.token);
        setLoading(false);
      } catch {
        if (cancelled) return;
        setError("Can't reach brain — is it running?");
        setLoading(false);
      }
    }

    void bootstrap();

    return () => {
      cancelled = true;
    };
    // `attempt` bump forces re-entry; `router`/`setToken` are stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt]);

  return (
    <BootstrapContext.Provider
      value={{ token, isFirstRun, vaultPath, loading, error, retry }}
    >
      {children}
    </BootstrapContext.Provider>
  );
}
