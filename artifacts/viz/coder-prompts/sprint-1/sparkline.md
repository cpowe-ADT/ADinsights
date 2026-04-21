# Sparkline Component

**Sprint:** 1
**Estimated size:** XS
**Depends on:** ChartSkeleton
**Blocks:** DataTable (inline sparklines), meta-campaigns (Sprint 2), google-ads-assets (Sprint 3), google-ads-campaigns (Sprint 3)
**Role needed:** frontend-engineer

## Context

`Sparkline` is a minimal inline chart used inside table cells to show trend at a glance. It renders a small `LineChart` from Recharts with no axes, no legend, and an optional tooltip on hover. It is used in `DataTable` columns and in the campaigns/assets pages.

## Inputs already in the repo (do not re-invent)

- `frontend/src/styles/chartTheme.ts`: import `chartPalette` for default color.
- `frontend/src/components/viz/ChartSkeleton.tsx`: use when `isLoading=true`.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/components/viz/Sparkline.tsx` (create)
  - `frontend/src/components/viz/__tests__/Sparkline.test.tsx` (create)

- **Props API**:
```typescript
interface SparklineProps {
  data: Array<{ date: string; value: number }>
  color?: string          // default: chartPalette[0] (#2563eb)
  height?: number         // default: 40
  width?: number          // default: 120
  showTooltip?: boolean   // default: false — tooltip adds weight, disable by default for table use
  isLoading?: boolean
  'aria-label'?: string   // for screen readers
}
```

- **Data binding**: caller passes the `data` array directly. No endpoint call inside this component.

- **Interactions**: if `showTooltip=true`, hovering shows a single-value tooltip with the `value` formatted as a number. No click.

- **Empty/loading/error states**:
  - `isLoading=true`: renders `<ChartSkeleton variant="line" height={height} />`
  - `data.length === 0`: renders a flat dashed line (SVG `<line>` — no Recharts needed for empty state)

- **A11y**: wrapper `<span>` with `role="img"` and `aria-label` prop (fallback: "Trend sparkline"). No keyboard interaction needed for the minimal `showTooltip=false` use case.

## Design

Recharts primitives used:
```
<LineChart width={width} height={height} data={data}>
  <Line
    type="monotone"
    dataKey="value"
    stroke={color}
    strokeWidth={1.5}
    dot={false}
    isAnimationActive={false}
  />
  {showTooltip && <Tooltip ... />}
</LineChart>
```

No axes, no grid, no legend. `isAnimationActive={false}` to prevent flicker inside table rows.

## Definition of Done

- [ ] Renders a Recharts line with no axes when given valid `data`
- [ ] Renders ChartSkeleton when `isLoading=true`
- [ ] Renders flat dashed line when `data` is empty
- [ ] `aria-label` present on wrapper
- [ ] `showTooltip=false` by default (no tooltip DOM node rendered)
- [ ] jest-axe passes
- [ ] Tests green: `cd frontend && npm test -- --run src/components/viz/__tests__/Sparkline.test.tsx`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Test deltas

File: `frontend/src/components/viz/__tests__/Sparkline.test.tsx`

```typescript
import { render, screen } from '@testing-library/react'
import { axe } from 'jest-axe'
import { Sparkline } from '../Sparkline'

const mockData = [
  { date: '2026-01-01', value: 100 },
  { date: '2026-01-02', value: 120 },
  { date: '2026-01-03', value: 110 },
]

describe('Sparkline', () => {
  it('renders without errors with data', () => {
    const { container } = render(<Sparkline data={mockData} aria-label="Spend trend" />)
    expect(container.firstChild).toBeInTheDocument()
  })

  it('renders ChartSkeleton when isLoading', () => {
    render(<Sparkline data={[]} isLoading aria-label="Loading" />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders empty state when data is empty and not loading', () => {
    const { container } = render(<Sparkline data={[]} aria-label="No data" />)
    // flat line indicator present
    expect(container.querySelector('[data-testid="sparkline-empty"]')).toBeInTheDocument()
  })

  it('has role="img" wrapper', () => {
    render(<Sparkline data={mockData} aria-label="Spend trend" />)
    expect(screen.getByRole('img')).toBeInTheDocument()
  })

  it('has no a11y violations', async () => {
    const { container } = render(<Sparkline data={mockData} aria-label="Spend trend" />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
```

## Out of scope

- Do NOT add axis labels or ticks
- Do NOT implement click-to-expand
- Do NOT display the date labels
