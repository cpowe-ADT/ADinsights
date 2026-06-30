# Parish Map Detail — Visualization Upgrade

**Sprint:** 4
**Estimated size:** M
**Depends on:** sprint-1/kpi-tile.md, sprint-1/data-table.md, sprint-1/sparkline.md, sprint-1/chart-skeleton.md
**Blocks:** none
**Role needed:** frontend-engineer (Leaflet experience recommended)

## Context

`ParishMapDetail` at `/dashboards/map` renders a Leaflet choropleth map of Jamaica's 14 parishes with KPI overlay. Data: `payload.parish[]` from `/api/metrics/combined/` + GeoJSON from `GET /api/parish-geometry/`. Leaflet is already installed (`leaflet ^1.9.4`). Sparkline in map tooltip is suppressed (no parish daily series endpoint). B-MAP-02 (EmptyState) is already applied.

## Inputs already in the repo (do not re-invent)

- `frontend/src/routes/ParishMapDetail.tsx`: existing file. B-MAP-02 applied.
- `frontend/src/stores/useDashboardStore*`: `parish` slice.
- Parish row fields: `{ parish: string; spend: number; impressions: number; clicks: number; conversions: number }`.
- GeoJSON: `{ type: 'FeatureCollection', features: [{ type: 'Feature', properties: { name: string }, geometry: {...} }] }` — join on `feature.properties.name === row.parish`.
- All Sprint 1 viz components.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/routes/ParishMapDetail.tsx` (modify)
  - `frontend/src/routes/__tests__/ParishMapDetail.test.tsx` (modify or create)

- **Data binding**:
  - KPI strip (4 tiles): Total Spend (sum), Top Parish (parish with max spend), Top Parish Spend, Parish Coverage % = (parishes with spend > 0 / 14) \* 100.
  - KPI picker `<select>`: Spend / Impressions / Clicks / Conversions — controls which metric fills the choropleth. Client-side state only.
  - Choropleth: Leaflet `GeoJSON` layer with `style` function. For each feature, look up parish row by `feature.properties.name`. Fill color: 5-bucket sequential scale using `chartPalette[0]` (#2563eb) at 5 alpha steps (0.15, 0.30, 0.50, 0.70, 0.95). Compute buckets as quintiles of the metric values across all parishes.
  - Popup on hover: `feature.properties.name`, all 4 KPI values, `[/* Sparkline: [NEW-ENDPOINT] /api/metrics/combined/?group_by=parish&group_id={id} - not yet implemented */]`.
  - DataTable: Parish, Spend, Impressions, Clicks, Conversions. Row click highlights corresponding map polygon (set Leaflet layer style to a highlighted border). CSV export filename `parishes`.

- **Platform toggle (B-MAP-01 deferred)**: when platform filter changes, force re-render of the entire Leaflet GeoJSON layer by changing its React `key` prop. Example: `<GeoJSON key={filters.platforms.join('-')} .../>`. This is the workaround for the Leaflet layer-not-updating-on-filter-change bug.

- **Interactions**:
  - KPI picker change → recompute choropleth fill metric (client-side, no new fetch).
  - Hover → Leaflet popup with parish name + KPI values.
  - DataTable row click → highlight the corresponding polygon via Leaflet layer.

- **Empty/loading/error states**:
  - GeoJSON not loaded: render `ChartSkeleton variant="line" height={400}` (no variant exists for map — use line as placeholder).
  - `payload.parish.length === 0`: `EmptyState reasonCode="no_data_for_scope"` (B-MAP-02 applied).
  - Loading: KPI strip shows `ChartSkeleton variant="kpi-strip"`.

- **A11y**: Map is not keyboard-navigable in Leaflet. The `DataTable` below provides the accessible equivalent. Add `aria-label="Jamaica parish map. Use the table below for accessible data."` on the Leaflet container div.

## Design

```
┌────────────────────────────────────────────────────────┐
│ [Total Spend] [Top Parish] [Top Spend] [Coverage %]    │  ← 4 KpiTiles
├────────────────────────────────────────────────────────┤
│ Metric: [Spend ▼]   Leaflet choropleth (14 parishes)  │  ← height=400
│ (blue sequential palette, hover=popup)                 │
├────────────────────────────────────────────────────────┤
│ DataTable: Parish | Spend | Impressions | Clicks | Conv│  ← row click highlights map
└────────────────────────────────────────────────────────┘
```

Choropleth color scale (5 buckets):

```typescript
const alphaSteps = [0.15, 0.3, 0.5, 0.7, 0.95];
// Bucket index 0–4 based on quintile rank of metric value
// Fill: `rgba(37, 99, 235, ${alphaSteps[bucketIndex]})`
```

## Definition of Done

- [ ] 4 KpiTiles render
- [ ] KPI picker dropdown changes choropleth metric
- [ ] Leaflet choropleth renders with 5-step alpha scale
- [ ] Parish hover shows popup with 4 KPI values
- [ ] DataTable row click highlights map polygon
- [ ] `key` prop on GeoJSON layer forces re-render on platform filter change
- [ ] Sparkline in popup suppressed with `[NEW-ENDPOINT]` comment
- [ ] `aria-label` on map container div
- [ ] DataTable provides accessible equivalent
- [ ] `EmptyState reasonCode="no_data_for_scope"` when parish data empty
- [ ] Tests green: `cd frontend && npm test -- --run src/routes/__tests__/ParishMapDetail.test.tsx`
- [ ] Lint clean and build clean

## Test deltas

Note: Leaflet requires a mock in vitest. Add `vi.mock('leaflet')` or use `jsdom` with a `ResizeObserver` mock.

```typescript
// In vitest setup: mock Leaflet to avoid canvas errors
vi.mock('leaflet', () => ({
  default: {
    map: vi.fn(() => ({ setView: vi.fn().mockReturnThis(), remove: vi.fn() })),
    tileLayer: vi.fn(() => ({ addTo: vi.fn() })),
    geoJSON: vi.fn(() => ({ addTo: vi.fn(), setStyle: vi.fn(), eachLayer: vi.fn() })),
  }
}))

it('renders 4 KpiTiles', () => { ... })
it('KPI picker select has 4 options', () => { ... })
it('DataTable renders parish rows', () => { ... })
it('shows EmptyState when parish data empty', () => { ... })
it('map container has aria-label', () => {
  expect(screen.getByLabelText(/jamaica parish map/i)).toBeInTheDocument()
})
```

## Out of scope

- Do NOT add a heat-scale legend (tooltip suffices)
- Do NOT implement per-parish sparkline (no endpoint)
- Do NOT fix B-MAP-01 Leaflet platform toggle lag beyond the `key` prop workaround

## Open questions resolved

- **OQ-9/OQ-10 (Sparkline in map tooltip — no daily series)**: CONFIRMED NO ENDPOINT for parish daily time series in `/api/metrics/combined/`. Sparkline suppressed. `[NEW-ENDPOINT]` comment added.
