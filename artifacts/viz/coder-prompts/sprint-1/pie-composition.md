# PieComposition Component

**Sprint:** 1
**Estimated size:** S
**Depends on:** ChartSkeleton, AccessibleTableToggle
**Blocks:** Sprint 2–4 pages using pie/donut charts
**Role needed:** frontend-engineer

## Context

`PieComposition` renders pie or donut charts for composition/mix data — spend by objective, post type mix, channel cost mix, gender split, etc. Each segment uses both color and a cross-hatch SVG pattern for non-color a11y encoding. Center label shows the total value for donut mode.

## Inputs already in the repo (do not re-invent)

- `frontend/src/styles/chartTheme.ts`: `chartPalette` for segment colors.
- `frontend/src/components/viz/ChartSkeleton.tsx`: loading state.
- `frontend/src/components/viz/AccessibleTableToggle.tsx`: a11y table toggle.
- `frontend/src/components/EmptyState.tsx`: empty state.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/components/viz/PieComposition.tsx` (create)
  - `frontend/src/components/viz/__tests__/PieComposition.test.tsx` (create)

- **Props API**:

```typescript
type ChartValueType = 'currency' | 'number' | 'percent' | 'rate';

interface PieCompositionProps {
  data: Array<{ label: string; value: number; color?: string }>;
  innerRadius?: number; // 0 = pie, 60 = donut (default: 60)
  yFormat?: ChartValueType;
  currency?: string;
  showLegend?: boolean; // default: true
  height?: number; // default: 220
  isLoading?: boolean;
  emptyReasonCode?: string;
  className?: string;
}
```

- **Data binding**: `data` is an array of `{ label, value }`. Colors auto-assigned from `chartPalette` if not provided.

- **Interactions**: hover tooltip on segment shows label + value + percentage of total. Legend items toggle segment visibility (local state). Each legend item `role="checkbox"` `aria-checked`.

- **Empty/loading/error states**:
  - `isLoading=true`: `<ChartSkeleton variant="pie" height={height} />`
  - `data.length === 0` or `data.every(d => d.value === 0)`: `<EmptyState reasonCode={emptyReasonCode ?? 'no_data_for_range'} />`

- **A11y**:
  - Wrapped in `<AccessibleTableToggle>`. Table: Label, Value, Percentage columns.
  - Each segment has both color fill AND an SVG cross-hatch pattern on top (pattern at ~25% opacity).
  - Center label (donut mode): the total value, `aria-hidden="true"` (screen reader reads the table instead).

## Design

Recharts primitives:

```tsx
<PieChart height={height}>
  <defs>
    {chartPalette.map((color, i) => (
      <pattern key={i} id={`hatch-${i}`} patternUnits="userSpaceOnUse" width="6" height="6">
        <rect width="6" height="6" fill={color} />
        <path d="M0,6 L6,0" stroke="rgba(0,0,0,0.25)" strokeWidth="1.5" />
      </pattern>
    ))}
  </defs>
  <Pie
    data={data}
    dataKey="value"
    nameKey="label"
    innerRadius={innerRadius}
    outerRadius={80}
    isAnimationActive={false}
  >
    {data.map((entry, i) => (
      <Cell
        key={i}
        fill={entry.color ?? chartPalette[i % chartPalette.length]}
        // pattern applied via second Cell or opacity overlay
      />
    ))}
  </Pie>
  <Tooltip formatter={formatValue} />
  {showLegend && <Legend ... />}
</PieChart>
```

Center label for donut (innerRadius > 0): render an absolutely-positioned `<text>` element inside a `<svg>` overlay or use Recharts `<Label>` inside `<Pie>`:

```tsx
<Label
  value={formatValue(total, yFormat, currency)}
  position="center"
  style={{ fontSize: 14, fontWeight: 600 }}
/>
```

## Definition of Done

- [ ] Renders pie chart (innerRadius=0) and donut chart (innerRadius=60)
- [ ] Segment colors from `chartPalette` when not provided
- [ ] Cross-hatch pattern on each segment (visible in DOM as `<pattern>` in `<defs>`)
- [ ] Legend toggles segment visibility
- [ ] `isLoading=true` shows ChartSkeleton
- [ ] Empty/zero data shows EmptyState
- [ ] AccessibleTableToggle wraps chart
- [ ] jest-axe passes
- [ ] Tests green: `cd frontend && npm test -- --run src/components/viz/__tests__/PieComposition.test.tsx`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Test deltas

File: `frontend/src/components/viz/__tests__/PieComposition.test.tsx`

```typescript
import { render, screen } from '@testing-library/react'
import { axe } from 'jest-axe'
import { PieComposition } from '../PieComposition'

const mockData = [
  { label: 'Search', value: 5000 },
  { label: 'Display', value: 3000 },
  { label: 'Video', value: 2000 },
]

describe('PieComposition', () => {
  it('renders without errors', () => {
    const { container } = render(<PieComposition data={mockData} />)
    expect(container.querySelector('.recharts-pie')).toBeInTheDocument()
  })

  it('renders patterns in defs', () => {
    const { container } = render(<PieComposition data={mockData} />)
    expect(container.querySelectorAll('pattern').length).toBeGreaterThan(0)
  })

  it('shows ChartSkeleton when isLoading', () => {
    render(<PieComposition data={[]} isLoading />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('shows EmptyState when data is empty', () => {
    render(<PieComposition data={[]} emptyReasonCode="no_data_for_range" />)
    expect(screen.getByTestId('empty-state')).toHaveAttribute('data-reason-code', 'no_data_for_range')
  })

  it('has no a11y violations', async () => {
    const { container } = render(<PieComposition data={mockData} />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
```

## Out of scope

- Do NOT add click-to-drill-down
- Do NOT add animation (use `isAnimationActive={false}`)
- Do NOT render more than 10 segments — callers must pre-aggregate to top N + "Other"
