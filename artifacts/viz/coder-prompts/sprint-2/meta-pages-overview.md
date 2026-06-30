# Meta Pages List + Page Overview — Visualization Upgrade

**Sprint:** 2
**Estimated size:** S
**Depends on:** sprint-1/kpi-tile.md, sprint-1/trend-line.md, sprint-1/pie-composition.md, sprint-1/data-table.md, sprint-1/chart-skeleton.md
**Blocks:** none
**Role needed:** frontend-engineer

## Context

Two pages are covered here since they share a tight scope:

1. **MetaPagesListPage** (`/dashboards/meta/pages`): a cards grid + DataTable of connected Facebook Pages. No analytics charts — no combined call. Endpoint: `GET /api/integrations/pages/`.
2. **MetaPageOverviewPage** (`/dashboards/meta/pages/:pageId/overview`): KPI strip + TrendLine + engagement PieComposition for a single page. Endpoint: `GET /api/integrations/pages/:pageId/overview/`. No combined call.

## Inputs already in the repo (do not re-invent)

- `frontend/src/routes/MetaPagesListPage.tsx`: existing file.
- `frontend/src/routes/MetaPageOverviewPage.tsx`: existing file. A4 patch M12 applied (period-reset effect no longer calls loadTimeseries directly).
- `frontend/src/stores/useMetaStore*`: pages store.
- All Sprint 1 viz components.
- `frontend/src/components/EmptyState.tsx`: `reasonCode` prop present.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/routes/MetaPagesListPage.tsx` (modify)
  - `frontend/src/routes/MetaPageOverviewPage.tsx` (modify)
  - `frontend/src/routes/__tests__/MetaPagesListPage.test.tsx` (create or modify)
  - `frontend/src/routes/__tests__/MetaPageOverviewPage.test.tsx` (create or modify)

### MetaPagesListPage changes

- **Data binding**: `GET /api/integrations/pages/` → `{ page_id, name, fan_count, last_synced_at, picture? }`.
- **Layout**: Cards grid (CSS `display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr))`) where each card shows: page thumbnail (if available), name, fan count formatted as number, last synced. Below the cards grid: `DataTable` with Page Name, Fan Count, Last Synced.
- **Card click**: navigate to `/dashboards/meta/pages/{page_id}/overview`.
- **Empty/loading**: ChartSkeleton variant `table` while loading. `EmptyState reasonCode="no_pages"` when empty.
- **No combined call**: assert in test that no fetch to `/api/metrics/combined/` is made.

### MetaPageOverviewPage changes

Response shape from `/api/integrations/pages/:pageId/overview/`:

```typescript
{
  kpis: Array<{
    metric: string;
    value: number | null;
    today_value: number | null;
    prior_value: number | null;
    change_pct: number | null;
  }>;
  daily_series: Record<string, Array<{ date: string; value: number }>>;
  engagement_breakdown: Record<string, Array<{ label: string; value: number }>>;
  date_preset: string;
  since: string;
  until: string;
}
```

- **KPI strip (4 tiles)**: map first 4 kpis by metric name. Typical metrics: `page_fans` (followers), `page_impressions`, `page_engaged_users`, `page_reach`. Use `kpi.change_pct` as the `change` prop.
- **TrendLine**: `daily_series[primary_metric]` where `primary_metric` is the first KPI metric name. Single series.
- **PieComposition**: `engagement_breakdown[primary_metric]` — slice labels and values.
- **Primary metric selection**: derive from the first entry in `kpis[]` that has non-null values. If no primary metric has a daily series, fall back to `daily_series[Object.keys(daily_series)[0]]`.
- **Empty state**: `EmptyState reasonCode="no_page_data"` when `kpis.every(k => k.value === null)`.

## Design

### Pages list

```
┌──────────────────────────────────────────────────────────┐
│ [Page Card]  [Page Card]  [Page Card]  [+ add more]      │
├──────────────────────────────────────────────────────────┤
│ DataTable: Page Name | Fan Count | Last Synced           │
└──────────────────────────────────────────────────────────┘
```

### Page overview

```
┌────────────────────────────────────────────────────────┐
│ [Followers] [Impressions] [Engaged] [Reach]             │  ← 4 KpiTiles
├────────────────────────────────────────────────────────┤
│ TrendLine: primary metric daily                         │  ← height=260
├────────────────────────────────────────────────────────┤
│ PieComposition: engagement breakdown                    │
└────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] Pages list renders card grid with click navigation to overview
- [ ] Pages list DataTable renders Page Name, Fan Count, Last Synced
- [ ] No `/api/metrics/combined/` call from pages list page (test asserts)
- [ ] Page overview renders 4 KpiTiles from `kpis[]`
- [ ] Page overview TrendLine uses `daily_series`
- [ ] Page overview PieComposition uses `engagement_breakdown`
- [ ] `EmptyState reasonCode="no_page_data"` when all kpi values null
- [ ] Tests green: `cd frontend && npm test -- --run src/routes/__tests__/MetaPagesListPage.test.tsx`
- [ ] Tests green: `cd frontend && npm test -- --run src/routes/__tests__/MetaPageOverviewPage.test.tsx`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Test deltas

`MetaPagesListPage.test.tsx`:

```typescript
it('renders page cards', () => { ... })
it('card click navigates to page overview', () => { ... })
it('renders DataTable with page rows', () => { ... })
it('does NOT call /api/metrics/combined/', () => {
  // use vi.spyOn(apiClient, 'get') and assert no call with /combined/
})
it('shows EmptyState reasonCode="no_pages" when empty', () => { ... })
```

`MetaPageOverviewPage.test.tsx`:

```typescript
it('renders KpiTiles from kpis[]', () => { ... })
it('renders TrendLine with daily_series data', () => { ... })
it('renders PieComposition with engagement_breakdown', () => { ... })
it('shows EmptyState reasonCode="no_page_data" when all kpis null', () => { ... })
it('does NOT call /api/metrics/combined/', () => { ... })
```

## Out of scope

- Do NOT add a page picker dropdown — navigation comes from the list page
- Do NOT add a "Posts" section here — that is a separate page (`meta-posts.md`)
- Do NOT implement date range picker for pages (uses `date_preset` from the endpoint)
