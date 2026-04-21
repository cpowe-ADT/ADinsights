# GA4 Dashboard Page — Visualization Upgrade

**Sprint:** 4
**Estimated size:** S
**Depends on:** sprint-1/* (all kit components)
**Blocks:** none
**Role needed:** frontend-engineer

## Context

`GoogleAnalyticsDashboardPage` at `/dashboards/web/ga4` shows web analytics data from Google Analytics 4. This page has its OWN store, its OWN date picker, and must NEVER call `/api/metrics/combined/`. Endpoint: `GET /api/web/ga4/?start_date=...&end_date=...`. The backend returns at most 500 rows ordered by `date_day DESC`.

## Inputs already in the repo (do not re-invent)

- `frontend/src/routes/GoogleAnalyticsDashboardPage.tsx`: existing file.
- GA4 response shape:
```typescript
{
  source: 'ga4'
  status: 'ok'
  count: number
  rows: Array<{
    date_day: string       // 'YYYY-MM-DD'
    property_id: string
    channel_group: string  // 'Organic Search' | 'Direct' | 'Paid Social' | 'Email' | etc.
    country: string
    city: string
    campaign_name: string | null
    sessions: number
    engaged_sessions: number
    conversions: number
    purchase_revenue: number
    engagement_rate: number
    conversion_rate: number
  }>
}
```
- All Sprint 1 viz components.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/routes/GoogleAnalyticsDashboardPage.tsx` (modify)
  - `frontend/src/routes/__tests__/GoogleAnalyticsDashboardPage.test.tsx` (modify or create)

- **Data binding** (all client-side aggregations):
  - KPI strip (4 tiles): Total Sessions = sum(sessions); Total Conversions = sum(conversions); Total Revenue = sum(purchase_revenue) — format as `currency` with `currency='USD'` (GA4 reports in USD); Avg Engagement Rate = mean(engagement_rate) — format as `percent`.
  - TrendLine: aggregate `rows` by `date_day` — sum sessions per day. Single series. Date range from own date picker.
  - PieComposition: aggregate `rows` by `channel_group` — sum sessions per channel. Top 8 channels, rest as "Other".
  - DataTable: aggregate `rows` by `channel_group` — columns: Channel Group, Sessions, Conversions, Revenue, Engagement Rate. CSV export filename `ga4`.

- **Date picker**: this page has its own date range state (not `useDashboardStore.filters`). Verify the existing component has a date picker; if not, add a simple `<input type="date">` pair for start/end and pass to the store action.

- **Interactions**: DataTable row click → no-op for Sprint 4.

- **Empty/loading/error states**:
  - Loading: ChartSkeleton for each block.
  - `rows.length === 0`: `EmptyState reasonCode="no_data_for_range"`.
  - `status !== 'ok'`: `EmptyState reasonCode="adapter_error"` with retry button.

- **A11y**: Revenue currency in KpiTile: `aria-label="Total Revenue: $1,234 USD"`.

## Design

```
┌────────────────────────────────────────────────────────┐
│ [Sessions] [Conversions] [Revenue] [Avg Engagement]    │  ← 4 KpiTiles (USD for revenue)
├────────────────────────────────────────────────────────┤
│ TrendLine: Sessions by day                             │  ← height=260
├──────────────────────────────┬─────────────────────────┤
│ Channel Mix (PieComposition) │  [reserved]             │  ← sessions by channel_group
├──────────────────────────────┴─────────────────────────┤
│ DataTable: Channel | Sessions | Conv | Revenue | Engage│  ← CSV: ga4
└────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] 4 KpiTiles (Sessions, Conv, Revenue in USD, Engagement Rate)
- [ ] TrendLine shows sessions by date_day
- [ ] PieComposition shows channel_group mix
- [ ] DataTable with channel group aggregation
- [ ] Date picker triggers refetch
- [ ] NO call to `/api/metrics/combined/` (test asserts)
- [ ] Loading and empty/error states
- [ ] Tests green: `cd frontend && npm test -- --run src/routes/__tests__/GoogleAnalyticsDashboardPage.test.tsx`
- [ ] Lint clean and build clean

## Test deltas

```typescript
it('renders 4 KpiTiles', () => { ... })
it('renders TrendLine with aggregated session data', () => { ... })
it('renders channel mix PieComposition', () => { ... })
it('DataTable aggregates by channel_group', () => { ... })
it('does NOT call /api/metrics/combined/', () => {
  const getSpy = vi.spyOn(apiClient, 'get')
  render(<GoogleAnalyticsDashboardPage />)
  const combined = getSpy.mock.calls.filter(([url]) => url?.includes('/metrics/combined'))
  expect(combined.length).toBe(0)
})
it('shows EmptyState reasonCode="no_data_for_range" when rows empty', () => { ... })
it('shows EmptyState reasonCode="adapter_error" on API error', () => { ... })
```

## Out of scope

- Do NOT add GA4 property selector
- Do NOT implement real-time GA4 data
- Do NOT add city/country drill-down
- Do NOT fetch `/api/metrics/combined/` for any reason
