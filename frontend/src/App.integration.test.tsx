import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import useDashboardStore from "./state/useDashboardStore";

vi.mock("./components/ParishMap", () => ({
  default: () => <div data-testid="parish-map" />,
}));

const campaignPayload = {
  summary: {
    currency: "JMD",
    totalSpend: 1000,
    totalImpressions: 2000,
    totalClicks: 300,
    totalConversions: 40,
    averageRoas: 3.2,
  },
  trend: [
    { date: "2024-09-01", spend: 100, conversions: 4, clicks: 20, impressions: 200 },
    { date: "2024-09-02", spend: 120, conversions: 5, clicks: 22, impressions: 240 },
  ],
  rows: [
    {
      id: "cmp_test",
      name: "Test Campaign",
      platform: "Meta",
      status: "Active",
      parish: "Kingston",
      spend: 500,
      impressions: 1000,
      clicks: 150,
      conversions: 20,
      roas: 3.4,
      ctr: 0.15,
      cpc: 3.33,
      cpm: 500,
    },
  ],
};

const creativePayload = [
  {
    id: "cr_test",
    name: "Hero Unit",
    campaignId: "cmp_test",
    campaignName: "Test Campaign",
    platform: "Meta",
    parish: "Kingston",
    spend: 120,
    impressions: 450,
    clicks: 40,
    conversions: 6,
    roas: 3.1,
    ctr: 0.089,
  },
];

const budgetPayload = [
  {
    id: "budget_test",
    campaignName: "Test Campaign",
    parishes: ["Kingston"],
    monthlyBudget: 200,
    spendToDate: 140,
    projectedSpend: 210,
    pacingPercent: 1.05,
  },
];

const parishPayload = [
  {
    parish: "Kingston",
    spend: 500,
    impressions: 1000,
    clicks: 150,
    conversions: 20,
    roas: 3.4,
    campaignCount: 1,
    currency: "JMD",
  },
];

const createResponse = (body: unknown, init?: ResponseInit) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });

describe("App integration", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_MOCK_MODE", "true");
    vi.restoreAllMocks();
    vi.clearAllMocks();
    window.localStorage.clear();
    useDashboardStore.getState().reset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("signs in and renders dashboard data in mock mode", async () => {
    const fetchMock = vi.fn((url: RequestInfo | URL) => {
      if (typeof url === "string" && url.endsWith("/sample_campaign_performance.json")) {
        return Promise.resolve(createResponse(campaignPayload));
      }
      if (typeof url === "string" && url.endsWith("/sample_creative_performance.json")) {
        return Promise.resolve(createResponse(creativePayload));
      }
      if (typeof url === "string" && url.endsWith("/sample_budget_pacing.json")) {
        return Promise.resolve(createResponse(budgetPayload));
      }
      if (typeof url === "string" && url.endsWith("/sample_parish_aggregates.json")) {
        return Promise.resolve(createResponse(parishPayload));
      }
      return Promise.reject(new Error(`Unhandled fetch: ${String(url)}`));
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(
      <AuthProvider>
        <App />
      </AuthProvider>
    );

    await userEvent.type(screen.getByLabelText(/email/i), "user@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "password123");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/sample_campaign_performance.json",
        expect.objectContaining({ method: "GET" })
      )
    );
    expect(await screen.findByText("Test Campaign")).toBeInTheDocument();
    expect(screen.getByTestId("parish-map")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("link", { name: /creatives/i }));
    expect(await screen.findByText("Top creatives")).toBeInTheDocument();
    expect(screen.getByText(/Hero Unit/)).toBeInTheDocument();
  });

  it("shows API errors without breaking the app", async () => {
    const fetchMock = vi.fn((url: RequestInfo | URL) => {
      if (typeof url === "string" && url.endsWith("/sample_campaign_performance.json")) {
        return Promise.resolve(createResponse({ detail: "Server unavailable" }, { status: 503 }));
      }
      if (typeof url === "string" && url.endsWith("/sample_creative_performance.json")) {
        return Promise.resolve(createResponse(creativePayload));
      }
      if (typeof url === "string" && url.endsWith("/sample_budget_pacing.json")) {
        return Promise.resolve(createResponse(budgetPayload));
      }
      if (typeof url === "string" && url.endsWith("/sample_parish_aggregates.json")) {
        return Promise.resolve(createResponse(parishPayload));
      }
      return Promise.reject(new Error(`Unhandled fetch: ${String(url)}`));
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    render(
      <AuthProvider>
        <App />
      </AuthProvider>
    );

    await userEvent.type(screen.getByLabelText(/email/i), "user@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "password123");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/server unavailable/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /budget pacing/i })).toBeInTheDocument();
  });
});
