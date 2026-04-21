import { afterAll, beforeEach, describe, expect, test, vi } from "vitest";
import { NextRequest } from "next/server";

vi.mock("@/lib/auth/token", () => ({
  readToken: vi.fn(),
  invalidateTokenCache: vi.fn(),
}));

import { readToken } from "@/lib/auth/token";
import { GET, POST } from "@/app/api/proxy/[...path]/route";

type FetchMock = ReturnType<typeof vi.fn>;

describe("proxy route", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.resetAllMocks();
    global.fetch = vi.fn() as unknown as typeof fetch;
  });

  afterAll(() => {
    global.fetch = originalFetch;
  });

  test("503 when token not available", async () => {
    (readToken as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(null);
    const req = new NextRequest("http://localhost:4316/api/proxy/healthz", {
      method: "GET",
    });
    const res = await GET(req, {
      params: Promise.resolve({ path: ["healthz"] }),
    });
    expect(res.status).toBe(503);
    const body = await res.json();
    expect(body.error).toBe("setup_required");
  });

  test("attaches X-Brain-Token + Origin on forward", async () => {
    (readToken as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      "test-token-abc",
    );
    (global.fetch as unknown as FetchMock).mockResolvedValue(
      new Response('{"ok":true}', { status: 200 }),
    );
    const req = new NextRequest(
      "http://localhost:4316/api/proxy/api/tools/brain_list_domains",
      {
        method: "POST",
        body: JSON.stringify({}),
      },
    );
    await POST(req, {
      params: Promise.resolve({
        path: ["api", "tools", "brain_list_domains"],
      }),
    });
    const call = (global.fetch as unknown as FetchMock).mock.calls[0];
    const targetUrl = call[0] as string;
    const init = call[1] as RequestInit;
    expect(targetUrl).toBe(
      "http://127.0.0.1:4317/api/tools/brain_list_domains",
    );
    const headers = init.headers as Headers;
    expect(headers.get("X-Brain-Token")).toBe("test-token-abc");
    expect(headers.get("Origin")).toBe("http://localhost:4316");
  });

  test("strips x-brain-token from response headers", async () => {
    (readToken as unknown as ReturnType<typeof vi.fn>).mockResolvedValue("tok");
    const upstreamHeaders = new Headers();
    upstreamHeaders.set("x-brain-token", "leaked");
    upstreamHeaders.set("content-type", "application/json");
    (global.fetch as unknown as FetchMock).mockResolvedValue(
      new Response("{}", { status: 200, headers: upstreamHeaders }),
    );
    const req = new NextRequest("http://localhost:4316/api/proxy/healthz", {
      method: "GET",
    });
    const res = await GET(req, {
      params: Promise.resolve({ path: ["healthz"] }),
    });
    expect(res.headers.get("x-brain-token")).toBeNull();
    expect(res.headers.get("content-type")).toBe("application/json");
  });

  test("preserves upstream status on 4xx", async () => {
    (readToken as unknown as ReturnType<typeof vi.fn>).mockResolvedValue("tok");
    (global.fetch as unknown as FetchMock).mockResolvedValue(
      new Response('{"error":"not_found"}', { status: 404 }),
    );
    const req = new NextRequest(
      "http://localhost:4316/api/proxy/api/tools/nope",
      { method: "POST" },
    );
    const res = await POST(req, {
      params: Promise.resolve({ path: ["api", "tools", "nope"] }),
    });
    expect(res.status).toBe(404);
  });
});
