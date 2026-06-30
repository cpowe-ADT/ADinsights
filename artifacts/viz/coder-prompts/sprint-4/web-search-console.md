# Search Console Dashboard Page — Visualization Upgrade

**Sprint:** 4
**Estimated size:** S
**Depends on:** sprint-1/\* (all kit components)
**Blocks:** none
**Role needed:** frontend-engineer

## Context

`SearchConsoleDashboardPage` at `/dashboards/web/search-console` shows Google Search Console data. Own store, own date picker, NO combined call. Endpoint: `GET /api/web/search-console/?start_date=...&end_date=...`. Backend returns at most 500 rows ordered by `date_day DESC`.

## Inputs already in the repo (do not re-invent)

- `frontend/src/routes/SearchConsoleDashboardPage.tsx`: existing file.
- Search Console response shape:

```typescript
{
  rows: Array<{
    date_day: string; // 'YYYY-MM-DD'
    site_url: string;
    country: string;
    device: string; // 'DESKTOP' | 'MOBILE' | 'TABLET'
    query: string;
    page: string; // URL path
    clicks: number;
    impressions: number;
    ctr: number; // 0.0 – 1.0
    position: number; // avg position (lower = better, e.g., 1.0 = top)
  }>;
}
```

- All Sprint 1 viz components.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/routes/SearchConsoleDashboardPage.tsx` (modify)
  - `frontend/src/routes/__tests__/SearchConsoleDashboardPage.test.tsx` (modify or create)

- **Data binding** (client-side aggregations):
  - KPI strip (4 tiles): Total Clicks = sum(clicks); Total Impressions = sum(impressions); Avg CTR = mean(ctr) — format as `percent`; Avg Position = mean(position) — format as `rate` with 1 decimal. Note: lower position is better — show no change-arrow direction inversion.
  - TrendLine dual-axis: aggregate `rows` by `date_day` — `{ date, clicks: sum(clicks), impressions: sum(impressions) }`. Left axis = Clicks (number), right axis = Impressions (number). Use `rightYFormat="number"` on TrendLine.
  - PieComposition: aggregate `rows` by `device` — sum clicks per device. 3 segments: DESKTOP, MOBILE, TABLET.
  - DataTable (top queries): aggregate `rows` by `query` — sum clicks, impressions, mean ctr, mean position. Sort by clicks descending. Top 50 rows. Columns: Query, Clicks, Impressions, CTR, Avg Position. CSV export filename `search-console`.

- **Interactions**: DataTable row click → no-op.

- **Empty/loading/error states**: same pattern as GA4 page.

## Design

```
┌────────────────────────────────────────────────────────┐
│ [Clicks] [Impressions] [Avg CTR] [Avg Position]        │  ← 4 KpiTiles
├────────────────────────────────────────────────────────┤
│ TrendLine: Clicks (left) + Impressions (right) by day  │  ← height=260, dual-axis
├──────────────────────────────┬─────────────────────────┤
│ Device Mix (Pie: Desktop/    │  [reserved]             │
│ Mobile/Tablet by clicks)     │                         │
├──────────────────────────────┴─────────────────────────┤
│ DataTable: Top 50 Queries by Clicks                    │  ← CSV: search-console
└────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] 4 KpiTiles (Clicks, Impressions, Avg CTR, Avg Position)
- [ ] Dual-axis TrendLine (Clicks left, Impressions right)
- [ ] Device mix PieComposition (3 segments)
- [ ] Top queries DataTable (top 50, aggregated by query)
- [ ] NO call to `/api/metrics/combined/` (test asserts)
- [ ] Loading and empty states
- [ ] Tests green: `cd frontend && npm test -- --run src/routes/__tests__/SearchConsoleDashboardPage.test.tsx`
- [ ] Lint clean and build clean

## Test deltas

```typescript
it('renders 4 KpiTiles', () => { ... })
it('renders dual-axis TrendLine', () => { ... })
it('renders device mix PieComposition with 3 segments', () => {
  // mock data with DESKTOP, MOBILE, TABLET rows
  // pie should have 3 slices
})
it('DataTable shows top 50 queries', () => { ... })
it('does NOT call /api/metrics/combined/', () => {
  const getSpy = vi.spyOn(apiClient, 'get')
  render(<SearchConsoleDashboardPage />)
  const combined = getSpy.mock.calls.filter(([url]) => url?.includes('/metrics/combined'))
  expect(combined.length).toBe(0)
})
it('shows EmptyState when rows empty', () => { ... })
```

## Out of scope

- Do NOT add Google Search Console property selector
- Do NOT add page (URL) drill-down
- Do NOT fetch `/api/metrics/combined/` for any reason
