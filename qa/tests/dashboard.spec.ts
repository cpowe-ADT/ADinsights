import AxeBuilder from '@axe-core/playwright';
import { expect, test } from './fixtures/base';
import { DashboardPage } from '../page-objects';
import {
  aggregatedMetricsResponse,
  campaignSnapshot,
  fulfillJson,
  parishAggregates,
} from './support/sampleData';

const sampleRows = campaignSnapshot.rows;
const DESKTOP_VIEWPORT = { width: 1280, height: 720 } as const;
const parseNumber = (text: string) => Number(text.replace(/,/g, ''));
const SKIP_SCREENSHOTS = process.env.QA_SKIP_SCREENSHOTS !== '0';
const metricsSnapshot = {
  tenant_id: 'tenant-qa',
  snapshot_generated_at: '2024-09-01T08:00:00-05:00',
  campaign: aggregatedMetricsResponse.campaign,
  creative: aggregatedMetricsResponse.creative,
  budget: aggregatedMetricsResponse.budget,
  parish: parishAggregates,
} as const;

async function expectNoSeriousViolations(page: import('@playwright/test').Page) {
  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter((v) =>
    ['serious', 'critical'].includes(v.impact ?? ''),
  );
  expect(
    serious,
    `Serious accessibility violations: ${JSON.stringify(serious, null, 2)}`,
  ).toHaveLength(0);
}

test.describe('dashboard metrics grid', () => {
  test('defaults to spend sorting and toggles to clicks', async ({ page, mockMode }) => {
    test.skip(!mockMode, 'This spec runs in mock mode for deterministic UI coverage.');
    await page.setViewportSize(DESKTOP_VIEWPORT);
    const dashboard = new DashboardPage(page);

    if (mockMode) {
      await page.route('**/sample_metrics.json*', (route) => fulfillJson(route, metricsSnapshot));
    } else {
      await page.route('**/api/metrics/**', (route) =>
        fulfillJson(route, aggregatedMetricsResponse),
      );
    }

    await dashboard.open();
    await dashboard.waitForMetricsLoaded(sampleRows.length);
    await expect.poll(async () => dashboard.getMetricRowCount()).toBe(sampleRows.length);

    const sortedBySpend = [...sampleRows].sort((a, b) => b.spend - a.spend);
    const firstRow = await dashboard.getFirstRow();
    expect(firstRow.parish).toBe(sortedBySpend[0].parish);
    expect(parseNumber(firstRow.impressions)).toBe(sortedBySpend[0].impressions);

    await dashboard.toggleSortByClicks();

    const sortedByClicks = [...sampleRows].sort((a, b) => b.clicks - a.clicks);
    const parishes = await dashboard.getColumnValues('parish');
    const clicks = await dashboard.getNumericColumn('clicks');
    expect(parishes).toEqual(sortedByClicks.map((r) => r.parish));
    expect(clicks).toEqual(sortedByClicks.map((r) => r.clicks));

    if (!SKIP_SCREENSHOTS) {
      const screenshot = await page.screenshot({
        animations: 'disabled',
        fullPage: true,
        encoding: 'base64',
      });
      await expect(screenshot).toMatchSnapshot('dashboard.txt');
    }
    await expectNoSeriousViolations(page);

    if (mockMode) {
      await page.unroute('**/sample_metrics.json*');
    } else {
      await page.unroute('**/api/metrics/**');
    }
  });
});
