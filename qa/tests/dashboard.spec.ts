import { expect, test } from "./fixtures/base";

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

test.describe("dashboard metrics grid", () => {
  test("defaults to impressions sorting and toggles to clicks", async ({ page, mockMode }) => {
    if (mockMode) {
      await page.route("**/sample_metrics.json", fulfillMetrics);
    } else {
      await page.route("**/api/metrics/**", fulfillMetrics);
    }

    await page.goto("/");

    const rows = page.locator("tbody tr");
    await expect(rows).toHaveCount(sampleRows.length);

    const sortedByImpressions = [...sampleRows].sort((a, b) => b.impressions - a.impressions);
    const firstRowParish = await rows.first().locator("td").nth(3).innerText();
    const firstRowImpressions = parseNumber(await rows.first().locator("td").nth(4).innerText());
    expect(firstRowParish).toBe(sortedByImpressions[0].parish);
    expect(firstRowImpressions).toBe(sortedByImpressions[0].impressions);

    await expect(page.getByText(/Sorted by Impressions/i)).toBeVisible();

    const clicksToggle = page.getByRole("button", { name: /Sort by Clicks/i });
    await clicksToggle.click();
    await clicksToggle.click();

    await expect(page.getByText(/Sorted by Clicks/i)).toBeVisible();

    const sortedByClicks = [...sampleRows].sort((a, b) => b.clicks - a.clicks);
    const reorderedParishes: string[] = [];
    const reorderedClicks: number[] = [];
    const count = await rows.count();
    for (let index = 0; index < count; index += 1) {
      const row = rows.nth(index);
      reorderedParishes.push(await row.locator("td").nth(3).innerText());
      reorderedClicks.push(parseNumber(await row.locator("td").nth(5).innerText()));
    }

    expect(reorderedParishes).toEqual(sortedByClicks.map((row) => row.parish));
    expect(reorderedClicks).toEqual(sortedByClicks.map((row) => row.clicks));

    if (mockMode) {
      await page.unroute("**/sample_metrics.json");
    } else {
      await page.unroute("**/api/metrics/**");
    }
  });
});
