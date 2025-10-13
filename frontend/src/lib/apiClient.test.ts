import { afterEach, describe, expect, it, vi } from "vitest";

import {
  request,
  setAccessToken,
  setRefreshHandler,
  setUnauthorizedHandler,
} from "./apiClient";

describe("apiClient request", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    vi.restoreAllMocks();
    setAccessToken(undefined);
    setRefreshHandler(undefined);
    setUnauthorizedHandler(undefined);
    global.fetch = originalFetch;
  });

  it("retries with a refreshed token after a 401", async () => {
    const fetchMock = vi
      .fn<Parameters<typeof fetch>, ReturnType<typeof fetch>>()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );

    global.fetch = fetchMock as unknown as typeof fetch;

    const unauthorizedSpy = vi.fn();
    setUnauthorizedHandler(unauthorizedSpy);

    setAccessToken("expired-token");
    setRefreshHandler(async () => {
      setAccessToken("refreshed-token");
      return "refreshed-token";
    });

    const result = await request<{ ok: boolean }>("/example");

    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);

    const firstCallInit = fetchMock.mock.calls[0][1];
    const secondCallInit = fetchMock.mock.calls[1][1];

    const firstRequestHeaders = new Headers(firstCallInit?.headers);
    const secondRequestHeaders = new Headers(secondCallInit?.headers);

    expect(firstRequestHeaders.get("Authorization")).toBe("Bearer expired-token");
    expect(secondRequestHeaders.get("Authorization")).toBe("Bearer refreshed-token");
    expect(unauthorizedSpy).not.toHaveBeenCalled();
  });
});
