import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { MetricRow } from "./useDashboardStore";

const originalFetch = globalThis.fetch;

describe("useDashboardStore loadMetrics", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.doUnmock("../lib/apiClient");
    if (typeof originalFetch === "undefined") {
      delete (globalThis as typeof globalThis & { fetch?: unknown }).fetch;
    } else {
      globalThis.fetch = originalFetch;
    }
  });

  it("loads metrics from mock data when mock mode is enabled", async () => {
    const sampleRows: MetricRow[] = [
      {
        date: "2024-01-01",
        platform: "Meta",
        campaign: "Awareness",
        parish: "Kingston",
        impressions: 1200,
        clicks: 120,
        spend: 300,
        conversions: 12,
        roas: 4,
      },
    ];

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(sampleRows),
    });

    const apiGetMock = vi.fn();

    vi.stubEnv("VITE_MOCK_MODE", "true");
    globalThis.fetch = fetchMock as typeof globalThis.fetch;
    vi.doMock("../lib/apiClient", () => ({
      default: {
        get: apiGetMock,
      },
    }));

    const { default: useDashboardStore } = await import("./useDashboardStore");

    await useDashboardStore.getState().loadMetrics();

    expect(fetchMock).toHaveBeenCalledWith("/sample_metrics.json");
    expect(apiGetMock).not.toHaveBeenCalled();
    expect(useDashboardStore.getState().rows).toEqual(sampleRows);
    expect(useDashboardStore.getState().status).toBe("loaded");
  });

  it("loads metrics from the API when mock mode is disabled", async () => {
    const apiRows: MetricRow[] = [
      {
        date: "2024-02-01",
        platform: "Google",
        campaign: "Search",
        parish: "Montego Bay",
        impressions: 900,
        clicks: 90,
        spend: 250,
        conversions: 10,
        roas: 3.2,
      },
    ];

    const fetchMock = vi.fn();
    const apiGetMock = vi.fn().mockResolvedValue({ data: apiRows });

    vi.stubEnv("VITE_MOCK_MODE", "false");
    globalThis.fetch = fetchMock as typeof globalThis.fetch;
    vi.doMock("../lib/apiClient", () => ({
      default: {
        get: apiGetMock,
      },
    }));

    const { default: useDashboardStore } = await import("./useDashboardStore");

    await useDashboardStore.getState().loadMetrics();

    expect(apiGetMock).toHaveBeenCalledWith("/metrics/");
    expect(fetchMock).not.toHaveBeenCalled();
    expect(useDashboardStore.getState().rows).toEqual(apiRows);
    expect(useDashboardStore.getState().status).toBe("loaded");
  });
});
