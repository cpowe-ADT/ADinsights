# Google Ads Pacing Tab — Visualization Upgrade

**Sprint:** 3
**Estimated size:** M
**Depends on:** sprint-1/\* (all kit components)
**Blocks:** none
**Role needed:** frontend-engineer

## Context

The Pacing tab in the Google Ads workspace. Endpoint: `GET /api/google-ads/budget-pacing/`. Shows a gauge ring (RadialBarChart), KPI strip, spend-vs-budget bar, and a campaigns budget table. A4 patch B7 applied (scope params on all fetches including budget page).

## Inputs already in the repo (do not re-invent)

- Pacing endpoint response fields (verified from sprint plan): `spend_mtd, budget_month, forecast_month_end, over_under, pacing_pct, overspend_risk, underdelivery`
- Campaign budget rows: `campaign_id, campaign_name, campaign_status, channel_type, spend, budget_amount, pacing_pct`
- All Sprint 1 viz components.
- `frontend/src/styles/chartTheme.ts`: `chartPalette[5]` = `#f43f5e` (red for overspend); `chartPalette[3]` = `#10b981` (green for on-track).

## Deliverable

- **File(s) to create/modify**: identify the Pacing tab component and modify it. A4 patch B7 references `GoogleAdsBudgetPage` — find that file.

- **Data binding**:
  - Gauge ring: `RadialBarChart` single bar with `pacing.pacing_pct` value. Domain [0, 1.2] (to show 120% scale). Reference lines at 0.8 (yellow underdelivery zone) and 1.1 (red overspend zone). Fill color: `pacing_pct < 0.8 ? chartPalette[5] : pacing_pct > 1.1 ? chartPalette[5] : chartPalette[3]`.
  - KPI strip (3 tiles): Spend MTD = `pacing.spend_mtd` (currency); Budget Month = `pacing.budget_month` (currency); Forecast Month-End = `pacing.forecast_month_end` (currency).
  - DistributionBar (paired): campaign_rows mapped to paired bars — `series=[{key:'spend',label:'Spent',color:chartPalette[1]},{key:'budget_amount',label:'Budget',color:'#e5e7eb'}]`. Filter out rows where `budget_amount === 0 || budget_amount === null`.
  - DataTable: Campaign, Status chip, Spend, Budget, Forecast (spend \* (days_in_month / days_elapsed)), Over/Under, Risk chip. CSV export filename `google-ads-pacing`.

- **Risk chip**: `pacing_pct > 1.1` → `<span class="bg-red-100 text-red-800">At Risk</span>`; `pacing_pct < 0.8` → `<span class="bg-yellow-100 text-yellow-800">Under</span>`; else → `<span class="bg-green-100 text-green-800">On Track</span>`.

- **Gauge ring implementation**:

```tsx
import { RadialBarChart, RadialBar, PolarAngleAxis, ResponsiveContainer } from 'recharts'

const gaugeData = [{ value: pacing.pacing_pct, fill: fillColor }]

<ResponsiveContainer width="100%" height={200}>
  <RadialBarChart
    innerRadius="60%"
    outerRadius="90%"
    data={gaugeData}
    startAngle={180}
    endAngle={-180 * pacing.pacing_pct}  // proportional sweep
  >
    <PolarAngleAxis type="number" domain={[0, 1.2]} tick={false} />
    <RadialBar dataKey="value" background={{ fill: '#e5e7eb' }} />
  </RadialBarChart>
</ResponsiveContainer>
// Add reference line annotations as SVG overlays or text
```

Note: Recharts RadialBarChart does not have native reference lines. Add red zone indicator as a text annotation: `> 110%` label on the gauge arc.

## Design

```
┌────────────────────────────────────────────────────────┐
│    [Gauge Ring: MTD Pacing %]     [Spend] [Budget] [Forecast] │
│    e.g., 87% — On Track          ← KPI tiles to right  │
├────────────────────────────────────────────────────────┤
│ DistributionBar: Spend vs Budget per campaign (paired) │  ← height=200
├────────────────────────────────────────────────────────┤
│ DataTable: Campaign | Status | Spend | Budget | Risk   │  ← CSV: google-ads-pacing
└────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] Gauge ring renders with `RadialBarChart`, color reflects pacing status
- [ ] 3 KpiTiles (Spend MTD, Budget Month, Forecast)
- [ ] Paired DistributionBar (spend vs budget per campaign)
- [ ] DataTable with risk chips
- [ ] Loading and empty states
- [ ] Tests green
- [ ] Lint clean and build clean

## Test deltas

```typescript
it('renders gauge ring via RadialBarChart', () => {
  const { container } = render(<PacingTab data={mockPacing} />)
  expect(container.querySelector('.recharts-radial-bar-chart')).toBeInTheDocument()
})
it('renders 3 KpiTiles for spend/budget/forecast', () => { ... })
it('renders paired DistributionBar for campaigns', () => { ... })
it('DataTable shows risk chips based on pacing_pct', () => { ... })
```

## Out of scope

- Do NOT add interactive budget editing
- Do NOT add forecast model controls
