import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./fixtures/base";
import { DashboardPage } from "../page-objects";

type MetricRow = {
  date: string;
  platform: string;
  campaign: string;
  parish: string;
  impressions: number;
  clicks: number;
  spend: number;
  conversions: number;
  roas: number;
};

const sampleRows: MetricRow[] = [
  {
    date: "2024-09-01",
    platform: "Meta",
    campaign: "Awareness Boost",
    parish: "Kingston",
    impressions: 125000,
    clicks: 3100,
    spend: 560,
    conversions: 118,
    roas: 3.7,
  },
  {
    date: "2024-09-02",
    platform: "Google Ads",
    campaign: "Search Capture",
    parish: "St James",
    impressions: 94000,
    clicks: 4200,
    spend: 430,
    conversions: 140,
    roas: 4.1,
  },
  {
    date: "2024-09-03",
    platform: "TikTok",
    campaign: "GenZ Launch",
    parish: "St Andrew",
    impressions: 68000,
    clicks: 2100,
    spend: 220,
    conversions: 95,
    roas: 3.2,
  },
];

function fulfillMetrics(route: import("@playwright/test").Route) {
  void route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(sampleRows),
  });
}

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
    if (mockMode) {
      await page.route("**/sample_metrics.json", fulfillMetrics);
    } else {
      await page.route("**/api/metrics/**", fulfillMetrics);
    }

    await page.setViewportSize(DESKTOP_VIEWPORT);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const rows = page.locator("tbody tr");
    await expect(rows).toHaveCount(sampleRows.length);
    const dashboard = new DashboardPage(page);
    await dashboard.open();
    await dashboard.waitForMetricsLoaded(sampleRows.length);

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
      await page.unroute("**/sample_metrics.json");
    } else {
      await page.unroute("**/api/metrics/**");
    }
  });
});
