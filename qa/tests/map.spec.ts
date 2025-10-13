import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./fixtures/base";

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

    await page.setViewportSize(DESKTOP_VIEWPORT);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const shapes = page.locator(".leaflet-interactive");
    await expect(shapes).toHaveCount(geoJson.features.length);

    const tooltip = page.locator(".leaflet-tooltip");
    const count = await shapes.count();
    let sawKingston = false;

    for (let index = 0; index < count; index += 1) {
      await shapes.nth(index).hover();
      await expect(tooltip).toBeVisible();
      const text = await tooltip.innerText();
      if (text.includes("Kingston")) {
        expect(text).toContain("IMPRESSIONS");
        expect(text.replace(/[,\s]/g, "")).toContain("IMPRESSIONS:120000");
        sawKingston = true;
        break;
      }
    }

    expect(sawKingston).toBe(true);

    const screenshot = await page.screenshot({
      animations: "disabled",
      fullPage: true,
      encoding: "base64",
    });
    await expect(screenshot).toMatchSnapshot("map-chromium-desktop.txt");

    await expectNoSeriousViolations(page);

    await page.unroute("**/jm_parishes.json");
    if (mockMode) {
      await page.unroute("**/sample_metrics.json");
    } else {
      await page.unroute("**/api/metrics/**");
    }
  });
});
