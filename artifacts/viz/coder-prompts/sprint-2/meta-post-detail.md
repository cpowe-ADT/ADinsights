# Meta Post Detail Page — Visualization Upgrade

**Sprint:** 2
**Estimated size:** S
**Depends on:** sprint-1/kpi-tile.md, sprint-1/trend-line.md, sprint-1/chart-skeleton.md
**Blocks:** none
**Role needed:** frontend-engineer

## Context

`MetaPostDetailPage` at `/dashboards/meta/posts/:postId` shows detail for a single post: KPI strip, metric trend line, and metadata. The A4 synthesis applied M16 (loadPostTimeseries now accepts override params `{ metric, period }`). No combined call. No comments endpoint exists — suppress the comments block permanently.

## Inputs already in the repo (do not re-invent)

- `frontend/src/routes/MetaPostDetailPage.tsx`: existing file. A4 patch M16 applied.
- `frontend/src/stores/useMetaPageInsightsStore*`: post detail store with `loadPostTimeseries({ metric, period })`.
- All Sprint 1 viz components.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/routes/MetaPostDetailPage.tsx` (modify)
  - `frontend/src/routes/__tests__/MetaPostDetailPage.test.tsx` (create or modify)

- **Data binding**:

Post detail from `GET /api/integrations/posts/:postId/`:

```typescript
{
  post_id: string
  created_time: string
  media_type: string
  message: string | null
  permalink: string | null
  thumbnail_url: string | null
  metrics: {
    post_reach?: number
    post_impressions?: number
    post_reactions_like_total?: number
    shares?: number
    post_clicks?: number
    post_engaged_users?: number
  }
}
```

Timeseries from `GET /api/integrations/posts/:postId/timeseries/?metric={metric}&period={period}`:

```typescript
{
  metric: string;
  period: string;
  data: Array<{ date: string; value: number }>;
}
```

- KPI strip (4 tiles): Reach = `metrics.post_reach`, Impressions = `metrics.post_impressions`, Reactions = `metrics.post_reactions_like_total`, Shares = `metrics.shares`. Format all as `number`.
- TrendLine: `timeseries.data` — single series for the selected metric. Default metric: `post_reach`.
- Metric selector: a `<select>` dropdown above TrendLine for the user to pick which metric to chart. Options: Reach, Impressions, Reactions, Shares. On change, call `loadPostTimeseries({ metric: selectedMetric, period: 'last_28d' })`.
- Metadata row: media type, created time (formatted), permalink link — rendered as plain HTML, not a chart component.
- Comments table: **suppressed** — no endpoint exists. Add a `{/* Comments: [NEW-ENDPOINT] /api/integrations/posts/:postId/comments/ - not yet implemented */}` comment in JSX where it would go.

- **Interactions**: metric selector dropdown triggers timeseries reload via `loadPostTimeseries`.

- **Empty/loading/error states**:
  - Post loading: ChartSkeleton `kpi-strip` + `line`.
  - Post not found: `EmptyState reasonCode="not_found"`.
  - Timeseries loading: `TrendLine` `isLoading=true`.
  - Timeseries empty: TrendLine `emptyReasonCode="no_data_for_range"`.

- **A11y**: Metric selector `<label>` associated with `<select>`. Permalink opens in new tab: `target="_blank"` + `rel="noopener noreferrer"` + `aria-label="View post on Facebook (opens in new tab)"`.

## Design

```
┌────────────────────────────────────────────────────────┐
│ [Reach] [Impressions] [Reactions] [Shares]             │  ← 4 KpiTiles
├────────────────────────────────────────────────────────┤
│ Metric: [Reach ▼]   TrendLine for selected metric     │  ← height=260
├────────────────────────────────────────────────────────┤
│ Media: VIDEO  Created: Jan 15, 2026  [View on Facebook]│  ← metadata row
│ Message: "Exciting campaign launch for..."             │
│ {/* Comments: [NEW-ENDPOINT] not implemented */}       │
└────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] 4 KpiTiles from `metrics` object
- [ ] TrendLine renders selected metric timeseries
- [ ] Metric selector dropdown switches TrendLine data
- [ ] Metadata row renders media type, created time, permalink
- [ ] Comments block suppressed with `[NEW-ENDPOINT]` comment
- [ ] No `/api/metrics/combined/` call
- [ ] Loading and empty states work
- [ ] Tests green: `cd frontend && npm test -- --run src/routes/__tests__/MetaPostDetailPage.test.tsx`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Test deltas

`MetaPostDetailPage.test.tsx`:

```typescript
it('renders 4 KpiTiles from post metrics', () => { ... })
it('renders TrendLine with timeseries data', () => { ... })
it('metric selector change triggers loadPostTimeseries', async () => {
  const loadSpy = vi.spyOn(store, 'loadPostTimeseries')
  await user.selectOptions(screen.getByRole('combobox'), 'post_impressions')
  expect(loadSpy).toHaveBeenCalledWith({ metric: 'post_impressions', period: 'last_28d' })
})
it('renders metadata row with permalink', () => { ... })
it('does NOT call /api/metrics/combined/', () => { ... })
it('shows EmptyState reasonCode="not_found" for missing post', () => { ... })
```

## Out of scope

- Do NOT implement the comments endpoint or table
- Do NOT add social sharing buttons
- Do NOT modify `useMetaPageInsightsStore` — A4 M16 patch already added override params

## Open questions resolved

- **OQ-2 (Post comments endpoint — none exists)**: CONFIRMED NO ENDPOINT. Resolution: suppress comments block entirely. Add JSX comment `{/* Comments: [NEW-ENDPOINT] /api/integrations/posts/:postId/comments/ - not yet implemented */}`. No backend work in this sprint.
