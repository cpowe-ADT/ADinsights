import { expect, test } from "./fixtures/base";
import { skipWhenNoLiveApi } from "../utils/live";
import { DashboardPage } from "../page-objects";
import { schemaValidate } from "../utils/schemaValidate";

test.describe("health endpoints", () => {
  skipWhenNoLiveApi(test);

  test("respond with healthy payloads", async ({ page, mockMode, liveApi }) => {
    test.skip(!mockMode && !liveApi.ready, "Live API is not configured");

    const mockedResponses: Record<string, unknown> = {
      "/api/health/": { status: "ok" },
      "/api/health/airbyte/": {
        component: "airbyte",
        status: "ok",
        configured: true,
        stale: false,
        last_sync: {
          tenant_id: "11111111-1111-1111-1111-111111111111",
          last_synced_at: "2024-09-01T08:00:00Z",
          last_job_status: "succeeded",
          last_job_id: "123",
        },
      },
      "/api/health/dbt/": {
        component: "dbt",
        status: "ok",
        run_results_path: "/srv/dbt/run_results.json",
        generated_at: "2024-09-01T08:00:00Z",
        failing_models: [],
        stale: false,
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

    const dashboard = new DashboardPage(page);
    await dashboard.open();

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

    const allowedStatuses = new Set([200, 502, 503]);
    for (const { endpoint, status, body } of results) {
      expect(
        allowedStatuses.has(status),
        `${endpoint} status expected one of ${Array.from(allowedStatuses).join(", ")}`
      ).toBe(true);
      await schemaValidate(endpoint, body);
    }

    if (mockMode) {
      const airbytePayload = results.find((item) => item.endpoint.endsWith("/api/health/airbyte/"));
      expect(airbytePayload?.body).toMatchObject({
        component: "airbyte",
        configured: true,
        last_sync: expect.objectContaining({
          tenant_id: expect.any(String),
          last_job_status: expect.any(String),
        }),
      });

      const dbtPayload = results.find((item) => item.endpoint.endsWith("/api/health/dbt/"));
      expect(dbtPayload?.body).toMatchObject({
        component: "dbt",
        generated_at: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T/),
        failing_models: expect.any(Array),
      });
    }

    if (mockMode) {
      await page.unroute("**/api/health/**");
    }
  });
});
