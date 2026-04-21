# Audience Dashboard — Visualization Upgrade

**Sprint:** 4
**Estimated size:** M
**Depends on:** sprint-1/* (all kit components)
**Blocks:** none
**Role needed:** frontend-engineer

## Context

`AudienceDashboard` at `/dashboards/audience` shows audience demographics: age distribution, gender split, device mix, and age×gender cross-tab. Data comes from `payload.platforms` slice of `/api/metrics/combined/`. A4 patch B-AUD-01 (zero-row EmptyState guard) is applied.

## Inputs already in the repo (do not re-invent)

- `frontend/src/routes/AudienceDashboard.tsx`: existing file. B-AUD-01 applied.
- Audience data shape from `payload.platforms`:
```typescript
{
  byAge: Array<{ ageRange: string; reach: number; impressions: number; spend: number }>
  byGender: Array<{ gender: string; reach: number; impressions: number; spend: number }>
  byAgeGender: Array<{ ageRange: string; gender: string; reach: number; impressions: number; spend: number }>
  byDevice: Array<{ device: string; impressions: number; clicks: number; spend: number }>
  byPlatform: Array<{ platform: string; ... }>
}
```
- All Sprint 1 viz components.
- `frontend/src/lib/platformLabels.ts`.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/routes/AudienceDashboard.tsx` (modify)
  - `frontend/src/routes/__tests__/AudienceDashboard.test.tsx` (modify or create)

- **Data binding**:
  - KPI strip (4 tiles):
    - Total Reach = `payload.metrics.reach`
    - Avg Frequency = `payload.metrics.frequency`
    - Top Age Range = `byAge[]` entry with max reach → `ageRange` label
    - Top Device = `byDevice[]` entry with max impressions → `device` label
  - Age distribution `DistributionBar`: `byAge[]` mapped to `{ label: row.ageRange, value: row.reach }`. Horizontal layout.
  - Gender split `PieComposition`: `byGender[]` mapped to `{ label: row.gender, value: row.reach }`.
  - Device mix `DistributionBar`: `byDevice[]` mapped to `{ label: row.device, value: row.impressions }`. Horizontal layout.
  - Age × Gender grouped bar: `byAgeGender[]` as grouped `DistributionBar` — age on categories (Y axis), gender as series. Data transformation:
    ```typescript
    const genders = [...new Set(byAgeGender.map(r => r.gender))]
    const ageGroups = [...new Set(byAgeGender.map(r => r.ageRange))]
    const chartData = ageGroups.map(age => {
      const row: Record<string, string | number> = { label: age }
      genders.forEach(g => {
        const match = byAgeGender.find(r => r.ageRange === age && r.gender === g)
        row[g] = match?.reach ?? 0
      })
      return row
    })
    const series = genders.map((g, i) => ({ key: g, label: g, color: chartPalette[i % chartPalette.length] }))
    ```
    Render as `DistributionBar` with `series={series}` and `data={chartData}`. If grouped bar has > 8 age groups, wrap in a `div` with `overflow-x: auto` and set a minimum width of `600px` on the chart.

- **Empty/loading/error states**:
  - `byAge.length === 0 && byGender.length === 0`: `EmptyState reasonCode="no_data_for_scope"`.
  - Each block independently shows `ChartSkeleton` while loading.

## Design

```
┌────────────────────────────────────────────────────────┐
│ [Total Reach] [Avg Freq] [Top Age] [Top Device]        │  ← 4 KpiTiles
├──────────────────────────────┬─────────────────────────┤
│ Age Reach (DistBar horiz.)   │ Gender Split (Pie)      │  ← 60/40
├──────────────────────────────┴─────────────────────────┤
│ Device Mix (DistBar horiz.)                            │
├────────────────────────────────────────────────────────┤
│ Age × Gender grouped DistBar (scrollable if needed)    │  ← access: table toggle
└────────────────────────────────────────────────────────┘
```

## Definition of Done

- [ ] 4 KpiTiles (Reach, Frequency, Top Age, Top Device)
- [ ] Age distribution DistributionBar
- [ ] Gender split PieComposition
- [ ] Device mix DistributionBar
- [ ] Age × Gender grouped DistributionBar (with scrollable wrapper if > 8 groups)
- [ ] All charts wrapped in AccessibleTableToggle
- [ ] `EmptyState reasonCode="no_data_for_scope"` when byAge + byGender both empty
- [ ] Loading skeletons for all blocks
- [ ] Tests green: `cd frontend && npm test -- --run src/routes/__tests__/AudienceDashboard.test.tsx`
- [ ] Lint clean and build clean

## Test deltas

```typescript
it('renders 4 KpiTiles', () => { ... })
it('renders age DistributionBar', () => { ... })
it('renders gender PieComposition', () => { ... })
it('renders device DistributionBar', () => { ... })
it('renders age×gender grouped DistributionBar', () => { ... })
it('age×gender data transformation produces correct series', () => {
  // Unit test the transformation function directly
  const result = transformAgeGender(mockByAgeGender)
  expect(result.series.map(s => s.key)).toContain('MALE')
  expect(result.chartData[0]).toHaveProperty('MALE')
})
it('shows EmptyState when no audience data', () => { ... })
it('shows scroll wrapper when age groups > 8', () => {
  // render with > 8 age groups, assert overflow-x: auto wrapper
})
```

## Out of scope

- Do NOT implement a true heatmap (requires custom SVG or a new chart library) — use grouped DistributionBar
- Do NOT add interest category data
- Do NOT add lookalike audience controls
