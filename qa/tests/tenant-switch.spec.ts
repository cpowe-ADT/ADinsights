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

const metricsSnapshot = {
  snapshot_generated_at: '2024-09-01T08:00:00-05:00',
  campaign: aggregatedMetricsResponse.campaign,
  creative: aggregatedMetricsResponse.creative,
  budget: aggregatedMetricsResponse.budget,
  parish: parishAggregates,
} as const;

test.describe('tenant switching', () => {
  test('switches tenants and uses fixture fallbacks when APIs are unavailable', async ({
    page,
    mockMode,
  }) => {
    test.skip(!mockMode, 'This spec runs in mock mode for deterministic UI coverage.');
    const dashboard = new DashboardPage(page);

    const requestCounts: Record<string, number> = {
      tenantFixture: 0,
      tenantApi: 0,
      metricsFixture: 0,
      metricsApi: 0,
    };
    page.on('request', (request) => {
      const url = request.url();
      if (url.includes('/mock/tenants.json')) {
        requestCounts.tenantFixture += 1;
      }
      if (url.includes('/api/tenants')) {
        requestCounts.tenantApi += 1;
      }
      if (url.includes('/sample_metrics.json')) {
        requestCounts.metricsFixture += 1;
      }
      if (url.includes('/api/metrics/combined')) {
        requestCounts.metricsApi += 1;
      }
    });

    await page.route('**/mock/tenants.json', (route) => fulfillJson(route, TENANTS));
    await page.route('**/sample_metrics.json*', (route) => fulfillJson(route, metricsSnapshot));

    await dashboard.open();
    await dashboard.waitForMetricsLoaded(campaignSnapshot.rows.length);
    await expect(page.getByText(/Demo dataset is active/i)).toBeVisible();
    await page.getByRole('button', { name: /Choose a tenant|Switch dashboards/i }).click();

    // Select the second tenant and confirm the header updates.
    await page.getByRole('option', { name: /Tenant Beta/i }).click();
    await expect(page.getByText(/Active tenant\s+Tenant Beta/i)).toBeVisible();

    await dashboard.waitForMetricsLoaded(campaignSnapshot.rows.length);
    expect(requestCounts.tenantFixture).toBeGreaterThan(0);
    expect(requestCounts.metricsFixture).toBeGreaterThan(0);
    expect(requestCounts.tenantApi).toBe(0);
    expect(requestCounts.metricsApi).toBe(0);

    await page.unroute('**/mock/tenants.json');
    await page.unroute('**/sample_metrics.json*');
  });
});
