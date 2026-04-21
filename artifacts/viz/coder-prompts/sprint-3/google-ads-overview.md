# Google Ads Overview Tab — Visualization Upgrade

**Sprint:** 3
**Estimated size:** M
**Depends on:** sprint-1/* (all kit components)
**Blocks:** none
**Role needed:** frontend-engineer

## Context

The Overview tab of the Google Ads workspace (`/dashboards/google-ads` → Overview tab) shows aggregate KPIs, a cost+conversions trend, channel cost mix, alert insight cards, and a governance stats row. The primary endpoint is `GET /api/google-ads/workspace/summary/` (also called `GoogleAdsWorkspaceSummaryView`). A4 patch B6 already ensures `{ platforms, customer_id, start_date, end_date }` is passed.

## Inputs already in the repo (do not re-invent)

- `frontend/src/routes/google-ads/GoogleAdsWorkspacePage.tsx`: workspace shell — tabs are rendered here. Identify which component handles the Overview tab content.
- `frontend/src/hooks/useGoogleAdsWorkspaceData.ts`: workspace data hook with `buildCommonParams`. B1 fix applied (adds `platforms: 'google_ads'`).
- All Sprint 1 viz components.
- `frontend/src/styles/chartTheme.ts`: `PLATFORM_CHART_TOKENS` (google_ads = `#f97316`).

## Deliverable

- **File(s) to create/modify**: identify and modify the Overview tab component (likely `GoogleAdsExecutivePage.tsx` or the overview tab panel inside `GoogleAdsWorkspacePage.tsx`).
- Also create/modify the corresponding test file.

- **Data binding**:

Workspace summary response shape (verified from `backend/analytics/google_ads_views.py:503–607`):
```typescript
{
  window: { start_date, end_date, compare_start_date, compare_end_date }
  metrics: { spend, impressions, clicks, conversions, conversion_value, ctr, cpm, roas }
  comparison: { spend, impressions, clicks, conversions, ...}
  pacing: { spend_mtd, budget_month, forecast_month_end, over_under, pacing_pct }
  trend: Array<{ date: string; spend: number; conversions: number; roas: number }>
  movers: Array<{ campaign_id, campaign_name, spend, conversion_value, roas }>
  alerts_summary: { overspend_risk: boolean; underdelivery: boolean; spend_spike: boolean; conversion_drop: boolean }
  governance_summary: { recent_changes_7d: number; active_recommendations: number; disapproved_ads: number }
  top_insights: Array<{ type: string; message: string }>
}
```

  - KPI strip (4 tiles — NOT 5; IS tile deferred): Cost = `metrics.spend`, Conversions = `metrics.conversions`, CPA = `metrics.spend / metrics.conversions` (computed client-side if not in payload), ROAS = `metrics.roas`.
  - TrendLine dual-axis: `trend[]` — `{ date, spend, conversions }`. Left axis = spend (currency), right axis = conversions (number). Series: `[{ key: 'spend', label: 'Cost', color: chartPalette[1] }, { key: 'conversions', label: 'Conversions', color: chartPalette[3], yAxisId: 'right' }]`.
  - Channel pie: `GET /api/google-ads/channels/` (separate call — use existing workspace hook if it already fetches this, else add the fetch). Response rows: `{ channel_type, spend, clicks, impressions, conversions }`. Map to `[{ label: row.channel_type, value: row.spend }]`.
  - Insights cards: render `top_insights[]` as 3 plain cards (no Recharts) — `<div>` with icon + message text. Alert badges from `alerts_summary` booleans.
  - Governance row: 3 stat tiles showing `governance_summary.recent_changes_7d`, `governance_summary.active_recommendations`, `governance_summary.disapproved_ads`.

- **Interactions**: Movers table (optional) — top 5 campaigns by spend as a mini DataTable below insights. Click row navigates to campaign detail.

- **Empty/loading/error states**:
  - Loading: ChartSkeleton for each block.
  - `metrics.spend === 0 && metrics.conversions === 0`: `EmptyState reasonCode="no_data_for_range"`.

- **A11y**: Insight cards — `role="alert"` for overspend risk cards. Governance stats — `role="list"`.

## Design

```
┌────────────────────────────────────────────────────────┐
│ [Cost] [Conversions] [CPA] [ROAS]                      │  ← 4 KpiTiles (IS deferred)
├────────────────────────────────────────────────────────┤
│ Cost (left) + Conversions (right) dual-axis TrendLine  │  ← height=260
├──────────────────────────────┬─────────────────────────┤
│ Cost by Channel (Pie)        │ Alert Insight Cards (3) │  ← 60/40
├──────────────────────────────┴─────────────────────────┤
│ Governance: [Changes 7d] [Active Recs] [Disapproved]   │  ← stat row
└────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] 4 KpiTiles (Cost, Conv, CPA, ROAS) — IS tile suppressed with `{/* IS: [DEFERRED] impression_share not in endpoint payload */}`
- [ ] Dual-axis TrendLine: Cost left, Conversions right
- [ ] Channel cost PieComposition from `/api/google-ads/channels/`
- [ ] Top insights cards rendered from `top_insights[]`
- [ ] Governance stat row renders `governance_summary` values
- [ ] Loading skeletons for all blocks
- [ ] EmptyState for no-data range
- [ ] Tests green: `cd frontend && npm test -- --run` (identify test file)
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Test deltas

```typescript
it('renders 4 KpiTiles (Cost, Conv, CPA, ROAS)', () => { ... })
it('renders TrendLine with dual axis', () => { ... })
it('renders PieComposition for channel costs', () => { ... })
it('renders governance stat row', () => { ... })
it('shows ChartSkeleton while loading', () => { ... })
```

## Out of scope

- Do NOT add Impression Share tile (IS not in endpoint payload — defer to future sprint)
- Do NOT add a competitor IS chart
- Do NOT modify `buildCommonParams` (B1 fix already applied)

## Open questions resolved

- **OQ-4 (Impression Share metric unconfirmed)**: CONFIRMED NOT AVAILABLE in workspace summary payload. Fields are: spend, impressions, clicks, conversions, conversion_value. IS tile deferred — marked with `[DEFERRED]` comment.
