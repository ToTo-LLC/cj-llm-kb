/**
 * Plan 11 Task 8 — first-mount scope hydration plumbing in app-store.
 *
 * The store half of D8 is the durable per-vault flag that tells the
 * topbar's hydration effect "you've already done first-load for this
 * vault, don't re-run on every navigation". Tests:
 *
 *   1. Fresh store → ``scopeInitialized === false``, ``scope === []``.
 *      Hydration is the topbar's job, but the defaults must be the
 *      "needs hydration" pair — never an arbitrary stub triple that
 *      would leak through to the picker.
 *
 *   2. ``markScopeInitialized(vaultPath)`` flips the in-memory mirror
 *      AND persists the per-vault localStorage flag at the documented
 *      key shape (``brain.scopeInitialized.<vault>``).
 *
 *   3. ``loadScopeInitializedFor(vaultPath)`` rehydrates the in-memory
 *      mirror from the per-vault flag. Simulates a page reload where
 *      the mirror starts ``false`` but the durable record says
 *      ``true``.
 *
 *   4. Two vaults → two independent flags. Switching vaults re-runs
 *      first-mount hydration without the user touching localStorage,
 *      because the new vault's key is unset.
 *
 *   5. ``scopeInitialized`` is NOT in the persisted ``brain-app``
 *      payload — it lives only under the per-vault key. (Otherwise it
 *      would leak across vaults via the single-key persist.)
 */

import { describe, expect, test, beforeEach } from "vitest";

import {
  useAppStore,
  readScopeInitialized,
} from "@/lib/state/app-store";

function resetStore() {
  useAppStore.setState({
    theme: "dark",
    density: "comfortable",
    mode: "ask",
    scope: [],
    view: "chat",
    railOpen: true,
    activeThreadId: null,
    streaming: false,
    scopeInitialized: false,
  });
}

describe("app-store scope-init plumbing", () => {
  beforeEach(() => {
    localStorage.clear();
    resetStore();
  });

  test("fresh store: scopeInitialized=false, scope=[]", () => {
    const s = useAppStore.getState();
    expect(s.scopeInitialized).toBe(false);
    expect(s.scope).toEqual([]);
  });

  test("markScopeInitialized flips the mirror AND persists the per-vault key", () => {
    const vault = "/Users/test/Documents/brain";

    expect(readScopeInitialized(vault)).toBe(false);

    useAppStore.getState().markScopeInitialized(vault);

    expect(useAppStore.getState().scopeInitialized).toBe(true);
    expect(localStorage.getItem(`brain.scopeInitialized.${vault}`)).toBe("true");
    expect(readScopeInitialized(vault)).toBe(true);
  });

  test("loadScopeInitializedFor: reload-from-storage path flips the mirror", () => {
    const vault = "/Users/test/Documents/brain";
    // Simulate a previous session that had hydrated the topbar — only
    // the durable record exists; the in-memory mirror is fresh.
    localStorage.setItem(`brain.scopeInitialized.${vault}`, "true");
    // Also pre-seed scope to a user-edited value so we can prove the
    // mirror flip doesn't clobber it (the topbar hydration effect bails
    // when the mirror is true).
    useAppStore.setState({ scope: ["research", "work", "personal"] });

    expect(useAppStore.getState().scopeInitialized).toBe(false);

    useAppStore.getState().loadScopeInitializedFor(vault);

    expect(useAppStore.getState().scopeInitialized).toBe(true);
    expect(useAppStore.getState().scope).toEqual([
      "research",
      "work",
      "personal",
    ]);
  });

  test("vault-path-keyed: two vaults each get an independent flag", () => {
    const vaultA = "/Users/test/Documents/brain";
    const vaultB = "/Users/test/Documents/brain-work";

    useAppStore.getState().markScopeInitialized(vaultA);

    // Mirror reflects "any vault has been initialised in THIS session"
    // — that's expected; the in-memory slot is a single boolean. The
    // durable per-vault keys are what guarantee vault B re-runs first-
    // mount hydration on the next reload.
    expect(readScopeInitialized(vaultA)).toBe(true);
    expect(readScopeInitialized(vaultB)).toBe(false);

    // Simulate a page reload by resetting the in-memory mirror, then
    // dispatching loadScopeInitializedFor for vault B.
    resetStore();
    useAppStore.getState().loadScopeInitializedFor(vaultB);
    expect(useAppStore.getState().scopeInitialized).toBe(false);

    // Same pattern for vault A → mirror flips, since its durable flag
    // is set.
    resetStore();
    useAppStore.getState().loadScopeInitializedFor(vaultA);
    expect(useAppStore.getState().scopeInitialized).toBe(true);
  });

  test("scopeInitialized is NOT in the persisted brain-app payload", () => {
    // Mutate a persisted field to force a write to the brain-app
    // payload, then mark scope initialised — the persist payload must
    // not include the flag (it lives under a separate vault-keyed
    // localStorage key).
    useAppStore.getState().setTheme("light");
    useAppStore.getState().markScopeInitialized("/some/vault");

    const raw = localStorage.getItem("brain-app");
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw!);
    expect(parsed.state).not.toHaveProperty("scopeInitialized");
    // Sanity: the per-vault key was written.
    expect(localStorage.getItem("brain.scopeInitialized./some/vault")).toBe(
      "true",
    );
  });

  test("loadScopeInitializedFor with unknown vault is a no-op", () => {
    useAppStore.getState().loadScopeInitializedFor("/never-seen");
    expect(useAppStore.getState().scopeInitialized).toBe(false);
  });
});
