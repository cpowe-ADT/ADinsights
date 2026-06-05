# Meta Campaigns Page — Visualization Upgrade

**Sprint:** 2
**Estimated size:** M
**Depends on:** sprint-1/kpi-tile.md, sprint-1/distribution-bar.md, sprint-1/data-table.md, sprint-1/sparkline.md, sprint-1/chart-skeleton.md
**Blocks:** none
**Role needed:** frontend-engineer

## Context

`MetaCampaignOverviewPage` at `/dashboards/meta/campaigns` shows a campaign-level rollup with a funnel visualization, top-campaigns bar, and a table with inline sparklines. The planned funnel requires Recharts `FunnelChart` — but `FunnelChart` is NOT available in Recharts 3.8.1. Use the stepped-bar fallback described below.

## Inputs already in the repo (do not re-invent)

- `frontend/src/routes/MetaCampaignOverviewPage.tsx`: existing file. A4 patch M7 applied.
- All Sprint 1 viz components.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/routes/MetaCampaignOverviewPage.tsx` (modify)
  - `frontend/src/routes/__tests__/MetaCampaignOverviewPage.test.tsx` (modify or create)

- **Data binding**:
  - KPI strip (4 tiles): `payload.metrics.spend`, `payload.metrics.impressions`, `payload.metrics.clicks`, `payload.metrics.conversions`.
  - Funnel (stepped-bar fallback): sum totals from `payload.metrics` — `{ impressions, clicks, conversions }`. Render as a `DistributionBar` in `layout="vertical"` (bars stacked vertically, each shorter than the one above, forming a funnel-like visual). Compute drop-off percentage between steps: `clickRate = clicks/impressions`, `convRate = conversions/clicks`.
  - Bar chart: `payload.campaign.rows` sorted by `spend` descending, take top 10. Use `DistributionBar` with `maxItems={10}`.
  - DataTable with inline Sparkline: `payload.campaign.rows[]`. Sparkline column: `Sparkline` component using `payload.campaign.trend` filtered by `campaign_id`. **If trend does not have per-campaign breakdown, suppress sparkline column and note `[NEW-ENDPOINT]`.**

- **Funnel fallback implementation**:

Since `FunnelChart` is not in Recharts 3.8.1, implement a custom stepped-bar funnel using `DistributionBar` with a visual treatment:

```typescript
// Funnel data: three bars, each sized proportionally to their value
const funnelData = [
  { label: `Impressions`, value: metrics.impressions, color: chartPalette[0] },
  {
    label: `Clicks (${clickRate}%)`,
    value: metrics.clicks,
    color: chartPalette[2],
  },
  {
    label: `Conversions (${convRate}%)`,
    value: metrics.conversions,
    color: chartPalette[3],
  },
];
// Render as DistributionBar with layout="horizontal" — bars extend rightward from labels on Y axis.
// The natural proportion of bar widths mimics funnel shape.
```

Add drop-off labels between bars: small text showing `▼ {drop-off pct}%` between each adjacent pair.

- **Empty/loading/error states**:
  - Loading: ChartSkeleton for each block.
  - `payload.campaign.rows.length === 0`: `EmptyState reasonCode="no_campaigns"`.

- **A11y**: Funnel fallback (DistributionBar) already has AccessibleTableToggle. Table has funnel values in rows.

## Design

```
┌────────────────────────────────────────────────────────┐
│ [Spend] [Impressions] [Clicks] [Conversions]           │  ← 4 KpiTiles
├───────────────────────────────┬────────────────────────┤
│ Funnel (stepped DistributionBar│ [reserved]            │  ← 50/50
│ Impressions → Clicks → Convs) │                       │
├───────────────────────────────┴────────────────────────┤
│ DistributionBar: Top 10 Campaigns by Spend             │  ← height=200
├────────────────────────────────────────────────────────┤
│ DataTable: Campaign, Spend, Impressions, CTR, ROAS     │  ← inline Sparkline (if available)
└────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] 4 KpiTiles render
- [ ] Funnel fallback (stepped DistributionBar) shows Impressions → Clicks → Conversions with drop-off %
- [ ] Top 10 Campaigns DistributionBar renders sorted by spend
- [ ] DataTable renders campaign rows with CSV export filename `meta-campaigns`
- [ ] Sparkline column suppressed with `[NEW-ENDPOINT]` comment if no per-campaign trend available
- [ ] `EmptyState reasonCode="no_campaigns"` when rows empty
- [ ] Tests green: `cd frontend && npm test -- --run src/routes/__tests__/MetaCampaignOverviewPage.test.tsx`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Test deltas

File: `frontend/src/routes/__tests__/MetaCampaignOverviewPage.test.tsx`

```typescript
it('renders 4 KpiTiles', () => { ... })
it('renders funnel as DistributionBar with 3 steps', () => {
  // DistributionBar receives data array of length 3 (impressions, clicks, conversions)
})
it('renders top 10 campaigns bar chart', () => { ... })
it('renders DataTable with campaign rows', () => { ... })
it('shows EmptyState with reasonCode="no_campaigns" when rows empty', () => { ... })
it('shows ChartSkeleton while loading', () => { ... })
```

## Out of scope

- Do NOT install a custom funnel chart library
- Do NOT implement FunnelChart (not available in Recharts 3.8.1)
- Do NOT modify `useMetaStore`

## Open questions resolved

- **OQ-6 (FunnelChart in Recharts 3.7.0/3.8.1)**: CONFIRMED NOT AVAILABLE. Recharts 3.x removed FunnelChart. Resolution: use `DistributionBar` with 3 bars (impressions, clicks, conversions) to create a proportional stepped-bar funnel. Drop-off percentages shown as annotations between bars.
