import { expect, test } from './fixtures/base';

async function setLiveDatasetMode(page: import('@playwright/test').Page): Promise<void> {
  await page.addInitScript(() => {
    window.localStorage.setItem(
      'dataset-mode',
      JSON.stringify({
        state: { mode: 'live' },
        version: 0,
      }),
    );
  });
}

async function mockWarehouseDatasetBootstrap(
  page: import('@playwright/test').Page,
  liveReason: 'missing_snapshot' | 'stale_snapshot' | 'default_snapshot' | 'ready' = 'missing_snapshot',
): Promise<void> {
  await page.route('**/api/adapters/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          key: 'warehouse',
          name: 'Warehouse',
          description: 'Live warehouse metrics',
          interfaces: [],
        },
        {
          key: 'demo',
          name: 'Demo',
          description: 'Demo dataset',
          interfaces: [],
          options: {
            demo_tenants: [{ id: 'tenant-demo', label: 'Demo Tenant' }],
          },
        },
      ]),
    });
  });
  await page.route('**/api/datasets/status/', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        live: {
          enabled: liveReason === 'ready',
          reason: liveReason,
          snapshot_generated_at: liveReason === 'ready' ? '2026-04-04T15:00:00Z' : null,
        },
        demo: {
          enabled: true,
          source: 'demo',
          tenant_count: 1,
        },
        warehouse_adapter_enabled: true,
      }),
    });
  });
}

test.describe('meta reporting readiness', () => {
  test('data sources shows staged Meta readiness and a truthful Instagram CTA', async ({
    page,
    mockMode,
  }) => {
    test.skip(!mockMode, 'Mock mode only');

    await mockWarehouseDatasetBootstrap(page);

    await page.route('**/api/airbyte/connections/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });
    await page.route('**/api/airbyte/connections/summary/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total: 0,
          active: 0,
          inactive: 0,
          due: 0,
          by_provider: {},
          latest_sync: null,
        }),
      });
    });
    await page.route('**/api/integrations/meta/setup/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          provider: 'meta_ads',
          ready_for_oauth: true,
          ready_for_provisioning_defaults: true,
          checks: [],
          oauth_scopes: ['ads_read', 'business_management', 'pages_show_list'],
          graph_api_version: 'v24.0',
          redirect_uri: 'http://localhost:5173/dashboards/data-sources',
        }),
      });
    });
    await page.route('**/api/integrations/social/status/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          generated_at: '2026-04-04T15:00:00Z',
          platforms: [
            {
              platform: 'meta',
              display_name: 'Meta (Facebook)',
              status: 'active',
              reason: {
                code: 'active_direct_sync',
                message: 'Meta direct sync completed successfully with fresh reporting rows.',
              },
              last_checked_at: '2026-04-04T15:00:00Z',
              last_synced_at: '2026-04-04T14:55:00Z',
              actions: ['sync_now', 'view'],
              reporting_readiness: {
                stage: 'waiting_for_warehouse_snapshot',
                message:
                  'Meta connected. Direct sync complete. Waiting for the first warehouse snapshot.',
                auth_status: 'active',
                direct_sync_status: 'complete',
                warehouse_status: 'waiting_snapshot',
                dataset_live_reason: 'missing_snapshot',
                warehouse_adapter_enabled: true,
                snapshot_generated_at: null,
              },
              metadata: {},
            },
            {
              platform: 'instagram',
              display_name: 'Instagram (Business)',
              status: 'not_connected',
              reason: {
                code: 'instagram_not_linked',
                message:
                  'Instagram business linking is optional and is completed inside the Meta asset-selection flow.',
              },
              last_checked_at: '2026-04-04T15:00:00Z',
              last_synced_at: null,
              actions: ['open_meta_setup'],
              metadata: {
                standalone_oauth_supported: false,
                connection_contract: 'linked_via_meta_setup',
              },
            },
          ],
        }),
      });
    });

    await page.goto('/dashboards/data-sources?sources=social');

    await expect(page.getByText(/Reporting stage:/)).toBeVisible();
    await expect(page.getByText('Waiting snapshot')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Open Meta setup' })).toBeVisible();

    await page.getByRole('button', { name: 'Open Meta setup' }).click();

    await expect(
      page.getByRole('heading', { name: 'Connect Meta (Facebook & Instagram)' }),
    ).toBeVisible();
  });

  test('dashboard routes show the exact warehouse blocker while direct Meta asset pages still load', async ({
    page,
    mockMode,
  }) => {
    test.skip(!mockMode, 'Mock mode only');

    await setLiveDatasetMode(page);
    await mockWarehouseDatasetBootstrap(page, 'missing_snapshot');
    await page.route('**/api/metrics/combined/**', async (route) => {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          detail:
            'Warehouse metrics are unavailable because the live warehouse snapshot has not been generated yet.',
          code: 'warehouse_snapshot_unavailable',
          reason: 'missing_snapshot',
        }),
      });
    });
    await page.route('**/api/meta/accounts/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 'acct-1',
              external_id: 'act_123',
              account_id: '123',
              name: 'Primary Account',
              currency: 'USD',
              status: '1',
              business_name: 'Demo Biz',
            },
          ],
        }),
      });
    });
    await page.route('**/api/meta/pages/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          count: 1,
          results: [
            {
              id: 'page-1',
              page_id: 'page-1',
              name: 'Business Page',
              category: 'Business',
              can_analyze: true,
              is_default: true,
              tasks: ['ANALYZE'],
              perms: [],
              last_synced_at: '2026-04-04T14:55:00Z',
            },
          ],
        }),
      });
    });
    await page.route('**/api/integrations/social/status/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          generated_at: '2026-04-04T15:00:00Z',
          platforms: [
            {
              platform: 'meta',
              display_name: 'Meta (Facebook)',
              status: 'active',
              reason: {
                code: 'active_direct_sync',
                message: 'Meta direct sync completed successfully with fresh reporting rows.',
              },
              last_checked_at: '2026-04-04T15:00:00Z',
              last_synced_at: '2026-04-04T14:55:00Z',
              actions: ['sync_now', 'view'],
              reporting_readiness: {
                stage: 'waiting_for_warehouse_snapshot',
                message:
                  'Meta connected. Direct sync complete. Waiting for the first warehouse snapshot.',
                auth_status: 'active',
                direct_sync_status: 'complete',
                warehouse_status: 'waiting_snapshot',
                dataset_live_reason: 'missing_snapshot',
                warehouse_adapter_enabled: true,
                snapshot_generated_at: null,
              },
              metadata: {},
            },
          ],
        }),
      });
    });

    for (const path of [
      '/dashboards/campaigns',
      '/dashboards/creatives',
      '/dashboards/budget',
      '/dashboards/create',
    ]) {
      await page.goto(path);
      await expect(
        page.getByLabel('Live data status'),
      ).toContainText(
        'Meta is connected, but the first live warehouse snapshot has not been generated yet.',
      );
    }

    await page.goto('/dashboards/meta/accounts');
    await expect(page.getByRole('cell', { name: 'Primary Account' }).first()).toBeVisible();
    await expect(
      page.getByText(/Meta ad accounts and Facebook Pages are separate assets\./i),
    ).toBeVisible();

    await page.goto('/dashboards/meta/pages');
    await expect(page.getByText('Business Page')).toBeVisible();
    await expect(page.getByText(/This screen lists Facebook Pages only\./i)).toBeVisible();
  });
});
