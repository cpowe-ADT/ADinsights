const assert = require('node:assert/strict');
const test = require('node:test');

const { renderReport } = require('../lib/renderReport');

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

