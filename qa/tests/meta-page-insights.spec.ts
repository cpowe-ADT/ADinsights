import { expect, test } from './fixtures/base';

async function ensureSignedIn(
  page: import('@playwright/test').Page,
  fallbackPath: string,
): Promise<void> {
  await page.waitForTimeout(100);
  if (!page.url().includes('/login')) {
    await page.waitForURL('**/login', { timeout: 1500 }).catch(() => undefined);
  }
  if (!page.url().includes('/login')) {
    return;
  }
  const destination = await page.evaluate((fallback) => {
    const state = window.history.state as
      | { usr?: { from?: { pathname?: string; search?: string; hash?: string } } }
      | undefined;
    const from = state?.usr?.from;
    if (!from?.pathname) {
      return fallback;
    }
    return `${from.pathname}${from.search ?? ''}${from.hash ?? ''}`;
  }, fallbackPath);
  await page.evaluate((targetPath) => {
    const exp = Math.floor(Date.now() / 1000) + 60 * 60;
    const toBase64Url = (value: string) =>
      btoa(value).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
    const header = toBase64Url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
    const payload = toBase64Url(JSON.stringify({ exp }));
    window.localStorage.setItem(
      'adinsights.auth',
      JSON.stringify({
        access: `${header}.${payload}.signature`,
        refresh: 'refresh-token',
        tenantId: 'tenant-qa',
        user: { email: 'qa@example.com' },
      }),
    );
    window.location.assign(targetPath);
  }, destination);
  await page.waitForURL((url) => !url.pathname.startsWith('/login'));
}

test.describe('meta page insights smoke', () => {
  test('connect callback, select page, view dashboard and post drill-down', async ({ page, mockMode }) => {
    test.skip(!mockMode, 'Mock mode only');

    await page.route('**/api/meta/connect/callback/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          connection_id: 'conn-1',
          default_page_id: 'page-1',
          missing_required_permissions: [],
          oauth_connected_but_missing_permissions: false,
          pages: [
            {
              id: '11111111-1111-1111-1111-111111111111',
              page_id: 'page-1',
              name: 'Business Page',
              can_analyze: true,
              is_default: true,
              tasks: ['ANALYZE'],
              perms: [],
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
          results: [
            {
              id: '11111111-1111-1111-1111-111111111111',
              page_id: 'page-1',
              name: 'Business Page',
              can_analyze: true,
              is_default: true,
              tasks: ['ANALYZE'],
              perms: [],
            },
          ],
          count: 1,
        }),
      });
    });

    await page.route('**/api/integrations/meta/pages/page-1/select/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ page_id: 'page-1', selected: true }),
      });
    });

    await page.route('**/api/meta/metrics/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [
            {
              metric_key: 'page_post_engagements',
              level: 'PAGE',
              status: 'ACTIVE',
              replacement_metric_key: '',
              title: 'Engagements',
              description: '',
              is_default: true,
              supported_periods: ['day', 'week', 'days_28'],
            },
            {
              metric_key: 'post_reactions_like_total',
              level: 'POST',
              status: 'ACTIVE',
              replacement_metric_key: '',
              title: 'Likes',
              description: '',
              is_default: true,
              supported_periods: ['lifetime', 'day'],
            },
          ],
          count: 2,
        }),
      });
    });

    await page.route('**/api/meta/pages/page-1/overview/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          page_id: 'page-1',
          name: 'Business Page',
          date_preset: 'last_28d',
          since: '2026-01-20',
          until: '2026-02-18',
          last_synced_at: '2026-02-18T08:00:00Z',
          metric_availability: {
            page_post_engagements: { supported: true, last_checked_at: null, reason: '' },
            page_impressions_unique: {
              supported: false,
              last_checked_at: null,
              reason: 'No access to this metric.',
            },
          },
          kpis: [
            {
              metric: 'page_post_engagements',
              resolved_metric: 'page_post_engagements',
              value: 403,
              today_value: 22,
            },
            {
              metric: 'page_impressions_unique',
              resolved_metric: 'page_impressions_unique',
              value: null,
              today_value: null,
            },
          ],
          daily_series: {
            page_post_engagements: [
              { date: '2026-02-17', value: 10 },
              { date: '2026-02-18', value: 22 },
            ],
          },
          primary_metric: 'page_post_engagements',
          cards: [
            {
              metric_key: 'page_post_engagements',
              status: 'ACTIVE',
              replacement_metric_key: '',
              value_today: '22',
              value_range: '403',
            },
            {
              metric_key: 'page_impressions_unique',
              status: 'INVALID',
              replacement_metric_key: 'page_views_total',
              value_today: null,
              value_range: null,
            },
          ],
          metrics: [
            {
              metric_key: 'page_post_engagements',
              level: 'PAGE',
              status: 'ACTIVE',
              replacement_metric_key: '',
              title: 'Engagements',
              description: '',
            },
            {
              metric_key: 'page_impressions_unique',
              level: 'PAGE',
              status: 'INVALID',
              replacement_metric_key: 'page_views_total',
              title: 'Reach',
              description: '',
            },
          ],
        }),
      });
    });

    await page.route('**/api/meta/pages/page-1/timeseries/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          page_id: 'page-1',
          metric: 'page_post_engagements',
          resolved_metric: 'page_post_engagements',
          period: 'day',
          metric_availability: {
            page_post_engagements: { supported: true, last_checked_at: null, reason: '' },
          },
          since: '2026-01-20',
          until: '2026-02-18',
          points: [
            { end_time: '2026-02-17T08:00:00Z', value: '10' },
            { end_time: '2026-02-18T08:00:00Z', value: '22' },
          ],
        }),
      });
    });

    await page.route('**/api/meta/pages/page-1/posts/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          page_id: 'page-1',
          date_preset: 'last_28d',
          since: '2026-01-20',
          until: '2026-02-18',
          last_synced_at: '2026-02-18T08:00:00Z',
          metric_availability: {
            post_reactions_like_total: { supported: true, last_checked_at: null, reason: '' },
          },
          count: 1,
          limit: 50,
          offset: 0,
          next_offset: null,
          prev_offset: null,
          results: [
            {
              post_id: 'page-1_abc',
              page_id: 'page-1',
              created_time: '2026-02-18T08:00:00Z',
              permalink: 'https://example.com/p',
              permalink_url: 'https://example.com/p',
              media_type: 'PHOTO',
              message: 'Post copy',
              message_snippet: 'Post copy',
              last_synced_at: '2026-02-18T08:00:00Z',
              metrics: { post_reactions_like_total: 44 },
            },
          ],
        }),
      });
    });

    await page.route('**/api/meta/posts/page-1_abc/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          post_id: 'page-1_abc',
          page_id: 'page-1',
          created_time: '2026-02-18T08:00:00Z',
          permalink: 'https://example.com/p',
          media_type: 'PHOTO',
          message: 'Post copy',
          last_synced_at: '2026-02-18T08:00:00Z',
          metric_availability: {
            post_reactions_like_total: { supported: true, last_checked_at: null, reason: '' },
          },
          metrics: { post_reactions_like_total: 44 },
        }),
      });
    });

    await page.route('**/api/meta/posts/page-1_abc/timeseries/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          post_id: 'page-1_abc',
          metric: 'post_reactions_like_total',
          resolved_metric: 'post_reactions_like_total',
          period: 'lifetime',
          metric_availability: {
            post_reactions_like_total: { supported: true, last_checked_at: null, reason: '' },
          },
          points: [{ end_time: '2026-02-18T08:00:00Z', value: '44' }],
        }),
      });
    });

    await page.route('**/api/meta/pages/page-1/sync/', async (route) => {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          page_id: 'page-1',
          tasks: { page_task_id: 'task-page', post_task_id: 'task-post' },
        }),
      });
    });

    await page.route('**/api/meta/pages/page-1/exports/**', async (route) => {
      const method = route.request().method();
      if (method === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([]),
        });
        return;
      }
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'export-1',
          report_id: 'rep-1',
          export_format: 'csv',
          status: 'queued',
          artifact_path: '',
          error_message: '',
          metadata: {},
          completed_at: null,
          created_at: '2026-02-18T08:00:00Z',
          updated_at: '2026-02-18T08:00:00Z',
        }),
      });
    });

    await page.goto('/integrations/meta?code=oauth-code&state=oauth-state');
    await ensureSignedIn(page, '/integrations/meta?code=oauth-code&state=oauth-state');
    await expect(page.getByRole('heading', { name: /Meta/i })).toBeVisible();
    await expect(page.getByText('Business Page')).toBeVisible();

    await page.getByRole('button', { name: /Select & Open/i }).click();
    await expect(page).toHaveURL(/\/dashboards\/meta\/pages\/page-1\/overview/);

    await expect(page.getByRole('heading', { name: /Business Page/i })).toBeVisible();
    await expect(page.getByText(/Some metrics are not available for this Page/i)).toBeVisible();
    await expect(page.locator('.meta-kpi-metric').filter({ hasText: 'page_post_engagements' })).toBeVisible();

    await page.getByRole('link', { name: 'Posts' }).click();
    await expect(page.getByRole('heading', { name: /Page Posts/i })).toBeVisible();
    await expect(page.getByText('page-1_abc')).toBeVisible();
    await page.goto('/dashboards/meta/posts/page-1_abc');
    await expect(page.getByRole('heading', { name: /Post Detail/i })).toBeVisible();
    await expect(page.getByText('page-1_abc')).toBeVisible();
  });
});
