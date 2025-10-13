import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./fixtures/base";
import { DashboardPage } from "../page-objects";
import {
  aggregatedMetricsResponse,
  campaignSnapshot,
  fulfillJson,
  parishAggregates,
} from "./support/sampleData";

const geoJson = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { name: "Kingston" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [-76.9, 17.9],
            [-76.7, 17.9],
            [-76.7, 18.1],
            [-76.9, 18.1],
            [-76.9, 17.9],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { name: "St Andrew" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [-76.8, 18.2],
            [-76.6, 18.2],
            [-76.6, 18.4],
            [-76.8, 18.4],
            [-76.8, 18.2],
          ],
        ],
      },
    },
  ],
} as const;

const DESKTOP_VIEWPORT = { width: 1280, height: 720 } as const;

async function expectNoSeriousViolations(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page }).analyze();
  const seriousViolations = results.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact ?? ""),
  );

  expect(seriousViolations, `Serious accessibility violations detected: ${JSON.stringify(seriousViolations, null, 2)}`).toHaveLength(0);
}

test.describe("parish choropleth", () => {
  test("displays tooltip data on hover", async ({ page, mockMode }) => {
    if (mockMode) {
      await page.route("**/sample_campaign_performance.json", (route) =>
        fulfillJson(route, campaignSnapshot)
      );
      await page.route("**/sample_creative_performance.json", (route) =>
        fulfillJson(route, aggregatedMetricsResponse.creative)
      );
      await page.route("**/sample_budget_pacing.json", (route) =>
        fulfillJson(route, aggregatedMetricsResponse.budget)
      );
      await page.route("**/sample_parish_aggregates.json", (route) =>
        fulfillJson(route, parishAggregates)
      );
    } else {
      await page.route("**/api/metrics/**", (route) => fulfillJson(route, aggregatedMetricsResponse));
    }

    await page.route("**/jm_parishes.json", (route) => {
      fulfillJson(route, geoJson);
    });

    await page.setViewportSize(DESKTOP_VIEWPORT);
    const dashboard = new DashboardPage(page);
    await dashboard.open();
    await dashboard.waitForMetricsLoaded(campaignSnapshot.rows.length);
    await dashboard.mapPanel.waitForFeatureCount(geoJson.features.length);

    const tooltipText = await dashboard.mapPanel.hoverEachFeatureUntil((text) => text.includes("Kingston"));
    expect(tooltipText).toBeTruthy();
    expect(tooltipText ?? "").toContain("IMPRESSIONS");

    const kingstonMetrics = parishAggregates.find((row) => row.parish === "Kingston");
    expect(kingstonMetrics).toBeDefined();
    const normalizedTooltip = (tooltipText ?? "").replace(/[\,\s]/g, "");
    expect(normalizedTooltip).toContain(`IMPRESSIONS:${kingstonMetrics?.impressions ?? 0}`);

    const screenshot = await page.screenshot({
      animations: "disabled",
      fullPage: true,
      encoding: "base64",
    });
    await expect(screenshot).toMatchSnapshot("map-chromium-desktop.txt");

    await expectNoSeriousViolations(page);

    await page.unroute("**/jm_parishes.json");
    if (mockMode) {
      await page.unroute("**/sample_campaign_performance.json");
      await page.unroute("**/sample_creative_performance.json");
      await page.unroute("**/sample_budget_pacing.json");
      await page.unroute("**/sample_parish_aggregates.json");
    } else {
      await page.unroute("**/api/metrics/**");
    }
  });
});
