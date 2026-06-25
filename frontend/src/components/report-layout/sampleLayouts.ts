import type { DashboardLayoutConfig } from './layoutSchema';

/**
 * SLB monthly social report rendered as a config. Values are the real
 * edge-sourced May 2026 figures recovered for the Students' Loan Bureau page
 * (6,023 followers; 16 reactions, 8 shares, 0 comments across 22 posts) — so
 * this doubles as a live example of the no-read_insights engagement fix.
 */
export const slbSampleLayout: DashboardLayoutConfig = {
  id: 'slb-monthly-sample',
  title: 'SLB Monthly Social — May 2026',
  cols: 12,
  rowHeight: 64,
  widgets: [
    { id: 'kpi-followers', type: 'kpi', title: 'Followers', x: 1, y: 1, w: 3, h: 2, data: 6023, options: { format: 'number' } },
    { id: 'kpi-reactions', type: 'kpi', title: 'Reactions', x: 4, y: 1, w: 3, h: 2, data: 16, options: { format: 'number' } },
    { id: 'kpi-shares', type: 'kpi', title: 'Shares', x: 7, y: 1, w: 3, h: 2, data: 8, options: { format: 'number' } },
    { id: 'kpi-posts', type: 'kpi', title: 'Posts published', x: 10, y: 1, w: 3, h: 2, data: 22, options: { format: 'number' } },
    {
      id: 'bar-top-posts',
      type: 'bar',
      title: 'Top posts by reactions',
      x: 1, y: 3, w: 7, h: 4,
      data: [
        { label: 'May 8', value: 3 },
        { label: 'May 18', value: 3 },
        { label: 'May 6', value: 2 },
        { label: 'May 26', value: 2 },
        { label: 'May 28', value: 2 },
      ],
      options: { height: 220 },
    },
    {
      id: 'pie-engagement',
      type: 'pie',
      title: 'Engagement mix',
      x: 8, y: 3, w: 5, h: 4,
      data: [
        { label: 'Reactions', value: 16 },
        { label: 'Shares', value: 8 },
        { label: 'Comments', value: 0 },
      ],
      options: { centerLabel: '24', height: 220 },
    },
    {
      id: 'table-posts',
      type: 'table',
      title: 'Post-level engagement',
      x: 1, y: 7, w: 12, h: 4,
      data: [
        { date: '2026-05-08', reactions: 3, shares: 0 },
        { date: '2026-05-18', reactions: 3, shares: 1 },
        { date: '2026-05-06', reactions: 2, shares: 0 },
        { date: '2026-05-26', reactions: 2, shares: 1 },
        { date: '2026-05-28', reactions: 2, shares: 0 },
      ],
      options: {
        columns: [
          { key: 'date', header: 'Date' },
          { key: 'reactions', header: 'Reactions', align: 'right' },
          { key: 'shares', header: 'Shares', align: 'right' },
        ],
      },
    },
    {
      id: 'note-reach',
      type: 'note',
      title: 'Reach & impressions',
      x: 1, y: 11, w: 12, h: 1,
      options: {
        text: 'Reach/impressions require the read_insights permission (pending Meta App Review) and are intentionally omitted rather than shown as zero.',
      },
    },
  ],
};

/**
 * Live-bound layout: widgets carry `dataKey`s instead of inline data, so the
 * page binds them to the real dashboard store (campaign summary + parish rows)
 * via {@link createStoreResolver}. Same schema, real data.
 */
export const liveDashboardLayout: DashboardLayoutConfig = {
  id: 'live-dashboard',
  title: 'Live dashboard',
  cols: 12,
  rowHeight: 64,
  widgets: [
    { id: 'spend', type: 'kpi', title: 'Spend', x: 1, y: 1, w: 3, h: 2, dataKey: 'summary.totalSpend', options: { format: 'currency', currency: 'JMD' } },
    { id: 'clicks', type: 'kpi', title: 'Clicks', x: 4, y: 1, w: 3, h: 2, dataKey: 'summary.totalClicks', options: { format: 'number' } },
    { id: 'conversions', type: 'kpi', title: 'Conversions', x: 7, y: 1, w: 3, h: 2, dataKey: 'summary.totalConversions', options: { format: 'number' } },
    { id: 'roas', type: 'kpi', title: 'ROAS', x: 10, y: 1, w: 3, h: 2, dataKey: 'summary.averageRoas', options: { format: 'rate' } },
    { id: 'parish-spend', type: 'bar', title: 'Spend by parish', x: 1, y: 3, w: 7, h: 4, dataKey: 'parish.spend', options: { currency: 'JMD', height: 220 } },
    { id: 'parish-clicks', type: 'pie', title: 'Clicks by parish', x: 8, y: 3, w: 5, h: 4, dataKey: 'parish.clicks', options: { height: 220 } },
    {
      id: 'parish-table',
      type: 'table',
      title: 'Parish metrics',
      x: 1, y: 7, w: 12, h: 4,
      dataKey: 'parish.rows',
      options: {
        columns: [
          { key: 'parish', header: 'Parish' },
          { key: 'spend', header: 'Spend', align: 'right' },
          { key: 'clicks', header: 'Clicks', align: 'right' },
          { key: 'roas', header: 'ROAS', align: 'right' },
        ],
      },
    },
  ],
};
