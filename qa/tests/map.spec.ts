import { expect, test } from "./fixtures/base";
import { DashboardPage } from "../page-objects";

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
};

const metricRows = [
  {
    date: "2024-09-01",
    platform: "Meta",
    campaign: "Awareness Boost",
    parish: "Kingston",
    impressions: 120000,
    clicks: 3400,
    spend: 540,
    conversions: 120,
    roas: 3.5,
  },
  {
    date: "2024-09-01",
    platform: "Google Ads",
    campaign: "Search Capture",
    parish: "St Andrew",
    impressions: 85000,
    clicks: 2200,
    spend: 320,
    conversions: 98,
    roas: 3.9,
  },
];

test.describe("parish choropleth", () => {
  test("displays tooltip data on hover", async ({ page, mockMode }) => {
    if (mockMode) {
      await page.route("**/sample_metrics.json", (route) => {
        void route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(metricRows),
        });
      });
    } else {
      await page.route("**/api/metrics/**", (route) => {
        void route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(metricRows),
        });
      });
    }

    await page.route("**/jm_parishes.json", (route) => {
      void route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(geoJson),
      });
    });

    const dashboard = new DashboardPage(page);
    await dashboard.open();
    await dashboard.mapPanel.waitForFeatureCount(geoJson.features.length);

    const tooltipText = await dashboard.mapPanel.hoverEachFeatureUntil((text) => text.includes("Kingston"));
    expect(tooltipText).toBeTruthy();
    expect(tooltipText ?? "").toContain("IMPRESSIONS");
    expect((tooltipText ?? "").replace(/[,\s]/g, "")).toContain("IMPRESSIONS:120000");

    await page.unroute("**/jm_parishes.json");
    if (mockMode) {
      await page.unroute("**/sample_metrics.json");
    } else {
      await page.unroute("**/api/metrics/**");
    }
  });
});
