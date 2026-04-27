/**
 * Plan 10 Task 7 — useDomains hook contract.
 *
 * Three behaviours pinned here:
 *
 *   1. The hook resolves with the live domain list (mocked listDomains),
 *      humanises the slug into a label, and surfaces the
 *      configured/on_disk flags.
 *
 *   2. Subsequent ``useDomains()`` calls share one in-flight fetch via
 *      the module-level singleton cache — peer surfaces (topbar +
 *      browse) shouldn't both trigger a network round-trip.
 *
 *   3. ``invalidateDomainsCache()`` drops the cache so the next mount
 *      re-fetches. This is the seam the settings panel uses after
 *      Add/Rename/Delete.
 */

import { describe, expect, test, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

const { listDomainsMock } = vi.hoisted(() => ({
  listDomainsMock: vi.fn(),
}));

vi.mock("@/lib/api/tools", () => ({
  listDomains: listDomainsMock,
}));

import {
  useDomains,
  invalidateDomainsCache,
  humaniseDomain,
  _setDomainsCacheForTesting,
} from "@/lib/hooks/use-domains";

beforeEach(() => {
  listDomainsMock.mockReset();
  // Drop any cache state from a prior test so the singleton starts
  // empty for each case.
  _setDomainsCacheForTesting(null);
});

describe("useDomains", () => {
  test("resolves with humanised labels + configured/on_disk flags", async () => {
    listDomainsMock.mockResolvedValue({
      text: "",
      data: {
        domains: ["personal", "research", "work"],
        entries: [
          { slug: "personal", configured: true, on_disk: true },
          { slug: "research", configured: true, on_disk: true },
          { slug: "side_project", configured: true, on_disk: false },
          { slug: "work", configured: true, on_disk: true },
        ],
      },
    });

    const { result } = renderHook(() => useDomains());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.domains.map((d) => d.slug)).toEqual([
      "personal",
      "research",
      "side_project",
      "work",
    ]);
    const sideProject = result.current.domains.find(
      (d) => d.slug === "side_project",
    );
    expect(sideProject).toBeDefined();
    expect(sideProject!.label).toBe("Side Project");
    expect(sideProject!.configured).toBe(true);
    expect(sideProject!.on_disk).toBe(false);
  });

  test("two mounts share one in-flight fetch via the module cache", async () => {
    listDomainsMock.mockResolvedValue({
      text: "",
      data: { domains: ["research"], entries: [{ slug: "research", configured: true, on_disk: true }] },
    });

    const a = renderHook(() => useDomains());
    const b = renderHook(() => useDomains());

    await waitFor(() => {
      expect(a.result.current.loading).toBe(false);
      expect(b.result.current.loading).toBe(false);
    });
    // Singleton cache means listDomains was called exactly once even
    // though two consumers mounted.
    expect(listDomainsMock).toHaveBeenCalledTimes(1);
  });

  test("invalidateDomainsCache forces a re-fetch on the next mount", async () => {
    listDomainsMock.mockResolvedValue({
      text: "",
      data: { domains: ["research"], entries: [{ slug: "research", configured: true, on_disk: true }] },
    });

    const first = renderHook(() => useDomains());
    await waitFor(() => expect(first.result.current.loading).toBe(false));
    expect(listDomainsMock).toHaveBeenCalledTimes(1);

    invalidateDomainsCache();

    const second = renderHook(() => useDomains());
    await waitFor(() => expect(second.result.current.loading).toBe(false));
    expect(listDomainsMock).toHaveBeenCalledTimes(2);
  });
});

describe("humaniseDomain", () => {
  test("title-cases dash- and underscore-separated slugs", () => {
    expect(humaniseDomain("research")).toBe("Research");
    expect(humaniseDomain("side_project")).toBe("Side Project");
    expect(humaniseDomain("client-work")).toBe("Client Work");
    expect(humaniseDomain("a-b_c")).toBe("A B C");
  });
});
