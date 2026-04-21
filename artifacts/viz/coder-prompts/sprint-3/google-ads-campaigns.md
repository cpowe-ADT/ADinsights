# Google Ads Campaigns Tab — Visualization Upgrade

**Sprint:** 3
**Estimated size:** M
**Depends on:** sprint-1/* (all kit components)
**Blocks:** none
**Role needed:** frontend-engineer

## Context

The Campaigns tab of the Google Ads workspace. Endpoint: `GET /api/google-ads/campaigns/`. Returns aggregated campaign rows — no daily time series. The TrendLine for per-campaign daily spend is not possible from this endpoint; use `DistributionBar` (top campaigns by spend) as the primary "trend" visualization. For a daily trend by channel, use `GET /api/google-ads/channels/` which returns rows that can be grouped by date if they include a `date_day` dimension — verify before implementing.

## Inputs already in the repo (do not re-invent)

- Campaign list endpoint response (verified from `backend/analytics/google_ads_views.py:610–686`):
```typescript
{
  count: number
  results: Array<{
    customer_id: string
    campaign_id: string
    campaign_name: string
    campaign_status: 'ENABLED' | 'PAUSED' | 'REMOVED'
    channel_type: string   // advertising_channel_type: SEARCH, DISPLAY, VIDEO, SHOPPING, PERFORMANCE_MAX
    spend: number
    impressions: number
    clicks: number
    ctr: number
    avg_cpc: number
    conversions: number
    cpa: number
    conversion_value: number
    roas: number
  }>
}
```

- All Sprint 1 viz components.

## Deliverable

- **File(s) to create/modify**: identify the campaigns tab component inside `frontend/src/routes/google-ads/` and modify it.
- Create corresponding test file.

- **Data binding**:
  - KPI strip (4 tiles): aggregate `results[]` client-side — Total Cost = sum(spend), Total Conversions = sum(conversions), Avg CPA = sum(spend)/sum(conversions), Avg ROAS = sum(conversion_value)/sum(spend).
  - BubbleScatter: `results[]` mapped to `{ id: campaign_id, label: campaign_name, x: spend, y: conversions/clicks (conv rate), z: impressions, shape: channel_type === 'SEARCH' || channel_type === 'PERFORMANCE_MAX' ? 'circle' : 'triangle', color: chartPalette[1] }`.
  - DistributionBar (replaces TrendLine — no daily series): Top 10 campaigns by spend. `data = results.slice(0,10).map(r => ({ label: r.campaign_name, value: r.spend }))`.
  - DataTable: columns — Campaign Name, Status chip, Channel, Cost, Clicks, Conv, CPA, ROAS. `onRowClick` → navigate to campaign detail URL.

- **Status chips**: inline colored badges in the Status column. Render as `<span>` with Tailwind classes:
  - `ENABLED`: `bg-green-100 text-green-800`
  - `PAUSED`: `bg-yellow-100 text-yellow-800`
  - `REMOVED`: `bg-red-100 text-red-800`
  - Use a TanStack Table `cell` renderer that returns the span.

- **Interactions**:
  - BubbleScatter `onBubbleClick(campaign_id)` → navigate to campaign detail.
  - DataTable row click → navigate to campaign detail.

- **Empty/loading/error states**: ChartSkeleton + EmptyState as per standard kit.

## Design

```
┌────────────────────────────────────────────────────────┐
│ [Total Cost] [Total Conv] [Avg CPA] [Avg ROAS]         │  ← 4 KpiTiles
├────────────────────────────────────────────────────────┤
│ BubbleScatter: x=Cost, y=Conv Rate, z=Impressions      │  ← height=300
├────────────────────────────────────────────────────────┤
│ DistributionBar: Top 10 Campaigns by Spend             │  ← replaces TrendLine
├────────────────────────────────────────────────────────┤
│ DataTable: Campaign | Status chip | Channel | Cost ... │  ← CSV export: google-ads-campaigns
└────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] 4 KpiTiles from aggregated campaign rows
- [ ] BubbleScatter with campaigns (x=cost, y=conv rate, z=impressions, shape by channel)
- [ ] DistributionBar top 10 campaigns by spend
- [ ] DataTable with Status chips, sortable, CSV export
- [ ] Row click navigates to campaign detail
- [ ] Loading and empty states
- [ ] Tests green: `cd frontend && npm test -- --run`
- [ ] Lint clean and build clean

## Test deltas

```typescript
it('renders 4 KpiTiles with aggregated values', () => { ... })
it('renders BubbleScatter with campaign points', () => { ... })
it('renders DistributionBar for top 10 campaigns', () => { ... })
it('DataTable renders Status chips with correct colors', () => { ... })
it('bubble click calls navigate with campaign detail URL', () => { ... })
```

## Out of scope

- Do NOT add per-campaign daily time series (no endpoint — `[NEW-ENDPOINT]` comment if needed)
- Do NOT add inline sparklines (no per-campaign daily data)
- Do NOT add change-log badges (that is the Changes tab)

## Open questions resolved

- **OQ-1 (Campaign daily series — may need new endpoint)**: CONFIRMED: `/api/google-ads/campaigns/` returns aggregate rows only, no date dimension. Resolution: replace TrendLine with `DistributionBar` showing top-10-by-spend. If per-campaign daily series is needed in a future sprint, it requires a `[NEW-ENDPOINT]`.
