/**
 * Plan 16 Task 43 / D32(b) — useDomainOverridesStore (zustand) contract.
 *
 * Pins the domain-overrides-store surface so the Settings → Domains
 * panel and the per-row override form can rely on a stable
 * cross-instance reactivity model:
 *
 *   1. Fresh store has the documented zero-state.
 *   2. ``refresh()`` populates from a single ``configGet({key:
 *      "domain_overrides"})`` read; failure lands on ``error`` without
 *      flipping ``loaded``.
 *   3. ``setOverrideField`` optimistically updates the slug entry then
 *      persists; on failure it reverts AND surfaces the error.
 *   4. Concurrent ``refresh()`` calls share one in-flight Promise.
 *   5. Outbound: every mutation broadcasts to peer tabs via the
 *      ``"brain-domain-overrides"`` BroadcastChannel.
 *   6. Inbound: peer payloads apply via ``_internalSet`` and do NOT
 *      re-broadcast (no ping-pong).
 *
 * Mirrors the canonical ``domains-store-broadcast.test.ts`` +
 * ``use-domains-store.test.ts`` shape exactly.
 */

import { describe, expect, test, vi, beforeEach } from "vitest";

const { configGetMock, configSetMock } = vi.hoisted(() => ({
  configGetMock: vi.fn(),
  configSetMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  configGet: configGetMock,
  configSet: configSetMock,
}));

import {
  useDomainOverridesStore,
  DOMAIN_OVERRIDES_BROADCAST_CHANNEL,
  type DomainOverrideEntry,
} from "@/lib/state/domain-overrides-store";

function makePeerChannel(): BroadcastChannel {
  return new BroadcastChannel(DOMAIN_OVERRIDES_BROADCAST_CHANNEL);
}

async function waitForCondition(
  predicate: () => boolean,
  timeoutMs = 100,
): Promise<void> {
  const start = Date.now();
  while (!predicate()) {
    if (Date.now() - start > timeoutMs) {
      throw new Error(
        `Condition not met within ${timeoutMs}ms (predicate stayed false)`,
      );
    }
    await new Promise((r) => setTimeout(r, 5));
  }
}

beforeEach(() => {
  configGetMock.mockReset();
  configSetMock.mockReset();
  useDomainOverridesStore.getState()._resetForTesting();
});

describe("useDomainOverridesStore — fresh state", () => {
  test("returns the documented zero-state on first read", () => {
    const s = useDomainOverridesStore.getState();
    expect(s.overrides).toEqual({});
    expect(s.loaded).toBe(false);
    expect(s.error).toBeNull();
  });
});

describe("useDomainOverridesStore — refresh()", () => {
  test("hydrates the overrides map from a successful configGet", async () => {
    configGetMock.mockResolvedValue({
      text: "",
      data: {
        key: "domain_overrides",
        value: {
          research: {
            classify_model: "haiku-3.5",
            default_model: "sonnet-4.6",
            temperature: 0.4,
            max_output_tokens: 1024,
          },
        },
      },
    });

    await useDomainOverridesStore.getState().refresh();

    const s = useDomainOverridesStore.getState();
    expect(s.overrides.research).toEqual({
      classify_model: "haiku-3.5",
      default_model: "sonnet-4.6",
      temperature: 0.4,
      max_output_tokens: 1024,
    });
    expect(s.loaded).toBe(true);
    expect(s.error).toBeNull();
    expect(configGetMock).toHaveBeenCalledWith({ key: "domain_overrides" });
    expect(configGetMock).toHaveBeenCalledTimes(1);
  });

  test("normalizes missing leaf fields to null", async () => {
    // The backend may omit fields that fall back to global; the helper
    // fills missing fields with ``null`` so consumers don't repeat
    // optional-chaining noise.
    configGetMock.mockResolvedValue({
      text: "",
      data: {
        key: "domain_overrides",
        value: {
          partial: { default_model: "sonnet-4.6" },
        },
      },
    });

    await useDomainOverridesStore.getState().refresh();

    expect(useDomainOverridesStore.getState().overrides.partial).toEqual({
      classify_model: null,
      default_model: "sonnet-4.6",
      temperature: null,
      max_output_tokens: null,
    });
  });

  test("records error on failed configGet (resolve-always semantics)", async () => {
    configGetMock.mockRejectedValue(new Error("backend unreachable"));

    await useDomainOverridesStore.getState().refresh();

    const s = useDomainOverridesStore.getState();
    expect(s.error).toBeInstanceOf(Error);
    expect(s.error?.message).toBe("backend unreachable");
    expect(s.loaded).toBe(false);
  });

  test("concurrent refresh() calls share one in-flight Promise", async () => {
    let resolveFetch: (val: unknown) => void = () => {};
    configGetMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        }),
    );

    const a = useDomainOverridesStore.getState().refresh();
    const b = useDomainOverridesStore.getState().refresh();

    expect(a).toBe(b);
    expect(configGetMock).toHaveBeenCalledTimes(1);

    resolveFetch({ text: "", data: { key: "domain_overrides", value: {} } });
    await Promise.all([a, b]);
    expect(configGetMock).toHaveBeenCalledTimes(1);
  });
});

describe("useDomainOverridesStore — setOverrideField (optimistic)", () => {
  test("optimistically updates the slug entry then persists", async () => {
    useDomainOverridesStore.setState({
      overrides: {
        research: {
          classify_model: null,
          default_model: null,
          temperature: null,
          max_output_tokens: null,
        },
      },
      loaded: true,
    });
    configSetMock.mockResolvedValue({
      text: "",
      data: { key: "domain_overrides.research.default_model", value: "sonnet-4.6" },
    });

    await useDomainOverridesStore
      .getState()
      .setOverrideField("research", "default_model", "sonnet-4.6");

    expect(
      useDomainOverridesStore.getState().overrides.research.default_model,
    ).toBe("sonnet-4.6");
    // Other fields untouched on the same slug.
    expect(
      useDomainOverridesStore.getState().overrides.research.classify_model,
    ).toBeNull();
    expect(configSetMock).toHaveBeenCalledWith({
      key: "domain_overrides.research.default_model",
      value: "sonnet-4.6",
    });
  });

  test("seeds an empty entry when the slug is not yet present", async () => {
    // The backend prunes empty slug entries; if the user opens the
    // override form on a slug with no overrides yet, the store starts
    // from the empty-shape default.
    useDomainOverridesStore.setState({ overrides: {}, loaded: true });
    configSetMock.mockResolvedValue({
      text: "",
      data: { key: "domain_overrides.work.temperature", value: 0.7 },
    });

    await useDomainOverridesStore
      .getState()
      .setOverrideField("work", "temperature", 0.7);

    expect(useDomainOverridesStore.getState().overrides.work).toEqual({
      classify_model: null,
      default_model: null,
      temperature: 0.7,
      max_output_tokens: null,
    });
  });

  test("reverts + surfaces error on configSet failure", async () => {
    useDomainOverridesStore.setState({
      overrides: {
        research: {
          classify_model: "haiku-3.5",
          default_model: null,
          temperature: null,
          max_output_tokens: null,
        },
      },
      loaded: true,
    });
    configSetMock.mockRejectedValue(new Error("invalid model"));

    await expect(
      useDomainOverridesStore
        .getState()
        .setOverrideField("research", "classify_model", "bogus-model"),
    ).rejects.toThrow("invalid model");

    // Revert: classify_model restored to the prior "haiku-3.5".
    expect(
      useDomainOverridesStore.getState().overrides.research.classify_model,
    ).toBe("haiku-3.5");
    expect(useDomainOverridesStore.getState().error?.message).toBe(
      "invalid model",
    );
  });
});

describe("useDomainOverridesStore — BroadcastChannel outbound posts", () => {
  test("setOverrideField posts the optimistic overrides map to peers", async () => {
    useDomainOverridesStore.setState({
      overrides: {},
      loaded: true,
    });
    configSetMock.mockResolvedValue({
      text: "",
      data: { key: "domain_overrides.research.temperature", value: 0.5 },
    });

    const peer = makePeerChannel();
    const messages: Array<{ overrides: Record<string, DomainOverrideEntry> }> =
      [];
    peer.onmessage = (e) => messages.push(e.data);

    await useDomainOverridesStore
      .getState()
      .setOverrideField("research", "temperature", 0.5);

    await waitForCondition(() => messages.length > 0, 100);
    expect(messages[0]!.overrides.research?.temperature).toBe(0.5);

    peer.close();
  });

  test("refresh() failure does NOT post (errors are per-tab transport state)", async () => {
    configGetMock.mockRejectedValue(new Error("boom"));

    const peer = makePeerChannel();
    const messages: unknown[] = [];
    peer.onmessage = (e) => messages.push(e.data);

    await useDomainOverridesStore.getState().refresh();
    await new Promise((r) => setTimeout(r, 50));

    expect(messages).toHaveLength(0);
    peer.close();
  });
});

describe("useDomainOverridesStore — BroadcastChannel inbound apply (no echo)", () => {
  test("inbound peer post updates the store within 100ms without re-broadcasting", async () => {
    const observer = makePeerChannel();
    const observed: Array<{ overrides: Record<string, DomainOverrideEntry> }> =
      [];
    observer.onmessage = (e) => observed.push(e.data);

    const peer = makePeerChannel();
    const payload = {
      overrides: {
        research: {
          classify_model: "haiku-3.5",
          default_model: null,
          temperature: 0.3,
          max_output_tokens: null,
        },
      },
    };
    peer.postMessage(payload);

    await waitForCondition(
      () =>
        useDomainOverridesStore.getState().overrides.research?.temperature ===
        0.3,
      100,
    );

    expect(
      useDomainOverridesStore.getState().overrides.research?.classify_model,
    ).toBe("haiku-3.5");

    // No re-broadcast: observer sees ONE message (the peer's original)
    // and not a second echo from the store's internal channel.
    await new Promise((r) => setTimeout(r, 50));
    expect(observed).toHaveLength(1);
    expect(observed[0]!.overrides.research?.temperature).toBe(0.3);

    peer.close();
    observer.close();
  });
});
