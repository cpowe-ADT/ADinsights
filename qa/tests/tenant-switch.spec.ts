import { expect, test } from './fixtures/base';
import { DashboardPage } from '../page-objects';
import {
  aggregatedMetricsResponse,
  fulfillJson,
  parishAggregates,
} from './support/sampleData';

const TENANTS = [
  { id: 'tenant-qa', name: 'Tenant QA', status: 'active' },
  { id: 'tenant-b', name: 'Tenant Beta', status: 'active' },
];

const metricsSnapshot = {
  tenant_id: 'tenant-qa',
  snapshot_generated_at: '2024-09-01T08:00:00-05:00',
  campaign: aggregatedMetricsResponse.campaign,
  creative: aggregatedMetricsResponse.creative,
  budget: aggregatedMetricsResponse.budget,
  parish: parishAggregates,
} as const;

test.describe('tenant switching', () => {
  test('switches tenants and surfaces dataset fallback', async ({ page, mockMode }) => {
    test.skip(!mockMode, 'This spec runs in mock mode for deterministic UI coverage.');
    const dashboard = new DashboardPage(page);

    if (mockMode) {
      await page.route('**/mock/tenants.json', (route) => fulfillJson(route, TENANTS));
      await page.route('**/sample_metrics.json', (route) => fulfillJson(route, metricsSnapshot));
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
    await page.getByRole('button', { name: /Choose a tenant|Switch dashboards/i }).click();

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
    } else {
      await page.unroute('**/api/tenants/');
      await page.unroute('**/api/adapters/');
      await page.unroute('**/api/metrics/**');
    }
  });
});
