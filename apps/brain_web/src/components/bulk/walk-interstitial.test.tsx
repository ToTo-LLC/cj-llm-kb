import {
  describe,
  expect,
  test,
  beforeEach,
  afterEach,
  vi,
} from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, screen, act, waitFor } from "@testing-library/react";

/**
 * Plan 26 T3 — EventSource lifecycle for the walk-phase interstitial.
 *
 * The component subscribes to ``/api/bulk/walk-progress`` via the
 * :func:`subscribeWalkProgress` wrapper. Four event-type callbacks
 * dispatch to UI state; a transport-level ``onerror`` BEFORE the first
 * frame falls back to timer-only (graceful degradation per D3).
 *
 * Five exercises:
 *   1. Happy path: walk_started → walk_progress → walk_complete updates
 *      ``filesSeen`` + ``currentPath`` and survives the terminal frame.
 *   2. walk_error frame flips into the error layout and calls
 *      ``endWalk(false)``.
 *   3. Transport error BEFORE any frame triggers timer fallback (live
 *      counter does NOT render).
 *   4. Transport error AFTER frames have landed is terminal (sets error
 *      copy + calls endWalk(false)).
 *   5. Unmount calls EventSource.close().
 *
 * We mock ``global.EventSource`` with a small class that records the
 * URL, exposes ``emit`` / ``emitError`` helpers, and stubs ``close``
 * with a spy so we can assert lifecycle.
 */

import { WalkInterstitial } from "@/components/bulk/walk-interstitial";
import { useBulkStore } from "@/lib/state/bulk-store";
import { useSystemStore } from "@/lib/state/system-store";
import { useTokenStore } from "@/lib/state/token-store";

interface MockInstance {
  url: string;
  onmessage: ((event: MessageEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
  onopen: ((event: Event) => void) | null;
  close: ReturnType<typeof vi.fn>;
  emit: (data: unknown) => void;
  emitError: () => void;
}

let instances: MockInstance[] = [];

class MockEventSource implements MockInstance {
  url: string;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onopen: ((event: Event) => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    instances.push(this);
  }

  emit(data: unknown): void {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }

  emitError(): void {
    this.onerror?.(new Event("error"));
  }
}

function latestInstance(): MockInstance {
  if (instances.length === 0) {
    throw new Error("no EventSource instance was created");
  }
  return instances[instances.length - 1];
}

function resetStore(): void {
  useBulkStore.setState({
    step: 1,
    folder: null,
    domain: "auto",
    cap: 20,
    files: [],
    applying: false,
    applyIdx: 0,
    cancelled: false,
    done: false,
    results: { applied: [], failed: [], quarantined: [] },
    phase: "idle",
    walkPath: null,
    walkStartedAt: null,
    applyStartedAt: null,
  });
}

describe("walk-interstitial EventSource wiring (Plan 26 T3)", () => {
  beforeEach(() => {
    instances = [];
    (globalThis as unknown as { EventSource: typeof MockEventSource }).EventSource =
      MockEventSource;
    resetStore();
    // Clear toasts so the per-test toast assertions are scoped.
    useSystemStore.setState({ toasts: [] });
    // The wrapper bails out without opening the EventSource when there's
    // no token — we want the streaming path exercised, so seed one.
    useTokenStore.setState({ token: "test-token-abc" });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("happy path: walk_started → walk_progress → walk_complete updates filesSeen + currentPath", async () => {
    useBulkStore.setState({
      phase: "walking",
      walkPath: "/Users/test/research",
      walkStartedAt: Date.now(),
    });

    render(<WalkInterstitial />);

    // EventSource constructed with the right URL (path + token both
    // URL-encoded into the query string).
    await waitFor(() => expect(instances).toHaveLength(1));
    const es = latestInstance();
    expect(es.url).toContain("/api/bulk/walk-progress");
    expect(es.url).toContain(
      "path=" + encodeURIComponent("/Users/test/research"),
    );
    expect(es.url).toContain("token=test-token-abc");

    // Initially in the "connecting" state — no live counter yet.
    expect(screen.queryByTestId("walk-files-seen")).not.toBeInTheDocument();

    // walk_started arrives; UI still shows the connecting layout until a
    // walk_progress frame lands.
    act(() => {
      es.emit({ type: "walk_started", path: "/Users/test/research" });
    });
    expect(screen.queryByTestId("walk-files-seen")).not.toBeInTheDocument();

    // walk_progress — live counter renders with the REAL file count and
    // the most-recent scanned path (the SSE wrapper hands us
    // ``current_path`` from the backend per ``WalkProgress``).
    act(() => {
      es.emit({
        type: "walk_progress",
        files_seen: 150,
        current_path: "/Users/test/research/papers/foo.pdf",
      });
    });
    expect(screen.getByTestId("walk-files-seen")).toHaveTextContent(
      "150 files seen",
    );
    expect(screen.getByTestId("walk-path")).toHaveTextContent(
      "/Users/test/research/papers/foo.pdf",
    );
    expect(screen.getByTestId("walk-interstitial")).toHaveAttribute(
      "data-streaming-mode",
      "live",
    );

    // walk_complete — wrapper closes the EventSource on the terminal
    // frame; the caller's runDryRun separately drives the wizard step
    // transition, so the UI here stays mounted until phase flips.
    act(() => {
      es.emit({
        type: "walk_complete",
        total_count: 250,
        plan_id: "abc-123",
      });
    });
    expect(es.close).toHaveBeenCalled();
  });

  test("walk_error frame pushes danger toast + calls endWalk(false)", () => {
    useBulkStore.setState({
      phase: "walking",
      walkPath: "/no/access",
      walkStartedAt: Date.now(),
    });

    render(<WalkInterstitial />);
    const es = latestInstance();

    act(() => {
      es.emit({
        type: "walk_error",
        error_message: "Permission denied: /no/access",
        error_code: "permission_denied",
      });
    });

    // The error_code → user-facing copy mapping shows in the toast's
    // ``lead``; the verbose ``error_message`` goes into ``msg``.
    const toasts = useSystemStore.getState().toasts;
    expect(toasts).toHaveLength(1);
    expect(toasts[0].lead).toBe("Permission denied while scanning folder.");
    expect(toasts[0].msg).toBe("Permission denied: /no/access");
    expect(toasts[0].variant).toBe("danger");

    // The structured walk_error frame closes the stream + flips the
    // store phase to ``error`` via ``endWalk(false)``. The phase change
    // unmounts the interstitial (parent picker UI re-renders).
    expect(useBulkStore.getState().phase).toBe("error");
    expect(es.close).toHaveBeenCalled();
  });

  test("transport error before first frame triggers timer fallback (no live counter)", () => {
    useBulkStore.setState({
      phase: "walking",
      walkPath: "/Users/test/research",
      walkStartedAt: Date.now(),
    });

    render(<WalkInterstitial />);
    const es = latestInstance();

    // Connection dies before any data frame arrives — the component
    // falls back to timer-only.
    act(() => {
      es.emitError();
    });

    expect(screen.getByTestId("walk-interstitial")).toHaveAttribute(
      "data-streaming-mode",
      "timer-fallback",
    );
    // No live counter — that's the fallback contract.
    expect(screen.queryByTestId("walk-files-seen")).not.toBeInTheDocument();
    // No toast either — graceful degradation is silent (the caller's
    // separate bulkImport HTTP call surfaces any actual failure).
    expect(useSystemStore.getState().toasts).toHaveLength(0);
    // The store stays in walking — the dry-run HTTP path still drives
    // the eventual transition.
    expect(useBulkStore.getState().phase).toBe("walking");
    expect(es.close).toHaveBeenCalled();
  });

  test("transport error after frames have landed is terminal (toast + endWalk(false))", () => {
    useBulkStore.setState({
      phase: "walking",
      walkPath: "/Users/test/research",
      walkStartedAt: Date.now(),
    });

    render(<WalkInterstitial />);
    const es = latestInstance();

    // A progress frame lands first — receivedAnyEvent becomes true.
    act(() => {
      es.emit({
        type: "walk_progress",
        files_seen: 50,
        current_path: "/Users/test/research/a.md",
      });
    });
    expect(screen.getByTestId("walk-files-seen")).toBeInTheDocument();

    // Then the transport drops. With at least one frame received, the
    // component treats this as terminal (NOT a fallback case).
    act(() => {
      es.emitError();
    });

    const toasts = useSystemStore.getState().toasts;
    expect(toasts).toHaveLength(1);
    expect(toasts[0].lead).toBe("Scan failed.");
    expect(toasts[0].variant).toBe("danger");
    expect(useBulkStore.getState().phase).toBe("error");
    expect(es.close).toHaveBeenCalled();
  });

  test("unmount calls EventSource.close()", () => {
    useBulkStore.setState({
      phase: "walking",
      walkPath: "/Users/test/research",
      walkStartedAt: Date.now(),
    });

    const { unmount } = render(<WalkInterstitial />);
    const es = latestInstance();
    expect(es.close).not.toHaveBeenCalled();

    unmount();

    expect(es.close).toHaveBeenCalledTimes(1);
  });

  test("no token in store → fall back to timer-only (no EventSource opened)", () => {
    useTokenStore.setState({ token: null });
    useBulkStore.setState({
      phase: "walking",
      walkPath: "/Users/test/research",
      walkStartedAt: Date.now(),
    });

    render(<WalkInterstitial />);

    // No EventSource was constructed.
    expect(instances).toHaveLength(0);
    // Timer-only layout — same contract as the transport-fallback path.
    expect(screen.getByTestId("walk-interstitial")).toHaveAttribute(
      "data-streaming-mode",
      "timer-fallback",
    );
    expect(screen.queryByTestId("walk-files-seen")).not.toBeInTheDocument();
  });
});
