const assert = require('node:assert/strict');
const test = require('node:test');

const { renderReport } = require('../lib/renderReport');
const { getLaunchOptions } = require('../lib/browser');

test('renderReport(meta_pages_v1) renders KPI cards and top posts', async () => {
  const html = await renderReport({
    template: 'meta_pages_v1',
    title: 'Facebook Page Insights',
    subtitle: 'Tenant X · Page: Y',
    dateRange: '2026-01-24 → 2026-02-20',
    generatedAt: '2026-02-21T00:00:00Z',
    kpis: [{ label: 'Engagements', rangeValue: '100', lastDayValue: '5' }],
    trend: {
      title: 'Engagements trend',
      note: 'Period: day',
      rangeLabel: '2026-01-24 → 2026-02-20',
      points: [{ date: '2026-02-20', value: 5 }],
    },
    topPosts: {
      title: 'Top posts',
      metricLabel: 'Media views',
      rows: [
        {
          createdTime: '2026-02-20',
          mediaType: 'PHOTO',
          messageSnippet: 'Hello <world>',
          metricValue: '10',
          permalink: 'https://example.com/post/1',
        },
      ],
    },
  });

  assert.ok(html.includes('Facebook Page Insights'));
  assert.ok(html.includes('Engagements'));
  assert.ok(html.includes('Range'));
  assert.ok(html.includes('Last day'));
  assert.ok(html.includes('Top posts'));
  assert.ok(html.includes('https://example.com/post/1'));
  assert.ok(html.includes('Hello &lt;world&gt;'));
});

test('renderReport(report_v1_snapshot) renders truthful client snapshot rows and availability notes', async () => {
  const html = await renderReport({
    template: 'report_v1_snapshot',
    title: 'SLB May report',
    subtitle: 'slb_monthly_social_report | preview abc123',
    dateRange: '2026-05-01 to 2026-05-31',
    generatedAt: '2026-06-26T00:00:00Z',
    kpis: [{ label: 'Page Follows', value: '6,023', context: 'organic_facebook_page' }],
    warnings: ['Reach unavailable without Meta approval <read_insights>.'],
    rows: [
      {
        page: 'Organic Facebook Page',
        widget: 'organic_page_summary',
        metric: 'Page Follows',
        value: '6,023',
        status: 'partial',
        note: 'Stored rows cover part of the requested range.',
      },
    ],
  });

  assert.ok(html.includes('SLB May report'));
  assert.ok(html.includes('Monthly client report'));
  assert.ok(html.includes('Social performance summary'));
  assert.ok(html.includes('Page Follows'));
  assert.ok(html.includes('6,023'));
  assert.ok(html.includes('Data availability notes'));
  assert.ok(!html.includes('<h2>Warnings</h2>'));
  assert.ok(html.includes('&lt;read_insights&gt;'));
  assert.ok(html.includes('organic_page_summary'));
  assert.ok(html.includes('Report evidence: slb_monthly_social_report | preview abc123'));
  assert.ok(html.indexOf('Report evidence:') > html.indexOf('organic_page_summary'));
});

test('renderReport(report_v1_snapshot) renders saved grid layout when provided', async () => {
  const html = await renderReport({
    template: 'report_v1_snapshot',
    title: 'SLB saved layout export',
    subtitle: 'slb_monthly_social_report | preview saved123',
    dateRange: '2026-05-01 to 2026-05-31',
    generatedAt: '2026-06-26T00:00:00Z',
    warnings: ['Reach unavailable without Meta approval.'],
    rows: [
      {
        page: 'Fallback page',
        widget: 'fallback_widget',
        metric: 'Fallback metric',
        value: '999',
        status: 'fresh',
        note: '',
      },
    ],
    reportLayout: {
      schema_version: 'report_layout_snapshot.v1',
      source: 'requester_saved_layout',
      config: {
        id: 'report-123',
        title: 'Saved client layout',
        cols: 12,
        rowHeight: 64,
        widgets: [
          {
            id: 'client-note',
            type: 'note',
            title: 'Client narrative',
            x: 1,
            y: 1,
            w: 12,
            h: 2,
            options: { text: 'Reach is unavailable without Meta approval.' },
          },
          {
            id: 'page-follows',
            type: 'kpi',
            title: 'Page Follows',
            x: 1,
            y: 3,
            w: 3,
            h: 2,
            data: null,
            options: { format: 'number' },
          },
          {
            id: 'engagement-table',
            type: 'table',
            title: 'Engagement',
            x: 4,
            y: 3,
            w: 8,
            h: 3,
            data: [
              { metric: 'Reactions', value: 122 },
              { metric: 'Comments', value: null },
            ],
            options: {
              columns: [
                { key: 'metric', header: 'Metric' },
                { key: 'value', header: 'Value' },
              ],
            },
          },
        ],
      },
    },
  });

  assert.ok(html.includes('Saved client layout'));
  assert.ok(html.includes('Monthly client report'));
  assert.ok(html.includes('Data availability notes'));
  assert.ok(html.includes('Client narrative'));
  assert.ok(html.includes('Page Follows'));
  assert.ok(html.includes('—'));
  assert.ok(html.includes('Comments'));
  assert.ok(html.includes('Report evidence: slb_monthly_social_report | preview saved123'));
  assert.ok(!html.includes('Fallback metric'));
});

test('getLaunchOptions uses configured native Chromium for container rendering', async (t) => {
  const originalPath = process.env.CHROMIUM_EXECUTABLE_PATH;
  process.env.CHROMIUM_EXECUTABLE_PATH = '/usr/bin/chromium';
  t.after(() => {
    if (originalPath === undefined) {
      delete process.env.CHROMIUM_EXECUTABLE_PATH;
    } else {
      process.env.CHROMIUM_EXECUTABLE_PATH = originalPath;
    }
  });

  assert.deepEqual(await getLaunchOptions(), {
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
    executablePath: '/usr/bin/chromium',
    headless: true,
  });
});
