import { beforeEach, describe, expect, test, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

/**
 * Bootstrap context (Plan 08 Task 2).
 *
 * Replaces the server-side ``readToken()`` flow. On mount the provider:
 *   1. GETs ``/api/setup-status`` (Origin-gated, no token).
 *   2. If ``is_first_run`` → ``router.push("/setup/")`` and resolve ``loading=false``.
 *   3. Else GETs ``/api/token`` → stores ``token`` in context + Zustand
 *      ``useTokenStore`` so module-level apiFetch + WS clients can read it.
 *
 * Network failures surface as ``error = "Can't reach brain — is it running?"``
 * — the BootGate reads that string + renders a retry card.
 */

const { routerPushMock, routerReplaceMock } = vi.hoisted(() => ({
  routerPushMock: vi.fn(),
  routerReplaceMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPushMock, replace: routerReplaceMock }),
  usePathname: () => "/",
}));

import {
  BootstrapProvider,
  useBootstrap,
} from "@/lib/bootstrap/bootstrap-context";
import { useTokenStore, getToken } from "@/lib/state/token-store";

type FetchMock = ReturnType<typeof vi.fn>;

function Probe(): React.ReactElement {
  const { token, isFirstRun, vaultPath, loading, error } = useBootstrap();
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="token">{token ?? "(null)"}</span>
      <span data-testid="is-first-run">{String(isFirstRun)}</span>
      <span data-testid="vault-path">{vaultPath ?? "(null)"}</span>
      <span data-testid="error">{error ?? "(null)"}</span>
    </div>
  );
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("BootstrapProvider", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.resetAllMocks();
    global.fetch = vi.fn() as unknown as typeof fetch;
    // Reset token store between tests so getToken() doesn't leak.
    act(() => {
      useTokenStore.setState({ token: null });
    });
  });

  test("while setup-status is inflight, loading=true and children see null token", async () => {
    // Never-resolving fetch so the effect stays in the loading branch.
    (global.fetch as unknown as FetchMock).mockImplementation(
      () => new Promise<Response>(() => {}),
    );
    render(
      <BootstrapProvider>
        <Probe />
      </BootstrapProvider>,
    );
    expect(screen.getByTestId("loading").textContent).toBe("true");
    expect(screen.getByTestId("token").textContent).toBe("(null)");
    expect(screen.getByTestId("error").textContent).toBe("(null)");
  });

  test("first-run triggers router.push('/setup/') and exposes vaultPath", async () => {
    (global.fetch as unknown as FetchMock).mockResolvedValueOnce(
      jsonResponse({
        has_token: false,
        is_first_run: true,
        vault_exists: false,
        vault_path: "/tmp/brain-vault",
      }),
    );
    render(
      <BootstrapProvider>
        <Probe />
      </BootstrapProvider>,
    );
    await waitFor(() => {
      expect(routerPushMock).toHaveBeenCalledWith("/setup/");
    });
    expect(screen.getByTestId("is-first-run").textContent).toBe("true");
    expect(screen.getByTestId("vault-path").textContent).toBe(
      "/tmp/brain-vault",
    );
    // When first-run fires, we don't call /api/token — only setup-status.
    expect((global.fetch as unknown as FetchMock).mock.calls).toHaveLength(1);
  });

  test("non-first-run fetches /api/token and stores it in token store", async () => {
    (global.fetch as unknown as FetchMock)
      .mockResolvedValueOnce(
        jsonResponse({
          has_token: true,
          is_first_run: false,
          vault_exists: true,
          vault_path: "/tmp/brain-vault",
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ token: "tkn-abc-123" }));

    render(
      <BootstrapProvider>
        <Probe />
      </BootstrapProvider>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("token").textContent).toBe("tkn-abc-123");
    });
    expect(screen.getByTestId("loading").textContent).toBe("false");
    expect(screen.getByTestId("is-first-run").textContent).toBe("false");
    expect(getToken()).toBe("tkn-abc-123");
    expect(routerPushMock).not.toHaveBeenCalled();
    // setup-status + token — two fetches in that order.
    const calls = (global.fetch as unknown as FetchMock).mock.calls;
    expect(calls[0][0]).toBe("/api/setup-status");
    expect(calls[1][0]).toBe("/api/token");
  });

  test("network failure surfaces 'Can't reach brain' error", async () => {
    (global.fetch as unknown as FetchMock).mockRejectedValue(
      new TypeError("Failed to fetch"),
    );
    render(
      <BootstrapProvider>
        <Probe />
      </BootstrapProvider>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("error").textContent).toMatch(
        /can't reach brain/i,
      );
    });
    expect(screen.getByTestId("loading").textContent).toBe("false");
    expect(screen.getByTestId("token").textContent).toBe("(null)");
  });

  test("backend 503 on /api/setup-status surfaces 'Setup required'", async () => {
    (global.fetch as unknown as FetchMock).mockResolvedValueOnce(
      new Response("{}", { status: 503 }),
    );
    render(
      <BootstrapProvider>
        <Probe />
      </BootstrapProvider>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("error").textContent).toMatch(
        /setup required/i,
      );
    });
    expect(screen.getByTestId("loading").textContent).toBe("false");
  });
});
