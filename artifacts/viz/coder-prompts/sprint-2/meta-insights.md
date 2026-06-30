# Meta Insights Dashboard Page — Visualization Upgrade

**Sprint:** 2
**Estimated size:** M
**Depends on:** sprint-1/kpi-tile.md, sprint-1/trend-line.md, sprint-1/bubble-scatter.md, sprint-1/data-table.md, sprint-1/chart-skeleton.md
**Blocks:** none
**Role needed:** frontend-engineer

## Context

`MetaInsightsDashboardPage` at `/dashboards/meta/insights` is the primary analytics view for a Meta ad account. It shows KPIs for the selected account (or all accounts), a dual-axis CTR+CPM trend, a bubble chart of campaigns by spend×ROAS×impressions, and a campaign drill-down table. Store: `useMetaStore`. Endpoint: `/api/metrics/combined/?platforms=meta_ads`.

## Inputs already in the repo (do not re-invent)

- `frontend/src/routes/MetaInsightsDashboardPage.tsx`: existing file. A4 patch M5 applied (loading guard).
- `frontend/src/styles/chartTheme.ts`: color tokens including `PLATFORM_CHART_TOKENS`.
- All Sprint 1 viz components.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/routes/MetaInsightsDashboardPage.tsx` (modify)
  - `frontend/src/routes/__tests__/MetaInsightsDashboardPage.test.tsx` (modify or create)

- **Props API / signature**: page component — no external props. Reads from `useMetaStore`.

- **Data binding**:
  - KPI strip (5 tiles): `payload.metrics.spend`, `payload.metrics.roas`, `payload.metrics.ctr`, `payload.metrics.frequency`, `payload.metrics.cpm` from `/api/metrics/combined/?platforms=meta_ads&account_id={selected}`.
  - TrendLine dual-axis: `payload.campaign.trend` array `{ date, ctr, cpm }`. Left Y axis = CTR (format: `percent`), right Y axis = CPM (format: `currency`). Two series: `{ key: 'ctr', label: 'CTR', color: chartPalette[0], yAxisId: 'left' }`, `{ key: 'cpm', label: 'CPM', color: chartPalette[1], dashed: true, yAxisId: 'right' }`.
  - NOTE: if `payload.campaign.trend` does not include `ctr` and `cpm` fields, derive them per day from `clicks/impressions` and `(spend/impressions)*1000`. Verify field availability before implementing.
  - BubbleScatter: `payload.campaign.rows[]` mapped to `{ id: row.campaign_id, label: row.campaign_name, x: row.spend, y: row.roas, z: row.impressions, shape: row.objective === 'LINK_CLICKS' ? 'circle' : 'triangle', color: chartPalette[0] }`.
  - Peer average: when `account_id` is selected, compute median `spend` per date from all-accounts trend data (cached in store). Pass as `peerData` to TrendLine.
  - DataTable: `payload.campaign.rows[]` columns: Campaign Name, Spend, Impressions, CTR, CPM, ROAS, Frequency, Objective.

- **Interactions**:
  - BubbleScatter `onBubbleClick(campaignId)` → no-op for Sprint 2 (campaign detail route may not be ready).
  - DataTable row click → no-op for Sprint 2 (same reason).
  - TrendLine legend toggle → hide/show CTR or CPM series.

- **Empty/loading/error states**:
  - `status === 'loading'`: ChartSkeleton for each block.
  - `payload empty`: `EmptyState reasonCode="no_data_for_range"` per block.
  - No accounts: `EmptyState reasonCode="no_accounts"`.

- **A11y**: dual-axis TrendLine must label both Y axes. BubbleScatter table view must have columns for all 4 dimensions.

## Design

```
┌────────────────────────────────────────────────────────┐
│ [Spend] [ROAS] [CTR] [Frequency] [CPM]                 │  ← 5 KpiTiles
├────────────────────────────────────────────────────────┤
│ CTR (left) + CPM (right) dual-axis TrendLine           │  ← height=260
├────────────────────────────────────────────────────────┤
│ BubbleScatter: x=Spend, y=ROAS, z=Impressions          │  ← height=300
├────────────────────────────────────────────────────────┤
│ DataTable: campaigns sorted by Spend desc              │  ← sortable, CSV export
└────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] 5 KpiTiles with correct values from `payload.metrics`
- [ ] Dual-axis TrendLine with CTR on left, CPM on right
- [ ] BubbleScatter with campaigns (x=spend, y=ROAS, z=impressions)
- [ ] Peer average line on TrendLine when account selected (median computed client-side)
- [ ] DataTable with campaign rows, CSV export filename `meta-insights`
- [ ] Loading skeletons for all blocks
- [ ] EmptyState variants work correctly
- [ ] Tests green: `cd frontend && npm test -- --run src/routes/__tests__/MetaInsightsDashboardPage.test.tsx`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Test deltas

File: `frontend/src/routes/__tests__/MetaInsightsDashboardPage.test.tsx`

```typescript
// Mock /api/metrics/combined/ returning payload with metrics + campaign.trend + campaign.rows
// Verify:
it('renders 5 KpiTile components', () => { ... })
it('renders dual-axis TrendLine (rightYFormat=currency)', () => {
  // The TrendLine must receive rightYFormat prop
  // Check that two Y axes are rendered in the chart SVG
})
it('renders BubbleScatter with campaign data', () => { ... })
it('DataTable shows campaign rows', () => { ... })
it('shows ChartSkeleton when loading', () => { ... })
it('shows EmptyState reasonCode="no_data_for_range" when payload empty', () => { ... })
```

## Out of scope

- Do NOT wire campaign detail drill-down (Sprint 2)
- Do NOT modify `useMetaStore`
- Do NOT add a new endpoint for CTR/CPM time series — derive client-side from existing trend data

## Open questions resolved

- **OQ-1 (Campaign daily series may need new endpoint)**: For `MetaInsightsDashboardPage`, `payload.campaign.trend` from the existing combined endpoint is used. If `ctr` and `cpm` are absent from trend rows, derive them client-side — no new endpoint required.
