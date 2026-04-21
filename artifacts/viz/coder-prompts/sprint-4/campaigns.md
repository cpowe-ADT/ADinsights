# Campaigns + Creatives + Budget Dashboards — Visualization Upgrade

**Sprint:** 4
**Estimated size:** M (combined)
**Depends on:** sprint-1/* (all kit components), sprint-4/platforms.md (for platformLabels.ts)
**Blocks:** none
**Role needed:** frontend-engineer

## Context

Three combined-platform dashboard pages with similar 5-block structure. All use `useDashboardStore` and `/api/metrics/combined/`. Combining into one prompt since the patterns are identical. A4 patches B-CAMP-01, B-CREA-01 (row-level platform filter) were deferred but the API call is already scoped — charts show filtered data correctly from the backend.

## Inputs already in the repo (do not re-invent)

- `frontend/src/routes/CampaignDashboard.tsx`: existing file.
- `frontend/src/routes/CreativeDashboard.tsx`: existing file.
- `frontend/src/routes/BudgetDashboard.tsx`: existing file. A4 patch B7 applied (B-BUDG-01 guard present).
- `frontend/src/lib/platformLabels.ts`: created in `platforms.md`.
- All Sprint 1 viz components.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/routes/CampaignDashboard.tsx` (modify)
  - `frontend/src/routes/CreativeDashboard.tsx` (modify)
  - `frontend/src/routes/BudgetDashboard.tsx` (modify)
  - `frontend/src/routes/__tests__/CampaignDashboard.test.tsx` (modify or create)
  - `frontend/src/routes/__tests__/CreativeDashboard.test.tsx` (modify or create)
  - `frontend/src/routes/__tests__/BudgetDashboard.test.tsx` (modify or create)

---

### CampaignDashboard (`/dashboards/campaigns`)

**Data binding**:
- KPI strip (4 tiles): `payload.metrics.spend`, `payload.metrics.clicks`, `payload.metrics.conversions`, ROAS = derived.
- TrendLine: `payload.campaign.trend` — spend by day. If `platform` field present in trend rows, use `getPlatformColor(row.platform)` for series colors. Otherwise single series.
- DistributionBar: `payload.campaign.rows` top 10 by spend. Labels from `row.campaign_name`.
- DataTable: Campaign, Platform chip (`getPlatformLabel`), Spend, Clicks, Conv, ROAS, CTR. Inline `Sparkline` per campaign if per-campaign daily data is available (otherwise suppress sparkline column). CSV filename `campaigns`.

**Platform chip in table**: colored badge using `getPlatformColor(row.platform)` as background.

---

### CreativeDashboard (`/dashboards/creatives`)

**Data binding**:
- KPI strip (4 tiles): aggregate from `payload.creative[]` — Total Spend, Total Impressions, Total Clicks, Top Creative Spend.
- BubbleScatter: `payload.creative[]` mapped to `{ id: row.name, label: row.name, x: row.spend, y: row.clicks/row.impressions (ctr), z: row.impressions, shape: row.platform === 'google_ads' ? 'triangle' : 'circle', color: getPlatformColor(row.platform) }`.
- PieComposition: `payload.creative[]` grouped by `platform` (use `getPlatformLabel`). Impressions per platform.
- DataTable: Creative Name, Platform chip, Spend, Impressions, Clicks, CTR (clicks/impressions — derived), CPM (spend*1000/impressions — derived), Reach. CSV filename `creatives`.

**Derived fields**: `payload.creative[]` rows have `name, platform, spend, impressions, clicks, conversions, reach`. Compute `ctr = clicks/impressions`, `cpm = (spend * 1000) / impressions` client-side.

---

### BudgetDashboard (`/dashboards/budget`)

Budget rows shape: `{ campaignName, spendToDate, budgetAmount, pacing_pct }`. Note: `budgetAmount` may be null for Meta campaigns.

**Data binding**:
- KPI strip (3 tiles): Total Spend to Date = sum(spendToDate); Total Budget = sum(budgetAmount || 0); Overall Pacing = sum(spendToDate) / sum(budgetAmount) where budgetAmount > 0.
- Paired DistributionBar: `payload.budget[]` where `budgetAmount > 0` mapped to paired bars — `{ label: campaignName, spend: spendToDate, budget: budgetAmount }`. Series = `[{key:'spend',label:'Spent',color:chartPalette[1]},{key:'budget',label:'Budget',color:'#e5e7eb'}]`.
- TrendLine: `payload.campaign.trend` cumulative sum vs budget ceiling. Compute cumulative spend per day client-side. Budget ceiling = horizontal `ReferenceLine` at `sum(budgetAmount)` value. Add `<ReferenceLine y={budgetTotal} stroke={chartPalette[5]} strokeDasharray="6 3" />` inside TrendLine.
- DataTable: Campaign, Platform, Spend, Budget (show `--` if null), Pacing %, Risk chip. CSV filename `budget`.

**B-BUDG-01 guard**: verify `budgetAvailability !== undefined` check is still in the file (A4 applied this). Do not remove.

---

## Definition of Done

- [ ] CampaignDashboard: 4 KpiTiles, TrendLine, DistributionBar, DataTable with platform chips
- [ ] CreativeDashboard: 4 KpiTiles, BubbleScatter, PieComposition, DataTable with derived CTR/CPM
- [ ] BudgetDashboard: 3 KpiTiles, paired DistributionBar, TrendLine with reference line, DataTable with risk chips
- [ ] All pages use `getPlatformLabel` from `platformLabels.ts`
- [ ] Loading and empty states for all pages
- [ ] Tests green for all 3 pages
- [ ] Lint clean and build clean

## Test deltas (per page)

CampaignDashboard:
```typescript
it('renders 4 KpiTiles', () => { ... })
it('renders TrendLine for campaign spend', () => { ... })
it('renders DistributionBar for top 10 campaigns', () => { ... })
it('DataTable platform chip uses getPlatformLabel', () => { ... })
```

CreativeDashboard:
```typescript
it('renders 4 KpiTiles from creative rows', () => { ... })
it('renders BubbleScatter with creative data', () => { ... })
it('CTR and CPM are derived client-side', () => { ... })
```

BudgetDashboard:
```typescript
it('renders 3 KpiTiles', () => { ... })
it('renders paired DistributionBar for spend vs budget', () => { ... })
it('skips rows where budgetAmount is 0 or null in paired bar', () => { ... })
it('budget reference line present in TrendLine', () => { ... })
```

## Out of scope

- Do NOT implement B-CAMP-01/B-CREA-01 row-level platform filter (deferred — API call is already scoped)
- Do NOT add campaign creation or edit functionality
