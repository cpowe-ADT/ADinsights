# Google Ads Assets Tab — Visualization Upgrade

**Sprint:** 3
**Estimated size:** S
**Depends on:** sprint-1/* (all kit components)
**Blocks:** none
**Role needed:** frontend-engineer

## Context

The Assets tab in the Google Ads workspace. Endpoint: `GET /api/google-ads/assets/`. Asset rows include type, performance metrics, and policy status. Per-asset sparklines are NOT available — no daily time series endpoint exists for assets. Sparkline column is suppressed.

## Inputs already in the repo (do not re-invent)

- Asset row fields (from sprint plan): `asset_type, asset_id, impressions, clicks, conversions, cpa, ctr, policy_approval_status`
- All Sprint 1 viz components.

## Deliverable

- **File(s) to create/modify**: identify the Assets tab component and modify it.

- **Data binding**:
  - KPI strip (3 tiles): Total Assets = count rows; Disapproved Count = count where `policy_approval_status === 'DISAPPROVED'`; Top Asset Conv = max(conversions) value.
  - PieComposition: group rows by `asset_type`, count per type. Data: `[{ label: type, value: count }]`.
  - DataTable: Asset Type, Asset ID (truncated), Impressions, Clicks, Conv, CPA, Status chip (`policy_approval_status` — APPROVED=green, DISAPPROVED=red, LIMITED=yellow). CSV export filename `google-ads-assets`.
  - Sparkline column: **suppressed**. Add `{/* Per-asset sparkline: [NEW-ENDPOINT] /api/google-ads/assets/:assetId/timeseries/ - not yet implemented */}` comment in the column definition.

- **Status chips**: `policy_approval_status` rendered as colored `<span>`:
  - `APPROVED`: `bg-green-100 text-green-800`
  - `DISAPPROVED`: `bg-red-100 text-red-800`
  - `LIMITED`: `bg-yellow-100 text-yellow-800`
  - `UNKNOWN` / other: `bg-gray-100 text-gray-800`

## Design

```
┌────────────────────────────────────────────────────────┐
│ [Total Assets] [Disapproved] [Top Asset Conv]          │  ← 3 KpiTiles
├──────────────────────────────┬─────────────────────────┤
│ Asset Type Distribution (Pie)│  [reserved]             │  ← 50%
├──────────────────────────────┴─────────────────────────┤
│ DataTable: Asset Type | ID | Impr | Clicks | Conv | ▼  │  ← CSV: google-ads-assets
└────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] 3 KpiTiles
- [ ] PieComposition by asset type
- [ ] DataTable with Status chips, no sparkline column
- [ ] `[NEW-ENDPOINT]` comment in DataTable column definition for sparklines
- [ ] Loading and empty states
- [ ] Tests green
- [ ] Lint clean and build clean

## Test deltas

```typescript
it('renders 3 KpiTiles', () => { ... })
it('renders PieComposition for asset type distribution', () => { ... })
it('renders DataTable with policy_approval_status chips', () => { ... })
it('DataTable does NOT render a Sparkline column', () => {
  // assert no <Sparkline> component in rendered output
})
```

## Out of scope

- Do NOT implement per-asset sparklines (no endpoint)
- Do NOT add asset preview/thumbnail display

## Open questions resolved

- **OQ-3 (Per-asset sparklines — no endpoint)**: CONFIRMED NO ENDPOINT. Resolution: suppress sparkline column entirely. Add `[NEW-ENDPOINT]` comment for `GET /api/google-ads/assets/:assetId/timeseries/`.
