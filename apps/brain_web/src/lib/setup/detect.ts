// First-run detection — server-only. Imported from the root Server Component
// (`app/page.tsx`) and runs once per SSR render. Intentionally uncached in
// Task 13 per Checkpoint 3 decision (3): simplicity over cost on the first
// paint. Plan 09 revisits caching once the setup wizard has settled.
//
// The detector does not care WHY setup is incomplete — only that the user
// has (a) a vault folder, (b) a BRAIN.md seed, and (c) a valid API token.
// Any combination missing sends them to `/setup`.
import { access } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

import { readToken } from "@/lib/auth/token";

export interface SetupStatus {
  isFirstRun: boolean;
  hasVault: boolean;
  hasToken: boolean;
  hasBrainMd: boolean;
  /**
   * Best-effort signal that an Anthropic API key has been configured. For
   * Task 13 we don't round-trip `brain_config_get` — that coupling adds
   * latency + failure modes on the marquee first-paint. We treat the
   * presence of a valid backend token as a proxy: if `readToken()` returns
   * a value, the backend is running, which means config was bootstrapped.
   * A real config-get check is future work (Task 25 sweep).
   */
  hasApiKey: boolean;
}

export async function detectSetupStatus(): Promise<SetupStatus> {
  const vaultRoot =
    process.env.BRAIN_VAULT_ROOT || join(homedir(), "Documents", "brain");

  const [hasVault, hasBrainMd, token] = await Promise.all([
    fileExists(vaultRoot),
    fileExists(join(vaultRoot, "BRAIN.md")),
    readToken(),
  ]);
  const hasToken = token !== null;
  // TODO(plan-07 task 25 sweep): replace `hasApiKey = hasToken` with a real
  // `brain_config_get({ key: "provider.anthropic.api_key" })` round-trip.
  const hasApiKey = hasToken;

  return {
    isFirstRun: !hasVault || !hasBrainMd || !hasApiKey,
    hasVault,
    hasToken,
    hasBrainMd,
    hasApiKey,
  };
}

async function fileExists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}
