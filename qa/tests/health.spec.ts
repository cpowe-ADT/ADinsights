import { expect, test } from "./fixtures/base";
import { skipWhenNoLiveApi } from "../utils/live";

test.describe("health endpoints", () => {
  skipWhenNoLiveApi(test);

  test("respond with healthy payloads", async ({ page, mockMode, liveApi }) => {
    test.skip(!mockMode && !liveApi.ready, "Live API is not configured");

    const mockedResponses: Record<string, unknown> = {
      "/api/health/": { status: "ok" },
      "/api/health/airbyte/": {
        status: "ok",
        latest_sync: {
          status: "succeeded",
          seconds_since_finished: 180,
        },
      },
      "/api/health/dbt/": {
        status: "ok",
        latest_run: {
          status: "success",
          finished_at: "2024-09-01T08:00:00Z",
        },
      },
    };

    if (mockMode) {
      await page.route("**/api/health/**", (route) => {
        const url = new URL(route.request().url());
        const payload = mockedResponses[url.pathname];
        if (!payload) {
          void route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
          return;
        }
        void route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(payload),
        });
      });
    }

    await page.goto("/");

    const results = await page.evaluate(async () => {
      const endpoints = ["/api/health/", "/api/health/airbyte/", "/api/health/dbt/"];
      const responses = [] as Array<{ endpoint: string; status: number; body: unknown }>;
      for (const endpoint of endpoints) {
        const response = await fetch(endpoint);
        let body: unknown = null;
        try {
          body = await response.json();
        } catch (error) {
          body = { error: String(error) };
        }
        responses.push({ endpoint, status: response.status, body });
      }
      return responses;
    });

    for (const { endpoint, status, body } of results) {
      expect(status, `${endpoint} status`).toBe(200);
      expect(body).toBeTruthy();
      const parsed = body as Record<string, unknown>;
      expect(parsed.status).toBe("ok");
    }

    if (mockMode) {
      const airbytePayload = results.find((item) => item.endpoint.endsWith("/api/health/airbyte/"));
      expect(airbytePayload?.body).toMatchObject({
        latest_sync: expect.objectContaining({ status: expect.stringMatching(/succeeded|ok/i) }),
      });

      const dbtPayload = results.find((item) => item.endpoint.endsWith("/api/health/dbt/"));
      expect(dbtPayload?.body).toMatchObject({
        latest_run: expect.objectContaining({ status: expect.stringMatching(/success|ok/i) }),
      });
    }

    if (mockMode) {
      await page.unroute("**/api/health/**");
    }
  });
});
