import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import apiClient from "./lib/apiClient";
import useDashboardStore from "./state/useDashboardStore";

vi.mock("./components/ParishMap", () => ({
  default: () => <div data-testid="parish-map" />,
}));

const futureExp = Math.floor(Date.now() / 1000) + 60 * 60;
const base64Url = (input: string) => Buffer.from(input, "utf-8").toString("base64url");
const accessToken = `${base64Url(JSON.stringify({ alg: "HS256", typ: "JWT" }))}.${base64Url(
  JSON.stringify({ exp: futureExp })
)}.signature`;
const refreshToken = "refresh-token";

const sampleMetrics = [
  {
    date: "2024-10-01",
    platform: "Meta",
    campaign: "Fall Outreach",
    parish: "Kingston",
    impressions: 1200,
    clicks: 120,
    spend: 340,
    conversions: 24,
    roas: 4.2,
  },
];

const loginResponse = {
  access: accessToken,
  refresh: refreshToken,
  tenant_id: "tenant-123",
  user: { email: "user@example.com" },
};

function createJsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response;
}

describe("App integration", () => {
beforeEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  window.localStorage.clear();
  useDashboardStore.getState().reset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

  it("signs in and renders tenant metrics", async () => {
    const fetchMock = vi.fn((url: RequestInfo | URL) => {
      if (typeof url === "string" && url.endsWith("/api/auth/login/")) {
        return Promise.resolve(createJsonResponse(loginResponse));
      }
      if (typeof url === "string" && url.endsWith("/api/auth/refresh/")) {
        return Promise.resolve(createJsonResponse({ access: accessToken }));
      }
      if (typeof url === "string" && url.endsWith("/jm_parishes.json")) {
        return Promise.resolve(createJsonResponse({ type: "FeatureCollection", features: [] }));
      }
      if (typeof url === "string" && url.endsWith("/sample_metrics.json")) {
        return Promise.resolve(createJsonResponse(sampleMetrics));
      }
      return Promise.reject(new Error(`Unhandled fetch: ${String(url)}`));
    });
    vi.stubGlobal("fetch", fetchMock);

    const getSpy = vi.spyOn(apiClient, "get");

    render(
      <AuthProvider>
        <App />
      </AuthProvider>
    );

    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);

    await userEvent.type(emailInput, "user@example.com");
    await userEvent.type(passwordInput, "password123");

    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/auth/login/", expect.any(Object)));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/sample_metrics.json"));
    expect(getSpy).not.toHaveBeenCalled();

    expect(await screen.findByText("Kingston")).toBeInTheDocument();
    expect(screen.getByText(/tenant-123/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /log out/i })).toBeInTheDocument();
  });

  it("surfaces API errors to the user", async () => {
    const fetchMock = vi.fn((url: RequestInfo | URL) => {
      if (typeof url === "string" && url.endsWith("/api/auth/login/")) {
        return Promise.resolve(createJsonResponse(loginResponse));
      }
      if (typeof url === "string" && url.endsWith("/api/auth/refresh/")) {
        return Promise.resolve(createJsonResponse({ access: accessToken }));
      }
      if (typeof url === "string" && url.endsWith("/jm_parishes.json")) {
        return Promise.resolve(createJsonResponse({ type: "FeatureCollection", features: [] }));
      }
      if (typeof url === "string" && url.endsWith("/sample_metrics.json")) {
        return Promise.resolve(createJsonResponse({ detail: "Server unavailable" }, 503));
      }
      return Promise.reject(new Error(`Unhandled fetch: ${String(url)}`));
    });
    vi.stubGlobal("fetch", fetchMock);

    const getSpy = vi.spyOn(apiClient, "get");

    render(
      <AuthProvider>
        <App />
      </AuthProvider>
    );

    await userEvent.type(screen.getByLabelText(/email/i), "user@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "password123");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/server unavailable/i)).toBeInTheDocument();
    expect(screen.getAllByText(/server unavailable/i).length).toBeGreaterThan(0);
    expect(getSpy).not.toHaveBeenCalled();
  });
});
