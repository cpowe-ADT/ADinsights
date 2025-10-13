import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./fixtures/base";
import { DashboardPage } from "../page-objects";
import { aggregatedMetricsResponse, fulfillJson, parishAggregates } from "./support/sampleData";

const geoJson = {
  type: "FeatureCollection",
  features: [
    { type: "Feature", properties: { name: "Kingston" }, geometry: { type: "Polygon", coordinates: [[[-76.9,17.9],[-76.7,17.9],[-76.7,18.1],[-76.9,18.1],[-76.9,17.9]]] } },
    { type: "Feature", properties: { name: "St Andrew" }, geometry: { type: "Polygon", coordinates: [[[-76.8,18.2],[-76.6,18.2],[-76.6,18.4],[-76.8,18.4],[-76.8,18.2]]] } },
  ],
} as const;

const metricRows = [
  { date: "2024-09-01", platform: "Meta",       campaign: "Awareness Boost", parish: "Kingston",  impressions: 120000, clicks: 3400, spend: 540, conversions: 120, roas: 3.5 },
  { date: "2024-09-01", platform: "Google Ads", campaign: "Search Capture",  parish: "St Andrew", impressions:  85000, clicks: 2200, spend: 320, conversions:  98, roas: 3.9 },
];

const DESKTOP_VIEWPORT = { width: 1280, height: 720 } as const;

async function expectNoSeriousViolations(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter(v => ["serious", "critical"].includes(v.impact ?? ""));
  expect(serious, `Serious accessibility violations: ${JSON.stringify(serious, null, 2)}`).toHaveLength(0);
}

test.describe("parish choropleth", () => {
  test("displays tooltip data on hover", async ({ page, mockMode }) => {
    if (mockMode) {
      await page.route("**/sample_metrics.json", route => fulfillJson(route, metricRows));
      await page.route("**/sample_campaign_performance.json", route => fulfillJson(route, aggregatedMetricsResponse.campaign));
      await page.route("**/sample_creative_performance.json", route => fulfillJson(route, aggregatedMetricsResponse.creative));
      await page.route("**/sample_budget_pacing.json", route => fulfillJson(route, aggregatedMetricsResponse.budget));
      await page.route("**/sample_parish_aggregates.json", route => fulfillJson(route, aggregatedMetricsResponse.parish));
    } else {
      await page.route("**/api/metrics/**", route => fulfillJson(route, aggregatedMetricsResponse));
    }

    await page.route("**/*parishes*.json", route => fulfillJson(route, geoJson));
    await page.setViewportSize(DESKTOP_VIEWPORT);

    const dashboard = new DashboardPage(page);
    await dashboard.open();
    await dashboard.mapPanel.waitForFeatureCount(geoJson.features.length);

    const tooltipText = await dashboard.mapPanel.hoverEachFeatureUntil(t => t.includes("Kingston"));
    expect(tooltipText).toBeTruthy();
    expect((tooltipText ?? "").toUpperCase()).toContain("IMPRESSIONS");

    const kingston = parishAggregates.find(r => r.parish === "Kingston");
    const normalized = (tooltipText ?? "").replace(/[\,\s]/g, "");
    expect(normalized).toContain(`IMPRESSIONS:${kingston?.impressions ?? 0}`);

    const screenshot = await page.screenshot({ animations: "disabled", fullPage: true, encoding: "base64" });
    await expect(screenshot).toMatchSnapshot("map-chromium-desktop.txt");
    await expectNoSeriousViolations(page);

    await page.unroute("**/*parishes*.json");
    if (mockMode) {
      await page.unroute("**/sample_metrics.json");
      await page.unroute("**/sample_campaign_performance.json");
      await page.unroute("**/sample_creative_performance.json");
      await page.unroute("**/sample_budget_pacing.json");
      await page.unroute("**/sample_parish_aggregates.json");
    } else {
      await page.unroute("**/api/metrics/**");
    }
  });
});
