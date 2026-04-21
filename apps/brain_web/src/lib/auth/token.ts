// Server-only — never imported in Client Components.
//
// Reads the per-run API token that `brain_api.create_app()` writes to
// `<vault>/.brain/run/api-secret.txt` (mode 0600 on POSIX). The token is
// attached to upstream requests as the `X-Brain-Token` header so the
// browser never sees it directly.
//
// The token is cached per-process after the first successful read. In dev,
// Next.js hot-reloads re-evaluate this module so the cache effectively resets
// on code changes; in production it persists until process restart. Both are
// acceptable — the token itself rotates on every `brain_api` restart, so a
// stale cache surfaces as a 401 from the backend that the proxy will bubble
// up with its upstream status intact.
import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

let cachedToken: string | null = null;
let cacheMiss = false;

/**
 * Read the API token from disk, cached per-process.
 *
 * Returns `null` when the token file is missing (e.g. first-run before
 * `brain_api` has started). Callers should treat `null` as the signal to
 * respond `503 setup_required` so the setup wizard (Task 13) can kick in.
 */
export async function readToken(): Promise<string | null> {
  if (cachedToken) return cachedToken;
  if (cacheMiss) return null;

  const vaultRoot =
    process.env.BRAIN_VAULT_ROOT || join(homedir(), "Documents", "brain");
  const tokenPath = join(vaultRoot, ".brain", "run", "api-secret.txt");

  try {
    const raw = await readFile(tokenPath, "utf-8");
    const token = raw.trim();
    if (!token) {
      cacheMiss = true;
      return null;
    }
    cachedToken = token;
    return token;
  } catch {
    cacheMiss = true;
    return null;
  }
}

/** Test helper — clears the module-level cache. */
export function invalidateTokenCache(): void {
  cachedToken = null;
  cacheMiss = false;
}
