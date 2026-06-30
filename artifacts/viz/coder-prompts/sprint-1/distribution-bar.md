# DistributionBar Component

**Sprint:** 1
**Estimated size:** S
**Depends on:** ChartSkeleton, AccessibleTableToggle
**Blocks:** Sprint 2–4 pages using horizontal/vertical bar distributions
**Role needed:** frontend-engineer

## Context

`DistributionBar` is a horizontal (or vertical) bar chart for distribution and comparison data. Used for platform spend mix, age range distribution, top campaigns by spend, keywords by conversion, and spend-vs-budget paired bars. Supports both single-value bars (one value per category) and paired bars (two values per category — e.g., spend vs budget).

## Inputs already in the repo (do not re-invent)

- `frontend/src/styles/chartTheme.ts`: `chartPalette` for default bar colors.
- `frontend/src/components/viz/ChartSkeleton.tsx`: use for loading.
- `frontend/src/components/viz/AccessibleTableToggle.tsx`: wrap every chart.
- `frontend/src/components/EmptyState.tsx`: use for empty data.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/components/viz/DistributionBar.tsx` (create)
  - `frontend/src/components/viz/__tests__/DistributionBar.test.tsx` (create)

- **Props API**:

```typescript
type ChartValueType = 'currency' | 'number' | 'percent' | 'rate';
type BarLayout = 'horizontal' | 'vertical'; // default: 'horizontal' — bars extend right

interface DistributionBarSeries {
  key: string;
  label: string;
  color: string;
}

interface DistributionBarProps {
  // Simple mode: one value per category
  data: Array<{ label: string; value: number; color?: string }>;
  // Paired mode: pass series array + data with multiple keys
  series?: DistributionBarSeries[]; // if provided, renders grouped bars
  layout?: BarLayout;
  showPercent?: boolean; // show % label on each bar
  yFormat?: ChartValueType;
  currency?: string;
  height?: number; // default: 200
  maxItems?: number; // trim to top N items, default: no limit
  isLoading?: boolean;
  emptyReasonCode?: string;
  className?: string;
}
```

- **Data binding**: `data` is an array of `{ label, value }`. For paired bars, `series` is also provided and `data` items have additional keys matching `series[i].key`.

- **Interactions**: hover tooltip shows label + value. No click. Legend below chart when `series` is provided.

- **Empty/loading/error states**:
  - `isLoading=true`: `<ChartSkeleton variant="bar" height={height} />`
  - `data.length === 0`: `<EmptyState reasonCode={emptyReasonCode ?? 'no_data_for_range'} />`

- **A11y**: wrapped in `<AccessibleTableToggle>`. Table: columns are Label, Value (and one column per series in paired mode). Non-color encoding: use Recharts `Cell` with `patternId` from an `<SVGDefs>` block — implement simple diagonal-stripe patterns (`pattern1` through `pattern6` covering `chartPalette` indices). Each bar uses both a fill color and a pattern at 30% opacity on top.

## Design

Recharts primitives:

```tsx
// Simple mode
<BarChart data={data} layout={layout === 'horizontal' ? 'vertical' : 'horizontal'}>
  <XAxis type="number" tickFormatter={formatTick(yFormat)} />
  <YAxis type="category" dataKey="label" width={120} />
  <Tooltip formatter={...} />
  <Bar dataKey="value">
    {data.map((entry, i) => (
      <Cell key={i} fill={entry.color ?? chartPalette[i % chartPalette.length]} />
    ))}
  </Bar>
</BarChart>

// Paired mode: render one <Bar> per series, each with a distinct color
```

Note: Recharts `layout` prop on `BarChart` is `"vertical"` for what the user perceives as "horizontal bars" (category on Y axis, value on X axis). This is the default for `DistributionBar` since category labels are typically long.

Percentage labels: when `showPercent=true`, compute `pct = value / sum(all values)` and render as `<LabelList position="right" formatter={v => `${pct.toFixed(0)}%`} />`.

## Definition of Done

- [ ] Renders single-value horizontal bars correctly
- [ ] Renders paired (grouped) bars when `series` provided
- [ ] `showPercent=true` appends percentage label to each bar
- [ ] `isLoading=true` shows ChartSkeleton
- [ ] Empty data shows EmptyState
- [ ] AccessibleTableToggle wraps the chart
- [ ] Non-color pattern encoding applied via SVG patterns
- [ ] jest-axe passes
- [ ] Tests green: `cd frontend && npm test -- --run src/components/viz/__tests__/DistributionBar.test.tsx`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Test deltas

File: `frontend/src/components/viz/__tests__/DistributionBar.test.tsx`

```typescript
import { render, screen } from '@testing-library/react'
import { axe } from 'jest-axe'
import { DistributionBar } from '../DistributionBar'

const mockData = [
  { label: 'Meta', value: 5000 },
  { label: 'Google', value: 3000 },
]

describe('DistributionBar', () => {
  it('renders without errors', () => {
    const { container } = render(<DistributionBar data={mockData} />)
    expect(container.firstChild).toBeInTheDocument()
  })

  it('shows ChartSkeleton when isLoading', () => {
    render(<DistributionBar data={[]} isLoading />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('shows EmptyState when data is empty', () => {
    render(<DistributionBar data={[]} emptyReasonCode="no_data_for_range" />)
    expect(screen.getByTestId('empty-state')).toHaveAttribute('data-reason-code', 'no_data_for_range')
  })

  it('renders AccessibleTableToggle', () => {
    render(<DistributionBar data={mockData} />)
    expect(screen.getByRole('button', { name: /table/i })).toBeInTheDocument()
  })

  it('has no a11y violations', async () => {
    const { container } = render(<DistributionBar data={mockData} />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
```

## Out of scope

- Do NOT implement a scrollable chart for > 20 items — use `maxItems` to trim
- Do NOT add click-to-filter behavior
- Do NOT add animation (use `isAnimationActive={false}`)
