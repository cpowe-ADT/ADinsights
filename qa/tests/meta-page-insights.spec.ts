import { expect, test } from './fixtures/base';

test.describe('meta page insights smoke', () => {
  test('connect callback, select page, view dashboard and post drill-down', async ({ page, mockMode }) => {
    test.skip(!mockMode, 'Mock mode only');

    await page.route('**/api/integrations/meta/oauth/callback/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          connection_id: 'conn-1',
          token_debug_valid: true,
          granted_permissions: ['read_insights', 'pages_read_engagement'],
          declined_permissions: [],
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

    await page.route('**/api/integrations/meta/pages/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
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
          missing_required_permissions: [],
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

    await page.route('**/api/metrics/meta/pages/page-1/overview/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          page_id: 'page-1',
          date_preset: 'last_28d',
          since: '2026-01-20',
          until: '2026-02-18',
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

    await page.route('**/api/metrics/meta/pages/page-1/timeseries/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          page_id: 'page-1',
          metric: 'page_post_engagements',
          resolved_metric: 'page_post_engagements',
          period: 'day',
          since: '2026-01-20',
          until: '2026-02-18',
          points: [
            { end_time: '2026-02-17T08:00:00Z', value: '10' },
            { end_time: '2026-02-18T08:00:00Z', value: '22' },
          ],
        }),
      });
    });

    await page.route('**/api/metrics/meta/pages/page-1/posts/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          page_id: 'page-1',
          since: '2026-01-20',
          until: '2026-02-18',
          results: [
            {
              post_id: 'page-1_abc',
              created_time: '2026-02-18T08:00:00Z',
              permalink_url: 'https://example.com/p',
              message: 'Post copy',
              metrics: { post_reactions_like_total: 44 },
            },
          ],
        }),
      });
    });

    await page.route('**/api/metrics/meta/posts/page-1_abc/timeseries/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          post_id: 'page-1_abc',
          metric: 'post_reactions_like_total',
          resolved_metric: 'post_reactions_like_total',
          period: 'lifetime',
          points: [{ end_time: '2026-02-18T08:00:00Z', value: '44' }],
        }),
      });
    });

    await page.route('**/api/metrics/meta/pages/page-1/refresh/', async (route) => {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({ page_task_id: 'task-page', post_task_id: 'task-post' }),
      });
    });

    await page.goto('/integrations/meta?code=oauth-code&state=oauth-state');
    await expect(page.getByRole('heading', { name: /Meta/i })).toBeVisible();
    await expect(page.getByText('Business Page')).toBeVisible();

    await page.getByRole('button', { name: 'Select' }).click();
    await page.getByRole('link', { name: 'Open dashboard' }).click();

    await expect(page.getByRole('heading', { name: /Facebook Page Insights/i })).toBeVisible();
    await expect(page.getByText(/page_impressions_unique is invalid/i)).toBeVisible();
    await expect(page.locator('.meta-kpi-title').filter({ hasText: 'page_post_engagements' })).toBeVisible();

    await page.getByRole('link', { name: 'Posts view' }).click();
    await expect(page.getByRole('heading', { name: /Facebook Post Insights/i })).toBeVisible();
    await expect(page.getByText('page-1_abc')).toBeVisible();
    await page.getByRole('button', { name: 'Drill down' }).click();
    await expect(page.getByText('Post page-1_abc')).toBeVisible();
  });
});
