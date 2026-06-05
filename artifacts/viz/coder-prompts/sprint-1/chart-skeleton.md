# ChartSkeleton Component

**Sprint:** 1
**Estimated size:** S
**Depends on:** none
**Blocks:** TrendLine, DistributionBar, PieComposition, BubbleScatter, DataTable, KpiTile
**Role needed:** frontend-engineer

## Context

`ChartSkeleton` provides loading shimmer placeholders that match the exact footprint of their target chart, preventing layout shift during data fetch. Every chart component in the viz kit uses `ChartSkeleton` internally when `isLoading=true`. It renders CSS-animated shimmer shapes, not actual chart primitives.

## Inputs already in the repo (do not re-invent)

- `frontend/src/styles/chartTheme.ts`: do not read — ChartSkeleton uses only neutral gray, no palette tokens.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/components/viz/ChartSkeleton.tsx` (create)
  - `frontend/src/components/viz/__tests__/ChartSkeleton.test.tsx` (create)

- **Props API**:

```typescript
type SkeletonVariant =
  | 'line'
  | 'bar'
  | 'pie'
  | 'table'
  | 'kpi-strip'
  | 'bubble';

interface ChartSkeletonProps {
  height?: number; // default varies by variant
  rows?: number; // for 'table' variant: number of skeleton rows, default 8
  columns?: number; // for 'table' variant: number of columns, default 5
  variant?: SkeletonVariant; // default 'line'
  className?: string;
}
```

- **Data binding**: none — purely presentational

- **Interactions**: none

- **Empty/loading/error states**: this component IS the loading state

- **A11y**: `role="status"` + `aria-label="Loading chart data"` on root. `aria-busy="true"`.

## Design

Each variant produces a different shimmer layout:

**kpi-strip**: 4–6 horizontal shimmer rectangles side by side, each 80px tall, rounded corners, 12px gap between.

**line**: one legend strip (2 short rectangles) + one large rectangle below (full width, configurable height default 260px).

**bar**: full-width rectangle (height default 200px) with subtle horizontal stripes to suggest bars.

**pie**: centered circle (radius ~80px) + 4 small legend items to the right.

**table**: column header strip + `rows` rows of alternating-width shimmer lines.

**bubble**: full-width rectangle with scattered circle outlines (SVG) inside.

CSS shimmer animation:

```css
@keyframes shimmer {
  0% {
    background-position: -400px 0;
  }
  100% {
    background-position: 400px 0;
  }
}
.shimmer {
  background: linear-gradient(90deg, #e5e7eb 25%, #f9fafb 50%, #e5e7eb 75%);
  background-size: 800px 100%;
  animation: shimmer 1.5s infinite;
}
```

Inject via a `<style>` tag or Tailwind's `animate-pulse` class if `animate-pulse` is already in the project's Tailwind config.

## Definition of Done

- [ ] All 6 variants render without errors (snapshot tests for each)
- [ ] Root element has `role="status"` and `aria-label="Loading chart data"`
- [ ] No layout shift when skeleton swaps to actual chart at same `height`
- [ ] jest-axe passes for each variant
- [ ] Tests green: `cd frontend && npm test -- --run src/components/viz/__tests__/ChartSkeleton.test.tsx`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Test deltas

File: `frontend/src/components/viz/__tests__/ChartSkeleton.test.tsx`

```typescript
import { render, screen } from '@testing-library/react'
import { axe } from 'jest-axe'
import { ChartSkeleton } from '../ChartSkeleton'

const variants = ['line', 'bar', 'pie', 'table', 'kpi-strip', 'bubble'] as const

describe('ChartSkeleton', () => {
  variants.forEach(variant => {
    it(`renders ${variant} variant without errors`, () => {
      const { container } = render(<ChartSkeleton variant={variant} />)
      expect(container.firstChild).toBeInTheDocument()
    })
  })

  it('has role="status" and aria-label', () => {
    render(<ChartSkeleton />)
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Loading chart data')
  })

  it('table variant renders correct number of rows', () => {
    const { container } = render(<ChartSkeleton variant="table" rows={5} />)
    // 5 row shimmer divs inside the table skeleton
    expect(container.querySelectorAll('[data-testid="skeleton-row"]')).toHaveLength(5)
  })

  it('has no a11y violations (line variant)', async () => {
    const { container } = render(<ChartSkeleton variant="line" />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
```

## Out of scope

- Do NOT use any chart library (Recharts etc.) for the skeleton shapes
- Do NOT add new CSS files — use inline styles or Tailwind classes only
- Do NOT animate with JavaScript — CSS animation only
