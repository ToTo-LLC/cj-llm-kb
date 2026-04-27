import { afterAll, beforeEach, describe, expect, test, vi } from "vitest";

import { apiFetch } from "@/lib/api/client";
import { ApiError } from "@/lib/api/types";
import { listDomains, search, ALL_TOOL_NAMES } from "@/lib/api/tools";
import { useTokenStore } from "@/lib/state/token-store";

type FetchMock = ReturnType<typeof vi.fn>;

describe("apiFetch", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.resetAllMocks();
    global.fetch = vi.fn() as unknown as typeof fetch;
    // Reset token store between tests to avoid cross-test bleed.
    useTokenStore.setState({ token: null });
  });

  afterAll(() => {
    global.fetch = originalFetch;
  });

  test("returns decoded ToolResponse envelope on 200 and attaches X-Brain-Token", async () => {
    useTokenStore.setState({ token: "tkn-xyz" });
    (global.fetch as unknown as FetchMock).mockResolvedValue(
      new Response(JSON.stringify({ text: "ok", data: { foo: 1 } }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const res = await apiFetch<{ foo: number }>("/api/tools/brain_noop", {
      method: "POST",
      body: JSON.stringify({}),
    });
    expect(res.text).toBe("ok");
    expect(res.data).toEqual({ foo: 1 });

    const call = (global.fetch as unknown as FetchMock).mock.calls[0];
    // Plan 08 Task 2: direct same-origin call — no /api/proxy prefix.
    expect(call[0]).toBe("/api/tools/brain_noop");
    const init = call[1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBe("application/json");
    expect(headers["X-Brain-Token"]).toBe("tkn-xyz");
  });

  test("omits X-Brain-Token header when token store is empty", async () => {
    useTokenStore.setState({ token: null });
    (global.fetch as unknown as FetchMock).mockResolvedValue(
      new Response(JSON.stringify({ text: "ok", data: null }), { status: 200 }),
    );
    await apiFetch("/api/tools/brain_noop", { method: "POST", body: "{}" });
    const init = (global.fetch as unknown as FetchMock).mock
      .calls[0][1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect("X-Brain-Token" in headers).toBe(false);
  });

  test("throws ApiError with typed envelope on 4xx", async () => {
    (global.fetch as unknown as FetchMock).mockResolvedValue(
      new Response(
        JSON.stringify({
          error: "invalid_input",
          message: "path is required",
          detail: { errors: [{ loc: ["path"], msg: "required" }] },
        }),
        { status: 400, headers: { "content-type": "application/json" } },
      ),
    );
    await expect(
      apiFetch("/api/tools/brain_read_note", {
        method: "POST",
        body: "{}",
      }),
    ).rejects.toMatchObject({
      name: "ApiError",
      status: 400,
      code: "invalid_input",
      message: "path is required",
      detail: { errors: [{ loc: ["path"], msg: "required" }] },
    });
  });

  test("throws ApiError with typed envelope on 5xx", async () => {
    (global.fetch as unknown as FetchMock).mockResolvedValue(
      new Response(
        JSON.stringify({
          error: "internal",
          message: "boom",
          detail: null,
        }),
        { status: 500 },
      ),
    );
    const err = await apiFetch("/api/tools/brain_noop", {
      method: "POST",
      body: "{}",
    }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(500);
    expect((err as ApiError).code).toBe("internal");
  });

  test("falls back to unknown code on unparseable error body", async () => {
    (global.fetch as unknown as FetchMock).mockResolvedValue(
      new Response("<html>gateway timeout</html>", {
        status: 502,
        statusText: "Bad Gateway",
      }),
    );
    const err = await apiFetch("/api/tools/brain_noop", {
      method: "POST",
      body: "{}",
    }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(502);
    expect((err as ApiError).code).toBe("unknown");
    expect((err as ApiError).detail).toBeNull();
  });

  test("maps 401 without a JSON body to code='unauthorized'", async () => {
    (global.fetch as unknown as FetchMock).mockResolvedValue(
      new Response("<html>nope</html>", { status: 401 }),
    );
    const err = await apiFetch("/api/tools/brain_noop", {
      method: "POST",
      body: "{}",
    }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(401);
    expect((err as ApiError).code).toBe("unauthorized");
  });

  test("per-tool bindings cover all 36 tools + hit same-origin /api path", async () => {
    // Plan 08 Task 2: bindings target ``/api/tools/<name>`` directly
    // (no proxy prefix). Issue #18 brought the count to 35 by adding
    // ``brain_list_threads``; issue #17 brought it to 36 by adding
    // ``brain_export_thread``.
    expect(ALL_TOOL_NAMES.length).toBe(36);

    (global.fetch as unknown as FetchMock).mockResolvedValue(
      new Response(JSON.stringify({ text: "", data: { domains: ["research"] } }), {
        status: 200,
      }),
    );
    await listDomains();
    expect((global.fetch as unknown as FetchMock).mock.calls[0][0]).toBe(
      "/api/tools/brain_list_domains",
    );

    (global.fetch as unknown as FetchMock).mockResolvedValueOnce(
      new Response(
        JSON.stringify({ text: "", data: { hits: [], top_k_used: 5 } }),
        { status: 200 },
      ),
    );
    await search({ query: "foo", top_k: 5 });
    const call = (global.fetch as unknown as FetchMock).mock.calls[1];
    expect(call[0]).toBe("/api/tools/brain_search");
    const init = call[1] as RequestInit;
    expect(JSON.parse(init.body as string)).toEqual({
      query: "foo",
      top_k: 5,
    });
  });
});
