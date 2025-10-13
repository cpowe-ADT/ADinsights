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
const DESKTOP_VIEWPORT = { width: 1280, height: 720 } as const;
const parseNumber = (text: string) => Number(text.replace(/,/g, ""));

async function expectNoSeriousViolations(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter(v => ["serious", "critical"].includes(v.impact ?? ""));
  expect(serious, `Serious accessibility violations: ${JSON.stringify(serious, null, 2)}`).toHaveLength(0);
}

test.describe("dashboard metrics grid", () => {
  test("defaults to impressions sorting and toggles to clicks", async ({ page, mockMode }) => {
    await page.setViewportSize(DESKTOP_VIEWPORT);
    const dashboard = new DashboardPage(page);

    if (mockMode) {
      await page.route("**/sample_metrics.json", route => fulfillJson(route, sampleRows));
      await page.route("**/sample_campaign_performance.json", route => fulfillJson(route, campaignSnapshot));
      await page.route("**/sample_creative_performance.json", route => fulfillJson(route, aggregatedMetricsResponse.creative));
      await page.route("**/sample_budget_pacing.json", route => fulfillJson(route, aggregatedMetricsResponse.budget));
      await page.route("**/sample_parish_aggregates.json", route => fulfillJson(route, parishAggregates));
    } else {
      await page.route("**/api/metrics/**", route => fulfillJson(route, aggregatedMetricsResponse));
    }

    await dashboard.open();
    await dashboard.waitForMetricsLoaded(sampleRows.length);
    await expect.poll(async () => dashboard.getMetricRowCount()).toBe(sampleRows.length);

    const sortedByImpr = [...sampleRows].sort((a, b) => b.impressions - a.impressions);
    const firstRow = await dashboard.getFirstRow();
    expect(firstRow.parish).toBe(sortedByImpr[0].parish);
    expect(parseNumber(firstRow.impressions)).toBe(sortedByImpr[0].impressions);
    await expect.poll(async () => dashboard.getSortedStatus()).toContain("Impressions");

    await dashboard.toggleSortByClicks();
    await expect.poll(async () => dashboard.getSortedStatus()).toContain("Clicks");

    const sortedByClicks = [...sampleRows].sort((a, b) => b.clicks - a.clicks);
    const parishes = await dashboard.getColumnValues("parish");
    const clicks = await dashboard.getNumericColumn("clicks");
    expect(parishes).toEqual(sortedByClicks.map(r => r.parish));
    expect(clicks).toEqual(sortedByClicks.map(r => r.clicks));

    const screenshot = await page.screenshot({ animations: "disabled", fullPage: true, encoding: "base64" });
    await expect(screenshot).toMatchSnapshot("dashboard-chromium-desktop.txt");
    await expectNoSeriousViolations(page);

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
