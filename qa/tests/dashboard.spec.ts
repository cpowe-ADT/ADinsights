import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./fixtures/base";
import { DashboardPage } from "../page-objects";
import {
  aggregatedMetricsResponse,
  campaignSnapshot,
  fulfillJson,
  parishAggregates,
} from "./support/sampleData";

const sampleRows = campaignSnapshot.rows;

function parseNumber(text: string): number {
  return Number(text.replace(/,/g, ""));
}

const DESKTOP_VIEWPORT = { width: 1280, height: 720 } as const;

async function expectNoSeriousViolations(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page }).analyze();
  const seriousViolations = results.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact ?? ""),
  );

  expect(seriousViolations, `Serious accessibility violations detected: ${JSON.stringify(seriousViolations, null, 2)}`).toHaveLength(0);
}

test.describe("dashboard metrics grid", () => {
  test("defaults to impressions sorting and toggles to clicks", async ({ page, mockMode }) => {
    await page.setViewportSize(DESKTOP_VIEWPORT);
    const dashboard = new DashboardPage(page);
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

    await dashboard.open();
    await dashboard.waitForMetricsLoaded(sampleRows.length);

    await expect.poll(async () => dashboard.getMetricRowCount()).toBe(sampleRows.length);

    const sortedByImpressions = [...sampleRows].sort((a, b) => b.impressions - a.impressions);
    const firstRow = await dashboard.getFirstRow();
    expect(firstRow.parish).toBe(sortedByImpressions[0].parish);
    expect(parseNumber(firstRow.impressions)).toBe(sortedByImpressions[0].impressions);

    await expect.poll(async () => dashboard.getSortedStatus()).toContain("Impressions");

    await dashboard.toggleSortByClicks();
    await dashboard.toggleSortByClicks();

    await expect.poll(async () => dashboard.getSortedStatus()).toContain("Clicks");

    const sortedByClicks = [...sampleRows].sort((a, b) => b.clicks - a.clicks);
    const parishes = await dashboard.getColumnValues("parish");
    const clicks = await dashboard.getNumericColumn("clicks");

    expect(parishes).toEqual(sortedByClicks.map((row) => row.parish));
    expect(clicks).toEqual(sortedByClicks.map((row) => row.clicks));

    const screenshot = await page.screenshot({
      animations: "disabled",
      fullPage: true,
      encoding: "base64",
    });
    await expect(screenshot).toMatchSnapshot("dashboard-chromium-desktop.txt");

    await expectNoSeriousViolations(page);

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
