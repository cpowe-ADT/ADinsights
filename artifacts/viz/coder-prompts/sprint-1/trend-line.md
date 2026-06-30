# TrendLine Component

**Sprint:** 1
**Estimated size:** M
**Depends on:** ChartSkeleton, AccessibleTableToggle
**Blocks:** all Sprint 2–4 pages with trend charts
**Role needed:** frontend-engineer

## Context

`TrendLine` is the primary time-series chart. Used on nearly every dashboard page for spend, CTR, sessions, clicks over time. Supports single-series, multi-series (one per account or platform), dual-Y-axis mode, stacked area mode, and an optional peer-average faded dashed line. Renders Recharts `LineChart` or `AreaChart` with full a11y table toggle.

## Inputs already in the repo (do not re-invent)

- `frontend/src/styles/chartTheme.ts`: `chartPalette` array for series colors. Import and use for `series[i].color` defaults.
- `frontend/src/components/viz/ChartSkeleton.tsx`: use when `isLoading=true`.
- `frontend/src/components/viz/AccessibleTableToggle.tsx`: wrap every chart.
- `frontend/src/components/EmptyState.tsx`: use for no-data state with `reasonCode` prop.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/components/viz/TrendLine.tsx` (create)
  - `frontend/src/components/viz/__tests__/TrendLine.test.tsx` (create)

- **Props API**:

```typescript
type ChartValueType = 'currency' | 'number' | 'percent' | 'rate';
type TrendVariant = 'line' | 'stacked-area'; // default: 'line'

interface TrendLineSeries {
  key: string;
  label: string;
  color: string;
  dashed?: boolean; // strokeDasharray="4 2" — non-color secondary encoding for a11y
  yAxisId?: 'left' | 'right'; // for dual-axis mode
}

interface TrendLineProps {
  data: Array<{ date: string; [key: string]: number | string }>;
  series: TrendLineSeries[];
  peerData?: Array<{ date: string; value: number }>; // renders as faded dashed peer avg line
  variant?: TrendVariant;
  yFormat?: ChartValueType;
  rightYFormat?: ChartValueType; // enables dual-Y-axis when provided
  currency?: string;
  height?: number; // default: 260
  isLoading?: boolean;
  emptyReasonCode?: string;
  onPointClick?: (date: string) => void;
  className?: string;
}
```

- **Data binding**: `data` is an array of objects where each object has a `date` key plus one key per series matching `series[i].key`. Example: `[{ date: '2026-01-01', spend_meta: 1000, spend_google: 800 }]`.

- **Interactions**:
  - Legend items toggle individual series visibility (local state). Each legend item has `role="checkbox"` and `aria-checked`.
  - Hover tooltip shows all active series values at the hovered date point.
  - Click on a data point fires `onPointClick(date)` if provided.
  - Keyboard: arrow keys navigate between data points when the chart is focused (Recharts handles this natively; ensure chart has `tabIndex={0}`).

- **Empty/loading/error states**:
  - `isLoading=true`: `<ChartSkeleton variant="line" height={height} />`
  - `data.length === 0 || series.length === 0`: `<EmptyState reasonCode={emptyReasonCode ?? 'no_data_for_range'} />`

- **A11y**: wrapped in `<AccessibleTableToggle>`. Table columns: Date + one column per series + optional Peer Average. `<th scope="col">` headers. Chart root `tabIndex={0}` for keyboard navigation.

## Design

Recharts primitives:

```tsx
// Line variant
<LineChart data={data} height={height}>
  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
  <XAxis dataKey="date" ... />
  <YAxis yAxisId="left" tickFormatter={formatTick(yFormat)} />
  {rightYFormat && <YAxis yAxisId="right" orientation="right" tickFormatter={formatTick(rightYFormat)} />}
  <Tooltip content={<CustomTooltip />} />
  <Legend content={<CustomLegend onToggle={...} />} />
  {series.map(s => (
    <Line
      key={s.key}
      yAxisId={s.yAxisId ?? 'left'}
      type="monotone"
      dataKey={s.key}
      stroke={s.color}
      strokeDasharray={s.dashed ? '4 2' : undefined}
      dot={false}
      hide={hiddenSeries.has(s.key)}
    />
  ))}
  {peerData && (
    <Line
      data={peerData}
      dataKey="value"
      stroke="rgba(148,163,184,0.5)"
      strokeDasharray="6 3"
      dot={false}
      name="Peer Average"
    />
  )}
</LineChart>

// Stacked area variant: replace LineChart → AreaChart, Line → Area with stackId="a"
```

Platform color tokens from `chartTheme.ts` (add these constants to `chartTheme.ts` as part of this ticket):

```typescript
export const PLATFORM_CHART_TOKENS = {
  meta_ads: '#2563eb', // chartPalette[0]
  google_ads: '#f97316', // chartPalette[1]
  peer_avg: 'rgba(148,163,184,0.5)',
};
```

## Definition of Done

- [ ] Renders multi-series line chart with legend
- [ ] Legend toggle hides/shows individual series (`aria-checked` updates)
- [ ] Dual Y-axis renders when `rightYFormat` provided
- [ ] Stacked area renders when `variant="stacked-area"`
- [ ] Peer average faded dashed line renders when `peerData` provided
- [ ] `isLoading=true` shows ChartSkeleton (no chart)
- [ ] Empty data shows EmptyState with correct reasonCode
- [ ] `AccessibleTableToggle` wraps the chart — table toggles correctly
- [ ] `PLATFORM_CHART_TOKENS` exported from `chartTheme.ts`
- [ ] jest-axe passes
- [ ] Tests green: `cd frontend && npm test -- --run src/components/viz/__tests__/TrendLine.test.tsx`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Test deltas

File: `frontend/src/components/viz/__tests__/TrendLine.test.tsx`

```typescript
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'jest-axe'
import { TrendLine } from '../TrendLine'

const series = [{ key: 'spend', label: 'Spend', color: '#2563eb' }]
const data = [
  { date: '2026-01-01', spend: 1000 },
  { date: '2026-01-02', spend: 1200 },
]
const peerData = [
  { date: '2026-01-01', value: 900 },
  { date: '2026-01-02', value: 950 },
]

describe('TrendLine', () => {
  it('renders without errors', () => {
    render(<TrendLine data={data} series={series} />)
    expect(screen.getByRole('img')).toBeInTheDocument() // chart wrapper
  })

  it('shows ChartSkeleton when isLoading', () => {
    render(<TrendLine data={[]} series={series} isLoading />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('shows EmptyState when data is empty', () => {
    render(<TrendLine data={[]} series={series} emptyReasonCode="no_data_for_range" />)
    expect(screen.getByTestId('empty-state')).toHaveAttribute('data-reason-code', 'no_data_for_range')
  })

  it('renders AccessibleTableToggle', () => {
    render(<TrendLine data={data} series={series} />)
    expect(screen.getByRole('button', { name: /table/i })).toBeInTheDocument()
  })

  it('peer average line is rendered when peerData provided', () => {
    const { container } = render(<TrendLine data={data} series={series} peerData={peerData} />)
    // The peer line uses stroke rgba(148,163,184,0.5) — verify via path count
    const paths = container.querySelectorAll('.recharts-line path')
    expect(paths.length).toBeGreaterThanOrEqual(2)
  })

  it('has no a11y violations', async () => {
    const { container } = render(<TrendLine data={data} series={series} />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
```

## Out of scope

- Do NOT implement client-side peer-average computation here — callers pass `peerData` pre-computed
- Do NOT add a zoom/brush control
- Do NOT change chart height based on window size (fixed height prop)
- Do NOT add animation (use `isAnimationActive={false}` on all series to prevent test flicker)
