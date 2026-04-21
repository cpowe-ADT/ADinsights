# Platforms Dashboard — Visualization Upgrade

**Sprint:** 4
**Estimated size:** M
**Depends on:** sprint-1/* (all kit components)
**Blocks:** none
**Role needed:** frontend-engineer

## Context

`PlatformDashboard` at `/dashboards/platforms` is the combined cross-platform analytics page. Shows both Meta and Google Ads data side by side. A4 patches B-PLAT-01 (stale-platform guard) and B-PLAT-02 (empty byPlatform EmptyState) are applied. B-PLAT-03 (hardcoded `facebook`/`instagram` labels) must be fixed in this sprint as part of the platform label normalization work.

## Inputs already in the repo (do not re-invent)

- `frontend/src/routes/PlatformDashboard.tsx`: existing file. A4 patches applied.
- `frontend/src/stores/useDashboardStore*`: `platforms.data` slice with `{ byPlatform[], byDevice[], byPlatformDevice[], byAge[], byGender[], byAgeGender[] }`.
- All Sprint 1 viz components.
- `frontend/src/styles/chartTheme.ts`: `PLATFORM_CHART_TOKENS` — `meta_ads: '#2563eb'`, `google_ads: '#f97316'`.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/routes/PlatformDashboard.tsx` (modify)
  - `frontend/src/lib/platformLabels.ts` (create — new helper)
  - `frontend/src/routes/__tests__/PlatformDashboard.test.tsx` (modify)

### platformLabels.ts (create this file)

```typescript
// frontend/src/lib/platformLabels.ts
export const PLATFORM_DISPLAY_LABELS: Record<string, string> = {
  facebook: 'Meta (Facebook)',
  instagram: 'Meta (Instagram)',
  meta_ads: 'Meta Ads',
  google_ads: 'Google Ads',
  audience_network: 'Audience Network',
  messenger: 'Messenger',
  SEARCH: 'Search',
  DISPLAY: 'Display',
  VIDEO: 'Video',
  SHOPPING: 'Shopping',
  PERFORMANCE_MAX: 'PMax',
}

export function getPlatformLabel(raw: string): string {
  return PLATFORM_DISPLAY_LABELS[raw] ?? raw
}

export function getPlatformColor(raw: string): string {
  if (raw === 'facebook' || raw === 'instagram' || raw === 'meta_ads') {
    return '#2563eb'
  }
  if (raw === 'google_ads' || raw === 'SEARCH' || raw === 'DISPLAY') {
    return '#f97316'
  }
  return '#0ea5e9'
}
```

- **Data binding**:
  - KPI strip (5 tiles): `payload.metrics.spend`, `payload.metrics.impressions`, `payload.metrics.clicks`, `payload.metrics.conversions`, ROAS = `conversion_value / spend` (derived client-side if not in payload).
  - Stacked area TrendLine: `payload.campaign.trend` split by `platform` field. For each unique platform in trend rows, create one series. If `platform` field absent from trend rows, fall back to a single total-spend line. Use `variant="stacked-area"` on TrendLine. Platform colors from `getPlatformColor()`.
  - Small-multiples (2×2 grid): 4 `DistributionBar` components in a CSS grid. Each shows Meta vs Google Ads split for one metric: Spend / Impressions / Clicks / Conversions. Data from `payload.platforms.byPlatform[]` with `getPlatformLabel()` applied to labels.
  - DataTable: `payload.platforms.byPlatform[]` columns — Platform (label from `getPlatformLabel`), Spend, Impressions, Clicks, Conversions, CTR (clicks/impressions), CPM (spend/impressions*1000), ROAS. CSV export filename `platforms`.

- **B-PLAT-03 fix**: replace all hardcoded `platform === 'facebook'` checks in the `kpis` useMemo with `getPlatformLabel(p.platform)` normalization from `platformLabels.ts`. Also normalize all chart labels.

- **account_id filtered**: when account selected — stacked area shows selected account's platform split + faded peer average computed from median per-platform spend across all accounts.

## Design

```
┌────────────────────────────────────────────────────────┐
│ [Spend] [Impressions] [Clicks] [Conv] [ROAS]           │  ← 5 KpiTiles
├────────────────────────────────────────────────────────┤
│ Stacked Area TrendLine: Meta spend (blue) + Google (orange)│  ← height=260
├───────────────────────┬────────────────────────────────┤
│ DistBar: Spend split  │ DistBar: Impressions split     │  ← 2×2 small multiples
│ DistBar: Clicks split │ DistBar: Conv split            │
├───────────────────────┴────────────────────────────────┤
│ DataTable: Platform | Spend | Impressions | CTR | ROAS │  ← CSV: platforms
└────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] `platformLabels.ts` created with `getPlatformLabel` and `getPlatformColor`
- [ ] B-PLAT-03 fixed: no hardcoded `'facebook'`/`'instagram'` strings in KPI computation
- [ ] 5 KpiTiles
- [ ] Stacked area TrendLine shows Meta + Google series
- [ ] 2×2 small-multiples grid with 4 DistributionBar charts
- [ ] DataTable with platform rows and normalized labels
- [ ] Loading and empty states (B-PLAT-02 already applied — verify)
- [ ] Tests green
- [ ] Lint clean and build clean

## Test deltas

```typescript
import { getPlatformLabel, getPlatformColor } from '../../lib/platformLabels'

describe('platformLabels', () => {
  it('normalizes facebook to Meta (Facebook)', () => {
    expect(getPlatformLabel('facebook')).toBe('Meta (Facebook)')
  })
  it('returns raw value for unknown platform', () => {
    expect(getPlatformLabel('tiktok')).toBe('tiktok')
  })
})

describe('PlatformDashboard', () => {
  it('renders 5 KpiTiles', () => { ... })
  it('renders stacked area TrendLine', () => { ... })
  it('renders 4 DistributionBar small multiples', () => { ... })
  it('DataTable uses getPlatformLabel for platform column', () => { ... })
  it('shows EmptyState with reasonCode="no_data_for_scope" when byPlatform empty', () => { ... })
})
```

## Out of scope

- Do NOT modify `useDashboardStore` platform slice selectors
- Do NOT add platform toggle controls (those are in the FilterBar, not this page)
