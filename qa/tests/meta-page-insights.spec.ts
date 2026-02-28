import { expect, test } from './fixtures/base';

test.describe('meta page insights smoke', () => {
  test('connect callback, select page, view dashboard and post drill-down', async ({
    page,
    mockMode,
  }) => {
    test.skip(!mockMode, 'Mock mode only');

    await page.route('**/api/meta/connect/callback/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          default_page_id: 'page-1',
          missing_required_permissions: [],
          oauth_connected_but_missing_permissions: false,
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

    await page.route('**/api/integrations/meta/pages/page-1/select/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ page_id: 'page-1', selected: true }),
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
          last_synced_at: '2026-02-19T10:00:00Z',
          metric_availability: {
            page_post_engagements: {
              supported: true,
              status: 'ACTIVE',
              last_checked_at: null,
              reason: 'Available',
            },
            page_impressions_unique: {
              supported: false,
              status: 'INVALID',
              last_checked_at: null,
              reason: 'Deprecated metric',
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
              resolved_metric: 'page_views_total',
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

    await page.route('**/api/meta/pages/page-1/posts/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          page_id: 'page-1',
          date_preset: 'last_28d',
          since: '2026-01-20',
          until: '2026-02-18',
          last_synced_at: '2026-02-19T10:00:00Z',
          metric_availability: {
            post_reactions_like_total: {
              supported: true,
              status: 'ACTIVE',
              last_checked_at: null,
              reason: 'Available',
            },
          },
          results: [
            {
              post_id: 'page-1_abc',
              page_id: 'page-1',
              created_time: '2026-02-18T08:00:00Z',
              permalink: 'https://example.com/p',
              media_type: 'status',
              message_snippet: 'Post copy',
              message: 'Post copy',
              last_synced_at: '2026-02-19T10:00:00Z',
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
          media_type: 'status',
          message: 'Post copy',
          last_synced_at: '2026-02-19T10:00:00Z',
          metric_availability: {
            post_reactions_like_total: {
              supported: true,
              status: 'ACTIVE',
              last_checked_at: null,
              reason: 'Available',
            },
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
            post_reactions_like_total: {
              supported: true,
              status: 'ACTIVE',
              last_checked_at: null,
              reason: 'Available',
            },
          },
          points: [{ end_time: '2026-02-18T08:00:00Z', value: 44 }],
        }),
      });
    });

    await page.route('**/api/meta/pages/page-1/sync/', async (route) => {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          page_id: 'page-1',
          tasks: { page: 'task-page', post: 'task-post' },
        }),
      });
    });

    await page.goto('/integrations/meta?code=oauth-code&state=oauth-state');
    await expect(page.getByRole('heading', { name: /Meta/i })).toBeVisible();
    await expect(page.getByText('Business Page')).toBeVisible();

    await page.getByRole('button', { name: /Select & Open/i }).click();

    await expect(page.getByRole('heading', { name: 'Business Page' })).toBeVisible();
    await expect(page.getByText(/Some metrics are not available for this Page/i)).toBeVisible();
    await expect(page.getByText('403')).toBeVisible();
    await expect(page.getByText(/Trend metric/i)).toBeVisible();

    await page.getByRole('link', { name: 'Posts' }).click();
    await expect(page.getByRole('heading', { name: /Page Posts/i })).toBeVisible();
    await expect(page.getByText('page-1_abc')).toBeVisible();
    await page.getByRole('button', { name: 'Open' }).click();
    await expect(page.getByRole('heading', { name: /Post Detail/i })).toBeVisible();
    await expect(page.getByText('page-1_abc')).toBeVisible();
  });
});
