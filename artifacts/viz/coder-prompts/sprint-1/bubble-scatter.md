# BubbleScatter Component

**Sprint:** 1
**Estimated size:** M
**Depends on:** ChartSkeleton, AccessibleTableToggle
**Blocks:** meta-insights (Sprint 2), google-ads-campaigns (Sprint 3), google-ads-search (Sprint 3), creatives (Sprint 4)
**Role needed:** frontend-engineer

## Context

`BubbleScatter` renders a scatter/bubble chart where each point encodes four dimensions: X position, Y position, bubble size (Z), and optionally shape (circle vs triangle). Used for campaigns-by-ROAS-vs-spend, keywords quality-score-vs-CPC, creatives-by-CTR-vs-impressions. Shape encoding (`circle` vs `triangle`) is required for WCAG non-color encoding.

## Inputs already in the repo (do not re-invent)

- `frontend/src/styles/chartTheme.ts`: `chartPalette` for bubble colors.
- `frontend/src/components/viz/ChartSkeleton.tsx`: loading state.
- `frontend/src/components/viz/AccessibleTableToggle.tsx`: a11y table toggle.
- `frontend/src/components/EmptyState.tsx`: empty state.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/components/viz/BubbleScatter.tsx` (create)
  - `frontend/src/components/viz/__tests__/BubbleScatter.test.tsx` (create)

- **Props API**:
```typescript
type ChartValueType = 'currency' | 'number' | 'percent' | 'rate'

interface BubblePoint {
  id: string
  label: string
  x: number
  y: number
  z: number           // maps to bubble radius (clamped to min 4, max 40 px)
  shape?: 'circle' | 'triangle'   // default: 'circle'
  color?: string      // defaults to chartPalette[0]
}

interface BubbleScatterProps {
  data: BubblePoint[]
  xLabel: string
  yLabel: string
  zLabel: string      // shown in tooltip as size dimension label
  xFormat?: ChartValueType
  yFormat?: ChartValueType
  currency?: string
  height?: number     // default: 300
  isLoading?: boolean
  emptyReasonCode?: string
  onBubbleClick?: (id: string) => void
  className?: string
}
```

- **Data binding**: caller maps endpoint rows to `BubblePoint[]`. Z values must be normalized client-side to a useful range before passing in (the component clamps Z to a pixel radius but does NOT do data normalization — that is the caller's responsibility).

- **Interactions**:
  - Hover tooltip shows `label`, formatted `x`, formatted `y`, formatted `z` (with `zLabel`).
  - Click on bubble fires `onBubbleClick(id)` if provided; cursor: pointer when handler present.
  - Keyboard: chart has `tabIndex={0}`. Recharts `ScatterChart` does not provide native keyboard navigation — implement a `data-focusable` pattern: each bubble has `tabIndex` and handles `Enter`/`Space` as click.

- **Empty/loading/error states**:
  - `isLoading=true`: `<ChartSkeleton variant="bubble" height={height} />`
  - `data.length === 0`: `<EmptyState reasonCode={emptyReasonCode ?? 'no_data_for_range'} />`

- **A11y**:
  - Wrapped in `<AccessibleTableToggle>`. Table columns: Label, X (xLabel), Y (yLabel), Size (zLabel).
  - Each bubble uses color AND shape encoding. For `shape='triangle'`, render via a custom Recharts `shape` prop on `<Scatter>`:

```tsx
const TriangleShape = (props) => {
  const { cx, cy, r } = props
  const h = r * Math.sqrt(3)
  return <polygon points={`${cx},${cy-r*0.8} ${cx-r*0.7},${cy+h*0.5} ${cx+r*0.7},${cy+h*0.5}`} fill={props.fill} />
}
// Circles use default Recharts rendering
```

## Design

Recharts primitives:
```tsx
<ScatterChart height={height}>
  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
  <XAxis dataKey="x" type="number" name={xLabel} tickFormatter={formatTick(xFormat)} label={{ value: xLabel }} />
  <YAxis dataKey="y" type="number" name={yLabel} tickFormatter={formatTick(yFormat)} label={{ value: yLabel, angle: -90 }} />
  <ZAxis dataKey="z" range={[16, 1600]} name={zLabel} />  {/* range maps z values to pixel area: sqrt(area)=radius */}
  <Tooltip content={<CustomTooltip />} />
  {/* Group by color/shape: render one <Scatter> per group */}
  <Scatter
    data={circleData}
    fill={chartPalette[0]}
    isAnimationActive={false}
    onClick={(point) => onBubbleClick?.(point.id)}
  />
  <Scatter
    data={triangleData}
    shape={<TriangleShape />}
    fill={chartPalette[1]}
    isAnimationActive={false}
    onClick={(point) => onBubbleClick?.(point.id)}
  />
</ScatterChart>
```

Note: Recharts `<ZAxis range={[16, 1600]}>` maps the data's Z values to pixel AREA (not radius). The visible radius is `sqrt(area/π)`, so range [16, 1600] gives radii roughly 2–23 px. Adjust to fit the expected data range.

## Definition of Done

- [ ] Renders scatter plot with correct X, Y axes and labels
- [ ] Bubble size varies with Z value
- [ ] `shape='triangle'` renders a triangle SVG shape
- [ ] Hover tooltip shows all four dimensions
- [ ] `onBubbleClick` fires when bubble clicked
- [ ] `isLoading=true` shows ChartSkeleton
- [ ] Empty data shows EmptyState
- [ ] AccessibleTableToggle wraps chart
- [ ] jest-axe passes
- [ ] Tests green: `cd frontend && npm test -- --run src/components/viz/__tests__/BubbleScatter.test.tsx`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Test deltas

File: `frontend/src/components/viz/__tests__/BubbleScatter.test.tsx`

```typescript
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'jest-axe'
import { BubbleScatter } from '../BubbleScatter'

const mockData = [
  { id: 'c1', label: 'Campaign A', x: 1000, y: 2.5, z: 50000, shape: 'circle' as const },
  { id: 'c2', label: 'Campaign B', x: 2000, y: 1.8, z: 80000, shape: 'triangle' as const },
]

describe('BubbleScatter', () => {
  it('renders without errors', () => {
    const { container } = render(
      <BubbleScatter data={mockData} xLabel="Spend" yLabel="ROAS" zLabel="Impressions" />
    )
    expect(container.querySelector('.recharts-scatter-chart')).toBeInTheDocument()
  })

  it('fires onBubbleClick when bubble clicked', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(
      <BubbleScatter
        data={mockData}
        xLabel="Spend"
        yLabel="ROAS"
        zLabel="Impressions"
        onBubbleClick={onClick}
      />
    )
    // Click first scatter point — Recharts renders them as <circle> elements
    const circles = document.querySelectorAll('.recharts-symbols circle, .recharts-scatter-symbol')
    if (circles.length > 0) {
      await user.click(circles[0] as Element)
      expect(onClick).toHaveBeenCalled()
    }
  })

  it('shows ChartSkeleton when isLoading', () => {
    render(<BubbleScatter data={[]} xLabel="X" yLabel="Y" zLabel="Z" isLoading />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('shows EmptyState when data is empty', () => {
    render(<BubbleScatter data={[]} xLabel="X" yLabel="Y" zLabel="Z" emptyReasonCode="no_data_for_range" />)
    expect(screen.getByTestId('empty-state')).toHaveAttribute('data-reason-code', 'no_data_for_range')
  })

  it('has no a11y violations', async () => {
    const { container } = render(
      <BubbleScatter data={mockData} xLabel="Spend" yLabel="ROAS" zLabel="Impressions" />
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
```

## Out of scope

- Do NOT implement Z-value normalization — callers must normalize their own data
- Do NOT add a color legend for color-encoded groups — AccessibleTableToggle provides the accessible equivalent
- Do NOT implement quadrant lines or reference lines
