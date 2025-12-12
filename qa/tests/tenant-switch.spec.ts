import { expect, test } from './fixtures/base';
import { DashboardPage } from '../page-objects';
import {
  aggregatedMetricsResponse,
  campaignSnapshot,
  fulfillJson,
  parishAggregates,
} from './support/sampleData';

const TENANTS = [
  { id: 'tenant-qa', name: 'Tenant QA', status: 'active' },
  { id: 'tenant-b', name: 'Tenant Beta', status: 'active' },
];

const IS_MOCK_ENV =
  process.env.MOCK === '1' || String(process.env.MOCK_MODE || '').toLowerCase() === 'true';

test.describe('tenant switching', () => {
  test('switches tenants and surfaces dataset fallback', async ({ page, mockMode }) => {
    test.skip(IS_MOCK_ENV, 'Tenant switch smoke exercised in live mode; mock lacks backend wiring.');
    const dashboard = new DashboardPage(page);

    if (mockMode) {
      await page.route('**/mock/tenants.json', (route) => fulfillJson(route, TENANTS));
      await page.route('**/sample_metrics.json', (route) =>
        fulfillJson(route, campaignSnapshot.rows),
      );
      await page.route('**/sample_campaign_performance.json', (route) =>
        fulfillJson(route, campaignSnapshot),
      );
      await page.route('**/sample_creative_performance.json', (route) =>
        fulfillJson(route, aggregatedMetricsResponse.creative),
      );
      await page.route('**/sample_budget_pacing.json', (route) =>
        fulfillJson(route, aggregatedMetricsResponse.budget),
      );
      await page.route('**/sample_parish_aggregates.json', (route) =>
        fulfillJson(route, parishAggregates),
      );
      await page.route('**/api/metrics/**', (route) =>
        fulfillJson(route, aggregatedMetricsResponse),
      );
    } else {
      await page.route('**/api/tenants/', (route) => fulfillJson(route, TENANTS));
      await page.route('**/api/adapters/', (route) =>
        fulfillJson(route, [
          { key: 'warehouse', name: 'Warehouse', description: '', interfaces: [] },
          { key: 'demo', name: 'Demo', description: '', interfaces: [], options: { demo_tenants: TENANTS } },
        ]),
      );
      await page.route('**/api/metrics/**', (route) => fulfillJson(route, aggregatedMetricsResponse));
    }

    await dashboard.open();
    await page.getByRole('button', { name: /Tenant QA|Select a tenant|Loading tenants/i }).click();

    // Select the second tenant and confirm the header updates.
    await page.getByRole('option', { name: /Tenant Beta/i }).click();
    await expect(page.getByText(/Active tenant\s+Tenant Beta/i)).toBeVisible();

    // Dataset toggle should allow switching to demo data if live is unavailable (only in live mode).
    if (!mockMode) {
      const datasetButton = page.getByRole('button', { name: /Use demo data|Use live data/i });
      await datasetButton.click();
      await expect(datasetButton).toHaveAttribute('aria-pressed', 'true');
    }

    if (mockMode) {
      await page.unroute('**/mock/tenants.json');
      await page.unroute('**/sample_metrics.json');
      await page.unroute('**/sample_campaign_performance.json');
      await page.unroute('**/sample_creative_performance.json');
      await page.unroute('**/sample_budget_pacing.json');
      await page.unroute('**/sample_parish_aggregates.json');
    } else {
      await page.unroute('**/api/tenants/');
      await page.unroute('**/api/adapters/');
      await page.unroute('**/api/metrics/**');
    }
  });
});
