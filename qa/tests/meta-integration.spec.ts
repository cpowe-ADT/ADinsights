import { expect, test } from './fixtures/base';

test.describe('meta integration flows', () => {
  test('oauth callback with missing permissions shows re-request path', async ({ page, mockMode }) => {
    test.skip(!mockMode, 'Mock mode only');

    await page.route('**/api/integrations/meta/setup/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          provider: 'meta_ads',
          ready_for_oauth: true,
          ready_for_provisioning_defaults: true,
          checks: [],
          oauth_scopes: ['ads_read'],
          graph_api_version: 'v24.0',
          source_definition_id: 'e7778cfc-e97c-4458-9ecb-b4f2bba8946c',
        }),
      });
    });
    await page.route('**/api/integrations/meta/oauth/exchange/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          selection_token: 'selection-token',
          expires_in_seconds: 600,
          pages: [{ id: 'page-1', name: 'Business Page', tasks: [], perms: [] }],
          ad_accounts: [{ id: 'act_123', account_id: '123', name: 'Primary Account' }],
          instagram_accounts: [],
          granted_permissions: ['ads_read'],
          declined_permissions: ['business_management', 'pages_show_list'],
          missing_required_permissions: [
            'business_management',
            'pages_show_list',
            'pages_read_engagement',
          ],
          token_debug_valid: true,
          oauth_connected_but_missing_permissions: true,
        }),
      });
    });
    await page.route('**/api/integrations/social/status/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          generated_at: '2026-02-19T10:00:00Z',
          platforms: [],
        }),
      });
    });
    await page.route('**/api/airbyte/connections/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.goto('/dashboards/data-sources?code=oauth-code&state=oauth-state');
    await expect(page.getByText(/required permissions are missing/i)).toBeVisible();
  });

  test('oauth callback success shows page and ad-account selection', async ({ page, mockMode }) => {
    test.skip(!mockMode, 'Mock mode only');

    await page.route('**/api/integrations/meta/setup/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          provider: 'meta_ads',
          ready_for_oauth: true,
          ready_for_provisioning_defaults: true,
          checks: [],
          oauth_scopes: ['ads_read', 'business_management', 'pages_show_list', 'pages_read_engagement'],
          graph_api_version: 'v24.0',
          source_definition_id: 'e7778cfc-e97c-4458-9ecb-b4f2bba8946c',
        }),
      });
    });
    await page.route('**/api/integrations/meta/oauth/exchange/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          selection_token: 'selection-token',
          expires_in_seconds: 600,
          pages: [{ id: 'page-1', name: 'Business Page', tasks: [], perms: [] }],
          ad_accounts: [{ id: 'act_123', account_id: '123', name: 'Primary Account' }],
          instagram_accounts: [],
          granted_permissions: [
            'ads_read',
            'business_management',
            'pages_show_list',
            'pages_read_engagement',
          ],
          declined_permissions: [],
          missing_required_permissions: [],
          token_debug_valid: true,
          oauth_connected_but_missing_permissions: false,
        }),
      });
    });
    await page.route('**/api/integrations/social/status/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          generated_at: '2026-02-19T10:00:00Z',
          platforms: [],
        }),
      });
    });
    await page.route('**/api/airbyte/connections/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.goto('/dashboards/data-sources?code=oauth-code&state=oauth-state');
    await expect(page.getByText(/save selected business page/i)).toBeVisible();
  });

  test('meta account list renders and insights dashboard displays 30-day records', async ({
    page,
    mockMode,
  }) => {
    test.skip(!mockMode, 'Mock mode only');

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
              id: 'a1',
              external_id: 'act_123',
              account_id: '123',
              name: 'Primary Account',
              currency: 'USD',
              status: '1',
              business_name: 'Demo Biz',
              metadata: {},
              created_at: '2026-02-19T10:00:00Z',
              updated_at: '2026-02-19T10:00:00Z',
            },
          ],
        }),
      });
    });
    await page.route('**/api/meta/insights/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          count: 2,
          next: null,
          previous: null,
          results: [
            {
              id: 'i1',
              external_id: 'ad-1',
              date: '2026-02-17',
              source: 'meta',
              level: 'ad',
              impressions: 1000,
              reach: 900,
              clicks: 35,
              spend: '17.50',
              cpc: '0.50',
              cpm: '17.50',
              conversions: 3,
              currency: 'USD',
              actions: [{ action_type: 'purchase', value: '3' }],
              raw_payload: {},
              ingested_at: '2026-02-19T10:00:00Z',
              updated_at: '2026-02-19T10:00:00Z',
            },
            {
              id: 'i2',
              external_id: 'ad-2',
              date: '2026-02-18',
              source: 'meta',
              level: 'ad',
              impressions: 1200,
              reach: 1100,
              clicks: 40,
              spend: '21.00',
              cpc: '0.53',
              cpm: '17.50',
              conversions: 4,
              currency: 'USD',
              actions: [{ action_type: 'purchase', value: '4' }],
              raw_payload: {},
              ingested_at: '2026-02-19T10:00:00Z',
              updated_at: '2026-02-19T10:00:00Z',
            },
          ],
        }),
      });
    });

    await page.goto('/dashboards/meta/accounts');
    await expect(page.getByRole('heading', { name: /ad accounts/i })).toBeVisible();
    await expect(page.getByText('Primary Account')).toBeVisible();

    await page.goto('/dashboards/meta/insights');
    await expect(page.getByRole('heading', { name: /insights dashboard/i })).toBeVisible();
    await expect(page.getByText('ad-1')).toBeVisible();
    await expect(page.getByText('ad-2')).toBeVisible();
  });

  test('insights page shows retry UI for 429 and recovers on retry', async ({ page, mockMode }) => {
    test.skip(!mockMode, 'Mock mode only');

    await page.route('**/api/meta/accounts/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: 0, next: null, previous: null, results: [] }),
      });
    });

    let calls = 0;
    await page.route('**/api/meta/insights/**', async (route) => {
      calls += 1;
      if (calls <= 2) {
        await route.fulfill({
          status: 429,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Rate limited' }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 'i3',
              external_id: 'ad-3',
              date: '2026-02-18',
              source: 'meta',
              level: 'ad',
              impressions: 500,
              reach: 450,
              clicks: 12,
              spend: '9.00',
              cpc: '0.75',
              cpm: '18.00',
              conversions: 1,
              currency: 'USD',
              actions: [],
              raw_payload: {},
              ingested_at: '2026-02-19T10:00:00Z',
              updated_at: '2026-02-19T10:00:00Z',
            },
          ],
        }),
      });
    });

    await page.goto('/dashboards/meta/insights');
    await expect(page.getByText(/unable to load insights/i)).toBeVisible();
    await page.getByRole('button', { name: /retry/i }).click();
    await expect(page.getByText('ad-3')).toBeVisible();
  });

  test('insights page shows permission guidance on 403', async ({ page, mockMode }) => {
    test.skip(!mockMode, 'Mock mode only');

    await page.route('**/api/meta/accounts/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: 0, next: null, previous: null, results: [] }),
      });
    });

    await page.route('**/api/meta/insights/**', async (route) => {
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Missing required permissions.' }),
      });
    });

    await page.goto('/dashboards/meta/insights');
    await expect(page.getByText(/unable to load insights/i)).toBeVisible();
    await expect(page.getByText(/missing meta permissions/i)).toBeVisible();
  });
});
