import AxeBuilder from '@axe-core/playwright';
import { expect, test } from './fixtures/base';
import { DashboardPage } from '../page-objects';
import { aggregatedMetricsResponse, fulfillJson, parishAggregates } from './support/sampleData';

const SKIP_SCREENSHOTS = process.env.QA_SKIP_SCREENSHOTS !== '0';
const metricsSnapshot = {
  tenant_id: 'tenant-qa',
  snapshot_generated_at: '2024-09-01T08:00:00-05:00',
  campaign: aggregatedMetricsResponse.campaign,
  creative: aggregatedMetricsResponse.creative,
  budget: aggregatedMetricsResponse.budget,
  parish: parishAggregates,
} as const;

const geoJson = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { name: 'Kingston' },
      geometry: {
        type: 'Polygon',
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
      type: 'Feature',
      properties: { name: 'St Andrew' },
      geometry: {
        type: 'Polygon',
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

test.describe('parish choropleth', () => {
  test('filters the table when selecting a parish', async ({ page, mockMode }) => {
    test.skip(!mockMode, 'This spec runs in mock mode for deterministic UI coverage.');
    if (mockMode) {
      await page.route('**/sample_metrics.json**', (route) => fulfillJson(route, metricsSnapshot));
    } else {
      await page.route('**/api/metrics/**', (route) =>
        fulfillJson(route, aggregatedMetricsResponse),
      );
    }

    await page.route('**/*parishes*.json', (route) => fulfillJson(route, geoJson));
    await page.setViewportSize(DESKTOP_VIEWPORT);

    const dashboard = new DashboardPage(page);
    await dashboard.open();
    await page.getByLabel(/Map metric/i).selectOption('impressions');
    await dashboard.mapPanel.waitForFeatureCount(geoJson.features.length);

    await expect(page.getByRole('group', { name: /Impressions legend/i })).toBeVisible();

    await dashboard.mapPanel.selectFeature('Kingston');
    await expect.poll(async () => dashboard.getMetricRowCount()).toBe(1);
    expect(await dashboard.getColumnValues('parish')).toEqual(['Kingston']);

    await dashboard.mapPanel.selectFeature('St Andrew');
    await expect.poll(async () => dashboard.getMetricRowCount()).toBe(1);
    expect(await dashboard.getColumnValues('parish')).toEqual(['St Andrew']);

    if (!SKIP_SCREENSHOTS) {
      const screenshot = await page.screenshot({
        animations: 'disabled',
        fullPage: true,
        encoding: 'base64',
      });
      await expect(screenshot).toMatchSnapshot('map.txt');
    }
    await expectNoSeriousViolations(page);

    await page.unroute('**/*parishes*.json');
    if (mockMode) {
      await page.unroute('**/sample_metrics.json**');
    } else {
      await page.unroute('**/api/metrics/**');
    }
  });
});
